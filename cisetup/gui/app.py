from __future__ import annotations

import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .. import git_service, help_texts, paths, teams_service
from .. import environment_scan as env_scan
from ..ci_preset_catalog import PRESETS, find_preset
from ..config_repository import ConfigRepository
from ..jenkins_client import (
    JenkinsClient,
    JenkinsError,
    apply_settings,
    test_file_server_write,
)
from ..local_ci import LocalCIError, run_local_ci
from ..models import CISetupConfig, CISetupSecrets
from ..project_setup import (
    apply_auto_detection,
    count_projects,
    deploy_ci_files,
    find_test_project,
    has_solution_file,
)
from ..recent_project import RecentProjectStore
from .commit_dialog import prompt_commit_message
from .layout import (
    COLOR_BEGINNER_BG,
    COLOR_BEGINNER_BORDER,
    COLOR_BEGINNER_TITLE,
    COLOR_CARD_BG,
    COLOR_DESC,
    COLOR_ENV_BG,
    COLOR_PRESET_BG,
    COLOR_RUN_BG,
    COLOR_RUN_BORDER,
    COLOR_RUN_TITLE,
    COLOR_SERVER_BG,
    COLOR_SERVER_BORDER,
    COLOR_SERVER_TITLE,
    COLOR_STEP,
    COLOR_TEXT,
    COLOR_WINDOW_BG,
    Expander,
    ScrollableFrame,
    button,
    card,
    font,
    hint_label,
    mono_font,
    primary_button,
    section_title,
    set_scale,
    step_desc,
    step_title,
)
from .tooltip import attach_tooltip

PAD = {"padx": 6, "pady": 3}

ENV_LINKS = [
    ("Git", "https://git-scm.com/download/win"),
    (".NET SDK 8", "https://dotnet.microsoft.com/download/dotnet/8.0"),
    ("Java (Temurin)", "https://adoptium.net/"),
    ("Jenkins (LTS)", "https://www.jenkins.io/download/"),
]


def _safe_int(value: str, fallback: int) -> int:
    try:
        return int(value.strip())
    except (ValueError, AttributeError):
        return fallback


def _enable_dpi_awareness() -> None:
    """高 DPI（拡大率 125%/150% など）でぼやけないよう DPI 対応を有効化する。

    tkinter は既定で DPI 非対応のため、Windows がビットマップ拡大して
    ぼやけてしまう。C# WPF は DPI 対応なのでくっきり表示される。
    Tk() を生成する前に呼ぶ必要がある。
    """
    if sys.platform != "win32":
        return
    import ctypes

    # Per-Monitor v2（最もくっきり）。
    # DPI_AWARENESS_CONTEXT は HANDLE 相当のためポインタサイズで渡す。
    # 64bit プロセスで int(-4) を渡すとハンドル値が壊れて失敗するので
    # c_void_p(-4) を使い、戻り値も確認してからフォールバックする。
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:
        # Per-Monitor（Windows 8.1+）
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
            return
    except (AttributeError, OSError):
        pass
    try:
        # System DPI aware（Vista+）
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


class MultiValueField:
    """＋/− で行を増減できる複数入力欄グループ（パス／URL を複数指定するため）。

    各行は [入力欄][参照...（任意）][＋][−]。＋ で空行を追加、− で行を削除する。
    行が 1 つだけのときは − でクリアのみ（最低 1 行は常に表示）。空行は値取得時に無視。
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        browse: str | None = None,
        on_change=None,
        entry_width: int | None = None,
    ) -> None:
        self._browse = browse
        self._on_change = on_change
        self._entry_width = entry_width
        try:
            self._bg = parent.cget("bg")
        except tk.TclError:
            self._bg = COLOR_CARD_BG
        self.container = tk.Frame(parent, bg=self._bg)
        self.container.pack(fill=tk.X)
        self._rows: list[dict] = []
        self._add_row("")

    def _notify(self) -> None:
        if self._on_change:
            self._on_change()

    def _add_row(self, value: str = "") -> dict:
        frame = tk.Frame(self.container, bg=self._bg)
        frame.pack(fill=tk.X, pady=2)
        var = tk.StringVar(value=value)
        var.trace_add("write", lambda *_: self._notify())
        if self._entry_width:
            entry = ttk.Entry(frame, textvariable=var, width=self._entry_width, font=font(12))
        else:
            entry = ttk.Entry(frame, textvariable=var, font=font(12))
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)
        row = {"var": var, "frame": frame, "entry": entry}
        if self._browse == "folder":
            button(frame, "参照...", lambda v=var: self._browse_folder(v), padx=10).pack(
                side=tk.LEFT, padx=(6, 0)
            )
        button(frame, "＋", lambda: self._on_add(), padx=8).pack(side=tk.LEFT, padx=(6, 0))
        button(frame, "−", lambda r=row: self._on_remove(r), padx=8).pack(side=tk.LEFT, padx=(4, 0))
        self._rows.append(row)
        return row

    def _browse_folder(self, var: tk.StringVar) -> None:
        path = filedialog.askdirectory(title="フォルダを選択")
        if path:
            var.set(path)

    def _on_add(self) -> None:
        self._add_row("")
        self._notify()

    def _on_remove(self, row: dict) -> None:
        if len(self._rows) <= 1:
            row["var"].set("")
            return
        row["frame"].destroy()
        self._rows.remove(row)
        self._notify()

    def get_values(self) -> list[str]:
        return [r["var"].get().strip() for r in self._rows if r["var"].get().strip()]

    def set_values(self, values: list[str]) -> None:
        cleaned = [str(v) for v in (values or []) if str(v).strip()] or [""]
        for row in self._rows:
            row["frame"].destroy()
        self._rows.clear()
        for value in cleaned:
            self._add_row(value)

    def focus(self) -> None:
        if self._rows:
            try:
                self._rows[0]["entry"].focus_set()
            except tk.TclError:
                pass


class ConfigureApp(tk.Tk):
    def __init__(self, initial_repository_root: str | None = None) -> None:
        _enable_dpi_awareness()
        super().__init__()

        # ディスプレイの拡大率を取得し、フォント・サイズを追従させる。
        try:
            scale = self.winfo_fpixels("1i") / 96.0
        except tk.TclError:
            scale = 1.0
        self._scale = scale if scale > 0 else 1.0
        set_scale(self._scale)

        self.title("CISetup")
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
        self._multi_fields: dict[str, MultiValueField] = {}
        self._path_status: dict[str, tk.Label] = {}
        self._agent_command = tk.StringVar()
        self._server_log = tk.StringVar()
        self._env_result = tk.StringVar()
        self._loading = False

        self._build_ui()
        self._initial_load(initial_repository_root)

    def _px(self, value: float) -> int:
        """論理ピクセルを画面倍率に合わせた物理ピクセルへ変換する。"""
        return max(1, int(round(value * self._scale)))

    def _apply_window_icon(self) -> None:
        """ウィンドウ/タスクバーのアイコンを設定する（ソース実行・exe 双方対応）。"""
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

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        self.configure(bg=COLOR_WINDOW_BG)
        outer = tk.Frame(self, padx=18, pady=12, bg=COLOR_WINDOW_BG)
        outer.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(outer, bg=COLOR_WINDOW_BG)
        header.pack(fill=tk.X, pady=(0, 14))
        tk.Label(
            header,
            text="CISetup",
            font=font(24, bold=True),
            fg=COLOR_TEXT,
            bg=COLOR_WINDOW_BG,
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            header,
            text="上から順に入力して、最後の「セットアップを実行」を押すだけです。",
            font=font(12),
            fg=COLOR_DESC,
            bg=COLOR_WINDOW_BG,
            anchor="w",
        ).pack(anchor="w", pady=(4, 0))

        scroll_host = ScrollableFrame(outer)
        scroll_host.pack(fill=tk.BOTH, expand=True)
        content = scroll_host.inner

        self._build_beginner_card(content)
        self._build_env_card(content)
        self._build_preset_card(content)
        self._build_step_folder(content)
        self._build_step_git(content)
        self._build_step_teams(content)
        self._build_step_storage(content)
        self._build_step_jenkins(content)
        self._build_step_run(content)
        self._build_details_expander(content)

        self._build_statusbar(outer)

    def _build_beginner_card(self, parent: tk.Misc) -> None:
        frame = card(parent, bg=COLOR_BEGINNER_BG, border=COLOR_BEGINNER_BORDER)
        tk.Label(
            frame,
            text="はじめての方へ",
            font=font(15, bold=True),
            fg=COLOR_BEGINNER_TITLE,
            bg=COLOR_BEGINNER_BG,
            anchor="w",
        ).pack(anchor="w", pady=(0, 6))
        tk.Label(
            frame,
            text=(
                "① アプリのフォルダ → ② 社内 Git → ③ Teams → ④ 保存先 → ⑤ Jenkins 接続 を入力し、\n"
                "最後に「セットアップを実行」を押すと、保存・Jenkins 登録・Git push まで自動で行います。\n"
                "むずかしい項目は「詳細設定（ふだんは開かなくて OK）」にまとめてあり、ほとんど自動で入力されます。"
            ),
            font=font(12),
            fg="#555555",
            bg=COLOR_BEGINNER_BG,
            justify=tk.LEFT,
            anchor="w",
        ).pack(anchor="w")

    def _build_env_card(self, parent: tk.Misc) -> None:
        frame = card(parent, bg=COLOR_ENV_BG)
        section_title(frame, "環境チェック（まず確認）", COLOR_STEP).pack(anchor="w", pady=(0, 6))
        tk.Label(
            frame,
            text="必要なツールがこの PC に入っているかを自動で確認します。エージェント PC でも実行すると確実です。",
            font=font(12),
            fg=COLOR_DESC,
            bg=COLOR_ENV_BG,
            anchor="w",
            wraplength=self._px(860),
        ).pack(anchor="w", pady=(0, 10))
        button(
            frame,
            "環境をスキャン",
            lambda: self._run_async(self._scan_env),
            kind="accent",
            padx=20,
            pady=7,
        ).pack(anchor="w", pady=(0, 10))
        self._env_text = tk.Text(
            frame,
            height=8,
            wrap=tk.WORD,
            font=mono_font(12),
            relief=tk.SOLID,
            borderwidth=1,
            highlightthickness=0,
            background="#FFFFFF",
        )
        self._env_text.pack(fill=tk.X, pady=(0, 10))
        self._env_text.insert("1.0", "「環境をスキャン」を押すと結果がここに表示されます。")
        tk.Label(
            frame,
            text="入手先を開く（未検出のものをインストール）:",
            font=font(12),
            fg=COLOR_DESC,
            bg=COLOR_ENV_BG,
            anchor="w",
        ).pack(anchor="w", pady=(0, 4))
        links = tk.Frame(frame, bg=COLOR_ENV_BG)
        links.pack(anchor="w")
        for label, url in ENV_LINKS:
            button(
                links,
                label,
                lambda u=url: self._open_link(u),
            ).pack(side=tk.LEFT, padx=(0, 8), pady=(0, 8))

        prep = Expander(frame, "アプリで自動化できない準備（手順とリンク）")
        prep.configure(bg=COLOR_ENV_BG)
        prep._toggle.configure(bg=COLOR_ENV_BG)
        prep.content.configure(bg=COLOR_ENV_BG)
        prep.pack(fill=tk.X, pady=(6, 0))
        self._build_manual_prep(prep.content, COLOR_ENV_BG)

    def _build_manual_prep(self, parent: tk.Frame, bg: str) -> None:
        blocks = [
            (
                "① Jenkins 本体のインストール（初回・サーバー機）",
                "Windows MSI 版 LTS をサーバー機にインストールします。インストール後、画面の「詳細設定 → Jenkins サーバー初回設定」でプラグインとエージェントを自動登録できます。",
                ("Jenkins ダウンロードを開く", "https://www.jenkins.io/download/"),
            ),
            (
                "② 共有フォルダ（ファイルサーバー）の作成",
                "成果物 zip とログを置く共有フォルダ（例: \\\\fileserver\\ci）を作成し、エージェントの実行アカウントに書き込み権限を付与します。作成後は「詳細設定 → ファイルサーバー書き込みテスト」で確認できます。",
                None,
            ),
            (
                "③ Teams Webhook の作成",
                "Teams チャンネル → ワークフロー →「Webhook アラートをチャネルに送信する」で URL を取得し、③ Teams 通知 に貼り付けます。「テスト送信」で確認できます。",
                (
                    "Teams ワークフローの説明を開く",
                    "https://support.microsoft.com/ja-jp/office/teams-%E3%81%AE%E3%83%AF%E3%83%BC%E3%82%AF%E3%83%95%E3%83%AD%E3%83%BC",
                ),
            ),
            (
                "④ エージェント PC の起動",
                "エージェント PC に Java と .NET SDK 8 と Git を入れ、「詳細設定 → Jenkins サーバー初回設定」で表示される起動コマンドを実行します。Jenkins の Nodes で Online になれば準備完了です。",
                None,
            ),
        ]
        for title, body_text, link in blocks:
            tk.Label(parent, text=title, font=font(12, bold=True), fg="#444444", bg=bg, anchor="w").pack(
                anchor="w", pady=(0, 2)
            )
            tk.Label(
                parent,
                text=body_text,
                font=font(12),
                fg=COLOR_DESC,
                bg=bg,
                anchor="w",
                wraplength=self._px(840),
                justify=tk.LEFT,
            ).pack(anchor="w", pady=(0, 4))
            if link:
                button(
                    parent,
                    link[0],
                    lambda u=link[1]: self._open_link(u),
                ).pack(anchor="w", pady=(0, 12))
            else:
                tk.Frame(parent, height=8, bg=bg).pack()

    def _build_preset_card(self, parent: tk.Misc) -> None:
        frame = card(parent, bg=COLOR_PRESET_BG, border_width=2)
        section_title(frame, "まずはプリセットを選ぶ", COLOR_STEP).pack(anchor="w", pady=(0, 6))
        tk.Label(
            frame,
            text="作りたい CI の種類を選んで「適用」を押すと、ビルド種別やコマンドなどの環境設定が一括で入ります。あとはフォルダや Git などを埋めるだけです。",
            font=font(12),
            fg="#555555",
            bg=COLOR_PRESET_BG,
            anchor="w",
            wraplength=self._px(860),
        ).pack(anchor="w", pady=(0, 10))
        row = tk.Frame(frame, bg=COLOR_PRESET_BG)
        row.pack(fill=tk.X)
        self._preset_var = tk.StringVar()
        self._preset_combo = ttk.Combobox(
            row,
            textvariable=self._preset_var,
            values=[p.name for p in PRESETS],
            state="readonly",
            width=48,
            font=font(12),
        )
        self._preset_combo.pack(side=tk.LEFT)
        self._preset_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_preset_selected())
        button(
            row,
            "このプリセットを適用",
            self._apply_preset,
            kind="accent",
            padx=18,
            pady=7,
        ).pack(side=tk.LEFT, padx=(10, 0))
        self._preset_desc = tk.Label(
            frame,
            text="",
            font=font(12),
            fg=COLOR_DESC,
            bg=COLOR_PRESET_BG,
            anchor="w",
            wraplength=self._px(860),
            justify=tk.LEFT,
        )
        self._preset_desc.pack(fill=tk.X, pady=(8, 0))

    def _build_step_folder(self, parent: tk.Misc) -> None:
        frame = card(parent)
        step_title(frame, "① アプリのフォルダ").pack(anchor="w", pady=(0, 4))
        step_desc(
            frame,
            "ビルドしたいアプリのフォルダ（.sln がある場所）を選びます。選ぶと必要な CI ファイルが自動で置かれ、プロジェクト名なども自動入力されます。",
        ).pack(anchor="w", pady=(0, 10))
        row = tk.Frame(frame, bg=COLOR_CARD_BG)
        row.pack(fill=tk.X, pady=(0, 4))
        self._path_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._path_var, width=64, font=font(12)).pack(
            side=tk.LEFT, ipady=2
        )
        for text, cmd in (
            ("フォルダを選ぶ", self._pick_folder),
            ("読み込み", self._load_from_text),
            ("保存した設定を開く", self._open_saved),
        ):
            button(row, text, cmd).pack(side=tk.LEFT, padx=(8, 0))
        self._status_project = tk.Label(
            frame,
            text="",
            font=font(12),
            fg=COLOR_DESC,
            bg=COLOR_CARD_BG,
            anchor="w",
            wraplength=self._px(860),
            justify=tk.LEFT,
        )
        self._status_project.pack(anchor="w", pady=(6, 0))

    def _build_step_git(self, parent: tk.Misc) -> None:
        frame = card(parent)
        step_title(frame, "② 社内 Git の場所とログイン").pack(anchor="w", pady=(0, 4))
        step_desc(
            frame,
            "Jenkins がソースコードを取りに行く先です。リポジトリの URL と、アクセスできるユーザー名・パスワード（または個人トークン）を入力します。",
        ).pack(anchor="w", pady=(0, 10))
        self._add_field(frame, "git.repository_url", "リポジトリ URL", help_texts.GIT_REPOSITORY_URL, label_width=16)
        hint_label(frame, "例: https://git.example.com/team/MyApp.git").pack(anchor="w", padx=(150, 0))
        self._add_field(frame, "git.branch", "ブランチ", help_texts.GIT_BRANCH, label_width=16)
        hint_label(frame, "ビルド対象のブランチ。例: main または master（このブランチへのマージで自動ビルドされます）").pack(
            anchor="w", padx=(150, 0)
        )
        self._add_field(frame, "secrets.git_username", "ユーザー名", label_width=16)
        self._add_field(frame, "secrets.git_password", "パスワード / トークン", label_width=16)
        hint_label(frame, "社内 Git のパスワード、または個人アクセストークン (PAT)。Git には保存されません。").pack(
            anchor="w", padx=(150, 0)
        )

    def _build_step_teams(self, parent: tk.Misc) -> None:
        frame = card(parent)
        step_title(frame, "③ Teams 通知").pack(anchor="w", pady=(0, 4))
        step_desc(
            frame,
            "ビルドの成功・失敗を Teams に通知します。Teams チャンネルのワークフローで作った Webhook URL を貼り付け、「テスト送信」で届くか確認できます。",
        ).pack(anchor="w", pady=(0, 10))
        tk.Label(frame, text="Webhook URL", font=font(12), bg=COLOR_CARD_BG, anchor="w").pack(anchor="w")
        self._add_field(frame, "secrets.teams_webhook_url", "", label_width=0, show_label=False)
        hint_label(frame, "Teams チャンネル → ワークフロー →「Webhook アラートをチャネルに送信する」で取得。").pack(anchor="w")
        tk.Label(
            frame,
            text="通知ボタンのリンク先（任意）",
            font=font(12, bold=True),
            fg=COLOR_TEXT,
            bg=COLOR_CARD_BG,
            anchor="w",
        ).pack(anchor="w", pady=(12, 2))
        hint_label(
            frame,
            "Teams のボタンから開く共有 URL（OneDrive / SharePoint 等）。"
            "ファイルの書き込み先は ④ CI_FILE_SERVER または詳細設定の「書き込み先ベース」"
            "（同期フォルダ等のパス）で、ここは閲覧用リンクです。"
            "各欄は右端の「＋」で複数 URL を追加でき、通知では全リンクをボタン表示します。"
            "テスト失敗時のみカードに失敗テスト名とログボタンが表示されます。",
        ).pack(anchor="w")
        for key, label, help_text in (
            ("storage.analysis_urls", "解析レポート URL", help_texts.ANALYSIS_URL),
            ("storage.release_urls", "成果物フォルダ URL", help_texts.RELEASE_URL),
            ("storage.logs_urls", "ログフォルダ URL", help_texts.LOGS_URL),
            ("storage.tests_urls", "ユニットテストログ URL", help_texts.TESTS_URL),
        ):
            self._add_multi_field(frame, key, label, help_text)
        button(
            frame,
            "テスト送信",
            lambda: self._run_async(self._test_teams),
            padx=16,
        ).pack(anchor="w", pady=(10, 0))

    def _build_step_storage(self, parent: tk.Misc) -> None:
        frame = card(parent)
        step_title(frame, "④ 成果物・ログの保存先（共有フォルダ）").pack(anchor="w", pady=(0, 4))
        step_desc(
            frame,
            "ビルドした zip や失敗ログを置く共有フォルダです。この下にプロジェクト名のフォルダが自動で作られます。",
        ).pack(anchor="w", pady=(0, 10))
        self._add_multi_field(frame, "jenkins.ci_file_servers", browse="folder")
        hint_label(
            frame,
            "例: \\\\fileserver\\ci（この下に自動でプロジェクト名フォルダを作成）。"
            "右端の「＋」で書き込み先を追加でき、設定した全先に成果物をコピーします。"
            "「−」で行を削除します。個人 ID を含むパスは Git に push されません。",
        ).pack(anchor="w")
        self._archive_source_var = tk.BooleanVar(value=False)
        cb = tk.Checkbutton(
            frame,
            text="開発環境一式（pull した最新ソース）を zip 化して保存する",
            variable=self._archive_source_var,
            command=self._on_field_changed,
            font=font(12),
            bg=COLOR_CARD_BG,
            activebackground=COLOR_CARD_BG,
            anchor="w",
        )
        cb.pack(anchor="w", pady=(8, 0))
        attach_tooltip(cb, help_texts.ARCHIVE_SOURCE)
        hint_label(
            frame,
            "チェックすると CI が .git / artifacts / bin / obj 等を除外してソースツリーを zip 化し、"
            "保存先の「source」フォルダ（詳細設定で名称変更可）へ格納します。",
        ).pack(anchor="w")

    def _build_step_jenkins(self, parent: tk.Misc) -> None:
        frame = card(parent)
        step_title(frame, "⑤ Jenkins への接続").pack(anchor="w", pady=(0, 4))
        step_desc(
            frame,
            "設定を登録する Jenkins サーバーです。URL・ユーザー名・API Token を入れ、「接続テスト」で確認します。",
        ).pack(anchor="w", pady=(0, 10))
        self._add_field(
            frame, "secrets.jenkins_url", "Jenkins URL", help_texts.JENKINS_URL, label_width=16
        )
        self._add_field(
            frame, "secrets.jenkins_user", "ユーザー名", help_texts.JENKINS_USER, label_width=16
        )
        self._add_field(
            frame, "secrets.jenkins_api_token", "API Token", help_texts.JENKINS_API_TOKEN, label_width=16
        )
        hint_label(
            frame,
            "Jenkins URL は普段ブラウザで開くトップ URL（例: http://localhost:8086/）。"
            "API Token は 右上のユーザー名 → Configure → API Token → Add new Token で発行。",
        ).pack(anchor="w", padx=(150, 0))
        button(
            frame,
            "接続テスト",
            lambda: self._run_async(self._test_jenkins),
            padx=16,
        ).pack(anchor="w", pady=(10, 0), padx=(150, 0))

    def _build_step_run(self, parent: tk.Misc) -> None:
        frame = card(parent, bg=COLOR_RUN_BG, border=COLOR_RUN_BORDER, border_width=2)
        section_title(frame, "⑥ セットアップを実行", COLOR_RUN_TITLE).pack(anchor="w", pady=(0, 6))
        tk.Label(
            frame,
            text="チェックした処理だけを上から順番に実行します。\n"
            "「テストビルド」は Jenkins がリモート Git のコードをビルドするため、"
            "最新の変更を確認するときは「Git push」も一緒に有効にしてください"
            "（push してからビルドする順で実行します）。\n"
            "「ローカルでビルド＆テスト」は push せずに現在のローカルコードを検証します"
            "（git 操作なし。push 前の動作確認に便利）。\n"
            "まず 保存 → Jenkins 反映 だけで設定を反映し、準備ができたら push＋テストビルドで確認する運用がおすすめです。",
            font=font(12),
            fg="#555555",
            bg=COLOR_RUN_BG,
            anchor="w",
            justify=tk.LEFT,
            wraplength=self._px(860),
        ).pack(anchor="w", pady=(0, 12))

        self._step_save_var = tk.BooleanVar(value=True)
        self._step_local_var = tk.BooleanVar(value=False)
        self._step_jenkins_var = tk.BooleanVar(value=True)
        self._step_push_var = tk.BooleanVar(value=False)
        self._step_build_var = tk.BooleanVar(value=False)
        options = tk.Frame(frame, bg=COLOR_RUN_BG)
        options.pack(anchor="w", pady=(0, 12))
        for text, var in (
            ("1. 設定を保存", self._step_save_var),
            ("ローカルでビルド＆テスト（push せず現在のコードを検証）", self._step_local_var),
            ("2. Jenkins に反映", self._step_jenkins_var),
            ("3. Git push", self._step_push_var),
            ("4. テストビルドを実行", self._step_build_var),
        ):
            cb = tk.Checkbutton(
                options,
                text=text,
                variable=var,
                font=font(12),
                bg=COLOR_RUN_BG,
                activebackground=COLOR_RUN_BG,
                anchor="w",
            )
            cb.pack(anchor="w")
            if var is self._step_local_var:
                attach_tooltip(cb, help_texts.LOCAL_BUILD_TEST)

        row = tk.Frame(frame, bg=COLOR_RUN_BG)
        row.pack(anchor="w")
        primary_button(
            row, "セットアップを実行", lambda: self._run_async(self._run_setup)
        ).pack(side=tk.LEFT)
        button(
            row,
            "設定だけ保存",
            lambda: self._run_async(self._save_only),
            size_px=15,
            padx=20,
            pady=10,
            bold=False,
        ).pack(side=tk.LEFT, padx=(10, 0))
        self._publish_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            frame,
            text="テストビルドで成果物 zip も作成・保存する",
            variable=self._publish_var,
            font=font(12),
            bg=COLOR_RUN_BG,
            activebackground=COLOR_RUN_BG,
            anchor="w",
        ).pack(anchor="w", pady=(12, 0))
        tk.Label(
            frame,
            text="ローカルビルド＆テストの実行ログ",
            font=font(12, bold=True),
            bg=COLOR_RUN_BG,
            anchor="w",
        ).pack(anchor="w", pady=(12, 2))
        self._run_log_text = tk.Text(
            frame, height=8, wrap=tk.WORD, font=mono_font(12), relief=tk.SOLID, borderwidth=1,
            highlightthickness=0, background="#FFFFFF",
        )
        self._run_log_text.pack(fill=tk.X)

    def _build_details_expander(self, parent: ttk.Frame) -> None:
        exp = Expander(parent, "詳細設定（ふだんは開かなくて OK・自動入力されています）")
        exp.pack(fill=tk.X, pady=(0, 14))
        self._details_expander = exp
        details = exp.content
        self._build_details_build(details)
        self._build_details_project(details)
        self._build_details_storage(details)
        self._build_details_ci_job(details)
        self._build_details_server(details)
        self._build_details_manual(details)

    def _build_details_build(self, parent: tk.Frame) -> None:
        frame = card(parent)
        step_title(frame, "ビルド種別（.NET 以外でも使えます）").pack(anchor="w", pady=(0, 4))
        step_desc(
            frame,
            "ふだんは「.NET」のままで OK。FPGA（Vivado 等）や他言語で使う場合は「カスタムコマンド」を選び、各ステップで実行するコマンドを入力します。",
        ).pack(anchor="w", pady=(0, 8))
        self._profile_var = tk.StringVar(value="dotnet")
        profile_combo = ttk.Combobox(
            frame,
            textvariable=self._profile_var,
            values=[
                ".NET（dotnet build / format / publish を自動実行）",
                "カスタムコマンド（FPGA・C/C++・Python など任意）",
            ],
            state="readonly",
            width=58,
            font=font(12),
        )
        profile_combo.pack(anchor="w")
        profile_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_profile_changed())
        self._custom_build_panel = tk.Frame(frame, bg=COLOR_CARD_BG)
        hint_label(
            self._custom_build_panel,
            "各コマンドはエージェントの作業ディレクトリ（リポジトリ直下）で PowerShell として実行されます。空欄のステップはスキップされます（ビルドは必須）。",
        ).pack(anchor="w", pady=(12, 0))
        for key, title, tip in (
            ("build.build_command", "ビルド コマンド（必須）", "例: vivado -mode batch -source build.tcl"),
            ("build.lint_command", "Lint / チェック コマンド（任意）", "例: verilator --lint-only -Wall src/top.v"),
            ("build.test_command", "テスト コマンド（任意）", "例: pytest -q または dotnet test tests/MyApp.Tests"),
            ("build.analyze_command", "解析 コマンド（任意）", "例: タイミング/使用率レポートの生成・集計スクリプト"),
            ("build.publish_command", "成果物生成 コマンド（任意）", "例: ビットストリーム生成など（成果物は下の glob で収集します）"),
        ):
            tk.Label(
                self._custom_build_panel,
                text=title,
                font=font(12, bold=True),
                bg=COLOR_CARD_BG,
                anchor="w",
            ).pack(anchor="w", pady=(8, 2))
            self._add_field(self._custom_build_panel, key, "", show_label=False)
            if tip:
                hint_label(self._custom_build_panel, tip).pack(anchor="w")
        tk.Label(
            self._custom_build_panel,
            text="成果物ファイル（glob・; 区切り）",
            font=font(12, bold=True),
            bg=COLOR_CARD_BG,
            anchor="w",
        ).pack(anchor="w", pady=(8, 2))
        self._add_field(self._custom_build_panel, "build.artifact_glob", "", show_label=False)
        hint_label(
            self._custom_build_panel,
            "例: **/*.bit;**/*.bin;reports/*.rpt — マッチしたファイルを zip にして成果物として保存します。",
        ).pack(anchor="w")

    def _build_details_project(self, parent: tk.Frame) -> None:
        frame = card(parent)
        step_title(frame, "自動入力された項目（必要なら変更）").pack(anchor="w", pady=(0, 8))
        for key, label, help_text, browse in (
            ("project.name", "プロジェクト名", help_texts.PROJECT_NAME, None),
            ("project.solution_file", "ソリューション (.sln)", help_texts.SOLUTION_FILE, "file"),
            ("project.publish_project", "Publish 対象 (.csproj)", help_texts.PUBLISH_PROJECT, "file"),
            ("project.test_project", "テスト対象 (.csproj)", help_texts.TEST_PROJECT, "file"),
            ("project.artifact_prefix", "成果物 zip プレフィックス", help_texts.ARTIFACT_PREFIX, None),
        ):
            self._add_field(
                frame,
                key,
                label,
                help_text,
                label_width=22,
                browse=browse,
                path_check=(browse == "file"),
            )
        hint_label(
            frame,
            "テスト対象を空にすると CI の Test ステージはスキップされます。"
            "「再検出」は空欄・プレースホルダに加え、実在しないパスも探し直して差し替えます。"
            "（各欄の右側に実在チェックを表示します）",
        ).pack(anchor="w")
        btn_row = tk.Frame(frame, bg=COLOR_CARD_BG)
        btn_row.pack(anchor="w", pady=(12, 8))
        self._redetect_btn = button(
            btn_row,
            "自動入力をやり直す（再検出）",
            self._redetect_project,
            state=tk.DISABLED,
        )
        self._redetect_btn.pack(side=tk.LEFT, padx=(0, 8))
        self._redeploy_btn = button(
            btn_row,
            "CI ファイルを再配置",
            self._redeploy_ci,
            state=tk.DISABLED,
        )
        self._redeploy_btn.pack(side=tk.LEFT)
        self._deploy_log_text = tk.Text(
            frame, height=3, wrap=tk.WORD, font=mono_font(12), relief=tk.SOLID, borderwidth=1,
            highlightthickness=0, background="#FFFFFF",
        )
        self._deploy_log_text.pack(fill=tk.X)

    def _build_details_storage(self, parent: tk.Frame) -> None:
        frame = card(parent)
        step_title(frame, "保存先の詳細").pack(anchor="w", pady=(0, 8))
        self._add_multi_field(
            frame,
            "storage.base_paths",
            "書き込み先ベース (任意・複数可)",
            help_texts.STORAGE_BASE_PATH,
            browse="folder",
        )
        hint_label(
            frame,
            "④ CI_FILE_SERVER と併用でき、両方に入れた全先へコピーします（相互排他ではありません）。"
            "「＋」で追加、「−」で削除。個人 ID を含むパスは Git に push されません。",
        ).pack(anchor="w")
        self._add_field(frame, "storage.logs_dir", "ログフォルダ名", help_texts.LOGS_DIR, label_width=22)
        self._add_field(frame, "storage.releases_dir", "成果物フォルダ名", help_texts.RELEASES_DIR, label_width=22)
        self._add_field(frame, "storage.tests_dir", "テスト成果物フォルダ名", help_texts.TESTS_DIR, label_width=22)
        self._add_field(frame, "storage.source_dir", "ソースフォルダ名", help_texts.SOURCE_DIR, label_width=22)
        row = tk.Frame(frame, bg=COLOR_CARD_BG)
        row.pack(fill=tk.X, pady=4)
        self._use_date_var = tk.BooleanVar(value=True)
        cb = tk.Checkbutton(
            row,
            text="日付フォルダ (YYYYMMDD) を使う",
            variable=self._use_date_var,
            command=self._on_field_changed,
            font=font(12),
            bg=COLOR_CARD_BG,
            activebackground=COLOR_CARD_BG,
        )
        cb.pack(side=tk.LEFT)
        attach_tooltip(cb, help_texts.USE_DATE_SUBFOLDER)
        preview = tk.LabelFrame(
            frame, text="保存先プレビュー", padx=10, pady=10, bg=COLOR_CARD_BG, font=font(11)
        )
        preview.pack(fill=tk.X, pady=(8, 0))
        self._preview_logs = tk.StringVar()
        self._preview_releases = tk.StringVar()
        self._preview_tests = tk.StringVar()
        self._preview_source = tk.StringVar()
        tk.Label(
            preview,
            text="レイアウト例（先頭の書き込み先・他の先も同じ構造）",
            font=font(11),
            bg=COLOR_CARD_BG,
            fg=COLOR_DESC,
            anchor="w",
        ).pack(anchor="w", pady=(0, 4))
        for title, var in (
            ("失敗時（ログ）", self._preview_logs),
            ("成功時（成果物 zip）", self._preview_releases),
            ("毎回（テスト成果物）", self._preview_tests),
            ("毎回（開発環境 zip・有効時）", self._preview_source),
        ):
            tk.Label(preview, text=title, font=font(12, bold=True), bg=COLOR_CARD_BG, anchor="w").pack(anchor="w")
            ttk.Entry(preview, textvariable=var, state="readonly", font=font(12)).pack(fill=tk.X, pady=(4, 8))
        tk.Label(
            preview,
            text="全書き込み先（この全てにコピー / ④はプロジェクト名を付与）",
            font=font(12, bold=True),
            bg=COLOR_CARD_BG,
            anchor="w",
        ).pack(anchor="w")
        self._preview_targets = tk.StringVar()
        tk.Label(
            preview,
            textvariable=self._preview_targets,
            font=mono_font(11),
            bg=COLOR_CARD_BG,
            fg=COLOR_DESC,
            anchor="w",
            justify=tk.LEFT,
            wraplength=self._px(820),
        ).pack(anchor="w", pady=(4, 0))

    def _build_details_ci_job(self, parent: tk.Frame) -> None:
        frame = card(parent)
        step_title(frame, "CI ジョブの詳細").pack(anchor="w", pady=(0, 8))
        for key, label, help_text in (
            ("jenkins.job_name", "ジョブ名", help_texts.JOB_NAME),
            ("jenkins.cron_schedule", "cron（定期実行）", help_texts.CRON_SCHEDULE),
            ("jenkins.poll_schedule", "pollSCM（マージ検知）", help_texts.POLL_SCHEDULE),
            ("jenkins.agent_label", "エージェントラベル", help_texts.AGENT_LABEL),
            ("jenkins.teams_credential_id", "Teams Credential ID", help_texts.TEAMS_CREDENTIAL_ID),
            ("git.credential_id", "Git Credential ID", help_texts.GIT_CREDENTIAL_ID),
            ("jenkins.timezone", "タイムゾーン", help_texts.TIMEZONE),
        ):
            self._add_field(frame, key, label, help_text, label_width=22)
        row = tk.Frame(frame, bg=COLOR_CARD_BG)
        row.pack(fill=tk.X, pady=4)
        tk.Label(
            row, text="ビルドタイムアウト (分) / ログ保持数", width=22, anchor="w", bg=COLOR_CARD_BG, font=font(12)
        ).pack(side=tk.LEFT)
        self._register_field("jenkins.build_timeout_minutes")
        self._register_field("jenkins.log_retention_count")
        ttk.Entry(row, textvariable=self._fields["jenkins.build_timeout_minutes"], width=8, font=font(12)).pack(side=tk.LEFT)
        tk.Label(row, text="分", bg=COLOR_CARD_BG, font=font(12)).pack(side=tk.LEFT, padx=(6, 16))
        ttk.Entry(row, textvariable=self._fields["jenkins.log_retention_count"], width=8, font=font(12)).pack(side=tk.LEFT)
        tk.Label(row, text="件保持", bg=COLOR_CARD_BG, font=font(12)).pack(side=tk.LEFT, padx=(6, 0))

    def _build_details_server(self, parent: tk.Frame) -> None:
        frame = card(parent, bg=COLOR_SERVER_BG, border=COLOR_SERVER_BORDER)
        section_title(frame, "Jenkins サーバー初回設定（はじめてのときだけ）", COLOR_SERVER_TITLE).pack(
            anchor="w", pady=(0, 4)
        )
        tk.Label(
            frame,
            text="Jenkins LTS インストール後に一度だけ実行します。必須プラグインのインストールと Windows エージェント登録を自動で行います。",
            font=font(12),
            fg=COLOR_DESC,
            bg=COLOR_SERVER_BG,
            anchor="w",
            wraplength=self._px(860),
        ).pack(anchor="w", pady=(0, 12))
        self._add_field(frame, "server.agent_name", "エージェント名", help_texts.JENKINS_AGENT_NAME, label_width=22)
        self._add_field(
            frame,
            "server.agent_root",
            "エージェント作業フォルダ",
            help_texts.JENKINS_AGENT_ROOT,
            label_width=22,
            browse="folder",
        )
        self._fields["server.agent_name"].set("windows-agent")
        self._fields["server.agent_root"].set(r"C:\Jenkins\workspace")
        btn_row = tk.Frame(frame, bg=COLOR_SERVER_BG)
        btn_row.pack(anchor="w", pady=(0, 8))
        button(
            btn_row,
            "Jenkins サーバーを初期設定",
            lambda: self._run_async(self._setup_server),
            kind="warn",
            padx=16,
        ).pack(side=tk.LEFT, padx=(0, 8))
        button(
            btn_row,
            "ファイルサーバー書き込みテスト",
            lambda: self._run_async(self._test_file_server),
            padx=16,
        ).pack(side=tk.LEFT)
        tk.Label(frame, text="実行ログ", font=font(12, bold=True), bg=COLOR_SERVER_BG, anchor="w").pack(anchor="w")
        self._server_log_text = tk.Text(
            frame, height=4, wrap=tk.WORD, font=mono_font(12), relief=tk.SOLID, borderwidth=1,
            highlightthickness=0, background="#FFFFFF",
        )
        self._server_log_text.pack(fill=tk.X, pady=(4, 8))
        tk.Label(
            frame,
            text="エージェント PC で実行するコマンド",
            font=font(12, bold=True),
            bg=COLOR_SERVER_BG,
            anchor="w",
        ).pack(anchor="w")
        self._agent_command_text = tk.Text(
            frame, height=4, wrap=tk.WORD, font=mono_font(12), relief=tk.SOLID, borderwidth=1,
            highlightthickness=0, background="#FFFFFF",
        )
        self._agent_command_text.pack(fill=tk.X, pady=(4, 8))
        button(frame, "起動コマンドをコピー", self._copy_agent_command).pack(anchor="w")

    def _build_details_manual(self, parent: tk.Frame) -> None:
        frame = card(parent)
        step_title(frame, "手動操作（個別に実行したいとき）").pack(anchor="w", pady=(0, 8))
        wrap = tk.Frame(frame, bg=COLOR_CARD_BG)
        wrap.pack(anchor="w")
        specs = [
            ("保存のみ", self._save_only),
            ("Jenkins に反映のみ", self._apply_jenkins),
            ("Git push のみ", self._git_push),
            ("今すぐビルド", self._build_now),
            ("再読み込み", self._reload),
        ]
        for text, func in specs:
            btn = button(wrap, text, lambda f=func: self._run_async(f), padx=16)
            if text == "Git push のみ":
                self._git_push_btn = btn
                btn.configure(state=tk.DISABLED)
            btn.pack(side=tk.LEFT, padx=(0, 8), pady=(0, 8))

    def _build_statusbar(self, parent: tk.Frame) -> None:
        bar = tk.Frame(parent, bg=COLOR_WINDOW_BG)
        bar.pack(fill=tk.X, pady=(12, 0))
        tk.Label(bar, text="状態:", font=font(12, bold=True), bg=COLOR_WINDOW_BG, fg=COLOR_TEXT).pack(side=tk.LEFT)
        self._status = tk.Label(
            bar, text="準備完了", font=font(12), fg="#444444", bg=COLOR_WINDOW_BG, anchor="w"
        )
        self._status.pack(side=tk.LEFT, padx=(6, 0), fill=tk.X, expand=True)

    def _register_field(self, key: str) -> tk.StringVar:
        if key not in self._fields:
            var = tk.StringVar()
            var.trace_add("write", lambda *_: self._on_field_changed())
            self._fields[key] = var
        return self._fields[key]

    def _add_multi_field(
        self,
        parent: tk.Misc,
        key: str,
        label: str = "",
        help_text: str = "",
        browse: str | None = None,
    ) -> MultiValueField:
        """＋/− で増減できる複数入力欄グループを追加する（書き込み先・閲覧 URL 用）。"""
        try:
            bg = parent.cget("bg")
        except tk.TclError:
            bg = COLOR_CARD_BG
        if label:
            lbl = tk.Label(parent, text=label, anchor="w", bg=bg, font=font(12))
            lbl.pack(anchor="w", pady=(6, 0))
            if help_text:
                attach_tooltip(lbl, help_text)
        field = MultiValueField(parent, browse=browse, on_change=self._on_field_changed)
        self._multi_fields[key] = field
        return field

    def _add_field(
        self,
        parent: tk.Misc,
        key: str,
        label: str,
        help_text: str = "",
        show: str | None = None,
        browse: str | None = None,
        label_width: int = 26,
        show_label: bool = True,
        path_check: bool = False,
    ) -> None:
        try:
            bg = parent.cget("bg")
        except tk.TclError:
            bg = COLOR_CARD_BG
        row = tk.Frame(parent, bg=bg)
        row.pack(fill=tk.X, pady=4)
        lbl = None
        if show_label and label:
            lbl = tk.Label(row, text=label, width=label_width, anchor="w", bg=bg, font=font(12))
            lbl.pack(side=tk.LEFT, anchor="n")
        var = self._register_field(key)
        entry = (
            ttk.Entry(row, textvariable=var, show=show, font=font(12))
            if show
            else ttk.Entry(row, textvariable=var, font=font(12))
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)
        self._field_widgets[key] = entry
        if help_text:
            if lbl:
                attach_tooltip(lbl, help_text)
            attach_tooltip(entry, help_text)
        if browse == "file":
            button(row, "参照...", lambda k=key: self._browse_file(k), padx=10).pack(
                side=tk.LEFT, padx=(8, 0)
            )
        elif browse == "folder":
            button(row, "参照...", lambda k=key: self._browse_folder(k), padx=10).pack(
                side=tk.LEFT, padx=(8, 0)
            )
        if path_check:
            status = tk.Label(
                row, text="", width=22, anchor="w", bg=bg, font=font(11)
            )
            status.pack(side=tk.LEFT, padx=(8, 0))
            self._path_status[key] = status

    def _on_profile_changed(self) -> None:
        is_custom = self._profile_var.get().startswith("カスタム")
        if is_custom:
            self._custom_build_panel.pack(fill=tk.X, pady=(12, 0))
        else:
            self._custom_build_panel.pack_forget()
        self._on_field_changed()

    def _open_link(self, url: str) -> None:
        webbrowser.open(url)

    # ------------------------------------------------------------- loading

    def _initial_load(self, initial: str | None) -> None:
        if initial and Path(initial).is_dir():
            self._open_project(Path(initial))
            return
        recent = self._recent.get_last_project_root()
        if recent:
            self._open_project(recent)
            return
        root = self._repo.find_repository_root(Path.cwd())
        if root:
            self._open_project(root)
        else:
            self._set_status("「フォルダを選ぶ」または「保存した設定を開く」を押してください。")

    def _open_project(self, repository_root: Path) -> None:
        repository_root = paths.normalize_project_root(repository_root)
        has_config = paths.has_saved_config(repository_root)
        if not has_config:
            self._deploy_ci_files(repository_root)
        self._load_repository(repository_root)

    def _deploy_ci_files(self, repository_root: Path) -> None:
        written = deploy_ci_files(repository_root)
        log = (
            "（配置済みのファイルはそのまま）"
            if not written
            else "\n".join(f"+ {path}" for path in written)
        )
        self._set_text(self._deploy_log_text, log)
        if not has_solution_file(repository_root):
            self._status_project.configure(
                text="警告: *.sln が見つかりません。.sln があるリポジトリルートか確認してください。",
                fg="#c33",
            )
        else:
            self._status_project.configure(text="CI ファイルを配置しました。", fg="#2a2")
        self._set_status(f"CI ファイルを配置: {len(written)} 件")

    def _redeploy_ci(self) -> None:
        root = self._ensure_repo()
        self._deploy_ci_files(root)
        self._set_status("CI ファイルを再配置しました。")

    def _redetect_project(self) -> None:
        """.sln から再検出して補完・修正する（実在しないパスも探し直す。有効な入力は保持）。"""
        root = self._ensure_repo()
        self._form_to_config()
        before = (
            self._config.project.name,
            self._config.project.solution_file,
            self._config.project.publish_project,
            self._config.project.test_project,
            self._config.project.artifact_prefix,
        )
        self._config = apply_auto_detection(root, self._config)
        after = (
            self._config.project.name,
            self._config.project.solution_file,
            self._config.project.publish_project,
            self._config.project.test_project,
            self._config.project.artifact_prefix,
        )
        self._config_to_form()
        self._update_preview()
        if before != after:
            self._set_status("再検出: 値を自動入力・修正しました（有効な入力は保持）。")
            return
        # 変化なし。csproj が見つからない場合は、選択フォルダがリポジトリルートか確認を促す。
        if count_projects(root) == 0:
            self._set_status(
                "再検出: .sln 内のプロジェクトも .csproj も見つかりません。"
                "選択フォルダがリポジトリのルート（.sln と同じ階層）か確認してください。"
            )
        else:
            self._set_status("再検出: 変更点はありませんでした（既に有効な値です）。")

    def _load_repository(self, repository_root: Path) -> None:
        self._loading = True
        try:
            self._repository_root = repository_root
            self._path_var.set(str(repository_root))
            has_config = paths.has_saved_config(repository_root)
            self._config = self._repo.load_config(repository_root)
            if not has_config:
                self._config = apply_auto_detection(repository_root, self._config)
            self._secrets = self._repo.load_secrets(repository_root)
            self._loaded_default_configuration = (
                self._config.jenkins.default_configuration or "Release"
            )
            self._config_to_form()
            self._recent.save(repository_root)
            self._update_project_ui()
            self._set_status(
                f"保存済みの設定を読み込みました: {repository_root}"
                if has_config
                else f"読み込みました: {repository_root}"
            )
        finally:
            self._loading = False
        self._update_preview()

    # ----------------------------------------------------------- form sync

    def _config_to_form(self) -> None:
        c = self._config
        mapping = {
            "project.name": c.project.name,
            "project.solution_file": c.project.solution_file,
            "project.publish_project": c.project.publish_project,
            "project.test_project": c.project.test_project,
            "project.artifact_prefix": c.project.artifact_prefix,
            "storage.logs_dir": c.storage.logs_dir,
            "storage.releases_dir": c.storage.releases_dir,
            "storage.tests_dir": c.storage.tests_dir,
            "storage.source_dir": c.storage.source_dir,
            "jenkins.job_name": c.jenkins.job_name,
            "jenkins.agent_label": c.jenkins.agent_label,
            "jenkins.cron_schedule": c.jenkins.cron_schedule,
            "jenkins.poll_schedule": c.jenkins.poll_schedule,
            "jenkins.teams_credential_id": c.jenkins.teams_credential_id,
            "jenkins.timezone": c.jenkins.timezone,
            "jenkins.build_timeout_minutes": str(c.jenkins.build_timeout_minutes),
            "jenkins.log_retention_count": str(c.jenkins.log_retention_count),
            "git.repository_url": c.git.repository_url,
            "git.branch": c.git.branch,
            "git.credential_id": c.git.credential_id,
            "build.build_command": c.build.build_command,
            "build.lint_command": c.build.lint_command,
            "build.analyze_command": c.build.analyze_command,
            "build.publish_command": c.build.publish_command,
            "build.test_command": c.build.test_command,
            "build.artifact_glob": c.build.artifact_glob,
            "secrets.jenkins_url": self._secrets.jenkins_url,
            "secrets.jenkins_user": self._secrets.jenkins_user,
            "secrets.jenkins_api_token": self._secrets.jenkins_api_token,
            "secrets.git_username": self._secrets.git_username,
            "secrets.git_password": self._secrets.git_password,
            "secrets.teams_webhook_url": self._secrets.teams_webhook_url,
        }
        for key, value in mapping.items():
            if key in self._fields:
                self._fields[key].set(value or "")

        multi_values = {
            "jenkins.ci_file_servers": c.jenkins.ci_file_servers,
            "storage.base_paths": c.storage.base_paths,
            "storage.release_urls": c.storage.release_urls,
            "storage.analysis_urls": c.storage.analysis_urls,
            "storage.logs_urls": c.storage.logs_urls,
            "storage.tests_urls": c.storage.tests_urls,
        }
        for key, values in multi_values.items():
            if key in self._multi_fields:
                self._multi_fields[key].set_values(list(values))

        self._use_date_var.set(c.storage.use_date_subfolder)
        self._archive_source_var.set(c.storage.archive_source)
        is_custom = c.build.profile.lower() == "custom"
        self._profile_var.set(
            "カスタムコマンド（FPGA・C/C++・Python など任意）"
            if is_custom
            else ".NET（dotnet build / format / publish を自動実行）"
        )
        self._on_profile_changed()

        preset = find_preset(c.build.preset)
        if preset:
            self._preset_var.set(preset.name)
            self._preset_desc.configure(text=preset.description)

    def _form_to_config(self) -> None:
        def get(key: str) -> str:
            return self._fields[key].get().strip()

        def get_multi(key: str) -> list[str]:
            field = self._multi_fields.get(key)
            return field.get_values() if field else []

        c = self._config
        c.project.name = get("project.name")
        c.project.solution_file = self._normalize_rel(get("project.solution_file"))
        c.project.publish_project = self._normalize_rel(get("project.publish_project"))
        c.project.test_project = self._normalize_rel(get("project.test_project"))
        c.project.artifact_prefix = get("project.artifact_prefix")

        c.storage.base_paths = get_multi("storage.base_paths")
        c.storage.logs_dir = get("storage.logs_dir") or "logs"
        c.storage.releases_dir = get("storage.releases_dir") or "releases"
        c.storage.tests_dir = get("storage.tests_dir") or "tests"
        c.storage.source_dir = get("storage.source_dir") or "source"
        c.storage.release_urls = get_multi("storage.release_urls")
        c.storage.analysis_urls = get_multi("storage.analysis_urls")
        c.storage.logs_urls = get_multi("storage.logs_urls")
        c.storage.tests_urls = get_multi("storage.tests_urls")
        c.storage.use_date_subfolder = bool(self._use_date_var.get())
        c.storage.archive_source = bool(self._archive_source_var.get())

        c.jenkins.job_name = get("jenkins.job_name")
        c.jenkins.agent_label = get("jenkins.agent_label")
        c.jenkins.cron_schedule = get("jenkins.cron_schedule")
        c.jenkins.poll_schedule = get("jenkins.poll_schedule")
        c.jenkins.ci_file_servers = get_multi("jenkins.ci_file_servers")
        c.jenkins.teams_credential_id = get("jenkins.teams_credential_id")
        c.jenkins.timezone = get("jenkins.timezone")
        c.jenkins.build_timeout_minutes = _safe_int(get("jenkins.build_timeout_minutes"), 30)
        c.jenkins.log_retention_count = _safe_int(get("jenkins.log_retention_count"), 30)
        c.jenkins.default_configuration = self._loaded_default_configuration

        c.git.repository_url = get("git.repository_url")
        c.git.branch = get("git.branch")
        c.git.credential_id = get("git.credential_id")

        is_custom = self._profile_var.get().startswith("カスタム")
        c.build.profile = "custom" if is_custom else "dotnet"
        c.build.build_command = get("build.build_command")
        c.build.lint_command = get("build.lint_command")
        c.build.analyze_command = get("build.analyze_command")
        c.build.publish_command = get("build.publish_command")
        c.build.test_command = get("build.test_command")
        c.build.artifact_glob = get("build.artifact_glob")
        preset = next((p for p in PRESETS if p.name == self._preset_var.get()), None)
        c.build.preset = preset.id if preset else ("custom-empty" if is_custom else "dotnet")

        self._secrets.jenkins_url = get("secrets.jenkins_url")
        self._secrets.jenkins_user = get("secrets.jenkins_user")
        self._secrets.jenkins_api_token = get("secrets.jenkins_api_token")
        self._secrets.git_username = get("secrets.git_username")
        self._secrets.git_password = get("secrets.git_password")
        self._secrets.teams_webhook_url = get("secrets.teams_webhook_url")

    @staticmethod
    def _normalize_rel(path: str) -> str:
        return path.strip().replace("\\", "/")

    def _on_field_changed(self) -> None:
        if self._loading:
            return
        self._update_preview()

    def _update_preview(self) -> None:
        try:
            self._form_to_config()
            logs, releases, tests = self._repo.build_preview_paths(self._config)
            self._preview_logs.set(logs)
            self._preview_releases.set(releases)
            self._preview_tests.set(tests)
            source_path = self._repo.build_source_preview(self._config)
            self._preview_source.set(
                source_path
                if self._config.storage.archive_source
                else f"（無効）{source_path}"
            )
            target_roots = self._repo.build_target_roots(self._config)
            if target_roots:
                lines = [
                    base if base == root else f"{base}  →  {root}"
                    for base, root in target_roots
                ]
                self._preview_targets.set("\n".join(lines))
            else:
                self._preview_targets.set("(未設定 — ④ か『書き込み先ベース』を入力)")
        except (ValueError, KeyError):
            pass
        self._update_path_statuses()

    def _update_path_statuses(self) -> None:
        """自動入力/手入力されたファイルパスがリポジトリ内に実在するか表示する。"""
        if not self._path_status:
            return
        root = self._repository_root
        for key, label in self._path_status.items():
            raw = self._fields[key].get().strip() if key in self._fields else ""
            text, color = self._path_status_text(key, raw, root)
            label.configure(text=text, fg=color)

    @staticmethod
    def _path_status_text(
        key: str, raw: str, root: Path | None
    ) -> tuple[str, str]:
        if not raw:
            if key == "project.test_project":
                return ("— 未設定（Test はスキップ）", "#888888")
            return ("— 未設定", "#888888")
        if root is None:
            return ("", "#888888")
        target = root / Path(raw.replace("\\", "/"))
        if target.is_file():
            return ("✓ 存在", "#2a8a2a")
        return ("⚠ 見つかりません", "#c0392b")

    # ------------------------------------------------------------ presets

    def _on_preset_selected(self) -> None:
        preset = next((p for p in PRESETS if p.name == self._preset_var.get()), None)
        if preset:
            self._preset_desc.configure(text=preset.description)

    def _apply_preset(self) -> None:
        preset = next((p for p in PRESETS if p.name == self._preset_var.get()), None)
        if not preset:
            messagebox.showwarning("CISetup", "先にプリセットを選んでください。")
            return
        has_custom = any(
            self._fields[k].get().strip()
            for k in (
                "build.build_command",
                "build.lint_command",
                "build.analyze_command",
                "build.publish_command",
                "build.test_command",
                "build.artifact_glob",
            )
        )
        if has_custom and not messagebox.askyesno(
            "プリセットの適用",
            "現在入力されているビルドコマンド等を、選んだプリセットの内容で上書きします。よろしいですか？",
        ):
            return
        self._profile_var.set(
            "カスタムコマンド（FPGA・C/C++・Python など任意）"
            if preset.profile == "custom"
            else ".NET（dotnet build / format / publish を自動実行）"
        )
        self._on_profile_changed()
        self._fields["build.build_command"].set(preset.build_command)
        self._fields["build.lint_command"].set(preset.lint_command)
        self._fields["build.analyze_command"].set(preset.analyze_command)
        self._fields["build.publish_command"].set(preset.publish_command)
        self._fields["build.test_command"].set(preset.test_command)
        self._fields["build.artifact_glob"].set(preset.artifact_glob)
        self._set_status(f"プリセット「{preset.name}」を適用しました。")

    # --------------------------------------------------------- file picks

    def _pick_folder(self) -> None:
        path = filedialog.askdirectory(title="プロジェクトフォルダを選択（.sln があるリポジトリルート）")
        if path:
            self._open_project(Path(path))

    def _open_saved(self) -> None:
        path = filedialog.askdirectory(title="保存した設定があるフォルダを選択")
        if not path:
            return
        root = paths.resolve_repository_root(Path(path))
        if root is None:
            messagebox.showwarning(
                "CISetup",
                "選んだフォルダに保存済みの設定が見つかりません。\n\n"
                "次のいずれかがあるフォルダを選んでください:\n"
                "• <プロジェクト>\\cisetup\\cisetup.config.json\n"
                "• <プロジェクト>\\cisetup.config.json",
            )
            return
        self._load_repository(root)

    def _load_from_text(self) -> None:
        text = self._path_var.get().strip()
        if not text or not Path(text).is_dir():
            messagebox.showwarning("CISetup", "有効なフォルダパスを入力してください。")
            return
        self._open_project(Path(text))

    def _reload(self) -> None:
        if self._repository_root:
            self._load_repository(self._repository_root)
        else:
            self._initial_load(None)

    def _browse_file(self, key: str) -> None:
        if not self._ensure_repo_silent():
            return
        path = filedialog.askopenfilename(
            title="ファイルを選択",
            initialdir=str(self._repository_root),
            filetypes=[("Project", "*.sln *.csproj"), ("All", "*.*")],
        )
        if path and self._repository_root:
            try:
                rel = Path(path).resolve().relative_to(self._repository_root.resolve())
                self._fields[key].set(rel.as_posix())
            except ValueError:
                self._fields[key].set(path)

    def _browse_folder(self, key: str) -> None:
        path = filedialog.askdirectory(title="フォルダを選択")
        if path:
            self._fields[key].set(path)

    # ------------------------------------------------------------ actions

    def _update_project_ui(self) -> None:
        has_root = self._repository_root is not None
        state = tk.NORMAL if has_root else tk.DISABLED
        self._redetect_btn.configure(state=state)
        self._redeploy_btn.configure(state=state)
        self._git_push_btn.configure(state=state)

    def _ensure_repo(self) -> Path:
        if self._repository_root is None:
            raise ValueError("先にプロジェクトフォルダを選んでください。")
        return self._repository_root

    def _ensure_repo_silent(self) -> bool:
        return self._repository_root is not None

    def _require_jenkins_secrets(self) -> None:
        if not (
            self._secrets.jenkins_url.strip()
            and self._secrets.jenkins_user.strip()
            and self._secrets.jenkins_api_token.strip()
        ):
            raise ValueError("Jenkins URL / ユーザー名 / API Token を入力してください。")

    def _confirm_test_project(self) -> bool:
        """テスト対象が未設定なのにリポジトリにテスト csproj がある場合、警告して続行確認する。

        戻り値 True で続行、False で中断（呼び出し側は処理を中止する）。
        """
        if self._config.build.profile.lower() == "custom":
            return True
        if self._config.project.test_project.strip():
            return True
        if self._repository_root is None:
            return True
        found = find_test_project(self._repository_root, self._config.project.name)
        if not found:
            return True
        return self._ask(
            "テスト対象が未設定です",
            "「テスト対象 (.csproj)」が未設定のため、CI ではユニットテストがスキップされます。\n\n"
            f"リポジトリにテストプロジェクトが見つかりました:\n  {found}\n\n"
            "このまま続行しますか？\n"
            "（「いいえ」で中断 →「自動入力をやり直す（再検出）」で設定できます）",
        )

    def _sync_saved_fields(self) -> None:
        """save_all 後、無害化された Git URL と移動済みユーザー名を画面へ反映する。"""
        if "git.repository_url" in self._fields:
            self._fields["git.repository_url"].set(self._config.git.repository_url)
        if "secrets.git_username" in self._fields:
            self._fields["secrets.git_username"].set(self._secrets.git_username)

    def _save_only(self) -> None:
        root = self._ensure_repo()
        self._form_to_config()
        if not self._confirm_test_project():
            self._set_status("保存を中断しました（テスト対象を設定してください）")
            return
        self._repo.save_all(root, self._config, self._secrets)
        self._sync_saved_fields()
        self._info(
            "保存完了",
            f"設定を保存しました。\n{root / 'cisetup'}\n\n"
            "※ 個人 ID を含む書き込み先（OneDrive 等）と Git ユーザー名は "
            "cisetup.local.json / secrets に保存し、Git には push されません。",
        )
        self._set_status("保存しました")

    def _test_jenkins(self) -> None:
        self._form_to_config()
        self._require_jenkins_secrets()
        JenkinsClient(self._secrets).test_connection()
        self._info("接続成功", "Jenkins への接続に成功しました。")
        self._set_status("Jenkins 接続テスト成功")

    def _apply_jenkins(self) -> None:
        root = self._ensure_repo()
        self._form_to_config()
        self._require_jenkins_secrets()
        if not self._confirm_test_project():
            self._set_status("反映を中断しました（テスト対象を設定してください）")
            return
        self._repo.save_all(root, self._config, self._secrets)
        self._sync_saved_fields()
        apply_settings(self._config, self._secrets)
        self._info("反映完了", f"Jenkins に設定を反映しました。\nジョブ: {self._config.jenkins.job_name}")
        self._set_status("Jenkins への反映が完了しました")

    def _test_teams(self) -> None:
        self._form_to_config()
        message = teams_service.send_test(self._secrets.teams_webhook_url, self._config)
        self._info("Teams テスト送信", message)
        self._set_status("Teams テスト通知を送信しました")

    def _test_file_server(self) -> None:
        self._form_to_config()
        targets = self._repo.effective_write_targets(self._config)
        if not targets:
            raise ValueError("書き込み先を入力してください（④ CI_FILE_SERVER、または詳細設定の書き込み先ベース）。")
        messages = []
        for unc in targets:
            messages.append(f"[{unc}]\n{test_file_server_write(unc)}")
        self._info("ファイルサーバー", "\n\n".join(messages))
        self._set_status(f"ファイルサーバー書き込み OK（{len(targets)} 件）")

    def _git_push(self) -> None:
        root = self._ensure_repo()
        self._form_to_config()
        if not self._confirm_test_project():
            self._set_status("push を中断しました（テスト対象を設定してください）")
            return
        if not self._ask(
            "Git push",
            "CI 関連ファイルだけ commit / push します。\n"
            "cisetup.secrets.local.json は含めません。\n\n続行しますか？",
        ):
            return
        commit_message = self._prompt_commit()
        if commit_message is None:
            return
        self._repo.save_all(root, self._config, self._secrets)
        self._sync_saved_fields()
        staged = git_service.push_ci_files(root, commit_message)
        self._info("Git push", f"Git push が完了しました。\n\n{staged}")
        self._set_status("Git push 完了")

    def _run_setup(self) -> None:
        root = self._ensure_repo()
        self._form_to_config()

        do_save = self._step_save_var.get()
        do_local = self._step_local_var.get()
        do_jenkins = self._step_jenkins_var.get()
        do_build = self._step_build_var.get()
        do_push = self._step_push_var.get()
        if not (do_save or do_local or do_jenkins or do_build or do_push):
            raise ValueError("実行する処理を 1 つ以上選んでください。")
        # 「Jenkins に反映」「Git push」は最新のローカル保存（config.json / Jenkinsfile / scripts 再生成）が
        # 前提。単独の各ボタンと同様に必ず保存してから実行する（保存をスキップすると古い定義のまま
        # push / 反映されてしまうため）。「ローカルでビルド＆テスト」は配置済みスクリプトをそのまま
        # 実行する純粋なローカル処理のため、保存は強制しない（git 操作も Jenkins も使わない）。
        if do_jenkins or do_push:
            do_save = True

        if (do_save or do_local or do_jenkins or do_build) and not self._confirm_test_project():
            self._set_status("セットアップを中断しました（テスト対象を設定してください）")
            return
        if do_jenkins or do_build:
            self._require_jenkins_secrets()
        if do_push and not self._config.git.repository_url.strip():
            raise ValueError("Git リポジトリ URL を入力してください。")

        steps: list[tuple[str, str]] = []
        if do_save:
            steps.append(("save", "設定を保存"))
        if do_local:
            steps.append(("local", "ローカルでビルド＆テスト"))
        if do_jenkins:
            steps.append(("jenkins", "Jenkins に反映"))
        if do_push:
            steps.append(("push", "Git push"))
        if do_build:
            steps.append(("build", "テストビルドを実行"))

        plan = "\n".join(f"  {i}. {label}" for i, (_, label) in enumerate(steps, 1))
        if not self._ask("セットアップを実行", f"次を順番に実行します。\n\n{plan}\n\n続行しますか？"):
            return

        commit_message = None
        if do_push:
            commit_message = self._prompt_commit()
            if commit_message is None:
                return

        total = len(steps)
        for index, (kind, label) in enumerate(steps, 1):
            self._set_status(f"{index}/{total} {label}...")
            if kind == "save":
                self._repo.save_all(root, self._config, self._secrets)
                self._sync_saved_fields()
            elif kind == "local":
                self._run_local_build_test(root)
            elif kind == "jenkins":
                apply_settings(self._config, self._secrets)
            elif kind == "build":
                self._build_now()
            elif kind == "push":
                git_service.push_ci_files(root, commit_message)

        self._set_status("セットアップが完了しました。")
        done = "\n".join(f"・{label}" for _, label in steps)
        suffix = "" if do_push else "\n\nGit push は実行していません。動作確認後に「Git push」を付けて再実行してください。"
        self._info("セットアップ", f"選択した処理が完了しました:\n\n{done}{suffix}")

    def _run_local_build_test(self, root: Path) -> None:
        """配置済み ci-build.ps1 → ci-test.ps1 をローカルで実行する（git 操作なし）。

        出力はバックグラウンドスレッドから ``after`` 経由で実行ログ欄へ流し込み、
        UI を固めないようにする（他のアクションと同じスレッド方式）。
        """
        configuration = self._loaded_default_configuration or "Release"
        self.after(0, lambda: self._set_text(self._run_log_text, ""))

        def emit(line: str) -> None:
            self.after(0, lambda value=line: self._append_text(self._run_log_text, value))

        run_local_ci(root, configuration=configuration, on_output=emit)

    def _build_now(self) -> None:
        self._form_to_config()
        self._require_jenkins_secrets()
        url = JenkinsClient(self._secrets).trigger_build(
            self._config.jenkins.job_name, bool(self._publish_var.get())
        )
        self._set_status("ビルドを開始しました。")
        if self._ask("ビルド開始", f"ビルドを開始しました。\n\n{url}\n\nブラウザで開きますか？"):
            self.after(0, lambda: webbrowser.open(url))

    def _setup_server(self) -> None:
        from ..jenkins_client import JenkinsClient as _Client

        self._form_to_config()
        self._require_jenkins_secrets()
        agent_name = self._fields["server.agent_name"].get().strip()
        agent_root = self._fields["server.agent_root"].get().strip()
        if not agent_name or not agent_root:
            raise ValueError("エージェント名と作業フォルダを入力してください。")

        self._set_status("Jenkins サーバー初期設定を実行中...")
        result = _Client(self._secrets).setup_server(self._config, agent_name, agent_root)
        self.after(0, lambda: self._set_text(self._server_log_text, "\n".join(result.log)))
        self.after(0, lambda: self._set_text(self._agent_command_text, result.agent_launch_command))
        msg = "Jenkins サーバーの初期設定が完了しました。"
        if result.requires_plugin_restart:
            msg += "\n\nプラグインインストール後、Jenkins の再起動が必要です。"
        self._info("サーバー初期設定", msg)
        self._set_status("Jenkins サーバー初期設定完了")

    def _copy_agent_command(self) -> None:
        text = self._agent_command_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("CISetup", "先に「Jenkins サーバーを初期設定」を実行してください。")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self._set_status("エージェント起動コマンドをコピーしました。")

    def _scan_env(self) -> None:
        self._set_status("環境をスキャンしています...")
        results = env_scan.scan()
        lines = []
        for r in results:
            lines.append(("[OK] " if r.found else "[未検出] ") + r.name + " : " + r.detail)
            if not r.found:
                lines.append("    → " + r.guidance)
                if r.download_url:
                    lines.append("      入手先: " + r.download_url)
        missing = sum(1 for r in results if not r.found)
        header = (
            "すべて見つかりました。\n\n"
            if missing == 0
            else f"未検出: {missing} 件（入手先からインストールしてください）\n\n"
        )
        self.after(0, lambda: self._set_text(self._env_text, header + "\n".join(lines)))
        self._set_status(
            "環境スキャン完了: 問題なし" if missing == 0 else f"環境スキャン完了: 未検出 {missing} 件"
        )

    # -------------------------------------------------------------- helpers

    def _prompt_commit(self) -> str | None:
        result: dict[str, str | None] = {}
        done = threading.Event()

        def ask() -> None:
            result["value"] = prompt_commit_message(self, git_service.DEFAULT_COMMIT_MESSAGE)
            done.set()

        self.after(0, ask)
        done.wait()
        return result.get("value")

    def _ask(self, title: str, message: str) -> bool:
        result: dict[str, bool] = {}
        done = threading.Event()

        def ask() -> None:
            result["value"] = messagebox.askyesno(title, message)
            done.set()

        self.after(0, ask)
        done.wait()
        return result.get("value", False)

    def _info(self, title: str, message: str) -> None:
        self.after(0, lambda: messagebox.showinfo(title, message))

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)

    def _append_text(self, widget: tk.Text, text: str) -> None:
        widget.insert(tk.END, text + "\n")
        widget.see(tk.END)

    def _set_status(self, text: str) -> None:
        self.after(0, lambda: self._status.configure(text=text))

    def _reveal_details(self) -> None:
        """詳細設定エクスパンダを開き、書き込み先ベース欄にフォーカスを当てる。"""
        exp = getattr(self, "_details_expander", None)
        if exp is not None:
            exp.open()
        field = self._multi_fields.get("storage.base_paths")
        if field is not None:
            field.focus()

    def _run_async(self, func) -> None:
        def worker() -> None:
            try:
                func()
            except (ValueError, JenkinsError, LocalCIError, git_service.GitError, OSError) as exc:
                msg = str(exc)
                # 「書き込み先ベース」に残った URL が原因のときは詳細設定を開いて気づけるようにする。
                if "書き込み先ベース" in msg:
                    self.after(0, self._reveal_details)
                self.after(0, lambda m=msg: messagebox.showerror("エラー", m))
                self.after(0, lambda m=msg: self._status.configure(text=f"エラー: {m}"))

        threading.Thread(target=worker, daemon=True).start()


def run_app(initial_repository_root: str | None = None) -> None:
    app = ConfigureApp(initial_repository_root)
    app.mainloop()
