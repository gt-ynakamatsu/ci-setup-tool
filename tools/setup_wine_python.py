"""Linux 上で Windows 向け CISetup.exe をビルドするための Wine + Python を用意する。

想定環境: Ubuntu など（wine / wine64 / wine32:i386 が利用可能であること）。

    sudo dpkg --add-architecture i386
    sudo apt-get update
    sudo apt-get install -y wine wine64 wine32:i386
    python tools/setup_wine_python.py
    python tools/rebuild_exe.py --windows
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

DEFAULT_WINEPREFIX = Path.home() / ".wine-cisetup"
PYTHON_VERSION = "3.12.8"
INSTALLER_URL = (
    f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-amd64.exe"
)
WINE_PYTHON_HOST = DEFAULT_WINEPREFIX / "drive_c" / "Python312" / "python.exe"
TARGET_DIR = r"C:\Python312"


def wine_env() -> dict[str, str]:
    env = os.environ.copy()
    env["WINEPREFIX"] = str(DEFAULT_WINEPREFIX)
    env["WINEARCH"] = "win64"
    env.setdefault("WINEDLLOVERRIDES", "mscoree,mshtml=")
    env.setdefault("WINEDEBUG", "-all")
    return env


def main() -> int:
    if sys.platform == "win32":
        print("Windows ホストでは不要です。python tools/rebuild_exe.py をそのまま実行してください。")
        return 0

    if not shutil.which("wine"):
        print(
            "[エラー] wine が見つかりません。"
            " sudo apt install wine wine64 wine32:i386 を実行してください。",
            file=sys.stderr,
        )
        return 1

    if WINE_PYTHON_HOST.is_file():
        print(f"既にセットアップ済み: {WINE_PYTHON_HOST}")
        return 0

    DEFAULT_WINEPREFIX.mkdir(parents=True, exist_ok=True)
    env = wine_env()

    print("==> Wine プレフィックス初期化")
    subprocess.run(["wineboot", "--init"], env=env, check=False)

    with tempfile.TemporaryDirectory(prefix="cisetup-wine-") as tmp:
        installer = Path(tmp) / "python-installer.exe"
        print(f"==> ダウンロード: {INSTALLER_URL}")
        urllib.request.urlretrieve(INSTALLER_URL, installer)

        print(f"==> Windows Python {PYTHON_VERSION} をインストール ({TARGET_DIR})")
        result = subprocess.run(
            [
                "wine",
                str(installer),
                "/quiet",
                "InstallAllUsers=1",
                "PrependPath=1",
                "Include_tcltk=1",
                "Include_pip=1",
                "Include_test=0",
                f"TargetDir={TARGET_DIR}",
            ],
            env=env,
            check=False,
        )
        if result.returncode != 0:
            print(
                f"[エラー] Python インストーラが失敗しました (exit={result.returncode})",
                file=sys.stderr,
            )
            return 1

    if not WINE_PYTHON_HOST.is_file():
        print(f"[エラー] インストール後も python.exe がありません: {WINE_PYTHON_HOST}", file=sys.stderr)
        return 1

    print("==> tkinter 確認")
    check = subprocess.run(
        ["wine", r"C:\Python312\python.exe", "-c", "import tkinter; print(tkinter.TkVersion)"],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if check.returncode != 0:
        print(check.stdout)
        print(check.stderr, file=sys.stderr)
        print("[エラー] tkinter を import できませんでした", file=sys.stderr)
        return 1
    print(f"    Tk {check.stdout.strip()}")
    print("完了。次: python tools/rebuild_exe.py --windows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
