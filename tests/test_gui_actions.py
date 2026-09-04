from __future__ import annotations

from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter")
from tkinter import TclError  # noqa: E402

import cisetup.gui.app as appmod  # noqa: E402
import cisetup.gui.deps as deps_mod  # noqa: E402
import cisetup.jenkins_client as jc  # noqa: E402


@pytest.fixture
def app(sln_repo: Path):
    try:
        application = appmod.ConfigureApp(initial_repository_root=str(sln_repo))
    except TclError:
        pytest.skip("Tk ディスプレイが利用できません")
    application.withdraw()
    application.update_idletasks()
    # ダイアログ系はブロック・ポップアップを避けるため無効化する
    application._info = lambda *a, **k: None
    application._ask = lambda *a, **k: True
    yield application
    application.destroy()


def _set_jenkins_secrets(app) -> None:
    app._fields["secrets.jenkins_url"].set("http://localhost:8080")
    app._fields["secrets.jenkins_user"].set("u")
    app._fields["secrets.jenkins_api_token"].set("t")


class FakeClient:
    last: "FakeClient | None" = None

    def __init__(self, secrets, timeout: float = 30.0) -> None:
        FakeClient.last = self
        self.secrets = secrets
        self.connected = False
        self.triggered: tuple[str, bool] | None = None
        self.setup_args: tuple | None = None

    def test_connection(self) -> None:
        self.connected = True

    def trigger_build(self, job_name: str, publish_release: bool = False) -> str:
        self.triggered = (job_name, publish_release)
        return "http://localhost:8080/job/MyApp-CI/"

    def setup_server(self, config, agent_name, agent_root):
        self.setup_args = (agent_name, agent_root)
        result = jc.JenkinsServerSetupResult()
        result.log = ["==> 接続確認", "OK"]
        result.agent_launch_command = "java -jar agent.jar"
        result.requires_plugin_restart = True
        return result


@pytest.fixture
def fake_jenkins(monkeypatch):
    FakeClient.last = None
    monkeypatch.setattr(deps_mod, "JenkinsClient", FakeClient)
    return FakeClient


# --------------------------------------------------------------- save / test

def test_save_only_writes_config(app, sln_repo):
    app._save_only()
    assert (sln_repo / "CISetup" / "cisetup.config.json").is_file()


def test_confirm_test_project_ok_when_set(app):
    # 自動検出で test_project が埋まっているので警告は出ず True
    assert app._config.project.test_project.strip()
    assert app._confirm_test_project() is True


def test_confirm_test_project_warns_when_empty(app, monkeypatch):
    # テスト対象が空でリポジトリにテスト csproj がある → 警告（_ask）が出る
    app._config.project.test_project = ""
    asked = {}

    def fake_ask(*a, **k):
        asked["called"] = True
        return False

    monkeypatch.setattr(app, "_ask", fake_ask)
    assert app._confirm_test_project() is False
    assert asked.get("called")


def test_save_only_aborts_when_test_warning_declined(app, monkeypatch, sln_repo):
    app._config.project.test_project = ""
    app._config_to_form()
    monkeypatch.setattr(app, "_ask", lambda *a, **k: False)
    app._save_only()
    # 中断したので config.json は書き出されない
    assert not (sln_repo / "CISetup" / "cisetup.config.json").is_file()


def test_test_jenkins_calls_connection(app, fake_jenkins):
    _set_jenkins_secrets(app)
    app._test_jenkins()
    assert fake_jenkins.last is not None
    assert fake_jenkins.last.connected is True


def test_test_jenkins_requires_secrets(app):
    app._fields["secrets.jenkins_url"].set("")
    with pytest.raises(ValueError):
        app._test_jenkins()


def test_apply_jenkins_calls_apply_settings(app, monkeypatch):
    calls = {}
    monkeypatch.setattr(deps_mod, "apply_settings", lambda cfg, sec: calls.setdefault("c", (cfg, sec)))
    _set_jenkins_secrets(app)
    app._fields["git.repository_url"].set("http://git/x.git")
    app._apply_jenkins()
    assert "c" in calls


def test_test_teams_calls_send(app, monkeypatch):
    captured = {}

    def fake_send(url, config, timeout=30.0):
        captured["url"] = url
        return "送信しました"

    monkeypatch.setattr(deps_mod.teams_service, "send_test", fake_send)
    app._fields["secrets.teams_webhook_url"].set("https://hook")
    app._test_teams()
    assert captured["url"] == "https://hook"


def test_test_file_server_calls_helper(app, monkeypatch):
    seen = []
    writer = lambda unc: seen.append(unc) or "OK"
    monkeypatch.setattr(deps_mod, "test_file_server_write", writer)
    app._multi_fields["jenkins.ci_file_servers"].set_values([r"\\srv\ci", r"\\srv2\ci"])
    app._multi_fields["storage.base_paths"].set_values([])
    app._test_file_server()
    # 全書き込み先に対して書き込みテストが走る
    assert seen == [r"\\srv\ci", r"\\srv2\ci"]


def test_create_storage_folders_requires_write_target(app):
    # 書き込み先未入力ならエラー（フォルダは作成されない）
    app._multi_fields["jenkins.ci_file_servers"].set_values([])
    app._multi_fields["storage.base_paths"].set_values([])
    with pytest.raises(ValueError, match="格納先フォルダ"):
        app._create_storage_folders()


def test_create_storage_folders_invokes_repo(app, tmp_path):
    app._multi_fields["jenkins.ci_file_servers"].set_values([])
    app._multi_fields["storage.base_paths"].set_values([str(tmp_path)])
    app._create_storage_folders()
    # 実効ルート直下にカテゴリフォルダが作られる
    assert (tmp_path / "releases").is_dir()
    assert (tmp_path / "logs").is_dir()


# --------------------------------------------------------------- setup

def test_run_setup_runs_all_steps(app, fake_jenkins, monkeypatch):
    seq = []
    monkeypatch.setattr(deps_mod.git_service, "pull_latest", lambda *a, **k: seq.append("pull") or "ok")
    monkeypatch.setattr(deps_mod, "apply_settings", lambda *a, **k: seq.append("apply"))
    monkeypatch.setattr(deps_mod, "run_local_ci", lambda *a, **k: seq.append("local"))
    _set_jenkins_secrets(app)
    app._fields["git.repository_url"].set("http://git/x.git")
    app._fields["jenkins.job_name"].set("MyApp-CI")
    app._run_setup()
    assert seq == ["pull", "local", "apply"]
    assert fake_jenkins.last.triggered == ("MyApp-CI", True)


def test_run_setup_ordering(app, fake_jenkins, monkeypatch):
    seq = []
    monkeypatch.setattr(deps_mod.git_service, "pull_latest", lambda *a, **k: seq.append("pull") or "ok")
    monkeypatch.setattr(app._repo, "save_all", lambda *a, **k: seq.append("save"))
    monkeypatch.setattr(deps_mod, "run_local_ci", lambda *a, **k: seq.append("local"))
    monkeypatch.setattr(deps_mod, "apply_settings", lambda *a, **k: seq.append("jenkins"))
    monkeypatch.setattr(app, "_build_now", lambda: seq.append("build"))
    _set_jenkins_secrets(app)
    app._fields["git.repository_url"].set("http://git/x.git")
    app._fields["jenkins.job_name"].set("MyApp-CI")
    app._run_setup()
    assert seq == ["pull", "save", "local", "jenkins", "build"]


def test_run_setup_pulls_configured_branch(app, fake_jenkins, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        deps_mod.git_service,
        "pull_latest",
        lambda root, branch: captured.setdefault("args", (root, branch)) or "ok",
    )
    monkeypatch.setattr(deps_mod, "run_local_ci", lambda *a, **k: None)
    monkeypatch.setattr(deps_mod, "apply_settings", lambda *a, **k: None)
    _set_jenkins_secrets(app)
    app._fields["git.repository_url"].set("http://git/x.git")
    app._fields["git.branch"].set("develop")
    app._run_setup()
    assert captured["args"][1] == "develop"


def test_run_setup_stops_when_pull_fails(app, fake_jenkins, monkeypatch):
    called = {}

    def boom(*a, **k):
        raise deps_mod.git_service.GitError("取り込みに失敗")

    monkeypatch.setattr(deps_mod.git_service, "pull_latest", boom)
    monkeypatch.setattr(app._repo, "save_all", lambda *a, **k: called.setdefault("save", True))
    monkeypatch.setattr(deps_mod, "run_local_ci", lambda *a, **k: called.setdefault("local", True))
    _set_jenkins_secrets(app)
    app._fields["git.repository_url"].set("http://git/x.git")
    with pytest.raises(deps_mod.git_service.GitError):
        app._run_setup()
    assert called == {}  # 取り込みに失敗したら以降は実行しない


def test_run_setup_requires_git_url(app):
    _set_jenkins_secrets(app)
    app._fields["git.repository_url"].set("")
    with pytest.raises(ValueError, match="Git リポジトリ URL"):
        app._run_setup()


def test_local_build_test_only_pulls_then_runs(app, fake_jenkins, monkeypatch):
    seq = []
    monkeypatch.setattr(deps_mod.git_service, "pull_latest", lambda *a, **k: seq.append("pull") or "ok")
    monkeypatch.setattr(deps_mod, "run_local_ci", lambda *a, **k: seq.append("local"))
    monkeypatch.setattr(deps_mod, "apply_settings", lambda *a, **k: seq.append("apply"))
    monkeypatch.setattr(app._repo, "save_all", lambda *a, **k: seq.append("save"))
    app._local_build_test_only()
    assert seq == ["pull", "local"]  # Jenkins 反映も保存もしない
    assert fake_jenkins.last is None


def test_local_build_test_only_does_not_require_jenkins_secrets(app, monkeypatch):
    monkeypatch.setattr(deps_mod.git_service, "pull_latest", lambda *a, **k: "ok")
    monkeypatch.setattr(deps_mod, "run_local_ci", lambda *a, **k: None)
    app._fields["secrets.jenkins_url"].set("")
    app._fields["secrets.jenkins_user"].set("")
    app._fields["secrets.jenkins_api_token"].set("")
    app._local_build_test_only()


def test_build_now_triggers(app, fake_jenkins, monkeypatch):
    monkeypatch.setattr(app, "_ask", lambda *a, **k: False)  # ブラウザは開かない
    _set_jenkins_secrets(app)
    app._fields["jenkins.job_name"].set("MyApp-CI")
    app._build_now()
    assert fake_jenkins.last.triggered == ("MyApp-CI", True)


def test_setup_server_runs(app, fake_jenkins):
    _set_jenkins_secrets(app)
    app._fields["server.agent_name"].set("win-agent")
    app._fields["server.agent_root"].set(r"C:\agent")
    app._setup_server()
    app.update()  # after() で予約された _set_text を反映
    assert fake_jenkins.last.setup_args == ("win-agent", r"C:\agent")
    assert "java -jar agent.jar" in app._agent_command_text.get("1.0", "end")


def test_setup_server_requires_agent_fields(app, fake_jenkins):
    _set_jenkins_secrets(app)
    app._fields["server.agent_name"].set("")
    with pytest.raises(ValueError):
        app._setup_server()


def test_copy_agent_command_empty_warns(app, monkeypatch):
    seen = {}
    monkeypatch.setattr(deps_mod.messagebox, "showinfo", lambda *a, **k: seen.setdefault("info", True))
    app._set_text(app._agent_command_text, "")
    app._copy_agent_command()
    assert seen.get("info")


# --------------------------------------------------- open project / layouts

def test_open_cisetup_folder_normalizes_to_parent(app, tmp_path_factory):
    from cisetup import paths

    repo = tmp_path_factory.mktemp("proj_norm")
    bb = repo / paths.CI_FOLDER
    bb.mkdir()
    (bb / paths.CONFIG_FILE).write_text("{}", encoding="utf-8")

    # cisetup フォルダ自体を選んでも親をリポジトリルートとして扱う
    app._open_project(bb)
    assert app._repository_root == repo.resolve()
    # 入れ子の cisetup/cisetup/ を作っていないこと
    assert not (bb / paths.CI_FOLDER).exists()


def test_open_legacy_layout_keeps_saved_values(app, tmp_path_factory):
    import json

    from cisetup import paths
    from cisetup.models import config_to_dict, default_config

    repo = tmp_path_factory.mktemp("proj_legacy")
    # .sln があると（バグ時は）自動検出で name が上書きされてしまう
    (repo / "Other.sln").write_text("dummy", encoding="utf-8")
    cfg = default_config()
    cfg.project.name = "LegacyKeep"
    cfg.project.solution_file = "Other.sln"
    # 旧レイアウト: ルート直下に cisetup.config.json
    (repo / paths.CONFIG_FILE).write_text(
        json.dumps(config_to_dict(cfg), ensure_ascii=False), encoding="utf-8"
    )

    app._open_project(repo)
    # 保存済み値が自動検出で上書きされない
    assert app._config.project.name == "LegacyKeep"
    # 旧レイアウトでも新規 cisetup/ を勝手に作らない
    assert not paths.config_path(repo).is_file()


def test_scan_env_populates_text(app, monkeypatch):
    from cisetup.environment_scan import EnvironmentCheckResult

    fake_scan = lambda: [
        EnvironmentCheckResult(name="Git", guidance="", found=True, detail="git 2.4"),
        EnvironmentCheckResult(
            name="Java", found=False, detail="未検出", guidance="入れてね", download_url="http://j"
        ),
    ]
    monkeypatch.setattr(deps_mod.env_scan, "scan", fake_scan)
    app._scan_env()
    app.update()
    text = app._env_text.get("1.0", "end")
    assert "[OK] Git" in text
    assert "[未検出] Java" in text
    assert "http://j" in text
