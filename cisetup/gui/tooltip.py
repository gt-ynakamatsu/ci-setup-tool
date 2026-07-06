from __future__ import annotations

import tkinter as tk

from .layout import COLOR_CARD_BG, COLOR_STEP, _bg_of, font


class ToolTip:
    """ウィジェットにホバー時のツールチップを付与する。"""

    def __init__(
        self,
        widget: tk.Widget,
        text: str,
        delay_ms: int = 400,
        wraplength: int = 420,
    ) -> None:
        self._widget = widget
        self._text = text
        self._delay = delay_ms
        self._wraplength = wraplength
        self._tip: tk.Toplevel | None = None
        self._after_id: str | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event: object = None) -> None:
        self._cancel()
        self._after_id = self._widget.after(self._delay, self._show)

    def _show(self) -> None:
        if self._tip or not self._text:
            return
        x = self._widget.winfo_rootx() + 16
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self._tip,
            text=self._text,
            justify=tk.LEFT,
            background="#ffffe0",
            relief=tk.SOLID,
            borderwidth=1,
            font=font(12),
            padx=8,
            pady=6,
            wraplength=self._wraplength,
        )
        label.pack()

    def _hide(self, _event: object = None) -> None:
        self._cancel()
        if self._tip:
            self._tip.destroy()
            self._tip = None

    def _cancel(self) -> None:
        if self._after_id:
            self._widget.after_cancel(self._after_id)
            self._after_id = None


def attach_tooltip(widget: tk.Widget, text: str) -> None:
    if text:
        ToolTip(widget, text)


def help_icon(parent: tk.Misc, text: str, *, bg: str | None = None) -> tk.Label:
    """設定項目の横に表示する「?」ヘルプアイコン（ホバーで説明を表示）。"""
    bg = bg if bg is not None else _bg_of(parent, COLOR_CARD_BG)
    icon = tk.Label(
        parent,
        text="?",
        font=font(11, bold=True),
        fg=COLOR_STEP,
        bg=bg,
        cursor="question_arrow",
        padx=2,
    )
    attach_tooltip(icon, text)
    return icon
