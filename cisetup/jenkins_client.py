from __future__ import annotations

import base64
import http
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any
from xml.sax.saxutils import escape as _sax_escape

from .models import CISetupConfig, CISetupSecrets
from .template_store import read_template

REQUIRED_PLUGINS = [
    "workflow-aggregator",
    "git",
    "credentials-binding",
    "plain-credentials",
    "parameterized-trigger",
    "naginator",
]

TRIGGER_JOB_SUFFIX = "-trigger"


def trigger_job_name(job_name: str) -> str:
    """cron 失敗時リトライ用ラッパー Freestyle ジョブの名前（本体ジョブ名 + サフィックス）。"""
    return f"{job_name}{TRIGGER_JOB_SUFFIX}"


def build_job_triggers_xml(config: CISetupConfig) -> str:
    """Pipeline ジョブ XML 用のトリガー断片（pollSCM / cron）。

    Jenkinsfile の triggers は「Jenkins に反映」でジョブ XML を上書きすると登録が消えうるため、
    poll（SCMTrigger）と cron（TimerTrigger）をジョブ XML 側に持たせる。
    retry_wrapper_enabled 時の cron はラッパー Freestyle ジョブ側のみ（二重起動防止）。
    """
    parts: list[str] = []
    poll = config.jenkins.poll_schedule.strip()
    if poll:
        parts.append(
            "    <hudson.triggers.SCMTrigger>\n"
            f"      <spec>{_escape_xml(poll)}</spec>\n"
            "      <ignorePostCommitHooks>false</ignorePostCommitHooks>\n"
            "    </hudson.triggers.SCMTrigger>"
        )
    if not config.jenkins.retry_wrapper_enabled:
        cron = config.jenkins.cron_schedule.strip()
        if cron:
            tz = config.jenkins.timezone.strip() or "Asia/Tokyo"
            parts.append(
                "    <hudson.triggers.TimerTrigger>\n"
                f"      <spec>TZ={_escape_xml(tz)}\n{_escape_xml(cron)}</spec>\n"
                "    </hudson.triggers.TimerTrigger>"
            )
    return "\n".join(parts)


def _escape_xml(value: str) -> str:
    """C# の SecurityElement.Escape 相当（< > & " ' をすべてエスケープ）。"""
    return _sax_escape(value, {'"': "&quot;", "'": "&apos;"})


def _escape_groovy(value: str) -> str:
    """Groovy シングルクォート文字列へ安全に埋め込むためのエスケープ。

    Windows パスはバックスラッシュを多く含むため \\ と ' のエスケープは必須。
    """
    return value.replace("\\", "\\\\").replace("'", "\\'")


class JenkinsError(RuntimeError):
    pass


class JenkinsHTTPError(JenkinsError):
    """HTTP ステータス非成功（4xx/5xx）。C# の応答 IsSuccessStatusCode=false 相当。"""

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


class JenkinsConnectionError(JenkinsError):
    """サーバーへ到達できない接続エラー。C# では例外がそのまま伝播する。"""


@dataclass
class JenkinsServerSetupResult:
    log: list[str] = field(default_factory=list)
    agent_launch_command: str = ""
    requires_plugin_restart: bool = False


def _strip_html(html: str) -> str:
    if not html.strip():
        return ""
    if "<" not in html:
        return html.strip()
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def format_jenkins_error(status: int, body: str) -> str:
    plain = _strip_html(body)
    if status == 401 or "unauthorized" in plain.lower():
        return (
            "Jenkins 認証エラー (401 Unauthorized)\n\n"
            "次を確認してください:\n"
            "• Jenkins URL（例: http://localhost:8086）\n"
            "• ユーザー名\n"
            "• API Token（パスワードではなく Token）\n\n"
            "Token の再発行: Jenkins → ユーザー名 → Configure → API Token → Add new Token"
        )
    if status == 403 or "forbidden" in plain.lower():
        return (
            "Jenkins 権限エラー (403 Forbidden)\n\n"
            "ログインユーザーに次の権限があるか確認してください:\n"
            "• Overall/Administer または Credentials の作成・更新\n"
            "• Job の作成・更新\n\n"
            "Manage Jenkins → Security で管理者権限を付与してください。"
        )
    if plain and len(plain) < 500:
        return f"Jenkins API エラー ({status}): {plain}"
    return f"Jenkins API エラー: {status} {_status_name(status)}".rstrip()


def _status_name(status: int) -> str:
    """.NET の HttpStatusCode.ToString()（例: 404→NotFound）相当の名前を返す。"""
    try:
        return http.HTTPStatus(status).phrase.replace(" ", "")
    except ValueError:
        return ""


def extract_agent_secret(jnlp: str) -> str:
    """Jenkins エージェント JNLP から -secret 引数を取り出す。"""
    arguments = [m.group(1).strip() for m in re.finditer(r"<argument[^>]*>([^<]*)</argument>", jnlp)]
    for i in range(len(arguments) - 1):
        if arguments[i].lower() == "-secret" and arguments[i + 1].strip():
            return arguments[i + 1]
    raise JenkinsError("エージェント secret を取得できませんでした。")


class JenkinsClient:
    def __init__(self, secrets: CISetupSecrets, timeout: float = 30.0) -> None:
        if not secrets.jenkins_url.strip():
            raise ValueError("Jenkins URL を入力してください。")
        if not secrets.jenkins_user.strip() or not secrets.jenkins_api_token.strip():
            raise ValueError("Jenkins ユーザー名と API Token を入力してください。")

        base = secrets.jenkins_url.strip().rstrip("/") + "/"
        parsed = urllib.parse.urlparse(base)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(
                "Jenkins URL の形式が正しくありません。\n"
                "http:// または https:// で始まる URL を入力してください。"
            )

        self._base = base
        self._timeout = timeout
        self._secrets = secrets
        token = base64.b64encode(
            f"{secrets.jenkins_user}:{secrets.jenkins_api_token}".encode("ascii")
        ).decode("ascii")
        self._headers = {
            "Authorization": f"Basic {token}",
            "User-Agent": "CISetup-Python/1.0",
        }
        self._crumb: str | None = None

    # --- low-level ---

    def _request(
        self,
        method: str,
        path: str,
        data: bytes | None = None,
        content_type: str | None = None,
        form: dict[str, str] | None = None,
    ) -> Any:
        url = urllib.parse.urljoin(self._base, path)
        headers = dict(self._headers)
        body = data

        if form is not None:
            body = urllib.parse.urlencode(form).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if content_type:
            headers["Content-Type"] = content_type
        if self._crumb:
            headers["Jenkins-Crumb"] = self._crumb

        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read()
                if not raw:
                    return None
                text = raw.decode("utf-8", errors="replace")
                stripped = text.lstrip()
                if stripped.startswith("{") or stripped.startswith("["):
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return text
                return text
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise JenkinsHTTPError(format_jenkins_error(exc.code, detail), exc.code) from exc
        except urllib.error.URLError as exc:
            raise JenkinsConnectionError(
                "Jenkins サーバーに接続できませんでした。\n"
                "• URL が正しいか（http/https・ポート番号）\n"
                "• サーバーが起動しているか\n"
                "• ネットワーク / VPN / ファイアウォール\n\n"
                f"詳細: {exc.reason}"
            ) from exc

    def _ensure_crumb(self) -> None:
        if self._crumb is not None:
            return
        try:
            data = self._request("GET", "crumbIssuer/api/json")
            self._crumb = data.get("crumb", "") if isinstance(data, dict) else ""
        except JenkinsError:
            self._crumb = ""

    def _post_xml(self, path: str, xml: str) -> None:
        self._ensure_crumb()
        self._request("POST", path, data=xml.encode("utf-8"), content_type="application/xml; charset=utf-8")

    def run_groovy(self, script: str) -> str:
        self._ensure_crumb()
        result = self._request("POST", "scriptText", form={"script": script})
        return (result if isinstance(result, str) else json.dumps(result)).strip()

    def set_global_env_var(self, name: str, value: str) -> None:
        """Jenkins 本体のグローバル環境変数（Global properties）を upsert する。

        別 PC・共有アクセス不可のエージェントへ CI_FILE_SERVER を届ける手段。
        値が空なら何もしない。失敗時は run_groovy 経由で既存のエラー型が伝播する。
        """
        if not value.strip():
            return
        self.run_groovy(_set_global_env_var_script(name, value))

    # --- connection ---

    def test_connection(self) -> None:
        self._request("GET", "api/json")

    # --- credentials ---

    def _credential_exists(self, credential_id: str) -> bool:
        encoded = urllib.parse.quote(credential_id, safe="")
        try:
            self._request("GET", f"credentials/store/system/domain/_/credential/{encoded}/api/json")
            return True
        except JenkinsHTTPError:
            return False

    def _upsert_credential(self, credential_id: str, xml: str) -> None:
        encoded = urllib.parse.quote(credential_id, safe="")
        exists = self._credential_exists(credential_id)
        path = (
            f"credentials/store/system/domain/_/credential/{encoded}/config.xml"
            if exists
            else "credentials/store/system/domain/_/createCredentials"
        )
        self._post_xml(path, xml)

    def upsert_string_credential(self, credential_id: str, secret_value: str, description: str) -> None:
        if not secret_value.strip():
            return
        xml = f"""<org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl plugin="plain-credentials">
  <scope>GLOBAL</scope>
  <id>{_escape_xml(credential_id)}</id>
  <secret>{_escape_xml(secret_value)}</secret>
  <description>{_escape_xml(description)}</description>
</org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl>"""
        self._upsert_credential(credential_id, xml)

    def upsert_username_password_credential(
        self, credential_id: str, username: str, password: str, description: str
    ) -> None:
        if not username.strip():
            return
        xml = f"""<com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl>
  <scope>GLOBAL</scope>
  <id>{_escape_xml(credential_id)}</id>
  <description>{_escape_xml(description)}</description>
  <username>{_escape_xml(username)}</username>
  <password>{_escape_xml(password)}</password>
</com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl>"""
        self._upsert_credential(credential_id, xml)

    # --- pipeline job ---

    def _job_exists(self, job_name: str) -> bool:
        encoded = urllib.parse.quote(job_name, safe="")
        try:
            self._request("GET", f"job/{encoded}/api/json")
            return True
        except JenkinsHTTPError:
            return False

    def disable_job_if_exists(self, job_name: str) -> None:
        """ジョブが存在すれば無効化する（retry ラッパー OFF 時の残骸対策）。"""
        if not job_name.strip() or not self._job_exists(job_name):
            return
        encoded = urllib.parse.quote(job_name, safe="")
        self._ensure_crumb()
        self._request("POST", f"job/{encoded}/disable")

    def upsert_pipeline_job(self, config: CISetupConfig) -> None:
        template = read_template("JenkinsJob.config.template.xml")
        job_xml = (
            template.replace("{{GIT_URL}}", _escape_xml(config.git.repository_url))
            .replace("{{GIT_CREDENTIAL_ID}}", _escape_xml(config.git.credential_id))
            .replace("{{GIT_BRANCH}}", _escape_xml(config.git.branch))
            .replace("{{JOB_TRIGGERS}}", build_job_triggers_xml(config))
        )
        encoded = urllib.parse.quote(config.jenkins.job_name, safe="")
        exists = self._job_exists(config.jenkins.job_name)
        path = f"job/{encoded}/config.xml" if exists else f"createItem?name={encoded}"
        self._post_xml(path, job_xml)

    def upsert_trigger_job(self, config: CISetupConfig) -> None:
        """cron 失敗時に Naginator で再試行するラッパー Freestyle ジョブを作成/更新する。

        Pipeline ジョブ（flow-definition）は Naginator の失敗時リトライに対応しておらず、
        かつ Jenkinsfile 取得自体の失敗は Pipeline 開始前に起きるため Pipeline 内の retry()
        でも救えない。そのため cron はこちらのジョブに持たせ、本体ジョブを起動・待機し、
        失敗したら Naginator が本ジョブごと再試行する構成にする。
        """
        template = read_template("JenkinsTriggerJob.config.template.xml")
        timezone = config.jenkins.timezone.strip() or "Asia/Tokyo"
        job_xml = (
            template.replace("{{PIPELINE_JOB_NAME}}", _escape_xml(config.jenkins.job_name))
            .replace("{{TIMEZONE}}", _escape_xml(timezone))
            .replace("{{CRON_SCHEDULE}}", _escape_xml(config.jenkins.cron_schedule))
            .replace("{{RETRY_COUNT}}", str(max(1, config.jenkins.retry_max_count)))
            .replace("{{RETRY_DELAY_SECONDS}}", str(max(1, config.jenkins.retry_delay_seconds)))
        )
        name = trigger_job_name(config.jenkins.job_name)
        encoded = urllib.parse.quote(name, safe="")
        exists = self._job_exists(name)
        path = f"job/{encoded}/config.xml" if exists else f"createItem?name={encoded}"
        self._post_xml(path, job_xml)

    def trigger_build(self, job_name: str, publish_release: bool = False) -> str:
        if not job_name.strip():
            raise ValueError("ジョブ名が空です。⑧ CI ジョブ設定でジョブ名を入力してください。")
        encoded = urllib.parse.quote(job_name, safe="")
        if not self._job_exists(job_name):
            raise ValueError(
                f"ジョブ '{job_name}' が Jenkins に見つかりません。\n"
                "先に「② Jenkins に設定を反映」を実行してジョブを作成してください。"
            )
        self._ensure_crumb()
        try:
            self._request(
                "POST",
                f"job/{encoded}/buildWithParameters",
                form={"PUBLISH_RELEASE": "true" if publish_release else "false"},
            )
        except JenkinsHTTPError:
            # 初回ビルド前はパラメータ未登録で buildWithParameters が失敗するため通常 build に
            # フォールバックする。接続エラー（JenkinsConnectionError）はそのまま伝播させる。
            self._request("POST", f"job/{encoded}/build")
        return f"{self._base}job/{encoded}/"

    # --- server setup ---

    def _agent_exists(self, agent_name: str) -> bool:
        encoded = urllib.parse.quote(agent_name, safe="")
        try:
            self._request("GET", f"computer/{encoded}/api/json")
            return True
        except JenkinsHTTPError:
            return False

    def _upsert_agent_node(self, agent_name: str, remote_root: str, label: str) -> None:
        xml = f"""<slave>
  <name>{_escape_xml(agent_name)}</name>
  <description>CISetup Windows Agent</description>
  <remoteFS>{_escape_xml(remote_root)}</remoteFS>
  <numExecutors>1</numExecutors>
  <mode>NORMAL</mode>
  <retentionStrategy class="hudson.slaves.RetentionStrategy$Always"/>
  <launcher class="hudson.slaves.JNLPLauncher">
    <workDirSettings>
      <disabled>false</disabled>
      <workDirPath></workDirPath>
      <internalDir>remoting</internalDir>
      <failIfWorkDirIsMissing>false</failIfWorkDirIsMissing>
    </workDirSettings>
  </launcher>
  <label>{_escape_xml(label)}</label>
  <nodeProperties/>
</slave>"""
        self._ensure_crumb()
        encoded = urllib.parse.quote(agent_name, safe="")
        exists = self._agent_exists(agent_name)
        path = (
            f"computer/{encoded}/config.xml"
            if exists
            else f"computer/doCreateItem?name={encoded}&type=hudson.slaves.DumbSlave"
        )
        self._post_xml(path, xml)

    def _build_agent_launch_command(self, agent_name: str, remote_root: str) -> str:
        encoded = urllib.parse.quote(agent_name, safe="")
        jnlp = self._request("GET", f"computer/{encoded}/jenkins-agent.jnlp")
        secret = extract_agent_secret(jnlp if isinstance(jnlp, str) else json.dumps(jnlp))
        base_url = self._secrets.jenkins_url.strip().rstrip("/")
        agent_jar_url = f"{base_url}/jnlpJars/agent.jar"
        return (
            "# Windows エージェント PC で実行（Java 11+ 必要）\n"
            "# 事前: .NET SDK 8 + Git をインストール\n"
            f'Invoke-WebRequest -Uri "{agent_jar_url}" -OutFile agent.jar\n'
            f'java -jar agent.jar -url "{base_url}/" -secret {secret} '
            f'-name "{agent_name}" -workDir "{remote_root}"'
        )

    def setup_server(
        self,
        config: CISetupConfig,
        agent_name: str,
        agent_remote_root: str,
    ) -> JenkinsServerSetupResult:
        result = JenkinsServerSetupResult()

        result.log.append("==> Jenkins 接続確認")
        self._request("GET", "api/json")

        version_json = self._request("GET", "api/json?tree=version")
        if isinstance(version_json, dict) and version_json.get("version"):
            result.log.append(f"Jenkins バージョン: {version_json['version']}")

        result.log.append("==> 必須プラグイン確認・インストール")
        plugin_result = self.run_groovy(_install_plugins_script())
        result.log.append(plugin_result)
        result.requires_plugin_restart = "restart" in plugin_result.lower()

        result.log.append("==> Jenkins URL 設定")
        location_result = self.run_groovy(
            _set_location_script(self._secrets.jenkins_url.strip().rstrip("/"))
        )
        result.log.append(location_result)

        label = (config.jenkins.agent_label or "").strip()
        label_display = "任意ノード用（ラベルなし）" if not label else label

        result.log.append(f"==> Windows エージェント登録: {agent_name}")
        self._upsert_agent_node(agent_name, agent_remote_root, label)
        result.log.append(f"エージェント '{agent_name}' を登録しました（ラベル: {label_display}）")

        result.log.append("==> エージェント起動コマンド取得")
        result.agent_launch_command = self._build_agent_launch_command(agent_name, agent_remote_root)
        result.log.append("エージェント PC で以下のコマンドを実行してください。")

        return result


def _install_plugins_script() -> str:
    plugin_list = "','".join(REQUIRED_PLUGINS)
    return f"""def required = ['{plugin_list}'] as String[]
def pm = jenkins.model.Jenkins.instance.pluginManager
def uc = pm.updateCenter
def installed = []
def missing = []
required.each {{ id ->
  def p = pm.getPlugin(id)
  if (p == null) {{ missing << id }} else {{ installed << id }}
}}
if (missing.isEmpty()) {{
  return 'OK: all plugins already installed (' + installed.join(', ') + ')'
}}
def deployed = []
missing.each {{ id ->
  def p = uc.getPlugin(id)
  if (p == null) {{ return }}
  def future = p.deploy()
  if (future != null) {{ future.get() }}
  deployed << id
}}
def needsRestart = pm.isRestartRequiredForCompletion()
return 'INSTALLED: ' + deployed.join(', ') + (needsRestart ? ' | RESTART required' : '')"""


def _set_location_script(jenkins_url: str) -> str:
    escaped = jenkins_url.replace("\\", "\\\\").replace("'", "\\'")
    return f"""def loc = jenkins.model.JenkinsLocationConfiguration.get()
loc.setUrl('{escaped}')
loc.save()
return 'OK: Jenkins URL set to {escaped}'"""


def _set_global_env_var_script(name: str, value: str) -> str:
    """グローバルノードプロパティに環境変数を upsert する Groovy を生成する。"""
    name_g = _escape_groovy(name)
    value_g = _escape_groovy(value)
    return f"""import jenkins.model.*
import hudson.slaves.EnvironmentVariablesNodeProperty
def instance = Jenkins.get()
def gp = instance.getGlobalNodeProperties()
def list = gp.getAll(EnvironmentVariablesNodeProperty.class)
def envVars
if (list == null || list.isEmpty()) {{
    def prop = new EnvironmentVariablesNodeProperty()
    gp.add(prop)
    envVars = prop.getEnvVars()
}} else {{
    envVars = list.get(0).getEnvVars()
}}
envVars.put('{name_g}', '{value_g}')
instance.save()
return 'OK: {name_g} set'"""


def test_file_server_write(unc_path: str) -> str:
    import uuid
    from pathlib import Path

    from . import paths

    if not unc_path.strip():
        raise ValueError("CI_FILE_SERVER（UNC パス）を入力してください。")

    if paths.is_url(unc_path):
        raise ValueError(
            "書き込み先には UNC またはローカルパスを指定してください（共有 URL には書き込みできません）。\n"
            "OneDrive/SharePoint は同期済みローカルフォルダのパスを指定し、"
            "共有 URL は各 URL 欄に入力してください。"
        )

    test_file = Path(unc_path.strip()) / f"cisetup-write-test-{uuid.uuid4().hex}.txt"
    test_file.write_text("CISetup write test", encoding="utf-8")
    test_file.unlink()
    return f"書き込み OK: {unc_path}"


def apply_settings(config: CISetupConfig, secrets: CISetupSecrets) -> None:
    if not config.git.repository_url.strip():
        raise ValueError("Git リポジトリ URL を GUI で入力してください。")

    client = JenkinsClient(secrets)
    client.upsert_string_credential(
        config.jenkins.teams_credential_id,
        secrets.teams_webhook_url,
        "Teams Webhook (CISetup)",
    )
    client.upsert_username_password_credential(
        config.git.credential_id,
        secrets.git_username,
        secrets.git_password,
        "Git (CISetup)",
    )
    client.upsert_pipeline_job(config)
    if config.jenkins.retry_wrapper_enabled:
        client.upsert_trigger_job(config)
    else:
        client.disable_job_if_exists(trigger_job_name(config.jenkins.job_name))
    # 別 PC/共有不可のエージェント向け: 先頭の書き込み先を Jenkins グローバル環境変数へ登録する。
    # 環境変数は単一値のため先頭のみ push する（複数先が必要な場合は兄弟パス配置を使う）。
    if config.jenkins.push_ci_file_server_env and config.jenkins.ci_file_server.strip():
        client.set_global_env_var("CI_FILE_SERVER", config.jenkins.ci_file_server)
