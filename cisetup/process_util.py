"""subprocess 起動の共通ユーティリティ。"""

from __future__ import annotations

import subprocess
import sys


def no_window_kwargs() -> dict:
    """コンソール無しの GUI/exe から子プロセスを起動しても

    cmd ウィンドウが一瞬出ないようにする subprocess の追加引数を返す
    （Windows のみ。C# の ProcessStartInfo.CreateNoWindow=true 相当）。
    """
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}
