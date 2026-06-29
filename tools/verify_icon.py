"""exe / assets のアイコン整合を確認する。

    python tools/verify_icon.py
"""
from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE = ROOT / "dist" / "CISetup.exe"
ICO = ROOT / "assets" / "icon.ico"
PNG = ROOT / "assets" / "icon.png"
SRC = ROOT / "assets" / "icon_source.png"


def _ico_frame_count(path: Path) -> list[tuple[int, int]]:
    data = path.read_bytes()
    count = struct.unpack_from("<H", data, 4)[0]
    sizes: list[tuple[int, int]] = []
    for i in range(count):
        off = 6 + i * 16
        w, h = data[off], data[off + 1]
        sizes.append((256 if w == 0 else w, 256 if h == 0 else h))
    return sizes


def _exe_icon_resources(exe: Path) -> list[bytes]:
    import pefile

    pe = pefile.PE(str(exe), fast_load=True)
    pe.parse_data_directories(
        directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]]
    )
    blobs: list[bytes] = []
    for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if entry.struct.Id != pefile.RESOURCE_TYPE["RT_ICON"]:
            continue
        for e in entry.directory.entries:
            for e2 in e.directory.entries:
                off = e2.data.struct.OffsetToData
                size = e2.data.struct.Size
                blobs.append(pe.get_data(off, size))
    return blobs


def _sha12(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def main() -> int:
    errors: list[str] = []

    for p in (EXE, ICO, PNG, SRC):
        if not p.is_file():
            errors.append(f"missing: {p}")

    if errors:
        for e in errors:
            print("FAIL", e)
        return 1

    if EXE.stat().st_mtime < ICO.stat().st_mtime:
        errors.append("exe is older than assets/icon.ico — rebuild required")
    if EXE.stat().st_mtime < SRC.stat().st_mtime:
        errors.append("exe is older than assets/icon_source.png — rebuild required")

    ico_sizes = _ico_frame_count(ICO)
    print("assets/icon.ico sizes:", ico_sizes)
    if ico_sizes != [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]:
        errors.append(f"unexpected ico sizes: {ico_sizes}")

    exe_icons = _exe_icon_resources(EXE)
    print("exe RT_ICON resources:", len(exe_icons))
    if len(exe_icons) != 7:
        errors.append(f"expected 7 RT_ICON in exe, got {len(exe_icons)}")

    # PyInstaller は各サイズを個別 RT_ICON として埋め込む（bytes は PNG/BMP 混在可）
    if exe_icons and max(len(b) for b in exe_icons) < 1000:
        errors.append("exe icon resources look too small")

    # 小アイコンは BMP 形式であること（PNG だと Explorer が汎用アイコンにフォールバックする）
    data = ICO.read_bytes()
    off16 = struct.unpack_from("<I", data, 6 + 12)[0]
    blob16 = data[off16 : off16 + struct.unpack_from("<I", data, 6 + 8)[0]]
    print("16px payload starts with:", blob16[:4])
    if blob16[:4] == b"\x89PNG":
        errors.append("16px icon is PNG — should be BMP for Explorer compatibility")
    elif blob16[:4] != b"\x28\x00\x00\x00":  # BITMAPINFOHEADER
        errors.append(f"16px icon unexpected format: {blob16[:4]!r}")

    has_group = False
    import pefile

    pe = pefile.PE(str(EXE), fast_load=True)
    pe.parse_data_directories(
        directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]]
    )
    for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if entry.struct.Id == pefile.RESOURCE_TYPE["RT_GROUP_ICON"]:
            has_group = True
    print("exe RT_GROUP_ICON:", "yes" if has_group else "no")
    if not has_group:
        errors.append("RT_GROUP_ICON missing in exe")

    print("sha256[:12] icon_source:", _sha12(SRC))
    print("sha256[:12] icon.png:    ", _sha12(PNG))
    print("sha256[:12] icon.ico:    ", _sha12(ICO))

    sys.path.insert(0, str(ROOT))
    from tools.rebuild_exe import exe_is_stale

    if exe_is_stale():
        errors.append("tools.rebuild_exe.exe_is_stale() == True")

    if errors:
        print("\nFAILED:")
        for e in errors:
            print(" -", e)
        return 1

    print("\nALL PASSED — icon is embedded and exe is fresh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
