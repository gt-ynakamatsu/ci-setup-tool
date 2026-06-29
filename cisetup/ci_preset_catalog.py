from __future__ import annotations

from dataclasses import dataclass

from .models import BuildConfig


@dataclass(frozen=True)
class CiPreset:
    id: str
    name: str
    description: str
    profile: str = "custom"
    build_command: str = ""
    lint_command: str = ""
    analyze_command: str = ""
    publish_command: str = ""
    test_command: str = ""
    artifact_glob: str = ""

    def apply_to(self, build: BuildConfig) -> None:
        build.preset = self.id
        build.profile = self.profile
        build.build_command = self.build_command
        build.lint_command = self.lint_command
        build.analyze_command = self.analyze_command
        build.publish_command = self.publish_command
        build.test_command = self.test_command
        build.artifact_glob = self.artifact_glob


PRESETS: list[CiPreset] = [
    CiPreset(
        id="dotnet",
        name=".NET デスクトップ / アプリ",
        description="dotnet build / format / publish を自動実行。テスト csproj 選択時のみ dotnet test。Roslyn 静的解析つき（既定）。",
        profile="dotnet",
    ),
    CiPreset(
        id="fpga-vivado",
        name="FPGA — AMD/Xilinx Vivado",
        description="build.tcl で合成〜ビットストリーム生成。.bit / レポートを成果物として保存します。",
        profile="custom",
        build_command="vivado -mode batch -source build.tcl",
        artifact_glob="**/*.bit;**/*.bin;**/*.ltx;**/*timing*.rpt;**/*utilization*.rpt",
    ),
    CiPreset(
        id="fpga-quartus",
        name="FPGA — Intel/Altera Quartus",
        description="quartus_sh のフローでコンパイル。.sof / .pof / レポートを保存します（PROJECT は実プロジェクト名に変更）。",
        profile="custom",
        build_command="quartus_sh --flow compile PROJECT",
        artifact_glob="output_files/*.sof;output_files/*.pof;output_files/*.rpt",
    ),
    CiPreset(
        id="cmake-cpp",
        name="C / C++（CMake）",
        description="CMake で構成・ビルド。バイナリを成果物として保存します。",
        profile="custom",
        build_command="cmake -S . -B build -DCMAKE_BUILD_TYPE=Release; cmake --build build --config Release",
        artifact_glob="build/**/*.exe;build/**/*.dll;build/**/*.bin",
    ),
    CiPreset(
        id="python",
        name="Python",
        description="依存インストール → Lint(ruff) → ビルド(wheel)。dist の成果物を保存します。",
        profile="custom",
        build_command="pip install -r requirements.txt",
        lint_command="ruff check .",
        publish_command="python -m build",
        artifact_glob="dist/*.whl;dist/*.tar.gz",
    ),
    CiPreset(
        id="custom-empty",
        name="カスタム（空・自分で入力）",
        description="ビルド種別をカスタムにして、各コマンドは自分で入力します。",
        profile="custom",
    ),
]


def find_preset(preset_id: str | None) -> CiPreset | None:
    if not preset_id:
        return None
    lowered = preset_id.lower()
    for preset in PRESETS:
        if preset.id.lower() == lowered:
            return preset
    return None
