# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — CISetup.exe（単一ファイル・GUI + CLI）

import sys
from pathlib import Path

root = Path(SPECPATH)
sys.path.insert(0, str(root))
from cisetup.version import write_pyinstaller_version_file

_version_file = write_pyinstaller_version_file(root / "build" / "file_version_info.txt")

a = Analysis(
    [str(root / "configure.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / "bundled_templates"), "bundled_templates"),
        (str(root / "assets"), "assets"),
    ],
    hiddenimports=["tkinter"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CISetup",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(_version_file),
    icon=str(root / "assets" / "icon.ico"),
)
