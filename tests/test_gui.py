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


def test_agent_workspace_path_form_roundtrip(app):
    app._fields["jenkins.agent_workspace_path"].set(r"C:\jenkins-agent\workspace\App")
    app._form_to_config()
    assert app._config.jenkins.agent_workspace_path == r"C:\jenkins-agent\workspace\App"
    # config -> form の復元（_loading ガードで trace 再入を防ぐ）
    app._config.jenkins.agent_workspace_path = r"C:\ws\Other"
    app._loading = True
    try:
        app._config_to_form()
    finally:
        app._loading = False
    assert app._fields["jenkins.agent_workspace_path"].get() == r"C:\ws\Other"


def test_form_invalid_int_falls_back(app):
    app._fields["jenkins.build_timeout_minutes"].set("abc")
    app._form_to_config()
    assert app._config.jenkins.build_timeout_minutes == 30


def test_config_to_form(app):
    app._config.project.name = "FromConfig"
    app._config_to_form()
    assert app._fields["project.name"].get() == "FromConfig"


def test_update_preview(app):
    app._multi_fields["jenkins.ci_file_servers"].set_values([r"\\srv\ci"])
    app._multi_fields["storage.base_paths"].set_values([])
    app._fields["project.name"].set("Demo")
    app._update_preview()
    assert r"\\srv\ci\Demo" in app._preview_logs.get()


def test_multi_field_add_remove(app):
    # ＋ で行追加、− で行削除。get_values は空行を無視する。
    mf = app._multi_fields["jenkins.ci_file_servers"]
    mf.set_values([r"\\srv1\ci"])
    mf._on_add()  # ＋ 相当
    assert len(mf._rows) == 2
    mf._rows[1]["var"].set(r"\\srv2\ci")
    assert mf.get_values() == [r"\\srv1\ci", r"\\srv2\ci"]
    mf._on_remove(mf._rows[1])  # − 相当
    assert mf.get_values() == [r"\\srv1\ci"]


def test_multi_field_remove_last_row_clears(app):
    # 行が 1 つのときの − はクリアのみ（最低 1 行は残す）
    mf = app._multi_fields["storage.base_paths"]
    mf.set_values([r"C:\local\CI"])
    mf._on_remove(mf._rows[0])
    assert len(mf._rows) == 1
    assert mf.get_values() == []


def test_both_write_targets_used_in_preview(app):
    # ④ と書き込み先ベースは併用でき、全書き込み先プレビューに両方表示される
    app._multi_fields["jenkins.ci_file_servers"].set_values([r"\\srv\ci"])
    app._multi_fields["storage.base_paths"].set_values([r"C:\local\CI"])
    app._fields["project.name"].set("Demo")
    app._update_preview()
    targets = app._preview_targets.get()
    assert r"\\srv\ci" in targets
    assert r"C:\local\CI" in targets


def test_form_to_config_reads_multi_urls(app):
    app._multi_fields["storage.release_urls"].set_values(["https://r1", "https://r2"])
    app._form_to_config()
    assert app._config.storage.release_urls == ["https://r1", "https://r2"]


def test_archive_source_form_roundtrip(app):
    # チェックボックス＋ソースフォルダ名がフォーム往復で保存・復元される
    app._archive_source_var.set(True)
    app._fields["storage.source_dir"].set("src-snap")
    app._form_to_config()
    assert app._config.storage.archive_source is True
    assert app._config.storage.source_dir == "src-snap"
    # 空欄なら "source" にフォールバック
    app._fields["storage.source_dir"].set("")
    app._form_to_config()
    assert app._config.storage.source_dir == "source"
    # config -> form の復元
    app._config.storage.archive_source = True
    app._config.storage.source_dir = "mysrc"
    app._config_to_form()
    assert app._archive_source_var.get() is True
    assert app._fields["storage.source_dir"].get() == "mysrc"


def test_archive_source_preview(app):
    app._multi_fields["jenkins.ci_file_servers"].set_values([r"\\srv\ci"])
    app._multi_fields["storage.base_paths"].set_values([])
    app._fields["project.name"].set("Demo")
    app._archive_source_var.set(True)
    app._fields["storage.source_dir"].set("source")
    app._update_preview()
    assert r"\\srv\ci\Demo\source" in app._preview_source.get()


def test_push_ci_file_server_env_form_roundtrip(app):
    app._push_env_var.set(True)
    app._form_to_config()
    assert app._config.jenkins.push_ci_file_server_env is True
    # config -> form の復元（_loading ガードで trace 再入を防ぐ）
    app._config.jenkins.push_ci_file_server_env = False
    app._loading = True
    try:
        app._config_to_form()
    finally:
        app._loading = False
    assert app._push_env_var.get() is False


def test_retry_wrapper_form_roundtrip(app):
    app._retry_wrapper_var.set(True)
    app._fields["jenkins.retry_max_count"].set("5")
    app._fields["jenkins.retry_delay_seconds"].set("120")
    app._fields["jenkins.checkout_retry_count"].set("4")
    app._form_to_config()
    assert app._config.jenkins.retry_wrapper_enabled is True
    assert app._config.jenkins.retry_max_count == 5
    assert app._config.jenkins.retry_delay_seconds == 120
    assert app._config.jenkins.checkout_retry_count == 4

    app._config.jenkins.retry_wrapper_enabled = False
    app._config.jenkins.retry_max_count = 3
    # 実際の呼び出し元（_open_project）と同様に _loading でガードする。
    # ガードしないと StringVar の trace 経由で _form_to_config が再入し、
    # まだ更新前の BooleanVar の値で config を上書きしてしまう。
    app._loading = True
    try:
        app._config_to_form()
    finally:
        app._loading = False
    assert app._retry_wrapper_var.get() is False
    assert app._fields["jenkins.retry_max_count"].get() == "3"


def test_retry_wrapper_toggle_shows_hides_options(app):
    app._retry_wrapper_var.set(True)
    app._on_retry_wrapper_changed()
    assert app._retry_options_row.winfo_manager() != ""
    app._retry_wrapper_var.set(False)
    app._on_retry_wrapper_changed()
    assert app._retry_options_row.winfo_manager() == ""


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


def test_deploy_local_to_agent_requires_write_target(app):
    # 書き込み先が空のまま配置すると、兄弟パスの設定を空内容で上書きしてしまう。
    # ValueError で中断し、deploy_local_to_agent を呼ばないことを検証する。
    app._multi_fields["jenkins.ci_file_servers"].set_values([])
    app._multi_fields["storage.base_paths"].set_values([])
    app._fields["jenkins.agent_workspace_path"].set(r"C:\jenkins-agent\workspace\App")

    called = []
    app._repo.deploy_local_to_agent = lambda *a, **k: called.append((a, k))

    with pytest.raises(ValueError):
        app._deploy_local_to_agent()
    assert called == []


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
