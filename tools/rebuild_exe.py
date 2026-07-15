"""dist/CISetup(.exe) を PyInstaller で再ビルドする。

PyInstaller は実行中の OS 向けにネイティブバイナリを生成する（クロスコンパイル不可）。
Windows では `CISetup.exe`、Linux/macOS では拡張子なしの `CISetup` が出力される。

配布成果物の正本は Windows 向け `dist/CISetup.exe`（利用者は Python 不要の自己完結
onefile。追加の pip 依存は無く、埋め込まれるのは Python 本体 + tkinter/Tcl/Tk +
同梱テンプレート程度で十数 MB）。

Linux 上でその `.exe` を作る場合は Wine + Windows Python が必要:

    python tools/setup_wine_python.py   # 初回のみ
    python tools/rebuild_exe.py --windows
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "cisetup.spec"

# 社内配布の正本（Windows GUI・Python 不要）
DIST_EXE = ROOT / "dist" / "CISetup.exe"

# Wine 経由 Windows ビルド用（tools/setup_wine_python.py と揃える）
DEFAULT_WINEPREFIX = Path.home() / ".wine-cisetup"
WINE_PYTHON_WIN = r"C:\Python312\python.exe"


def exe_name(platform: str = sys.platform) -> str:
    """PyInstaller が出力する実行ファイル名（OS 依存）。"""
    return "CISetup.exe" if platform == "win32" else "CISetup"


def native_exe(platform: str = sys.platform) -> Path:
    return ROOT / "dist" / exe_name(platform)


# 鮮度チェック・検証スクリプト向け（配布正本）
EXE = DIST_EXE

# exe に影響するソース（鮮度チェックと同期）
EXE_SOURCE_GLOBS = (
    "cisetup/**/*.py",
    "configure.py",
    "cisetup.spec",
    "bundled_templates/**/*",
)


def exe_source_paths() -> list[Path]:
    paths: list[Path] = []
    for pattern in EXE_SOURCE_GLOBS:
        paths.extend(ROOT.glob(pattern))
    return [p for p in paths if p.is_file()]


def newest_source_mtime() -> float:
    paths = exe_source_paths()
    if not paths:
        return 0.0
    return max(p.stat().st_mtime for p in paths)


def exe_is_stale(*, margin_seconds: float = 1.0, path: Path | None = None) -> bool:
    target = path or EXE
    if not target.is_file():
        return True
    return target.stat().st_mtime + margin_seconds < newest_source_mtime()


def wine_prefix() -> Path:
    return Path(os.environ.get("WINEPREFIX", str(DEFAULT_WINEPREFIX)))


def wine_python_host_path() -> Path:
    return wine_prefix() / "drive_c" / "Python312" / "python.exe"


def wine_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("WINEPREFIX", str(DEFAULT_WINEPREFIX))
    env.setdefault("WINEARCH", "win64")
    env.setdefault("WINEDLLOVERRIDES", "mscoree,mshtml=")
    # wine の冗長ログを抑える
    env.setdefault("WINEDEBUG", "-all")
    return env


def _require_wine_python() -> None:
    if not shutil.which("wine"):
        raise RuntimeError(
            "Windows .exe を Linux でビルドするには wine が必要です。"
            " (例: sudo apt install wine wine64 wine32:i386)"
        )
    if not wine_python_host_path().is_file():
        raise RuntimeError(
            f"Wine 上の Windows Python が見つかりません: {wine_python_host_path()}\n"
            "  先に実行してください: python tools/setup_wine_python.py"
        )


def rebuild_native(*, clean: bool = True) -> Path:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "pyinstaller", "--quiet"],
        cwd=ROOT,
        check=True,
    )
    cmd = [sys.executable, "-m", "PyInstaller", str(SPEC)]
    if clean:
        cmd.append("--clean")
    cmd.append("--noconfirm")
    subprocess.run(cmd, cwd=ROOT, check=True)
    path = native_exe()
    if not path.is_file():
        raise FileNotFoundError(f"ビルド後に exe が見つかりません: {path}")
    return path


def rebuild_windows(*, clean: bool = True) -> Path:
    """Wine 上の Windows Python で `dist/CISetup.exe` を生成する。"""
    _require_wine_python()
    env = wine_env()
    subprocess.run(
        ["wine", WINE_PYTHON_WIN, "-m", "pip", "install", "pyinstaller", "--quiet"],
        cwd=ROOT,
        check=True,
        env=env,
    )
    cmd = ["wine", WINE_PYTHON_WIN, "-m", "PyInstaller", str(SPEC)]
    if clean:
        cmd.append("--clean")
    cmd.append("--noconfirm")
    subprocess.run(cmd, cwd=ROOT, check=True, env=env)
    if not DIST_EXE.is_file():
        raise FileNotFoundError(f"ビルド後に exe が見つかりません: {DIST_EXE}")
    return DIST_EXE


def rebuild(*, clean: bool = True, windows: bool | None = None) -> Path:
    """再ビルドする。

    windows:
      True  … 常に Windows .exe（非 Windows では Wine 経由）
      False … 常にホスト OS 向けネイティブ
      None  … Windows ホストなら .exe、それ以外はネイティブ
              （Linux で WINEPREFIX に Python がある場合は .exe を優先）
    """
    if windows is None:
        if sys.platform == "win32":
            windows = True
        else:
            windows = wine_python_host_path().is_file()

    if windows:
        if sys.platform == "win32":
            return rebuild_native(clean=clean)
        return rebuild_windows(clean=clean)
    return rebuild_native(clean=clean)


def main() -> int:
    parser = argparse.ArgumentParser(description="CISetup を PyInstaller で再ビルドする")
    parser.add_argument(
        "--windows",
        action="store_true",
        help="Windows 向け CISetup.exe を生成（Linux では Wine + setup_wine_python.py が必要）",
    )
    parser.add_argument(
        "--native",
        action="store_true",
        help="ホスト OS 向けバイナリのみ生成（Linux なら拡張子なし CISetup）",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="PyInstaller の --clean を付けない",
    )
    args = parser.parse_args()
    if args.windows and args.native:
        print("[エラー] --windows と --native は同時に指定できません", file=sys.stderr)
        return 2

    windows: bool | None
    if args.windows:
        windows = True
    elif args.native:
        windows = False
    else:
        windows = None

    try:
        path = rebuild(clean=not args.no_clean, windows=windows)
    except (subprocess.CalledProcessError, OSError, RuntimeError) as exc:
        print(f"[エラー] exe ビルドに失敗しました: {exc}", file=sys.stderr)
        return 1
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"完了: {path} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
