#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v56 → v57: две задачи пользователя.

ЗАДАЧА 1 — «видео становится на паузу, как только я сворачиваю приложение».
WebView мы на паузу не ставили и раньше, но Chromium сам гасит элемент в
скрытой вкладке (фоновое энергосбережение / потеря аудиофокуса), и в 3.10
это выглядело как «свернул — встало». Лечение:
  * обёртки play()/pause() метят юзерское намерение (userPaused);
  * capture-сторож на событие 'pause': если элемент встал НЕ через наши
    кнопки/шторку (сырой video.pause() от Chromium/системы) — немедленно
    играем дальше, с повторами;
  * «сердце фона» раз в ~10с: позиция в медиа-сервис (шторка честная) +
    страховка сторожа, если событие потерялось;
  * в NATV переключатель «пауза при сворачивании» больше не действует и
    скрыт из настроек — сворачивание всегда = играем дальше.

ЗАДАЧА 2 — «крестик на карточке убирает видео, но после перезахода оно
снова в списке. Сделай отдельный реестр и кнопку в настройках вернуть
скрытые видео»:
  * реестр rmSet (id → {название, когда, тип}) в IDB kv 'rmreg' — переживает
    рестарты; скан медиатеки и picked-реестр больше не воскрешают убранное;
  * кнопка «вернуть скрытые видео» в настройках → шит со списком: вернуть
    по одному / вернуть все; nc:-файлы НЕ выпускаются из SAF-реестра при
    удалении — возврат работает и для них.
"""
import sys, io, os

SRC = '/home/z/my-project/download/plenka-optimized-56.html'
DST = '/home/z/my-project/download/plenka-optimized-57.html'

html = io.open(SRC, encoding='utf-8').read()

def rep(old, new, what, cnt=1):
    global html
    n = html.count(old)
    if n != cnt:
        print('FAIL: якорь %r найден %d раз (ожидалось %d)' % (what, n, cnt)); sys.exit(1)
    html = html.replace(old, new)
    print('ok: %s' % what)

# ── P1: версия ──────────────────────────────────────────────────────────────
rep("s('версия','страница v56 / оболочка 3.10');",
    "s('версия','страница v57 / оболочка 3.11');", 'версия v57/3.11')

# ── P2: обёртки игра/пауза метят юзерское намерение ─────────────────────────
rep("function play(){ if(!video.src)return; video.play().then(function(){},function(err){",
    "function play(){ if(!video.src)return; markUserPause(false); video.play().then(function(){},function(err){",
    'play(): метка «юзер хочет играть»')

rep("function pause(){ video.pause(); }",
    "function pause(){ markUserPause(true); video.pause(); }",
    'pause(): метка «юзер хочет паузу»')

# ── P3: NATV — сворачивание НИКОГДА не паузит ───────────────────────────────
rep("""    if(S.pauseOnHidden&&!video.paused)pause();   /* по умолчанию — как на ютубе: звук продолжается */""",
    """    if(S.pauseOnHidden&&!NATV&&!video.paused)pause();   /* 57: в нативе сворачивание всегда
                                      = играем дальше (задача юзера); в браузере — как на
                                      ютубе: звук продолжается */""",
    'pauseOnHidden: гейт NATV')

# ── P4: фоновый сторож + сердце фона ────────────────────────────────────────
rep("""    if(MIRROR.on&&!MIRROR.swapping)mirrorPump();   /* 25.9: зеркало снова в синхрон */
  }
});""",
    """    if(MIRROR.on&&!MIRROR.swapping)mirrorPump();   /* 25.9: зеркало снова в синхрон */
  }
});

/* ═══ 57: фоновый сторож — сворачивание НЕ ставит видео на паузу ═══
   Что бы ни гасило элемент в скрытой вкладке — Chromium (фоновое энергосбережение,
   потеря аудиофокуса) или система, — пауза, пришедшая НЕ через наши кнопки/шторку,
   отменяется немедленно. Признак «нашего»: вызов прошёл через обёртки play()/pause()
   (метка userPaused). Сырое video.pause() от Chromium — «чужое»: играем дальше,
   несколько попыток. MSE-мост и сон-таймер не трогаем (их паузы — намеренные). */
var userPaused=false;
function markUserPause(v){ userPaused=!!v }
function bgPauseGated(el){
  if(el!==video||!NATV||!document.hidden)return true;   /* не наш элемент / не фон */
  if(userPaused||el.ended||!el.src||el.error)return true;/* юзер сам встал / конец / ошибка */
  if(localStorage.getItem('plenka.pipMode')==='pip')return true;   /* видимое PiP-окно живёт по своим правилам */
  var b=null; try{ b=el._mseb }catch(e0){}
  if(b&&(b.techPaused||b.dead||(b.st&&(b.st.rebuilding||b.st.seekT!=null))))return true;   /* мост чинит себя сам */
  return false;
}
document.addEventListener('pause',function(e){
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
},true);
(function bgHeart(){                                /* 57: сердце фона — раз в ~10с: позиция в
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
    'сторож фона + сердце')

# ── P5: реестр убранных — глобально ─────────────────────────────────────────
rep("var hiddenSet={},hiddenView=false;        /* скрытый список: id → true; вход — особым жестом */",
    """var hiddenSet={},hiddenView=false;        /* скрытый список: id → true; вход — особым жестом */
var rmSet={};                            /* 57: реестр «убрано крестиком»: id → {n:название,a:когда,k:тип};
                                     переживает рестарты (IDB kv 'rmreg'); вернуть — из настроек */
function saveRm(){ idbPut('kv','rmreg',rmSet) }""",
    'rmSet + saveRm')

# ── P6: removeItem — писать в реестр, nc: не выпускать из SAF ───────────────
rep("""async function removeItem(it){
  items=items.filter(function(x){return x!==it});
  if(hiddenSet[it.id]){ delete hiddenSet[it.id]; saveHidden(); }""",
    """async function removeItem(it){
  items=items.filter(function(x){return x!==it});
  if(hiddenSet[it.id]){ delete hiddenSet[it.id]; saveHidden(); }
  rmSet[it.id]={n:it.name,a:Date.now(),k:it.kind}; saveRm();   /* 57: реестр — крестик больше
                                     не «временный»: после перезахода видео не возвращается,
                                     пока не вернёшь его кнопкой в настройках */""",
    'removeItem: запись в реестр')

rep("""  if(it.kind==='native'&&/^nc:/.test(it.id)){ try{ natvCall('unpick',parseInt(it.id.slice(3),10)) }catch(e){} }   /* native 2.1: ручной выбор — вычёркиваем из реестра оболочки */""",
    """  /* 57: nc: НЕ unpick — SAF-хэндл оставляем в реестре оболочки: скрытие держит
     rmSet, и «вернуть скрытые» работает без повторного выбора файла */""",
    'removeItem: nc: не выпускаем из SAF')

# ── P7: natvMerge — скан не воскрешает убранное ─────────────────────────────
rep("""    var key=m.k+':'+m.id, url=NATV_BASE+'/'+m.k+'/'+m.id+(m.vol?('?vol='+encodeURIComponent(m.vol)):'');   /* 2.1: вторичные тома (SD) — id различны на каждом томе */
    seen[key]=1;""",
    """    var key=m.k+':'+m.id, url=NATV_BASE+'/'+m.k+'/'+m.id+(m.vol?('?vol='+encodeURIComponent(m.vol)):'');   /* 2.1: вторичные тома (SD) — id различны на каждом томе */
    if(rmSet['n'+key])continue;   /* 57: убрано крестиком — в библиотеку не возвращается */
    seen[key]=1;""",
    'natvMerge: фильтр реестра')

# ── P8: natvMergePicked — то же для ручного выбора ──────────────────────────
rep("""    var id='nc:'+m.id, url=NATV_BASE+'/c/'+m.id;
    var it=byId[id];""",
    """    var id='nc:'+m.id, url=NATV_BASE+'/c/'+m.id;
    if(rmSet[id])continue;   /* 57: убрано крестиком — файл в SAF-реестре ждёт возврата */
    var it=byId[id];""",
    'natvMergePicked: фильтр реестра')

# ── P9: бут — реестр читаем параллельно, кэш IDB не воскрешает ──────────────
rep("""  var v,R=await Promise.all([                            /* стартовые чтения параллельно (были последовательно) */
    idbGet('kv','settings'), idbGet('kv','badlist'), idbGet('kv','hiddenlist'),
    idbAll('items'), idbGet('kv','folders'), idbGet('kv','playlists'), idbKeys('blobs'),
    idbKeys('handles') ]);""",
    """  var v,R=await Promise.all([                            /* стартовые чтения параллельно (были последовательно) */
    idbGet('kv','settings'), idbGet('kv','badlist'), idbGet('kv','hiddenlist'),
    idbAll('items'), idbGet('kv','folders'), idbGet('kv','playlists'), idbKeys('blobs'),
    idbKeys('handles'), idbGet('kv','rmreg') ]);""",
    'бут: чтение rmreg')

rep("""  try{
    var hl=R[2];
    if(hl&&hl.length)hl.forEach(function(id){ hiddenSet[id]=true });
  }catch(e){}""",
    """  try{
    var hl=R[2];
    if(hl&&hl.length)hl.forEach(function(id){ hiddenSet[id]=true });
  }catch(e){}
  try{                                              /* 57: реестр убранных крестиком */
    var rr=R[8];
    if(rr&&typeof rr==='object')for(var rk in rr)rmSet[rk]=rr[rk];
  }catch(e){}""",
    'бут: применение rmreg')

rep("        if(badSet[m.id]){ idbDel('items',m.id); continue; }",
    "        if(badSet[m.id]||rmSet[m.id]){ idbDel('items',m.id); continue; }   /* 57: убранные крестиком из кэша не воскрешают */",
    'бут: фильтр кэша IDB')

# ── P10: кнопка в настройках ────────────────────────────────────────────────
rep("""      <div class="row" id="natvRow" hidden><button class="btn sm" id="btnNatvRescan" data-i="natvRescan">обновить медиатеку</button></div>""",
    """      <div class="row" id="natvRow" hidden><button class="btn sm" id="btnNatvRescan" data-i="natvRescan">обновить медиатеку</button></div>
      <div class="row"><button class="btn sm" id="btnRmShow" data-i="rmShow">вернуть скрытые видео</button></div>   <!-- 57: реестр убранных крестиком -->""",
    'кнопка «вернуть скрытые»')

# ── P11: шит списка скрытых ─────────────────────────────────────────────────
rep("""  <div id="infoBody" style="padding:4px 18px 18px"></div>
</div>""",
    """  <div id="infoBody" style="padding:4px 18px 18px"></div>
</div>
<div class="sheet" id="rmSheet" aria-label="скрытые видео">
  <div class="sh-head"><h3 data-i="rmTitle">скрытые видео</h3>
    <button class="ibtn" id="rmClose"><svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
  </div>
  <div id="rmBody" style="padding:4px 18px 18px"></div>
</div>""",
    'rmSheet: разметка')

# ── P12: логика шита ────────────────────────────────────────────────────────
rep("""function closeInfo(){ $('#infoSheet').classList.remove('open'); if(!$('#pickSheet').classList.contains('open'))$('#sheetBack').classList.remove('open'); }
 $('#infoClose').addEventListener('click',closeInfo);""",
    """function closeInfo(){ $('#infoSheet').classList.remove('open'); if(!$('#pickSheet').classList.contains('open')&&!$('#rmSheet').classList.contains('open'))$('#sheetBack').classList.remove('open'); }
 $('#infoClose').addEventListener('click',closeInfo);
/* ═══ 57: реестр убранных крестиком — вернуть из настроек ═══ */
function rmCount(){ var n=0; for(var k in rmSet)n++; return n }
function rmLabelSync(){ try{ var b=$('#btnRmShow'); if(b)b.textContent=t('rmShow')+(rmCount()?(' ('+rmCount()+')'):''); }catch(e){} }
function rmCanRestore(id){ return /^n[va]:/.test(id)||/^nc:/.test(id) }   /* медиатека/SAF — скан вернёт; память браузера — увы */
function openRm(){
  var h='', ids=Object.keys(rmSet);
  if(!ids.length)h='<div class="pill" style="margin:10px 0">'+t('rmEmpty')+'</div>';
  else{
    ids.sort(function(a,b){ return (rmSet[b].a||0)-(rmSet[a].a||0) });
    if(ids.length>1)h+='<div class="row" style="margin:4px 0 10px"><button class="btn sm" id="rmAllBtn">'+t('rmRestoreAll')+' ('+ids.length+')</button></div>';
    ids.forEach(function(id){
      var r=rmSet[id]||{}, ok=rmCanRestore(id);
      h+='<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-top:1px solid var(--line)">'
        +'<span style="flex:1;min-width:0;font-size:11px;color:var(--tx);word-break:break-word">'+esc(r.n||id)
        +'<i style="display:block;color:var(--mut);font-style:normal;font-size:9px;margin-top:2px">'
        +((r.a?new Date(r.a).toLocaleDateString():'')+(ok?'':(' · '+t('rmGoneHint'))))+'</i></span>'
        +(ok?('<button class="btn sm" data-rmid="'+esc(id)+'">'+t('rmRestore')+'</button>'):'')
        +'</div>';
    });
  }
  $('#rmBody').innerHTML=h;
  $('#rmSheet').classList.add('open'); $('#sheetBack').classList.add('open');
  var all=$('#rmAllBtn');
  if(all)all.addEventListener('click',function(){
    var n=0; Object.keys(rmSet).forEach(function(id){ if(rmCanRestore(id))n++; delete rmSet[id] });
    saveRm(); rmAfterRestore(n);
  });
  $$('#rmBody [data-rmid]').forEach(function(b){
    b.addEventListener('click',function(){
      var id=b.getAttribute('data-rmid');
      if(rmSet[id]){ delete rmSet[id]; saveRm() }
      rmAfterRestore(1);
    });
  });
}
function rmAfterRestore(n){
  rmLabelSync();
  try{ if(NATV){ nativeSync(false); natvPickedSync(false) } }catch(e){}   /* скан вернёт убранное из медиатеки/SAF */
  renderLib(); renderStrip();
  closeRm();
  toast(t('rmRestoredN',{n:n}));
}
function closeRm(){ $('#rmSheet').classList.remove('open'); if(!$('#pickSheet').classList.contains('open')&&!$('#infoSheet').classList.contains('open'))$('#sheetBack').classList.remove('open'); }
 $('#rmClose').addEventListener('click',closeRm);
 $('#btnRmShow').addEventListener('click',openRm);""",
    'rmSheet: логика')

# ── P13: общий closeSheet гасит и rmSheet ───────────────────────────────────
rep("""function closeSheet(){
  $('#pickSheet').classList.remove('open'); $('#infoSheet').classList.remove('open');
  $('#sheetBack').classList.remove('open');
}""",
    """function closeSheet(){
  $('#pickSheet').classList.remove('open'); $('#infoSheet').classList.remove('open'); $('#rmSheet').classList.remove('open');
  $('#sheetBack').classList.remove('open');
}""",
    'closeSheet: rmSheet')

# ── P14: системный «назад» закрывает и наш шит ──────────────────────────────
rep("""    if($('#infoSheet').classList.contains('open')){ $('#infoClose').click(); return 'ui'; }""",
    """    if($('#rmSheet').classList.contains('open')){ $('#rmClose').click(); return 'ui'; }   /* 57 */
    if($('#infoSheet').classList.contains('open')){ $('#infoClose').click(); return 'ui'; }""",
    'назад: rmSheet')

# ── P15: счётчик на кнопке при открытии настроек ────────────────────────────
rep(" $('#btnLibSettings').addEventListener('click',function(){ openDrawer('#settingsDrawer') });",
    """ $('#btnLibSettings').addEventListener('click',function(){ rmLabelSync(); openDrawer('#settingsDrawer') });   /* 57: счётчик скрытых на кнопке */""",
    'настройки: счётчик')

# ── P16: NATV — переключатель «пауза при сворачивании» скрыт ────────────────
rep("""      $('#optFiles').hidden=true; $('#optFolder').hidden=true;
      $('#pwaNote').hidden=true;""",
    """      $('#optFiles').hidden=true; $('#optFolder').hidden=true;
      $('#pwaNote').hidden=true;
      try{ var poh=$('[data-sw="pauseOnHidden"]'); if(poh&&poh.closest('.row'))poh.closest('.row').hidden=true; }catch(e2){}   /* 57: сворачивание всегда = играем */""",
    'NATV: ряд pauseOnHidden скрыт')

# ── P17: i18n ───────────────────────────────────────────────────────────────
rep(" removedLib:'убрано из библиотеки',",
    """ removedLib:'убрано из библиотеки',
 rmShow:'вернуть скрытые видео', rmTitle:'скрытые видео',
 rmEmpty:'пусто: видео, убранные крестиком на карточке, попадают сюда и не возвращаются в библиотеку сами',
 rmRestoreAll:'вернуть все', rmRestore:'вернуть',
 rmRestoredN:'вернуто в библиотеку: {n}',
 rmGoneHint:'источник удалён из памяти — добавьте файл заново',""",
    'i18n ru')

rep(" removedLib:'removed from library',",
    """ removedLib:'removed from library',
 rmShow:'restore hidden videos', rmTitle:'hidden videos',
 rmEmpty:'empty: videos removed with the card cross land here and never come back on their own',
 rmRestoreAll:'restore all', rmRestore:'restore',
 rmRestoredN:'restored to library: {n}',
 rmGoneHint:'source dropped from browser storage — add the file again',""",
    'i18n en')

io.open(DST, 'w', encoding='utf-8').write(html)
print('размер: %d байт (v56 был %d)' % (len(html.encode('utf-8')), os.path.getsize(SRC)))
print('OK →', DST)
