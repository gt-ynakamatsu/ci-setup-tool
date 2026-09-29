from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .ci_preset_catalog import fpga_tool, is_fpga_preset, preset_mode
from .process_util import no_window_kwargs


@dataclass
class EnvironmentCheckResult:
    name: str
    guidance: str
    download_url: str = ""
    found: bool = False
    detail: str = ""


def _run(file_name: str, *args: str) -> tuple[bool, str, str]:
    try:
        proc = subprocess.run(
            [file_name, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            stdin=subprocess.DEVNULL,
            **no_window_kwargs(),
        )
        return proc.returncode == 0, proc.stdout or "", proc.stderr or ""
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False, "", ""


def _first_line(text: str) -> str:
    for line in text.replace("\r", "\n").split("\n"):
        if line.strip():
            return line.strip()
    return ""


def _check_git() -> EnvironmentCheckResult:
    is_windows = sys.platform == "win32"
    result = EnvironmentCheckResult(
        name="Git for Windows" if is_windows else "Git",
        guidance="社内 Git から clone / push するために必要です（設定 PC・エージェント PC の両方）。",
        download_url="https://git-scm.com/download/win" if is_windows else "https://git-scm.com/downloads",
    )
    ok, stdout, _ = _run("git", "--version")
    if ok:
        result.found = True
        result.detail = _first_line(stdout)
    else:
        result.detail = "見つかりません。"
    return result


def _check_dotnet() -> EnvironmentCheckResult:
    result = EnvironmentCheckResult(
        name=".NET SDK 8",
        guidance="アプリをビルドするために必要です（特にエージェント PC に必須）。",
        download_url="https://dotnet.microsoft.com/download/dotnet/8.0",
    )
    ok, stdout, _ = _run("dotnet", "--list-sdks")
    if not ok:
        result.detail = "見つかりません（dotnet コマンド未検出）。"
        return result

    sdks = [line.strip() for line in stdout.replace("\r", "\n").split("\n") if line.strip()]
    sdk8 = [line for line in sdks if line.startswith("8.")]
    if sdk8:
        result.found = True
        result.detail = "検出: " + ", ".join(s.split(" ")[0] for s in sdk8)
    elif sdks:
        result.detail = "8.x がありません。検出された SDK: " + ", ".join(s.split(" ")[0] for s in sdks)
    else:
        result.detail = "SDK が見つかりません。"
    return result


def _first_existing_file(candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _versioned_tool_paths(roots: list[str], relative: tuple[tuple[str, ...], ...]) -> list[Path]:
    """`C:\\Xilinx\\Vivado\\2023.2\\bin\\vivado.bat` のようなバージョン階層を新しい順に並べる。"""
    found: list[Path] = []
    for root in roots:
        if not root:
            continue
        base = Path(root)
        try:
            versions = sorted(
                (d for d in base.iterdir() if d.is_dir()),
                key=lambda d: d.name,
                reverse=True,
            )
        except OSError:
            continue
        for version in versions:
            found.extend(version.joinpath(*parts) for parts in relative)
    return found


def _check_vivado() -> EnvironmentCheckResult:
    """Vivado の実行ファイルを探す（起動は遅いため実行はしない）。"""
    result = EnvironmentCheckResult(
        name="AMD/Xilinx Vivado",
        guidance="FPGA 合成に必要です（エージェント PC に必須。設定 PC では未検出でも構いません）。"
        "PATH か XILINX_VIVADO から見えるようにしてください。",
        download_url="https://www.xilinx.com/support/download.html",
    )
    which = shutil.which("vivado")
    if which:
        result.found = True
        result.detail = f"検出: {which}"
        return result

    candidates: list[Path] = []
    for env_name in ("XILINX_VIVADO", "VIVADO_PATH"):
        base = os.environ.get(env_name, "").strip()
        if base:
            candidates += [Path(base) / "bin" / "vivado.bat", Path(base) / "bin" / "vivado"]
    candidates += _versioned_tool_paths(
        [r"C:\Xilinx\Vivado", r"D:\Xilinx\Vivado", os.path.join(os.environ.get("ProgramFiles", ""), "Xilinx", "Vivado")],
        (("bin", "vivado.bat"), ("bin", "vivado")),
    )
    hit = _first_existing_file(candidates)
    if hit:
        result.found = True
        result.detail = f"検出: {hit}"
    else:
        result.detail = "見つかりません（vivado コマンド・XILINX_VIVADO ともに未検出）。"
    return result


def _check_quartus() -> EnvironmentCheckResult:
    """Quartus の quartus_sh を探す（起動は遅いため実行はしない）。"""
    result = EnvironmentCheckResult(
        name="Intel/Altera Quartus",
        guidance="FPGA コンパイルに必要です（エージェント PC に必須。設定 PC では未検出でも構いません）。"
        "PATH か QUARTUS_ROOTDIR から見えるようにしてください。",
        download_url="https://www.intel.com/content/www/us/en/software-kit/",
    )
    which = shutil.which("quartus_sh")
    if which:
        result.found = True
        result.detail = f"検出: {which}"
        return result

    candidates: list[Path] = []
    for env_name in ("QUARTUS_ROOTDIR", "QSYS_ROOTDIR"):
        base = os.environ.get(env_name, "").strip()
        if base:
            candidates += [
                Path(base) / "quartus_sh.exe",
                Path(base) / "bin64" / "quartus_sh.exe",
                Path(base) / "bin" / "quartus_sh.exe",
                Path(base) / "quartus" / "bin64" / "quartus_sh.exe",
            ]
    candidates += _versioned_tool_paths(
        [r"C:\intelFPGA_lite", r"C:\intelFPGA", r"C:\altera", r"D:\intelFPGA_lite", r"D:\intelFPGA"],
        (("quartus", "bin64", "quartus_sh.exe"), ("quartus", "bin", "quartus_sh.exe")),
    )
    hit = _first_existing_file(candidates)
    if hit:
        result.found = True
        result.detail = f"検出: {hit}"
    else:
        result.detail = "見つかりません（quartus_sh コマンド・QUARTUS_ROOTDIR ともに未検出）。"
    return result


def _check_java() -> EnvironmentCheckResult:
    result = EnvironmentCheckResult(
        name="Java (JRE/JDK)",
        guidance="Jenkins サーバー（JDK 17+）/ エージェント（JRE 11+）の実行に必要です。",
        download_url="https://adoptium.net/",
    )
    # java -version はバージョンを標準エラーに出力する
    ok, stdout, stderr = _run("java", "-version")
    text = stderr if stderr.strip() else stdout
    if ok or text.strip():
        result.found = True
        result.detail = _first_line(text)
    else:
        result.detail = "見つかりません。"
    return result


def _check_jenkins_service() -> EnvironmentCheckResult:
    result = EnvironmentCheckResult(
        name="Jenkins サービス（この PC）",
        guidance="このPCがJenkinsサーバーでない場合は未検出で問題ありません。サーバー機で確認してください。",
        download_url="https://www.jenkins.io/download/",
    )
    if sys.platform == "win32":
        _, stdout, _ = _run("sc", "query", "Jenkins")
        if "RUNNING" in stdout.upper():
            result.found = True
            result.detail = "起動中 (RUNNING)"
        elif "STOPPED" in stdout.upper():
            result.found = True
            result.detail = "インストール済みだが停止中 (STOPPED) → サービスを開始してください。"
        else:
            result.detail = "このPCには見つかりません。"
        return result

    # Linux: systemd 管理下の jenkins サービスを確認（systemd 以外の環境では未検出扱い）。
    ok, stdout, _ = _run("systemctl", "is-active", "jenkins")
    state = stdout.strip().lower()
    if ok and state == "active":
        result.found = True
        result.detail = "起動中 (active)"
    elif state:
        result.found = True
        result.detail = f"インストール済みだが停止中 ({state}) → サービスを開始してください。"
    else:
        result.detail = "このPCには見つかりません。"
    return result


def scan(preset_id: str = "dotnet") -> list[EnvironmentCheckResult]:
    """選んでいるプリセットに合わせてチェック項目を組み替える。

    FPGA プリセットなら .NET SDK の代わりに Vivado / Quartus を確認する
    （FPGA の CI に .NET SDK は不要で、未検出と出ると混乱するため）。
    """
    checks = [_check_git()]
    if is_fpga_preset(preset_id):
        checks.append(_check_vivado() if fpga_tool(preset_id) == "Vivado" else _check_quartus())
    elif preset_mode(preset_id) == "dotnet":
        checks.append(_check_dotnet())
    checks += [_check_java(), _check_jenkins_service()]
    return checks
