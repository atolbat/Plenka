/* ═══════════════════ ЛАБОРАТОРИЯ /seek · v52 · стенд 2 (нативный поток) ═══════════════════
   Сервер оболочки отдаёт этот же HTML по пути /seek — страница поднимается в режиме
   лаборатории вместо приложения. MSE-мост в v52 убран: все файлы играют нативным
   потоком (localhost + Range), как file:// — стенд меряет именно этот путь:
   открытие с нуля, резюм-открытие, сики (50/75/конец−15с/назад/шквал/сразу),
   живучесть элемента и ХВОСТ — качество последних секунд с замером пауз
   (waiting) и дрейфа декода (медиа-время против реального). */
var __LAB=false;
try{ __LAB=/(^|\/)seek\/?$/.test(location.pathname); }catch(e){}
var LAB={el:null,url:'',label:'',size:0,metaDur:0,log:[],res:[],stalls:[],stall0:0,test:'',busy:false,report:'',list:null,pickVol:''};
function LJ(tag,msg){
  var line='+'+(performance.now()/1000).toFixed(1)+'s '+tag+': '+msg;
  LAB.log.push(line);
  if(LAB.log.length>420)LAB.log.splice(0,LAB.log.length-420);
  try{ if(window.__plenkaJ)__plenkaJ('lab:'+tag,msg) }catch(e){}
  var lg=document.getElementById('labLog');
  if(lg){ lg.textContent=LAB.log.slice(-90).join('\n'); lg.scrollTop=lg.scrollHeight; }
}
function labErrName(c){ return c===1?'MEDIA_ERR_ABORTED':c===2?'MEDIA_ERR_NETWORK':c===3?'MEDIA_ERR_DECODE':c===4?'MEDIA_ERR_SRC_NOT_SUPPORTED':'код '+c; }
function labVer(){ try{ return (''+PlenkaNative.version()) }catch(e){ return 'объект есть, version() упал' } }
function labBridge(){ try{ return (typeof PlenkaNative==='object')?('есть ('+labVer()+')'):'нет — Chrome-режим' }catch(e){ return 'нет — Chrome-режим' } }
function labDur(){ var el=LAB.el; if(el&&isFinite(el.duration)&&el.duration>0)return el.duration; return LAB.metaDur||0; }
function labWire(el){
  var sus=0;
  ['emptied','abort','loadstart','durationchange','loadedmetadata','canplay','playing','pause','ended','stalled','seeking','seeked'].forEach(function(ev){
    el.addEventListener(ev,function(){
      LJ(LAB.test||'open','событие: '+ev+(ev==='durationchange'&&isFinite(el.duration)?' (длительность='+fmtT(el.duration)+')':''));
    });
  });
  el.addEventListener('suspend',function(){ sus++; if(sus<=6||sus%5===0)LJ(LAB.test||'open','событие: suspend'); });
  el.addEventListener('waiting',function(){
    if(LAB.stall0)return;
    LAB.stall0=performance.now();
    LJ(LAB.test||'open','событие: waiting (пауза @ '+fmtT(el.currentTime)+')');
  });
  ['playing','seeked','canplay','pause','ended'].forEach(function(ev){
    el.addEventListener(ev,function(){
      if(!LAB.stall0)return;
      var ms=performance.now()-LAB.stall0; LAB.stall0=0;
      if(ms<60)return;
      LAB.stalls.push({t:LAB.test||'фон',ms:Math.round(ms),at:el.currentTime});
      LJ(LAB.test||'open','пауза '+(ms<1000?Math.round(ms)+'мс':(ms/1000).toFixed(1)+'с')+' — возобновление по '+ev);
    });
  });
  el.addEventListener('error',function(){
    LJ(LAB.test||'open','ОШИБКА элемента: '+(el.error?(labErrName(el.error.code)+(el.error.message?' · '+el.error.message:'')):'без кода'));
  });
}
function labKill(){
  var el=LAB.el;
  if(!el)return;
  try{ el.pause() }catch(e){}
  try{ el.removeAttribute('src'); el.load() }catch(e){}
  try{ if(el.parentNode)el.parentNode.removeChild(el) }catch(e){}
  LAB.el=null; LAB.stall0=0;
}
function labNewEl(){
  labKill();
  var el=document.createElement('video');
  el.muted=true; el.setAttribute('playsinline',''); el.preload='auto';
  el.style.cssText='width:100%;max-height:38vh;background:#000;object-fit:contain;display:block';
  labWire(el);
  var host=document.getElementById('labStage');
  if(host){ host.innerHTML=''; host.appendChild(el); }
  LAB.el=el;
  return el;
}
function labW(m){ return once(LAB.el,m[0],m[1]); }
async function labWaitData(cap){
  var el=LAB.el,g0=performance.now();
  cap=cap||2500;
  while(performance.now()-g0<cap){
    if(el.error)return false;
    if(el.readyState>=2&&!el.seeking)return true;
    await new Promise(function(r){ setTimeout(r,40) });
  }
  return el.readyState>=2&&!el.seeking&&!el.error;
}
async function labPlay(cap){
  var el=LAB.el; if(!el)return false;
  var p=el.play(); if(p&&p.catch)p.catch(function(){});
  try{ await once(el,'playing',cap||6000); return !el.error; }catch(e){ return !el.error&&el.readyState>=2; }
}
async function labEnsurePlaying(){
  var el=LAB.el; if(!el)return false;
  if(!el.paused&&!el.ended)return true;
  return await labPlay();
}
async function labOpenFresh(){
  var el=labNewEl(), t0=performance.now(), ev;
  LJ('open','открываем нативным потоком: '+LAB.label);
  el.src=LAB.url; try{ el.load() }catch(e){}
  try{ ev=await once(el,['loadedmetadata','error'],20000); }catch(e){ ev='timeout'; }
  var tMeta=Math.round(performance.now()-t0);
  if(ev==='error')return {ok:false,why:'ошибка элемента',ms:tMeta};
  if(ev==='timeout')return {ok:false,why:'метаданные не пришли за 20с',ms:tMeta};
  var tCan=tMeta;
  try{ await once(el,['canplay','error'],9000); tCan=Math.round(performance.now()-t0); }catch(e){ return {ok:false,why:'canplay не пришёл',ms:tCan}; }
  var okp=await labPlay(7000);
  var m={dur:isFinite(el.duration)?el.duration:0,w:el.videoWidth,h:el.videoHeight,rs:el.readyState};
  LAB.metaDur=m.dur||LAB.metaDur;
  if(!okp)return {ok:false,why:'playing не наступил',ms:tCan,m:m};
  return {ok:m.dur>0,why:m.dur>0?'':'длительность 0',ms:tCan,m:m};
}
async function labSeekF(f,target,cap){
  var el=LAB.el, dur=labDur();
  if(!dur)return {ok:false,why:'длительность неизвестна',ms:0};
  var tg=(target!=null)?target:Math.max(0,Math.min(dur-0.05,dur*f));
  var t0=performance.now(), ok=true;
  try{ el.currentTime=tg; await once(el,['seeked','error'],cap||9000); }catch(e){ ok=false; }
  await labWaitData(2500);
  var ms=Math.round(performance.now()-t0);
  return {ok:ok&&!el.error&&el.readyState>=2,ms:ms,tg:tg,rs:el.readyState};
}
async function labSeekBurst(){ /* шквал: 6 сиков подряд без ожидания, потом устойчивость */
  var el=LAB.el, dur=labDur(), t0=performance.now();
  var fr=[0.1,0.3,0.5,0.7,0.9,0.2];
  for(var i=0;i<fr.length;i++){
    (function(f,d){ setTimeout(function(){ try{ el.currentTime=Math.max(0,Math.min(d-0.05,d*f)) }catch(e){} },d?i*140:0); })(fr[i],dur);
  }
  var ok=false, cap=performance.now()+9000;
  while(performance.now()<cap){
    if(el.error)break;
    if(performance.now()-t0>fr.length*140+450&&el.readyState>=2&&!el.seeking&&!el.paused&&!el.ended){ ok=true; break; }
    await new Promise(function(r){ setTimeout(r,60) });
  }
  return {ok:ok,ms:Math.round(performance.now()-t0),pos:el.currentTime};
}
var LABTESTS=[
 {n:'открыть (нативный поток — с нуля)',run:function(){ return labOpenFresh().then(function(r){
    if(!r.ok)return ['FAIL','открытие не удалось ('+r.why+', '+r.ms+'мс)'];
    LAB.size=LAB.size||0;
    return ['PASS','нативный поток · кадр '+(r.m.w||'?')+'×'+(r.m.h||'?')+' · длительность '+fmtT(r.m.dur)+' ('+r.ms+'мс)'];
  }); }},
 {n:'резюм-открытие (50%)',run:async function(){
    var dur=labDur();
    if(!dur)return ['FAIL','длительность неизвестна'];
    if(dur<2)return ['SKIP','ролик короче 2с — резюм-позиция совпадает со стартом ('+fmtT(dur)+')'];
    var el=labNewEl(), t0=performance.now();
    el.src=LAB.url; try{ el.load() }catch(e){}
    try{ await once(el,'loadedmetadata',16000); }catch(e){ return ['FAIL','метаданные не пришли']; }
    var tg=dur*0.5;
    el.currentTime=tg;
    try{ await once(el,'seeked',9000); }catch(e){}
    await labWaitData(2500);
    if(Math.abs(el.currentTime-tg)>0.7)return ['FAIL','позиция не встала ('+fmtT(el.currentTime)+' вместо '+fmtT(tg)+')'];
    var okp=await labPlay(7000);
    if(!okp)return ['FAIL','после резюма не играет'];
    return ['PASS','старт с '+fmtT(el.currentTime)+' (цель '+fmtT(tg)+') · играет ('+Math.round(performance.now()-t0)+'мс)'];
 }},
 {n:'сик 50%',run:async function(){
    var dur=labDur();
    if(!dur)return ['FAIL','длительность неизвестна'];
    if(dur<2.5)return ['SKIP','длительность мала ('+fmtT(dur)+')'];
    await labEnsurePlaying();
    var r=await labSeekF(0.5);
    if(!r.ok)return ['FAIL','сик не завершился ('+(r.rs!==undefined?('readyState '+r.rs):'таймаут')+')'];
    return ['PASS',r.ms+'мс · позиция '+fmtT(r.tg)];
 }},
 {n:'сик 75%',run:async function(){
    var dur=labDur();
    if(!dur)return ['FAIL','длительность неизвестна'];
    if(dur<2.5)return ['SKIP','длительность мала ('+fmtT(dur)+')'];
    await labEnsurePlaying();
    var r=await labSeekF(0.75);
    if(!r.ok)return ['FAIL','сик не завершился'];
    return ['PASS',r.ms+'мс · позиция '+fmtT(r.tg)];
 }},
 {n:'сик конец−15с',run:async function(){
    var dur=labDur();
    if(!dur)return ['FAIL','длительность неизвестна'];
    if(dur<6)return ['SKIP','ролик короче 6с («конец−15с» вырождается в конец−'+(dur*0.25).toFixed(1)+'с — меряет хвостовой тест)'];
    var back=Math.min(15,dur*0.25);
    await labEnsurePlaying();
    var r=await labSeekF(0,dur-back);
    if(!r.ok)return ['FAIL','сик не завершился'];
    return ['PASS',r.ms+'мс · позиция '+fmtT(r.tg)+' (конец минус '+back.toFixed(0)+'с)'];
 }},
 {n:'сик назад 75%→25%',run:async function(){
    var dur=labDur();
    if(!dur)return ['FAIL','длительность неизвестна'];
    if(dur<4)return ['SKIP','длительность мала ('+fmtT(dur)+')'];
    await labEnsurePlaying();
    var r1=await labSeekF(0.75);
    if(!r1.ok)return ['FAIL','первый сик (75%) не завершился'];
    var r2=await labSeekF(0.25);
    if(!r2.ok)return ['FAIL','сик назад не завершился'];
    return ['PASS','назад за '+r2.ms+'мс (вперёд было '+r1.ms+'мс)'];
 }},
 {n:'шквал 6 сиков',run:async function(){
    var dur=labDur();
    if(!dur)return ['FAIL','длительность неизвестна'];
    if(dur<3)return ['SKIP','длительность мала ('+fmtT(dur)+')'];
    await labEnsurePlaying();
    var r=await labSeekBurst();
    if(!r.ok)return ['FAIL','после шквала элемент не играет/не устоял'];
    return ['PASS','устоял за '+r.ms+'мс · позиция '+fmtT(r.pos)];
 }},
 {n:'сик сразу после открытия',run:async function(){
    var dur=labDur();
    if(!dur)return ['FAIL','длительность неизвестна'];
    if(dur<2.5)return ['SKIP','длительность мала ('+fmtT(dur)+')'];
    var el=labNewEl(), t0=performance.now();
    el.src=LAB.url; try{ el.load() }catch(e){}
    try{ await once(el,'loadedmetadata',16000); }catch(e){ return ['FAIL','метаданные не пришли']; }
    el.currentTime=dur*0.9;
    var ok=true;
    try{ await once(el,'seeked',9000); }catch(e){ ok=false; }
    if(!ok)return ['FAIL','seeked не пришёл'];
    var okd=await labWaitData(2500);
    var okp=await labPlay(7000);
    if(!okp)return ['FAIL','играть после сика не начал'];
    return ['PASS','готов за '+Math.round(performance.now()-t0)+'мс'+(okd?'':' (данные догружались)')+' · играет с '+fmtT(el.currentTime)];
 }},
 {n:'живучесть: убить элемент → реанимация',run:async function(){
    var el=LAB.el;
    if(!el)return ['FAIL','элемента нет'];
    await labEnsurePlaying();
    LJ('test','убиваем: src убран, load()');
    try{ el.pause() }catch(e){}
    try{ el.removeAttribute('src'); el.load() }catch(e){}
    try{ await once(el,'emptied',2500); }catch(e){}
    await new Promise(function(r){ setTimeout(r,400) });
    var t0=performance.now();
    el.src=LAB.url; try{ el.load() }catch(e){}
    try{ await once(el,'canplay',10000); }catch(e){ return ['FAIL','реанимация: canplay не пришёл']; }
    var okp=await labPlay(7000);
    if(!okp)return ['FAIL','после реанимации не играет'];
    return ['PASS','ожил за '+Math.round(performance.now()-t0)+'мс'];
 }},
 {n:'хвост: качество последних секунд',run:async function(){
    var dur=labDur();
    if(!dur)return ['FAIL','длительность неизвестна'];
    if(dur<1.5)return ['SKIP','ролик слишком короткий для хвоста ('+fmtT(dur)+')'];
    var el=LAB.el;
    if(!el)el=labNewEl();
    var tailWin=Math.min(3,Math.max(1,dur*0.35));
    /* короткие ролики (≤12с): входим с середины и играем НАТУРАЛЬНО до конца —
       ровно сценарий жалобы «в конце видео лаг»; длинные: сик прямо в хвост */
    var startAt=(dur<=12)?Math.max(0,dur*0.45):Math.max(0,dur-tailWin-0.3);
    await labEnsurePlaying();
    LJ('test','хвост: '+(dur<=12
      ?('играем с '+fmtT(startAt)+' до конца естественно — последние '+tailWin.toFixed(1)+'с под микроскопом')
      :('сик на '+fmtT(startAt)+', следим до ended')));
    var t0s=performance.now(), okS=true;
    try{ el.currentTime=startAt; await once(el,'seeked',9000); }catch(e){ okS=false; }
    if(!okS)return ['FAIL','сик в хвост не завершился'];
    var tSeek=Math.round(performance.now()-t0s);
    if(el.paused){ var p=el.play(); if(p&&p.catch)p.catch(function(){}); }
    try{ await once(el,'playing',6000); }catch(e){}
    LAB.stall0=0;                    /* паузы ДО старта хвоста (сам сик) не считаются */
    var t0=performance.now(), st0=LAB.stalls.length, ended=false;
    var capMs=Math.max(15000,((dur-startAt)+2)*3000+6000);
    while(performance.now()-t0<capMs){
      if(el.error)return ['FAIL','ошибка элемента в хвосте: '+labErrName(el.error.code)];
      if(el.ended){ ended=true; break; }
      await new Promise(function(r){ setTimeout(r,100) });
    }
    var wall=(performance.now()-t0)/1000;
    var media=Math.max(0,el.currentTime-startAt);
    if(!ended)return ['FAIL','ended не наступил за '+wall.toFixed(1)+'с (медиа на '+fmtT(el.currentTime)+')'];
    var sts=LAB.stalls.slice(st0);
    var stSum=0; sts.forEach(function(s){ stSum+=s.ms; });
    var drift=(media>0.4)?(wall/media):1;
    var base='вход за '+tSeek+'мс'+(sts.length?(' · пауз '+sts.length+' ('+stSum+'мс)'):' · без пауз')
      +' · '+media.toFixed(1)+'с контента за '+wall.toFixed(1)+'с';
    if(stSum>=120)return ['FAIL',base];
    if(drift>1.3)return ['FAIL','декод не поспевает: '+base];
    return ['PASS',base+(drift>1.05?(' (замедление '+Math.round(drift*100)+'%)'):'')];
 }}
];
function labReport(){
  var np=0,nf=0,ns=0;
  LAB.res.forEach(function(r){ if(r.r==='PASS')np++; else if(r.r==='FAIL')nf++; else ns++; });
  var lines=[];
  lines.push('ПЛЁНКА /seek · стенд 2 (страница v52 · нативный поток — MSE-мост убран в v52)');
  lines.push('UA: '+navigator.userAgent);
  lines.push('мост: '+labBridge());
  lines.push('цель: '+(LAB.label||'(не выбрана)'));
  lines.push('итог: PASS '+np+' / FAIL '+nf+(ns?' / SKIP '+ns:'')+' · '+new Date().toTimeString().slice(0,8));
  LAB.res.forEach(function(r){ lines.push('['+r.r+'] '+r.n+' — '+r.d); });
  LAB.report=lines.join('\n')+'\n\n— журнал (последние 90) —\n'+LAB.log.slice(-90).join('\n');
  var rp=document.getElementById('labRep');
  if(rp){ rp.hidden=false; rp.textContent=LAB.report; }
  return LAB.report;
}
async function labRunAll(){
  if(LAB.busy)return;
  var tg=labTarget();               /* ввод мог смениться после «Открыть» — переприцеливаемся */
  if(!tg&&!LAB.url){ LJ('open','сначала выберите цель (id или /v/<id>)'); return; }
  LAB.busy=true;
  var btn=document.getElementById('labRun'); if(btn)btn.disabled=true;
  try{
    LAB.res=[];
    for(var i=0;i<LABTESTS.length;i++){
      var t=LABTESTS[i], short=t.n.replace(/\s*\(.*\)$/,'');
      LAB.test=short;
      LJ('test','════ '+t.n+' ════');
      var st0=LAB.stalls.length, out;
      try{ out=await t.run(); }catch(e){ out=['FAIL','исключение: '+((e&&e.message)||e)]; }
      var sts=LAB.stalls.slice(st0), stSum=0;
      sts.forEach(function(s){ stSum+=s.ms; });
      if(out[0]==='PASS'&&sts.length&&t.n.indexOf('хвост')!==0){
        out[1]+=' · пауз '+sts.length+' ('+stSum+'мс)';
      }
      LAB.res.push({r:out[0],n:t.n,d:out[1]});
      LJ('test','['+out[0]+'] '+t.n+' — '+out[1]);
      LAB.test='';
      await new Promise(function(r){ setTimeout(r,180) });
    }
    labReport();
  }finally{
    LAB.busy=false; LAB.test='';
    if(btn)btn.disabled=false;
  }
}
async function labOpenBtn(){
  if(LAB.busy)return;
  var tg=labTarget();
  if(!tg){ LJ('open','цель не распознана — введите id или /v/<id>'); return; }
  LAB.busy=true;
  var btn=document.getElementById('labOpenBtn'); if(btn)btn.disabled=true;
  try{
    LAB.test='открыть';
    LJ('test','════ '+LABTESTS[0].n+' ════');
    var out;
    try{ out=await LABTESTS[0].run(); }catch(e){ out=['FAIL','исключение: '+((e&&e.message)||e)]; }
    LAB.res=[{r:out[0],n:LABTESTS[0].n,d:out[1]}];
    LJ('test','['+out[0]+'] '+LABTESTS[0].n+' — '+out[1]);
    LAB.test='';
    labReport();
  }finally{
    LAB.busy=false;
    if(btn)btn.disabled=false;
  }
}
async function labLoadList(){
  var sel=document.getElementById('labList');
  try{
    var r=await fetch('/list',{cache:'no-store'});
    if(!r.ok){ LJ('list','/list → HTTP '+r.status); return; }
    var j=await r.json();
    if(!j||!j.items||!j.items.length){ LJ('list','список пуст'); return; }
    LAB.list=j.items;
    var nV=0;
    if(sel){
      sel.innerHTML='';
      j.items.forEach(function(m){
        if(m.k!=='v')return;
        nV++;
        var o=document.createElement('option');
        o.value=String(m.id)+(m.vol?('\t'+m.vol):'');
        o.textContent=(m.n||('id '+m.id))+(m.s?' · '+fmtSize(m.s):'')+(m.d?' · '+fmtT(Math.round(m.d/1000)):'');
        sel.appendChild(o);
      });
      sel.hidden=(nV===0);
      sel.onchange=function(){
        var v=(''+this.value).split('\t');
        document.getElementById('labId').value=v[0];
        LAB.pickVol=(v[1]||'');
        var found=null;
        if(LAB.list)LAB.list.forEach(function(x){ if(String(x.id)===v[0]&&(!x.vol||x.vol===LAB.pickVol))found=x; });
        LAB.selIt=found;
      };
    }
    LJ('list','медиатека: '+j.items.length+' файлов, видео в списке: '+nV);
  }catch(e){ LJ('list','/list недоступен: '+((e&&e.message)||e)); }
}
function labTarget(){
  var raw=(''+(document.getElementById('labId').value||'')).trim();
  if(!raw)return null;
  var k='v',id=raw,vol=LAB.pickVol||'',it=null;
  var mm=raw.match(/\/(v|a|c)\/(\d+)/);
  if(mm){ k=mm[1]; id=mm[2]; vol=''; }
  else if(/^c\d+$/i.test(raw)){ k='c'; id=raw.slice(1); }
  else if(!/^\d+$/.test(raw))return null;
  if(LAB.list)LAB.list.forEach(function(x){ if(String(x.id)===id&&String(x.k)===k&&(!x.vol||x.vol===vol))it=x; });
  if(it&&!LAB.selIt)LAB.selIt=it;
  if(LAB.selIt&&String(LAB.selIt.id)===id)it=LAB.selIt;
  LAB.url='/'+k+'/'+id+(vol?('?vol='+encodeURIComponent(vol)):'');
  LAB.label='/'+k+'/'+id+(it&&it.s?' · '+fmtSize(it.s):'')+(it&&it.d?' · '+fmtT(Math.round(it.d/1000)):'');
  LAB.size=(it&&it.s)||0;
  return {k:k,id:id,url:LAB.url,it:it};
}
function labLegacyCopy(txt){
  try{
    var ta=document.createElement('textarea');
    ta.value=txt; ta.style.cssText='position:fixed;opacity:0';
    document.body.appendChild(ta); ta.select();
    var ok=document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  }catch(e){ return false; }
}
function labCopy(){
  var txt=LAB.report||labReport();
  var done=document.getElementById('labCopyDone');
  function ok(){ if(done){ done.style.display='inline'; setTimeout(function(){ done.style.display='none' },1800); } }
  try{
    navigator.clipboard.writeText(txt).then(ok,function(){ if(labLegacyCopy(txt))ok(); else LJ('copy','не вышло — выделите текст отчёта вручную'); });
  }catch(e){ if(labLegacyCopy(txt))ok(); }
}
function __plenkaLabBoot(){
  try{ document.body.className='' }catch(e){}
  try{ document.title='ПЛЁНКА · лаборатория перемотки' }catch(e){}
  document.body.innerHTML='';
  var css=document.createElement('style');
  css.textContent='#labRoot{max-width:780px;margin:0 auto;padding:14px 12px 46px;font:13px/1.55 system-ui,sans-serif;color:#e8dfd0;background:#151210;min-height:100vh}'
   +'#labRoot h1{font-size:15px;margin:0 0 4px;color:#f0c46a;letter-spacing:.5px;font-weight:700}'
   +'#labRoot .sub{color:#9a917f;font-size:12px;margin:0 0 12px}'
   +'#labRoot .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:6px 0 10px}'
   +'#labRoot input,#labRoot select{background:#221f1a;color:#eee;border:1px solid #3a352c;border-radius:9px;padding:9px 11px;font-size:13px;min-width:160px;flex:1}'
   +'#labRoot button{background:#f0c46a;color:#241d10;border:0;border-radius:9px;padding:9px 15px;font-weight:700;font-size:13px;cursor:pointer;flex:none}'
   +'#labRoot button:disabled{opacity:.45;cursor:default}'
   +'#labRoot #labStage{margin:10px 0;background:#000;border-radius:11px;overflow:hidden}'
   +'#labRoot pre{background:#1c1915;border:1px solid #2e2a22;border-radius:11px;padding:11px;margin:8px 0;white-space:pre-wrap;word-break:break-word;font:11px/1.5 ui-monospace,Menlo,Consolas,monospace;color:#cfc6b4;max-height:340px;overflow:auto}'
   +'#labRoot #labCopyDone{color:#7dc98a;font-size:12px;align-self:center}';
  document.head.appendChild(css);
  var root=document.createElement('div');
  root.id='labRoot';
  root.innerHTML='<h1>ПЛЁНКА · лаборатория перемотки</h1>'
   +'<div class="sub">стенд 2 — страница v52 · нативный поток (MSE-мост убран в v52: все файлы играют как file://)</div>'
   +'<div class="row">'
   +'<select id="labList" hidden aria-label="медиатека"></select>'
   +'<input id="labId" placeholder="id или /v/&lt;id&gt;" inputmode="numeric" autocomplete="off">'
   +'<button id="labOpenBtn" type="button">Открыть</button>'
   +'<button id="labRun" type="button">Тесты</button>'
   +'<button id="labCopy" type="button">Копировать отчёт</button><span id="labCopyDone" style="display:none">скопировано</span>'
   +'</div>'
   +'<div id="labStage"></div>'
   +'<pre id="labRep" hidden></pre>'
   +'<pre id="labLog"></pre>';
  document.body.appendChild(root);
  LJ('init','лаборатория поднята · страница v52 · стенд 2 (нативный поток)');
  LJ('init','мост: '+labBridge());
  var qid='';
  try{ qid=new URLSearchParams(location.search).get('id')||new URLSearchParams(location.search).get('v')||'' }catch(e){}
  if(qid)document.getElementById('labId').value=qid;
  document.getElementById('labOpenBtn').addEventListener('click',labOpenBtn);
  document.getElementById('labRun').addEventListener('click',labRunAll);
  document.getElementById('labCopy').addEventListener('click',labCopy);
  document.getElementById('labId').addEventListener('keydown',function(e){ if(e.key==='Enter')labOpenBtn(); });
  labLoadList();
}
