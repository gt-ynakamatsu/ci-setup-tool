from __future__ import annotations

import tkinter as tk
from pathlib import Path

from ..config_repository import ConfigRepository
from ..models import CISetupConfig, CISetupSecrets
from ..recent_project import RecentProjectStore
from ..version import VERSION, display_version
from .actions.ops import ActionsMixin
from .details.panels import DetailsMixin
from .dialogs import DialogMixin
from .fields import FieldMixin
from .file_picks import FilePickMixin
from .form_sync import FormSyncMixin
from .layout import (
    COLOR_DESC,
    COLOR_TEXT,
    COLOR_WINDOW_BG,
    ScrollableFrame,
    font,
    set_scale,
)
from .mode import ModeMixin
from .multi_value_field import MultiValueField
from .presets import PresetMixin
from .repository import RepositoryMixin
from .steps.fpga import FpgaStepMixin
from .steps.intro import IntroStepsMixin
from .steps.start import StartStepMixin
from .steps.workflow import WorkflowStepsMixin
from .util import enable_dpi_awareness


class ConfigureApp(
    tk.Tk,
    FieldMixin,
    ModeMixin,
    StartStepMixin,
    IntroStepsMixin,
    WorkflowStepsMixin,
    FpgaStepMixin,
    DetailsMixin,
    FormSyncMixin,
    RepositoryMixin,
    PresetMixin,
    FilePickMixin,
    ActionsMixin,
    DialogMixin,
):
    def __init__(self, initial_repository_root: str | None = None) -> None:
        enable_dpi_awareness()
        super().__init__()

        try:
            scale = self.winfo_fpixels("1i") / 96.0
        except tk.TclError:
            scale = 1.0
        self._scale = scale if scale > 0 else 1.0
        set_scale(self._scale)

        self.title(f"CISetup {VERSION}")
        self._apply_window_icon()
        self.geometry(f"{self._px(960)}x{self._px(900)}")
        self.minsize(self._px(880), self._px(720))

        self._repo = ConfigRepository()
        self._recent = RecentProjectStore()
        self._repository_root: Path | None = None
        self._config = CISetupConfig()
        self._secrets = CISetupSecrets()
        self._loaded_default_configuration = "Release"
        self._fields: dict[str, tk.Variable] = {}
        self._field_widgets: dict[str, tk.Widget] = {}
        self._field_rows: dict[str, tk.Widget] = {}
        self._multi_fields: dict[str, MultiValueField] = {}
        self._path_status: dict[str, tk.Label] = {}
        self._agent_command = tk.StringVar()
        self._server_log = tk.StringVar()
        self._env_result = tk.StringVar()
        self._loading = False
        # プリセット（モード）関連の状態。
        self._applied_preset_name = ""
        # ビルドコマンド欄に手書きされた FPGA 以外のコマンド（あれば ci-fpga.ps1 より優先）。
        self._fpga_raw_command = ""
        self._fpga_scan_cache: dict[tuple[str, str], list[str]] = {}
        self._init_mode_registry()

        self._build_ui()
        self._initial_load(initial_repository_root)

    def _px(self, value: float) -> int:
        return max(1, int(round(value * self._scale)))

    def _apply_window_icon(self) -> None:
        from ..app_paths import get_package_root

        assets = get_package_root() / "assets"
        try:
            ico = assets / "icon.ico"
            if ico.is_file():
                self.iconbitmap(default=str(ico))
                return
        except tk.TclError:
            pass
        try:
            png = assets / "icon.png"
            if png.is_file():
                self._window_icon = tk.PhotoImage(file=str(png))
                self.iconphoto(True, self._window_icon)
        except tk.TclError:
            pass

    def _build_ui(self) -> None:
        self.configure(bg=COLOR_WINDOW_BG)
        outer = tk.Frame(self, padx=18, pady=12, bg=COLOR_WINDOW_BG)
        outer.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(outer, bg=COLOR_WINDOW_BG)
        header.pack(fill=tk.X, pady=(0, 14))
        title_row = tk.Frame(header, bg=COLOR_WINDOW_BG)
        title_row.pack(fill=tk.X)
        tk.Label(
            title_row,
            text="CISetup",
            font=font(24, bold=True),
            fg=COLOR_TEXT,
            bg=COLOR_WINDOW_BG,
            anchor="w",
        ).pack(side=tk.LEFT)
        tk.Label(
            title_row,
            text=display_version(),
            font=font(12),
            fg=COLOR_DESC,
            bg=COLOR_WINDOW_BG,
            anchor="w",
        ).pack(side=tk.LEFT, padx=(12, 0), pady=(10, 0))
        self._header_hint = tk.Label(
            header,
            text="上から順に入力して、最後の「セットアップを実行」を押すだけです。",
            font=font(12),
            fg=COLOR_DESC,
            bg=COLOR_WINDOW_BG,
            anchor="w",
        )
        self._header_hint.pack(anchor="w", pady=(4, 0))

        scroll_host = ScrollableFrame(outer)
        scroll_host.pack(fill=tk.BOTH, expand=True)
        # 起動直後の「CI の種類を選ぶ」画面と、入力フォームを入れ替えて表示する。
        self._chooser_frame = tk.Frame(scroll_host.inner, bg=COLOR_WINDOW_BG)
        self._form_frame = tk.Frame(scroll_host.inner, bg=COLOR_WINDOW_BG)
        self._build_mode_chooser(self._chooser_frame)

        content = self._form_frame
        self._build_beginner_card(content)
        self._build_env_card(content)
        self._build_preset_card(content)
        self._build_fpga_card(content)
        self._build_step_folder(content)
        self._build_step_git(content)
        self._build_step_storage(content)
        self._build_step_teams(content)
        self._build_step_jenkins(content)
        self._build_step_run(content)
        self._build_details_expander(content)

        self._build_statusbar(outer)
        self._show_chooser()


def run_app(initial_repository_root: str | None = None) -> None:
    app = ConfigureApp(initial_repository_root)
    app.mainloop()
