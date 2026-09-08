#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v58 → v59: две жалобы на v58/3.12.

ЖАЛОБА 1 «когда сворачиваю, пауза слишком долгая — ты отменяешь паузу, и это
очень сильно слышно»: Chromium гасит <video> на скрытой странице ЧЕРЕЗ
AwContents.onWindowVisibilityChanged → setWindowVisibilityInternal →
document.hidden (проверено по исходникам Chromium; JS-сторож в принципе не
может выиграть — v58 честно ограничил войну 3 попытками, но заикание и
сдача остались). Причина лечится ТОЛЬКО в нативе (оболочка 3.13): окно
«остаётся видимым» для Chromium, пока играет медиа (хак SO 52028940 /
53723297). Страница лишь убирает свой вклад в проблему:

  * stopMini(true) теперь зовёт обёртку pause() (userPaused/bgLive честны):
    раньше крестик мини-панели ставил СЫРУЮ паузу — bgLive зависал true, и
    фоновый сторож потом «оживлял» УЖЕ ЗАКРЫТОЕ юзером видео (лишние
    пауза/отмена на слуху).

ЖАЛОБА 2 «когда просто запускаю видео — кадр с первого видео висит надолго,
само не играет, пока вручную плей не нажму»: крестик мини-панели делал
playToken++ и СЫРУЮ video.pause() ПОСЛЕДНИМ жестом юзера:
  * playToken++ убивал ЛЮБОЕ открытие в полёте (loadStandby → lsWhy='race'
    → тихий return БЕЗ play()) — плеер с постером стоял до ручного плей;
  * на устройстве юзер ходил циклом «открыл → медленно → назад → мини → ✕
    → открыл» — каждый ✕ глушил и открытие, и тёплый запасной элемент,
    следующее открытие снова медленное — спираль.
Лечение:
  * miniClose: если плеер уже открывает ДРУГОЕ видео (панель — хвост
    прошлого) — гасим ТОЛЬКО панель: токен/запасной/открытие не трогаем;
    полный стоп (playToken++) остаётся для случая «панель = текущее видео,
    плеер закрыт»;
  * страховка автоплея в openItem: через 600мс один повторный play(), если
    open ещё актуален, элемент стоит, юзер не паузил — лечит молчаливый
    AbortError и любые WebView-причуды;
  * play() больше НЕ глотает AbortError молча — причина видна в ДИАГ;
  * ДИАГ: элементы теперь с флагами pa=/ld= (пауза/загрузка) + событие
    'playing' пишется в журнал — «play() вызван, а элемент не едет» больше
    не слепая зона.
"""
import sys, io, os, shutil

SRC = '/home/z/my-project/download/plenka-optimized-58.html'
DST = '/home/z/my-project/download/plenka-optimized-59.html'
ASSET = '/home/z/my-project/plenka-native/app/src/main/assets/plenka.html'

html = io.open(SRC, encoding='utf-8').read()

def rep(old, new, what, cnt=1):
    global html
    n = html.count(old)
    if n != cnt:
        print('FAIL: якорь %r найден %d раз (ожидалось %d)' % (what, n, cnt))
        sys.exit(1)
    html = html.replace(old, new)
    print('ok: %s' % what)

# ── P1: версия ──────────────────────────────────────────────────────────────
rep("s('версия','страница v58 / оболочка 3.12');",
    "s('версия','страница v59 / оболочка 3.13');", 'версия v59/3.13')

# ── P2: play() — AbortError больше не молчит ───────────────────────────────
rep("""function play(){ if(!video.src)return; markUserPause(false); bgLive=true; video.play().then(function(){},function(err){
  if(err&&err.name==='AbortError')return;          /* перебито следующим быстрым открытием — не ошибка жеста */
  toast(t('errNeedGesture'),'err') }); }""",
    """function play(){ if(!video.src)return; markUserPause(false); bgLive=true; video.play().then(function(){},function(err){
  if(err&&err.name==='AbortError'){ NJ('open','play() перебит (AbortError): seek='+(video.seeking?'1':'0')+' rs='+video.readyState+' net='+video.networkState+' pa='+(video.paused?'1':'0')); return; }   /* 59: не глотаем молча — репорт «кадр висит, само не играет» требует виновника */
  toast(t('errNeedGesture'),'err') }); }""",
    'play(): лог AbortError')

# ── P3: страховка автоплея в openItem ───────────────────────────────────────
rep("""    if(video._mseb&&!video.error&&my===playToken)await msebStartGate(video);   /* 51: буфер у позиции до play() — старт без рывка */
    if(my!==playToken)return;    /* гейт ждал — цель могла смениться */
    play();
    if(!wasPl&&!video.paused)playFx();
  }""",
    """    play();
    if(!wasPl&&!video.paused)playFx();
    (function(tk){ setTimeout(function(){          /* 59: страховка автоплея — репорт v58 «кадр с первого
        видео висит, само не играет до ручного плей». play() мог быть перебит
        (AbortError глотался молча) либо не прокнуть на WebView. Один повтор
        через 600мс — пока open актуален, юзер не паузил, не ушли в фон */
      try{
        if(tk!==playToken||player.hidden||userPaused||document.hidden)return;
        if(localStorage.getItem('plenka.pipMode')==='pip')return;
        var V=video; if(!V||!V.src||V.ended||V.error)return;
        if(V._mseb&&V._mseb.techPaused)return;
        if(V.paused){ play(); NJ('open','автоплей-страховка: элемент стоял — повторный play()') }
      }catch(e){}
    },600) })(my);
  }""",
    'openItem: страховка автоплея 600мс')

# ── P4: miniClose не убивает открытие в полёте ──────────────────────────────
rep("""miniCloseB.addEventListener('click',function(){
  if(miniSwipe){ miniSwipe=false; return; }
  if(MINI.mode==='remote'){ if(REMOTE)syncPost({t:'cmd',to:REMOTE.tab,cmd:'close'}); REMOTE=null; hideMini(); updTitle(); return; }
  stopMini(true);
  playToken++; currentIdx=-1;
  try{ if(vStandby&&vStandby!==vActive)vStandby.pause() }catch(e){}
  syncPost({t:'bye'});
  renderLib(); updTitle();
});""",
    """miniCloseB.addEventListener('click',function(){
  if(miniSwipe){ miniSwipe=false; return; }
  if(MINI.mode==='remote'){ if(REMOTE)syncPost({t:'cmd',to:REMOTE.tab,cmd:'close'}); REMOTE=null; hideMini(); updTitle(); return; }
  /* 59: репорт v58 «кадр с первого видео висит, само не играет до ручного
     плей»: playToken++ последним жестом убивал открытие в полёте (тихий
     lsWhy='race' без play()). Если плеер уже на экране и открывает ДРУГОЕ
     видео — эта панель хвост прошлого: гасим ТОЛЬКО её, токен/запасной
     элемент/открытие не трогаем */
  var openingNew=(!player.hidden)&&currentIdx>=0&&items[currentIdx]&&MINI.item&&items[currentIdx]!==MINI.item;
  if(openingNew){ stopMini(true); syncPost({t:'bye'}); renderLib(); updTitle(); return; }
  stopMini(true);
  playToken++; currentIdx=-1;
  try{ if(vStandby&&vStandby!==vActive)vStandby.pause() }catch(e){}
  syncPost({t:'bye'});
  renderLib(); updTitle();
});""",
    'miniClose: открытие в полёте живёт')

# ── P5: stopMini — обёртка pause() (userPaused/bgLive честны) ───────────────
rep("""  if(stopPlayback&&MINI.mode==='local'){ try{video.pause()}catch(e){} savePos(true); }""",
    """  if(stopPlayback&&MINI.mode==='local'){ try{ pause() }catch(e){} savePos(true); }   /* 59: обёртка —
     сырая пауза оставляла bgLive=true: сторож фона «оживлял» уже закрытое юзером видео */""",
    'stopMini: pause() обёрткой')

# ── P6: ДИАГ — элементы с pa=/ld=, факт старта в журнал ─────────────────────
rep("""      return 'rs='+el.readyState+' net='+el.networkState+' t='+Math.round(el.currentTime||0)+'с буф='+bf+
        ' err='+((el.error&&el.error.code)||'-')+mb+' src='+(''+(el.currentSrc||el.src||'')).slice(-36); };""",
    """      return 'rs='+el.readyState+' net='+el.networkState+' t='+Math.round(el.currentTime||0)+'с буф='+bf+
        ' pa='+(el.paused?'1':'0')+(el._loading?' ld=1':'')+
        ' err='+((el.error&&el.error.code)||'-')+mb+' src='+(''+(el.currentSrc||el.src||'')).slice(-36); };""",
    'ДИАГ: элементы pa/ld')

rep("""VOn('seeked',stallReset);""",
    """VOn('seeked',stallReset);
VOn('playing',function(){ NJ('open','событие: playing (t='+Math.round(video.currentTime||0)+'с)') });   /* 59: факт старта — в ДИАГ: «play() вызван, а элемент не едет» виден сразу */""",
    'журнал: событие playing')

io.open(DST, 'w', encoding='utf-8', newline='').write(html)
shutil.copyfile(DST, ASSET)
print('записан %s (%d Б), ассет обновлён' % (DST, len(html.encode('utf-8'))))
