from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ... import help_texts
from ..layout import (
    COLOR_CARD_BG,
    COLOR_DESC,
    COLOR_SERVER_BG,
    COLOR_SERVER_BORDER,
    COLOR_SERVER_TITLE,
    COLOR_TEXT,
    COLOR_WINDOW_BG,
    Expander,
    button,
    card,
    font,
    hint_label,
    mono_font,
    section_title,
    step_desc,
    step_title,
)
from ..tooltip import help_icon


class DetailsMixin:
    def _build_details_expander(self, parent: ttk.Frame) -> None:
        exp = Expander(parent, "詳細設定（ふだんは開かなくて OK・自動入力されています）")
        exp.pack(fill=tk.X, pady=(0, 14))
        self._details_expander = exp
        details = exp.content
        self._build_details_build(details)
        self._build_details_project(details)
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
        profile_row = tk.Frame(frame, bg=COLOR_CARD_BG)
        profile_row.pack(anchor="w")
        help_icon(profile_row, help_texts.BUILD_PROFILE, bg=COLOR_CARD_BG).pack(side=tk.LEFT, padx=(0, 4))
        profile_combo = ttk.Combobox(
            profile_row,
            textvariable=self._profile_var,
            values=[
                ".NET（dotnet build / format / publish を自動実行）",
                "カスタムコマンド（FPGA・C/C++・Python など任意）",
            ],
            state="readonly",
            width=58,
            font=font(12),
        )
        profile_combo.pack(anchor="w", side=tk.LEFT)
        profile_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_profile_changed())
        self._custom_build_panel = tk.Frame(frame, bg=COLOR_CARD_BG)
        hint_label(
            self._custom_build_panel,
            "各コマンドはエージェントの作業ディレクトリ（リポジトリ直下）で PowerShell として実行されます。空欄のステップはスキップされます（ビルドは必須）。",
        ).pack(anchor="w", pady=(12, 0))
        for key, title, tip, field_help in (
            ("build.build_command", "ビルド コマンド（必須）", "例: vivado -mode batch -source build.tcl", help_texts.BUILD_COMMAND),
            ("build.lint_command", "Lint / チェック コマンド（任意）", "例: verilator --lint-only -Wall src/top.v", help_texts.LINT_COMMAND),
            ("build.test_command", "テスト コマンド（任意）", "例: pytest -q または dotnet test tests/MyApp.Tests", help_texts.TEST_COMMAND),
            ("build.analyze_command", "解析 コマンド（任意）", "例: タイミング/使用率レポートの生成・集計スクリプト", help_texts.ANALYZE_COMMAND),
            ("build.publish_command", "成果物生成 コマンド（任意）", "例: ビットストリーム生成など（成果物は下の glob で収集します）", help_texts.PUBLISH_COMMAND),
        ):
            title_row = tk.Frame(self._custom_build_panel, bg=COLOR_CARD_BG)
            title_row.pack(anchor="w", fill=tk.X, pady=(8, 2))
            tk.Label(
                title_row,
                text=title,
                font=font(12, bold=True),
                bg=COLOR_CARD_BG,
                anchor="w",
            ).pack(side=tk.LEFT)
            help_icon(title_row, field_help, bg=COLOR_CARD_BG).pack(side=tk.LEFT, padx=(4, 0))
            self._add_field(self._custom_build_panel, key, "", show_label=False)
            if tip:
                hint_label(self._custom_build_panel, tip).pack(anchor="w")
        glob_row = tk.Frame(self._custom_build_panel, bg=COLOR_CARD_BG)
        glob_row.pack(anchor="w", fill=tk.X, pady=(8, 2))
        tk.Label(
            glob_row,
            text="成果物ファイル（glob・; 区切り）",
            font=font(12, bold=True),
            bg=COLOR_CARD_BG,
            anchor="w",
        ).pack(side=tk.LEFT)
        help_icon(glob_row, help_texts.ARTIFACT_GLOB, bg=COLOR_CARD_BG).pack(side=tk.LEFT, padx=(4, 0))
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
            "（①でフォルダを開いたあと、見つからないパスだけ右側に表示します）",
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
        help_icon(row, help_texts.BUILD_TIMEOUT, bg=COLOR_CARD_BG).pack(side=tk.LEFT, padx=(12, 0))
        help_icon(row, help_texts.LOG_RETENTION, bg=COLOR_CARD_BG).pack(side=tk.LEFT, padx=(4, 0))

        retry_row = tk.Frame(frame, bg=COLOR_CARD_BG)
        retry_row.pack(fill=tk.X, pady=4)
        retry_label = tk.Label(
            retry_row, text="Checkout 失敗時の自動リトライ回数", width=22, anchor="w", bg=COLOR_CARD_BG, font=font(12)
        )
        retry_label.pack(side=tk.LEFT)
        self._register_field("jenkins.checkout_retry_count")
        retry_entry = ttk.Entry(
            retry_row, textvariable=self._fields["jenkins.checkout_retry_count"], width=8, font=font(12)
        )
        retry_entry.pack(side=tk.LEFT)
        tk.Label(retry_row, text="回", bg=COLOR_CARD_BG, font=font(12)).pack(side=tk.LEFT, padx=(6, 0))
        help_icon(retry_row, help_texts.CHECKOUT_RETRY_COUNT, bg=COLOR_CARD_BG).pack(side=tk.LEFT, padx=(8, 0))

        self._retry_wrapper_var = tk.BooleanVar(value=False)
        wrapper_row = tk.Frame(frame, bg=COLOR_CARD_BG)
        wrapper_row.pack(anchor="w", pady=(10, 0), fill=tk.X)
        wrapper_cb = tk.Checkbutton(
            wrapper_row,
            text="cron 失敗時に自動リトライする（別建てジョブ + Naginator）",
            variable=self._retry_wrapper_var,
            command=self._on_retry_wrapper_changed,
            font=font(12),
            bg=COLOR_CARD_BG,
            activebackground=COLOR_CARD_BG,
            anchor="w",
        )
        wrapper_cb.pack(side=tk.LEFT)
        help_icon(wrapper_row, help_texts.RETRY_WRAPPER_ENABLED, bg=COLOR_CARD_BG).pack(side=tk.LEFT, padx=(4, 0))

        self._retry_options_row = tk.Frame(frame, bg=COLOR_CARD_BG)
        self._retry_options_row.pack(fill=tk.X, pady=(4, 0))
        tk.Label(
            self._retry_options_row, text="最大リトライ回数 / 間隔",
            width=22, anchor="w", bg=COLOR_CARD_BG, font=font(12),
        ).pack(side=tk.LEFT)
        self._register_field("jenkins.retry_max_count")
        self._register_field("jenkins.retry_delay_seconds")
        max_entry = ttk.Entry(
            self._retry_options_row, textvariable=self._fields["jenkins.retry_max_count"], width=8, font=font(12)
        )
        max_entry.pack(side=tk.LEFT)
        tk.Label(self._retry_options_row, text="回", bg=COLOR_CARD_BG, font=font(12)).pack(side=tk.LEFT, padx=(6, 16))
        delay_entry = ttk.Entry(
            self._retry_options_row, textvariable=self._fields["jenkins.retry_delay_seconds"], width=8, font=font(12)
        )
        delay_entry.pack(side=tk.LEFT)
        tk.Label(self._retry_options_row, text="秒後に再実行", bg=COLOR_CARD_BG, font=font(12)).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        help_icon(self._retry_options_row, help_texts.RETRY_MAX_COUNT, bg=COLOR_CARD_BG).pack(side=tk.LEFT, padx=(12, 0))
        help_icon(self._retry_options_row, help_texts.RETRY_DELAY_SECONDS, bg=COLOR_CARD_BG).pack(side=tk.LEFT, padx=(4, 0))
        self._on_retry_wrapper_changed()
    def _on_retry_wrapper_changed(self) -> None:
        if self._retry_wrapper_var.get():
            self._retry_options_row.pack(fill=tk.X, pady=(4, 0))
        else:
            self._retry_options_row.pack_forget()
        self._on_field_changed()
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
