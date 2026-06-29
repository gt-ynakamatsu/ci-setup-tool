from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class CommitMessageDialog(tk.Toplevel):
    """コミットメッセージ入力ダイアログ。OK 時に self.result を設定する。"""

    def __init__(self, parent: tk.Misc, default_message: str) -> None:
        super().__init__(parent)
        self.title("コミットメッセージ")
        self.result: str | None = None
        self.transient(parent)
        self.resizable(False, False)

        ttk.Label(self, text="Git に commit するメッセージを入力してください。").pack(
            padx=12, pady=(12, 4), anchor=tk.W
        )

        self._var = tk.StringVar(value=default_message)
        entry = ttk.Entry(self, textvariable=self._var, width=60)
        entry.pack(padx=12, pady=4, fill=tk.X)
        entry.focus_set()
        entry.selection_range(0, tk.END)

        buttons = ttk.Frame(self)
        buttons.pack(padx=12, pady=12, anchor=tk.E)
        ttk.Button(buttons, text="OK", command=self._ok).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="キャンセル", command=self._cancel).pack(side=tk.LEFT, padx=4)

        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _ok(self) -> None:
        message = self._var.get().strip()
        if message:
            self.result = message
            self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


def prompt_commit_message(parent: tk.Misc, default_message: str) -> str | None:
    dialog = CommitMessageDialog(parent, default_message)
    dialog.grab_set()
    parent.wait_window(dialog)
    return dialog.result
