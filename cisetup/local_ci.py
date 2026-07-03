"""ローカル（Jenkins / git を介さない）での CI ビルド & テスト実行。

配置済みの `CISetup/scripts/ci-build.ps1` → `ci-test.ps1` を、リポジトリの
作業コピーに対してそのまま PowerShell で実行する。fetch / pull / push といった
git 操作は一切行わないため、push 前に手元のコードを検証する用途に使う。
各スクリプトは自前で `ci-config.ps1` を読み込み `Set-Location $ci.Root` するため、
ここでは cwd をリポジトリルートにして起動するだけでよい。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable

from . import paths
from .process_util import no_window_kwargs


class LocalCIError(RuntimeError):
    """ローカル CI 実行でスクリプトが見つからない / 失敗したときに送出する。"""


def _powershell_candidates() -> list[str]:
    """利用する PowerShell の実行ファイル候補（優先順）。

    Jenkins / Windows 環境では `powershell`（Windows PowerShell 5.1）を優先して
    挙動を合わせる。見つからなければ `pwsh`（PowerShell 7+）にフォールバックする。
    """
    if sys.platform == "win32":
        return ["powershell", "pwsh"]
    return ["pwsh", "powershell"]


def _run_script(
    root: Path,
    script: Path,
    configuration: str,
    on_output: Callable[[str], None] | None,
    label: str,
) -> None:
    if not script.is_file():
        raise LocalCIError(
            f"{label}用スクリプトが見つかりません:\n  {script}\n\n"
            "先に「設定を保存」を実行して CI スクリプトを配置してください。"
        )

    tail = [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-Configuration",
        configuration,
    ]

    proc = None
    last_exc: OSError | None = None
    for exe in _powershell_candidates():
        try:
            proc = subprocess.Popen(
                [exe, *tail],
                cwd=str(root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                **no_window_kwargs(),
            )
            break
        except FileNotFoundError as exc:
            last_exc = exc
    if proc is None:
        raise LocalCIError(
            "PowerShell を起動できません（powershell / pwsh が見つかりません）。"
        ) from last_exc

    if proc.stdout is not None:
        for line in proc.stdout:
            if on_output is not None:
                on_output(line.rstrip("\n"))
    proc.wait()

    if proc.returncode != 0:
        raise LocalCIError(
            f"{label}に失敗しました（終了コード {proc.returncode}）。"
            "上のログを確認してください。"
        )


def run_local_ci(
    root: Path,
    configuration: str = "Release",
    on_output: Callable[[str], None] | None = None,
) -> None:
    """ローカルでビルド→テストを順に実行する（git 操作なし）。

    `CISetup/scripts/ci-build.ps1` を実行し、成功した場合のみ `ci-test.ps1` を実行する。
    いずれかが見つからない / 失敗した場合は :class:`LocalCIError` を送出する。

    :param root: リポジトリルート（`CISetup/` がある階層）。
    :param configuration: ビルド構成（既定 ``Release``）。各スクリプトの ``-Configuration``。
    :param on_output: 標準出力/標準エラーを 1 行ずつ受け取るコールバック（任意）。
    """
    scripts = paths.scripts_dir(root)
    configuration = (configuration or "Release").strip() or "Release"

    if on_output is not None:
        on_output("==> ローカルビルドを開始します（git 操作なし）")
    _run_script(root, scripts / "ci-build.ps1", configuration, on_output, "ビルド")

    if on_output is not None:
        on_output("")
        on_output("==> ローカルテストを開始します（git 操作なし）")
    _run_script(root, scripts / "ci-test.ps1", configuration, on_output, "テスト")

    if on_output is not None:
        on_output("")
        on_output("==> ローカルビルド＆テストが完了しました。")
