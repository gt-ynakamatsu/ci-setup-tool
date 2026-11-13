from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass

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


_DOTNET_CHANNEL = re.compile(r"^\d+\.0$")
_DOTNET_VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def parse_dotnet_sdk_spec(spec: str | None) -> tuple[str, str, str]:
    """指定を ('channel'|'version', 表示用の値, メジャー) に分ける。空は 8.0。"""
    text = (spec or "").strip() or "8.0"
    if _DOTNET_CHANNEL.fullmatch(text):
        return "channel", text, text.split(".", 1)[0]
    if _DOTNET_VERSION.fullmatch(text):
        return "version", text, text.split(".", 1)[0]
    raise ValueError(
        ".NET SDK は 8.0 のようなチャネルか、8.0.428 のような版で指定してください: " + text
    )


def dotnet_download_url(spec: str | None) -> str:
    _kind, _text, major = parse_dotnet_sdk_spec(spec)
    return f"https://dotnet.microsoft.com/download/dotnet/{major}.0"


def _sdk_version_token(line: str) -> str:
    return line.strip().split(" ", 1)[0]


def _sdk_matches(version: str, kind: str, spec: str, major: str) -> bool:
    if kind == "version":
        return version == spec
    return version.startswith(major + ".")


def _check_dotnet(spec: str | None = None) -> EnvironmentCheckResult:
    kind, text, major = parse_dotnet_sdk_spec(spec)
    result = EnvironmentCheckResult(
        name=f".NET SDK {text}",
        guidance="アプリをビルドするために必要です（特にエージェント PC に必須）。",
        download_url=dotnet_download_url(text),
    )
    ok, stdout, _ = _run("dotnet", "--list-sdks")
    if not ok:
        result.detail = "見つかりません（dotnet コマンド未検出）。"
        return result

    sdks = [line.strip() for line in stdout.replace("\r", "\n").split("\n") if line.strip()]
    matched = [
        line
        for line in sdks
        if _sdk_matches(_sdk_version_token(line), kind, text, major)
    ]
    if matched:
        result.found = True
        result.detail = "検出: " + ", ".join(_sdk_version_token(line) for line in matched)
    elif sdks:
        found = ", ".join(_sdk_version_token(line) for line in sdks)
        result.detail = f"{text} がありません。検出された SDK: {found}"
    else:
        result.detail = "SDK が見つかりません。"
    return result


def _check_java() -> EnvironmentCheckResult:
    result = EnvironmentCheckResult(
        name="Java (JRE/JDK)",
        guidance="Jenkins サーバー（JDK 21/25）/ エージェント（JRE 11+）の実行に必要です。",
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


_SCRIPT_JENKINS_TASK = "CISetup Jenkins"


def _windows_jenkins_war_running() -> bool:
    """セットアップスクリプトは jenkins.war を java -jar で起動する。"""
    _, stdout, _ = _run(
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-CimInstance Win32_Process -Filter \"Name = 'java.exe'\" | "
        "Where-Object { $_.CommandLine -match 'jenkins\\.war' } | "
        "Select-Object -First 1 -ExpandProperty ProcessId",
    )
    return bool(stdout.strip())


def _windows_scheduled_task_exists(name: str) -> bool:
    ok, _, _ = _run("schtasks", "/Query", "/TN", name, "/FO", "LIST")
    return ok


def _check_jenkins_service() -> EnvironmentCheckResult:
    result = EnvironmentCheckResult(
        name="Jenkins（この PC）",
        guidance=(
            "Windows サービス名 Jenkins、またはセットアップスクリプトのタスク "
            "CISetup Jenkins と java -jar jenkins.war を確認します。"
            "設定用 PC では未検出で問題ありません。サーバー機で確認してください。"
        ),
        download_url="https://www.jenkins.io/download/",
    )
    if sys.platform == "win32":
        _, stdout, _ = _run("sc", "query", "Jenkins")
        upper = stdout.upper()
        if "RUNNING" in upper:
            result.found = True
            result.detail = "起動中 (RUNNING)"
        elif "STOPPED" in upper:
            result.found = True
            result.detail = "インストール済みだが停止中 (STOPPED) → サービスを開始してください。"
        elif _windows_jenkins_war_running():
            result.found = True
            result.detail = "起動中（java -jar jenkins.war）"
        elif _windows_scheduled_task_exists(_SCRIPT_JENKINS_TASK):
            result.found = True
            result.detail = (
                "タスク CISetup Jenkins は登録済みだが、プロセスは停止しています。"
                "start-jenkins.bat を確認してください。"
            )
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


def scan(dotnet_sdk: str | None = None) -> list[EnvironmentCheckResult]:
    return [_check_git(), _check_dotnet(dotnet_sdk), _check_java(), _check_jenkins_service()]
