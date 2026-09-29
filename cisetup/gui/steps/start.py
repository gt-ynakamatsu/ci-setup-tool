"""起動直後の「どの CI を作るか」を選ぶ画面。

.NET と FPGA では入力する項目もビルド手順も違うため、先に種類を決めてから
その構成に合わせたフォームだけを見せる。保存済みの設定があるプロジェクトを
開いたときは、選び直しを求めず保存された種類のフォームへ直行する。
"""

from __future__ import annotations

import tkinter as tk

from ...ci_preset_catalog import PRESETS
from ..layout import (
    COLOR_CARD_BG,
    COLOR_DESC,
    COLOR_PRESET_BG,
    COLOR_STEP,
    COLOR_TEXT,
    COLOR_WINDOW_BG,
    button,
    card,
    font,
)

_CHOOSER_HINT = "作りたい CI の種類を選んでください（あとから画面上部で変更できます）。"
_FORM_HINT = "上から順に入力して、最後の「セットアップを実行」を押すだけです。"


class StartStepMixin:
    def _build_mode_chooser(self, parent: tk.Frame) -> None:
        tk.Label(
            parent,
            text="どの CI を作りますか？",
            font=font(20, bold=True),
            fg=COLOR_TEXT,
            bg=COLOR_WINDOW_BG,
            anchor="w",
        ).pack(anchor="w", pady=(4, 4))
        tk.Label(
            parent,
            text=(
                "選んだ種類に合わせて、入力する項目（.NET なら .sln / csproj、FPGA なら合成対象）と "
                "CI が実行するビルド手順が変わります。"
            ),
            font=font(12),
            fg=COLOR_DESC,
            bg=COLOR_WINDOW_BG,
            anchor="w",
            wraplength=self._px(860),
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 14))

        for preset in PRESETS:
            frame = card(parent, bg=COLOR_PRESET_BG, pady=(0, 10))
            top = tk.Frame(frame, bg=COLOR_PRESET_BG)
            top.pack(fill=tk.X)
            tk.Label(
                top,
                text=preset.name,
                font=font(14, bold=True),
                fg=COLOR_STEP,
                bg=COLOR_PRESET_BG,
                anchor="w",
            ).pack(side=tk.LEFT)
            button(
                top,
                "この種類で始める",
                lambda p=preset: self._choose_mode(p.name),
                kind="accent",
                padx=18,
                pady=6,
            ).pack(side=tk.RIGHT)
            tk.Label(
                frame,
                text=preset.description,
                font=font(11),
                fg=COLOR_DESC,
                bg=COLOR_PRESET_BG,
                anchor="w",
                wraplength=self._px(760),
                justify=tk.LEFT,
            ).pack(anchor="w", pady=(4, 0))

        footer = card(parent, bg=COLOR_CARD_BG)
        tk.Label(
            footer,
            text="すでに CISetup で設定したプロジェクトなら、種類を選ばずそのまま開けます。",
            font=font(12),
            fg=COLOR_DESC,
            bg=COLOR_CARD_BG,
            anchor="w",
            wraplength=self._px(860),
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 8))
        button(footer, "保存した設定を開く", self._open_saved, padx=16).pack(anchor="w")

    def _choose_mode(self, preset_name: str) -> None:
        self._preset_var.set(preset_name)
        self._apply_preset()
        self._show_form()

    def _show_chooser(self) -> None:
        self._form_frame.pack_forget()
        self._chooser_frame.pack(fill=tk.BOTH, expand=True)
        self._header_hint.configure(text=_CHOOSER_HINT)

    def _show_form(self) -> None:
        self._chooser_frame.pack_forget()
        self._form_frame.pack(fill=tk.BOTH, expand=True)
        self._header_hint.configure(text=_FORM_HINT)
