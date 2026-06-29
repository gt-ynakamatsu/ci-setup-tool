from __future__ import annotations

from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter")
from tkinter import TclError  # noqa: E402

from cisetup.gui.commit_dialog import CommitMessageDialog  # noqa: E402
from cisetup.gui.tooltip import ToolTip, attach_tooltip  # noqa: E402


@pytest.fixture
def app(sln_repo: Path):
    from cisetup.gui.app import ConfigureApp

    try:
        application = ConfigureApp(initial_repository_root=str(sln_repo))
    except TclError:
        pytest.skip("Tk ディスプレイが利用できません")
    application.withdraw()
    application.update_idletasks()
    yield application
    application.destroy()


def test_app_loads_project(app, sln_repo):
    assert app._repository_root == sln_repo
    # 自動検出でプロジェクト名がフォームに反映される
    assert app._fields["project.name"].get() == "MyApp"


def test_form_roundtrip(app):
    app._fields["project.name"].set("Renamed")
    app._fields["jenkins.build_timeout_minutes"].set("45")
    app._form_to_config()
    assert app._config.project.name == "Renamed"
    assert app._config.jenkins.build_timeout_minutes == 45


def test_form_invalid_int_falls_back(app):
    app._fields["jenkins.build_timeout_minutes"].set("abc")
    app._form_to_config()
    assert app._config.jenkins.build_timeout_minutes == 30


def test_config_to_form(app):
    app._config.project.name = "FromConfig"
    app._config_to_form()
    assert app._fields["project.name"].get() == "FromConfig"


def test_update_preview(app):
    app._fields["jenkins.ci_file_server"].set(r"\\srv\ci")
    app._fields["storage.base_path"].set("")
    app._fields["project.name"].set("Demo")
    app._update_preview()
    assert r"\\srv\ci\Demo" in app._preview_logs.get()


def test_write_target_ci_file_server_clears_base_path(app):
    # base_path が入っている状態で ④ を入力 → base_path が自動クリア（後勝ち）
    app._fields["storage.base_path"].set(r"C:\local\CI")
    app._fields["jenkins.ci_file_server"].set(r"\\srv\ci")
    assert app._fields["storage.base_path"].get() == ""
    assert app._fields["jenkins.ci_file_server"].get() == r"\\srv\ci"


def test_write_target_base_path_clears_ci_file_server(app):
    # ④ が入っている状態で base_path を入力 → ④ が自動クリア（後勝ち・逆方向）
    app._fields["jenkins.ci_file_server"].set(r"\\srv\ci")
    app._fields["storage.base_path"].set(r"C:\local\CI")
    assert app._fields["jenkins.ci_file_server"].get() == ""
    assert app._fields["storage.base_path"].get() == r"C:\local\CI"


def test_write_target_not_cleared_while_loading(app):
    # ロード中は相互排他を発火させない（両方そのまま保持）
    app._loading = True
    try:
        app._fields["storage.base_path"].set(r"C:\local\CI")
        app._fields["jenkins.ci_file_server"].set(r"\\srv\ci")
    finally:
        app._loading = False
    assert app._fields["storage.base_path"].get() == r"C:\local\CI"
    assert app._fields["jenkins.ci_file_server"].get() == r"\\srv\ci"


def test_normalize_rel(app):
    assert app._normalize_rel("a\\b\\c.sln") == "a/b/c.sln"


def test_apply_preset_python(app):
    app._preset_var.set("Python")
    app._apply_preset()
    assert app._fields["build.lint_command"].get() == "ruff check ."
    assert app._profile_var.get().startswith("カスタム")


def test_preset_selected_updates_description(app):
    app._preset_var.set("Python")
    app._on_preset_selected()
    assert "ruff" in app._preset_desc.cget("text").lower() or app._preset_desc.cget("text")


def test_set_text(app):
    app._set_text(app._server_log_text, "hello")
    assert app._server_log_text.get("1.0", "end").strip() == "hello"


def test_require_jenkins_secrets_raises(app):
    app._secrets.jenkins_url = ""
    with pytest.raises(ValueError):
        app._require_jenkins_secrets()


def test_ensure_repo(app, sln_repo):
    assert app._ensure_repo() == sln_repo


def test_commit_dialog_ok(app):
    dlg = CommitMessageDialog(app, "default msg")
    dlg._ok()
    assert dlg.result == "default msg"


def test_commit_dialog_cancel(app):
    dlg = CommitMessageDialog(app, "x")
    dlg._cancel()
    assert dlg.result is None


def test_commit_dialog_empty_stays_open(app):
    dlg = CommitMessageDialog(app, "x")
    dlg._var.set("   ")
    dlg._ok()
    assert dlg.result is None
    dlg.destroy()


def test_tooltip_show_hide(app):
    label = tk.Label(app, text="hi")
    label.pack()
    app.update_idletasks()
    tip = ToolTip(label, "help text", delay_ms=1)
    tip._show()
    assert tip._tip is not None
    tip._hide()
    assert tip._tip is None


def test_attach_tooltip_empty_text(app):
    label = tk.Label(app, text="x")
    attach_tooltip(label, "")  # 空文字なら ToolTip を生成しない（例外が出ないこと）
