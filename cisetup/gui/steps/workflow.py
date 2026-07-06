from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ... import help_texts
from ..layout import (
    COLOR_CARD_BG,
    COLOR_DESC,
    COLOR_RUN_BG,
    COLOR_RUN_BORDER,
    COLOR_RUN_TITLE,
    COLOR_TEXT,
    button,
    card,
    font,
    hint_label,
    mono_font,
    primary_button,
    section_title,
    step_desc,
    step_title,
)
from ..multi_value_field import MultiValueField
from ..tooltip import help_icon

# ③ 保存フォルダ ↔ ④ Teams URL の対応（表示名を統一）
_STORAGE_CATEGORY_LABELS: dict[str, str] = {
    "logs": "失敗時ログ",
    "releases": "成果物 zip",
    "analysis": "解析レポート",
    "tests": "テスト成果物",
    "source": "開発環境 zip",
}


def _category_label(category_key: str) -> str:
    title = _STORAGE_CATEGORY_LABELS[category_key]
    return f"{title}（{category_key}）"


class WorkflowStepsMixin:
    def _build_step_folder(self, parent: tk.Misc) -> None:
        frame = card(parent)
        step_title(frame, "① アプリのフォルダ").pack(anchor="w", pady=(0, 4))
        step_desc(
            frame,
            "ビルドしたいアプリのフォルダ（.sln がある場所）を選びます。選ぶと必要な CI ファイルが自動で置かれ、プロジェクト名なども自動入力されます。",
        ).pack(anchor="w", pady=(0, 10))
        folder_hdr = tk.Frame(frame, bg=COLOR_CARD_BG)
        folder_hdr.pack(anchor="w", pady=(0, 4))
        tk.Label(folder_hdr, text="対象フォルダ", font=font(12), bg=COLOR_CARD_BG).pack(side=tk.LEFT)
        help_icon(folder_hdr, help_texts.PROJECT_FOLDER, bg=COLOR_CARD_BG).pack(side=tk.LEFT, padx=(4, 0))
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
        self._add_field(frame, "secrets.git_username", "ユーザー名", help_texts.GIT_USERNAME, label_width=16)
        self._add_field(frame, "secrets.git_password", "パスワード / トークン", help_texts.GIT_PASSWORD, label_width=16)
        hint_label(frame, "社内 Git のパスワード、または個人アクセストークン (PAT)。Git には保存されません。").pack(
            anchor="w", padx=(150, 0)
        )
    def _build_step_storage(self, parent: tk.Misc) -> None:
        frame = card(parent)
        step_title(frame, "③ 成果物・ログの保存先").pack(anchor="w", pady=(0, 4))
        step_desc(
            frame,
            "ビルド成果物やログの書き込み先を指定します。ベースディレクトリを指定し、必要なカテゴリフォルダを作成してから Teams のリンク先を設定します。",
        ).pack(anchor="w", pady=(0, 10))
        self._add_multi_field(
            frame,
            "storage.base_paths",
            "書き込み先ベース（複数可）",
            help_texts.STORAGE_BASE_PATH,
            browse="folder",
        )
        hint_label(
            frame,
            "例: C:\\Users\\you\\OneDrive - 会社\\CI\\MyApp や \\\\fileserver\\share\\builds\\MyApp。"
            "右端の「＋」で複数指定でき、設定した全先へコピーします。"
            "個人 ID を含むパスは Git に push されません。",
        ).pack(anchor="w")
        self._add_multi_field(
            frame,
            "jenkins.ci_file_servers",
            "共有フォルダルート（CI_FILE_SERVER・複数可）",
            help_texts.CI_FILE_SERVERS,
            browse="folder",
        )
        hint_label(
            frame,
            "例: \\\\fileserver\\ci（この下に自動でプロジェクト名フォルダを作成）。"
            "書き込み先ベースと併用でき、両方に入れた全先へコピーします（相互排他ではありません）。",
        ).pack(anchor="w", pady=(0, 8))
        hint_label(
            frame,
            "各行の左のチェックを外すと、そのカテゴリは「格納先フォルダを作成」でも"
            "CI の配置(deploy)でも対象外になります（プロジェクトで不要なカテゴリを無効化）。"
            "ソース行のチェックは「開発環境一式を zip 化して保存する」と同じ設定です。",
        ).pack(anchor="w", pady=(0, 4))
        self._enable_logs_var = tk.BooleanVar(value=True)
        self._enable_releases_var = tk.BooleanVar(value=True)
        self._enable_analysis_var = tk.BooleanVar(value=True)
        self._enable_tests_var = tk.BooleanVar(value=True)
        self._archive_source_var = tk.BooleanVar(value=False)
        self._add_field(
            frame, "storage.logs_dir", _category_label("logs"), help_texts.LOGS_DIR,
            check_var=self._enable_logs_var,
            check_help=help_texts.ENABLE_CATEGORY,
        )
        self._add_field(
            frame, "storage.releases_dir", _category_label("releases"), help_texts.RELEASES_DIR,
            check_var=self._enable_releases_var,
            check_help=help_texts.ENABLE_CATEGORY,
        )
        self._add_field(
            frame, "storage.analysis_dir", _category_label("analysis"), help_texts.ANALYSIS_DIR,
            check_var=self._enable_analysis_var,
            check_help=help_texts.ENABLE_CATEGORY,
        )
        self._add_field(
            frame, "storage.tests_dir", _category_label("tests"), help_texts.TESTS_DIR,
            check_var=self._enable_tests_var,
            check_help=help_texts.ENABLE_CATEGORY,
        )
        self._add_field(
            frame, "storage.source_dir", _category_label("source"), help_texts.SOURCE_DIR,
            check_var=self._archive_source_var,
            check_help=help_texts.ENABLE_CATEGORY,
        )
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
        help_icon(row, help_texts.USE_DATE_SUBFOLDER, bg=COLOR_CARD_BG).pack(side=tk.LEFT, padx=(4, 0))
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
            ("失敗時ログ（logs）", self._preview_logs),
            ("成果物 zip（releases）", self._preview_releases),
            ("テスト成果物（tests）", self._preview_tests),
            ("開発環境 zip（source）・有効時", self._preview_source),
        ):
            tk.Label(preview, text=title, font=font(12, bold=True), bg=COLOR_CARD_BG, anchor="w").pack(anchor="w")
            ttk.Entry(preview, textvariable=var, state="readonly", font=font(12)).pack(fill=tk.X, pady=(4, 8))
        tk.Label(
            preview,
            text="全書き込み先（この全てにコピー / 共有フォルダルートはプロジェクト名を付与）",
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
        create_row = tk.Frame(frame, bg=COLOR_CARD_BG)
        create_row.pack(anchor="w", pady=(10, 0))
        button(
            create_row,
            "格納先フォルダを作成",
            lambda: self._run_async(self._create_storage_folders),
            padx=16,
        ).pack(side=tk.LEFT)
        help_icon(create_row, help_texts.CREATE_STORAGE_FOLDERS, bg=COLOR_CARD_BG).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        hint_label(
            frame,
            "書き込み先の実効ルート配下に、有効化したカテゴリフォルダ（releases/logs/analysis/tests"
            "[/source]）を作成します。上のチェックを外したカテゴリは作成対象から除外されます。"
            "OneDrive 同期フォルダなら同期後に SharePoint 側で各フォルダの共有 URL を取得し、"
            "④ Teams の各 URL 欄に貼り付けられます。",
        ).pack(anchor="w")

        tk.Label(
            frame,
            text="Jenkins エージェントのワークスペースパス（同一 PC のとき）",
            font=font(12, bold=True),
            fg=COLOR_TEXT,
            bg=COLOR_CARD_BG,
            anchor="w",
        ).pack(anchor="w", pady=(12, 2))
        self._add_field(
            frame,
            "jenkins.agent_workspace_path",
            "ワークスペースパス",
            help_texts.AGENT_WORKSPACE_PATH,
            browse="folder",
            label_width=16,
        )
        hint_label(
            frame,
            "例: C:\\jenkins-agent\\workspace\\IPU_TEST_APP。"
            "この PC で Jenkins エージェントを動かしている場合に設定すると、保存時に書き込み先設定"
            "(cisetup.local.json) をワイプで消えない兄弟パスへ自動配置します。"
            "空なら何もしません（Git には push されません）。",
        ).pack(anchor="w", padx=(150, 0))
        button(
            frame,
            "エージェントへ書き込み先設定を配置",
            lambda: self._run_async(self._deploy_local_to_agent),
            padx=16,
        ).pack(anchor="w", pady=(8, 0), padx=(150, 0))
        deploy_row = tk.Frame(frame, bg=COLOR_CARD_BG)
        deploy_row.pack(anchor="w", padx=(150, 0))
        help_icon(deploy_row, help_texts.DEPLOY_LOCAL_TO_AGENT, bg=COLOR_CARD_BG).pack(side=tk.LEFT)

        self._push_env_var = tk.BooleanVar(value=False)
        push_cb = tk.Checkbutton(
            frame,
            text="書き込み先を Jenkins のグローバル環境変数 (CI_FILE_SERVER) として登録する（別 PC/共有不可の環境向け）",
            variable=self._push_env_var,
            command=self._on_field_changed,
            font=font(12),
            bg=COLOR_CARD_BG,
            activebackground=COLOR_CARD_BG,
            anchor="w",
        )
        push_cb.pack(anchor="w", pady=(12, 0))
        push_help_row = tk.Frame(frame, bg=COLOR_CARD_BG)
        push_help_row.pack(anchor="w")
        help_icon(push_help_row, help_texts.PUSH_CI_FILE_SERVER_ENV, bg=COLOR_CARD_BG).pack(side=tk.LEFT)
        hint_label(
            frame,
            "ON にすると「Jenkinsに反映」時に、先頭の共有フォルダルートを Jenkins 本体のグローバル環境変数"
            " CI_FILE_SERVER として自動登録します（Jenkins 管理者権限が必要）。"
            "別 PC・共有アクセス不可のエージェントでも書き込み先が届きます。"
            "値は単一のため、複数先が必要な場合は上の兄弟パス配置を使ってください。",
        ).pack(anchor="w")
    def _build_step_teams(self, parent: tk.Misc) -> None:
        frame = card(parent)
        step_title(frame, "④ Teams 通知").pack(anchor="w", pady=(0, 4))
        step_desc(
            frame,
            "ビルドの成功・失敗を Teams に通知します。Teams チャンネルのワークフローで作った Webhook URL を貼り付け、「テスト送信」で届くか確認できます。",
        ).pack(anchor="w", pady=(0, 10))
        wh_row = tk.Frame(frame, bg=COLOR_CARD_BG)
        wh_row.pack(anchor="w", fill=tk.X)
        tk.Label(wh_row, text="Webhook URL", font=font(12), bg=COLOR_CARD_BG, anchor="w").pack(side=tk.LEFT)
        help_icon(wh_row, help_texts.TEAMS_WEBHOOK_URL, bg=COLOR_CARD_BG).pack(side=tk.LEFT, padx=(4, 0))
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
            "③ の各行と同じカテゴリ名（logs / releases / analysis / tests / source）の URL を貼り付けます。"
            "Teams のボタンから開く共有 URL（OneDrive / SharePoint 等）。"
            "ファイルの書き込み先は ③ 保存先で設定し、ここは閲覧用リンクです。"
            "各欄は右端の「＋」で複数 URL を追加でき、通知では全リンクをボタン表示します。"
            "カテゴリが無効、または格納フォルダが未作成の欄はグレーアウトされます"
            "（③ の「格納先フォルダを作成」でフォルダを作ると有効化）。"
            "テスト失敗時のみカードに失敗テスト名とログボタンが表示されます。",
        ).pack(anchor="w")
        self._teams_url_labels: dict[str, tk.Label] = {}
        self._teams_url_categories = {
            "storage.logs_urls": ("enable_logs", "logs"),
            "storage.release_urls": ("enable_releases", "releases"),
            "storage.analysis_urls": ("enable_analysis", "analysis"),
            "storage.tests_urls": ("enable_tests", "tests"),
            "storage.source_urls": ("archive_source", "source"),
        }
        for key, category_key, help_text in (
            ("storage.logs_urls", "logs", help_texts.LOGS_URL),
            ("storage.release_urls", "releases", help_texts.RELEASE_URL),
            ("storage.analysis_urls", "analysis", help_texts.ANALYSIS_URL),
            ("storage.tests_urls", "tests", help_texts.TESTS_URL),
            ("storage.source_urls", "source", help_texts.SOURCE_URL),
        ):
            label = _category_label(category_key)
            lbl_row = tk.Frame(frame, bg=COLOR_CARD_BG)
            lbl_row.pack(anchor="w", fill=tk.X, pady=(6, 0))
            lbl = tk.Label(lbl_row, text=label, anchor="w", bg=COLOR_CARD_BG, font=font(12))
            lbl.pack(side=tk.LEFT)
            if help_text:
                help_icon(lbl_row, help_text, bg=COLOR_CARD_BG).pack(side=tk.LEFT, padx=(4, 0))
            self._teams_url_labels[key] = lbl
            field = MultiValueField(frame, on_change=self._on_field_changed)
            self._multi_fields[key] = field
        button(
            frame,
            "テスト送信",
            lambda: self._run_async(self._test_teams),
            padx=16,
        ).pack(anchor="w", pady=(10, 0))
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
        self._step_local_var = tk.BooleanVar(value=True)
        self._step_jenkins_var = tk.BooleanVar(value=True)
        self._step_push_var = tk.BooleanVar(value=True)
        self._step_build_var = tk.BooleanVar(value=True)
        options = tk.Frame(frame, bg=COLOR_RUN_BG)
        options.pack(anchor="w", pady=(0, 12))
        for text, var, help_text in (
            ("1. 設定を保存", self._step_save_var, help_texts.STEP_SAVE),
            ("ローカルでビルド＆テスト（push せず現在のコードを検証）", self._step_local_var, help_texts.LOCAL_BUILD_TEST),
            ("2. Jenkins に反映", self._step_jenkins_var, help_texts.STEP_JENKINS),
            ("3. Git push", self._step_push_var, help_texts.STEP_PUSH),
            ("4. テストビルドを実行", self._step_build_var, help_texts.STEP_BUILD),
        ):
            opt_row = tk.Frame(options, bg=COLOR_RUN_BG)
            opt_row.pack(anchor="w")
            cb = tk.Checkbutton(
                opt_row,
                text=text,
                variable=var,
                font=font(12),
                bg=COLOR_RUN_BG,
                activebackground=COLOR_RUN_BG,
                anchor="w",
            )
            cb.pack(side=tk.LEFT)
            if help_text:
                help_icon(opt_row, help_text, bg=COLOR_RUN_BG).pack(side=tk.LEFT, padx=(4, 0))

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
        self._publish_var = tk.BooleanVar(value=True)
        pub_row = tk.Frame(frame, bg=COLOR_RUN_BG)
        pub_row.pack(anchor="w", pady=(12, 0))
        tk.Checkbutton(
            pub_row,
            text="テストビルドで成果物 zip も作成・保存する",
            variable=self._publish_var,
            font=font(12),
            bg=COLOR_RUN_BG,
            activebackground=COLOR_RUN_BG,
            anchor="w",
        ).pack(side=tk.LEFT)
        help_icon(pub_row, help_texts.PUBLISH_RELEASE, bg=COLOR_RUN_BG).pack(side=tk.LEFT, padx=(4, 0))
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
