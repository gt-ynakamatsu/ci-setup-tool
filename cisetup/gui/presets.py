from __future__ import annotations

from tkinter import messagebox

from ..ci_preset_catalog import CiPreset, find_preset_by_name, is_fpga_preset
from ..project_setup import apply_auto_detection, apply_fpga_auto_detection
from .util import safe_int

# FPGA 合成は既定の 30 分では足りないため、プリセット適用時に引き上げる。
_FPGA_BUILD_TIMEOUT_MINUTES = 180

# 画面のコマンド欄 → CiPreset の属性（手入力かプリセット由来かの判定に使う）。
_COMMAND_FIELDS = {
    "build.build_command": "build_command",
    "build.lint_command": "lint_command",
    "build.analyze_command": "analyze_command",
    "build.publish_command": "publish_command",
    "build.test_command": "test_command",
    "build.artifact_glob": "artifact_glob",
}

_PROFILE_LABELS = {
    "dotnet": ".NET（dotnet build / format / publish を自動実行）",
    "custom": "カスタムコマンド（FPGA・C/C++・Python など任意）",
}


class PresetMixin:
    def _on_preset_selected(self) -> None:
        """選んだ時点で適用する。

        以前は「適用」を押すまで画面が .NET のままで、プリセットを変えたのに
        何も切り替わらないように見えていた。選択＝適用にして食い違いを無くす。
        """
        if find_preset_by_name(self._preset_var.get()) is None:
            return
        self._apply_preset()

    def _apply_preset(self) -> None:
        preset = find_preset_by_name(self._preset_var.get())
        if not preset:
            messagebox.showwarning("CISetup", "先にプリセットを選んでください。")
            return
        if self._has_custom_commands() and not messagebox.askyesno(
            "プリセットの適用",
            "現在入力されているビルドコマンド等を、選んだプリセットの内容で上書きします。よろしいですか？",
        ):
            self._restore_applied_preset()
            return

        self._profile_var.set(_PROFILE_LABELS["custom" if preset.profile == "custom" else "dotnet"])
        self._on_profile_changed()
        self._fields["build.build_command"].set(preset.build_command)
        self._fields["build.lint_command"].set(preset.lint_command)
        self._fields["build.analyze_command"].set(preset.analyze_command)
        self._fields["build.publish_command"].set(preset.publish_command)
        self._fields["build.test_command"].set(preset.test_command)
        self._fields["build.artifact_glob"].set(preset.artifact_glob)
        # FPGA の入力欄はプリセットごとに対象ツールが変わるため引き継がない。
        self._fields["fpga.project"].set("")
        self._fields["fpga.tcl"].set("")
        self._fpga_raw_command = ""

        self._applied_preset_name = preset.name
        self._preset_desc.configure(text=preset.description)
        extra = self._raise_fpga_timeout(preset)
        self._refresh_mode_ui()
        extra += self._redetect_for_preset(preset)
        self._set_status(f"プリセット「{preset.name}」を適用しました。{extra}".strip())

    def _has_custom_commands(self) -> bool:
        """適用済みプリセットの内容から書き換えられたコマンド欄があるか。

        プリセットが入れた値（FPGA の成果物 glob など）で確認を出すと、
        種類を選び直すたびに無意味なダイアログが出てしまうため区別する。
        """
        applied = find_preset_by_name(self._applied_preset_name)
        for key, attribute in _COMMAND_FIELDS.items():
            current = self._fields[key].get().strip()
            baseline = getattr(applied, attribute).strip() if applied else ""
            if current and current != baseline:
                return True
        return False

    def _restore_applied_preset(self) -> None:
        """上書きを断られたときは、選択を適用済みのプリセットへ戻す。"""
        self._preset_var.set(self._applied_preset_name)
        preset = find_preset_by_name(self._applied_preset_name)
        self._preset_desc.configure(text=preset.description if preset else "")
        self._set_status("プリセットの適用を取り消しました。")

    def _raise_fpga_timeout(self, preset: CiPreset) -> str:
        if not is_fpga_preset(preset.id):
            return ""
        timeout_field = self._fields.get("jenkins.build_timeout_minutes")
        # 利用者が広げている場合は尊重し、既定のままのときだけ引き上げる。
        if timeout_field is None or safe_int(timeout_field.get(), 30) > 30:
            return ""
        timeout_field.set(str(_FPGA_BUILD_TIMEOUT_MINUTES))
        return f" ビルドタイムアウトを {_FPGA_BUILD_TIMEOUT_MINUTES} 分にしました（FPGA 合成向け）。"

    def _redetect_for_preset(self, preset: CiPreset) -> str:
        """プリセットに合わせて自動入力をやり直す。

        FPGA では .sln / csproj の残骸を消してプロジェクト名を FPGA 側から決め、
        .NET へ戻したときは .sln から再検出して埋め直す。
        """
        if self._repository_root is None:
            return ""
        self._form_to_config()
        if is_fpga_preset(preset.id):
            self._config = apply_fpga_auto_detection(
                self._repository_root, self._config, preset.tool
            )
        elif preset.profile == "dotnet":
            self._config = apply_auto_detection(self._repository_root, self._config)
        else:
            return ""
        self._config_to_form()
        self._update_preview()
        return f" プロジェクト名などを {preset.tool or '.NET'} 向けに再検出しました。"
