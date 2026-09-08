# -*- coding: utf-8 -*-
"""Иконка v4-checkers → mipmap-набор лаунчера (PNG, как в 3.14/3.15).

Квадратная (ic_launcher.png): точный v4 из icon_variants.py (скруглённый
квадрат r=104/512), ресайз 48/72/96/144/192.
Круглая (ic_launcher_round.png): компоновка v4 вписана в круг r=256 с запасом
(колонки шашек и буква гарантированно внутри маски).
"""
import os
from PIL import Image, ImageDraw, ImageFont

S = 512
ROOT = '/home/z/my-project'
OUT = ROOT + '/plenka-native/app/src/main/res'
FONT = ROOT + '/scripts/Unbounded.ttf'
BG    = (13, 11, 9)
BG2   = (21, 16, 10)
AMBER = (232, 163, 61)
CREAM = (235, 225, 205)

def font(sz, wght=800):
    f = ImageFont.truetype(FONT, sz)
    try: f.set_variation_by_axes([wght])
    except Exception: pass
    return f

def bg_canvas():
    im = Image.new('RGBA', (S, S))
    d = ImageDraw.Draw(im)
    top, bot = BG2, BG
    for y in range(S):
        t = y / (S - 1)
        c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,)
        d.line([(0, y), (S, y)], fill=c)
    return im

def perf_column(d, cx, y0, y1, n, w, h, r, fill):
    step = (y1 - y0) / (n - 1)
    for i in range(n):
        cy = y0 + step * i
        d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], radius=r, fill=fill)

def round_v4():
    """v4, вписанный в круг: колонки x=118/394, шашки 30×42, y 84..428, Ё кремовая 196pt"""
    im = bg_canvas()
    d = ImageDraw.Draw(im)
    perf_column(d, 124, 96, 416, 7, 28, 38, 8, AMBER + (255,))
    perf_column(d, S - 124, 96, 416, 7, 28, 38, 8, AMBER + (255,))
    f = font(188)
    d.text((S / 2, S / 2 + 4), 'Ё', font=f, fill=CREAM + (255,), anchor='mm')
    # круглая маска с лёгким анти-алиасингом (маска 4× и downscale)
    m = Image.new('L', (S * 4, S * 4), 0)
    ImageDraw.Draw(m).ellipse([0, 0, S * 4 - 1, S * 4 - 1], fill=255)
    m = m.resize((S, S), Image.LANCZOS)
    im.putalpha(m)
    return im

DENS = [('mdpi', 48), ('hdpi', 72), ('xhdpi', 96), ('xxhdpi', 144), ('xxxhdpi', 192)]
src_sq = Image.open(ROOT + '/download/icon-variants/v4-checkers.png').convert('RGBA')
src_rd = round_v4()

for dpi, sz in DENS:
    d1 = os.path.join(OUT, 'mipmap-' + dpi)
    os.makedirs(d1, exist_ok=True)
    sq = src_sq.resize((sz, sz), Image.LANCZOS)
    sq.save(os.path.join(d1, 'ic_launcher.png'))
    rd = src_rd.resize((sz, sz), Image.LANCZOS)
    rd.save(os.path.join(d1, 'ic_launcher_round.png'))
    print('ok mipmap-%s: ic_launcher %d×%d + round' % (dpi, sz, sz))

# контроль: углы шашек внутри круга
import math
ok = True
for cy in (96, 416):
    for cx in (124, S - 124):
        for dx, dy in ((-14, -19), (14, 19), (14, -19), (-14, 19)):
            r = math.hypot(cx + dx - 256, cy + dy - 256)
            if r > 256: ok = False; print('ВНИМАНИЕ: шашка за кругом', cx, cy, round(r))
print('геометрия круга: %s' % ('ok' if ok else 'ПРЕВЫШЕНИЕ'))
