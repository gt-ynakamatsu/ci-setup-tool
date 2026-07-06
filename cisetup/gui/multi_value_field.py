from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk

from .layout import COLOR_CARD_BG, button, font


class MultiValueField:
    """＋/− で行を増減できる複数入力欄グループ（パス／URL を複数指定するため）。

    各行は [入力欄][参照...（任意）][＋][−]。＋ で空行を追加、− で行を削除する。
    行が 1 つだけのときは − でクリアのみ（最低 1 行は常に表示）。空行は値取得時に無視。
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        browse: str | None = None,
        on_change=None,
        entry_width: int | None = None,
    ) -> None:
        self._browse = browse
        self._on_change = on_change
        self._entry_width = entry_width
        try:
            self._bg = parent.cget("bg")
        except tk.TclError:
            self._bg = COLOR_CARD_BG
        self.container = tk.Frame(parent, bg=self._bg)
        self.container.pack(fill=tk.X)
        self._rows: list[dict] = []
        self._add_row("")

    def _notify(self) -> None:
        if self._on_change:
            self._on_change()

    def _add_row(self, value: str = "") -> dict:
        frame = tk.Frame(self.container, bg=self._bg)
        frame.pack(fill=tk.X, pady=2)
        var = tk.StringVar(value=value)
        var.trace_add("write", lambda *_: self._notify())
        if self._entry_width:
            entry = ttk.Entry(frame, textvariable=var, width=self._entry_width, font=font(12))
        else:
            entry = ttk.Entry(frame, textvariable=var, font=font(12))
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)
        row = {"var": var, "frame": frame, "entry": entry}
        if self._browse == "folder":
            browse_btn = button(frame, "参照...", lambda v=var: self._browse_folder(v), padx=10)
            browse_btn.pack(side=tk.LEFT, padx=(6, 0))
            row["browse_btn"] = browse_btn
        add_btn = button(frame, "＋", lambda: self._on_add(), padx=8)
        add_btn.pack(side=tk.LEFT, padx=(6, 0))
        remove_btn = button(frame, "−", lambda r=row: self._on_remove(r), padx=8)
        remove_btn.pack(side=tk.LEFT, padx=(4, 0))
        row["add_btn"] = add_btn
        row["remove_btn"] = remove_btn
        self._rows.append(row)
        return row

    def _browse_folder(self, var: tk.StringVar) -> None:
        path = filedialog.askdirectory(title="フォルダを選択")
        if path:
            var.set(path)

    def _on_add(self) -> None:
        self._add_row("")
        self._notify()

    def _on_remove(self, row: dict) -> None:
        if len(self._rows) <= 1:
            row["var"].set("")
            return
        row["frame"].destroy()
        self._rows.remove(row)
        self._notify()

    def get_values(self) -> list[str]:
        return [r["var"].get().strip() for r in self._rows if r["var"].get().strip()]

    def set_values(self, values: list[str]) -> None:
        cleaned = [str(v) for v in (values or []) if str(v).strip()] or [""]
        for row in self._rows:
            row["frame"].destroy()
        self._rows.clear()
        for value in cleaned:
            self._add_row(value)

    def set_enabled(self, enabled: bool) -> None:
        """入力欄と行操作ボタンの有効/無効を切り替える（グレーアウト用）。"""
        state = tk.NORMAL if enabled else tk.DISABLED
        for row in self._rows:
            row["entry"].configure(state=state)
            for key in ("add_btn", "remove_btn", "browse_btn"):
                btn = row.get(key)
                if btn is not None:
                    btn.configure(state=state)

    def focus(self) -> None:
        if self._rows:
            try:
                self._rows[0]["entry"].focus_set()
            except tk.TclError:
                pass
