"""FPGA プリセットのときだけ出す設定カード。

`.NET` 用の .sln / csproj の代わりに、合成対象（`.xpr` / `.qpf` / `build.tcl`）と
合成タイムアウトを指定する。ここでの入力は `ci-fpga.ps1` のオプションとして
ビルドコマンド欄へ書き出されるため、利用者がコマンドを手書きする必要はない。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ... import help_texts
from ...fpga_build import compose_fpga_build_command
from ...project_setup import find_fpga_projects
from ..layout import (
    COLOR_DESC,
    COLOR_PRESET_BG,
    COLOR_STEP,
    COLOR_TEXT,
    button,
    card,
    card_frame,
    font,
    hint_label,
    section_title,
)
from ..tooltip import help_icon

_WARN_COLOR = "#B45309"


class FpgaStepMixin:
    def _build_fpga_card(self, parent: tk.Misc) -> None:
        frame = card(parent, bg=COLOR_PRESET_BG, border=COLOR_STEP, border_width=2)
        section_title(frame, "FPGA ビルドの設定", COLOR_STEP).pack(anchor="w", pady=(0, 6))
        tk.Label(
            frame,
            text=(
                "合成対象を指定します。空欄ならエージェント上の ci-fpga.ps1 が"
                "リポジトリ内（サブフォルダ可）から探します。ビルドコマンドの手書きは不要です。"
            ),
            font=font(12),
            fg="#555555",
            bg=COLOR_PRESET_BG,
            anchor="w",
            wraplength=self._px(860),
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 10))

        tool_row = tk.Frame(frame, bg=COLOR_PRESET_BG)
        tool_row.pack(anchor="w", fill=tk.X, pady=(0, 6))
        self._fpga_tool_label = tk.Label(
            tool_row,
            text="使用ツール:",
            font=font(12, bold=True),
            fg=COLOR_TEXT,
            bg=COLOR_PRESET_BG,
            anchor="w",
        )
        self._fpga_tool_label.pack(side=tk.LEFT)
        help_icon(tool_row, help_texts.FPGA_TOOL, bg=COLOR_PRESET_BG).pack(side=tk.LEFT, padx=(4, 0))

        project_row = tk.Frame(frame, bg=COLOR_PRESET_BG)
        project_row.pack(fill=tk.X, pady=4)
        tk.Label(
            project_row,
            text="合成するプロジェクト",
            width=22,
            anchor="w",
            bg=COLOR_PRESET_BG,
            font=font(12),
        ).pack(side=tk.LEFT)
        help_icon(project_row, help_texts.FPGA_PROJECT, bg=COLOR_PRESET_BG).pack(
            side=tk.LEFT, padx=(2, 6)
        )
        self._fpga_project_combo = ttk.Combobox(
            project_row,
            textvariable=self._register_field("fpga.project"),
            font=font(12),
        )
        self._fpga_project_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)
        button(
            project_row,
            "候補を再検出",
            self._detect_fpga_projects,
            padx=10,
        ).pack(side=tk.LEFT, padx=(8, 0))
        hint_label(
            frame,
            "リポジトリルートからの相対パス（例: hw/quartus/blink.qpf、fpga/top.xpr）。"
            "候補が 1 つだけなら空欄のままで自動選択されます。",
            bg=COLOR_PRESET_BG,
        ).pack(anchor="w", padx=(150, 0))

        self._add_field(
            frame,
            "fpga.tcl",
            "ビルド Tcl（Vivado のみ）",
            help_texts.FPGA_TCL,
            label_width=22,
            browse="fpga-tcl",
        )
        hint_label(
            frame,
            "Vivado の合成スクリプト（例: fpga/build.tcl）。空欄なら build.tcl を自動で探し、"
            "無ければ .xpr の impl_1 を実行します。",
            bg=COLOR_PRESET_BG,
        ).pack(anchor="w", padx=(150, 0))

        timeout_row = tk.Frame(frame, bg=COLOR_PRESET_BG)
        timeout_row.pack(fill=tk.X, pady=(8, 0))
        self._fpga_timeout_row = timeout_row
        tk.Label(
            timeout_row,
            text="合成タイムアウト",
            width=22,
            anchor="w",
            bg=COLOR_PRESET_BG,
            font=font(12),
        ).pack(side=tk.LEFT)
        help_icon(timeout_row, help_texts.BUILD_TIMEOUT, bg=COLOR_PRESET_BG).pack(
            side=tk.LEFT, padx=(2, 6)
        )
        ttk.Entry(
            timeout_row,
            textvariable=self._register_field("jenkins.build_timeout_minutes"),
            width=8,
            font=font(12),
        ).pack(side=tk.LEFT)
        tk.Label(timeout_row, text="分", bg=COLOR_PRESET_BG, font=font(12)).pack(
            side=tk.LEFT, padx=(6, 0)
        )

        self._fpga_status = tk.Label(
            frame,
            text="",
            font=font(11),
            fg=COLOR_DESC,
            bg=COLOR_PRESET_BG,
            anchor="w",
            justify=tk.LEFT,
            wraplength=self._px(860),
        )
        self._fpga_status.pack(anchor="w", pady=(10, 0))
        self._mode_only(card_frame(frame), "fpga")

    def _fpga_candidates(self, tool: str, rescan: bool = False) -> list[str]:
        """合成対象の候補（ルート相対）。入力のたびに走査しないよう結果を覚える。"""
        if self._repository_root is None:
            return []
        key = (str(self._repository_root), tool)
        if rescan or key not in self._fpga_scan_cache:
            self._fpga_scan_cache[key] = find_fpga_projects(self._repository_root, tool)
        return self._fpga_scan_cache[key]

    def _detect_fpga_projects(self) -> None:
        """リポジトリ内の合成対象を探して候補一覧に入れる（1 件なら欄も埋める）。"""
        self._ensure_repo()
        tool = self._current_fpga_tool()
        found = self._fpga_candidates(tool, rescan=True)
        candidates = [p for p in found if not p.lower().endswith(".tcl")]
        self._fpga_project_combo.configure(values=candidates)
        if len(candidates) == 1:
            self._fields["fpga.project"].set(candidates[0])
        tcl = [p for p in found if p.lower().endswith(".tcl")]
        if tool == "Vivado" and len(tcl) == 1 and not self._fields["fpga.tcl"].get().strip():
            self._fields["fpga.tcl"].set(tcl[0])
        self._refresh_fpga_panel()
        self._set_status(
            f"FPGA プロジェクトの候補: {len(found)} 件" if found else "FPGA プロジェクトが見つかりませんでした。"
        )

    def _refresh_fpga_panel(self) -> None:
        """カードの表示（ツール名・検出状況・実行されるコマンド）を今の状態に合わせる。"""
        if not hasattr(self, "_fpga_status"):
            return
        tool = self._current_fpga_tool()
        if not tool:
            return
        self._fpga_tool_label.configure(text=f"使用ツール: {tool}（プリセットで切り替わります）")
        # Tcl は Vivado 専用のため、Quartus では触れないようにする。
        tcl_entry = self._field_widgets.get("fpga.tcl")
        if tcl_entry is not None:
            tcl_entry.configure(state="normal" if tool == "Vivado" else "disabled")
        text, color = self._fpga_status_text(tool)
        self._fpga_status.configure(text=text, fg=color)

    def _fpga_status_text(self, tool: str) -> tuple[str, str]:
        if self._fpga_raw_command:
            return (
                "ビルドコマンド欄に独自コマンドがあるため、ci-fpga.ps1 ではなくそちらを実行します:\n"
                f"  {self._fpga_raw_command}",
                _WARN_COLOR,
            )
        project = self._fields["fpga.project"].get().strip()
        tcl = self._fields["fpga.tcl"].get().strip() if tool == "Vivado" else ""
        command = compose_fpga_build_command(project, tcl)
        lines = [f"CI で実行: ci-fpga.ps1 -Tool {tool} {command}".rstrip()]

        if self._repository_root is None:
            return ("\n".join(lines + ["① でフォルダを選ぶと合成対象を検出します。"]), COLOR_DESC)

        found = self._fpga_candidates(tool)
        projects = [p for p in found if not p.lower().endswith(".tcl")]
        tcl_files = [p for p in found if p.lower().endswith(".tcl")]
        self._fpga_project_combo.configure(values=projects)
        if project or (tool == "Vivado" and tcl):
            return ("\n".join(lines), COLOR_DESC)

        auto = projects + (tcl_files if tool == "Vivado" else [])
        if not auto:
            wanted = "build.tcl / *.xpr" if tool == "Vivado" else "*.qpf"
            lines.append(f"このリポジトリに {wanted} が見つかりません（{tool} の合成対象を置いてください）。")
            return ("\n".join(lines), _WARN_COLOR)
        if len(auto) == 1:
            lines.append(f"自動選択: {auto[0]}")
            return ("\n".join(lines), COLOR_DESC)
        lines.append("候補が複数あります。1 つ選んでください: " + "、".join(auto))
        return ("\n".join(lines), _WARN_COLOR)
