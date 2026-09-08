#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v57 → v58: починка фонового воспроизведения (регресс v57/3.11).

ДИАГНОЗ по логам юзера (репорт: «после сворачивания пауза всё равно слышна
до отмены», «нормально открытые видео останавливаются и паузятся», «10сек
пауза, пока не продолжит»):

1. ВОЙНА ПАУЗ (шторм 30Гц «пауза в фоне не от юзера — возобновляем»):
   v57-сторож гасил КАЖДУЮ чужую паузу мгновенным play(). Пока элемент
   MUTED (гейт «звук после первого кадра», окно 4с у нового трека — rVFC
   в скрытой странице не приходит, гейт не спадает), Chromium гасит
   muted-видео в скрытой вкладке ЛЕГАЛЬНО (энергосбережение): пауза →
   наш play() → снова пауза → … Шторм длился ровно до 4с-страховки гейта,
   на слух — заикание («пауза слышна»).

2. ШТОРМ САМОЛЕЧЕНИЯ в foreground: поток-вочдог НЕ сбрасывал stall-состояние
   при открытии НОВОГО видео/перезарядке — новому сразу прилетало «6с без
   хода» (репорт: самолечение №1 через 0.8с после open), а перезарядка к
   позиции МЕНЬШЕ stallPos не считалась «прогрессом» → перезарядки №1/2/3
   подряд уже на экране. Это и есть «нормально открытые видео
   останавливаются и паузятся» после любого сворачивания.

3. «10сек пауза, пока не продолжит»: сердце фона дёргало play() раз в 10с —
   окно между попытками и было десятисекундной паузой.

ЛЕЧЕНИЕ (v58):
  * гейт mute снимается ПРИ уходе в фон (visibilitychange) — muted-триггер
    исчезает, Chromium честно играет audible-элемент в скрытой вкладке;
  * чужая пауза в фоне: первая попытка сразу, дальше максимум 3 с шагом
    700мс; после 3 неудач — bgGaveUp (тишина, не воюем), оживление одним
    play() при возврате на экран;
  * stallReset() на 'play'/'seeked' и в перезарядке: вочдог всегда начинает
    с чистого листа; буфер ещё пуст (readyState<3) — окно 14с вместо 6с;
  * сердце фона: 5с, шлёт ТОЛЬКО честное состояние и только по его смене,
    play() не дёргает вовсе.

Оболочка 3.12 (правится отдельно): версия, страховка webView.onResume()
в onResume — OEM-глушилки больше не оставляют WebView «на паузе».
"""
import sys, io, os

SRC = '/home/z/my-project/download/plenka-optimized-57.html'
DST = '/home/z/my-project/download/plenka-optimized-58.html'
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
rep("s('версия','страница v57 / оболочка 3.11');",
    "s('версия','страница v58 / оболочка 3.12');", 'версия v58/3.12')

# ── P2/P3: обёртки — честный bgLive (жили/умерли через наши кнопки) ─────────
rep("function play(){ if(!video.src)return; markUserPause(false); video.play().then(function(){},function(err){",
    "function play(){ if(!video.src)return; markUserPause(false); bgLive=true; video.play().then(function(){},function(err){",
    'play(): bgLive=true')

rep("function pause(){ markUserPause(true); video.pause(); }",
    "function pause(){ markUserPause(true); bgLive=false; video.pause(); }",
    'pause(): bgLive=false')

# ── P4: stallReset + вочдог с ширеим окном на пустом буфере ─────────────────
rep("var stallPos=-1, stallN=0, stallT=0;",
    """var stallPos=-1, stallN=0, stallT=0;
function stallReset(){ stallPos=-2; stallT=0; stallN=0 }   /* 58: новая эпоха (открытие/resume/сик/
  перезарядка) — вочдог обязан начинать с чистого листа. Старое состояние протекало из
  прошлого видео/эпизода: новому сразу прилетало «6с без хода» (репорт: самолечение №1
  через 0.8с после open) и разгонялось до шторма перезарядок уже на экране */
VOn('play',stallReset);
VOn('seeked',stallReset);
VOn('ended',function(){ bgLive=false });""",
    'stallReset + эпохи')

rep("    if(Date.now()-stallT<6000)return;",
    """    var need=(video.readyState<3)?14000:6000;         /* 58: буфера ещё нет (moov/медленный вход) —
      окно шире: тяжёлый старт не наказываем перезарядкой на 6-й секунде */
    if(Date.now()-stallT<need)return;""",
    'вочдог: окно 14с при пустом буфере')

rep("    NJ('плеер','поток встал на '+fmtT(tpos)+' (6с без хода времени) — самолечение №'+stallN);",
    "    NJ('плеер','поток встал на '+fmtT(tpos)+' ('+(need/1000)+'с без хода времени) — самолечение №'+stallN);",
    'вочдог: честное окно в логе')

# ── P5: перезарядка = новая эпоха вочдога ───────────────────────────────────
rep("    window.__plHeal.reload++;",
    """    window.__plHeal.reload++;
    stallReset();                                     /* 58: перезарядка = новая эпоха вочдога,
      иначе «перезарядка к 0:00» ниже stallPos не считалась прогрессом — шторм №1/№2/№3 */""",
    'reloadActiveTo: stallReset')

# ── P6: visibilitychange — гейт mute в фон + честный push + возврат ─────────
rep("""    else{ try{ if(NATV)natvMediaPush(true) }catch(e){} }   /* 56: ушли в фон играющими — состояние
                                      наружу (оболочка поднимет/обновит медиа-сервис,
                                      шторка получает честную позицию и заголовок) */""",
    """    else{
      /* 58: гейт «звук после первого кадра» снимаем ПРИ уходе в фон: rVFC в скрытой
         странице не прийдёт (кадры не презентуются), гейт держал бы элемент muted —
         а muted-видео Chromium в скрытой вкладке гасит легально (энергосбережение).
         Ровно это порождало шторм «пауза↔играем» ~30Гц, слышный как заикание */
      try{ if(NATV)sndGateDrop(playToken) }catch(e){}
      try{ if(NATV)natvMediaPush(!video.paused) }catch(e){}   /* 56→58: честное состояние наружу
                                      (оболочка поднимет/обновит медиа-сервис,
                                      шторка получает честную позицию и заголовок) */
    }""",
    'фон: снятие гейта mute + честный push')

rep("""    try{ if(MIRROR.on&&!MIRROR.swapping&&vStandby&&!vStandby.paused)vStandby.pause() }catch(e){}
  }
  else{""",
    """    /* 58: эпоха фона — свежие счётчики: с чужой паузой воюем максимум 3 раза */
    bgTries=0; bgGaveUp=false; bgTryAt=0;
    bgWasPlaying=((bgLive||!video.paused))&&!userPaused&&!video.ended;
    try{ if(MIRROR.on&&!MIRROR.swapping&&vStandby&&!vStandby.paused)vStandby.pause() }catch(e){}
  }
  else{""",
    'фон: эпоха с чистыми счётчиками')

rep("""    if(!video.paused)lockWake();
    try{ if(NATV)natvMediaPush(!video.paused) }catch(e){}   /* 56: вернулись на экран — оболочка""",
    """    if(!video.paused)lockWake();
    /* 58: система успела погасить элемент, пока мы в фоне — один play() СРАЗУ
       (жалоба: «10сек пауза, пока не продолжит»), без ожидания сердца/вочдога */
    if(NATV&&bgWasPlaying&&!userPaused&&video.paused&&video.src&&!video.ended){
      try{ bgPlayOnce('возврат на экран') }catch(e){}
    }
    bgTries=0; bgGaveUp=false; bgWasPlaying=false; bgHeartState=null;
    try{ if(NATV)natvMediaPush(!video.paused) }catch(e){}   /* 56: вернулись на экран — оболочка""",
    'возврат: мгновенный play + сброс эпохи')

# ── P7: сторож v2 — без войны ───────────────────────────────────────────────
rep("""/* ═══ 57: фоновый сторож — сворачивание НЕ ставит видео на паузу ═══
   Что бы ни гасило элемент в скрытой вкладке — Chromium (фоновое энергосбережение,
   потеря аудиофокуса) или система, — пауза, пришедшая НЕ через наши кнопки/шторку,
   отменяется немедленно. Признак «нашего»: вызов прошёл через обёртки play()/pause()
   (метка userPaused). Сырое video.pause() от Chromium — «чужое»: играем дальше,
   несколько попыток. MSE-мост и сон-таймер не трогаем (их паузы — намеренные). */
var userPaused=false;
function markUserPause(v){ userPaused=!!v }""",
    """/* ═══ 58: фоновый сторож v2 — БЕЗ «войны пауз» ═══
   v57 воевала с Chromium: его пауза в скрытой вкладке гасилась нашим мгновенным
   play() — шторм 30Гц (на слух — заикание), а muted-видео (гейт первого кадра)
   Chromium гасит в скрытой вкладке легально: война не могла кончиться. Теперь:
   * первая попытка сразу, дальше максимум 3 с шагом 700мс — заикания нет;
   * после 3 неудач — bgGaveUp: тишина до возврата на экран (там один play());
   * гейт mute снимается при уходе в фон (visibilitychange);
   * сердце фона шлёт только честное состояние и только по его смене.
   MSE-мост и сон-таймер не трогаем (их паузы — намеренные). */
var userPaused=false, bgLive=false, bgWasPlaying=false, bgGaveUp=false, bgTryAt=0, bgTries=0;
function markUserPause(v){ userPaused=!!v }""",
    'сторож v2: декларации')

rep("  if(userPaused||el.ended||!el.src||el.error)return true;/* юзер сам встал / конец / ошибка */",
    "  if(userPaused||bgGaveUp||el.ended||!el.src||el.error)return true;/* юзер/сдались/конец/ошибка */",
    'гейт: bgGaveUp')

rep("""document.addEventListener('pause',function(e){
  var el=e.target;
  if(bgPauseGated(el))return;
  NJ('фон','пауза в фоне не от юзера — возобновляем');
  (function retry(n){
    if(!document.hidden||el!==video||!el.paused||el.ended)return;
    var p=null; try{ p=el.play() }catch(e1){}
    if(p&&p.then)p.then(function(){
      if(!el.paused)NJ('фон','фон: играем дальше (попытка '+(n+1)+')');
    },function(){
      if(n<6)setTimeout(function(){ retry(n+1) },300+n*350);
      else NJ('фон','возобновление не вышло — возьмёт сердце фона/возврат на экран');
    });
  })(0);
},true);""",
    """function bgPlayOnce(why){
  var p=null; try{ p=video.play() }catch(e){}
  if(p&&p.then)p.then(function(){
    if(!video.paused){ bgTries=0; bgLive=true; NJ('фон','фон: играем дальше ('+why+')') }
  },function(){});
}
var bgRetryTimer=0;
function bgResumeTick(){                          /* 58: отложенная попытка — событие 'pause'
  может прийти ВНУТРИ кулдауна (система гасит мгновенно): перепланируем, а не ждём
  нового события (его может не быть) */
  if(bgRetryTimer){ clearTimeout(bgRetryTimer); bgRetryTimer=0 }
  if(bgPauseGated(video))return;
  var now=Date.now();
  var cd=700-(now-bgTryAt);
  if(cd>0){ bgRetryTimer=setTimeout(bgResumeTick,cd+30); return }
  bgTryAt=now; bgTries++;
  if(bgTries>3){
    bgGaveUp=true;
    NJ('фон','система гасит элемент ('+(bgTries-1)+' попыток) — не воюем: оживим на возврате');
    return;
  }
  NJ('фон','пауза в фоне не от юзера — пробуем дальше ('+bgTries+'/3)');
  bgPlayOnce('попытка '+bgTries);
}
document.addEventListener('pause',function(e){
  var el=e.target;
  if(bgPauseGated(el))return;
  bgResumeTick();                                 /* тик сам разберётся: сейчас или после кулдауна */
},true);""",
    'сторож v2: слушатель пауз + отложенный тик')

rep("""(function bgHeart(){                                /* 57: сердце фона — раз в ~10с: позиция в
  шторку (оболочка обновит медиа-сервис) + страховка сторожа, если событие pause
  потерялось. Обычный setTimeout: скрытая вкладка режет его до ~1с, для 10-секундного
  такта достаточно, впустую процесс не жжём ( audible-страница не попадает под
  интенсивный троттлинг) */
  setTimeout(function step(){
    try{
      if(NATV&&document.hidden){
        if(!video.paused)natvMediaPush(true);
        else if(!bgPauseGated(video)){ var pp=video.play(); if(pp&&pp.catch)pp.catch(function(){}) }
      }
    }catch(e){}
    setTimeout(step,10000);
  },4000);
})();""",
    """var bgHeartState=null;                             /* 58: прошлое состояние сердца — пушим по СМЕНЕ */
(function bgHeart(){                                /* 58: сердце фона — 5с: честная позиция в
  шторку, но ТОЛЬКО по смене состояния (сервис не перекладываем каждые 5с);
  play() сердце НЕ дёргает: дёрганье раз в 10с и было источником «10сек пауза,
  пока не продолжит». Обычный setTimeout: скрытая вкладка режет его до ~1с —
  для 5-секундного такта за глаза; audible-страница не попадает под
  интенсивный троттлинг */
  setTimeout(function step(){
    try{
      if(NATV&&document.hidden){
        var st=!video.paused;
        if(st!==bgHeartState){ bgHeartState=st; natvMediaPush(st) }
      }
    }catch(e){}
    setTimeout(step,5000);
  },4000);
})();""",
    'сердце фона: 5с, по смене, без play()')

io.open(DST, 'w', encoding='utf-8').write(html)
# ассет оболочки — то, что уедет в APK
io.open(ASSET, 'w', encoding='utf-8').write(html)
print('размер: %d байт (v57 был %d)' % (len(html.encode('utf-8')), os.path.getsize(SRC)))
print('OK →', DST)
print('OK →', ASSET)
