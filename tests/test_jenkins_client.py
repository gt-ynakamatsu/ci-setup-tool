from __future__ import annotations

import io
import urllib.error
import urllib.parse
import urllib.request

import pytest

from cisetup import jenkins_client
from cisetup.jenkins_client import (
    JenkinsClient,
    JenkinsConnectionError,
    JenkinsError,
    apply_settings,
    extract_agent_secret,
    format_jenkins_error,
)
from cisetup.jenkins_client import test_file_server_write as fs_write
from cisetup.models import CISetupConfig, CISetupSecrets


# ----------------------------------------------------------- pure helpers

def test_format_jenkins_error_401():
    assert "401" in format_jenkins_error(401, "")


def test_format_jenkins_error_403():
    assert "403" in format_jenkins_error(403, "")


def test_format_jenkins_error_strip_html():
    msg = format_jenkins_error(500, "<html><body>Boom</body></html>")
    assert "Boom" in msg


def test_format_jenkins_error_long_body():
    msg = format_jenkins_error(500, "x" * 600)
    assert "500" in msg


def test_format_jenkins_error_status_name():
    # C# の HttpStatusCode.ToString()（404→NotFound）と一致させる
    assert format_jenkins_error(404, "") == "Jenkins API エラー: 404 NotFound"
    assert format_jenkins_error(500, "") == "Jenkins API エラー: 500 InternalServerError"


def test_escape_xml_escapes_quotes():
    # C# の SecurityElement.Escape と同様に " と ' もエスケープする
    out = jenkins_client._escape_xml("""a<b>&"c'd""")
    assert out == "a&lt;b&gt;&amp;&quot;c&apos;d"


def test_extract_agent_secret():
    jnlp = "<a><argument>-secret</argument><argument>deadbeef</argument></a>"
    assert extract_agent_secret(jnlp) == "deadbeef"


def test_extract_agent_secret_missing():
    with pytest.raises(JenkinsError):
        extract_agent_secret("<a><argument>-url</argument></a>")


def test_install_plugins_script():
    script = jenkins_client._install_plugins_script()
    assert "workflow-aggregator" in script
    assert "isRestartRequiredForCompletion" in script


def test_set_location_script_escapes():
    script = jenkins_client._set_location_script("http://h/a'b")
    assert "\\'" in script


# ----------------------------------------------------------- constructor

def _secrets():
    return CISetupSecrets(jenkins_url="http://localhost:8080", jenkins_user="u", jenkins_api_token="t")


def test_client_requires_url():
    with pytest.raises(ValueError):
        JenkinsClient(CISetupSecrets(jenkins_user="u", jenkins_api_token="t"))


def test_client_requires_credentials():
    with pytest.raises(ValueError):
        JenkinsClient(CISetupSecrets(jenkins_url="http://x"))


def test_client_requires_http_scheme():
    with pytest.raises(ValueError):
        JenkinsClient(CISetupSecrets(jenkins_url="ftp://x", jenkins_user="u", jenkins_api_token="t"))


# ----------------------------------------------------------- HTTP mocking

class FakeResponse:
    def __init__(self, body: str = "", status: int = 200):
        self._body = body.encode("utf-8")
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Recorder:
    """urlopen を差し替えて (method, url) ごとに応答を返すフェイク。"""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.bodies: list[bytes] = []
        self.responses: dict[str, FakeResponse] = {}
        self.errors: dict[str, urllib.error.HTTPError] = {}

    def handler(self, req, timeout=None):
        method = req.get_method()
        url = req.full_url
        self.calls.append((method, url))
        self.bodies.append(req.data or b"")
        for key, err in self.errors.items():
            if key in url:
                raise err
        for key, resp in self.responses.items():
            if key in url:
                return resp
        return FakeResponse("{}")


@pytest.fixture
def recorder(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(urllib.request, "urlopen", rec.handler)
    return rec


def _http_error(url: str, code: int, body: str = "err") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, "msg", {}, io.BytesIO(body.encode("utf-8")))


def test_test_connection_ok(recorder):
    client = JenkinsClient(_secrets())
    client.test_connection()
    assert any("api/json" in url for _, url in recorder.calls)


def test_test_connection_unauthorized(recorder):
    recorder.errors["api/json"] = _http_error("http://x/api/json", 401, "Unauthorized")
    client = JenkinsClient(_secrets())
    with pytest.raises(JenkinsError, match="401"):
        client.test_connection()


def test_url_error(monkeypatch):
    def boom(req, timeout=None):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    client = JenkinsClient(_secrets())
    with pytest.raises(JenkinsError, match="接続できませんでした"):
        client.test_connection()


def test_run_groovy(recorder):
    recorder.responses["scriptText"] = FakeResponse("OK: done")
    client = JenkinsClient(_secrets())
    assert client.run_groovy("println 'x'") == "OK: done"


def test_trigger_build_existing_job(recorder):
    recorder.responses["job/MyApp-CI/api/json"] = FakeResponse("{}")
    client = JenkinsClient(_secrets())
    url = client.trigger_build("MyApp-CI", publish_release=True)
    assert url.endswith("job/MyApp-CI/")


def test_trigger_build_falls_back_on_http_error(recorder):
    # buildWithParameters が HTTP エラー → 通常 build にフォールバック（C# と同じ）
    recorder.responses["job/MyApp-CI/api/json"] = FakeResponse("{}")
    recorder.errors["buildWithParameters"] = _http_error(
        "http://x/job/MyApp-CI/buildWithParameters", 400
    )
    client = JenkinsClient(_secrets())
    url = client.trigger_build("MyApp-CI")
    assert url.endswith("job/MyApp-CI/")
    assert any(url.endswith("/build") for _, url in recorder.calls)


def test_trigger_build_connection_error_propagates(monkeypatch):
    # 接続エラーは build へフォールバックせずそのまま伝播する（C# と同じ）
    def handler(req, timeout=None):
        url = req.full_url
        if "buildWithParameters" in url:
            raise urllib.error.URLError("down")
        if "/build" in url:
            raise AssertionError("接続エラー時に build へフォールバックしてはいけない")
        return FakeResponse("{}")

    monkeypatch.setattr(urllib.request, "urlopen", handler)
    client = JenkinsClient(_secrets())
    with pytest.raises(JenkinsConnectionError):
        client.trigger_build("MyApp-CI")


def test_client_rejects_url_without_host():
    with pytest.raises(ValueError):
        JenkinsClient(CISetupSecrets(jenkins_url="http://", jenkins_user="u", jenkins_api_token="t"))


def test_trigger_build_missing_job(recorder):
    recorder.errors["job/Ghost/api/json"] = _http_error("http://x/job/Ghost/api/json", 404)
    client = JenkinsClient(_secrets())
    with pytest.raises(ValueError, match="見つかりません"):
        client.trigger_build("Ghost")


def test_trigger_build_empty_name(recorder):
    client = JenkinsClient(_secrets())
    with pytest.raises(ValueError):
        client.trigger_build("")


def test_upsert_credentials_and_job(recorder):
    client = JenkinsClient(_secrets())
    client.upsert_string_credential("teams-webhook-url", "http://hook", "Teams")
    client.upsert_username_password_credential("internal-git", "user", "pw", "Git")
    cfg = CISetupConfig()
    cfg.git.repository_url = "http://git/x.git"
    client.upsert_pipeline_job(cfg)
    assert any("createItem" in url or "config.xml" in url for _, url in recorder.calls)


def test_upsert_string_credential_skips_empty(recorder):
    client = JenkinsClient(_secrets())
    client.upsert_string_credential("id", "", "desc")
    assert recorder.calls == []


def test_setup_server(recorder):
    recorder.responses["api/json?tree=version"] = FakeResponse('{"version":"2.426"}')
    recorder.responses["scriptText"] = FakeResponse("OK")
    recorder.responses["jenkins-agent.jnlp"] = FakeResponse(
        "<a><argument>-secret</argument><argument>sec123</argument></a>"
    )
    client = JenkinsClient(_secrets())
    cfg = CISetupConfig()
    result = client.setup_server(cfg, "win-agent", r"C:\agent")
    assert "sec123" in result.agent_launch_command
    assert any("バージョン" in line for line in result.log)


def test_set_global_env_var_script_escapes():
    # Windows パス（バックスラッシュ）と ' を Groovy 文字列へ安全にエスケープする
    script = jenkins_client._set_global_env_var_script(
        "CI_FILE_SERVER", r"\\srv\ipu-tes-app-ci"
    )
    assert "EnvironmentVariablesNodeProperty" in script
    assert "instance.save()" in script
    assert "CI_FILE_SERVER" in script
    assert r"\\\\srv\\ipu-tes-app-ci" in script


def test_set_global_env_var_calls_run_groovy(recorder):
    recorder.responses["scriptText"] = FakeResponse("OK: CI_FILE_SERVER set")
    client = JenkinsClient(_secrets())
    client.set_global_env_var("CI_FILE_SERVER", r"\\srv\ci")
    body = urllib.parse.unquote_plus(recorder.bodies[-1].decode("utf-8"))
    assert "scriptText" in recorder.calls[-1][1]
    assert "CI_FILE_SERVER" in body
    # 値はエスケープ済み（バックスラッシュが二重化）で POST body に含まれる
    assert r"\\\\srv\\ci" in body


def test_set_global_env_var_skips_empty(recorder):
    client = JenkinsClient(_secrets())
    client.set_global_env_var("CI_FILE_SERVER", "   ")
    assert recorder.calls == []


def test_apply_settings_pushes_env_when_enabled(recorder):
    cfg = CISetupConfig()
    cfg.git.repository_url = "http://git/x.git"
    cfg.jenkins.push_ci_file_server_env = True
    cfg.jenkins.ci_file_servers = [r"\\srv\ci"]
    apply_settings(cfg, _secrets())
    assert any("scriptText" in url for _, url in recorder.calls)
    assert any(b"CI_FILE_SERVER" in body for body in recorder.bodies)


def test_apply_settings_skips_env_by_default(recorder):
    cfg = CISetupConfig()
    cfg.git.repository_url = "http://git/x.git"
    cfg.jenkins.ci_file_servers = [r"\\srv\ci"]
    apply_settings(cfg, _secrets())
    assert not any(b"CI_FILE_SERVER" in body for body in recorder.bodies)


def test_apply_settings_skips_env_when_no_target(recorder):
    cfg = CISetupConfig()
    cfg.git.repository_url = "http://git/x.git"
    cfg.jenkins.push_ci_file_server_env = True
    cfg.jenkins.ci_file_servers = []
    apply_settings(cfg, _secrets())
    assert not any(b"CI_FILE_SERVER" in body for body in recorder.bodies)


def test_apply_settings(recorder):
    cfg = CISetupConfig()
    cfg.git.repository_url = "http://git/x.git"
    apply_settings(cfg, _secrets())
    assert any("createItem" in url or "job/" in url for _, url in recorder.calls)


def test_apply_settings_skips_trigger_job_by_default(recorder):
    cfg = CISetupConfig()
    cfg.git.repository_url = "http://git/x.git"
    apply_settings(cfg, _secrets())
    assert not any("trigger" in url for _, url in recorder.calls)


def test_apply_settings_creates_trigger_job_when_enabled(recorder):
    cfg = CISetupConfig()
    cfg.git.repository_url = "http://git/x.git"
    cfg.jenkins.retry_wrapper_enabled = True
    apply_settings(cfg, _secrets())
    assert any("CISetup-CI-trigger" in url for _, url in recorder.calls)


def test_trigger_job_name():
    assert jenkins_client.trigger_job_name("MyApp-CI") == "MyApp-CI-trigger"


def test_upsert_trigger_job_xml(recorder):
    client = JenkinsClient(_secrets())
    cfg = CISetupConfig()
    cfg.jenkins.job_name = "MyApp-CI"
    cfg.jenkins.cron_schedule = "0 0 * * *"
    cfg.jenkins.timezone = "Asia/Tokyo"
    cfg.jenkins.retry_max_count = 5
    cfg.jenkins.retry_delay_seconds = 120
    client.upsert_trigger_job(cfg)
    assert any("MyApp-CI-trigger" in url for _, url in recorder.calls)
    body = recorder.bodies[-1].decode("utf-8")
    assert "<projects>MyApp-CI</projects>" in body
    assert "TZ=Asia/Tokyo" in body
    assert "0 0 * * *" in body
    assert "<maxSchedule>5</maxSchedule>" in body
    assert "<delay>120</delay>" in body


def test_apply_settings_requires_repo_url(recorder):
    cfg = CISetupConfig()
    cfg.git.repository_url = ""
    with pytest.raises(ValueError, match="リポジトリ URL"):
        apply_settings(cfg, _secrets())


# ----------------------------------------------------------- file server

def test_fs_write_ok(tmp_path):
    msg = fs_write(str(tmp_path))
    assert "OK" in msg


def test_fs_write_empty():
    with pytest.raises(ValueError):
        fs_write("")
