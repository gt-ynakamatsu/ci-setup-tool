"""dist/CISetup(.exe) を PyInstaller で再ビルドする。

PyInstaller は実行中の OS 向けにネイティブバイナリを生成する（クロスコンパイル不可）。
Windows では `CISetup.exe`、Linux/macOS では拡張子なしの `CISetup` が出力される。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "cisetup.spec"


def exe_name(platform: str = sys.platform) -> str:
    """PyInstaller が出力する実行ファイル名（OS 依存）。"""
    return "CISetup.exe" if platform == "win32" else "CISetup"


EXE = ROOT / "dist" / exe_name()

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


def exe_is_stale(*, margin_seconds: float = 1.0) -> bool:
    if not EXE.is_file():
        return True
    return EXE.stat().st_mtime + margin_seconds < newest_source_mtime()


def rebuild(*, clean: bool = True) -> Path:
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
    if not EXE.is_file():
        raise FileNotFoundError(f"ビルド後に exe が見つかりません: {EXE}")
    return EXE


def main() -> int:
    try:
        path = rebuild()
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"[エラー] exe ビルドに失敗しました: {exc}", file=sys.stderr)
        return 1
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"完了: {path} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
