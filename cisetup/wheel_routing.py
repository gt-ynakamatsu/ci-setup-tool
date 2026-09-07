"""マウスホイールの配送先を決める処理。

tkinter を import しないため、GUI が無い環境（CI・Linux）でも単体テストできる。
ウィジェットは ``yview`` / ``yview_scroll`` / ``master`` を持つものとして扱う。

Windows の Tk は ``<MouseWheel>`` を「ポインタの下」ではなく「フォーカスのある
ウィジェット」へ配送する。そのままだとログ欄にフォーカスが無いとホイールが届かず、
逆にフォーカスがあると別の場所を指していてもログが動く。そこで配送は常に
ポインタ位置から決める。
"""

from __future__ import annotations

from typing import Any

# log_text() が作る Text に付ける目印。
LOG_WIDGET_FLAG = "_cisetup_log_widget"

# route() の戻り値。呼び出し側とテストが結果を判別できるようにする。
TARGET_LOG = "log"
TARGET_PAGE = "page"
TARGET_NONE = "none"


def scroll_widget(widget: Any, units: int) -> bool:
    """縦に units 行スクロールする。端で動かせなければ False。"""
    if widget is None or not units:
        return False
    try:
        first, last = widget.yview()
    except Exception:  # noqa: BLE001 - Tk からは TclError 以外も飛びうる
        return False
    if (units < 0 and first <= 0.0) or (units > 0 and last >= 1.0):
        return False
    widget.yview_scroll(units, "units")
    return True


def find_log_widget(node: Any) -> Any | None:
    """自身から親をたどってログ欄を探す。無ければ None。"""
    while node is not None:
        if getattr(node, LOG_WIDGET_FLAG, False):
            return node
        node = getattr(node, "master", None)
    return None


def route(under_pointer: Any, page_canvas: Any, units: int) -> str:
    """ポインタ下のウィジェットとページを見て、どちらを送ったか返す。

    ログ欄の上ならログを優先し、端まで来たらページへ渡す（行き止まりにしない）。
    """
    if not units:
        return TARGET_NONE
    log = find_log_widget(under_pointer)
    if log is not None and scroll_widget(log, units):
        return TARGET_LOG
    if page_canvas is not None:
        page_canvas.yview_scroll(units, "units")
        return TARGET_PAGE
    return TARGET_NONE
