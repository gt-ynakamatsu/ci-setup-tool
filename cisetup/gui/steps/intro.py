from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...ci_preset_catalog import PRESETS
from ..constants import ENV_LINKS
from ..layout import (
    COLOR_BEGINNER_BG,
    COLOR_BEGINNER_BORDER,
    COLOR_BEGINNER_TITLE,
    COLOR_DESC,
    COLOR_ENV_BG,
    COLOR_PRESET_BG,
    COLOR_STEP,
    Expander,
    button,
    card,
    font,
    log_text,
    section_title,
)


class IntroStepsMixin:
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
        body = tk.Label(
            frame,
            font=font(12),
            fg="#555555",
            bg=COLOR_BEGINNER_BG,
            justify=tk.LEFT,
            anchor="w",
        )
        body.pack(anchor="w")
        self._mode_text(
            body,
            dotnet=(
                "① アプリのフォルダ → ② 社内 Git → ③ 保存先 → ④ Teams → ⑤ Jenkins 接続 を入力し、\n"
                "最後に「セットアップを実行」を押すと、保存・手元のビルド確認・Jenkins 登録・テストビルドまで自動で行います。\n"
                "むずかしい項目は「詳細設定（ふだんは開かなくて OK）」にまとめてあり、ほとんど自動で入力されます。"
            ),
            fpga=(
                "まず上のプリセットで FPGA（Vivado / Quartus）を選び、\n"
                "① プロジェクトのフォルダ → ② 社内 Git → ③ 保存先 → ④ Teams → ⑤ Jenkins 接続 を入力し、\n"
                "最後に「セットアップを実行」を押します。合成コマンドは書かなくても、"
                "エージェント上のツールと合成対象を自動で探します。"
            ),
        )
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
        self._env_text = log_text(frame, height=8, pady=(0, 10))
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
        for label, url, modes in ENV_LINKS:
            link_button = button(
                links,
                label,
                lambda u=url: self._open_link(u),
            )
            link_button.pack(side=tk.LEFT, padx=(0, 8), pady=(0, 8))
            if modes:
                self._mode_only(link_button, *modes)

        prep = Expander(frame, "アプリで自動化できない準備（手順とリンク）")
        prep.configure(bg=COLOR_ENV_BG)
        prep._toggle.configure(bg=COLOR_ENV_BG)
        prep.content.configure(bg=COLOR_ENV_BG)
        prep.pack(fill=tk.X, pady=(6, 0))
        self._build_manual_prep(prep.content, COLOR_ENV_BG)
    def _build_manual_prep(self, parent: tk.Frame, bg: str) -> None:
        agent_prep_dotnet = (
            "エージェント PC に Java と .NET SDK 8 と Git を入れ、"
            "「詳細設定 → Jenkins サーバー初回設定」で表示される起動コマンドを実行します。"
            "Jenkins の Nodes で Online になれば準備完了です。"
        )
        agent_prep_fpga = (
            "エージェント PC に Java と Git、そして Vivado / Quartus を入れ（PATH か "
            "XILINX_VIVADO / QUARTUS_ROOTDIR から見えるように）、"
            "「詳細設定 → Jenkins サーバー初回設定」で表示される起動コマンドを実行します。"
            "合成は時間がかかるため、エージェント PC のディスク空きも確認してください。"
        )
        blocks = [
            (
                "① Jenkins 本体のインストール（初回・サーバー機）",
                "Windows MSI 版 LTS をサーバー機にインストールします。インストール後、画面の「詳細設定 → Jenkins サーバー初回設定」でプラグインとエージェントを自動登録できます。",
                ("Jenkins ダウンロードを開く", "https://www.jenkins.io/download/"),
            ),
            (
                "② 共有フォルダ（ファイルサーバー）の作成",
                "成果物 zip とログを置く共有フォルダ（例: \\\\fileserver\\ci）を作成し、エージェントの実行アカウントに書き込み権限を付与します。"
                "③ 保存先で設定後、「格納先フォルダを作成」または「詳細設定 → ファイルサーバー書き込みテスト」で確認できます。",
                None,
            ),
            (
                "④ Teams Webhook の作成",
                "Teams チャンネル → ワークフロー →「Webhook アラートをチャネルに送信する」で URL を取得し、④ Teams 通知 に貼り付けます。「テスト送信」で確認できます。",
                (
                    "Teams ワークフローの説明を開く",
                    "https://support.microsoft.com/ja-jp/office/teams-%E3%81%AE%E3%83%AF%E3%83%BC%E3%82%AF%E3%83%95%E3%83%AD%E3%83%BC",
                ),
            ),
            (
                "④ エージェント PC の起動",
                (agent_prep_dotnet, agent_prep_fpga),
                None,
            ),
        ]
        for title, body_text, link in blocks:
            tk.Label(parent, text=title, font=font(12, bold=True), fg="#444444", bg=bg, anchor="w").pack(
                anchor="w", pady=(0, 2)
            )
            body = tk.Label(
                parent,
                text=body_text if isinstance(body_text, str) else "",
                font=font(12),
                fg=COLOR_DESC,
                bg=bg,
                anchor="w",
                wraplength=self._px(840),
                justify=tk.LEFT,
            )
            body.pack(anchor="w", pady=(0, 4))
            if not isinstance(body_text, str):
                self._mode_text(body, dotnet=body_text[0], fpga=body_text[1])
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
        section_title(frame, "CI の種類（プリセット）", COLOR_STEP).pack(anchor="w", pady=(0, 6))
        tk.Label(
            frame,
            text="選び直すと、その場で画面と設定項目が切り替わります（ビルド種別・コマンド・設定欄）。ビルドコマンドを手入力していた場合は上書き確認が出ます。",
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
            "もう一度適用",
            self._apply_preset,
            padx=18,
            pady=7,
        ).pack(side=tk.LEFT, padx=(10, 0))
        button(
            row,
            "種類の選択に戻る",
            self._show_chooser,
            padx=18,
            pady=7,
        ).pack(side=tk.LEFT, padx=(8, 0))
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
        # いま何モードなのかを一目で分かるようにする（設定欄の出入りと連動）。
        mode_label = tk.Label(
            frame,
            font=font(12, bold=True),
            fg=COLOR_STEP,
            bg=COLOR_PRESET_BG,
            anchor="w",
            wraplength=self._px(860),
            justify=tk.LEFT,
        )
        mode_label.pack(fill=tk.X, pady=(8, 0))
        self._mode_text(
            mode_label,
            dotnet="現在の画面: .NET — .sln / csproj を指定し、dotnet build / test / publish を実行します。",
            fpga="現在の画面: FPGA — 合成対象（.xpr / .qpf / build.tcl）を指定し、"
            "エージェント上の Vivado / Quartus で合成します（.NET 専用の項目は隠しています）。",
            custom="現在の画面: カスタム — 各ステージのコマンドを詳細設定で指定します"
            "（.NET 専用の項目は隠しています）。",
        )
