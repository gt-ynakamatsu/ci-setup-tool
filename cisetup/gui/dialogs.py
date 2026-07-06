from __future__ import annotations

import threading
import tkinter as tk

from . import deps
from .commit_dialog import prompt_commit_message


class DialogMixin:
    def _prompt_commit(self) -> str | None:
        result: dict[str, str | None] = {}
        done = threading.Event()

        def ask() -> None:
            result["value"] = prompt_commit_message(self, deps.git_service.DEFAULT_COMMIT_MESSAGE)
            done.set()

        self.after(0, ask)
        done.wait()
        return result.get("value")

    def _ask(self, title: str, message: str) -> bool:
        result: dict[str, bool] = {}
        done = threading.Event()

        def ask() -> None:
            result["value"] = deps.messagebox.askyesno(title, message)
            done.set()

        self.after(0, ask)
        done.wait()
        return result.get("value", False)

    def _info(self, title: str, message: str) -> None:
        self.after(0, lambda: deps.messagebox.showinfo(title, message))

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)

    def _append_text(self, widget: tk.Text, text: str) -> None:
        widget.insert(tk.END, text + "\n")
        widget.see(tk.END)

    def _set_status(self, text: str) -> None:
        self.after(0, lambda: self._status.configure(text=text))

    def _focus_storage_paths(self) -> None:
        """③ 保存先の書き込み先ベース欄にフォーカスを当てる。"""
        field = self._multi_fields.get("storage.base_paths")
        if field is not None:
            field.focus()

    def _run_async(self, func) -> None:
        def worker() -> None:
            try:
                func()
            except (ValueError, deps.JenkinsError, deps.LocalCIError, deps.git_service.GitError, OSError) as exc:
                msg = str(exc)
                if "書き込み先ベース" in msg:
                    self.after(0, self._focus_storage_paths)
                self.after(0, lambda m=msg: deps.messagebox.showerror("エラー", m))
                self.after(0, lambda m=msg: self._status.configure(text=f"エラー: {m}"))

        threading.Thread(target=worker, daemon=True).start()
