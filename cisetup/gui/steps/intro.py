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
    mono_font,
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
        tk.Label(
            frame,
            text=(
                "① アプリのフォルダ → ② 社内 Git → ③ 保存先 → ④ Teams → ⑤ Jenkins 接続 を入力し、\n"
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
