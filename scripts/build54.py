#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v53 → v54 (оболочка 3.8). Регрессы из репорта:
  1) «лаги» — __plenkaResume на PiP-циклах (каждые 5-8с) гонял полный скан+мерж;
     гейт 5с → 15с: частые возвраты только тикают вочдог;
  2) «длинное видео не работает, не говоря о перемотке» — нативный поток молча
     умирает после сика/в PiP-циклах: один Range-запрос и тишина, БЕЗ error-события
     (в 3.6 лечил MSE-мост своими вочдогами, нативному их не было). Ставим два:
     • сик-вочдог: 3с нет кадра у цели → перезарядка элемента К ЦЕЛИ (≤2 попытки),
       плей/пауза сохраняются, всё пишется в журнал («самолечение»);
     • поток-вочдог: «играет», а время 6с стоит → та же перезарядка;
     счётчики самолечения — отдельной строкой в ДИАГ;
  3) версия v54 / 3.8."""
import sys, io, os

SRC = '/home/z/my-project/download/plenka-optimized-53.html'
DST = '/home/z/my-project/download/plenka-optimized-54.html'

html = io.open(SRC, encoding='utf-8').read()

def rep(old, new, what, cnt=1):
    global html
    n = html.count(old)
    if n != cnt:
        print('FAIL: якорь %r найден %d раз (ожидалось %d)' % (what, n, cnt)); sys.exit(1)
    html = html.replace(old, new)
    print('ok: %s' % what)

# ── P1: версия ──────────────────────────────────────────────────────────────
rep("s('версия','страница v53 / оболочка 3.7');",
    "s('версия','страница v54 / оболочка 3.8');", 'версия')

# ── P2: resume — гейт 15с вместо 5с ────────────────────────────────────────
rep('''var natvResAt=0;
window.__plenkaResume=function(){                    /* возврат в приложение: право могли выдать в настройках */
  if(!NATV)return 'nonatv';
  var now=Date.now(); if(now-natvResAt<5000)return 'gate'; natvResAt=now;
  NJ('стр','__plenkaResume — возврат в приложение, синк + тик вочдога');
  natvRepair('возврат в приложение');       /* 2.4: PiP мог побить мост — лечим ДО синка */
  nativeSync(false); natvPickedSync(false);
  try{ if(!items.length)natvWatchdog(); }catch(e){}
  return 'ok';
};''',
    '''var natvResAt=0;
window.__plenkaResume=function(){                    /* возврат в приложение: право могли выдать в настройках */
  if(!NATV)return 'nonatv';
  var now=Date.now();
  if(now-natvResAt<15000){                       /* 54: авто-PiP будит активность каждые 5-8с, и КАЖДЫЙ
    возврат гонял полный скан+мерж — это и были «лаги». Гейт 15с: часто вернулись —
    только тик вочдога, медиатека за секунды измениться не могла */
    if(!items.length){ try{ natvWatchdog(); }catch(e){} }
    return 'gate15';
  }
  natvResAt=now;
  NJ('стр','__plenkaResume — возврат в приложение, синк + тик вочдога');
  natvRepair('возврат в приложение');       /* 2.4: PiP мог побить мост — лечим ДО синка */
  nativeSync(false); natvPickedSync(false);
  try{ if(!items.length)natvWatchdog(); }catch(e){}
  return 'ok';
};''',
    'resume: гейт 15с')

# ── P3: сик-вочдог + перезарядка элемента + поток-вочдог ───────────────────
rep('''var seekSpinT=null;                                    /* 53: перемотка дольше 180мс видна как перемотка (точка-
  пульс), а не «всё зависло»; быстрые сики спиннер не мигают */
VOn('seeking',function(){ clearTimeout(seekSpinT); seekSpinT=setTimeout(function(){ try{$('#loadDot').classList.add('on')}catch(e){} },180) });
VOn('waiting',function(){ $('#loadDot').classList.add('on') });''',
    '''var seekSpinT=null;                                    /* 53: перемотка дольше 180мс видна как перемотка (точка-
  пульс), а не «всё зависло»; быстрые сики спиннер не мигают */
window.__plHeal={reload:0,seek:0,stall:0};             /* 54: счётчики самолечения — строка в ДИАГ */
var seekStuckT=null, seekStuckN=0;
VOn('seeking',function(){
  clearTimeout(seekSpinT); seekSpinT=setTimeout(function(){ try{$('#loadDot').classList.add('on')}catch(e){} },180);
  clearTimeout(seekStuckT);
  seekStuckT=setTimeout(function(){                  /* 54: сик-вочдог. Нативный поток иногда умирает после
    перемотки МОЛЧА: один Range-запрос и тишина, error-события нет — «чёрный экран,
    думал что зависло». 3с нет кадра у цели → перезарядка элемента К ЦЕЛИ (как
    самолечение MSE-моста в 3.6, только для нативного потока) */
    seekStuckT=null;
    try{
      if(!video.src||!video.seeking||video.error||video.ended)return;
      if(video.readyState>=2)return;                /* кадр у цели есть — доматывает сам, не лечим */
      var tgt=video.currentTime||0;
      seekStuckN++; window.__plHeal.seek++;
      NJ('плеер','сик '+fmtT(tgt)+' не садится 3с — самолечение №'+seekStuckN+': перезарядка элемента к цели');
      if(seekStuckN<=2)reloadActiveTo(tgt);
      else{ seekStuckN=0; toast(t('seekStuck'),'err'); }
    }catch(e){}
  },3000);
});
VOn('waiting',function(){ $('#loadDot').classList.add('on') });''',
    'сик-вочдог')

rep('''VOn('seeked',function(){
  clearTimeout(seekSpinT); try{ $('#loadDot').classList.remove('on') }catch(e){}   /* 53: перемотка закончилась — гасим спиннер */''',
    '''VOn('seeked',function(){
  clearTimeout(seekSpinT); try{ $('#loadDot').classList.remove('on') }catch(e){}   /* 53: перемотка закончилась — гасим спиннер */
  clearTimeout(seekStuckT); seekStuckN=0;             /* 54: сик сел — вочдог снят */''',
    'seeked: сброс сик-вочдога')

rep('''VOn('canplay',function(){ $('#loadDot').classList.remove('on') });''',
    '''/* ═══ 54: самолечение нативного потока ═══
   Две беды проходят БЕЗ error-события: (а) сик повис — элемент ждёт данные, которые
   не приходят; (б) «играющий» поток встал — время не идёт, кадр замер (после
   PiP-циклов/сбоя конвейера). Лечение одно: перезарядка элемента К ТОЙ ЖЕ позиции —
   сервер отдаёт Range мгновенно, moov уже в кэше, вход быстрый; плей/пауза и
   открытый файл сохраняются. Открытие другого файла отменяет лечение (playToken) */
function reloadActiveTo(tgt){
  try{
    var u=video.currentSrc||video.src;
    if(!u)return;
    var wasPlay=!video.paused;
    var my=playToken;
    window.__plHeal.reload++;
    try{ video.pause() }catch(e){}
    try{ natvPfCache={} }catch(e){}                  /* кэш префлайта не должен врать после сбоя */
    video.src=u; try{ video.load() }catch(e){}
    var done=false;
    var meta=function(){
      if(done)return; done=true;
      try{ video.removeEventListener('loadedmetadata',meta) }catch(e){}
      if(my!==playToken)return;                      /* открыли другое — лечение отменено */
      try{ video.currentTime=tgt }catch(e){}
      var sk=function(){
        try{ video.removeEventListener('seeked',sk) }catch(e){}
        if(my!==playToken)return;
        NJ('плеер','самолечение: перезарядка к '+fmtT(tgt)+' прошла — поток жив');
        if(wasPlay){ playIntent='ctl'; play(); }
      };
      video.addEventListener('seeked',sk);
      setTimeout(sk,1500);                            /* seeked мог прийти до подписки — страховка */
    };
    video.addEventListener('loadedmetadata',meta);
    setTimeout(function(){ if(!done&&video.readyState>=1)meta() },2500);   /* метаданные могли уже быть в кэше */
  }catch(e){ NJ('плеер','самолечение упало: '+e.message) }
}
var stallPos=-1, stallN=0, stallT=0;
setInterval(function(){                               /* 54: поток-вочдог: пауз нет, а время 6с стоит */
  try{
    if(player.hidden||!video.src||video.paused||video.ended||video.error||video.seeking)return;
    var it=(currentIdx>=0)?items[currentIdx]:null;
    if(!it||it.kind!=='native')return;               /* только нативный поток: блобы/ссылки лечит их хозяин */
    var tpos=video.currentTime;
    if(tpos>stallPos+0.05){ stallPos=tpos; stallT=Date.now(); if(stallN)stallN=0; return }
    if(!stallT){ stallT=Date.now(); stallPos=tpos; return }
    if(Date.now()-stallT<6000)return;
    stallN++; window.__plHeal.stall++;
    NJ('плеер','поток встал на '+fmtT(tpos)+' (6с без хода времени) — самолечение №'+stallN);
    if(stallN<=2)reloadActiveTo(tpos);
    else{ stallN=0; try{ pause() }catch(e){} toast(t('streamStuck'),'err'); }
  }catch(e){}
},1000);
VOn('canplay',function(){ $('#loadDot').classList.remove('on') });''',
    'перезарядка + поток-вочдог')

# ── P4: ДИАГ — строка самолечения ──────────────────────────────────────────
rep('''  try{s('NATV-флаг',fmt(window.NATV))}catch(e){}''',
    '''  try{s('NATV-флаг',fmt(window.NATV))}catch(e){}
  try{ if(window.__plHeal)s('самолечение','перезарядок: '+window.__plHeal.reload+' · сиков зависло: '+window.__plHeal.seek+' · потоков встало: '+window.__plHeal.stall) }catch(e){}''',
    'ДИАГ: самолечение')

# ── P5: i18n ───────────────────────────────────────────────────────────────
rep(''' natvOpenErr:'сервер не смог открыть файл ({w})',''',
    ''' natvOpenErr:'сервер не смог открыть файл ({w})',
 seekStuck:'перемотка не садится — поток сбит; попробуйте ещё раз',
 streamStuck:'поток остановился — поставлено на паузу',''',
    'i18n ru')

rep(''' natvOpenErr:'server could not open the file ({w})',''',
    ''' natvOpenErr:'server could not open the file ({w})',
 seekStuck:'seek is not settling — stream broken; try again',
 streamStuck:'stream stalled — paused',''',
    'i18n en')

io.open(DST, 'w', encoding='utf-8').write(html)
print('размер: %d байт (v53 был %d)' % (len(html.encode('utf-8')), os.path.getsize(SRC)))
print('OK →', DST)
