from __future__ import annotations

from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter")
from tkinter import TclError  # noqa: E402

import cisetup.gui.app as appmod  # noqa: E402
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
    application._prompt_commit = lambda: "commit msg"
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
    monkeypatch.setattr(appmod, "JenkinsClient", FakeClient)
    monkeypatch.setattr(jc, "JenkinsClient", FakeClient)
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
    monkeypatch.setattr(appmod, "apply_settings", lambda cfg, sec: calls.setdefault("c", (cfg, sec)))
    _set_jenkins_secrets(app)
    app._fields["git.repository_url"].set("http://git/x.git")
    app._apply_jenkins()
    assert "c" in calls


def test_test_teams_calls_send(app, monkeypatch):
    captured = {}

    def fake_send(url, config, timeout=30.0):
        captured["url"] = url
        return "送信しました"

    monkeypatch.setattr(appmod.teams_service, "send_test", fake_send)
    app._fields["secrets.teams_webhook_url"].set("https://hook")
    app._test_teams()
    assert captured["url"] == "https://hook"


def test_test_file_server_calls_helper(app, monkeypatch):
    seen = []
    monkeypatch.setattr(
        appmod, "test_file_server_write", lambda unc: seen.append(unc) or "OK"
    )
    app._multi_fields["jenkins.ci_file_servers"].set_values([r"\\srv\ci", r"\\srv2\ci"])
    app._multi_fields["storage.base_paths"].set_values([])
    app._test_file_server()
    # 全書き込み先に対して書き込みテストが走る
    assert seen == [r"\\srv\ci", r"\\srv2\ci"]


# --------------------------------------------------------------- git / setup

def test_git_push_invokes_service(app, monkeypatch, sln_repo):
    captured = {}
    monkeypatch.setattr(
        appmod.git_service,
        "push_ci_files",
        lambda root, msg: captured.setdefault("args", (root, msg)) or "staged",
    )
    app._git_push()
    assert captured["args"][0] == sln_repo
    assert captured["args"][1] == "commit msg"


def test_git_push_cancelled(app, monkeypatch):
    monkeypatch.setattr(app, "_ask", lambda *a, **k: False)
    called = {}
    monkeypatch.setattr(
        appmod.git_service, "push_ci_files", lambda *a, **k: called.setdefault("x", True)
    )
    app._git_push()
    assert "x" not in called


def test_run_setup_runs_all_steps(app, fake_jenkins, monkeypatch):
    seq = []
    monkeypatch.setattr(appmod, "apply_settings", lambda *a, **k: seq.append("apply"))
    monkeypatch.setattr(appmod.git_service, "push_ci_files", lambda *a, **k: seq.append("push"))
    _set_jenkins_secrets(app)
    app._fields["git.repository_url"].set("http://git/x.git")
    app._fields["jenkins.job_name"].set("MyApp-CI")
    # 全ステップを有効化（build はビルド実行後に push される順）
    app._step_save_var.set(True)
    app._step_jenkins_var.set(True)
    app._step_build_var.set(True)
    app._step_push_var.set(True)
    app._run_setup()
    assert seq == ["apply", "push"]
    assert fake_jenkins.last.triggered == ("MyApp-CI", False)


def test_run_setup_skips_unchecked_steps(app, fake_jenkins, monkeypatch):
    # 既定（push=OFF）でローカル確認のみ。Git push は実行されない。
    pushed = {}
    monkeypatch.setattr(appmod, "apply_settings", lambda *a, **k: None)
    monkeypatch.setattr(
        appmod.git_service, "push_ci_files", lambda *a, **k: pushed.setdefault("x", True)
    )
    _set_jenkins_secrets(app)
    app._fields["jenkins.job_name"].set("MyApp-CI")
    app._step_build_var.set(False)
    app._step_push_var.set(False)
    app._run_setup()
    assert "x" not in pushed  # push されない
    assert fake_jenkins.last is None  # build もされない


def test_run_setup_push_forces_save(app, monkeypatch, sln_repo):
    # 「設定を保存」をオフにして「Git push」だけ選んでも、push 前に必ず save_all される
    seq = []
    monkeypatch.setattr(app._repo, "save_all", lambda *a, **k: seq.append("save"))
    monkeypatch.setattr(appmod.git_service, "push_ci_files", lambda *a, **k: seq.append("push"))
    app._fields["git.repository_url"].set("http://git/x.git")
    app._step_save_var.set(False)
    app._step_jenkins_var.set(False)
    app._step_build_var.set(False)
    app._step_push_var.set(True)
    app._run_setup()
    # save が push より前に実行される
    assert seq == ["save", "push"]


def test_run_setup_local_only_no_git_no_jenkins(app, fake_jenkins, monkeypatch):
    # 「ローカルでビルド＆テスト」だけ選択 → git push / pull も apply_settings /
    # trigger_build も呼ばれず、ローカルランナーだけが実行される。
    called = {}
    monkeypatch.setattr(appmod, "run_local_ci", lambda *a, **k: called.setdefault("local", (a, k)))
    monkeypatch.setattr(appmod, "apply_settings", lambda *a, **k: called.setdefault("apply", True))
    monkeypatch.setattr(
        appmod.git_service, "push_ci_files", lambda *a, **k: called.setdefault("push", True)
    )
    monkeypatch.setattr(app._repo, "save_all", lambda *a, **k: called.setdefault("save", True))
    app._step_save_var.set(False)
    app._step_local_var.set(True)
    app._step_jenkins_var.set(False)
    app._step_push_var.set(False)
    app._step_build_var.set(False)
    app._run_setup()
    assert "local" in called
    assert "apply" not in called
    assert "push" not in called
    assert "save" not in called  # ローカルは保存を強制しない
    assert fake_jenkins.last is None  # trigger_build されない


def test_run_setup_local_does_not_require_jenkins_secrets(app, monkeypatch):
    # ローカル単独なら Jenkins URL 等が未入力でも例外にならない。
    monkeypatch.setattr(appmod, "run_local_ci", lambda *a, **k: None)
    app._fields["secrets.jenkins_url"].set("")
    app._fields["secrets.jenkins_user"].set("")
    app._fields["secrets.jenkins_api_token"].set("")
    app._step_save_var.set(False)
    app._step_local_var.set(True)
    app._step_jenkins_var.set(False)
    app._step_push_var.set(False)
    app._step_build_var.set(False)
    app._run_setup()  # 例外が出なければ OK


def test_run_setup_local_ordering(app, fake_jenkins, monkeypatch):
    # save → local → jenkins → push → build の順で実行される。
    seq = []
    monkeypatch.setattr(app._repo, "save_all", lambda *a, **k: seq.append("save"))
    monkeypatch.setattr(appmod, "run_local_ci", lambda *a, **k: seq.append("local"))
    monkeypatch.setattr(appmod, "apply_settings", lambda *a, **k: seq.append("jenkins"))
    monkeypatch.setattr(appmod.git_service, "push_ci_files", lambda *a, **k: seq.append("push"))
    monkeypatch.setattr(app, "_build_now", lambda: seq.append("build"))
    _set_jenkins_secrets(app)
    app._fields["git.repository_url"].set("http://git/x.git")
    app._fields["jenkins.job_name"].set("MyApp-CI")
    app._step_save_var.set(True)
    app._step_local_var.set(True)
    app._step_jenkins_var.set(True)
    app._step_push_var.set(True)
    app._step_build_var.set(True)
    app._run_setup()
    assert seq == ["save", "local", "jenkins", "push", "build"]


def test_run_setup_requires_at_least_one_step(app):
    app._step_save_var.set(False)
    app._step_jenkins_var.set(False)
    app._step_build_var.set(False)
    app._step_push_var.set(False)
    with pytest.raises(ValueError):
        app._run_setup()


def test_build_now_triggers(app, fake_jenkins, monkeypatch):
    monkeypatch.setattr(app, "_ask", lambda *a, **k: False)  # ブラウザは開かない
    _set_jenkins_secrets(app)
    app._fields["jenkins.job_name"].set("MyApp-CI")
    app._build_now()
    assert fake_jenkins.last.triggered == ("MyApp-CI", False)


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
    monkeypatch.setattr(appmod.messagebox, "showinfo", lambda *a, **k: seen.setdefault("info", True))
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

    monkeypatch.setattr(
        appmod.env_scan,
        "scan",
        lambda: [
            EnvironmentCheckResult(name="Git", guidance="", found=True, detail="git 2.4"),
            EnvironmentCheckResult(
                name="Java", found=False, detail="未検出", guidance="入れてね", download_url="http://j"
            ),
        ],
    )
    app._scan_env()
    app.update()
    text = app._env_text.get("1.0", "end")
    assert "[OK] Git" in text
    assert "[未検出] Java" in text
    assert "http://j" in text
