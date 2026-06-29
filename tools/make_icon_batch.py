"""CISetup 向けアイコン案を大量生成する（Pillow / 完全制御）。

    python tools/make_icon_batch.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "icon_candidates" / "batch"
SIZE = 1024

JO = "#D96B2B"  # Jenkins orange
JO_DARK = "#B45309"
JO_LIGHT = "#FDBA74"
WIN = "#0078D4"
WIN_LIGHT = "#E8F4FC"
WIN_DARK = "#005A9E"
GREEN = "#22C55E"
GREEN_DARK = "#16A34A"
WHITE = "#FFFFFF"
SLATE = "#334155"
DARK = "#1E293B"
CREAM = "#FFFBF5"


def rr(draw, xy, radius, fill, outline=None, width=0):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def check(draw, cx, cy, size, color=WHITE, w=14):
    s = size
    draw.line((cx - s, cy, cx - s // 3, cy + s), fill=color, width=w)
    draw.line((cx - s // 3, cy + s, cx + s, cy - s // 2), fill=color, width=w)


def pipeline_h(draw, cx, cy, scale, node_colors, last_check=False):
    r = int(48 * scale)
    gap = int(120 * scale)
    n = len(node_colors)
    xs = [cx + (i - (n - 1) / 2) * gap for i in range(n)]
    for i, x in enumerate(xs):
        c = node_colors[i]
        draw.ellipse((x - r, cy - r, x + r, cy + r), fill=c)
        if last_check and i == n - 1:
            check(draw, x, cy, int(22 * scale), WHITE, int(12 * scale))
        if i < n - 1:
            x2 = xs[i + 1]
            rr(draw, (x + r - 6, cy - int(14 * scale), x2 - r + 6, cy + int(14 * scale)), 10, JO)


def save(name: str, im: Image.Image) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{name}.png"
    im.save(p)


def v06_vertical_pipeline():
    im = Image.new("RGBA", (SIZE, SIZE), WIN_LIGHT)
    draw = ImageDraw.Draw(im)
    rr(draw, (100, 100, SIZE - 100, SIZE - 100), 160, WHITE)
    cx, y, gap = SIZE // 2, 280, 160
    colors = [JO, WIN, GREEN]
    for i, c in enumerate(colors):
        yy = y + i * gap
        draw.ellipse((cx - 70, yy - 70, cx + 70, yy + 70), fill=c)
        if i == 2:
            check(draw, cx, yy, 28)
        if i < 2:
            rr(draw, (cx - 16, yy + 70, cx + 16, yy + gap - 70), 8, JO)
    save("06_vertical_pipeline", im)


def v07_orange_tile():
    im = Image.new("RGBA", (SIZE, SIZE), JO)
    draw = ImageDraw.Draw(im)
    pipeline_h(draw, SIZE // 2, SIZE // 2, 1.1, [WHITE, WHITE, GREEN], last_check=True)
    save("07_orange_tile_pipeline", im)


def v08_blue_tile():
    im = Image.new("RGBA", (SIZE, SIZE), WIN)
    draw = ImageDraw.Draw(im)
    rr(draw, (180, 380, SIZE - 180, 520), 40, WHITE)
    rr(draw, (220, 420, 520, 480), 20, JO)
    draw.ellipse((SIZE - 320, 360, SIZE - 160, 520), fill=GREEN)
    check(draw, SIZE - 240, 440, 32)
    save("08_blue_tile_progress", im)


def v09_four_pane():
    im = Image.new("RGBA", (SIZE, SIZE), WHITE)
    draw = ImageDraw.Draw(im)
    m, g, s = 140, 16, 200
    colors = [WIN_LIGHT, JO_LIGHT, WIN_LIGHT, GREEN]
    idx = 0
    for row in range(2):
        for col in range(2):
            x1 = m + col * (s + g)
            y1 = m + row * (s + g)
            rr(draw, (x1, y1, x1 + s, y1 + s), 36, colors[idx])
            if idx == 3:
                check(draw, x1 + s // 2, y1 + s // 2, 40, WHITE, 16)
            idx += 1
    save("09_four_pane_check", im)


def v10_dark_friendly():
    im = Image.new("RGBA", (SIZE, SIZE), DARK)
    draw = ImageDraw.Draw(im)
    pipeline_h(draw, SIZE // 2, SIZE // 2, 1.0, [JO, JO_LIGHT, GREEN], last_check=True)
    save("10_dark_pipeline", im)


def v11_hammer_circle():
    im = Image.new("RGBA", (SIZE, SIZE), CREAM)
    draw = ImageDraw.Draw(im)
    cx, cy = SIZE // 2, SIZE // 2
    draw.ellipse((cx - 200, cy - 200, cx + 200, cy + 200), fill=JO)
    draw.rectangle((cx - 80, cy - 120, cx - 10, cy - 40), fill=WHITE)
    draw.rectangle((cx - 12, cy - 40, cx + 12, cy + 100), fill=WHITE)
    save("11_hammer_circle", im)


def v12_wrench_circle():
    im = Image.new("RGBA", (SIZE, SIZE), WIN_LIGHT)
    draw = ImageDraw.Draw(im)
    cx, cy = SIZE // 2, SIZE // 2
    draw.ellipse((cx - 200, cy - 200, cx + 200, cy + 200), fill=WIN)
    # 簡易レンチ
    draw.rectangle((cx - 100, cy - 20, cx + 100, cy + 20), fill=WHITE)
    draw.ellipse((cx + 60, cy - 50, cx + 140, cy + 50), fill=WHITE)
    draw.ellipse((cx + 78, cy - 32, cx + 122, cy + 32), fill=WIN)
    save("12_wrench_circle", im)


def v13_ring_progress():
    im = Image.new("RGBA", (SIZE, SIZE), WHITE)
    draw = ImageDraw.Draw(im)
    cx, cy, ro, ri = SIZE // 2, SIZE // 2, 280, 200
    draw.ellipse((cx - ro, cy - ro, cx + ro, cy + ro), fill=JO_LIGHT)
    draw.ellipse((cx - ri, cy - ri, cx + ri, cy + ri), fill=WHITE)
    draw.pieslice((cx - ro, cy - ro, cx + ro, cy + ro), -90, 180, fill=JO)
    check(draw, cx, cy, 50, GREEN, 18)
    save("13_ring_progress", im)


def v14_stacked_cards():
    im = Image.new("RGBA", (SIZE, SIZE), (241, 245, 249, 255))
    draw = ImageDraw.Draw(im)
    for i, (c, off) in enumerate([(WHITE, 0), (WIN_LIGHT, 24), (WHITE, 48)]):
        y = 260 + off
        rr(draw, (200 + off, y, SIZE - 200 + off, y + 180), 24, c, SLATE if i == 2 else None, 3 if i == 2 else 0)
    check(draw, SIZE // 2 + 48, 400, 36, GREEN, 14)
    save("14_stacked_cards", im)


def v15_play_build():
    im = Image.new("RGBA", (SIZE, SIZE), JO)
    draw = ImageDraw.Draw(im)
    cx, cy = SIZE // 2, SIZE // 2
    draw.polygon([(cx - 60, cy - 100), (cx - 60, cy + 100), (cx + 100, cy)], fill=WHITE)
    save("15_play_orange", im)


def v16_ci_letters():
    im = Image.new("RGBA", (SIZE, SIZE), WIN)
    draw = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("segoeuib.ttf", 280)
    except OSError:
        font = ImageFont.load_default()
    for text, color, dx in [("CI", WHITE, 0)]:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((SIZE - tw) // 2 - bbox[0] + dx, (SIZE - th) // 2 - bbox[1]), text, fill=color, font=font)
    rr(draw, (280, SIZE - 280, SIZE - 280, SIZE - 220), 12, JO)
    save("16_ci_text", im)


def v17_squircle_gradient():
    im = Image.new("RGBA", (SIZE, SIZE), WHITE)
    draw = ImageDraw.Draw(im)
    for y in range(SIZE):
        t = y / SIZE
        r = int(232 + t * 20)
        g = int(244 - t * 30)
        b = int(252 - t * 40)
        draw.line([(0, y), (SIZE, y)], fill=(r, g, b, 255))
    rr(draw, (120, 120, SIZE - 120, SIZE - 120), 200, WIN)
    pipeline_h(draw, SIZE // 2, SIZE // 2, 0.85, [WHITE, WHITE, GREEN], last_check=True)
    save("17_squircle_blue", im)


def v18_badge_j():
    im = Image.new("RGBA", (SIZE, SIZE), WHITE)
    draw = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("segoeuib.ttf", 360)
    except OSError:
        font = ImageFont.load_default()
    draw.ellipse((180, 180, SIZE - 180, SIZE - 180), fill=JO)
    bbox = draw.textbbox((0, 0), "J", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((SIZE - tw) // 2 - bbox[0], (SIZE - th) // 2 - bbox[1] - 30), "J", fill=WHITE, font=font)
    save("18_j_badge", im)


def v19_toolbox():
    im = Image.new("RGBA", (SIZE, SIZE), WIN_LIGHT)
    draw = ImageDraw.Draw(im)
    rr(draw, (220, 340, SIZE - 220, 680), 32, WIN)
    rr(draw, (380, 280, SIZE - 380, 380), 20, WIN_DARK)
    draw.rectangle((460, 420, 540, 600), fill=JO)
    draw.ellipse((580, 440, 660, 580), fill=WHITE)
    check(draw, 720, 500, 30, GREEN, 12)
    save("19_toolbox", im)


def v20_chain():
    im = Image.new("RGBA", (SIZE, SIZE), DARK)
    draw = ImageDraw.Draw(im)
    for i, c in enumerate([JO, WIN, GREEN]):
        x = 220 + i * 200
        draw.ellipse((x, 412, x + 200, 612), outline=c, width=28)
    save("20_chain_links", im)


def v21_sunrise_check():
    im = Image.new("RGBA", (SIZE, SIZE), (254, 243, 199, 255))
    draw = ImageDraw.Draw(im)
    draw.pieslice((120, 500, SIZE - 120, SIZE + 200), 180, 360, fill=JO)
    draw.ellipse((SIZE // 2 - 120, 280, SIZE // 2 + 120, 520), fill=JO_LIGHT)
    check(draw, SIZE // 2, 400, 45, JO, 16)
    save("21_sunrise", im)


def v22_window_simple():
    im = Image.new("RGBA", (SIZE, SIZE), WHITE)
    draw = ImageDraw.Draw(im)
    m = 160
    rr(draw, (m, m, SIZE - m, SIZE - m), 40, WIN_LIGHT, WIN, 8)
    rr(draw, (m, m, SIZE - m, m + 90), 40, WIN)
    pipeline_h(draw, SIZE // 2, SIZE // 2 + 60, 0.9, [JO, WIN, GREEN], last_check=True)
    save("22_window_pipeline", im)


def v23_dots_only():
    im = Image.new("RGBA", (SIZE, SIZE), JO)
    draw = ImageDraw.Draw(im)
    for i, c in enumerate([WHITE, WHITE, GREEN]):
        draw.ellipse((280 + i * 180, 440, 400 + i * 180, 560), fill=c)
        if i == 2:
            check(draw, 340 + i * 180, 500, 22, WHITE, 10)
    save("23_minimal_dots", im)


def v24_split():
    im = Image.new("RGBA", (SIZE, SIZE), WHITE)
    draw = ImageDraw.Draw(im)
    draw.polygon([(0, 0), (SIZE, 0), (0, SIZE)], fill=WIN)
    draw.polygon([(SIZE, 0), (SIZE, SIZE), (0, SIZE)], fill=JO)
    draw.ellipse((SIZE // 2 - 140, SIZE // 2 - 140, SIZE // 2 + 140, SIZE // 2 + 140), fill=WHITE)
    check(draw, SIZE // 2, SIZE // 2, 50, GREEN, 18)
    save("24_split_diagonal", im)


def v25_rounded_app():
    im = Image.new("RGBA", (SIZE, SIZE), (248, 250, 252, 255))
    draw = ImageDraw.Draw(im)
    rr(draw, (140, 140, SIZE - 140, SIZE - 140), 220, WIN)
    rr(draw, (240, 340, SIZE - 240, 440), 28, WHITE)
    rr(draw, (240, 500, SIZE - 400, 600), 28, JO)
    draw.ellipse((SIZE - 360, 480, SIZE - 240, 600), fill=GREEN)
    check(draw, SIZE - 300, 540, 26)
    save("25_fluent_tile", im)


VARIANTS = [
    v06_vertical_pipeline,
    v07_orange_tile,
    v08_blue_tile,
    v09_four_pane,
    v10_dark_friendly,
    v11_hammer_circle,
    v12_wrench_circle,
    v13_ring_progress,
    v14_stacked_cards,
    v15_play_build,
    v16_ci_letters,
    v17_squircle_gradient,
    v18_badge_j,
    v19_toolbox,
    v20_chain,
    v21_sunrise_check,
    v22_window_simple,
    v23_dots_only,
    v24_split,
    v25_rounded_app,
]


def main() -> None:
    for fn in VARIANTS:
        fn()
    print(f"wrote {len(VARIANTS)} icons to {OUT}")


if __name__ == "__main__":
    main()
