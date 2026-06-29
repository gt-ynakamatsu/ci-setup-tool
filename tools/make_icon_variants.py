"""キーワード向けのシンプルアイコン案を Pillow で生成する。

AI 生成と違い、形状・色を完全に制御できる。
    python tools/make_icon_variants.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "icon_candidates" / "code"
SIZE = 1024

# Jenkins 寄りオレンジ / Windows ブルー / 親しみやすい丸み
JENKINS_ORANGE = "#D96B2B"
WIN_BLUE = "#0078D4"
WIN_BLUE_LIGHT = "#E8F4FC"
GREEN = "#22C55E"
WHITE = "#FFFFFF"
SLATE = "#334155"


def _rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: str,
    outline: str | None = None,
    width: int = 0,
) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def _draw_pipeline(draw: ImageDraw.ImageDraw, cx: int, cy: int, scale: float) -> None:
    r = int(52 * scale)
    gap = int(130 * scale)
    xs = [cx - gap, cx, cx + gap]
    for i, x in enumerate(xs):
        color = GREEN if i == 2 else JENKINS_ORANGE
        draw.ellipse((x - r, cy - r, x + r, cy + r), fill=color)
        if i < 2:
            x2 = xs[i + 1]
            draw.rounded_rectangle(
                (x + r - 8, cy - int(18 * scale), x2 - r + 8, cy + int(18 * scale)),
                radius=int(12 * scale),
                fill=JENKINS_ORANGE,
            )
    # チェック
    x = xs[2]
    s = int(28 * scale)
    draw.line((x - s, cy, x - s // 3, cy + s), fill=WHITE, width=int(14 * scale))
    draw.line((x - s // 3, cy + s, x + s, cy - s // 2), fill=WHITE, width=int(14 * scale))


def variant_01_pipeline() -> Image.Image:
    """01: 丸パイプライン（CI + Jenkins オレンジ）"""
    im = Image.new("RGBA", (SIZE, SIZE), WIN_BLUE_LIGHT)
    draw = ImageDraw.Draw(im)
    _rounded_rect(draw, (64, 64, SIZE - 64, SIZE - 64), 180, WHITE)
    _draw_pipeline(draw, SIZE // 2, SIZE // 2 + 20, 1.0)
    return im


def variant_02_window_build() -> Image.Image:
    """02: Windows ウィンドウ + ビルドバー"""
    im = Image.new("RGBA", (SIZE, SIZE), WHITE)
    draw = ImageDraw.Draw(im)
    margin = 120
    _rounded_rect(draw, (margin, margin, SIZE - margin, SIZE - margin), 48, WHITE, SLATE, 6)
    bar_h = 100
    _rounded_rect(
        draw,
        (margin, margin, SIZE - margin, margin + bar_h),
        48,
        WIN_BLUE,
    )
    # タイトルバーの丸ボタン
    for i, color in enumerate(["#FF5F57", "#FFBD2E", "#28CA41"]):
        bx = margin + 36 + i * 44
        by = margin + 34
        draw.ellipse((bx, by, bx + 28, by + 28), fill=color)
    # ビルドプログレス
    py = SIZE // 2 + 40
    _rounded_rect(draw, (margin + 80, py, SIZE - margin - 80, py + 48), 24, "#E2E8F0")
    _rounded_rect(draw, (margin + 80, py, SIZE - margin - 220, py + 48), 24, JENKINS_ORANGE)
    # チェック丸
    cx, cy = SIZE - margin - 120, py + 24
    draw.ellipse((cx - 56, cy - 56, cx + 56, cy + 56), fill=GREEN)
    s = 22
    draw.line((cx - s, cy, cx - 4, cy + s), fill=WHITE, width=12)
    draw.line((cx - 4, cy + s, cx + s, cy - s), fill=WHITE, width=12)
    return im


def variant_03_blocks() -> Image.Image:
    """03: 積み上げブロック（build）"""
    im = Image.new("RGBA", (SIZE, SIZE), WHITE)
    draw = ImageDraw.Draw(im)
    colors = [WIN_BLUE, JENKINS_ORANGE, GREEN]
    bw, bh = 280, 120
    base_y = 620
    for i, color in enumerate(colors):
        x = SIZE // 2 - bw // 2 + (2 - i) * 20
        y = base_y - i * (bh - 20)
        _rounded_rect(draw, (x, y, x + bw, y + bh), 28, color)
    # 上に小さなチェックバッジ
    bx, by = SIZE // 2 + bw // 2 - 30, base_y - 2 * (bh - 20) - 50
    draw.ellipse((bx - 50, by - 50, bx + 50, by + 50), fill=GREEN)
    draw.line((bx - 18, by, bx - 4, by + 18), fill=WHITE, width=10)
    draw.line((bx - 4, by + 18, bx + 22, by - 14), fill=WHITE, width=10)
    return im


def variant_04_monogram() -> Image.Image:
    """04: CS モノグラム（CISetup / シンプル）"""
    im = Image.new("RGBA", (SIZE, SIZE), WIN_BLUE)
    draw = ImageDraw.Draw(im)
    # 白い円
    pad = 140
    draw.ellipse((pad, pad, SIZE - pad, SIZE - pad), fill=WHITE)
    try:
        font = ImageFont.truetype("segoeuib.ttf", 320)
    except OSError:
        try:
            font = ImageFont.truetype("arialbd.ttf", 320)
        except OSError:
            font = ImageFont.load_default()
    text = "CS"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((SIZE - tw) // 2 - bbox[0], (SIZE - th) // 2 - bbox[1] - 20),
        text,
        fill=WIN_BLUE,
        font=font,
    )
    # 下に小さなオレンジライン（パイプライン暗示）
    ly = SIZE - pad - 80
    _rounded_rect(draw, (pad + 100, ly, SIZE - pad - 100, ly + 16), 8, JENKINS_ORANGE)
    return im


def variant_05_hammer_pipeline() -> Image.Image:
    """05: ハンマー + 矢印 + チェック（build → 完了）"""
    im = Image.new("RGBA", (SIZE, SIZE), (248, 250, 252, 255))
    draw = ImageDraw.Draw(im)
    cx, cy = SIZE // 2, SIZE // 2
    # 左: 丸背景 + ハンマー（簡易幾何）
    lx = cx - 200
    draw.ellipse((lx - 90, cy - 90, lx + 90, cy + 90), fill=JENKINS_ORANGE)
    draw.rectangle((lx - 50, cy - 70, lx + 10, cy - 20), fill=WHITE)
    draw.rectangle((lx - 8, cy - 20, lx + 8, cy + 55), fill=WHITE)
    # 矢印
    draw.polygon(
        [(cx - 40, cy), (cx + 40, cy), (cx + 20, cy - 30), (cx + 80, cy), (cx + 20, cy + 30)],
        fill=SLATE,
    )
    # 右: チェック丸
    rx = cx + 200
    draw.ellipse((rx - 90, cy - 90, rx + 90, cy + 90), fill=GREEN)
    s = 36
    draw.line((rx - s, cy, rx - 8, cy + s), fill=WHITE, width=16)
    draw.line((rx - 8, cy + s, rx + s, cy - s // 2), fill=WHITE, width=16)
    return im


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    variants = [
        ("01_pipeline", variant_01_pipeline),
        ("02_window_build", variant_02_window_build),
        ("03_blocks", variant_03_blocks),
        ("04_monogram_cs", variant_04_monogram),
        ("05_hammer_flow", variant_05_hammer_pipeline),
    ]
    for name, fn in variants:
        path = OUT / f"icon_code_{name}.png"
        fn().save(path)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
