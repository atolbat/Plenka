# -*- coding: utf-8 -*-
"""ПЛЁНКА — варианты иконки: Ё (Unbounded 800) + перфорация плёнки с двух сторон.
Палитра приложения: bg #0d0b09, amber #e8a33d, cream #ebe1cd.
Выход: download/icon-variants/v1..v6 PNG 512x512 (RGBA, скруглённые углы)
       + контактный лист download/icon-variants-preview.png
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

S = 512                      # холст
OUT = '/home/z/my-project/download/icon-variants'
FONT = '/home/z/my-project/scripts/Unbounded.ttf'
os.makedirs(OUT, exist_ok=True)

BG    = (13, 11, 9)          # #0d0b09 тёплый чёрный
BG2   = (21, 16, 10)         # верх градиента
AMBER = (232, 163, 61)       # #e8a33d
CREAM = (235, 225, 205)      # #ebe1cd

def font(sz, wght=800):
    f = ImageFont.truetype(FONT, sz)
    try: f.set_variation_by_axes([wght])
    except Exception: pass
    return f

def rr(d, box, r, fill):
    d.rounded_rectangle(box, radius=r, fill=fill)

def bg_canvas():
    """тёмный фон с мягким вертикальным градиентом"""
    im = Image.new('RGBA', (S, S))
    top, bot = BG2, BG
    for y in range(S):
        t = y / (S - 1)
        c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,)
        d = ImageDraw.Draw(im)
        d.line([(0, y), (S, y)], fill=c)
    return im

def amber_canvas():
    im = Image.new('RGBA', (S, S), AMBER + (255,))
    return im

def round_mask(im, r=104):
    """скруглить углы прозрачностью"""
    m = Image.new('L', (S, S), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, S - 1, S - 1], radius=r, fill=255)
    im.putalpha(m)
    return im

def perf_column(im, cx, y0, y1, n, w, h, r, fill, rot=0):
    """вертикальный ряд шашечек-перфорации с центром колонки в cx"""
    d = ImageDraw.Draw(im)
    step = (y1 - y0) / (n - 1)
    for i in range(n):
        cy = y0 + step * i
        box = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
        rr(d, box, r, fill)
    return im

# геометрия плёнки
STRIP_X0, STRIP_X1 = 116, 396            # полоса шириной 280
STRIP_Y0, STRIP_Y1 = 44, 468
PERF_W, PERF_H, PERF_R = 26, 36, 8        # шашечка
PERF_L = STRIP_X0 + 21                    # центр левой колонки
PERF_R = STRIP_X1 - 21                    # центр правой колонки
PERF_N = 7
PERF_Y0, PERF_Y1 = 74, 438

def letter(im, ch, box, size, fill, wght=800):
    d = ImageDraw.Draw(im)
    f = font(size, wght)
    d.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), ch, font=f,
           fill=fill, anchor='mm')

# ─── V1 «Кадр»: янтарная плёнка, широкий тёмный кадр, кремовая Ё ───
def v1():
    im = bg_canvas()
    d = ImageDraw.Draw(im)
    rr(d, [STRIP_X0, STRIP_Y0, STRIP_X1, STRIP_Y1], 30, AMBER + (255,))
    # кадр — тёмное окно, крупнее (одна рамка, минимум обрезки)
    FR = [STRIP_X0 + 52, STRIP_Y0 + 42, STRIP_X1 - 52, STRIP_Y1 - 42]
    rr(d, FR, 20, BG + (255,))
    perf_column(im, PERF_L, PERF_Y0, PERF_Y1, PERF_N, PERF_W, PERF_H, PERF_R, BG + (255,))
    perf_column(im, PERF_R, PERF_Y0, PERF_Y1, PERF_N, PERF_W, PERF_H, PERF_R, BG + (255,))
    letter(im, 'Ё', FR, 168, CREAM + (255,))
    return round_mask(im)

# ─── V2 «Сплошная»: янтарная полоса, тёмная Ё, перфорация-вырезы ───
def v2():
    im = bg_canvas()
    d = ImageDraw.Draw(im)
    rr(d, [STRIP_X0, STRIP_Y0, STRIP_X1, STRIP_Y1], 30, AMBER + (255,))
    perf_column(im, PERF_L, PERF_Y0, PERF_Y1, PERF_N, PERF_W, PERF_H, PERF_R, BG + (255,))
    perf_column(im, PERF_R, PERF_Y0, PERF_Y1, PERF_N, PERF_W, PERF_H, PERF_R, BG + (255,))
    letter(im, 'Ё', [STRIP_X0, STRIP_Y0, STRIP_X1, STRIP_Y1], 185, BG + (255,))
    return round_mask(im)

# ─── V3 «Крем»: кремовая полоса, тёмная Ё — высокий контраст ───
def v3():
    im = bg_canvas()
    d = ImageDraw.Draw(im)
    rr(d, [STRIP_X0, STRIP_Y0, STRIP_X1, STRIP_Y1], 30, CREAM + (255,))
    perf_column(im, PERF_L, PERF_Y0, PERF_Y1, PERF_N, PERF_W, PERF_H, PERF_R, BG + (255,))
    perf_column(im, PERF_R, PERF_Y0, PERF_Y1, PERF_N, PERF_W, PERF_H, PERF_R, BG + (255,))
    letter(im, 'Ё', [STRIP_X0, STRIP_Y0, STRIP_X1, STRIP_Y1], 185, BG + (255,))
    return round_mask(im)

# ─── V4 «Шашки»: без полосы — кремовая Ё, янтарные шашки плотно по бокам ───
def v4():
    im = bg_canvas()
    perf_column(im, 108, PERF_Y0 - 8, PERF_Y1 + 8, 7, 38, 50, 10, AMBER + (255,))
    perf_column(im, S - 108, PERF_Y0 - 8, PERF_Y1 + 8, 7, 38, 50, 10, AMBER + (255,))
    letter(im, 'Ё', [100, 80, S - 100, S - 80], 208, CREAM + (255,))
    return round_mask(im)

# ─── V5 «строчная»: кремовая строчная ё крупнее, янтарные шашки ───
def v5():
    im = bg_canvas()
    perf_column(im, 108, PERF_Y0 - 8, PERF_Y1 + 8, 7, 38, 50, 10, AMBER + (255,))
    perf_column(im, S - 108, PERF_Y0 - 8, PERF_Y1 + 8, 7, 38, 50, 10, AMBER + (255,))
    letter(im, 'ё', [100, 70, S - 100, S - 50], 238, CREAM + (255,))
    return round_mask(im)

# ─── V6 «Негатив»: янтарный фон, тёмная Ё, тёмные шашки ───
def v6():
    im = amber_canvas()
    perf_column(im, 84, PERF_Y0 - 6, PERF_Y1 + 6, 7, 36, 48, 10, (13, 11, 9, 255))
    perf_column(im, S - 84, PERF_Y0 - 6, PERF_Y1 + 6, 7, 36, 48, 10, (13, 11, 9, 255))
    letter(im, 'Ё', [84, 90, S - 84, S - 90], 200, (13, 11, 9, 255))
    return round_mask(im)

VARIANTS = [
    ('v1-frame',      'Кадр: янтарная плёнка, тёмный кадр, кремовая Ё', v1),
    ('v2-solid',      'Сплошная: янтарная полоса, тёмная Ё',            v2),
    ('v3-cream',      'Крем: кремовая полоса, янтарная Ё',              v3),
    ('v4-checkers',   'Шашки: янтарные шашки, кремовая Ё',              v4),
    ('v5-lower',      'Строчная: янтарные шашки, кремовая ё',           v5),
    ('v6-negative',   'Негатив: янтарный фон, тёмная Ё и шашки',        v6),
]

files = []
for name, title, fn in VARIANTS:
    im = fn()
    p = os.path.join(OUT, name + '.png')
    im.save(p)
    files.append((p, name, title))
    print('ok', p)

# ─── контактный лист 3×2 с подписями ───
TH = 300; GAP = 36; PAD = 40
LBL = 44
cols, rows = 3, 2
W = PAD * 2 + cols * TH + (cols - 1) * GAP
H = PAD * 2 + rows * (TH + LBL) + (rows - 1) * GAP
sheet = Image.new('RGB', (W, H), (24, 20, 15))
d = ImageDraw.Draw(sheet)
f_lbl = font(26, 600)
f_tit = font(19, 400)
for i, (p, name, title) in enumerate(files):
    r, c = divmod(i, cols)
    x = PAD + c * (TH + GAP)
    y = PAD + r * (TH + LBL + GAP)
    sheet.paste(Image.open(p).convert('RGB').resize((TH, TH), Image.LANCZOS), (x, y))
    d.text((x + 4, y + TH + 8), name.upper(), font=f_lbl, fill=AMBER)
    d.text((x + 4, y + TH + 8 + 30), title, font=f_tit, fill=(150, 138, 110))
sp = '/home/z/my-project/download/icon-variants-preview.png'
sheet.save(sp)
print('ok', sp, sheet.size)
