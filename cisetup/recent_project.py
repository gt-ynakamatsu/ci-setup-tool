from __future__ import annotations

import os
from pathlib import Path


class RecentProjectStore:
    """最後に開いたプロジェクトフォルダを %AppData%\\CISetup に記憶する。"""

    def __init__(self, file_path: Path | None = None) -> None:
        if file_path is not None:
            self._file_path = file_path
        else:
            appdata = os.environ.get("APPDATA") or str(Path.home())
            self._file_path = Path(appdata) / "CISetup" / "recent-project.txt"

    def get_last_project_root(self) -> Path | None:
        try:
            if not self._file_path.is_file():
                return None
            path = Path(self._file_path.read_text(encoding="utf-8").strip())
            return path if path.is_dir() else None
        except OSError:
            return None

    def save(self, repository_root: Path) -> None:
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            self._file_path.write_text(str(repository_root), encoding="utf-8")
        except OSError:
            pass
