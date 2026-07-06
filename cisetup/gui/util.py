from __future__ import annotations

import sys


def safe_int(value: str, fallback: int) -> int:
    try:
        return int(value.strip())
    except (ValueError, AttributeError):
        return fallback


def enable_dpi_awareness() -> None:
    """高 DPI でぼやけないよう DPI 対応を有効化する（Tk() 生成前に呼ぶ）。"""
    if sys.platform != "win32":
        return
    import ctypes

    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass
