"""ブリッジ系アイコン（Windows × CI 接続）をコード生成。

Jenkins マスコット・執事・人物は使わない。
下段はパイプライン／ビルド等の抽象シンボルのみ。

    python tools/make_icon_bridge.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "icon_candidates" / "bridge"
SIZE = 1024
PAD = 48

WIN = "#0078D4"
JO = "#D96B2B"
WHITE = "#FFFFFF"
GREEN = "#22C55E"
SLATE = "#475569"


def rr(draw, xy, radius, fill, outline=None, width=0):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def check(draw, cx, cy, size, color=JO, w=14):
    s = size
    draw.line((cx - s, cy, cx - s // 3, cy + s), fill=color, width=w)
    draw.line((cx - s // 3, cy + s, cx + s, cy - s // 2), fill=color, width=w)


def rounded_icon_canvas(bg=WHITE):
    im = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    rr(draw, (PAD, PAD, SIZE - PAD, SIZE - PAD), 200, bg)
    return im, draw, PAD


def fill_halves(draw, inner_pad: int, split_y: int):
    """上=Windows ブルー、下=CI オレンジの半分背景（角丸内）"""
    x1, y1 = PAD + inner_pad, PAD + inner_pad
    x2, y2 = SIZE - PAD - inner_pad, SIZE - PAD - inner_pad
    mid = split_y
    rr(draw, (x1, y1, x2, mid), 80, WIN)
    # 下半分は下側角丸を維持
    rr(draw, (x1, mid, x2, y2), 80, JO)


def draw_four_panes(draw, cx, cy, pane, gap, color=WHITE):
    """Windows 風4ペイン（ロゴそのものではなく抽象）"""
    o = pane + gap // 2
    for row in range(2):
        for col in range(2):
            x = cx - o + col * (pane + gap)
            y = cy - o + row * (pane + gap)
            rr(draw, (x, y, x + pane, y + pane), 16, color)


def draw_bridge(draw, y_deck: int, check_on_bridge: bool = True):
    """白いアーチ橋＋中央チェック"""
    x1, x2 = PAD + 80, SIZE - PAD - 80
    deck_h = 36
    # 橋面
    rr(draw, (x1, y_deck - deck_h // 2, x2, y_deck + deck_h // 2), 18, WHITE)
    # 欄干
    post_w = 14
    for px in (x1 + 40, x2 - 40, SIZE // 2):
        draw.rectangle((px - post_w // 2, y_deck - 70, px + post_w // 2, y_deck + deck_h // 2), fill=WHITE)
    draw.line((x1 + 20, y_deck - 55, x2 - 20, y_deck - 55), fill=WHITE, width=8)
    # アーチ（簡易）
    cx = SIZE // 2
    draw.arc((cx - 120, y_deck - 130, cx + 120, y_deck + 10), 200, 340, fill=WHITE, width=10)
    if check_on_bridge:
        r = 52
        draw.ellipse((cx - r, y_deck - r - 10, cx + r, y_deck + r - 10), fill=WHITE)
        check(draw, cx, y_deck - 10, 28, JO, 12)


def pipeline_bottom(draw, cy: int):
    pipeline_h(draw, SIZE // 2, cy, 0.75, [WHITE, WHITE, GREEN], last_check=True)


def pipeline_h(draw, cx, cy, scale, node_colors, last_check=False):
    r = int(40 * scale)
    gap = int(100 * scale)
    n = len(node_colors)
    xs = [cx + (i - (n - 1) / 2) * gap for i in range(n)]
    for i, x in enumerate(xs):
        draw.ellipse((x - r, cy - r, x + r, cy + r), fill=node_colors[i])
        if last_check and i == n - 1:
            check(draw, x, cy, int(18 * scale), WHITE, int(10 * scale))
        if i < n - 1:
            x2 = xs[i + 1]
            rr(draw, (x + r - 5, cy - int(12 * scale), x2 - r + 5, cy + int(12 * scale)), 8, WHITE)


def hammer_bottom(draw, cx, cy):
    draw.ellipse((cx - 90, cy - 90, cx + 90, cy + 90), fill=WHITE)
    draw.rectangle((cx - 45, cy - 55, cx + 5, cy - 15), fill=JO)
    draw.rectangle((cx - 6, cy - 15, cx + 6, cy + 50), fill=JO)


def gear_bottom(draw, cx, cy, teeth=8, outer=80, inner=50):
    draw.ellipse((cx - outer, cy - outer, cx + outer, cy + outer), fill=WHITE)
    draw.ellipse((cx - inner, cy - inner, cx + inner, cy + inner), fill=JO)
    for i in range(teeth):
        ang = 2 * math.pi * i / teeth
        dx, dy = math.cos(ang) * (outer - 10), math.sin(ang) * (outer - 10)
        draw.ellipse((cx + dx - 14, cy + dy - 14, cx + dx + 14, cy + dy + 14), fill=WHITE)


def progress_bottom(draw, y):
    x1, x2 = PAD + 120, SIZE - PAD - 120
    rr(draw, (x1, y, x2, y + 40), 20, (255, 255, 255, 180))
    rr(draw, (x1, y, x1 + (x2 - x1) * 7 // 10, y + 40), 20, WHITE)


def save(name: str, im: Image.Image) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    im.save(OUT / f"{name}.png")


def bridge_01_pipeline():
    im, draw, _ = rounded_icon_canvas(WHITE)
    split = SIZE // 2 - 20
    fill_halves(draw, 16, split)
    draw_four_panes(draw, SIZE // 2, split // 2 + 40, 90, 20)
    draw_bridge(draw, split)
    pipeline_bottom(draw, split + (SIZE - PAD - split) // 2 + 20)
    save("bridge_01_pipeline", im)


def bridge_02_hammer():
    im, draw, _ = rounded_icon_canvas(WHITE)
    split = SIZE // 2 - 20
    fill_halves(draw, 16, split)
    draw_four_panes(draw, SIZE // 2, split // 2 + 40, 90, 20)
    draw_bridge(draw, split)
    hammer_bottom(draw, SIZE // 2, split + (SIZE - PAD - split) // 2 + 20)
    save("bridge_02_hammer", im)


def bridge_03_gear():
    im, draw, _ = rounded_icon_canvas(WHITE)
    split = SIZE // 2 - 20
    fill_halves(draw, 16, split)
    draw_four_panes(draw, SIZE // 2, split // 2 + 40, 90, 20)
    draw_bridge(draw, split)
    gear_bottom(draw, SIZE // 2, split + (SIZE - PAD - split) // 2 + 20)
    save("bridge_03_gear", im)


def bridge_04_progress():
    im, draw, _ = rounded_icon_canvas(WHITE)
    split = SIZE // 2 - 20
    fill_halves(draw, 16, split)
    draw_four_panes(draw, SIZE // 2, split // 2 + 40, 90, 20)
    draw_bridge(draw, split)
    progress_bottom(draw, split + 130)
    draw.ellipse((SIZE - PAD - 200, split + 110, SIZE - PAD - 80, split + 230), fill=GREEN)
    check(draw, SIZE - PAD - 140, split + 170, 24)
    save("bridge_04_progress", im)


def bridge_05_minimal():
    """橋＋チェックのみ。下は小さな3ドット"""
    im, draw, _ = rounded_icon_canvas(WHITE)
    split = SIZE // 2
    fill_halves(draw, 16, split)
    draw_four_panes(draw, SIZE // 2, 260, 70, 16)
    draw_bridge(draw, split - 10)
    for i, x in enumerate([SIZE // 2 - 80, SIZE // 2, SIZE // 2 + 80]):
        c = GREEN if i == 2 else WHITE
        draw.ellipse((x - 28, 700, x + 28, 756), fill=c)
    save("bridge_05_minimal", im)


def bridge_06_soft_shadow():
    im, draw, _ = rounded_icon_canvas((245, 247, 250, 255))
    split = SIZE // 2 - 20
    fill_halves(draw, 24, split)
    draw_four_panes(draw, SIZE // 2, split // 2 + 30, 85, 18)
    draw_bridge(draw, split)
    pipeline_bottom(draw, split + 155)
  # subtle inner highlight
    save("bridge_06_soft", im)


def bridge_07_no_panes_hammer():
    """上はウィンドウ枠のみ（4ペインなし）"""
    im, draw, _ = rounded_icon_canvas(WHITE)
    split = SIZE // 2 - 20
    fill_halves(draw, 16, split)
    m = 180
    rr(draw, (m, 120, SIZE - m, split - 50), 28, WHITE, WHITE, 6)
    rr(draw, (m, 120, SIZE - m, 200), 28, "#005A9E")
    draw_bridge(draw, split)
    hammer_bottom(draw, SIZE // 2, split + 160)
    save("bridge_07_window_frame", im)


def bridge_08_check_green():
    """チェックを緑に（成功強調）"""
    im, draw, _ = rounded_icon_canvas(WHITE)
    split = SIZE // 2 - 20
    fill_halves(draw, 16, split)
    draw_four_panes(draw, SIZE // 2, split // 2 + 40, 90, 20)
    draw_bridge(draw, split, check_on_bridge=True)
    # 上書きで緑チェック
    cx, y_deck = SIZE // 2, split
    r = 52
    draw.ellipse((cx - r, y_deck - r - 10, cx + r, y_deck + r - 10), fill=GREEN)
    check(draw, cx, y_deck - 10, 28, WHITE, 12)
    pipeline_bottom(draw, split + 155)
    save("bridge_08_green_check", im)


VARIANTS = [
    bridge_01_pipeline,
    bridge_02_hammer,
    bridge_03_gear,
    bridge_04_progress,
    bridge_05_minimal,
    bridge_06_soft_shadow,
    bridge_07_no_panes_hammer,
    bridge_08_check_green,
]


def main() -> None:
    for fn in VARIANTS:
        fn()
    print(f"wrote {len(VARIANTS)} bridge icons to {OUT}")


if __name__ == "__main__":
    main()
