#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Синтакс-чек HTML: вытащить все <script> без src и прогнать node --check."""
import re, subprocess, sys, os

path = sys.argv[1] if len(sys.argv) > 1 else '/home/z/my-project/download/plenka-optimized-64.html'
src = open(path, encoding='utf-8').read()
blocks = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', src, re.S | re.I)
print('скрипт-блоков: %d' % len(blocks))
ok = True
for i, b in enumerate(blocks):
    tmp = '/home/z/my-project/scripts/_synt%d.js' % i
    open(tmp, 'w', encoding='utf-8').write(b)
    r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
    if r.returncode != 0:
        ok = False
        print('БЛОК %d: ОШИБКА СИНТАКСИСА' % i)
        print(r.stderr[:2000])
    else:
        print('блок %d: ok (%d Б)' % (i, len(b)))
    os.unlink(tmp)
sys.exit(0 if ok else 1)
