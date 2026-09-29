"""プリセット（.NET / FPGA / カスタム）による画面切り替えの検証。"""

from __future__ import annotations

from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter")
from tkinter import TclError  # noqa: E402

QUARTUS = "FPGA — Intel/Altera Quartus"
VIVADO = "FPGA — AMD/Xilinx Vivado"
DOTNET = ".NET デスクトップ / アプリ"


def _app(root: Path):
    from cisetup.gui.app import ConfigureApp

    # Tk の初期化は環境要因で失敗しうるため、withdraw までまとめて面倒を見る。
    try:
        application = ConfigureApp(initial_repository_root=str(root))
        application.withdraw()
        application.update_idletasks()
    except TclError as exc:
        pytest.skip(f"Tk ディスプレイが利用できません: {exc}")
    return application


def _close(application) -> None:
    try:
        application.destroy()
    except TclError:
        pass


@pytest.fixture
def fpga_app(qpf_repo: Path):
    application = _app(qpf_repo)
    yield application
    _close(application)


@pytest.fixture
def app(sln_repo: Path):
    application = _app(sln_repo)
    yield application
    _close(application)


def _packed(widget) -> bool:
    return widget.winfo_manager() == "pack"


def test_starts_on_mode_chooser(app):
    # 設定が無いプロジェクトでは、まず「どの CI を作るか」を選ばせる。
    assert _packed(app._chooser_frame)
    assert not _packed(app._form_frame)


def test_saved_config_skips_chooser(app, sln_repo):
    app._form_to_config()
    app._repo.save_all(sln_repo, app._config, app._secrets)
    app._load_repository(sln_repo)
    assert _packed(app._form_frame)
    assert not _packed(app._chooser_frame)


def test_choose_fpga_switches_screen(fpga_app):
    fpga_app._choose_mode(QUARTUS)
    assert fpga_app._current_mode() == "fpga"
    assert fpga_app._current_fpga_tool() == "Quartus"
    # 選択画面からフォームへ切り替わる
    assert _packed(fpga_app._form_frame)
    # FPGA 専用カードが出て、.NET 専用の入力欄は隠れる
    from cisetup.gui.layout import card_frame

    assert _packed(card_frame(fpga_app._fpga_status.master))
    for key in ("project.solution_file", "project.publish_project", "project.test_project"):
        assert not _packed(fpga_app._field_rows[key])
    # 合成は 30 分では終わらないため既定を引き上げる
    assert fpga_app._fields["jenkins.build_timeout_minutes"].get() == "180"


def test_switch_back_to_dotnet_restores_fields(fpga_app):
    fpga_app._choose_mode(QUARTUS)
    fpga_app._preset_var.set(DOTNET)
    fpga_app._on_preset_selected()
    assert fpga_app._current_mode() == "dotnet"
    for key in ("project.solution_file", "project.publish_project", "build.runtime_identifier"):
        assert _packed(fpga_app._field_rows[key])


def test_dotnet_only_rows_keep_their_order(app):
    # 隠して戻したとき、プロジェクト名 → .sln → csproj の並びが崩れないこと。
    order_before = list(app._field_rows["project.name"].master.pack_slaves())
    app._preset_var.set(QUARTUS)
    app._on_preset_selected()
    app._preset_var.set(DOTNET)
    app._on_preset_selected()
    assert list(app._field_rows["project.name"].master.pack_slaves()) == order_before


def test_fpga_card_stays_between_preset_and_step_one(fpga_app):
    from cisetup.gui.layout import card_frame

    def position() -> tuple[int, int]:
        slaves = list(fpga_app._form_frame.pack_slaves())
        return (
            slaves.index(card_frame(fpga_app._preset_desc.master)),
            slaves.index(card_frame(fpga_app._fpga_status.master)),
        )

    fpga_app._choose_mode(QUARTUS)
    preset_at, fpga_at = position()
    assert fpga_at == preset_at + 1
    # 種類を往復させても、隠して戻したカードの位置は変わらない
    for name in (DOTNET, QUARTUS):
        fpga_app._preset_var.set(name)
        fpga_app._on_preset_selected()
    assert position() == (preset_at, fpga_at)


def test_fpga_project_field_writes_build_command(fpga_app):
    fpga_app._choose_mode(QUARTUS)
    fpga_app._fields["fpga.project"].set("hw/quartus/blink.qpf")
    fpga_app._form_to_config()
    assert fpga_app._config.build.build_command == "-Project hw/quartus/blink.qpf"
    # 保存済み設定を読み直すと、欄に戻る
    fpga_app._config_to_form()
    assert fpga_app._fields["fpga.project"].get() == "hw/quartus/blink.qpf"


def test_fpga_detect_fills_single_candidate(fpga_app):
    fpga_app._choose_mode(QUARTUS)
    fpga_app._fields["fpga.project"].set("")
    fpga_app._detect_fpga_projects()
    assert fpga_app._fields["fpga.project"].get() == "hw/quartus/blink.qpf"
    assert "blink.qpf" in fpga_app._fpga_status.cget("text")


def test_fpga_autodetect_names_project_from_qpf(fpga_app):
    fpga_app._choose_mode(QUARTUS)
    assert fpga_app._fields["project.name"].get() == "blink"
    # .NET 専用のプレースホルダは残さない
    assert fpga_app._fields["project.solution_file"].get() == ""
    assert fpga_app._fields["project.publish_project"].get() == ""


def test_fpga_status_warns_when_no_project(app):
    # .sln だけのリポジトリで Vivado を選ぶと、合成対象が無いことを警告する。
    app._choose_mode(VIVADO)
    assert "見つかりません" in app._fpga_status.cget("text")


def test_raw_build_command_is_kept(fpga_app):
    fpga_app._choose_mode(QUARTUS)
    fpga_app._config.build.build_command = "make bitstream"
    fpga_app._config_to_form()
    assert fpga_app._fpga_raw_command == "make bitstream"
    fpga_app._form_to_config()
    assert fpga_app._config.build.build_command == "make bitstream"
    assert "独自コマンド" in fpga_app._fpga_status.cget("text")


def test_cancelling_overwrite_restores_selection(fpga_app, monkeypatch):
    from cisetup.gui import presets as presets_mod

    fpga_app._choose_mode(QUARTUS)
    fpga_app._fields["build.lint_command"].set("verilator --lint-only src/top.v")
    monkeypatch.setattr(presets_mod.messagebox, "askyesno", lambda *a, **k: False)
    fpga_app._preset_var.set(DOTNET)
    fpga_app._on_preset_selected()
    # 断ったら選択もモードも元のまま
    assert fpga_app._preset_var.get() == QUARTUS
    assert fpga_app._current_mode() == "fpga"


def test_settings_are_not_duplicated_between_main_form_and_details(fpga_app):
    from cisetup.gui.layout import card_frame

    fpga_app._choose_mode(QUARTUS)
    # 合成タイムアウトは FPGA カードだけ。詳細設定側は隠す。
    assert _packed(fpga_app._fpga_timeout_row)
    assert not _packed(fpga_app._details_timeout_row)
    # 保存とローカルビルドは ⑥ だけ。詳細設定の手動操作には置かない。
    assert "保存のみ" not in fpga_app._details_manual_labels
    assert "ローカルでビルド＆テスト" not in fpga_app._details_manual_labels

    fpga_app._preset_var.set(DOTNET)
    fpga_app._on_preset_selected()
    # .NET では追加コマンドカードを出さず、タイムアウトは詳細設定だけ。
    assert not _packed(card_frame(fpga_app._fpga_status.master))
    assert not _packed(fpga_app._details_commands_card)
    assert _packed(fpga_app._details_timeout_row)


def test_mode_texts_change_with_preset(fpga_app):
    fpga_app._choose_mode(QUARTUS)
    fpga_texts = [widget.cget("text") for widget, _ in fpga_app._mode_texts]
    assert any("FPGA" in text for text in fpga_texts)
    fpga_app._preset_var.set(DOTNET)
    fpga_app._on_preset_selected()
    dotnet_texts = [widget.cget("text") for widget, _ in fpga_app._mode_texts]
    assert dotnet_texts != fpga_texts
    assert any(".sln" in text for text in dotnet_texts)
