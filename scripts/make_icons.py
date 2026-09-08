#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Иконка ПЛЁНКА native: плёнка с янтарной рамкой на тёмном фоне."""
from PIL import Image, ImageDraw
import os

BG = (13, 11, 9, 255)        # #0d0b09
BG2 = (21, 17, 9, 255)       # #151109
LINE = (60, 51, 32, 255)     # #3c3320
ACC = (232, 163, 61, 255)    # #e8a33d
TXT = (235, 225, 205, 255)   # #ebe1cd

SIZES = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}

BASE = "/home/z/my-project/plenka-native/app/src/main/res"

def draw_icon(px: int) -> Image.Image:
    S = 512  # мастер-масштаб, потом ресайз
    im = Image.new("RGBA", (S, S), BG)
    d = ImageDraw.Draw(im)

    # рамка-плёнка: скруглённый прямоугольник
    m = 64
    d.rounded_rectangle([m, m + 60, S - m, S - m - 60], radius=72, outline=ACC, width=22)

    # перфорация сверху и снизу
    hole_w, hole_h = 40, 26
    step = 86
    n = 4
    x0 = m + 58
    row_y_top = m + 60 + 34
    row_y_bot = S - m - 60 - 34 - hole_h + 2
    for i in range(n):
        x = x0 + i * step
        d.rounded_rectangle([x, row_y_top, x + hole_w, row_y_top + hole_h], radius=10, fill=BG2, outline=LINE, width=4)
        d.rounded_rectangle([x, row_y_bot, x + hole_w, row_y_bot + hole_h], radius=10, fill=BG2, outline=LINE, width=4)

    # «кадр»: янтарный треугольник play по центру
    cx, cy = S // 2, S // 2
    r = 118
    d.polygon([(cx - r * 0.55, cy - r), (cx - r * 0.55, cy + r), (cx + r * 0.9, cy)], fill=ACC)

    return im.resize((px, px), Image.LANCZOS)

for folder, px in SIZES.items():
    d = os.path.join(BASE, folder)
    os.makedirs(d, exist_ok=True)
    draw_icon(px).save(os.path.join(d, "ic_launcher.png"))
    # раунд-иконка та же (лаунчеры сами маскируют)
    draw_icon(px).save(os.path.join(d, "ic_launcher_round.png"))
    print(f"{folder}: {px}px OK")

print("icons done")
