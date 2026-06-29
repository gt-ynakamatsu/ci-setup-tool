"""アプリアイコン生成スクリプト。

assets/icon_source.png（詳細版）から icon.png / マルチサイズ icon.ico を作る。
16〜32px は文字が潰れるため、専用の簡略デザインを描画する。

    python tools/make_icon.py
"""
from __future__ import annotations

import io
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "icon_source.png"
OUT_PNG = ROOT / "assets" / "icon.png"
OUT_ICO = ROOT / "assets" / "icon.ico"
PREVIEW_DIR = ROOT / "assets" / "icon_sizes"

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
SMALL_MAX = 32  # このサイズ以下は簡略アイコン

JO = "#D96B2B"
BLOCK_BASE = "#3F3F46"
BLOCK_BUILD = "#1D4ED8"
BLOCK_TEST = "#3B82F6"
GREEN = "#22C55E"
SKIN = "#FCD9B6"
WHITE = "#FFFFFF"
BLACK = "#1E293B"

FLOOD_THRESHOLD = 60


def _rr(draw: ImageDraw.ImageDraw, xy, radius: int, fill: str) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def _make_background_transparent(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    rgb = im.convert("RGB")
    sentinel = (255, 0, 255)
    w, h = im.size
    for corner in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        ImageDraw.floodfill(rgb, corner, sentinel, thresh=FLOOD_THRESHOLD)
    marked = rgb.getdata()
    original = im.getdata()
    out = [
        (r, g, b, 0) if (mr, mg, mb) == sentinel else (r, g, b, a)
        for (mr, mg, mb), (r, g, b, a) in zip(marked, original)
    ]
    im.putdata(out)
    return im


def _build_detailed_master() -> Image.Image:
    im = _make_background_transparent(Image.open(SRC))
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    w, h = im.size
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - w) // 2, (side - h) // 2))
    return canvas.resize((1024, 1024), Image.LANCZOS)


def _tiny_check(draw: ImageDraw.ImageDraw, cx: int, cy: int, arm: int, color: str, width: int) -> None:
    draw.line((cx - arm, cy, cx - arm // 3, cy + arm), fill=color, width=width)
    draw.line((cx - arm // 3, cy + arm, cx + arm, cy - arm // 2), fill=color, width=width)


def render_small_icon(size: int) -> Image.Image:
    """16〜32px 向け: オレンジ地＋おじさん顔＋CI ブロック（文字なし）。"""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    pad = max(0, size // 20)
    rad = max(1, size // 5)
    _rr(draw, (pad, pad, size - pad - 1, size - pad - 1), rad, JO)

    # 右: ブロック積み（4段・太め）
    bx1 = size * 50 // 100
    bx2 = size - pad - 1
    n = 4
    gap = max(1, size // 32)
    bh = max(2, (size * 58 // 100 - gap * (n - 1)) // n)
    y0 = size * 18 // 100
    colors = [BLOCK_BASE, BLOCK_BUILD, BLOCK_TEST, GREEN]
    for i, color in enumerate(colors):
        y1 = y0 + i * (bh + gap)
        y2 = min(size - pad - 1, y1 + bh)
        _rr(draw, (bx1, y1, bx2, y2), max(1, size // 24), color)
        if i == 3 and size >= 16:
            _tiny_check(
                draw,
                (bx1 + bx2) // 2,
                (y1 + y2) // 2,
                max(2, size // 9),
                WHITE,
                max(1, size // 12),
            )

    # 左: おじさん（ハゲ丸顔）
    cx = size * 22 // 100
    cy = size * 48 // 100
    face_r = max(2, size * 18 // 100)
    draw.ellipse((cx - face_r, cy - face_r, cx + face_r, cy + face_r), fill=SKIN)
    if size >= 16:
        eye_y = cy - max(1, size // 32)
        eye_dx = max(1, size // 14)
        ew = max(1, size // 18)
        for ex in (cx - eye_dx, cx + eye_dx):
            draw.line((ex - ew, eye_y, ex + ew, eye_y), fill=BLACK, width=max(1, size // 20))
        mouth_y = cy + max(1, size // 14)
        draw.arc(
            (cx - face_r, mouth_y - face_r // 2, cx + face_r, mouth_y + face_r),
            10,
            170,
            fill=BLACK,
            width=max(1, size // 20),
        )
    if size >= 24:
        body_w = max(3, size * 24 // 100)
        body_h = max(3, size * 22 // 100)
        _rr(
            draw,
            (cx - body_w // 2, cy + face_r, cx + body_w // 2, cy + face_r + body_h),
            max(1, size // 14),
            "#111827",
        )

    return im


def _resize_detailed(master: Image.Image, size: int) -> Image.Image:
    im = master.resize((size, size), Image.LANCZOS)
    if size <= 64:
        im = im.filter(ImageFilter.SHARPEN)
    return im


def _frame_for_size(master: Image.Image, size: int) -> Image.Image:
    if size <= SMALL_MAX:
        return render_small_icon(size)
    return _resize_detailed(master, size)


def _flatten_opaque(im: Image.Image, bg: str = JO) -> Image.Image:
    """ICO 用に不透過 RGBA にする（角の透明をオレンジで埋める）。"""
    flat = Image.new("RGBA", im.size, bg)
    flat.paste(im, mask=im.split()[3])
    return flat


def _rgba_to_ico_dib(im: Image.Image) -> bytes:
    """RGBA 画像を Windows ICO 用 32bit DIB（XOR+AND）に変換する。"""
    im = im.convert("RGBA")
    w, h = im.size
    row = w * 4
    raw = im.tobytes("raw", "BGRA")
    xor = b"".join(raw[y * row : (y + 1) * row] for y in range(h - 1, -1, -1))

    mask_stride = ((w + 31) // 32) * 4
    and_rows = bytearray()
    for y in range(h - 1, -1, -1):
        row_bits = bytearray(mask_stride)
        for x in range(w):
            if im.getpixel((x, y))[3] < 128:
                row_bits[x // 8] |= 1 << (7 - (x % 8))
        and_rows.extend(row_bits)

    header = struct.pack(
        "<IIIHHIIIIII",
        40,
        w,
        h * 2,
        1,
        32,
        0,
        len(xor),
        0,
        0,
        0,
        0,
    )
    return header + xor + bytes(and_rows)


def _encode_ico_image(im: Image.Image) -> tuple[bytes, int, int]:
    im = _flatten_opaque(im)
    return _rgba_to_ico_dib(im), im.width, im.height


def _save_ico_windows(frames: list[Image.Image], path: Path) -> None:
    """サイズごとに異なる画像を BMP ベース ICO として書き出す（Explorer 小アイコン互換）。"""
    encoded = [_encode_ico_image(im) for im in frames]
    count = len(encoded)
    header = struct.pack("<HHH", 0, 1, count)
    entries = bytearray()
    offset = 6 + count * 16
    for blob, w, h in encoded:
        bw = 0 if w == 256 else w
        bh = 0 if h == 256 else h
        entries.extend(struct.pack("<BBBBHHII", bw, bh, 0, 0, 1, 32, len(blob), offset))
        offset += len(blob)

    with path.open("wb") as f:
        f.write(header)
        f.write(entries)
        for blob, _, _ in encoded:
            f.write(blob)


def main() -> None:
    if not SRC.is_file():
        raise SystemExit(f"元画像が見つかりません: {SRC}")

    master = _build_detailed_master()
    master.save(OUT_PNG)

    frames = [_frame_for_size(master, size) for size in ICO_SIZES]
    _save_ico_windows(frames, OUT_ICO)

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    for size, frame in zip(ICO_SIZES, frames):
        frame.save(PREVIEW_DIR / f"icon_{size}.png")

    print(f"wrote {OUT_PNG}")
    print(f"wrote {OUT_ICO} ({len(ICO_SIZES)} sizes, small<= {SMALL_MAX}px use simplified art)")
    print(f"wrote previews under {PREVIEW_DIR}")


if __name__ == "__main__":
    main()
