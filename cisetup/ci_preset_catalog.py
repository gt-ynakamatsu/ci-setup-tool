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
    # FPGA プリセットの合成ツール（ci-fpga.ps1 の -Tool）。それ以外は空。
    tool: str = ""

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
            "リポジトリ内（サブフォルダ可）の build.tcl、または .xpr（標準ラン impl_1）が対象。"
            "Vivado を PATH か XILINX_VIVADO で見えるようにしてください。"
        ),
        profile="custom",
        artifact_glob="**/*.bit;**/*.bin;**/*.ltx;**/*timing*.rpt;**/*utilization*.rpt;**/*.dcp",
        tool="Vivado",
    ),
    CiPreset(
        id="fpga-quartus",
        name="FPGA — Intel/Altera Quartus",
        description=(
            "エージェント上の Quartus でコンパイルします。"
            "リポジトリ内（サブフォルダ可）の .qpf を自動検出（複数あるときはビルドコマンドに -Project 相対パス）。"
            "quartus_sh を PATH か QUARTUS_ROOTDIR で見えるようにしてください。"
        ),
        profile="custom",
        artifact_glob="output_files/*.sof;output_files/*.pof;output_files/*.rpt;**/*.sof;**/*.pof",
        tool="Quartus",
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


def find_preset_by_name(name: str | None) -> CiPreset | None:
    """GUI のコンボボックス表示名からプリセットを引く。"""
    label = (name or "").strip()
    for preset in PRESETS:
        if preset.name == label:
            return preset
    return None


def fpga_tool(preset_id: str | None) -> str:
    """FPGA プリセットの合成ツール名（Vivado / Quartus）。FPGA 以外は空。"""
    preset = find_preset(preset_id)
    return preset.tool if preset and is_fpga_preset(preset.id) else ""


def preset_mode(preset_id: str | None) -> str:
    """プリセットの種別。GUI の画面切り替え（表示文言・入力欄）に使う。

    "dotnet" … dotnet build / publish を自動実行するプリセット
    "fpga"   … ci-fpga.ps1 で Vivado / Quartus を実行するプリセット
    "custom" … コマンドを自分で書くプリセット（C/C++・Python・空）
    """
    if is_fpga_preset(preset_id):
        return "fpga"
    preset = find_preset(preset_id)
    if preset is None:
        return "dotnet"
    return "dotnet" if preset.profile.lower() != "custom" else "custom"
