#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v61 → v62: «время на панели — ЗАРАНЕЕ позиция нового трека» (репорт юзера).

Симптом: закончили смотреть видео / свайпнули на соседнее — на контроле
ещё «неск мгновений» висит ВРЕМЯ УХОДЯЩЕГО видео (и его линия), и только
потом приезжает время нового. Юзер просил: ставить сразу 00:00 — или, если
у нового трека отмечено «смотреть с момента», сразу ту позицию.

Причина: hudPrewind (v61) сбрасывал только кэш строк, но НЕ писал новые —
а rAF-цикл hud() тут же перерисовывал tCur/tDur/ползунок со СТАРОГО
активного элемента, пока loadStandby грузит новый. Строки становились
правдивыми только после swapRoles ($('#tDur')… в openItem) — на медленной
загрузке это заметное окно со старым временем.

Решение (62):
  - hudPrewind пишет и СТРОКИ: tCur = 00:00 или позиция продолжения
    (та же логика, что startPosOf/sbSeek: S.resume && position>10,
    «почти у конца» d-20 → старт с нуля); tDur = длительность нового
    трека из метаданных карточки (неизвестна → 0:00);
  - hudHoldId: от переключения до склейки HUD-цикл молчит — не затирает
    панель временем уходящего элемента; тонкая линия уходящего трека
    гаснет сразу; мини-линия в панели — на позиции ЦЕЛИ;
  - авторелиз: активным стал элемент цели (vActive._pid===hudHoldId,
    метаданные есть) → HUD разморожен, рисует по факту. Отказ/перебой
    открытия (fail / abort / race) — тоже разморозка. Зеркало PiP и
    мини-цикл покрыты тем же авторелизом (роли меняются там же).

Патчи (якоря уникальные, каждый проверяется count==1):
  P1 js : hudPrewind — строки заранее + hudHoldId/hudPrePct
  P2 js : hud() — замолкание до склейки + авторелиз
  P3 js : abort/race — разморозка
  P4 js : провал открытия — разморозка
  P5 js : мини-линия — позиция цели до склейки
  P6 ver: ДИАГ 'страница v61' → 'страница v62 / оболочка 3.15'
"""
import sys

SRC = '/home/z/my-project/download/plenka-optimized-61.html'
DST = '/home/z/my-project/download/plenka-optimized-62.html'

src = open(SRC, encoding='utf-8').read()
orig_len = len(src)


def patch(name, anchor, repl, count=1):
    global src
    n = src.count(anchor)
    assert n == count, 'ЯКОРЬ %s: найден %d раз (ожидался %d)' % (name, n, count)
    src = src.replace(anchor, repl, count)
    print('  [%s] ok' % name)


# ── P1: hudPrewind — строки времени ЗАРАНЕЕ + hold ───────────────────
A = (
"function hudPrewind(it){                          /* 24.10: прогресс и время — сразу на позиции цели,\n"
"    пока старый элемент ещё активен: линия не прыгает «со старой позиции в начало» */\n"
"  var d=(it&&it.duration)||0, w=startPosOf(it);\n"
"  var p=(isFinite(d)&&d>0)?Math.round(w/d*1000)/10:0;\n"
"  lastPct=p; lastTimeStr='\\u0000'; lastDurStr='\\u0000';\n"
"  if(hudEls.fill){ hudEls.fill.style.width=p+'%'; hudEls.knob.style.left=p+'%'; }\n"
"  if(TB.fill)TB.last=-1;\n"
"}\n"
)
R = (
"function hudPrewind(it){                          /* 24.10: прогресс и время — сразу на позиции цели,\n"
"    пока старый элемент ещё активен: линия не прыгает «со старой позиции в начало» */\n"
"  var d=(it&&it.duration)||0, w=startPosOf(it);\n"
"  if(isFinite(d)&&d>0&&w>d-20)w=0;                /* 62: «почти у конца» — как в открытии: стартуем с нуля */\n"
"  var p=(isFinite(d)&&d>0)?Math.round(w/d*1000)/10:0;\n"
"  lastPct=p;\n"
"  if(hudEls.fill){ hudEls.fill.style.width=p+'%'; hudEls.knob.style.left=p+'%'; }\n"
"  if(TB.fill)TB.last=-1;\n"
"  if(TB.el){ TB.on=false; TB.el.classList.remove('show'); }   /* 62: тонкая линия уходящего трека гаснет сразу */\n"
"  /* 62: и СТРОКИ — заранее позиция ЦЕЛИ: 00:00 или продолжение «с момента».\n"
"     Больше не мигаем временем уходящего видео, пока новый элемент грузится */\n"
"  hudHoldId=(it&&it.id)||null; hudPrePct=p;\n"
"  var pc=(S.timeLeft&&isFinite(d)&&d>0)?('\\u2212'+fmtT(d-w)):fmtT(w);\n"
"  var pd=(isFinite(d)&&d>0)?fmtT(d):'0:00';\n"
"  hudEls.cur.textContent=pc; lastTimeStr=pc;\n"
"  hudEls.dur.textContent=pd; lastDurStr=pd;\n"
"}\n"
"var hudHoldId=null,hudPrePct=0;   /* 62: цель, чьё время уже на панели; null — HUD рисует по факту */\n"
)
patch('P1 hudPrewind pre-write', A, R)

# ── P2: hud() — молчание до склейки + авторелиз ──────────────────────
A = (
"function hud(){\n"
"  if(!hudOn)return;\n"
"  var t=video.currentTime;\n"
)
R = (
"function hud(){\n"
"  if(!hudOn)return;\n"
"  if(hudHoldId){                                  /* 62: на панели уже время ЦЕЛИ — не затирать его\n"
"    временем уходящего элемента, пока новый не стал активным */\n"
"    if(vActive._pid===hudHoldId&&vActive.readyState>=1){ hudHoldId=null; lastTimeStr='\\u0000'; lastDurStr='\\u0000'; lastPct=-1; }\n"
"    else{ requestAnimationFrame(hud); return; }\n"
"  }\n"
"  var t=video.currentTime;\n"
)
patch('P2 hud hold', A, R)

# ── P3: abort/race — разморозка ──────────────────────────────────────
A = "if(!ok&&(lsWhy==='abort'||lsWhy==='race')){ return; }"
R = ("if(!ok&&(lsWhy==='abort'||lsWhy==='race')){ hudHoldId=null; return; }   /* 62: перебито/отменено — "
     "HUD рисует по факту */")
patch('P3 abort/race release', A, R)

# ── P4: провал открытия — разморозка ─────────────────────────────────
A = "    if(!ok){\n      NJ('open','НЕ открылось: why='+lsWhy+' err='+"
R = ("    if(!ok){\n"
     "      hudHoldId=null;                            /* 62: не открылось — панель показывает реальность активного */\n"
     "      NJ('open','НЕ открылось: why='+lsWhy+' err='+")
patch('P4 fail release', A, R)

# ── P5: мини-линия — позиция цели до склейки ─────────────────────────
A = "    if(miniFill)miniFill.style.width=((isFinite(d)&&d>0)?video.currentTime/d*100:0)+'%';\n"
R = (
"    if(hudHoldId){ if(miniFill)miniFill.style.width=hudPrePct+'%'; return; }   /* 62: до склейки — линия на позиции ЦЕЛИ, не уходящего */\n"
"    if(miniFill)miniFill.style.width=((isFinite(d)&&d>0)?video.currentTime/d*100:0)+'%';\n"
)
patch('P5 mini line', A, R)

# ── P6: версия ───────────────────────────────────────────────────────
A = "s('версия','страница v61 / оболочка 3.13');"
R = "s('версия','страница v62 / оболочка 3.15');   /* 62: время на панели — заранее позиция нового трека */"
patch('P6 version', A, R)

# ── запись ───────────────────────────────────────────────────────────
assert src.count('hudHoldId') >= 8, 'hudHoldId должен встречаться минимум 8 раз'
assert 'страница v61' not in src and 'страница v62' in src
open(DST, 'w', encoding='utf-8').write(src)
print('OK: %s (%d → %d байт, +%d)' % (DST, orig_len, len(src), len(src) - orig_len))
