#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v62 → v63: пять репортов юзера + иконка v4 (сборка отдельно, patch63).

1) PiP из миниплеера — «чёрное всё и юац другой»: __pipMode ставил класс
   minist, который прятал и #player, и #stage — в системном PiP-окне
   оставались тёмная страница + панелька мини. Решение: minist не ставим —
   body.pip показывает #player со stage (видео) + pipHud, тот же вид,
   что из открытого видео. CSS minist остаётся мёртвым (не удаляем блок).

2) «После PiP в миниплеере закрыл его, закрыл видео, зашёл — снизу виден
   кадр из ДРУГОГО видео»: vblank (подложка z2 под видео) чистился только
   в closePlayerView (кнопка «вниз» плеера), но НЕ в stopMini (крестик
   мини-панели) — путь «PiP → закрыл → крестик мини» оставлял в vblank
   миниатюру прошлого видео; при следующем открытии до первого кадра
   нового она просвечивала «снизу». Решение: stopMini(stopPlayback) —
   setVblank(null) (+hideFreeze/hidePoster — симметрично closePlayerView).

3) «При каждом рестарте у каждого видео значок „новое“»: natvMerge,
   присланный оболочкой (__plenkaResume на onPageFinished), обгонял
   стартовое чтение реестра из IDB — items ещё пусты, все нативные файлы
   считались новыми: it.fresh=true, position=0, persistItem ПЕРЕЗАПИСЫВАЛ
   IDB (терялись и позиции «смотреть с момента»). Решение: гейт REG_READY
   (как hiddenReady v61, но для данных): nativeSync придерживается до
   готовности реестра; после чтения — догоняет накопленный синк.

4) 4К: msebAheadHi — ветка hi-res (w>=2560 || h>=1440 || bps>4МБ/с):
   цель буфера до 50МБ/24с (было 18МБ/14с, у 4К фактически 6с) и троттлинг
   качалки мягче (сон 140→60мс) — буфер не отстаёт от декодера.

5) Индикация подгрузки на линии перемотки: renderBufs (#pBufs — светлые
   полосы «что подгрузилось») — убрать совсем (заглушка + снята подписка
   на progress).

Патчи (якоря уникальные, каждый проверяется count==1):
  P1 js : __pipMode — minist больше не ставится
  P2 js : stopMini — чистка vblank/freeze/poster
  P3 js : REG_READY-гейт (глобал + nativeSync + стартап)
  P4 js : msebAheadHi 4K-ветка + мягкий троттлинг качалки
  P5 js : renderBufs-заглушка + снять VOn('progress')
  P6 ver: ДИАГ 'страница v62 / оболочка 3.15' → 'страница v63 / оболочка 3.16'
"""
import sys

SRC = '/home/z/my-project/download/plenka-optimized-62.html'
DST = '/home/z/my-project/download/plenka-optimized-63.html'

src = open(SRC, encoding='utf-8').read()
orig_len = len(src)


def patch(name, anchor, repl, count=1):
    global src
    n = src.count(anchor)
    assert n == count, 'ЯКОРЬ %s: найден %d раз (ожидался %d)' % (name, n, count)
    src = src.replace(anchor, repl, count)
    print('  [%s] ok' % name)


# ── P1: PiP из мини — видео вместо чёрного ───────────────────────────
A = "document.body.classList.toggle('minist',!!(on&&player.hidden));"
R = ("document.body.classList.remove('minist');   /* 63: PiP из миниплеера показывает ТОТ ЖЕ вид, что из\n"
     "                                       открытого видео: #player+stage (видео) поверх pipHud — вместо\n"
     "                                       чёрного экрана с панелькой (minist) */")
patch('P1-pip-minist', A, R)

# ── P2: stopMini — чистить vblank (призрак прошлого кадра) ──────────
A = ("function stopMini(stopPlayback){\n"
     "  if(MINI.mode==='local')dockVideos();\n"
     "  if(stopPlayback&&MINI.mode==='local'){ try{ pause() }catch(e){} savePos(true); }   /* 59: обёртка —\n")
R = ("function stopMini(stopPlayback){\n"
     "  if(MINI.mode==='local')dockVideos();\n"
     "  if(stopPlayback&&MINI.mode==='local'){ try{ pause() }catch(e){} savePos(true);\n"
     "    try{ setVblank(null) }catch(e){}                  /* 63: крестик мини — тот же выход, что «вниз» из\n"
     "    try{ hideFreeze() }catch(e){}                        плеера: подложка/маска/постер не должны оставлять\n"
     "    try{ hidePoster(true) }catch(e){}                    кадр прошлого видео под следующим открытием */\n"
     "  }   /* 59: обёртка —\n")
patch('P2-stopmini-vblank', A, R)

# ── P3: REG_READY-гейт natv-скана ───────────────────────────────────
A = ("hiddenReady=false;   /* скрытый список: id → true; вход — особым жестом; 61: hiddenReady — список рендерится только после прочтения hiddenlist из IDB */\n")
R = ("hiddenReady=false;   /* скрытый список: id → true; вход — особым жестом; 61: hiddenReady — список рендерится только после прочтения hiddenlist из IDB */\n"
     "var REG_READY=false, natvHold=false;   /* 63: стартовый реестр items ещё не дочитан из IDB — natvMerge\n"
     "                                  обгонял чтение и перезаписывал все записи (fresh/position=0): «точка нового\n"
     "                                  у всех при рестарте» + потеря позиций «смотреть с момента» */\n")
patch('P3a-gate-global', A, R)

A = ("function nativeSync(rescan){\n"
     "  if(!NATV){ NJ('sync','моста нет — выходим'); return; }\n")
R = ("function nativeSync(rescan){\n"
     "  if(!NATV){ NJ('sync','моста нет — выходим'); return; }\n"
     "  if(!REG_READY){ natvHold=true; NJ('sync','реестр из IDB ещё читается — синк придержан (63)'); return; }\n")
patch('P3b-gate-sync', A, R)

A = ("function natvPickedSync(announce){\n"
     "  if(!NATV)return;\n")
R = ("function natvPickedSync(announce){\n"
     "  if(!NATV)return;\n"
     "  if(!REG_READY){ natvHold=true; NJ('мерж-выбор','реестр из IDB ещё читается — придержано (63)'); return; }   /* 63: та же гонка, что у nativeSync */\n")
patch('P3d-gate-picked', A, R)

A = "function natvMerge(arr,rescan){\n  var byNat={};\n"
R = ("function natvMerge(arr,rescan){\n"
     "  if(!REG_READY){ natvHold=true; NJ('мерж','реестр из IDB ещё читается — слияние отложено (63: watchdog-форс не должен обгонять чтение и пересоздавать записи с fresh/position=0)'); return; }\n"
     "  var byNat={};\n")
patch('P3e-gate-merge', A, R)

A = "function natvMergePicked(arr,announce){\n"
R = ("function natvMergePicked(arr,announce){\n"
     "  if(!REG_READY){ natvHold=true; NJ('мерж-выбор','реестр из IDB ещё читается — слияние отложено (63)'); return; }\n")
patch('P3f-gate-merge-picked', A, R)


A = "hiddenReady=true;                     /* 61: скрытые известны (или IDB отказал) — список можно показывать */\n"
R = "hiddenReady=true;                     /* 61: скрытые известны (или IDB отказал) — список можно показывать (63: REG_READY ниже — ПОСЛЕ наполнения items) */\n"
patch('P3c-gate-anchor-keep', A, R)

A = ("        else if(m.kind==='blob'){\n"
     "          if(blobSet.has(m.id))items.push(m);\n"
     "        }\n"
     "      }\n"
     "    }\n"
     "    var fv=R[4];\n")
R = ("        else if(m.kind==='blob'){\n"
     "          if(blobSet.has(m.id))items.push(m);\n"
     "        }\n"
     "      }\n"
     "    }\n"
     "    REG_READY=true;    /* 63: реестр items дочитан и в памяти — natvMerge не перезапишет\n"
     "      свежими записями (fresh/position=0), как было при обгоне синком чтения IDB */\n"
     "    if(natvHold){ natvHold=false; try{ nativeSync(false); natvPickedSync(false) }catch(e){} }   /* 63: догоняем придержанный синк */\n"
     "    var fv=R[4];\n")
patch('P3c-gate-release', A, R)

# ── P4: 4K — цель буфера и троттлинг ────────────────────────────────
A = ("function msebAheadHi(b){                               /* 45: цель буфера — запас 6…14с, но ≤18МБ памяти:\n"
     "    у высокого разрешения 14с запаса = 40-70МБ в MSE — устройство душится (GC/эвикция);\n"
     "    теперь качалка не выхватывает файл целиком на максимуме скорости */\n"
     "  var bps=(b.bps&&b.bps>30000)?b.bps:1500000;\n"
     "  return Math.max(6,Math.min(14,Math.round(18874368/bps)));\n"
     "}\n")
R = ("function msebAheadHi(b){                               /* 63: hi-res (4К, ≥2560×1440 или >4МБ/с) — запас шире:\n"
     "    до 50МБ/24с вместо 18МБ/14с; у 4К фактически было 6с — буфер отставал от декодера,\n"
     "    рывки. Прочим — прежняя формула 45 (≤18МБ, 6…14с) */\n"
     "  var bps=(b.bps&&b.bps>30000)?b.bps:1500000;\n"
     "  var hi4k=((b.w||0)>=2560)||((b.h||0)>=1440)||(bps>4194304);\n"
     "  var cap=hi4k?52428800:18874368, lo=hi4k?8:6, hiS=hi4k?24:14;\n"
     "  return Math.max(lo,Math.min(hiS,Math.round(cap/bps)));\n"
     "}\n")
patch('P4a-ahead-hi', A, R)

A = "if(ahead!=null&&ahead>1.5&&(st.bufEnd||0)>2.5){ await msebSleep(140) }  /* 46: 3→1.5с —"
R = ("if(ahead!=null&&ahead>1.5&&(st.bufEnd||0)>2.5){\n"
     "          await msebSleep(((b&&(b.w||0)>=2560)||((b&&(b.h||0))>=1440))?60:140) }  /* 63: hi-res — сон 60: буфер 4К не отстаёт; 46: 3→1.5с —")
patch('P4b-pump-sleep', A, R)

# ── P5: убрать индикацию подгрузки на линии перемотки ───────────────
A = ("function renderBufs(){\n"
     "  if(!isFinite(video.duration))return;\n")
R = ("function renderBufs(){\n"
     "  return;                                  /* 63: светлые полосы подгрузки на линии перемотки убраны\n"
     "                                              по репорту — ничего не рисуем */\n"
     "  if(!isFinite(video.duration))return;\n")
patch('P5a-renderbufs-stub', A, R)

A = "VOn('progress',renderBufs);"
R = "/* 63: VOn('progress',renderBufs) — убрано: индикации подгрузки на линии больше нет */"
patch('P5b-unsubscribe', A, R)

# ── P6: версия ──────────────────────────────────────────────────────
A = "s('версия','страница v62 / оболочка 3.15');"
R = "s('версия','страница v63 / оболочка 3.16');   /* 63: PiP из мини, призрак vblank, fresh при рестарте, 4К-буфер, буферной полосы нет */"
patch('P6a-diag', A, R)

assert len(src) > orig_len * 0.995, 'файл подозрительно уменьшился'
open(DST, 'w', encoding='utf-8').write(src)
print('ГОТОВО: %s (%d Б, было %d Б, +%d)' % (DST, len(src), orig_len, len(src) - orig_len))
