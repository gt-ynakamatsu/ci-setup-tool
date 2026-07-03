from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any


@dataclass
class BuildConfig:
    preset: str = "dotnet"
    profile: str = "dotnet"
    build_command: str = ""
    lint_command: str = ""
    analyze_command: str = ""
    publish_command: str = ""
    test_command: str = ""
    artifact_glob: str = ""


@dataclass
class ProjectConfig:
    name: str = ""
    solution_file: str = ""
    publish_project: str = ""
    test_project: str = ""
    artifact_prefix: str = ""


@dataclass
class StorageConfig:
    # 書き込み先（base_paths）と閲覧用 URL（*_urls）は複数指定できる（後方互換で単一文字列も読める）。
    base_paths: list[str] = field(default_factory=list)
    logs_dir: str = "logs"
    releases_dir: str = "releases"
    tests_dir: str = "tests"
    source_dir: str = "source"
    use_date_subfolder: bool = True
    # pull した最新ソースツリーを zip 化して保存するか（個人 ID を含まない通常設定）。
    archive_source: bool = False
    release_urls: list[str] = field(default_factory=list)
    analysis_urls: list[str] = field(default_factory=list)
    logs_urls: list[str] = field(default_factory=list)
    tests_urls: list[str] = field(default_factory=list)

    # --- 後方互換アクセサ（旧コード/設定の単一文字列向け。先頭要素を見る/設定する）---
    @property
    def base_path(self) -> str:
        return self.base_paths[0] if self.base_paths else ""

    @base_path.setter
    def base_path(self, value: str) -> None:
        self.base_paths = _single_to_list(value)

    @property
    def release_url(self) -> str:
        return self.release_urls[0] if self.release_urls else ""

    @release_url.setter
    def release_url(self, value: str) -> None:
        self.release_urls = _single_to_list(value)

    @property
    def analysis_url(self) -> str:
        return self.analysis_urls[0] if self.analysis_urls else ""

    @analysis_url.setter
    def analysis_url(self, value: str) -> None:
        self.analysis_urls = _single_to_list(value)

    @property
    def logs_url(self) -> str:
        return self.logs_urls[0] if self.logs_urls else ""

    @logs_url.setter
    def logs_url(self, value: str) -> None:
        self.logs_urls = _single_to_list(value)

    @property
    def tests_url(self) -> str:
        return self.tests_urls[0] if self.tests_urls else ""

    @tests_url.setter
    def tests_url(self, value: str) -> None:
        self.tests_urls = _single_to_list(value)


@dataclass
class JenkinsConfig:
    job_name: str = "CISetup-CI"
    agent_label: str = ""
    cron_schedule: str = "0 0 * * *"
    poll_schedule: str = "H/5 * * * *"
    # 書き込み先サーバーは複数指定できる（後方互換で単一文字列 ciFileServer も読める）。
    ci_file_servers: list[str] = field(default_factory=lambda: [r"\\fileserver\ci"])
    teams_credential_id: str = "teams-webhook-url"
    default_configuration: str = "Release"
    build_timeout_minutes: int = 30
    log_retention_count: int = 30
    timezone: str = "Asia/Tokyo"
    # Jenkinsfile 取得前の "Checkout" ステージで一時的な Git エラー（ネットワーク/サーバー瞬断）
    # が起きた際に何回まで自動リトライするか。
    checkout_retry_count: int = 3
    # true の場合、cron トリガーは Jenkinsfile 側ではなく別建てのトリガー用ジョブ
    # （JenkinsTriggerJob）に持たせ、Naginator の失敗時リトライで再実行できるようにする。
    # Jenkinsfile 取得自体が失敗するケース（Pipeline 開始前）はこちらでしか救えないため。
    retry_wrapper_enabled: bool = False
    retry_max_count: int = 3
    retry_delay_seconds: int = 300
    # 同一 PC で Jenkins エージェントを動かす場合の、エージェントのワークスペースパス。
    # 機械固有・git 非追跡。書き込み先設定(cisetup.local.json)をワイプで消えない兄弟パスへ
    # 自動配置する用途にのみ使い、Jenkinsfile/config には残さない（save_all で committed を空にする）。
    agent_workspace_path: str = ""
    # true の場合、「Jenkinsに反映」時に先頭の書き込み先を Jenkins 本体のグローバル環境変数
    # CI_FILE_SERVER として登録する（別 PC/共有不可のエージェント向け）。個人 ID ではないため
    # committed config.json に保存する（save_all で strip しない）。
    push_ci_file_server_env: bool = False

    @property
    def ci_file_server(self) -> str:
        return self.ci_file_servers[0] if self.ci_file_servers else ""

    @ci_file_server.setter
    def ci_file_server(self, value: str) -> None:
        self.ci_file_servers = _single_to_list(value)


@dataclass
class GitConfig:
    repository_url: str = ""
    branch: str = "main"
    credential_id: str = "internal-git"


@dataclass
class CISetupConfig:
    project: ProjectConfig = field(default_factory=ProjectConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    jenkins: JenkinsConfig = field(default_factory=JenkinsConfig)
    git: GitConfig = field(default_factory=GitConfig)
    build: BuildConfig = field(default_factory=BuildConfig)


@dataclass
class CISetupSecrets:
    jenkins_url: str = ""
    jenkins_user: str = ""
    jenkins_api_token: str = ""
    git_username: str = ""
    git_password: str = ""
    teams_webhook_url: str = ""


@dataclass
class CISetupLocal:
    """個人 ID / マシン固有の値（git に push しないローカル設定）。

    OneDrive 等の書き込み先パスは個人名 ID を含むことがあるため、
    コミットされる cisetup.config.json には保存せず、このローカルファイルに保持する。
    書き込み先は複数指定できる（後方互換で単一文字列キーも読める）。
    """

    base_paths: list[str] = field(default_factory=list)
    ci_file_servers: list[str] = field(default_factory=list)
    # 同一 PC の Jenkins エージェントのワークスペースパス（機械固有・git 非追跡）。
    agent_workspace_path: str = ""

    @property
    def base_path(self) -> str:
        return self.base_paths[0] if self.base_paths else ""

    @base_path.setter
    def base_path(self, value: str) -> None:
        self.base_paths = _single_to_list(value)

    @property
    def ci_file_server(self) -> str:
        return self.ci_file_servers[0] if self.ci_file_servers else ""

    @ci_file_server.setter
    def ci_file_server(self, value: str) -> None:
        self.ci_file_servers = _single_to_list(value)


# --- 複数値（リスト）ヘルパ：単一文字列⇔リストの正規化と後方互換読み込み ---

def _single_to_list(value: str) -> list[str]:
    s = (value or "").strip()
    return [s] if s else []


def _as_str_list(value: Any) -> list[str]:
    """JSON 値（文字列 or 配列）を空要素を除いた文字列リストに正規化する。"""
    if value is None:
        return []
    if isinstance(value, str):
        s = value.strip()
        return [s] if s else []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _coalesce_list(data: dict[str, Any], *camel_keys: str) -> list[str]:
    """複数形→旧単数形の順にキーを探し、最初に値があるものをリストとして返す。"""
    for key in camel_keys:
        if key in data:
            values = _as_str_list(data[key])
            if values:
                return values
    return []


# --- camelCase <-> snake_case 変換（C# 版 JSON と相互運用するため） ---

def _snake_to_camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in rest)


def _camel_to_snake(name: str) -> str:
    out: list[str] = []
    for ch in name:
        if ch.isupper():
            out.append("_")
            out.append(ch.lower())
        else:
            out.append(ch)
    return "".join(out)


def _to_camel_dict(obj: Any) -> Any:
    if is_dataclass(obj):
        result: dict[str, Any] = {}
        for f in fields(obj):
            result[_snake_to_camel(f.name)] = _to_camel_dict(getattr(obj, f.name))
        return result
    return obj


def _from_camel_dict(cls: type, data: dict[str, Any] | None) -> Any:
    if not data:
        return cls()
    field_names = {f.name for f in fields(cls)}
    kwargs: dict[str, Any] = {}
    for raw_key, value in data.items():
        snake = _camel_to_snake(raw_key)
        if snake in field_names:
            kwargs[snake] = value
    return cls(**kwargs)


def _storage_from_dict(data: dict[str, Any] | None) -> StorageConfig:
    data = data or {}
    storage = _from_camel_dict(StorageConfig, data)
    # 書き込み先・閲覧 URL は複数対応（旧単一キーも読む）。
    storage.base_paths = _coalesce_list(data, "basePaths", "basePath")
    storage.release_urls = _coalesce_list(data, "releaseUrls", "releaseUrl")
    storage.analysis_urls = _coalesce_list(data, "analysisUrls", "analysisUrl")
    storage.logs_urls = _coalesce_list(data, "logsUrls", "logsUrl")
    storage.tests_urls = _coalesce_list(data, "testsUrls", "testsUrl")
    return storage


def _jenkins_from_dict(data: dict[str, Any] | None) -> JenkinsConfig:
    data = data or {}
    jenkins = _from_camel_dict(JenkinsConfig, data)
    jenkins.ci_file_servers = _coalesce_list(data, "ciFileServers", "ciFileServer")
    return jenkins


def config_from_dict(data: dict[str, Any]) -> CISetupConfig:
    return CISetupConfig(
        project=_from_camel_dict(ProjectConfig, data.get("project")),
        storage=_storage_from_dict(data.get("storage")),
        jenkins=_jenkins_from_dict(data.get("jenkins")),
        git=_from_camel_dict(GitConfig, data.get("git")),
        build=_from_camel_dict(BuildConfig, data.get("build")),
    )


def secrets_from_dict(data: dict[str, Any]) -> CISetupSecrets:
    return _from_camel_dict(CISetupSecrets, data)


def config_to_dict(config: CISetupConfig) -> dict[str, Any]:
    return _to_camel_dict(config)


def secrets_to_dict(secrets: CISetupSecrets) -> dict[str, Any]:
    return _to_camel_dict(secrets)


def local_from_dict(data: dict[str, Any]) -> CISetupLocal:
    data = data or {}
    local = CISetupLocal()
    local.base_paths = _coalesce_list(data, "basePaths", "basePath")
    local.ci_file_servers = _coalesce_list(data, "ciFileServers", "ciFileServer")
    local.agent_workspace_path = str(data.get("agentWorkspacePath", "") or "").strip()
    return local


def local_to_dict(local: CISetupLocal) -> dict[str, Any]:
    return _to_camel_dict(local)


def split_repository_url(url: str) -> tuple[str, str]:
    """Git URL から埋め込みユーザー情報を分離する。

    例: http://user@host/path → ("http://host/path", "user")
        http://user:pass@host/path → ("http://host/path", "user")
    認証は Jenkins 資格情報で行うため、コミットする URL から個人名を除去する。
    戻り値は (ユーザー情報を除いた URL, ユーザー名)。
    """
    value = (url or "").strip()
    if "://" not in value:
        return value, ""
    scheme, rest = value.split("://", 1)
    # userinfo は authority（最初の "/" まで）に含まれる。パス内の "@" は対象外。
    slash = rest.find("/")
    authority = rest if slash == -1 else rest[:slash]
    path = "" if slash == -1 else rest[slash:]
    if "@" not in authority:
        return value, ""
    userinfo, host = authority.split("@", 1)
    username = userinfo.split(":", 1)[0]
    return f"{scheme}://{host}{path}", username


def migrate_from_legacy(data: dict[str, Any]) -> CISetupConfig:
    """旧フラット形式 ci.settings.json からの移行（C# MigrateFromLegacy 相当）。"""
    config = CISetupConfig()
    config.project.name = str(data.get("projectName", "") or "")
    config.project.solution_file = str(data.get("solutionFile", "") or "")
    config.project.publish_project = str(data.get("publishProject", "") or "")
    config.project.artifact_prefix = str(data.get("artifactPrefix", "") or "")
    storage = data.get("storage")
    if isinstance(storage, dict):
        config.storage = _storage_from_dict(storage)
    return config


def default_config() -> CISetupConfig:
    return CISetupConfig(
        project=ProjectConfig(
            name="YourProject",
            solution_file="YourProject.sln",
            publish_project="src/YourProject/YourProject.csproj",
            artifact_prefix="YourProject",
        )
    )
