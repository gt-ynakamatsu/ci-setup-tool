from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

from .. import paths


class FilePickMixin:
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
                "• <プロジェクト>\\CISetup\\cisetup.config.json\n"
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
