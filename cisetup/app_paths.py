from __future__ import annotations

import sys
from pathlib import Path


def get_package_root() -> Path:
    """ソース実行時は cisetup/、PyInstaller exe 時は展開先 (_MEIPASS)。"""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent
