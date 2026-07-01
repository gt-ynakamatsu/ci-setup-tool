from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_exe_name_per_platform():
    from tools.rebuild_exe import exe_name

    assert exe_name("win32") == "CISetup.exe"
    assert exe_name("linux") == "CISetup"
    assert exe_name("darwin") == "CISetup"


def test_dist_exe_exists_and_is_fresh():
    """GUI/同梱物を直したあと exe が古いまま残っていないか確認する。"""
    from tools.rebuild_exe import EXE, exe_is_stale, newest_source_mtime

    if not EXE.is_file():
        pytest.fail(
            "dist\\CISetup.exe がありません。"
            " python tools/rebuild_exe.py を実行してください。"
        )

    if exe_is_stale():
        from datetime import datetime

        src_time = datetime.fromtimestamp(newest_source_mtime())
        exe_time = datetime.fromtimestamp(EXE.stat().st_mtime)
        pytest.fail(
            "dist\\CISetup.exe がソースより古いです。\n"
            f"  ソース最新: {src_time:%Y-%m-%d %H:%M:%S}\n"
            f"  exe:        {exe_time:%Y-%m-%d %H:%M:%S}\n"
            "  修正後は python tools/rebuild_exe.py を実行してください。"
        )
