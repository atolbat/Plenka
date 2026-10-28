#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch67.py — страница v67 (оболочка 3.20).

Блок A. «Не та подложка» (жалоба юзера: под играющим видео проступает чужое
видео/кадр, особенно при разном aspect ratio) + остаточные гонки переключений:
  RC-101/HIGH  setVblank: токен _tok бампался только в remote-ветке — устаревший
               posterFirstMs-колбэк рисовал чужой кадр поверх играющего (ветки
               null/data: не инвалидались)
  VL-1/HIGH    в подложку/постер попадал карточный thumb 320×180 с запечённым
               леттербоксом (нет fframe) — при несовпадении аспектов его поля
               торчали из-под видео. Источник маски — только истинный аспект:
               fframe или серверная /t/ (докажет X-Plenka-FrameT)
  RC-102/HIGH  openItem: откат по устаревшему prevIdx (items мутирует за долгую
               загрузку) — подложка/профиль получали ЧУЖОЙ трек
  RC-103/HIGH  постер упавшей цели поднимался над возобновлённым треком
               (posterUpgrade гвардил только playToken, не владение открытием)
  RC-105/HIGH  ended с 800мс-окном: при загрузке цели дольше 800мс уходящий
               трек перескакивал через только что выбранный / переигрывался в
               loop='one' — замена на проверку владения (_pid ↔ currentIdx)
  VL-2/MED     кадр подложки жил весь сеанс трека: чистим в момент первого
               показанного кадра (killOld) и в mirrorStop — поля снова чёрные
  VL-3/MED     chase-PiP: freeze момента входа не снимался никем
  VL-4/MED     abort-ветка openItem: постер/freeze недооткрытой цели висели над
               возобновлённым треком
  VL-5/MED     chase: бокс Y (элемент окна) участвовал в гонке DOM-порядка
  RC-104/MED   mirrorOpen: catch-фолбэк без токен-гварда ретаргетил играющий
               элемент и перетирал подложку нового открытия; hudHoldId залипал
  RC-106/MED   MINI.tick: hudHoldId не сбрасывался — прогресс мини замирал
  RC-107/MED   openItem: бамп токена до валидации — тап по стухшему индексу
               убивал чужое открытие в полёте
  RC-108/MED   loadedmetadata писал длительность в чужой трек
  RC-109/LOW   3с-таймер 4К-релиза гасил элемент, уехавший в мини-панель
  VL-8/LOW     snapPoster писал в подложку мимо токена

Блок B. 3.20 «Открыть с помощью»: приёмник window.__plenkaExt — оболочка
  принимает ACTION_VIEW (аудио/видео из проводника/браузера/чужих приложений),
  раздаёт по /x/<seq> с Range; элемент живёт сессию, в библиотеку/IDB не пишется.
"""
import sys, os, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'download', 'plenka-optimized-66.html')
DST = os.path.join(ROOT, 'download', 'plenka-optimized-67.html')
ASSET = os.path.join(ROOT, 'plenka-native', 'app', 'src', 'main', 'assets', 'plenka.html')

R = []  # (old, new, note)

def rep(old, new, note):
    R.append((old, new, note))

# ─── A1: версия в шапке ───
rep('страница v66 / оболочка 3.19.',
    'страница v67 / оболочка 3.20.', 'версия')

# ─── A2: trueAspectPoster (VL-1/VL-7) ───
rep("""  return it.fthumb||it.thumb||null;
}
var vblankEl=$('#vblank');""",
"""  return it.fthumb||it.thumb||null;
}
function trueAspectPoster(it){    /* 67: источник маски ТОЛЬКО истинного аспекта: fframe (снят с элемента —
  композиция совпадает с видео) или серверная /t/ (первый кадр, докажет X-Plenka-FrameT).
  Карточные thumb/fthumb — лэндскейп 320×180 с запечённым леттербоксом: вписанные в подложку/
  постер, они торчали полями из-под играющего видео при любом несовпадении аспектов
  («под видео видно другое») — VL-1/VL-7 */
  if(!it)return null;
  if(it.fframe)return it.fframe;
  var th=(''+(it.thumb||''));
  return th.indexOf('/t/')>=0?th:null;
}
var vblankEl=$('#vblank');""", 'trueAspectPoster')

# ─── A3: setVblank — токен в каждой ветке + истинный аспект (RC-101/VL-1) ───
rep("""  try{
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
}""",
"""  try{
    if(!vblankEl)return;
    vblankEl._tok=(vblankEl._tok||0)+1; var my=vblankEl._tok;   /* 67: RC-101 — токен бампается в КАЖДОЙ ветке:
      устаревший posterFirstMs-колбэк прежней цели больше не может нарисовать чужой кадр
      поверх играющего (ветки null/data: раньше не бампались — колбэк проходил гвард) */
    var src=(it&&!it.audio)?trueAspectPoster(it):null;          /* 67: VL-1 — только истинный аспект */
    if(!src){ vblankEl.style.backgroundImage=''; return }
    if(src.indexOf('data:')===0){ vblankEl.style.backgroundImage='url("'+src+'")'; return }
    vblankEl.style.backgroundImage='';
    posterFirstMs(src,function(ms){
      if(my!==vblankEl._tok)return;                    /* цель уже сменилась — чужой кадр не подставляем */
      if(ms<=POSTER_FIRST_MS)vblankEl.style.backgroundImage='url("'+src+'")';
    })
  }catch(e){}
}""", 'setVblank RC-101/VL-1')

# ─── A4: posterUpgrade — истинный аспект + владение (VL-7/RC-103) ───
rep("""  try{
    var ps=(!it||it.audio)?null:posterSrcOf(it);
    if(!ps)return;
    if(ps.indexOf('data:')===0){ showPoster(ps); return }
    posterFirstMs(ps,function(ms){
      if(my!=null&&my!==playToken)return;              /* открытие перебито — постер принадлежит новому */
      if(ms<=POSTER_FIRST_MS)showPoster(ps);
    })
  }catch(e){}
}""",
"""  try{
    if(my!=null&&posterEl&&posterEl._own!=null&&posterEl._own!==my)return;   /* 67: RC-103 — владение открытием */
    var ps=(!it||it.audio)?null:trueAspectPoster(it);        /* 67: VL-7 — без карточного thumb с чужим леттербоксом */
    if(!ps)return;
    if(ps.indexOf('data:')===0){ showPoster(ps); return }
    posterFirstMs(ps,function(ms){
      if(my!=null&&(my!==playToken||(posterEl&&posterEl._own!=null&&posterEl._own!==my)))return;   /* 67: RC-103 */
      if(ms<=POSTER_FIRST_MS)showPoster(ps);
    })
  }catch(e){}
}""", 'posterUpgrade VL-7/RC-103')

# ─── A5: snapPoster — бамп токена (VL-8) ───
rep("""        if(posterEl&&!posterEl.hidden)posterEl.style.setProperty('--pi','url("'+url+'")');
        if(vblankEl)vblankEl.style.backgroundImage='url("'+url+'")';   /* 30.1: подложка докручивается
          синхронно с постером — снятие постера открывает идентичную картинку (пик-в-пик) */""",
"""        if(posterEl&&!posterEl.hidden)posterEl.style.setProperty('--pi','url("'+url+'")');
        try{ vblankEl._tok=(vblankEl._tok||0)+1 }catch(eT9){}          /* 67: VL-8/RC-101 — кадр позиции свежее
          pending-fetch setVblank: инвалидируем его колбэк, пик-в-пик не перебивается кадром 0:00 */
        if(vblankEl)vblankEl.style.backgroundImage='url("'+url+'")';   /* 30.1: подложка докручивается
          синхронно с постером — снятие постера открывает идентичную картинку (пик-в-пик) */""", 'snapPoster VL-8')

# ─── A5b: snapPoster — докрутка только ДО склейки (VL-2, найдено live-тестом) ───
rep("""        if(myTok!==playToken||sb.error||sb._pid!==it.id)return;   /* 66: токен открытия + цель — чужой кадр не пишем в постер/подложку */""",
"""        if(myTok!==playToken||sb.error||sb._pid!==it.id)return;   /* 66: токен открытия + цель — чужой кадр не пишем в постер/подложку */
        if(sb===vActive)return;   /* 67: VL-2 (live-тест) — склейка уже произошла и killOld очистил подложку:
          поздняя докрутка снова закрашивала её кадром позиции на весь сеанс трека; кадр теперь рисует само видео */""", 'snapPoster post-swap gate')

# ─── A6: swapRoles — очистка подложки по первому кадру (VL-2) ───
rep("""  sb.style.visibility=curIsAudio()?'hidden':'';   /* аудио: элементы скрыты, обложка на экране */
  var killOld=function(){ try{ if(old!==vActive)old.style.visibility='hidden' }catch(e){} };""",
"""  sb.style.visibility=curIsAudio()?'hidden':'';   /* аудио: элементы скрыты, обложка на экране */
  var mySwTok=playToken;                          /* 67: токен свапа — очистку подложки делает только свой переход */
  var killOld=function(){ try{ if(old!==vActive){ old.style.visibility='hidden';
    if(mySwTok===playToken&&vblankEl)vblankEl.style.backgroundImage=''; } }catch(e){} };   /* 67: VL-2 — кадр подложки
    нужен только до первого показанного кадра: после — чистый чёрный (зум/пан/перезарядка элемента
    не подставят в поля устаревший кадр; центр и так перекрыт видео) */""", 'swapRoles VL-2')

# ─── A7: 4К-релиз не трогает элемент в мини (RC-109) ───
rep("""        if(oldEl!==vStandby||oldEl===vActive||oldEl._loading||oldEl._lgen!==lgen0)return;   /* 66: элемент перезаряжен после свапа — не наша цель */""",
"""        if(oldEl!==vStandby||oldEl===vActive||oldEl._loading||oldEl._lgen!==lgen0)return;   /* 66: элемент перезаряжен после свапа — не наша цель */
        var p0m=oldEl.parentNode; if(p0m&&p0m.id==='miniThumb')return;   /* 67: RC-109 — элемент уехал в мини-панель: его кадр и есть картинка панели */""", '4K-таймер RC-109')

# ─── A8: openItem — валидация до токена (RC-107) ───
rep("""async function openItem(idx,opts){
  opts=opts||{}; var my=++playToken; lastSwAt=Date.now();   /* 66: метка старта переключения — гвард двойного авто-перехода */
  cardPreviewStop();                                 /* открытие гасит превью карточки (если было) */
  try{ ffAbort() }catch(e){}                         /* 2.5: фоновый декодер fframe не делит I/O с открытием */
  var keepMini=!!opts.keepMini&&MINI.mode==='local';   /* автопереход внутри мини-панели: плеер не открываем */
  var it=items[idx]; if(!it)return;
  if(MINI.mode==='local'&&MINI.item===it){ openMiniPlayer(); return; }   /* это уже играет в панели — просто открываем плеер */""",
"""async function openItem(idx,opts){
  opts=opts||{};
  var it=items[idx]; if(!it)return;                  /* 67: RC-107 — валидация ДО бампа токена: тап по стухшему
    индексу/мини-плашке больше не убивает чужое открытие в полёте (его откат не выполнялся бы вовсе) */
  if(MINI.mode==='local'&&MINI.item===it){ openMiniPlayer(); return; }   /* это уже играет в панели — просто открываем плеер */
  var my=++playToken; lastSwAt=Date.now();   /* 66: метка старта переключения — гвард двойного авто-перехода */
  cardPreviewStop();                                 /* открытие гасит превью карточки (если было) */
  try{ ffAbort() }catch(e){}                         /* 2.5: фоновый декодер fframe не делит I/O с открытием */
  var keepMini=!!opts.keepMini&&MINI.mode==='local';   /* автопереход внутри мини-панели: плеер не открываем */""", 'openItem RC-107')

# ─── A9: prevIt по ссылке (RC-102) ───
rep("""  var prevIdx=currentIdx;
  var fromEnded=autoAdv; autoAdv=false;""",
"""  var prevIdx=currentIdx;
  var prevIt=(prevIdx>=0)?items[prevIdx]:null;   /* 67: RC-102 — по ссылке: items может мутировать
    за долгую загрузку (удаление/рескан во второй вкладке) — устаревший индекс давал чужой трек */
  var fromEnded=autoAdv; autoAdv=false;""", 'prevIt RC-102')

# ─── A10: владение постером (RC-103) ───
rep("""                                            старое видео (z1) не видно в принципе, гонки таймингов
                                            безразличны: под постером и под видео одна и та же картинка */
  try{ var msk=posterSrcOf(it);""",
"""                                            старое видео (z1) не видно в принципе, гонки таймингов
                                            безразличны: под постером и под видео одна и та же картинка */
  try{ posterEl._own=my }catch(eP0){}              /* 67: RC-103 — постер принадлежит этому открытию: колбэк
    упавшей/перебитой цели не поднимет кадр над возобновлённым треком */
  try{ var msk=posterSrcOf(it);""", 'poster._own RC-103')

# ─── A11: abort-ветка — маски гасим, откат по ссылке (VL-4/RC-102/103) ───
rep("""    if(!ok&&((lsOut.why||lsWhy)==='abort'||(lsOut.why||lsWhy)==='race')){   /* 62: перебито/отменено — HUD рисует по факту */
      if(hudHoldId===(it&&it.id))hudHoldId=null;   /* 66: гасим только СВОЙ hold — race-выход больше не мигает чужим HUD */
      try{ setVblank(prevIdx>=0?items[prevIdx]:null) }catch(eV0){}   /* 66: открытие мертво (токен наш — это не новый openItem):
        маска возвращается к возобновлённому треку — кадр недооткрытой цели больше не торчит
        в леттербоксе играющего («под видео видно другое») */
      try{ var cR0=-1; for(var qR0=0;qR0<items.length;qR0++)if(vActive._pid&&items[qR0]&&items[qR0].id===vActive._pid){cR0=qR0;break}
        currentIdx=cR0>=0?cR0:prevIdx; }catch(eR1){}   /* 66: preheat-гонка не оставляет currentIdx на неиграющем */
      return; }   /* 24.4: перебито другим открытием/прогревом — не ошибка */""",
"""    if(!ok&&((lsOut.why||lsWhy)==='abort'||(lsOut.why||lsWhy)==='race')){   /* 62: перебито/отменено — HUD рисует по факту */
      if(hudHoldId===(it&&it.id))hudHoldId=null;   /* 66: гасим только СВОЙ hold — race-выход больше не мигает чужим HUD */
      try{ posterEl._own=null }catch(eO1){}        /* 67: RC-103 — pending-колбэк постера этой цели гасим */
      try{ hidePoster(true) }catch(eP1){}          /* 67: VL-4 — маска/кадр недооткрытой цели не висит над возобновлённым треком */
      try{ hideFreeze() }catch(eF1){}              /* 67: VL-4 */
      try{ var cR0=-1; for(var qR0=0;qR0<items.length;qR0++)if(vActive._pid&&items[qR0]&&items[qR0].id===vActive._pid){cR0=qR0;break}
        currentIdx=cR0>=0?cR0:prevIdx;   /* 66: preheat-гонка не оставляет currentIdx на неиграющем */
        var rIt0=(cR0>=0&&items[cR0])?items[cR0]:((prevIt&&!prevIt._dead)?prevIt:null);   /* 67: RC-102 — по факту играющему */
        setVblank(rIt0) }catch(eV0){}   /* 66→67: открытие мертво (токен наш — это не новый openItem):
        маска возвращается к возобновлённому треку — кадр недооткрытой цели больше не торчит
        в леттербоксе играющего («под видео видно другое») */
      return; }   /* 24.4: перебито другим открытием/прогревом — не ошибка */""", 'abort-ветка VL-4/RC-102')

# ─── A12: fail-ветка — профиль и подложка по факту (RC-102/103) ───
rep("""      try{ profApply(prevIdx>=0?items[prevIdx]:null) }catch(e){}   /* 37.4: неудача — профиль играющего трека возвращается (применяли же нового) */""",
"""      try{ profApply((cR>=0&&items[cR])?items[cR]:((prevIt&&!prevIt._dead)?prevIt:null)) }catch(e){}   /* 37.4→67: RC-102 — профиль по факту играющего, не по устаревшему prevIdx */""", 'fail profApply RC-102')

rep("""      hidePoster(true); hideFreeze();
      try{ setVblank(prevIdx>=0?items[prevIdx]:null) }catch(eV1){}   /* 66: подложка — на возобновлённый трек (его кадр той же
        геометрии, что и возобновляемое видео): кадр упавшей цели не торчит
        в леттербоксе возобновлённого воспроизведения при другом aspect ratio */""",
"""      try{ posterEl._own=null }catch(eO2){}   /* 67: RC-103 — pending-колбэк постера упавшей цели гасим */
      hidePoster(true); hideFreeze();
      try{ setVblank((cR>=0&&items[cR])?items[cR]:((prevIt&&!prevIt._dead)?prevIt:null)) }catch(eV1){}   /* 66→67: подложка — на ФАКТИЧЕСКИ играющий трек
        (его кадр той же геометрии, что и возобновляемое видео): кадр упавшей цели не торчит
        в леттербоксе возобновлённого воспроизведения при другом aspect ratio */""", 'fail setVblank RC-102/103')

# ─── A13: loadedmetadata — только владеемому (RC-108) ───
rep("""VOn('loadedmetadata',function(){
  $('#tDur').textContent=fmtT(video.duration);
  if(currentIdx>=0&&items[currentIdx]&&!items[currentIdx].duration&&isFinite(video.duration)){
    items[currentIdx].duration=video.duration; persistItem(items[currentIdx]); renderSoon();
  }
});""",
"""VOn('loadedmetadata',function(){
  $('#tDur').textContent=fmtT(video.duration);
  if(currentIdx>=0&&items[currentIdx]&&vActive._pid&&items[currentIdx].id===vActive._pid&&!items[currentIdx].duration&&isFinite(video.duration)){   /* 67: RC-108 — только владеемому треку */
    items[currentIdx].duration=video.duration; persistItem(items[currentIdx]); renderSoon();
  }
});""", 'loadedmetadata RC-108')

# ─── A14: ended — владение вместо 800мс (RC-105) ───
rep("""VOn('ended',function(){
  try{ if(Date.now()-(window.lastSwAt||0)<800&&vActive&&vActive._pid&&items[currentIdx]&&items[currentIdx].id!==vActive._pid)return; }catch(e0W){}   /* 66: ended УХОДЯЩЕГО
    трека против свежего next: currentIdx уже на новом — авто-переход от старого не перескакивает через новый */""",
"""VOn('ended',function(){
  try{ if(vActive&&vActive._pid&&items[currentIdx]&&items[currentIdx].id!==vActive._pid)return; }catch(e0W){}   /* 67: RC-105 — владение вместо 800мс-окна: пока активный
    элемент не владеет currentIdx (цель ещё грузится), ended уходящего НЕ двигает очередь и не
    переигрывает старый трек в loop='one' — прежнее окно было меньше реальной загрузки цели */""", 'ended RC-105')

# ─── A15: MINI.tick — сброс hold (RC-106) ───
rep("""    if(hudHoldId){ if(miniFill)miniFill.style.width=hudPrePct+'%'; return; }   /* 62: до склейки — линия на позиции ЦЕЛИ, не уходящего */""",
"""    if(hudHoldId){
      if(video&&video._pid===hudHoldId&&video.readyState>=1){ hudHoldId=null; hudPrePct=0; }   /* 67: RC-106 — склейка в мини сбрасывает hold: прогресс не замирает на % цели */
      else{ if(miniFill)miniFill.style.width=hudPrePct+'%'; return; } }   /* 62: до склейки — линия на позиции ЦЕЛИ, не уходящего */""", 'MINI.tick RC-106')

# ─── A16: chase — freeze снимаем (VL-3) ───
rep("""function startChaseMirror(it,X){                   /* фолбэк: прежнее зеркало вторым декодером */
  MIRROR.mode='chase';""",
"""function startChaseMirror(it,X){                   /* фолбэк: прежнее зеркало вторым декодером */
  try{ hideFreeze() }catch(e){}                    /* 67: VL-3 — стоп-кадр момента входа в PiP не висит над chase-зеркалом
    (в chase-ветке его никто не снимал — он навсегда перекрывал страницу поверх зеркала) */
  MIRROR.mode='chase';""", 'chase VL-3')

# ─── A17: chase — бокс Y вне гонки DOM-порядка (VL-5) ───
rep("""    try{ Y.style.zIndex=3; X.style.zIndex=(MIRROR.mode==='stream')?1:3; }catch(e){}   /* 30: активный — над
      подложкой; на потоке запасной ПОД ней (страницу рисует зеркало-элемент m), в chase запасной
      и есть зеркало страницы — НАД подложкой */""",
"""    try{ Y.style.zIndex=3; X.style.zIndex=(MIRROR.mode==='stream')?1:3;
      if(MIRROR.mode==='chase')Y.style.visibility='hidden'; }catch(e){}   /* 30→67: активный — над подложкой; на потоке запасной ПОД ней
      (страницу рисует зеркало-элемент m), в chase запасной и есть зеркало страницы — НАД подложкой.
      VL-5: бокс Y (элемент окна) в chase не участвует в гонке DOM-порядка с зеркалом X (оба z3):
      чёрный ящик Y больше не может накрыть страницу; видимость вернут mirrorVis/mirrorStop */""", 'chase VL-5')

# ─── A18: mirrorOpen — hold цели не залипает (RC-104) ───
rep("""    var f=await ensureFile(it);
    if(my!==playToken)return;
    if(!f||!f.size){ toast(t(fileErr==='NotAllowedError'||fileErr==='SecurityError'?'errPerm':'errOpenFail'),'err'); return; }""",
"""    var f=await ensureFile(it);
    if(my!==playToken)return;
    if(!f||!f.size){ if(hudHoldId===it.id)hudHoldId=null; toast(t(fileErr==='NotAllowedError'||fileErr==='SecurityError'?'errPerm':'errOpenFail'),'err'); return; }   /* 67: RC-104 — hold цели не залипает */""", 'mirrorOpen hold RC-104')

# ─── A19: mirrorOpen — фолбэк под токен-гвардом (RC-104) ───
rep("""  }catch(e){}
  /* ═══ запасный путь: окно рисует тот же элемент (источник меняется с чёрной паузой) ═══ */
  if(MIRROR.swapTok===my)MIRROR.swapping=false;   /* 32.3 */
  setVblank(it);               /* 30.1: подложка на цель ДО смены src: элемент на странице станет""",
"""  }catch(e){}
  /* ═══ запасный путь: окно рисует тот же элемент (источник меняется с чёрной паузой) ═══ */
  if(MIRROR.swapTok===my)MIRROR.swapping=false;   /* 32.3 */
  if(my!==playToken){                              /* 67: RC-104 — перебитый mirrorOpen НЕ ретаргетит играющий
    элемент и не перетирает подложку, уже выставленную новым открытием */
    try{ if(hudHoldId===it.id)hudHoldId=null }catch(e){} return; }
  setVblank(it);               /* 30.1: подложка на цель ДО смены src: элемент на странице станет""", 'mirrorOpen fallback RC-104')

# ─── A20: mirrorStop — подложка в чёрный (VL-2) ───
rep("""  hideFreeze();
  if(MINI.mode==='local'&&MINI.item&&!MINI.item.audio&&miniThumb&&!miniThumb.querySelector('video')){""",
"""  hideFreeze();
  try{ if(vblankEl)vblankEl.style.backgroundImage='' }catch(e){}   /* 67: VL-2 — страница снова рисует активный элемент:
    кадр в подложке больше не нужен, поля — чистый чёрный (не проступит при зуме/перезарядке) */
  if(MINI.mode==='local'&&MINI.item&&!MINI.item.audio&&miniThumb&&!miniThumb.querySelector('video')){""", 'mirrorStop VL-2')

# ─── A21: постеры зеркальных путей — истинный аспект (VL-7) ───
rep("""      var psC=posterSrcOf(it); if(psC)showPoster(psC);""",
"""      var psC=trueAspectPoster(it); if(psC)showPoster(psC);   /* 67: VL-7 */""", 'chase poster')
rep("""  if(!it.audio){ var psA=posterSrcOf(it); if(psA)showPoster(psA); else showPoster(null); }   /* 32.2:""",
"""  if(!it.audio){ var psA=trueAspectPoster(it); if(psA)showPoster(psA); else showPoster(null); }   /* 32.2→67: VL-7 —""", 'mirror poster A')
rep("""      if(!it.audio){ var psB=posterSrcOf(it); if(psB)showPoster(psB); }   /* 26.5 (chase): страница под постером,""",
"""      if(!it.audio){ var psB=trueAspectPoster(it); if(psB)showPoster(psB); }   /* 26.5→67 (chase, VL-7): страница под постером,""", 'mirror poster B')
rep("""  if(!it.audio){ var psD=posterSrcOf(it); if(psD)showPoster(psD); }   /* 26.5: запасной путь — то же прикрытие */""",
"""  if(!it.audio){ var psD=trueAspectPoster(it); if(psD)showPoster(psD); }   /* 26.5→67: запасной путь — то же прикрытие (VL-7) */""", 'mirror poster D')

# ─── B1: kind 'x' в источниках ───
rep("""    if(it.kind==='url'||it.kind==='native'){ u=it.url;""",
"""    if(it.kind==='url'||it.kind==='native'||it.kind==='x'){ u=it.url;   /* 67: 'x' — внешнее открытие («Открыть с помощью») */""", 'loadStandby1 x')
rep("""      if(it.kind==='native'){                  /* 2.5: префлайт HEAD — «gone» и причины сервера""",
"""      if(it.kind==='native'||it.kind==='x'){   /* 2.5→67: префлайт HEAD — «gone» и причины сервера ('x' — смерть SAF-права),""", 'preflight x')
rep("""  var u=(it.kind==='url'||it.kind==='native')?it.url:cachedUrl(it.id);
  if(u&&(sb.src===u||sb.currentSrc===u))return true;""",
"""  var u=(it.kind==='url'||it.kind==='native'||it.kind==='x')?it.url:cachedUrl(it.id);
  if(u&&(sb.src===u||sb.currentSrc===u))return true;""", 'standbyReadyFor x src')
rep("""  if(it&&(it.kind==='url'||it.kind==='native'))return false;""",
"""  if(it&&(it.kind==='url'||it.kind==='native'||it.kind==='x'))return false;""", 'standbyReadyFor x strict')
rep("""    var u=(it.kind==='url'||it.kind==='native')?it.url:cachedUrl(it.id);
    if(u&&(Y._pid!==it.id||((Y.currentSrc||Y.src)!==u&&Y.src!==u))){""",
"""    var u=(it.kind==='url'||it.kind==='native'||it.kind==='x')?it.url:cachedUrl(it.id);
    if(u&&(Y._pid!==it.id||((Y.currentSrc||Y.src)!==u&&Y.src!==u))){""", 'chase url x')
rep("""  var u=(it.kind==='url'||it.kind==='native')?it.url:cachedUrl(it.id);
  if(!u){""",
"""  var u=(it.kind==='url'||it.kind==='native'||it.kind==='x')?it.url:cachedUrl(it.id);
  if(!u){""", 'mirrorOpen url x')

# ─── B2: 'x' не персистится и не виден в библиотеке ───
rep("""function persistItem(it){
  if(!idbOK||it._dead)return;   /* 66: удалённое не воскресает из фоновых записей */""",
"""function persistItem(it){
  if(!idbOK||it._dead)return;   /* 66: удалённое не воскресает из фоновых записей */
  if(it.kind==='x')return;      /* 67: внешнее открытие живёт только сессию — в IDB не пишем */""", 'persistItem x')
rep("""  var F=S.filter||{},a=items.filter(function(it){
    if(it.pend)return false;                           /* снифится — карточки ещё нет */""",
"""  var F=S.filter||{},a=items.filter(function(it){
    if(it.pend)return false;                           /* снифится — карточки ещё нет */
    if(it.kind==='x')return false;                     /* 67: внешние открытия — вне библиотеки (одноразовый сеанс) */""", 'viewItems x')

# ─── B3: приёмник __plenkaExt (3.20) ───
rep("""var pqEl=null,pqT=0;                                /* 26.2: пауза открытия трека — служебная, UI не будит */""",
"""/* ═══ 3.20: внешние открытия — «Открыть с помощью» / «Открыть по умолчанию» ═══
   Оболочка принимает ACTION_VIEW (аудио/видео из проводника, браузера, других приложений),
   раздаёт файл по /x/<seq> с Range и доставляет карточку сюда (pushExtToPage, ретраи).
   Элемент живёт одну сессию: в библиотеку и IDB не попадает, очередь — сам файл. */
window.__plenkaExt=function(o){
  try{
    if(typeof o==='string')o=JSON.parse(o);
    if(!o||o.i==null)return 'err:args';
    var xid='x'+(o.i|0);
    for(var q=0;q<items.length;q++)if(items[q].id===xid){ openItem(q); return 'ok'; }   /* повторный VIEW того же файла */
    var it={id:xid,kind:'x',xid:(o.i|0),name:''+(o.n||'внешний файл'),mime:''+(o.m||''),size:o.s||0,
      audio:!!o.a,duration:0,w:0,h:0,dir:'',status:'ok',addedAt:Date.now(),lastAt:Date.now(),views:0,position:0};
    var u=natvTok(NATV_BASE+'/x/'+(o.i|0)); if(u)it.url=u;
    items.push(it);
    renderSoon();
    openItem(items.length-1,{autoplay:true});
    return 'ok';
  }catch(e){ return 'err:'+((e&&e.message)||e) }
};
var pqEl=null,pqT=0;                                /* 26.2: пауза открытия трека — служебная, UI не будит */""", '__plenkaExt')

def main():
    with open(SRC, encoding='utf-8') as f:
        s = f.read()
    errs = []
    for old, new, note in R:
        n = s.count(old)
        if n != 1:
            errs.append(f'[{note}] вхождений {n} (ожидалось 1)')
            continue
        s = s.replace(old, new, 1)
    if errs:
        print('ОШИБКИ ЯКОРЕЙ:')
        for e in errs: print('  ' + e)
        sys.exit(1)
    with open(DST, 'w', encoding='utf-8') as f:
        f.write(s)
    os.makedirs(os.path.dirname(ASSET), exist_ok=True)
    shutil.copyfile(DST, ASSET)
    print(f'OK: {DST} ({len(s)} байт) + ассет {ASSET}')
    # контроль: старые маркеры версии не должны остаться в шапке
    print('v66 в шапке:', 'страница v66' in s, '| v67 в шапке:', 'страница v67' in s)

if __name__ == '__main__':
    main()
