from __future__ import annotations

from tkinter import messagebox

from ..ci_preset_catalog import PRESETS


class PresetMixin:
    def _on_preset_selected(self) -> None:
        preset = next((p for p in PRESETS if p.name == self._preset_var.get()), None)
        if preset:
            self._preset_desc.configure(text=preset.description)

    def _apply_preset(self) -> None:
        preset = next((p for p in PRESETS if p.name == self._preset_var.get()), None)
        if not preset:
            messagebox.showwarning("CISetup", "先にプリセットを選んでください。")
            return
        has_custom = any(
            self._fields[k].get().strip()
            for k in (
                "build.build_command",
                "build.lint_command",
                "build.analyze_command",
                "build.publish_command",
                "build.test_command",
                "build.artifact_glob",
            )
        )
        if has_custom and not messagebox.askyesno(
            "プリセットの適用",
            "現在入力されているビルドコマンド等を、選んだプリセットの内容で上書きします。よろしいですか？",
        ):
            return
        self._profile_var.set(
            "カスタムコマンド（FPGA・C/C++・Python など任意）"
            if preset.profile == "custom"
            else ".NET（dotnet build / format / publish を自動実行）"
        )
        self._on_profile_changed()
        self._fields["build.build_command"].set(preset.build_command)
        self._fields["build.lint_command"].set(preset.lint_command)
        self._fields["build.analyze_command"].set(preset.analyze_command)
        self._fields["build.publish_command"].set(preset.publish_command)
        self._fields["build.test_command"].set(preset.test_command)
        self._fields["build.artifact_glob"].set(preset.artifact_glob)
        self._set_status(f"プリセット「{preset.name}」を適用しました。")
