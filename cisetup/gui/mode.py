"""プリセット（.NET / FPGA / カスタム）に合わせた画面の切り替え。

プリセットを変えても .NET 前提の説明文と入力欄（.sln / csproj / RID）が
そのまま残っていると、何が対象なのか分からなくなる。ここでは

* 文言 … `_mode_text` で登録したラベルをモード別の文に差し替える
* 入力欄 … `_mode_only` で登録したウィジェットを、そのモードのときだけ表示する

という 2 つの仕組みだけを提供し、実際の文言・対象は画面組み立て側に置く。
表示・非表示は pack を外して戻すだけなので、元の並び順を壊さないよう
初回に親フレーム内の並びを覚えておき、後ろの兄弟の手前へ戻す。
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field

from ..ci_preset_catalog import find_preset_by_name, fpga_tool, preset_mode

MODES = ("dotnet", "fpga", "custom")


@dataclass
class _ModeWidget:
    widget: tk.Misc
    modes: tuple[str, ...]
    pack_options: dict = field(default_factory=dict)


def _resolve_text(texts: dict[str, str], mode: str) -> str:
    """モード別の文言を選ぶ。専用文が無ければカスタム→.NET の順に落とす。"""
    if mode == "fpga":
        return texts.get("fpga") or texts.get("custom") or texts["dotnet"]
    if mode == "custom":
        return texts.get("custom") or texts["dotnet"]
    return texts["dotnet"]


class ModeMixin:
    def _init_mode_registry(self) -> None:
        self._mode_widgets: list[_ModeWidget] = []
        self._mode_texts: list[tuple[tk.Misc, dict[str, str]]] = []
        self._mode_order: dict[tk.Misc, list[tk.Misc]] = {}
        self._mode_order_ready = False

    # --- 画面組み立て時の登録 ---

    def _mode_text(self, widget: tk.Misc, dotnet: str, fpga: str = "", custom: str = "") -> tk.Misc:
        """モードによって文言が変わるラベルを登録する（`dotnet` が既定文）。"""
        self._mode_texts.append((widget, {"dotnet": dotnet, "fpga": fpga, "custom": custom}))
        widget.configure(text=dotnet)
        return widget

    def _mode_only(self, widget: tk.Misc, *modes: str) -> tk.Misc:
        """指定モードのときだけ表示するウィジェットを登録する（pack 済みで呼ぶ）。"""
        self._mode_widgets.append(_ModeWidget(widget, modes, dict(widget.pack_info())))
        return widget

    # --- 現在のモード ---

    def _current_preset_id(self) -> str:
        preset = find_preset_by_name(self._preset_var.get())
        return preset.id if preset else self._config.build.preset

    def _current_mode(self) -> str:
        return preset_mode(self._current_preset_id())

    def _current_fpga_tool(self) -> str:
        return fpga_tool(self._current_preset_id())

    # --- 反映 ---

    def _refresh_mode_ui(self) -> None:
        self._snapshot_mode_order()
        mode = self._current_mode()
        for widget, texts in self._mode_texts:
            widget.configure(text=_resolve_text(texts, mode))
        for entry in self._mode_widgets:
            self._apply_mode_visibility(entry, visible=mode in entry.modes)
        self._refresh_fpga_panel()

    def _snapshot_mode_order(self) -> None:
        """並び順は「まだ何も隠していない」最初の反映時に覚える必要がある。"""
        if self._mode_order_ready:
            return
        for entry in self._mode_widgets:
            self._sibling_order(entry.widget.master)
        self._mode_order_ready = True

    def _apply_mode_visibility(self, entry: _ModeWidget, visible: bool) -> None:
        managed = entry.widget.winfo_manager() == "pack"
        if visible and not managed:
            self._repack_in_order(entry)
        elif not visible and managed:
            entry.widget.pack_forget()

    def _repack_in_order(self, entry: _ModeWidget) -> None:
        options = {key: value for key, value in entry.pack_options.items() if key != "in"}
        parent = entry.widget.master
        order = self._sibling_order(parent)
        try:
            following = order[order.index(entry.widget) + 1 :]
        except ValueError:
            following = []
        for sibling in following:
            if sibling.winfo_manager() == "pack":
                entry.widget.pack(before=sibling, **options)
                return
        entry.widget.pack(**options)

    def _sibling_order(self, parent: tk.Misc) -> list[tk.Misc]:
        if parent not in self._mode_order:
            self._mode_order[parent] = list(parent.pack_slaves())
        return self._mode_order[parent]
