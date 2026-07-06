from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import ttk

from .layout import COLOR_CARD_BG, button, font
from .multi_value_field import MultiValueField
from .tooltip import help_icon


def _label_width_units(text: str) -> int:
    """tk.Label の width 用。全角文字は約 2 単位として見積もる。"""
    return sum(2 if ord(ch) > 127 else 1 for ch in text)


class FieldMixin:
    def _register_field(self, key: str) -> tk.StringVar:
        if key not in self._fields:
            var = tk.StringVar()
            var.trace_add("write", lambda *_: self._on_field_changed())
            self._fields[key] = var
        return self._fields[key]

    def _add_multi_field(
        self,
        parent: tk.Misc,
        key: str,
        label: str = "",
        help_text: str = "",
        browse: str | None = None,
    ) -> MultiValueField:
        """＋/− で増減できる複数入力欄グループを追加する（書き込み先・閲覧 URL 用）。"""
        try:
            bg = parent.cget("bg")
        except tk.TclError:
            bg = COLOR_CARD_BG
        if label:
            row = tk.Frame(parent, bg=bg)
            row.pack(anchor="w", fill=tk.X, pady=(6, 0))
            tk.Label(row, text=label, anchor="w", bg=bg, font=font(12)).pack(side=tk.LEFT)
            if help_text:
                help_icon(row, help_text, bg=bg).pack(side=tk.LEFT, padx=(4, 0))
        field = MultiValueField(parent, browse=browse, on_change=self._on_field_changed)
        self._multi_fields[key] = field
        return field

    def _add_field(
        self,
        parent: tk.Misc,
        key: str,
        label: str,
        help_text: str = "",
        show: str | None = None,
        browse: str | None = None,
        label_width: int = 26,
        show_label: bool = True,
        path_check: bool = False,
        check_var: tk.BooleanVar | None = None,
        check_help: str = "",
    ) -> None:
        try:
            bg = parent.cget("bg")
        except tk.TclError:
            bg = COLOR_CARD_BG
        row = tk.Frame(parent, bg=bg)
        row.pack(fill=tk.X, pady=4)
        if check_var is not None:
            chk = tk.Checkbutton(
                row,
                variable=check_var,
                command=self._on_field_changed,
                bg=bg,
                activebackground=bg,
            )
            chk.pack(side=tk.LEFT)
            if check_help:
                help_icon(row, check_help, bg=bg).pack(side=tk.LEFT, padx=(0, 2))
        if not show_label and help_text:
            help_icon(row, help_text, bg=bg).pack(side=tk.LEFT, padx=(0, 4))
        if show_label and label:
            width = max(label_width, _label_width_units(label)) if label_width > 0 else 0
            lbl = tk.Label(row, text=label, anchor="w", bg=bg, font=font(12))
            if width > 0:
                lbl.config(width=width)
            lbl.pack(side=tk.LEFT, anchor="n")
            if help_text:
                help_icon(row, help_text, bg=bg).pack(side=tk.LEFT, anchor="n", padx=(2, 6))
        elif show_label and help_text:
            help_icon(row, help_text, bg=bg).pack(side=tk.LEFT, anchor="n", padx=(0, 6))
        var = self._register_field(key)
        entry = (
            ttk.Entry(row, textvariable=var, show=show, font=font(12))
            if show
            else ttk.Entry(row, textvariable=var, font=font(12))
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)
        self._field_widgets[key] = entry
        if browse == "file":
            button(row, "参照...", lambda k=key: self._browse_file(k), padx=10).pack(
                side=tk.LEFT, padx=(8, 0)
            )
        elif browse == "folder":
            button(row, "参照...", lambda k=key: self._browse_folder(k), padx=10).pack(
                side=tk.LEFT, padx=(8, 0)
            )
        if path_check:
            status = tk.Label(
                row, text="", width=22, anchor="w", bg=bg, font=font(11)
            )
            status.pack(side=tk.LEFT, padx=(8, 0))
            self._path_status[key] = status

    def _on_profile_changed(self) -> None:
        is_custom = self._profile_var.get().startswith("カスタム")
        if is_custom:
            self._custom_build_panel.pack(fill=tk.X, pady=(12, 0))
        else:
            self._custom_build_panel.pack_forget()
        self._on_field_changed()

    def _open_link(self, url: str) -> None:
        webbrowser.open(url)
