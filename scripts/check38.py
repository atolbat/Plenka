#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v38: извлечь оба <script>-блока и проверить синтаксис через node --check."""
import re, subprocess, sys

P = "/home/z/my-project/download/plenka-optimized-38.html"
html = open(P, encoding="utf-8").read()

scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
print("script-блоков:", len(scripts))
ok = True
for i, s in enumerate(scripts):
    fn = "/home/z/my-project/scripts/_v38_s%d.js" % i
    with open(fn, "w", encoding="utf-8") as f:
        f.write(s)
    r = subprocess.run(["node", "--check", fn], capture_output=True, text=True)
    st = "OK" if r.returncode == 0 else "FAIL"
    print("блок %d: %s (%d строк)" % (i, st, s.count("\n")))
    if r.returncode != 0:
        print(r.stderr[:2000])
        ok = False

# быстрые контекстные проверки
checks = [
    ("journal API", "window.__plenkaJ=function(tag,msg)"),
    ("клик-логгер", "tapDesc(e.target)"),
    ("ретрай-лестница", "natvSyncSchedule"),
    ("опрос права", "natvPermPoll"),
    ("вочдог", "natvWatchdogStart"),
    ("квитанция permResult", "return 'gate'"),
    ("квитанция picked", "return 'n='+n"),
    ("i18n mismatch ru", "natvScanMismatch:'скан медиатеки"),
    ("версия в отчёте", "страница v38 / оболочка 2.3"),
    ("journal в отчёте", "журнал',D.journal.length"),
    ("watchdog старт в init", "natvWatchdogStart();"),
    ("natvCall журнал исключений", "ИСКЛЮЧЕНИЕ '+fn"),
]
for name, needle in checks:
    print(("  ✓ " if needle in html else "  ✗ НЕТ ") + name)
    if needle not in html:
        ok = False

# ES5-гвард: стрелочные функции/let/const в новых блоках запрещены
m = re.search(r"window\.__plenkaJ=function.*?\n};", html, re.S)
if m:
    bad = re.findall(r"=>|\blet\s|\bconst\s", m.group(0))
    print("ES5 в журнале:", "OK" if not bad else "НАЙДЕНО: %s" % bad)
    ok = ok and not bad
nblk = re.search(r"var natvSyncBusy=false.*?function natvMerge\(", html, re.S)
if nblk:
    bad = re.findall(r"=>|\blet\s[^a-zA-Z]", nblk.group(0))
    print("ES5 в nativeSync-блоке:", "OK" if not bad else "НАЙДЕНО: %s" % bad)
    ok = ok and not bad

sys.exit(0 if ok else 1)
