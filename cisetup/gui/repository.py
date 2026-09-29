from __future__ import annotations

from pathlib import Path

from .. import paths
from ..project_setup import (
    apply_auto_detection,
    apply_fpga_auto_detection,
    count_projects,
    deploy_ci_files,
    has_solution_file,
)


class RepositoryMixin:
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
        text, color = self._project_check_message(repository_root)
        self._status_project.configure(text=text, fg=color)
        self._set_status(f"CI ファイルを配置: {len(written)} 件")

    def _project_check_message(self, repository_root: Path) -> tuple[str, str]:
        """選んだフォルダが今のモードの対象になっているかを一言で伝える。"""
        mode = self._current_mode()
        if mode == "fpga":
            tool = self._current_fpga_tool()
            found = self._fpga_candidates(tool, rescan=True)
            if found:
                return (f"CI ファイルを配置しました。{tool} の合成対象: " + "、".join(found), "#2a2")
            wanted = "build.tcl / *.xpr" if tool == "Vivado" else "*.qpf"
            return (
                f"警告: {wanted} が見つかりません。{tool} のプロジェクトがあるリポジトリルートか確認してください。",
                "#c33",
            )
        if mode == "dotnet" and not has_solution_file(repository_root):
            return (
                "警告: *.sln が見つかりません。.sln があるリポジトリルートか確認してください。",
                "#c33",
            )
        return ("CI ファイルを配置しました。", "#2a2")
    def _redeploy_ci(self) -> None:
        root = self._ensure_repo()
        self._deploy_ci_files(root)
        self._set_status("CI ファイルを再配置しました。")
    def _redetect_project(self) -> None:
        """.sln から再検出して補完・修正する（実在しないパスも探し直す。有効な入力は保持）。"""
        root = self._ensure_repo()
        if self._current_mode() == "fpga":
            self._redetect_fpga_project(root)
            return
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
    def _redetect_fpga_project(self, root: Path) -> None:
        """FPGA モードの再検出（合成対象の探し直しとプロジェクト名の補完）。"""
        self._detect_fpga_projects()
        self._form_to_config()
        self._config = apply_fpga_auto_detection(root, self._config, self._current_fpga_tool())
        self._config_to_form()
        self._update_preview()
        self._set_status("再検出: 合成対象とプロジェクト名を探し直しました。")

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
        # 設定済みのプロジェクトは種類が決まっているので、選択画面を出さずフォームへ。
        if has_config:
            self._show_form()
        self._update_preview()
