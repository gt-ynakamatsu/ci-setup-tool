#!/usr/bin/env python3
"""CISetup 設定 GUI — 正式版エントリポイント。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cisetup import paths
from cisetup.gui import run_app
from cisetup.project_setup import deploy_ci_files, has_solution_file


def _program_name() -> str:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).name
    return "configure.py"


def _attach_console_for_cli(argv: list[str]) -> None:
    """windowed exe でも --bootstrap / --help がターミナルで動くようにする（Windows のみ）。

    Linux の PyInstaller windowed ビルドには Windows の GUI/コンソール
    サブシステム分離がなく、frozen 実行ファイルも通常どおり呼び出し元の
    ターミナルに出力されるため、この対応は不要（かつ ctypes.windll が
    存在せず AttributeError になる）。
    """
    if sys.platform != "win32":
        return
    if not getattr(sys, "frozen", False):
        return
    if not any(arg in argv for arg in ("--bootstrap", "--help", "-h")):
        return

    import ctypes

    if ctypes.windll.kernel32.GetConsoleWindow():
        return

    ctypes.windll.kernel32.AllocConsole()
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if stream and hasattr(stream, "close"):
            try:
                stream.close()
            except OSError:
                pass
    sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")  # noqa: SIM115
    sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")  # noqa: SIM115


def _build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog=_program_name(),
        description="CISetup CI setup GUI and template deployment",
    )


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--open",
        metavar="folder",
        help="指定フォルダを開いて GUI を起動",
    )
    parser.add_argument(
        "--bootstrap",
        metavar="folder",
        help="CI ファイルをフォルダへ自動配置（GUI なし）",
    )


def _resolve_folder(value: str) -> Path:
    folder = Path(value).expanduser().resolve()
    if not folder.is_dir():
        print(f"エラー: フォルダが見つかりません: {folder}", file=sys.stderr)
        raise SystemExit(1)
    return folder


def _run_bootstrap(folder: Path) -> None:
    folder = paths.normalize_project_root(folder)
    deploy_ci_files(folder, overwrite=True)
    if not has_solution_file(folder):
        print(
            "CI ファイルを配置しました。\n\n警告: *.sln が見つかりません。",
            file=sys.stderr,
        )
        raise SystemExit(0)
    print(f"CI ファイルを配置しました: {folder / 'cisetup'}")


def main(argv: list[str] | None = None) -> None:
    args_list = list(sys.argv[1:] if argv is None else argv)
    _attach_console_for_cli(args_list)

    parser = _build_parser()
    _add_arguments(parser)
    args = parser.parse_args(args_list)

    if args.bootstrap:
        _run_bootstrap(_resolve_folder(args.bootstrap))
        return

    initial = _resolve_folder(args.open) if args.open else None
    run_app(str(initial) if initial else None)


if __name__ == "__main__":
    main()
