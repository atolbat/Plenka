#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v52 → v53:
  1) карточки: метка «медиатека телефона» убрана (все файлы такие — пользователь просил)
  2) кнопка фулскрина скрыта в андроид-сборках (NATV)
  3) подложка/постер — ТОЛЬКО первый кадр: серверная миниатюра с неизвестным/дальних
     временем кадра (жалоба на 4K: «сначала кадр с превью, потом прыжок на видео»)
     проверяется заголовком X-Plenka-FrameT; не первый — чистый чёрный
  4) сворачивание: setPipAuto только для ВИДЕО (аудио — фон без окна, как просили),
     в mediaState летит w/h для аспекта PiP-окна
  5) долгая перемотка видна как перемотка (спиннер через 180мс), не «зависло»
  6) ДИАГ: подсказка про стенд /seek; версия v53 / 3.7
  7) natvThumbUrl +f=2 — новая генерация миниатюр (лестница первых кадров на сервере)"""
import sys, io, os

SRC='/home/z/my-project/download/plenka-optimized-52.html'
DST='/home/z/my-project/download/plenka-optimized-53.html'

html=io.open(SRC,encoding='utf-8').read()

def rep(old,new,what,cnt=1):
    global html
    n=html.count(old)
    if n!=cnt:
        print('FAIL: якорь %r найден %d раз (ожидалось %d)'%(what,n,cnt)); sys.exit(1)
    html=html.replace(old,new)
    print('ok: %s'%what)

# ── P1: версия ──────────────────────────────────────────────────────────────
rep("s('версия','страница v52 / оболочка 3.5');",
    "s('версия','страница v53 / оболочка 3.7');",'версия')

# ── P2: ДИАГ — подсказка про стенд перемотки ────────────────────────────────
rep("""  try{s('NATV-флаг',fmt(window.NATV))}catch(e){}""",
    """  try{s('NATV-флаг',fmt(window.NATV))}catch(e){}
  try{ if(typeof window.PlenkaNative==='object')s('стенд перемотки','Chrome → http://127.0.0.1:8977/seek — файл из СПИСКА (айди искать не нужно); айди открытого видео — конец строки src=/v/<цифры> ниже в «элементы»') }catch(e){}""",
    'подсказка /seek в ДИАГ')

# ── P3: карточка без метки «медиатека телефона» ────────────────────────────
rep("""      +(it.kind==='native'?'<span style="color:var(--acc)">'+t(it.picked?'srcFile':'natvSrc')+'</span>':'')""",
    """      +(it.kind==='native'&&it.picked?'<span style="color:var(--acc)">'+t('srcFile')+'</span>':'')   /* 53: «медиатека телефона» не пишем — все файлы такие; метка осталась только у ручного выбора */""",
    'карточка: без метки медиатеки')

# ── P4: фулскрин-кнопка скрыта в андроид-сборках ────────────────────────────
rep("""body.pip #plenkaDiagBtn{display:none!important}        /* 2.4: кнопка диагностики в PiP не нужна */""",
    """body.pip #plenkaDiagBtn{display:none!important}        /* 2.4: кнопка диагностики в PiP не нужна */
body.natv #btnFs{display:none!important}                  /* 53: фулскрин-кнопка в андроид-сборках не нужна (просьба) — системное поведение и так полноэкранное */""",
    'CSS: #btnFs скрыт в natv')

# ── P5: подложка/постер — только первый кадр ────────────────────────────────
OLD_VBLANK='''var vblankEl=$('#vblank');
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
NEW_VBLANK='''var vblankEl=$('#vblank');
/* 53: первый ли кадр у постера? data: (fframe/fthumb — JS-снимки) — первый по построению.
   Серверная миниатюра /t/ — спрашиваем заголовком X-Plenka-FrameT (оболочка 3.7 отдаёт
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
  53: серверная миниатюра — только если она ДОКАЗАННО первый кадр (X-Plenka-FrameT);
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
function posterUpgrade(it,my){    /* 53: постер — только первый кадр. Вызывается ПОСЛЕ showPoster(null):
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
rep(OLD_VBLANK,NEW_VBLANK,'setVblank + posterFirstMs + posterUpgrade')

# ── P6: три точки показа постера → чёрный сразу, кадр после проверки ────────
OLD_A='''    if(!it.audio){ var psA=posterSrcOf(it);
      if(psA)showPoster(psA);
      else showPoster(null);   /* 31.4: уходящий активный (z3) — НАД подложкой (z2): прикрыть его
        может только постер (z4). Гася постер без кадра цели, оголяли замерший кадр прошлого
        видео на всё время загрузки. Без кадра — постер = непрозрачный чёрный (как подложка
        без изображения): переход пик-в-пик, снимается по доказанному кадру (hidePosterSoon) */
    }
    else hidePoster(true);'''
NEW_A='''    if(!it.audio){ showPoster(null); posterUpgrade(it,my); }   /* 53: чёрная маска сразу (31.4:
        уходящий кадр прикрыт), серверный кадр — только после подтверждения «первый»;
        чужой/дальний кадр с прыжком на видео больше не показываем */
    else hidePoster(true);'''
rep(OLD_A,NEW_A,'openItem: постер-А через проверку')

OLD_B='''    if(!it.audio&&!posterEl.hidden){ var ps8=posterSrcOf(it);
      if(ps8)showPoster(ps8);
      else showPoster(null); }   /* 31.4: без кадра цели постер остаётся чёрной маской над уходящим кадром */
    else hidePoster(true);'''
NEW_B='''    if(!it.audio&&!posterEl.hidden){ showPoster(null); posterUpgrade(it,my); }   /* 53: без кадра цели постер остаётся чёрной маской над уходящим кадром */
    else hidePoster(true);'''
rep(OLD_B,NEW_B,'openItem: постер-B через проверку')

OLD_C='''      if(!it.audio){ var ps9=posterSrcOf(it); if(ps9)showPoster(ps9); else showPoster(null); }   /* 31.4:
        досмотр длится секунды — уходящий кадр обязан быть прикрыт, хоть чёрным постером */'''
NEW_C='''      if(!it.audio){ showPoster(null); posterUpgrade(it,my); }   /* 53: досмотр прикрывает честный чёрный, дальний кадр не подставляем */'''
rep(OLD_C,NEW_C,'openItem: постер-C через проверку')

# ── P7: спиннер на долгой перемотке ─────────────────────────────────────────
rep("""VOn('waiting',function(){ $('#loadDot').classList.add('on') });""",
    """var seekSpinT=null;                                    /* 53: перемотка дольше 180мс видна как перемотка (точка-
  пульс), а не «всё зависло»; быстрые сики спиннер не мигают */
VOn('seeking',function(){ clearTimeout(seekSpinT); seekSpinT=setTimeout(function(){ try{$('#loadDot').classList.add('on')}catch(e){} },180) });
VOn('waiting',function(){ $('#loadDot').classList.add('on') });""",'спиннер перемотки: seeking')
rep("""VOn('seeked',function(){
  /* 24.8: после перемотки Chromium иногда «залипает» в HAVE_CURRENT_DATA: кадр стоит,""",
    """VOn('seeked',function(){
  clearTimeout(seekSpinT); try{ $('#loadDot').classList.remove('on') }catch(e){}   /* 53: перемотка закончилась — гасим спиннер */
  /* 24.8: после перемотки Chromium иногда «залипает» в HAVE_CURRENT_DATA: кадр стоит,""",
    'спиннер перемотки: seeked')

# ── P8: PiP — только для видео; аспект в mediaState ─────────────────────────
OLD_WAKE='''function natvWakePip(){ if(!NATV)return; try{
  var on=!!(video&&video.src&&!video.paused&&!video.ended);
  if(on===natvPipLast)return;      /* 2.4: мост дёргаем только при ИЗМЕНЕНИИ состояния —
                                      журнал не тонет в ежесекундном heartbeat */
  natvPipLast=on;
  natvCall('setPipAuto',on); natvCall('keepScreenOn',on);
  natvMediaPush(on);
}catch(e){} }'''
NEW_WAKE='''function natvWakePip(){ if(!NATV)return; try{
  var on=!!(video&&video.src&&!video.paused&&!video.ended);
  if(on===natvPipLast)return;      /* 2.4: мост дёргаем только при ИЗМЕНЕНИИ состояния —
                                      журнал не тонет в ежесекундном heartbeat */
  natvPipLast=on;
  var wi=(currentIdx>=0)?items[currentIdx]:null;
  var vid=on&&wi&&!wi.audio;       /* 53: сворачивание с ВИДЕО → окно PiP, видео продолжает
                                      играть ВИДИМО; сворачивание с АУДИО → фон без окна
                                      (звук продолжает, как и раньше) */
  natvCall('setPipAuto',vid); natvCall('keepScreenOn',on);
  natvMediaPush(on);
}catch(e){} }'''
rep(OLD_WAKE,NEW_WAKE,'natvWakePip: setPipAuto только для видео')

OLD_PUSH='''    natvCall('mediaState',JSON.stringify({playing:!!playing,
      pos:Math.round((video&&video.currentTime)||0),
      dur:((video&&isFinite(video.duration))?Math.round(video.duration):0),
      title:(it?fileNameOf(it):''), artist:((it&&it.meta&&it.meta.artist)||'')}));'''
NEW_PUSH='''    natvCall('mediaState',JSON.stringify({playing:!!playing,
      pos:Math.round((video&&video.currentTime)||0),
      dur:((video&&isFinite(video.duration))?Math.round(video.duration):0),
      w:((it&&it.w)||((video&&video.videoWidth)||0)), h:((it&&it.h)||((video&&video.videoHeight)||0)),
      title:(it?fileNameOf(it):''), artist:((it&&it.meta&&it.meta.artist)||'')}));   /* 53: w/h — аспект PiP-окна */'''
rep(OLD_PUSH,NEW_PUSH,'mediaState: + w/h')

# ── P9: миниатюры — генерация 2 (лестница первых кадров на сервере) ─────────
rep('''  return NATV_BASE+'/t/'+m.k+'/'+m.id+vq+(vq?'&':'?')+'r='+(m.s||0)+'-'+(m.t||0);''',
    '''  return NATV_BASE+'/t/'+m.k+'/'+m.id+vq+(vq?'&':'?')+'r='+(m.s||0)+'-'+(m.t||0)+'&f=2';   /* 53: f=2 — генерация 2 (лестница первых кадров), кэш браузера обновляется */''',
    'natvThumbUrl: +f=2')

io.open(DST,'w',encoding='utf-8').write(html)
print('размер: %d байт (v52 был %d)'%(len(html.encode('utf-8')),os.path.getsize(SRC)))
print('OK →',DST)
