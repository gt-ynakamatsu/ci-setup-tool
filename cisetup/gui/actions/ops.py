from __future__ import annotations

import tkinter as tk
import webbrowser
from pathlib import Path

from ... import paths
from ...project_setup import find_test_project
from .. import deps


class ActionsMixin:
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
            f"設定を保存しました。\n{paths.ci_dir(root)}\n\n"
            "※ 個人 ID を含む書き込み先（OneDrive 等）と Git ユーザー名は "
            "cisetup.local.json / secrets に保存し、Git には push されません。",
        )
        self._set_status("保存しました")
    def _deploy_local_to_agent(self) -> None:
        self._form_to_config()
        if not self._repo.effective_write_targets(self._config):
            raise ValueError(
                "配置する書き込み先が未入力です。"
                "③ 保存先の『書き込み先ベース』または『共有フォルダルート』を入力してください。"
            )
        if not self._config.jenkins.agent_workspace_path.strip():
            raise ValueError(
                "「Jenkins エージェントのワークスペースパス」を入力してください"
                "（同一 PC でエージェントを動かしている場合の配置先。例: "
                "C:\\jenkins-agent\\workspace\\IPU_TEST_APP）。"
            )
        sibling = self._repo.deploy_local_to_agent(self._config)
        self._info(
            "配置完了",
            "書き込み先設定（cisetup.local.json）をエージェントの兄弟パスへ配置しました。\n"
            f"{sibling}\n\n"
            "※ ワークスペースの「ワイプ＋再クローン」でも消えない位置です。"
            "ワークスペース内に CISetup フォルダ（旧 cisetup も可）があれば、そちらにも配置しました。",
        )
        self._set_status("エージェントへ書き込み先設定を配置しました")
    def _test_jenkins(self) -> None:
        self._form_to_config()
        self._require_jenkins_secrets()
        deps.JenkinsClient(self._secrets).test_connection()
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
        deps.apply_settings(self._config, self._secrets)
        message = f"Jenkins に設定を反映しました。\nジョブ: {self._config.jenkins.job_name}"
        if (
            self._config.jenkins.push_ci_file_server_env
            and self._config.jenkins.ci_file_server.strip()
        ):
            message += (
                "\n\nグローバル環境変数を登録しました:\n"
                f"CI_FILE_SERVER = {self._config.jenkins.ci_file_server}"
            )
        self._info("反映完了", message)
        self._set_status("Jenkins への反映が完了しました")
    def _test_teams(self) -> None:
        self._form_to_config()
        message = deps.teams_service.send_test(self._secrets.teams_webhook_url, self._config)
        self._info("Teams テスト送信", message)
        self._set_status("Teams テスト通知を送信しました")
    def _test_file_server(self) -> None:
        self._form_to_config()
        targets = self._repo.effective_write_targets(self._config)
        if not targets:
            raise ValueError("書き込み先を入力してください（③ 保存先の書き込み先ベースまたは共有フォルダルート）。")
        messages = []
        for unc in targets:
            messages.append(f"[{unc}]\n{deps.test_file_server_write(unc)}")
        self._info("ファイルサーバー", "\n\n".join(messages))
        self._set_status(f"ファイルサーバー書き込み OK（{len(targets)} 件）")
    def _create_storage_folders(self) -> None:
        self._form_to_config()
        if not self._repo.effective_write_targets(self._config):
            raise ValueError(
                "格納先フォルダを作成するには、先に③ 保存先の書き込み先ベースまたは"
                "共有フォルダルートを入力してください。"
            )
        result = self._repo.create_storage_folders(self._config)
        lines: list[str] = []
        if result.created:
            lines.append("作成/確保したフォルダ:")
            lines.extend(f"  {p}" for p in result.created)
        if result.skipped_urls:
            if lines:
                lines.append("")
            lines.append("URL の書き込み先はスキップしました（フォルダは作成できません）:")
            lines.extend(f"  {u}" for u in result.skipped_urls)
        if result.failed:
            detail = "\n".join(f"  {p}\n    {err}" for p, err in result.failed)
            message = "一部のフォルダ作成に失敗しました:\n" + detail
            if lines:
                message += "\n\n" + "\n".join(lines)
            raise ValueError(message)
        if not result.created:
            self._info(
                "格納先フォルダ",
                "作成対象のフォルダがありませんでした"
                "（書き込み先が URL のみか、カテゴリ名が空です）。\n"
                + ("\n".join(lines) if lines else ""),
            )
            self._set_status("格納先フォルダ: 作成対象なし")
            return
        self._info("格納先フォルダを作成", "\n".join(lines))
        self._set_status(f"格納先フォルダを作成しました（{len(result.created)} 件）")
        self._update_teams_url_states()
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
        staged = deps.git_service.push_ci_files(root, commit_message)
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
                deps.apply_settings(self._config, self._secrets)
            elif kind == "build":
                self._build_now()
            elif kind == "push":
                deps.git_service.push_ci_files(root, commit_message)

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

        deps.run_local_ci(root, configuration=configuration, on_output=emit)
    def _build_now(self) -> None:
        self._form_to_config()
        self._require_jenkins_secrets()
        url = deps.JenkinsClient(self._secrets).trigger_build(
            self._config.jenkins.job_name, bool(self._publish_var.get())
        )
        self._set_status("ビルドを開始しました。")
        if self._ask("ビルド開始", f"ビルドを開始しました。\n\n{url}\n\nブラウザで開きますか？"):
            self.after(0, lambda: webbrowser.open(url))
    def _setup_server(self) -> None:
        self._form_to_config()
        self._require_jenkins_secrets()
        agent_name = self._fields["server.agent_name"].get().strip()
        agent_root = self._fields["server.agent_root"].get().strip()
        if not agent_name or not agent_root:
            raise ValueError("エージェント名と作業フォルダを入力してください。")

        self._set_status("Jenkins サーバー初期設定を実行中...")
        result = deps.JenkinsClient(self._secrets).setup_server(self._config, agent_name, agent_root)
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
            deps.messagebox.showinfo("CISetup", "先に「Jenkins サーバーを初期設定」を実行してください。")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self._set_status("エージェント起動コマンドをコピーしました。")
    def _scan_env(self) -> None:
        self._set_status("環境をスキャンしています...")
        results = deps.env_scan.scan()
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
