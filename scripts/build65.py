#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка v65 из v64: багфиксы аудита 2026-10-29.

Kotlin/оболочка 3.18 правится отдельно (patch65.py — натив), здесь — только HTML.
Каждая правка: точный якорь, count==1, короткий комментарий-маркер «65:».

Список фиксов:
  F01 XSS: buildFmtSeg — расширение имени файла вставлялось в innerHTML без esc
  F02 XSS: showInfo — ext/status в строках «о файле» без esc
  F03 currentIdx по ссылке: dropBadItem
  F04 currentIdx по ссылке: removeItem
  F05 currentIdx по ссылке: applyLibSync(del)
  F06 currentIdx по ссылке: natvMerge (исчезнувшие с устройства)
  F07 currentIdx по ссылке: natvMergePicked (исчезнувшие из реестра)
  F08 currentIdx по ссылке: scanFolder (рескан папки)
  F09 drag&drop папки: readEntries порциями (раньше >100 файлов обрезались молча)
  F10 bgPauseGated: localStorage в try (среды с заблокированным storage)
  F11 idbOp: успех транзакции реанимирует idbOK (одна ошибка больше не хоронит IDB)
  F12 postMessage: только самовызов; кап незавершённых импортов (inflight ≤2)
  F13 msebPatchMoof: пропуск default_sample_duration (fl&0x000008) перед чтением size
  F14 trex: дефолты сэмплов читались со сдвигом -4 (dur/size/flags)
  F15 tfdt: версия/BMDT читались со сдвигом +4 — карта якорей была мусорной на v0
      (msebAnchors + msebTimeToByte) — корень «сик промахивается → recover → фолбэк»
  F16 msebPrevMoof: размер moof читался из ASCII 'moof' — валидация «после moof идёт
      mdat» была мертва
  F17 msebPump: смерть качалки по сетевому исключению → msebRecover (было — навсегда)
  F18 msebReopen: кап 3 полных пересозданий на файл (раньше — бесконечный цикл)
  F19 msebFetch: таймаут 10с + один ретрай (зависший фетч блокировал pump навсегда)
  F20 doProbe: revoke objectURL в catch-пути
  F21 cardPreviewStart: не плодим второй objectURL при живом кэше
  F22 savePos: гвард «активный элемент владеет треком currentIdx» — время уходящего
      больше не пишется в позицию нового («назад»/pagehide в окне переключения)
  F23 openItem: resync мини-панели после swap, если soft-close пересадил в неё
      устаревший элемент (кадр A + звук/заголовок B)
  F24 PiP из мини: natvPipEnter и __pipMode(true) возвращают живой элемент в #stage
      (иначе body.pip прячет miniBar вместе с единственным видео — окно PiP = стоп-кадр)
  F25 swapRoles: PiP-элемент уходит за новым активным (exitPictureInPicture)
  F26 swapRoles: сброс seek-таймеров уходящего элемента
  F27 поток-вочдог работает и в мини-панели
  F28 openItem !ok: возврат игры к уходящему треку (не оставляем замороженный кадр)
  F29 msebPump: пауза — такт 1с вместо 320мс (фон не будим зря)
  F30 msebSleep: микро-пауза между MessageChannel-тиками (фоновый busy-spin)
  F31 msebSeekByte/msebSeek: неудача поиска байта = -1 → реанимация (раньше молча
      «сажались» в начало файла)
"""
import sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC  = os.path.join(ROOT, 'download', 'plenka-optimized-64.html')
DST  = os.path.join(ROOT, 'download', 'plenka-optimized-65.html')

src = open(SRC, encoding='utf-8').read()

FIXES = []
def F(name, old, new):
    FIXES.append((name, old, new))

# ─── F01 XSS buildFmtSeg ───────────────────────────────────────────────────────
F('F01 buildFmtSeg esc',
"""  var h='<button data-v="all">'+t('allQ')+'</button>'+exts.map(function(e2){return '<button data-v="'+e2+'">'+e2+'</button>'}).join('');""",
"""  /* 65: расширение имени — данные извне (файл «clip.mp4<img src=x onerror=…>.mkv»):
     esc обязателен и в атрибуте, и в тексте — воспроизведённый PoC Stored XSS */
  var h='<button data-v="all">'+t('allQ')+'</button>'+exts.map(function(e2){return '<button data-v="'+esc(e2)+'">'+esc(e2)+'</button>'}).join('');""")

# ─── F02 XSS showInfo ─────────────────────────────────────────────────────────
F('F02 showInfo esc',
"""      +'<span style="color:var(--mut);width:108px;flex:none">'+esc(r[0])+'</span>'
      +'<span style="color:var(--tx);min-width:0">'+r[1]+'</span></div>';""",
"""      +'<span style="color:var(--mut);width:108px;flex:none">'+esc(r[0])+'</span>'
      +'<span style="color:var(--tx);min-width:0">'+esc(String(r[1]))+'</span></div>';""")   # 65: ext/status — тоже данные извне

# ─── F03 dropBadItem ──────────────────────────────────────────────────────────
F('F03 dropBadItem currentIdx',
"""function dropBadItem(it,silent){
  items=items.filter(function(x){return x!==it});
  if(currentIdx>=0&&items[currentIdx]===undefined)currentIdx=-1;
  idbDel('items',it.id); idbDel('blobs',it.id); idbDel('kv','subs:'+it.id); idbDel('handles','fh::'+it.id);""",
"""function dropBadItem(it,silent){
  var curO=(currentIdx>=0&&items[currentIdx])?items[currentIdx]:null;   /* 65: индекс привязан к ССЫЛКЕ,
    а не к позиции: удалили играющего (или соседа слева) — раньше currentIdx молча указывал на чужого */
  items=items.filter(function(x){return x!==it});
  currentIdx=curO?(curO===it?-1:items.indexOf(curO)):-1;
  idbDel('items',it.id); idbDel('blobs',it.id); idbDel('kv','subs:'+it.id); idbDel('handles','fh::'+it.id);""")

# ─── F04 removeItem ───────────────────────────────────────────────────────────
F('F04 removeItem currentIdx',
"""async function removeItem(it){
  items=items.filter(function(x){return x!==it});""",
"""async function removeItem(it){
  var curO=(currentIdx>=0&&items[currentIdx])?items[currentIdx]:null;   /* 65: пересчёт по ссылке */
  items=items.filter(function(x){return x!==it});""")
F('F04 removeItem currentIdx tail',
"""  if(currentIdx>=0&&items[currentIdx]===undefined)currentIdx=-1;
  renderLib(); renderStrip(); renderPlTabs(); toast(t('removedLib'));""",
"""  currentIdx=curO?(curO===it?-1:items.indexOf(curO)):-1;   /* 65: гвард по undefined ловил только сдвиг последнего индекса */
  renderLib(); renderStrip(); renderPlTabs(); toast(t('removedLib'));""")

# ─── F05 applyLibSync del ─────────────────────────────────────────────────────
F('F05 applyLibSync del',
"""    if(it){
      items=items.filter(function(x){return x!==it});
      if(hiddenSet[it.id]){ delete hiddenSet[it.id]; saveHidden(); }
      var pt=false;
      playlists.forEach(function(P){ var k=P.ids.indexOf(it.id); if(k>=0){P.ids.splice(k,1);pt=true} });
      if(pt)savePlaylists();
      forgetUrl(it);
      if(currentIdx>=0&&items[currentIdx]===undefined)currentIdx=-1;
    }""",
"""    if(it){
      var curO=(currentIdx>=0&&items[currentIdx])?items[currentIdx]:null;   /* 65: пересчёт по ссылке (del со второй вкладки) */
      items=items.filter(function(x){return x!==it});
      if(hiddenSet[it.id]){ delete hiddenSet[it.id]; saveHidden(); }
      var pt=false;
      playlists.forEach(function(P){ var k=P.ids.indexOf(it.id); if(k>=0){P.ids.splice(k,1);pt=true} });
      if(pt)savePlaylists();
      forgetUrl(it);
      currentIdx=curO?(curO===it?-1:items.indexOf(curO)):-1;
    }""")

# ─── F06 natvMerge gone ───────────────────────────────────────────────────────
F('F06 natvMerge gone',
"""  if(goneList.length){
    var goneSet={};
    goneList.forEach(function(d){ goneSet[d.id]=1; items=items.filter(function(x){return x!==d}); idbDel('items',d.id); idbDel('prev',d.id); });""",
"""  if(goneList.length){
    var goneSet={},curO=(currentIdx>=0&&items[currentIdx])?items[currentIdx]:null;   /* 65: рескан сдвигал индексы молча */
    goneList.forEach(function(d){ goneSet[d.id]=1; items=items.filter(function(x){return x!==d}); idbDel('items',d.id); idbDel('prev',d.id); });
    currentIdx=curO?items.indexOf(curO):-1;""")

# ─── F07 natvMergePicked gone ─────────────────────────────────────────────────
F('F07 natvMergePicked gone',
"""  gone.forEach(function(g){ items=items.filter(function(x){return x!==g}); idbDel('items',g.id); idbDel('prev',g.id); });""",
"""  var curO=(currentIdx>=0&&items[currentIdx])?items[currentIdx]:null;   /* 65: индекс по ссылке */
  gone.forEach(function(g){ items=items.filter(function(x){return x!==g}); idbDel('items',g.id); idbDel('prev',g.id); });
  currentIdx=curO?items.indexOf(curO):-1;""")

# ─── F08 scanFolder ───────────────────────────────────────────────────────────
F('F08 scanFolder currentIdx',
"""    items=items.filter(function(x){ return !(x.kind==='dir'&&x.dir===f.id&&!found[x.id]) });
  }catch(e){}""",
"""    var curO=(currentIdx>=0&&items[currentIdx])?items[currentIdx]:null;   /* 65: рескан папки — та же порча индекса */
    items=items.filter(function(x){ return !(x.kind==='dir'&&x.dir===f.id&&!found[x.id]) });
    currentIdx=curO?items.indexOf(curO):-1;
  }catch(e){}""")

# ─── F09 readEntries порциями ────────────────────────────────────────────────
F('F09 readEntries paging',
"""    var read=function(dir){ return new Promise(function(res){
      dir.createReader().readEntries(async function(es){
        var out=[];
        for(var j=0;j<es.length;j++){
          if(es[j].isFile)out.push(await new Promise(function(r){ es[j].file(r) }));
          else out=out.concat(await read(es[j]));
        }
        res(out);
      });
    })};""",
"""    var read=function(dir){ return new Promise(function(res){
      var rd=dir.createReader(),ents=[];   /* 65: readEntries отдаёт максимум 100 записей за вызов —
        папки больше сотни файлов молча обрезались; читаем порциями до пустого ответа */
      var flush=function(){
        (async function(){
          var out=[];
          for(var j=0;j<ents.length;j++){
            if(ents[j].isFile){ try{ out.push(await new Promise(function(r,eR){ ents[j].file(r,eR) })) }catch(eF){} }
            else{ try{ out=out.concat(await read(ents[j])) }catch(eD){} }
          }
          res(out);
        })();
      };
      var page=function(es){
        if(!es.length){ flush(); return }
        ents=ents.concat(es);
        try{ rd.readEntries(page,flush) }catch(eR){ flush() }
      };
      try{ rd.readEntries(page,flush) }catch(e0){ flush() }
    })};""")

# ─── F10 bgPauseGated localStorage ────────────────────────────────────────────
F('F10 bgPauseGated try',
"""  if(localStorage.getItem('plenka.pipMode')==='pip')return true;   /* видимое PiP-окно живёт по своим правилам */
  var b=null; try{ b=el._mseb }catch(e0){}""",
"""  try{ if(localStorage.getItem('plenka.pipMode')==='pip')return true }catch(eL){}   /* 65: storage может быть заблокирован — как в соседних обращениях */
  var b=null; try{ b=el._mseb }catch(e0){}""")

# ─── F11 idbOp реанимация ─────────────────────────────────────────────────────
F('F11 idbOp revive',
"""      t.oncomplete=function(){ res(q&&q.result) };
      t.onerror=function(){ rej(t.error) };
      t.onabort=function(){ rej(t.error) };""",
"""      t.oncomplete=function(){ if(!idbOK)idbOK=true; res(q&&q.result) };   /* 65: одна транзиентная ошибка
        больше не хоронит сохранение до перезагрузки — успешная транзакция реанимирует */
      t.onerror=function(){ rej(t.error) };
      t.onabort=function(){ rej(t.error) };""")

# ─── F12 postMessage источник + inflight кап ─────────────────────────────────
F('F12 message source',
"""addEventListener('message',function(e){
  try{
    var m=(typeof e.data==='string')?JSON.parse(e.data):e.data;
    if(m&&m.plenka){""",
"""addEventListener('message',function(e){
  try{
    if(e.source!==window)return;   /* 65: только самовызов — чужой фрейм больше не наполняет библиотеку */
    var m=(typeof e.data==='string')?JSON.parse(e.data):e.data;
    if(m&&m.plenka){""")
F('F12 inflight cap',
"""  beginVideo:function(o){ if(!o||!o.id)return; inflight[o.id]={name:o.name||'video',mime:o.mime||'video/mp4',size:o.size||0,chunks:[]} },""",
"""  beginVideo:function(o){ if(!o||!o.id)return;   /* 65: кап незавершённых импортов — падение оболочки без commit не копит память */
    var ks=Object.keys(inflight); if(ks.length>2){ for(var qi=0;qi<ks.length-2;qi++){ try{ delete inflight[ks[qi]] }catch(eI){} } }
    inflight[o.id]={name:o.name||'video',mime:o.mime||'video/mp4',size:o.size||0,chunks:[]} },""")

# ─── F13 msebPatchMoof fl&0x8 ─────────────────────────────────────────────────
F('F13 patchMoof default_sample_duration',
"""      var defSize=(fl&0x000010)?u32b(pair,fp):null;""",
"""      if(fl&0x000008)fp+=4;                            /* 65: default_sample_duration присутствует — курсор обязан его пройти
          (раньше defSize читался со смещением duration; msebKeyAt обходил правильно — пары разошлись) */
      var defSize=(fl&0x000010)?u32b(pair,fp):null;""")

# ─── F14 trex сдвиг ───────────────────────────────────────────────────────────
F('F14 trex offsets',
"""        if(t2==='trex'){ var tid=u32b(mo,o2+h2+4);
          (R.trex=R.trex||{})[tid]={dur:u32b(mo,o2+h2+8),size:u32b(mo,o2+h2+12),flags:u32b(mo,o2+h2+16)} }""",
"""        if(t2==='trex'){ var tid=u32b(mo,o2+h2+4);   /* 65: trex — FullBox: track_ID@+4, desc@+8, dur@+12, size@+16, flags@+20;
            раньше все три дефолта читались со сдвигом -4 (dur=desc, size=dur, flags=size) —
            ломало и адресацию PatchMoof, и keyframe-бэкофф */
          (R.trex=R.trex||{})[tid]={dur:u32b(mo,o2+h2+12),size:u32b(mo,o2+h2+16),flags:u32b(mo,o2+h2+20)} }""")

# ─── F15 tfdt сдвиг (два места) ───────────────────────────────────────────────
F('F15 tfdt anchors',
"""        if(q>0){ var v=u[q+8];
          var t=(v===1?u64b(u,q+12):u32b(u,q+12))/ts;""",
"""        if(q>0){ var v=u[q+4];   /* 65: tfdt — FullBox: версия в байте ПОСЛЕ типа (q+4), BMDT сразу за version+flags (q+8).
            Раньше версия читалась из payload (q+8), время — из соседнего бокса (q+12): карта якорей была
            мусорной на tfdt v0 (дефолт ffmpeg) — сик систематически промахивался, мост уезжал в recover/фолбэк */
          var t=(v===1?u64b(u,q+8):u32b(u,q+8))/ts;""")
F('F15 tfdt windows',
"""        if(q>0){ var v=win[q+8];
          cands.push({off:ws+bs,t:v===1?u64b(win,q+12):u32b(win,q+12)});
          var at=(((v===1?u64b(win,q+12):u32b(win,q+12))/ts)||0);   /* 45: якорь в карту (и пробные окна — тоже факты) */""",
"""        if(q>0){ var v=win[q+4];   /* 65: tfdt FullBox — версия @q+4, BMDT @q+8 (см. msebAnchors) */
          cands.push({off:ws+bs,t:v===1?u64b(win,q+8):u32b(win,q+8)});
          var at=(((v===1?u64b(win,q+8):u32b(win,q+8))/ts)||0);   /* 45: якорь в карту (и пробные окна — тоже факты) */""")

# ─── F16 msebPrevMoof размер ──────────────────────────────────────────────────
F('F16 prevMoof size',
"""      var off=from+pos-4,sz=u32b(u,pos);
      if(off<byte-8&&sz>=8){
        var okv=true;
        if(pos+sz+8<=u.length)okv=(typ4(u,pos+sz)==='mdat');   /* после moof обязан идти mdat — ложные сигнатуры внутри данных отсеиваются */""",
"""      var off=-1,sz=0;
      if(pos>=4){ off=from+pos-4; sz=u32b(u,pos-4) }   /* 65: размер бокса лежит ПЕРЕД типом; раньше читали ASCII 'moof' (~1.8млрд)
          — проверка «после moof идёт mdat» не срабатывала никогда */
      if(off<byte-8&&sz>=8){
        var okv=true;
        if(pos-4+sz+8<=u.length)okv=(typ4(u,pos-4+sz)==='mdat');   /* 65: соседний бокс — от начала moof-бокса */""")

# ─── F17 pump catch → recover ────────────────────────────────────────────────
F('F17 pump recover',
"""    }catch(e){ if(st.gen===myGen)NJ('open','MSE: качалка остановилась — '+e) }""",
"""    }catch(e){ if(st.gen===myGen){ NJ('open','MSE: качалка упала ('+e+') — реанимация');
      try{ msebRecover(el,'качалка остановилась: '+e) }catch(eR){} } }   /* 65: один обрыв сети больше не оставляет мост навсегда без качалки */""")

# ─── F18 кап reopen ───────────────────────────────────────────────────────────
F('F18 reopen cap',
"""async function msebReopen(el,tSec){
  var b=el._mseb; if(!b)return false;
  var it=b.it, wasPlaying=!!(b.playing||b.techPaused);   /* 50: тех-пауза от ошибки — тоже вернуть играющим */""",
"""async function msebReopen(el,tSec){
  var b=el._mseb; if(!b)return false;
  var it=b.it, wasPlaying=!!(b.playing||b.techPaused);   /* 50: тех-пауза от ошибки — тоже вернуть играющим */
  if(it){ it._mreopen=(it._mreopen||0)+1;
    if(it._mreopen>3){   /* 65: кап полных пересозданий на файл: каждый reopen обнулял deadResets
        свежего моста — «ядовитый» фрагмент гонял цикл сброс→пересоздание бесконечно */
      try{ MSEB_NO[it.id]=1 }catch(eM){}
      NJ('open','MSE: пересозданий больше 3 — файлу мост отключён до перезагрузки');
      try{ toast(t('errOpenFail'),'err') }catch(eT){}
      return false;
    }
  }""")

# ─── F19 msebFetch timeout+retry ──────────────────────────────────────────────
F('F19 msebFetch timeout',
"""function msebFetch(url,start,len){
  return fetch(url,{headers:{Range:'bytes='+start+'-'+(start+len-1)},cache:'no-store'})
    .then(function(r){ if(!r.ok&&r.status!=206)throw new Error('HTTP '+r.status); return r.arrayBuffer() })
    .then(function(ab){ return new Uint8Array(ab) });
}""",
"""function msebFetch(url,start,len){   /* 65: таймаут 10с + один ретрай: зависший фетч больше не блокирует качалку навсегда
    и не копит висячие коннекты до паралича всей сети к 127.0.0.1 */
  function mFetch1(){
    var ac=null; try{ ac=new AbortController() }catch(eA){}
    var tid=setTimeout(function(){ try{ if(ac)ac.abort() }catch(eB){} },10000);
    return fetch(url,{headers:{Range:'bytes='+start+'-'+(start+len-1)},cache:'no-store',signal:ac?ac.signal:undefined})
      .then(function(r){ clearTimeout(tid); if(!r.ok&&r.status!=206)throw new Error('HTTP '+r.status); return r.arrayBuffer() },
            function(eR){ clearTimeout(tid); throw eR })
      .then(function(ab){ return new Uint8Array(ab) });
  }
  return mFetch1().catch(function(){ return mFetch1() });
}""")

# ─── F20 doProbe revoke в catch ───────────────────────────────────────────────
F('F20 doProbe revoke',
"""  }catch(e){ if(!probeHarvest(it))it.status=(it.duration>0)?'ok':'bad'; }   /* 34: атомы дали длительность — «ok» без постера; живая карточка вместо «bad» */""",
"""  }catch(e){ try{ if(u)URL.revokeObjectURL(u) }catch(eU){} if(!probeHarvest(it))it.status=(it.duration>0)?'ok':'bad'; }   /* 34: атомы дали длительность — «ok» без постера; 65: URL пробы отзываем и в ошибке */""")

# ─── F21 cardPreview не плодим URL ────────────────────────────────────────────
F('F21 cardPreview url',
"""  ensure.then(function(f){
    if(!f||!cardPrevV)return;
    u=URL.createObjectURL(f);
    rememberUrl(it.id,u); cardPrevUrl=null;           /* URL в общем LRU — отзыв общим механизмом */
    go2();
  }).catch(function(){});""",
"""  ensure.then(function(f){
    if(!f||!cardPrevV)return;
    u=cachedUrl(it.id)||URL.createObjectURL(f);       /* 65: при живом кэше не плодим второй URL (rememberUrl его бы потерял) */
    rememberUrl(it.id,u); cardPrevUrl=null;           /* URL в общем LRU — отзыв общим механизмом */
    go2();
  }).catch(function(){});""")

# ─── F22 savePos гвард ────────────────────────────────────────────────────────
F('F22 savePos guard',
"""function savePos(force){
  if(currentIdx<0||!video.src)return;
  var it=items[currentIdx];
  it.position=(force===0)?0:video.currentTime;""",
"""function savePos(force){
  if(currentIdx<0||!video.src)return;
  var it=items[currentIdx];
  if(!it||(vActive&&vActive._pid)!==it.id)return;   /* 65: окно переключения: активный элемент ещё не владеет треком
    currentIdx — время уходящего раньше записывалось в позицию нового («назад»/pagehide посреди загрузки) */
  it.position=(force===0)?0:video.currentTime;""")

# ─── F23 мини-resync после swap ───────────────────────────────────────────────
F('F23 mini resync',
"""    if(it.audio){ miniThumb.innerHTML=miniArtHTML(it); }   /* 61: 404 арта → нота */
    else{ miniThumb.innerHTML=''; try{ vActive.style.transform=''; }catch(e){} miniThumb.appendChild(vActive); }
    miniIcon();
  }
  $('#tDur').textContent=fmtT(video.duration);   /* метаданные уже были — слушатель loadedmetadata не придёт */""",
"""    if(it.audio){ miniThumb.innerHTML=miniArtHTML(it); }   /* 61: 404 арта → нота */
    else{ miniThumb.innerHTML=''; try{ vActive.style.transform=''; }catch(e){} miniThumb.appendChild(vActive); }
    miniIcon();
  }
  else if(MINI.mode==='local'&&MINI.item===it&&!it.audio&&!miniThumb.contains(vActive)&&!(MIRROR.on&&MIRROR.mode==='stream')){
    /* 65: soft-close («свайп-назад») посреди загрузки: enterMini пересадил в панель УСТАРЕВШИЙ
       активный элемент (кадр A), а заголовок уже показывал B. После склейки приводим панель
       к факту: в мини — новый активный элемент (звук и кадр одного трека) */
    miniThumb.innerHTML='';
    try{ vActive.style.transform=''; }catch(eM){}
    miniThumb.appendChild(vActive);
    miniIcon();
  }
  $('#tDur').textContent=fmtT(video.duration);   /* метаданные уже были — слушатель loadedmetadata не придёт */""")

# ─── F24 PiP из мини ─────────────────────────────────────────────────────────
F('F24 natvPipEnter dock',
"""function natvPipEnter(){
  if(!NATV)return;
  if(!video.src){ toast(t('errPip'),'err'); return; }
  try{ natvCall('pipEnter',((vActive&&vActive.videoWidth)||16)+':'+((vActive&&vActive.videoHeight)||9)); }catch(e){}
}""",
"""function natvPipEnter(){
  if(!NATV)return;
  if(!video.src){ toast(t('errPip'),'err'); return; }
  try{ if(MINI.mode==='local'){ openMiniPlayer() } }catch(e0){}   /* 65: «PiP из мини»: живой элемент обязан вернуться
    в #stage ДО pipEnter — иначе body.pip прячет miniBar вместе с ЕДИНСТВЕННЫМ видео-элементом,
    и окно PiP показывает стоп-кадр/чёрное при играющем звуке */
  try{ natvCall('pipEnter',((vActive&&vActive.videoWidth)||16)+':'+((vActive&&vActive.videoHeight)||9)); }catch(e){}
}""")
F('F24 __pipMode dock',
"""    if(on){
      $('#pipT').textContent=fileNameOf(items[currentIdx]||{});
      pipHudSync(); pipHudSize(); pipTapShow();""",
"""    if(on){
      try{ if(MINI.mode==='local'){ openMiniPlayer() } }catch(eP){}   /* 65: авто-PiP (home-жест) из мини — тот же докинг,
        иначе окно PiP показывает стоп-кадр: элементы остаются в скрытом miniBar */
      $('#pipT').textContent=fileNameOf(items[currentIdx]||{});
      pipHudSync(); pipHudSize(); pipTapShow();""")

# ─── F25 swapRoles: PiP уходит за активным ────────────────────────────────────
F('F25 swapRoles PiP follow',
"""  try{ old.pause(); old.muted=true; }catch(e){}
  old._seekDone=false;                          /* при возврате к нему — перескок на сохранённую позицию */""",
"""  try{ old.pause(); old.muted=true; }catch(e){}
  try{                                          /* 65: уходящий элемент был зеркалом оконного PiP — окно уходит вместе
      с ним, иначе висит стоп-кадр старого трека при живом звуке нового (video→audio,
      swap при открытом PiP вне mirror-пути) */
    if(document.pictureInPictureElement&&old&&document.pictureInPictureElement===old&&document.exitPictureInPicture){
      document.exitPictureInPicture().catch(function(){}); PIP.native=false; PIP.mode='off';
    }
  }catch(e){}
  old._seekDone=false;                          /* при возврате к нему — перескок на сохранённую позицию */""")

# ─── F26 swapRoles: сброс seek-таймеров ───────────────────────────────────────
F('F26 swapRoles timers',
"""function swapRoles(){
  var old=vActive, sb=vStandby;
  lastBufs='\\u0000';                            /* кэш полос буфера больше не про тот элемент */""",
"""function swapRoles(){
  var old=vActive, sb=vStandby;
  try{ clearTimeout(seekStuckT); clearTimeout(seekSpinT) }catch(e){}   /* 65: seek-таймеры уходящего элемента
      не должны сработать уже по новому video и дёрнуть лишний reloadActiveTo */
  lastBufs='\\u0000';                            /* кэш полос буфера больше не про тот элемент */""")

# ─── F27 поток-вочдог в мини ──────────────────────────────────────────────────
F('F27 flow watchdog mini',
"""    if(player.hidden||!video.src||video.paused||video.ended||video.error||video.seeking)return;
    if(video._mseb)return;                            /* MSE-мост следит за буфером сам (v51) */""",
"""    if((player.hidden&&MINI.mode!=='local')||!video.src||video.paused||video.ended||video.error||video.seeking)return;   /* 65: в мини-панели поток тоже лечим — зависший кадр фризил навсегда */
    if(video._mseb)return;                            /* MSE-мост следит за буфером сам (v51) */""")

# ─── F28 openItem !ok — вернуть игру уходящему ────────────────────────────────
F('F28 openItem wasPlaying',
"""  if(!vActive.paused)quietPause(vActive);   /* 23.1/26.2: старый звук глушим сразу и ТИХО —
    пауза открытия не поднимает панель (вспышка UI на старте свайпнутого видео) */""",
"""  var wasPrevPlaying=!vActive.paused;       /* 65: помним, был ли прошлый трек играющим */
  if(wasPrevPlaying)quietPause(vActive);   /* 23.1/26.2: старый звук глушим сразу и ТИХО —
    пауза открытия не поднимает панель (вспышка UI на старте свайпнутого видео) */""")
F('F28 openItem resume',
"""      try{ profApply(prevIdx>=0?items[prevIdx]:null) }catch(e){}   /* 37.4: неудача — профиль играющего трека возвращается (применяли же нового) */
      try{ applyAudio(); applyFilters(); applyFit() }catch(e){}   /* 33.1: неудача — старый трек снова слышим: mute был служебным */""",
"""      try{ profApply(prevIdx>=0?items[prevIdx]:null) }catch(e){}   /* 37.4: неудача — профиль играющего трека возвращается (применяли же нового) */
      try{ applyAudio(); applyFilters(); applyFit() }catch(e){}   /* 33.1: неудача — старый трек снова слышим: mute был служебным */
      try{ if(wasPrevPlaying&&vActive._pid&&(!it||it.id!==vActive._pid))vActive.play() }catch(eP){}   /* 65: не оставляем
        уходящий трек замороженным кадром без звука — возвращаем то, что играло до неудачного открытия */""")

# ─── F29 pump пауза-такт ──────────────────────────────────────────────────────
F('F29 pump pause tick',
"""          if(myT>tgt+hi){ await msebSleep(320); continue }
        }else if(ahead>hi){ await msebSleep(320); continue }""",
"""          if(myT>tgt+hi){ await msebSleep(el.paused?1000:320); continue }   /* 65: пауза — такт раз в секунду, фон не будим зря */
        }else if(ahead>hi){ await msebSleep(el.paused?1000:320); continue }""")

# ─── F30 msebSleep busy-spin ──────────────────────────────────────────────────
F('F30 msebSleep throttle',
"""    var step=function(){
      if(Date.now()-t0>=ms-8){ try{mc.port1.close();mc.port2.close()}catch(e2){} res(); return }
      mc.port1.onmessage=function(){ mc.port1.onmessage=null; step() };
      try{ mc.port2.postMessage(0) }catch(e3){ setTimeout(res,Math.max(0,ms-(Date.now()-t0))) }
    };""",
"""    var done=function(){ try{mc.port1.close();mc.port2.close()}catch(e2){} res() };
    var step=function(){
      if(Date.now()-t0>=ms-8){ done(); return }
      mc.port1.onmessage=function(){ mc.port1.onmessage=null; setTimeout(function(){   /* 65: микро-пауза 8мс между макротасками —
          MessageChannel-сон без неё крутил сотни-тысячи тиков в секунду в фоне */
        if(Date.now()-t0>=ms-8){ done(); return }
        step() },8) };
      try{ mc.port2.postMessage(0) }catch(e3){ setTimeout(res,Math.max(0,ms-(Date.now()-t0))) }
    };""")

# ─── F31 сик: неудача поиска байта ────────────────────────────────────────────
F('F31 seekByte -1',
"""  var byte;
  try{ byte=await msebTimeToByte(url,tSec,b) }catch(e){ byte=b.initEnd||0 }""",
"""  var byte;
  try{ byte=await msebTimeToByte(url,tSec,b) }catch(e){ return -1 }   /* 65: неудача поиска — сигнал наверх;
      раньше молча «сажались» в начало файла: сик выглядел успешным, а данные к цели не везлись */""")
F('F31 msebSeek byte<0',
"""  var byte=await msebSeekByte(b.furl||b.url,t,b);   /* 48: байт выровнен на ключевой кадр — аппенд не начинается с P-кадра */
  if(el._mseb!==b||b.dead||b.seekSeq!==mySq)return;   /* 46: сик перебит/мост снесли, пока искали байт — тихо уходим
      (в 3.0 здесь выживал зомби и вешал мёртвый мост поверх фолбэка) */
  byte=Math.max(b.initEnd,Math.min(byte,b.size-1));""",
"""  var byte=await msebSeekByte(b.furl||b.url,t,b);   /* 48: байт выровнен на ключевой кадр — аппенд не начинается с P-кадра */
  if(el._mseb!==b||b.dead||b.seekSeq!==mySq)return;   /* 46: сик перебит/мост снесли, пока искали байт — тихо уходим
      (в 3.0 здесь выживал зомби и вешал мёртвый мост поверх фолбэка) */
  if(byte<0){ NJ('open','MSE: байт сика не найден (окна мимо) — реанимация'); try{ msebRecover(el,'сик: байт не найден') }catch(eR1){} return }   /* 65 */
  byte=Math.max(b.initEnd,Math.min(byte,b.size-1));""")

# ─── F32 токен моста: разбор из URL страницы + хелпер ─────────────────────────
F('F32 natvTok helper',
"""var NATV=false, NATV_PIP=false, NATV_FS=false, NATV_BASE='http://127.0.0.1:8977';
try{ NATV=!!(window.PlenkaNative&&typeof window.PlenkaNative.scan==='function'); }catch(e){}""",
"""var NATV=false, NATV_PIP=false, NATV_FS=false, NATV_BASE='http://127.0.0.1:8977';
try{ NATV=!!(window.PlenkaNative&&typeof window.PlenkaNative.scan==='function'); }catch(e){}
var NATV_TOK=(function(){ try{ var mT=(location.search||'').match(/[?&]tok=([A-Za-z0-9_-]+)/); return mT?mT[1]:'' }catch(eT){ return '' } })();   /* 65: токен локального моста —
  оболочка кладёт его в URL страницы; loopback Android общий для всех процессов, поэтому данные
  (/v,/a,/c,/t, списки) без валидного токена отдают 404 — чужое приложение медиатеку не выкачает */
function natvTok(p){ return (NATV&&NATV_TOK)?(p+((p.indexOf('?')<0?'?':'&')+'tok='+NATV_TOK)):p }""")

# ─── F33 natvTok на всех построителях URL ────────────────────────────────────
F('F33 thumbUrl',
"""  return NATV_BASE+'/t/'+m.k+'/'+m.id+vq+(vq?'&':'?')+'r='+(m.s||0)+'-'+(m.t||0)+'&f=3';""",
"""  return natvTok(NATV_BASE+'/t/'+m.k+'/'+m.id+vq+(vq?'&':'?')+'r='+(m.s||0)+'-'+(m.t||0)+'&f=3');""")
F('F33 media url',
"""    var key=m.k+':'+m.id, url=NATV_BASE+'/'+m.k+'/'+m.id+(m.vol?('?vol='+encodeURIComponent(m.vol)):'');   /* 2.1: вторичные тома (SD) — id различны на каждом томе */""",
"""    var key=m.k+':'+m.id, url=natvTok(NATV_BASE+'/'+m.k+'/'+m.id+(m.vol?('?vol='+encodeURIComponent(m.vol)):''));   /* 2.1: вторичные тома (SD) — id различны на каждом томе */""")
F('F33 picked url',
"""  var id='nc:'+m.id, url=NATV_BASE+'/c/'+m.id;""",
"""  var id='nc:'+m.id, url=natvTok(NATV_BASE+'/c/'+m.id);""")
F('F33 picked thumb a',
"""      var thu=NATV_BASE+'/t/c/'+m.id+'?r='+(m.s||0)+'-'+(m.t||0);   /* 2.4: превью ручного выбора — тем же /t/ */""",
"""      var thu=natvTok(NATV_BASE+'/t/c/'+m.id+'?r='+(m.s||0)+'-'+(m.t||0));   /* 2.4: превью ручного выбора — тем же /t/ */""")
F('F33 picked thumb b',
"""        thumb:NATV_BASE+'/t/c/'+m.id+'?r='+(m.s||0)+'-'+(m.t||0)};""",
"""        thumb:natvTok(NATV_BASE+'/t/c/'+m.id+'?r='+(m.s||0)+'-'+(m.t||0))};""")

# ─── F34 миграция URL в IDB после обновления ─────────────────────────────────
F('F34 tok migration',
"""    NJ('init','первый синк медиатеки (items='+items.length+' после рестора)');
    nativeSync(false);
    natvPickedSync(false);       /* native 2.1: реестр SAF — живой источник, IDB лишь кэш */""",
"""    NJ('init','первый синк медиатеки (items='+items.length+' после рестора)');
    try{ if(NATV&&NATV_TOK){ var nTk=0;   /* 65: миграция после обновления — у записей из IDB нет токена моста */
      for(var qT=0;qT<items.length;qT++){ var xT=items[qT];
        if(xT&&xT.kind==='native'&&xT.url&&xT.url.indexOf('tok=')<0){ xT.url=natvTok(xT.url); nTk++; persistItem(xT); } }
      if(nTk)NJ('init','токен моста: обновлено URL у '+nTk+' записей');
    } }catch(eTk){}
    nativeSync(false);
    natvPickedSync(false);       /* native 2.1: реестр SAF — живой источник, IDB лишь кэш */""")

# ─── применение ───────────────────────────────────────────────────────────────
ok = True
for name, old, new in FIXES:
    n = src.count(old)
    if n != 1:
        print(f"[FAIL] {name}: якорь найден {n} раз(а)")
        ok = False
        continue
    src = src.replace(old, new)
    print(f"[OK]   {name}")
if not ok:
    print("\nЕсть неприменённые фиксы — сборка прервана, v65 НЕ записана.")
    sys.exit(1)

open(DST, 'w', encoding='utf-8').write(src)
print(f"\nv65 записана: {DST} ({len(src)} байт, фиксов: {len(FIXES)})")
