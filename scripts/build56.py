#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v55 → v56: фоновое воспроизведение БЕЗ PiP.

Задача пользователя: «видео проигрывались, когда я сверну приложение без pip.
Или без видимого пип».

Что делает натив (3.9 → 3.10, scripts/patch40.py): при сворачивании активность
уходит в фон, WebView остаётся жить (onPause вызывать не будем и раньше не
звали), процесс держит foreground mediaPlayback-сервис с медиа-уведомлением
(пауза/плей/треки в шторке и на локскрине) + partial WakeLock на погашенный
экран. Это и есть «без pip»: ни окна, ни черной плашки — просто звук и позиция
продолжают идти, а в шторке кнопки.

Что нужно от СТРАНИЦЫ (этот скрипт):
  1) setPipAuto больше не включаем (режим 'pip' можно вернуть localStorage
     plenka.pipMode='pip') — авто-вход в PiP не срабатывает, сворачивание
     уходит в фон;
  2) на visibilitychange: hidden+играем → natvMediaPush(true) ДО onStop
     (оболочка поднимет/обновит медиа-сервис), visible → push (оболочка
     гасит сервис, звук не трогает);
  3) MSE-качалка: в скрытой вкладке Chromium давит setTimeout до 1с (а через
     5 минут — до минуты): спим через MessageChannel-задачу, которую
     таймер-троттлинг не режет — темп фоновой подкачки = как на экране;
  4) сторож картинки (rVFC «кадра нет 3с») в фоне ложно колотил бы
     реанимацией каждые 15с: кадры в скрытой вкладке не рисуются ПО
     ОПРЕДЕЛЕНИЮ — гейтим ветку document.hidden;
  5) версия v56 / оболочка 3.10.
"""
import sys, io, os

SRC = '/home/z/my-project/download/plenka-optimized-55.html'
DST = '/home/z/my-project/download/plenka-optimized-56.html'

html = io.open(SRC, encoding='utf-8').read()

def rep(old, new, what, cnt=1):
    global html
    n = html.count(old)
    if n != cnt:
        print('FAIL: якорь %r найден %d раз (ожидалось %d)' % (what, n, cnt)); sys.exit(1)
    html = html.replace(old, new)
    print('ok: %s' % what)

# ── P1: версия ──────────────────────────────────────────────────────────────
rep("s('версия','страница v55 / оболочка 3.9');",
    "s('версия','страница v56 / оболочка 3.10');", 'версия v56/3.10')

# ── P2: сворачивание — фон по умолчанию, PiP опционально ────────────────────
rep("""  var vid=on&&wi&&!wi.audio;       /* 55: сворачивание с ВИДЕО → окно PiP, видео продолжает
                                      играть ВИДИМО; сворачивание с АУДИО → фон без окна
                                      (звук продолжает, как и раньше) */
  natvCall('setPipAuto',vid); natvCall('keepScreenOn',on);""",
    """  var pipW=(localStorage.getItem('plenka.pipMode')==='pip');   /* 56: сворачивание БЕЗ PiP —
                                      видео уходит в фон играющим (звук + позиция), оболочка
                                      3.10 держит процесс медиа-сервисом (кнопки в шторке);
                                      'pip' в localStorage возвращает старое видимое окно */
  natvCall('setPipAuto',on&&pipW&&!!wi&&!wi.audio); natvCall('keepScreenOn',on);""",
    'natvWakePip: фон по умолчанию')

# ── P3: MSE-качалка — сны в фоне через MessageChannel ───────────────────────
rep("""function msebPump(el){                                 /* качалка: пары moof+mdat с патчем адресации.""",
    """function msebSleep(ms){                                /* 56: фоновый режим. setTimeout в скрытой
    вкладке Chromium давится до 1с (спустя 5 минут — до минуты): качалка гигантов
    засыпала и длинное видео в фоне вставало. MessageChannel-ожидание — обычная
    задача, таймер-троттлинг её не режет: темп фоновой подкачки = как на экране */
  if(!document.hidden||ms<=12)return new Promise(function(r){ setTimeout(r,ms) });
  return new Promise(function(res){
    var t0=Date.now(),mc=null;
    try{ mc=new MessageChannel() }catch(e){}
    if(!mc){ setTimeout(res,ms); return }
    var step=function(){
      if(Date.now()-t0>=ms-8){ try{mc.port1.close();mc.port2.close()}catch(e2){} res(); return }
      mc.port1.onmessage=function(){ mc.port1.onmessage=null; step() };
      try{ mc.port2.postMessage(0) }catch(e3){ setTimeout(res,Math.max(0,ms-(Date.now()-t0))) }
    };
    step();
  });
}
function msebPump(el){                                 /* качалка: пары moof+mdat с патчем адресации.""",
    'msebSleep вставлен')

rep("""          if(myT>tgt+hi){ await new Promise(function(r){ setTimeout(r,320) }); continue }""",
    """          if(myT>tgt+hi){ await msebSleep(320); continue }""",
    'сон 320 (myT>цели)')

rep("""        }else if(ahead>hi){ await new Promise(function(r){ setTimeout(r,320) }); continue }""",
    """        }else if(ahead>hi){ await msebSleep(320); continue }""",
    'сон 320 (буфер полон)')

rep("""        if(ahead!=null&&ahead>1.5&&(st.bufEnd||0)>2.5){ await new Promise(function(r){ setTimeout(r,140) }) }""",
    """        if(ahead!=null&&ahead>1.5&&(st.bufEnd||0)>2.5){ await msebSleep(140) }""",
    'сон 140 (темп)')

rep("""        if(st.burst&&st.seekT!=null&&burstBytes>4194304){ await new Promise(function(r){ setTimeout(r,40) }) }""",
    """        if(st.burst&&st.seekT!=null&&burstBytes>4194304){ await msebSleep(40) }""",
    'сон 40 (микро)')

# ── P4: сторож картинки не срабатывает в фоне ───────────────────────────────
rep("""        if(!el.paused&&!el.seeking&&(el.readyState||0)>=2&&b.hasVid){""",
    """        if(!document.hidden&&!el.paused&&!el.seeking&&(el.readyState||0)>=2&&b.hasVid){   /* 56: в фоне
                                      кадры не рисуются ПО ОПРЕДЕЛЕНИЮ (rVFC молчит) — без
                                      гейта «кадра нет 3с» ложно колотил бы реанимацией
                                      каждые 15с, срывая фоновое воспроизведение */""",
    'сторож rVFC: гейт document.hidden')

# ── P5: visibilitychange — уходим играющими наружу ─────────────────────────
rep("""    if(S.pauseOnHidden&&!video.paused)pause();   /* по умолчанию — как на ютубе: звук продолжается */""",
    """    if(S.pauseOnHidden&&!video.paused)pause();   /* по умолчанию — как на ютубе: звук продолжается */
    else{ try{ if(NATV)natvMediaPush(true) }catch(e){} }   /* 56: ушли в фон играющими — состояние
                                      наружу (оболочка поднимет/обновит медиа-сервис,
                                      шторка получает честную позицию и заголовок) */""",
    'visibilitychange: push наружу')

rep("""    if(!video.paused)lockWake();""",
    """    if(!video.paused)lockWake();
    try{ if(NATV)natvMediaPush(!video.paused) }catch(e){}   /* 56: вернулись на экран — оболочка
                                      гасит фоновый медиа-сервис (звук не трогаем) */""",
    'visibilitychange: push при возврате')

io.open(DST, 'w', encoding='utf-8').write(html)
print('размер: %d байт (v55 был %d)' % (len(html.encode('utf-8')), os.path.getsize(SRC)))
print('OK →', DST)
