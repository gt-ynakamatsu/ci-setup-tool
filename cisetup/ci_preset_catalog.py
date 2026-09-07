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
        description=(
            "エージェント上の Vivado で合成〜ビットストリームまで実行します。"
            "リポジトリ直下の build.tcl、または .xpr（標準ラン impl_1）が対象。"
            "Vivado を PATH か XILINX_VIVADO で見えるようにしてください。"
        ),
        profile="custom",
        artifact_glob="**/*.bit;**/*.bin;**/*.ltx;**/*timing*.rpt;**/*utilization*.rpt;**/*.dcp",
    ),
    CiPreset(
        id="fpga-quartus",
        name="FPGA — Intel/Altera Quartus",
        description=(
            "エージェント上の Quartus でコンパイルします。"
            "リポジトリ直下の .qpf を自動検出（複数あるときはビルドコマンドに -Project 名前）。"
            "quartus_sh を PATH か QUARTUS_ROOTDIR で見えるようにしてください。"
        ),
        profile="custom",
        artifact_glob="output_files/*.sof;output_files/*.pof;output_files/*.rpt;**/*.sof;**/*.pof",
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


def is_fpga_preset(preset_id: str | None) -> bool:
    return (preset_id or "").strip().lower().startswith("fpga-")


def find_preset(preset_id: str | None) -> CiPreset | None:
    if not preset_id:
        return None
    lowered = preset_id.lower()
    for preset in PRESETS:
        if preset.id.lower() == lowered:
            return preset
    return None
