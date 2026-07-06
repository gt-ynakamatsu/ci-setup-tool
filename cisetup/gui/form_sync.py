from __future__ import annotations

from pathlib import Path

from ..ci_preset_catalog import PRESETS, find_preset
from .layout import COLOR_DESC, COLOR_TEXT
from .util import safe_int


class FormSyncMixin:
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
            "storage.analysis_dir": c.storage.analysis_dir,
            "storage.tests_dir": c.storage.tests_dir,
            "storage.source_dir": c.storage.source_dir,
            "jenkins.job_name": c.jenkins.job_name,
            "jenkins.agent_label": c.jenkins.agent_label,
            "jenkins.cron_schedule": c.jenkins.cron_schedule,
            "jenkins.poll_schedule": c.jenkins.poll_schedule,
            "jenkins.agent_workspace_path": c.jenkins.agent_workspace_path,
            "jenkins.teams_credential_id": c.jenkins.teams_credential_id,
            "jenkins.timezone": c.jenkins.timezone,
            "jenkins.build_timeout_minutes": str(c.jenkins.build_timeout_minutes),
            "jenkins.log_retention_count": str(c.jenkins.log_retention_count),
            "jenkins.checkout_retry_count": str(c.jenkins.checkout_retry_count),
            "jenkins.retry_max_count": str(c.jenkins.retry_max_count),
            "jenkins.retry_delay_seconds": str(c.jenkins.retry_delay_seconds),
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
            "storage.source_urls": c.storage.source_urls,
        }
        for key, values in multi_values.items():
            if key in self._multi_fields:
                self._multi_fields[key].set_values(list(values))

        self._use_date_var.set(c.storage.use_date_subfolder)
        self._archive_source_var.set(c.storage.archive_source)
        self._enable_logs_var.set(c.storage.enable_logs)
        self._enable_releases_var.set(c.storage.enable_releases)
        self._enable_analysis_var.set(c.storage.enable_analysis)
        self._enable_tests_var.set(c.storage.enable_tests)
        self._push_env_var.set(c.jenkins.push_ci_file_server_env)
        self._retry_wrapper_var.set(c.jenkins.retry_wrapper_enabled)
        self._on_retry_wrapper_changed()
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
        c.storage.analysis_dir = get("storage.analysis_dir") or "analysis"
        c.storage.tests_dir = get("storage.tests_dir") or "tests"
        c.storage.source_dir = get("storage.source_dir") or "source"
        c.storage.release_urls = get_multi("storage.release_urls")
        c.storage.analysis_urls = get_multi("storage.analysis_urls")
        c.storage.logs_urls = get_multi("storage.logs_urls")
        c.storage.tests_urls = get_multi("storage.tests_urls")
        c.storage.source_urls = get_multi("storage.source_urls")
        c.storage.use_date_subfolder = bool(self._use_date_var.get())
        c.storage.archive_source = bool(self._archive_source_var.get())
        c.storage.enable_logs = bool(self._enable_logs_var.get())
        c.storage.enable_releases = bool(self._enable_releases_var.get())
        c.storage.enable_analysis = bool(self._enable_analysis_var.get())
        c.storage.enable_tests = bool(self._enable_tests_var.get())

        c.jenkins.job_name = get("jenkins.job_name")
        c.jenkins.agent_label = get("jenkins.agent_label")
        c.jenkins.cron_schedule = get("jenkins.cron_schedule")
        c.jenkins.poll_schedule = get("jenkins.poll_schedule")
        c.jenkins.agent_workspace_path = get("jenkins.agent_workspace_path")
        c.jenkins.push_ci_file_server_env = bool(self._push_env_var.get())
        c.jenkins.ci_file_servers = get_multi("jenkins.ci_file_servers")
        c.jenkins.teams_credential_id = get("jenkins.teams_credential_id")
        c.jenkins.timezone = get("jenkins.timezone")
        c.jenkins.build_timeout_minutes = safe_int(get("jenkins.build_timeout_minutes"), 30)
        c.jenkins.log_retention_count = safe_int(get("jenkins.log_retention_count"), 30)
        c.jenkins.checkout_retry_count = safe_int(get("jenkins.checkout_retry_count"), 3)
        c.jenkins.retry_wrapper_enabled = bool(self._retry_wrapper_var.get())
        c.jenkins.retry_max_count = safe_int(get("jenkins.retry_max_count"), 3)
        c.jenkins.retry_delay_seconds = safe_int(get("jenkins.retry_delay_seconds"), 300)
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
                self._preview_targets.set("(未設定 — ③ 保存先の書き込み先を入力)")
        except (ValueError, KeyError):
            pass
        self._update_teams_url_states()
        self._update_path_statuses()
    def _update_teams_url_states(self) -> None:
        """Teams 通知 URL 欄を、カテゴリ有効フラグと格納フォルダの有無に連動させる。"""
        categories = getattr(self, "_teams_url_categories", None)
        if not categories:
            return
        c = self._config
        for key, (enable_attr, category) in categories.items():
            field = self._multi_fields.get(key)
            if field is None:
                continue
            enabled = bool(getattr(c.storage, enable_attr))
            folder_ready = self._repo.storage_folder_exists(c, category) if enabled else False
            active = enabled and folder_ready
            field.set_enabled(active)
            label = self._teams_url_labels.get(key)
            if label is not None:
                label.configure(fg=COLOR_TEXT if active else COLOR_DESC)
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
