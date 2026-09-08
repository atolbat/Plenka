#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v51 → v55 (возврат к базе 3.6 + удачные правки поздних версий).

БАЗА: plenka-optimized-51.html — вытащена из вложений чата (пара оболочки 3.6,
«самая удачная версия» по пользователю). MSE-мост, карта якорей, самолечение
сика, webgen-обложки — всё из v51 НЕ трогаем.

Портируем ТОЛЬКО удачные правки v53/v54:
  1) карточки: метка «медиатека телефона» убрана (осталась «файл с диска» у picked)
  2) кнопка фулскрина скрыта в андроид-сборках (NATV)
  3) подложка/постер — только подтверждённый ПЕРВЫЙ кадр (X-Plenka-FrameT),
     иначе честный чёрный (жалоба на 4K «превью → прыжок»)
  4) сворачивание: setPipAuto только для ВИДЕО, в mediaState летит w/h (аспект PiP)
  5) долгая перемотка видна как перемотка (спиннер 180мс)
  6) resume-гейт 5с → 15с (лаги от rescan-шторма при PiP-циклах)
  7) natvThumbUrl + f=3 — кэш-бастер (устройство помнит t_-обложки 3.6 и t2_ 3.7)
  8) вочдоги v54 (сик завис / поток встал) — ТОЛЬКО для нативного потока:
     элемент на MSE-мосту (video._mseb) лечится СВОЕЙ машинерией v51,
     перезарядка blob:-src убила бы мост
  9) версия v55 / оболочка 3.9, ДИАГ: строка самолечения
"""
import sys, io, os

SRC = '/home/z/my-project/scripts/from_chat_plenka-optimized-51.html'
DST = '/home/z/my-project/download/plenka-optimized-55.html'

html = io.open(SRC, encoding='utf-8').read()

def rep(old, new, what, cnt=1):
    global html
    n = html.count(old)
    if n != cnt:
        print('FAIL: якорь %r найден %d раз (ожидалось %d)' % (what, n, cnt)); sys.exit(1)
    html = html.replace(old, new)
    print('ok: %s' % what)

# ── P1: версия ──────────────────────────────────────────────────────────────
rep("s('версия','страница v51 / оболочка 3.6');",
    "s('версия','страница v55 / оболочка 3.9');", 'версия')

# ── P2: карточка без метки «медиатека телефона» ────────────────────────────
rep("""      +(it.kind==='native'?'<span style="color:var(--acc)">'+t(it.picked?'srcFile':'natvSrc')+'</span>':'')""",
    """      +(it.kind==='native'&&it.picked?'<span style="color:var(--acc)">'+t('srcFile')+'</span>':'')   /* 55: «медиатека телефона» не пишем — все файлы такие; метка осталась только у ручного выбора */""",
    'карточка: без метки медиатеки')

# ── P3: фулскрин-кнопка скрыта в андроид-сборках ────────────────────────────
rep("""body.pip #plenkaDiagBtn{display:none!important}        /* 2.4: кнопка диагностики в PiP не нужна */""",
    """body.pip #plenkaDiagBtn{display:none!important}        /* 2.4: кнопка диагностики в PiP не нужна */
body.natv #btnFs{display:none!important}                  /* 55: фулскрин-кнопка в андроид-сборках не нужна (просьба) — системное поведение и так полноэкранное */""",
    'CSS: #btnFs скрыт в natv')

# ── P4: подложка/постер — только первый кадр ────────────────────────────────
OLD_VBLANK = '''var vblankEl=$('#vblank');
function setVblank(it){    /* 30.1: подложка на цель — первый кадр вписан в чёрный. НИКОГДА не
  прячется и не гасится таймером: видео (z3) перекрывает её (z2) само. Нет кадра — честный
  чистый чёрный; аудио — чистый чёрный под арт-сценой. Любой момент снятия постера открывает
  ИДЕНТИЧНУЮ картинку — переход пик-в-пик, мигание невозможно по построению */
  try{
    if(!vblankEl)return;
    var src=(it&&!it.audio)?posterSrcOf(it):null;
    vblankEl.style.backgroundImage=src?('url("'+src+'")'):'';
  }catch(e){}
}'''
NEW_VBLANK = '''var vblankEl=$('#vblank');
/* 55: первый ли кадр у постера? data: (fframe/fthumb — JS-снимки) — первый по построению.
   Серверная миниатюра /t/ — спрашиваем заголовком X-Plenka-FrameT (оболочка 3.7+ отдаёт
   мс от старта; дальние кадры помечены sentinel). Ответ кэшируется по URL. */
var thumbFirstT={}, thumbFirstPend={};
function posterFirstMs(src,cb){
  if(!src){ cb(-1); return }
  if(src.indexOf('data:')===0){ cb(0); return }
  if(src in thumbFirstT){ cb(thumbFirstT[src]); return }
  if((src.indexOf(NATV_BASE)!==0)&&(src.indexOf('/t/')<0)){ cb(0); return }   /* не серверная — считаем своим снимком */
  if(thumbFirstPend[src]){ thumbFirstPend[src].push(cb); return }              /* запрос уже летит — подвешиваемся */
  var q=[cb]; thumbFirstPend[src]=q;
  var fin=function(ms){ var arr=thumbFirstPend[src]||[]; delete thumbFirstPend[src];
    thumbFirstT[src]=ms; for(var i=0;i<arr.length;i++)try{arr[i](ms)}catch(e){} };
  var ac=null;
  try{ ac=new AbortController(); setTimeout(function(){ try{ac.abort()}catch(e){} },1600) }catch(e){}
  fetch(src,{cache:'force-cache',signal:ac?ac.signal:undefined}).then(function(r){
    var ft=3600000;                                    /* нет заголовка/не JSON — считаем НЕ первым: чёрный честнее чужого кадра */
    try{ var h=r.headers.get('X-Plenka-FrameT'); if(h!==null){ var v=+h; if(isFinite(v))ft=Math.max(0,v) } }catch(e){}
    fin(ft)
  },function(){ fin(3600000) })
}
var POSTER_FIRST_MS=250;                                /* ≤250мс от старта = «первый кадр» (лестница сервера: 0/16/50/150мс) */
function setVblank(it){    /* 30.1: подложка на цель — первый кадр вписан в чёрный. НИКОГДА не
  прячется и не гасится таймером: видео (z3) перекрывает её (z2) само. Нет кадра — честный
  чистый чёрный; аудио — чистый чёрный под арт-сценой. Любой момент снятия постера открывает
  ИДЕНТИЧНУЮ картинку — переход пик-в-пик, мигание невозможно по построению.
  55: серверная миниатюра — только если она ДОКАЗАННО первый кадр (X-Plenka-FrameT);
  иначе чистый чёрный: «кадр с превью, потом прыжок» больше не показываем */
  try{
    if(!vblankEl)return;
    var src=(it&&!it.audio)?posterSrcOf(it):null;
    if(!src){ vblankEl.style.backgroundImage=''; return }
    if(src.indexOf('data:')===0){ vblankEl.style.backgroundImage='url("'+src+'")'; return }
    vblankEl._tok=(vblankEl._tok||0)+1; var my=vblankEl._tok;
    vblankEl.style.backgroundImage='';
    posterFirstMs(src,function(ms){
      if(my!==vblankEl._tok)return;                    /* цель уже сменилась — чужой кадр не подставляем */
      if(ms<=POSTER_FIRST_MS)vblankEl.style.backgroundImage='url("'+src+'")';
    })
  }catch(e){}
}
function posterUpgrade(it,my){    /* 55: постер — только первый кадр. Вызывается ПОСЛЕ showPoster(null):
  экран уже прикрыт честным чёрным; серверную миниатюру подставляем лишь после подтверждения */
  try{
    var ps=(!it||it.audio)?null:posterSrcOf(it);
    if(!ps)return;
    if(ps.indexOf('data:')===0){ showPoster(ps); return }
    posterFirstMs(ps,function(ms){
      if(my!=null&&my!==playToken)return;              /* открытие перебито — постер принадлежит новому */
      if(ms<=POSTER_FIRST_MS)showPoster(ps);
    })
  }catch(e){}
}'''
rep(OLD_VBLANK, NEW_VBLANK, 'setVblank + posterFirstMs + posterUpgrade')

# ── P5: три точки показа постера → чёрный сразу, кадр после проверки ────────
OLD_A = '''    if(!it.audio){ var psA=posterSrcOf(it);
      if(psA)showPoster(psA);
      else showPoster(null);   /* 31.4: уходящий активный (z3) — НАД подложкой (z2): прикрыть его
        может только постер (z4). Гася постер без кадра цели, оголяли замерший кадр прошлого
        видео на всё время загрузки. Без кадра — постер = непрозрачный чёрный (как подложка
        без изображения): переход пик-в-пик, снимается по доказанному кадру (hidePosterSoon) */
    }
    else hidePoster(true);'''
NEW_A = '''    if(!it.audio){ showPoster(null); posterUpgrade(it,my); }   /* 55: чёрная маска сразу (31.4:
        уходящий кадр прикрыт), серверный кадр — только после подтверждения «первый»;
        чужой/дальний кадр с прыжком на видео больше не показываем */
    else hidePoster(true);'''
rep(OLD_A, NEW_A, 'openItem: постер-А через проверку')

OLD_B = '''    if(!it.audio&&!posterEl.hidden){ var ps8=posterSrcOf(it);
      if(ps8)showPoster(ps8);
      else showPoster(null); }   /* 31.4: без кадра цели постер остаётся чёрной маской над уходящим кадром */
    else hidePoster(true);'''
NEW_B = '''    if(!it.audio&&!posterEl.hidden){ showPoster(null); posterUpgrade(it,my); }   /* 55: без кадра цели постер остаётся чёрной маской над уходящим кадром */
    else hidePoster(true);'''
rep(OLD_B, NEW_B, 'openItem: постер-B через проверку')

OLD_C = '''      if(!it.audio){ var ps9=posterSrcOf(it); if(ps9)showPoster(ps9); else showPoster(null); }   /* 31.4:
        досмотр длится секунды — уходящий кадр обязан быть прикрыт, хоть чёрным постером */'''
NEW_C = '''      if(!it.audio){ showPoster(null); posterUpgrade(it,my); }   /* 55: досмотр прикрывает честный чёрный, дальний кадр не подставляем */'''
rep(OLD_C, NEW_C, 'openItem: постер-C через проверку')

# ── P6: спиннер на долгой перемотке ─────────────────────────────────────────
rep("""VOn('waiting',function(){ $('#loadDot').classList.add('on') });""",
    """var seekSpinT=null;                                    /* 55: перемотка дольше 180мс видна как перемотка (точка-
  пульс), а не «всё зависло»; быстрые сики спиннер не мигают */
VOn('seeking',function(){ clearTimeout(seekSpinT); seekSpinT=setTimeout(function(){ try{$('#loadDot').classList.add('on')}catch(e){} },180) });
VOn('waiting',function(){ $('#loadDot').classList.add('on') });""", 'спиннер перемотки: seeking')

rep("""VOn('seeked',function(){
  /* 24.8: после перемотки Chromium иногда «залипает» в HAVE_CURRENT_DATA: кадр стоит,""",
    """VOn('seeked',function(){
  clearTimeout(seekSpinT); try{ $('#loadDot').classList.remove('on') }catch(e){}   /* 55: перемотка закончилась — гасим спиннер */
  /* 24.8: после перемотки Chromium иногда «залипает» в HAVE_CURRENT_DATA: кадр стоит,""",
    'спиннер перемотки: seeked')

# ── P7: PiP — только для видео; аспект в mediaState ─────────────────────────
OLD_WAKE = '''function natvWakePip(){ if(!NATV)return; try{
  var on=!!(video&&video.src&&!video.paused&&!video.ended);
  if(on===natvPipLast)return;      /* 2.4: мост дёргаем только при ИЗМЕНЕНИИ состояния —
                                      журнал не тонет в ежесекундном heartbeat */
  natvPipLast=on;
  natvCall('setPipAuto',on); natvCall('keepScreenOn',on);
  natvMediaPush(on);
}catch(e){} }'''
NEW_WAKE = '''function natvWakePip(){ if(!NATV)return; try{
  var on=!!(video&&video.src&&!video.paused&&!video.ended);
  if(on===natvPipLast)return;      /* 2.4: мост дёргаем только при ИЗМЕНЕНИИ состояния —
                                      журнал не тонет в ежесекундном heartbeat */
  natvPipLast=on;
  var wi=(currentIdx>=0)?items[currentIdx]:null;
  var vid=on&&wi&&!wi.audio;       /* 55: сворачивание с ВИДЕО → окно PiP, видео продолжает
                                      играть ВИДИМО; сворачивание с АУДИО → фон без окна
                                      (звук продолжает, как и раньше) */
  natvCall('setPipAuto',vid); natvCall('keepScreenOn',on);
  natvMediaPush(on);
}catch(e){} }'''
rep(OLD_WAKE, NEW_WAKE, 'natvWakePip: setPipAuto только для видео')

OLD_PUSH = '''    natvCall('mediaState',JSON.stringify({playing:!!playing,
      pos:Math.round((video&&video.currentTime)||0),
      dur:((video&&isFinite(video.duration))?Math.round(video.duration):0),
      title:(it?fileNameOf(it):''), artist:((it&&it.meta&&it.meta.artist)||'')}));
'''
NEW_PUSH = '''    natvCall('mediaState',JSON.stringify({playing:!!playing,
      pos:Math.round((video&&video.currentTime)||0),
      dur:((video&&isFinite(video.duration))?Math.round(video.duration):0),
      w:((it&&it.w)||((video&&video.videoWidth)||0)), h:((it&&it.h)||((video&&video.videoHeight)||0)),
      title:(it?fileNameOf(it):''), artist:((it&&it.meta&&it.meta.artist)||'')}));   /* 55: w/h — аспект PiP-окна */
'''
rep(OLD_PUSH, NEW_PUSH, 'mediaState: + w/h')

# ── P8: миниатюры — кэш-бастер f=3 ──────────────────────────────────────────
rep('''  return NATV_BASE+'/t/'+m.k+'/'+m.id+vq+(vq?'&':'?')+'r='+(m.s||0)+'-'+(m.t||0);''',
    '''  return NATV_BASE+'/t/'+m.k+'/'+m.id+vq+(vq?'&':'?')+'r='+(m.s||0)+'-'+(m.t||0)+'&f=3';   /* 55: f=3 — кэш-бастер: браузер устройства помнит обложки 3.6 (t_) и 3.7 (t2_) — перезагружаем */''',
    'natvThumbUrl: +f=3')

# ── P9: resume — гейт 15с вместо 5с ────────────────────────────────────────
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
  if(now-natvResAt<15000){                       /* 55: авто-PiP будит активность каждые 5-8с, и КАЖДЫЙ
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

# ── P10: сик-вочдог (только нативный поток, MSE лечится сам) ────────────────
rep('''var seekSpinT=null;                                    /* 55: перемотка дольше 180мс видна как перемотка (точка-
  пульс), а не «всё зависло»; быстрые сики спиннер не мигают */
VOn('seeking',function(){ clearTimeout(seekSpinT); seekSpinT=setTimeout(function(){ try{$('#loadDot').classList.add('on')}catch(e){} },180) });
VOn('waiting',function(){ $('#loadDot').classList.add('on') });''',
    '''var seekSpinT=null;                                    /* 55: перемотка дольше 180мс видна как перемотка (точка-
  пульс), а не «всё зависло»; быстрые сики спиннер не мигают */
window.__plHeal={reload:0,seek:0,stall:0};             /* 55: счётчики самолечения — строка в ДИАГ */
var seekStuckT=null, seekStuckN=0;
VOn('seeking',function(){
  clearTimeout(seekSpinT); seekSpinT=setTimeout(function(){ try{$('#loadDot').classList.add('on')}catch(e){} },180);
  clearTimeout(seekStuckT);
  seekStuckT=setTimeout(function(){                  /* 55: сик-вочдог. Нативный поток иногда умирает после
    перемотки МОЛЧА: один Range-запрос и тишина, error-события нет. 3с нет кадра у цели →
    перезарядка элемента К ЦЕЛИ. MSE-мост НЕ трогаем: у него своя машина лечения
    («не сел за 6с» → пересборка), перезарядка blob:-src мост убила бы */
    seekStuckT=null;
    try{
      if(!video.src||!video.seeking||video.error||video.ended)return;
      if(video.readyState>=2)return;                /* кадр у цели есть — доматывает сам, не лечим */
      if(video._mseb)return;                        /* элемент на MSE-мосту — лечится сам, пропускаем */
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
  clearTimeout(seekSpinT); try{ $('#loadDot').classList.remove('on') }catch(e){}   /* 55: перемотка закончилась — гасим спиннер */''',
    '''VOn('seeked',function(){
  clearTimeout(seekSpinT); try{ $('#loadDot').classList.remove('on') }catch(e){}   /* 55: перемотка закончилась — гасим спиннер */
  clearTimeout(seekStuckT); seekStuckN=0;             /* 55: сик сел — вочдог снят */''',
    'seeked: сброс сик-вочдога')

# ── P11: перезарядка + поток-вочдог (MSE-гейт) ──────────────────────────────
rep('''VOn('canplay',function(){ $('#loadDot').classList.remove('on') });''',
    '''/* ═══ 55: самолечение НАТИВНОГО потока (не MSE) ═══
   Две беды проходят БЕЗ error-события: (а) сик повис — элемент ждёт данные, которые
   не приходят; (б) «играющий» поток встал — время не идёт, кадр замер. Лечение одно:
   перезарядка элемента К ТОЙ ЖЕ позиции — сервер отдаёт Range мгновенно, moov уже
   в кэше, вход быстрый; плей/пауза и открытый файл сохраняются. Элементы MSE-моста
   исключены (у моста свои вочдоги v51), открытие другого файла отменяет лечение */
function reloadActiveTo(tgt){
  try{
    if(video._mseb){ NJ('плеер','самолечение: элемент на MSE-мосту — пропускаем (мост лечится сам)'); return }
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
setInterval(function(){                               /* 55: поток-вочдог: пауз нет, а время 6с стоит */
  try{
    if(player.hidden||!video.src||video.paused||video.ended||video.error||video.seeking)return;
    if(video._mseb)return;                            /* MSE-мост следит за буфером сам (v51) */
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

# ── P12: ДИАГ — строка самолечения ──────────────────────────────────────────
rep('''  try{s('NATV-флаг',fmt(window.NATV))}catch(e){}''',
    '''  try{s('NATV-флаг',fmt(window.NATV))}catch(e){}
  try{ if(window.__plHeal)s('самолечение','перезарядок: '+window.__plHeal.reload+' · сиков зависло: '+window.__plHeal.seek+' · потоков встало: '+window.__plHeal.stall) }catch(e){}''',
    'ДИАГ: самолечение')

# ── P13: i18n ───────────────────────────────────────────────────────────────
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
print('размер: %d байт (v51 был %d)' % (len(html.encode('utf-8')), os.path.getsize(SRC)))
print('OK →', DST)
