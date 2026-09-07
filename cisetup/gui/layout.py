"""C# WPF 版 MainWindow.xaml に近いカード／スクロールレイアウト。

WPF の見た目に寄せるため、
- フォントは日本語がきれいな ``Yu Gothic UI`` に統一
- フォントサイズは負値（= ピクセル指定）で WPF の FontSize と一致
- カードは Canvas で角丸（WPF CornerRadius=4）を再現
- ボタンはフラット（ホバーで色が変わる）
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from .. import wheel_routing as wheel

FONT_FAMILY = "Yu Gothic UI"

# C# MainWindow.xaml の色
COLOR_WINDOW_BG = "#FFFFFF"
COLOR_STEP = "#0078D4"
COLOR_HINT = "#888888"
COLOR_DESC = "#666666"
COLOR_TEXT = "#1F1F1F"
COLOR_CARD_BG = "#F5F9FF"
COLOR_CARD_BORDER = "#0078D4"
COLOR_BEGINNER_BG = "#FFFDF5"
COLOR_BEGINNER_BORDER = "#E0B000"
COLOR_BEGINNER_TITLE = "#9A7A00"
COLOR_ENV_BG = "#F3F8FF"
COLOR_PRESET_BG = "#EEF6FF"
COLOR_RUN_BG = "#F0FFF4"
COLOR_RUN_BORDER = "#107C10"
COLOR_RUN_TITLE = "#107C10"
COLOR_SERVER_BG = "#FFFBF5"
COLOR_SERVER_BORDER = "#CA5010"
COLOR_SERVER_TITLE = "#CA5010"

# ボタン配色（kind 別）
_BUTTON_PALETTE = {
    # 白・薄青カード・薄緑セクションのいずれとも差が出るよう、薄い青で塗る
    "secondary": {
        "bg": "#D6E8F7",
        "fg": COLOR_TEXT,
        "hover": "#B8D9F2",
        "border": "#005A9E",
    },
    "primary": {"bg": COLOR_RUN_TITLE, "fg": "#FFFFFF", "hover": "#0E6B0E", "border": COLOR_RUN_TITLE},
    "accent": {"bg": COLOR_STEP, "fg": "#FFFFFF", "hover": "#106EBE", "border": COLOR_STEP},
    "warn": {"bg": COLOR_SERVER_TITLE, "fg": "#FFFFFF", "hover": "#A8430D", "border": COLOR_SERVER_TITLE},
}


# 画面 DPI（拡大率）に合わせた表示倍率。app 起動時に set_scale で設定する。
_SCALE = 1.0


def set_scale(scale: float) -> None:
    """ディスプレイの拡大率（96dpi=1.0, 150%=1.5 など）を設定する。"""
    global _SCALE
    _SCALE = scale if scale and scale > 0 else 1.0


def scaled(px: float) -> int:
    """ピクセル値を画面倍率に合わせて拡大する。"""
    return max(1, int(round(px * _SCALE)))


def font(size_px: int, *, bold: bool = False) -> tuple:
    """WPF の FontSize(px) に合わせ、DPI 倍率を反映したフォントタプルを返す。"""
    size = -scaled(size_px)
    return (FONT_FAMILY, size, "bold") if bold else (FONT_FAMILY, size)


def mono_font(size_px: int = 12, *, bold: bool = False) -> tuple:
    """ログ等の等幅フォント（DPI 倍率反映）。"""
    size = -scaled(size_px)
    return ("Consolas", size, "bold") if bold else ("Consolas", size)


def _bg_of(parent: tk.Misc, fallback: str = COLOR_CARD_BG) -> str:
    try:
        return parent.cget("bg")
    except tk.TclError:
        return fallback


def _widget_under_pointer(root: tk.Misc, x_root: int, y_root: int) -> tk.Misc | None:
    try:
        return root.winfo_containing(x_root, y_root)
    except tk.TclError:
        return None


def _enclosing_scrollable(widget: tk.Misc) -> "ScrollableFrame | None":
    node = widget if isinstance(widget, ScrollableFrame) else widget.master
    while node is not None:
        if isinstance(node, ScrollableFrame):
            return node
        node = node.master
    return None


def route_wheel(widget: tk.Misc, x_root: int, y_root: int, units: int) -> str:
    """ポインタ位置を見て、ログ欄かページのどちらを送るか決める。"""
    page = _enclosing_scrollable(widget)
    return wheel.route(
        _widget_under_pointer(widget, x_root, y_root),
        page.canvas if page is not None else None,
        units,
    )


class ScrollableFrame(ttk.Frame):
    """縦スクロール可能なメイン領域。"""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.canvas = tk.Canvas(
            self, highlightthickness=0, borderwidth=0, background=COLOR_WINDOW_BG
        )
        self.vbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, background=COLOR_WINDOW_BG)
        self.inner.bind(
            "<Configure>",
            lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self._bind_mousewheel()

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)

    def _bind_mousewheel(self) -> None:
        """ホイールを常時受け取り、ポインタ位置で行き先を決める。

        Windows の Tk は ``<MouseWheel>`` をポインタ下ではなく**フォーカスのある
        ウィジェット**へ配送する。ウィジェット個別の bind ではログ欄にフォーカスが
        無いと届かないため、bind_all で受けてから配送先を自分で決める。
        Enter/Leave で bind_all を付け外しすると子ウィジェットへの出入りで
        取り外されたままになるため、付けっぱなしにする。
        """
        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.bind_all("<Button-4>", lambda e: route_wheel(self, e.x_root, e.y_root, -1), add="+")  # X11
        self.bind_all("<Button-5>", lambda e: route_wheel(self, e.x_root, e.y_root, 1), add="+")

    def _on_mousewheel(self, event: tk.Event) -> None:
        route_wheel(self, event.x_root, event.y_root, int(-event.delta / 120))


def log_text(
    parent: tk.Misc,
    *,
    height: int = 8,
    wrap: str = tk.WORD,
    pady: tuple[int, int] = (0, 0),
) -> tk.Text:
    """縦スクロールできるログ表示欄。

    ホイールの行き先は常にポインタ位置で決める。Windows の Tk はフォーカスのある
    ウィジェットへ ``<MouseWheel>`` を配送し、Text クラス標準の binding が
    そのまま自分をスクロールしてしまうため、ウィジェット側では必ず "break" を
    返して標準 binding を止め、判定を route_wheel に一本化する。
    """
    holder = tk.Frame(parent, background=_bg_of(parent, COLOR_WINDOW_BG))
    text = tk.Text(
        holder,
        height=height,
        wrap=wrap,
        font=mono_font(12),
        relief=tk.SOLID,
        borderwidth=1,
        highlightthickness=0,
        background="#FFFFFF",
    )
    bar = ttk.Scrollbar(holder, orient=tk.VERTICAL, command=text.yview)
    text.configure(yscrollcommand=bar.set)
    text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    bar.pack(side=tk.RIGHT, fill=tk.Y)
    holder.pack(fill=tk.X, pady=pady)
    setattr(text, wheel.LOG_WIDGET_FLAG, True)

    def on_wheel(event: tk.Event, units: int) -> str:
        route_wheel(text, event.x_root, event.y_root, units)
        return "break"

    text.bind("<MouseWheel>", lambda e: on_wheel(e, int(-e.delta / 120)), add="+")
    text.bind("<Button-4>", lambda e: on_wheel(e, -1), add="+")  # X11
    text.bind("<Button-5>", lambda e: on_wheel(e, 1), add="+")
    return text


def _round_rect_points(x1: float, y1: float, x2: float, y2: float, r: float) -> list[float]:
    r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
    return [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1,
    ]


class _Card(tk.Canvas):
    """角丸の枠を描く Canvas。内容は ``body`` フレームに入れる。"""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        bg: str,
        border: str,
        border_width: int,
        padding: int,
        radius: int,
    ) -> None:
        super().__init__(
            parent, highlightthickness=0, borderwidth=0, background=COLOR_WINDOW_BG
        )
        self._bg = bg
        self._border = border
        self._bw = max(border_width, 1)
        self._pad = padding
        self._radius = radius
        self.body = tk.Frame(self, background=bg)
        self._win = self.create_window(padding, padding, window=self.body, anchor="nw")
        self.bind("<Configure>", self._redraw)
        self.body.bind("<Configure>", self._redraw)

    def _redraw(self, _event: tk.Event | None = None) -> None:
        width = self.winfo_width()
        if width <= 1:
            return
        inner_w = width - 2 * self._pad
        self.itemconfigure(self._win, width=inner_w)
        self.update_idletasks()
        body_h = self.body.winfo_reqheight()
        total_h = body_h + 2 * self._pad
        self.configure(height=total_h)
        self.delete("card_bg")
        pts = _round_rect_points(
            self._bw, self._bw, width - self._bw, total_h - self._bw, self._radius
        )
        self.create_polygon(
            pts,
            smooth=True,
            fill=self._bg,
            outline=self._border,
            width=self._bw,
            tags="card_bg",
        )
        self.tag_lower("card_bg")


def card(
    parent: tk.Misc,
    *,
    bg: str = COLOR_CARD_BG,
    border: str = COLOR_CARD_BORDER,
    border_width: int = 1,
    padding: int = 16,
    radius: int = 6,
    pady: tuple[int, int] = (0, 14),
) -> tk.Frame:
    holder = _Card(
        parent,
        bg=bg,
        border=border,
        border_width=border_width,
        padding=padding,
        radius=radius,
    )
    holder.pack(fill=tk.X, pady=pady)
    return holder.body


def step_title(parent: tk.Misc, text: str) -> tk.Label:
    return tk.Label(
        parent,
        text=text,
        font=font(16, bold=True),
        fg=COLOR_STEP,
        bg=_bg_of(parent),
        anchor="w",
        justify=tk.LEFT,
    )


def section_title(parent: tk.Misc, text: str, color: str) -> tk.Label:
    return tk.Label(
        parent,
        text=text,
        font=font(16, bold=True),
        fg=color,
        bg=_bg_of(parent),
        anchor="w",
        justify=tk.LEFT,
    )


def step_desc(parent: tk.Misc, text: str) -> tk.Label:
    return tk.Label(
        parent,
        text=text,
        font=font(12),
        fg=COLOR_DESC,
        bg=_bg_of(parent),
        anchor="w",
        justify=tk.LEFT,
        wraplength=860,
    )


def hint_label(parent: tk.Misc, text: str, *, bg: str | None = None) -> tk.Label:
    return tk.Label(
        parent,
        text=text,
        font=font(11),
        fg=COLOR_HINT,
        bg=bg or _bg_of(parent),
        anchor="w",
        justify=tk.LEFT,
        wraplength=860,
    )


def button(
    parent: tk.Misc,
    text: str,
    command: Callable[[], None] | None,
    *,
    kind: str = "secondary",
    size_px: int = 12,
    padx: int = 14,
    pady: int = 6,
    bold: bool | None = None,
    **kwargs,
) -> tk.Button:
    palette = _BUTTON_PALETTE[kind]
    if bold is None:
        bold = kind != "secondary"
    outline = 2 if kind == "secondary" else 1
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        font=font(size_px, bold=bold),
        bg=palette["bg"],
        fg=palette["fg"],
        activebackground=palette["hover"],
        activeforeground=palette["fg"],
        relief=tk.FLAT,
        bd=0,
        highlightthickness=outline,
        highlightbackground=palette["border"],
        highlightcolor=palette["border"],
        cursor="hand2",
        padx=padx,
        pady=pady,
    )
    btn.bind("<Enter>", lambda _e: btn.configure(bg=palette["hover"]), add="+")
    btn.bind("<Leave>", lambda _e: btn.configure(bg=palette["bg"]), add="+")
    if kwargs:
        btn.configure(**kwargs)
    return btn


def primary_button(parent: tk.Misc, text: str, command, **kwargs) -> tk.Button:
    kwargs.setdefault("size_px", 15)
    kwargs.setdefault("padx", 28)
    kwargs.setdefault("pady", 10)
    return button(parent, text, command, kind="primary", **kwargs)


class Expander(tk.Frame):
    """ttk.Expander の簡易代替（初期は折りたたみ）。"""

    def __init__(self, parent: tk.Misc, title: str, *, expanded: bool = False) -> None:
        super().__init__(parent, background=_bg_of(parent, COLOR_WINDOW_BG))
        self._expanded = expanded
        self._title = title
        self._toggle = tk.Button(
            self,
            text=self._header_text(),
            command=self._on_toggle,
            anchor="w",
            relief=tk.FLAT,
            bd=0,
            font=font(13, bold=True),
            fg=COLOR_TEXT,
            bg=_bg_of(parent, COLOR_WINDOW_BG),
            activebackground="#EAF3FB",
            cursor="hand2",
            padx=10,
            pady=8,
        )
        self._toggle.pack(fill=tk.X)
        self.content = tk.Frame(self, background=_bg_of(parent, COLOR_WINDOW_BG))
        if expanded:
            self.content.pack(fill=tk.X, pady=(4, 0))

    def _header_text(self) -> str:
        arrow = "▼" if self._expanded else "▶"
        return f"{arrow}  {self._title}"

    def _on_toggle(self) -> None:
        self._expanded = not self._expanded
        self._toggle.configure(text=self._header_text())
        if self._expanded:
            self.content.pack(fill=tk.X, pady=(4, 0))
        else:
            self.content.pack_forget()

    def open(self) -> None:
        """折りたたまれていれば展開する。"""
        if not self._expanded:
            self._on_toggle()
