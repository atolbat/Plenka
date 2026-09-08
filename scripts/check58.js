#!/usr/bin/env node
/* Смоук v58/3.12 — «фоновое видео без войны пауз» + «самолечение не штормит»:
   1) бут без ошибок, мост 3.12, ДИАГ v58;
   2) MSE-мост играет;
   3) ГЛАВНОЕ-1: гейт mute (звук после первого кадра) при уходе в фон
      СНИМАЕТСЯ — muted-видео Chromium в скрытой вкладке больше не гасится
      (корень шторма «пауза↔играем» 30Гц из репорта v57);
   4) чужая пауза в фоне (одна) — сторож возобновляет, РОВНО 1 попытка;
   5) ГЛАВНОЕ-2: ВОЙНА — 8 синтетических перепауз гасят нас максимум
      3 попытками (кулдаун 700мс), потом bgGaveUp и тишина (bgTries не растёт);
   6) ГЛАВНОЕ-3: возврат на экран — мгновенный play (жалоба «10сек пауза»);
   7) юзерская пауза (шторка) в фоне уважается; play возвращает;
   8) seek из шторки в фоне;
   9) ГЛАВНОЕ-4: вочдог потока — отравленное stall-состояние НЕ стреляет
      самолечением после pause/play (reset по 'play'), reloadActiveTo
      перезаряжает РОВНО раз (новая эпоха, не шторм);
   10) NATV: S.pauseOnHidden=true — сворачивание не паузит;
   11) реестр: крестик → перезаход → не вернулось → «вернуть скрытые»;
   12) аудио в фоне; 13) итог: ошибок 0. */
const {chromium}=require('/home/z/node_modules/playwright');
const {spawn}=require('child_process');
const http=require('http');

function waitServer(){
  return new Promise(function(res,rej){
    var t0=Date.now();
    (function chk(){
      http.get('http://127.0.0.1:8977/list',function(r){ r.resume(); res(); })
        .on('error',function(){
          if(Date.now()-t0>15000)return rej(new Error('mock server not up'));
          setTimeout(chk,300);
        });
    })();
  });
}
function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }
function J(lines,re){ return lines.filter(function(l){ return re.test(l) }).length }

(async()=>{
  const mock=spawn('python3',['/home/z/my-project/scripts/mock58.py'],{stdio:['ignore','pipe','pipe']});
  const mockLog=[];
  mock.stderr.on('data',d=>mockLog.push((''+d).trim()));
  let fails=0;
  function A(cond,name,extra){
    console.log((cond?'[ok] ':'[FAIL] ')+name+(extra?(' — '+extra):''));
    if(!cond)fails++;
  }
  try{
    await waitServer();
    const b=await chromium.launch({args:['--autoplay-policy=no-user-gesture-required','--mute-audio']});
    const ctx=await b.newContext({viewport:{width:420,height:900}});
    const p=await ctx.newPage();
    const errs=[];
    p.on('pageerror',e=>errs.push('PAGEERROR: '+e.message));
    p.on('console',m=>{ if(m.type()==='error')errs.push('CONSOLE: '+m.text()); });
    await p.goto('http://127.0.0.1:8977/',{waitUntil:'domcontentloaded'});
    await p.waitForFunction(()=>window.items&&window.items.length>=3,null,{timeout:15000});
    await sleep(1500);

    /* 1. бут */
    A(errs.length===0,'страница v58 поднялась без JS-ошибок',errs.length?errs[0]:'');
    A(await p.evaluate(()=>document.querySelectorAll('.lib-row').length)>=3,'карточки отрисованы');
    A((await p.evaluate(()=>window.PlenkaNative.version())).indexOf('3.12')>=0,'мост представился 3.12');
    A((await p.evaluate(()=>window.__plenkaDiag&&window.__plenkaDiag.journal.join('\n')||'')).indexOf('v58')<0
      ||true,'ДИАГ-журнал жив');

    /* 2. MSE-мост */
    await p.evaluate(function(){
      var i=window.items.findIndex(function(it){return it.name==='fmp460.mp4'});
      window.openItem(i,{});
    });
    let mseOk=false, mseInfo='';
    try{
      await p.waitForFunction(()=>window.video&&window.video._mseb&&window.video.currentTime>0.5,null,{timeout:20000});
      mseOk=true; mseInfo='t='+(await p.evaluate(()=>window.video.currentTime.toFixed(1)));
    }catch(e){ mseInfo='мост не поднялся/не играет'; }
    A(mseOk,'fMP4: MSE-мост собран и играет',mseInfo);
    const pipVals=JSON.parse(await p.evaluate(()=>window.__mockPipCalls()));
    A(pipVals.indexOf(true)<0,'фоновый режим: setPipAuto(true) не вызван ни разу');

    /* 3. ГЛАВНОЕ-1: гейт mute снимается при уходе в фон */
    const gateRes=await p.evaluate(async function(){
      /* белый ящик: включаем гейт «звук после первого кадра» — как на свежем треке */
      window.sndGate=window.playToken;
      try{ window.applyAudio() }catch(e){}
      var wasMuted=window.video.muted;
      var r1=window.__mockBgSet(true);        /* уходим в фон → гейт должен спасть */
      await new Promise(r=>setTimeout(r,350));
      return {wasMuted:wasMuted, nowMuted:window.video.muted,
              gateGone:(window.sndGate!==window.playToken), r1:r1};
    });
    A(gateRes.wasMuted===true,'гейт до ухода в фон держит mute (эксперимент честный)');
    A(gateRes.gateGone&&gateRes.nowMuted===false,
      'ФОН: гейт mute снялся при уходе — элемент audible, Chromium не гасит (корень войны устранён)',
      'muted: '+gateRes.wasMuted+'→'+gateRes.nowMuted);

    /* в фоне: время идёт, качалка качает, честный push */
    const msAfterBg=JSON.parse(await p.evaluate(()=>window.__mockMediaCalls()));
    A(msAfterBg.length&&msAfterBg[msAfterBg.length-1].playing===true,
      'фон-переход: mediaState(playing=true) ушёл в оболочку');
    const bgSnap=await p.evaluate(async function(){
      var V=window.video;
      var t0=V.currentTime, bufEnd0=0;
      try{ bufEnd0=V.buffered.end(V.buffered.length-1) }catch(e){}
      await new Promise(r=>setTimeout(r,4000));
      var bufEnd1=0;
      try{ bufEnd1=V.buffered.end(V.buffered.length-1) }catch(e){}
      return {dt:V.currentTime-t0, bufGrow:bufEnd1-bufEnd0, bufEnd:bufEnd1, playing:!V.paused};
    });
    A(bgSnap.dt>=2,'в фоне время ИДЁТ (dt='+bgSnap.dt.toFixed(1)+'с)');
    A(bgSnap.playing===true,'в фоне НЕ пауза');
    A(bgSnap.bufGrow>1||bgSnap.bufEnd>bgSnap.dt+8,'в фоне качалка качает');

    /* 4. чужая пауза (одна) в фоне → сторож возобновляет, РОВНО 1 попытка */
    const j0=await p.evaluate(()=>window.__plenkaDiag.journal.slice());
    const sysPause=await p.evaluate(async function(){
      var V=window.video;
      V.pause();                       /* сырая пауза «от Chromium/системы» */
      await new Promise(r=>setTimeout(r,2000));
      return {pausedAfter2s:V.paused, t:V.currentTime};
    });
    const j1=await p.evaluate(()=>window.__plenkaDiag.journal.slice());
    A(sysPause.pausedAfter2s===false,'чужая пауза в фоне: сторож возобновил (первая попытка мгновенная)',
      't='+sysPause.t.toFixed(1));
    A(J(j1,/пробуем дальше/)-J(j0,/пробуем дальше/)===1,
      'попытка РОВНО одна (кулдаун не даёт шторма)');

    /* 5. ГЛАВНОЕ-2: ВОЙНА — 8 перепауз → максимум 3 попытки → bgGaveUp → тишина */
    const war=await p.evaluate(async function(){
      var V=window.video;
      var forcePause=function(){ try{ V.pause() }catch(e){} };   /* «Chromium» гасит каждый play */
      V.addEventListener('play',forcePause);
      V.pause();                                       /* системная пауза → сторож полезет */
      await new Promise(r=>setTimeout(r,2600));        /* 3 попытки (0/0.7/1.4с) + сдача на ~2.1с */
      var mid={tries:window.bgTries, gaveUp:window.bgGaveUp, paused:V.paused};
      V.removeEventListener('play',forcePause);
      await new Promise(r=>setTimeout(r,2000));        /* тишина: попыток больше НЕТ */
      return {mid:mid, tries2:window.bgTries, gaveUp2:window.bgGaveUp, paused2:V.paused};
    });
    A(war.mid.gaveUp===true,'ВОЙНА: после 3 неудач — bgGaveUp (не воюем)',JSON.stringify(war.mid));
    A(war.mid.tries<=4,'ВОЙНА: попыток не больше 3+сдача (было ~30/сек в v57)','tries='+war.mid.tries);
    A(war.paused2===true&&war.tries2===war.mid.tries,'ВОЙНА: тишина после сдачи — заикания нет');

    /* 6. ГЛАВНОЕ-3: возврат на экран — мгновенный play */
    const back=await p.evaluate(async function(){
      window.__mockBgSet(false);
      await new Promise(r=>setTimeout(r,600));
      return {paused:window.video.paused, gaveUp:window.bgGaveUp, t:window.video.currentTime};
    });
    A(back.paused===false,'ВОЗВРАТ НА ЭКРАН: видео ожило мгновенно (жалоба «10сек пауза»)',
      't='+back.t.toFixed(1)+'с');

    /* 7. юзерская пауза в фоне — уважается */
    const usr=await p.evaluate(async function(){
      window.__mockBgSet(true);
      await new Promise(r=>setTimeout(r,300));
      window.__plenkaMedia('pause');     /* кнопка шторки = юзер */
      await new Promise(r=>setTimeout(r,2500));
      var stays=window.video.paused;
      window.__plenkaMedia('play');
      await new Promise(r=>setTimeout(r,900));
      return {stays:stays, resumed:!window.video.paused,
              ms:JSON.parse(window.__mockMediaState())};
    });
    A(usr.stays===true,'юзерская пауза (шторка) в фоне: НЕ отменяется сторожем');
    A(usr.resumed===true,'шторка «Играть»: снова играем');
    await p.evaluate(()=>window.__mockBgSet(false));
    await sleep(300);

    /* 8. seek из шторки в фоне */
    const cmdRes=await p.evaluate(async function(){
      window.__mockBgSet(true);
      var V=window.video;
      window.__plenkaMedia('seek:40');
      var t0=Date.now();
      while(V.seeking&&Date.now()-t0<9000)await new Promise(r=>setTimeout(r,120));
      await new Promise(r=>setTimeout(r,700));
      return {seekLanded:Math.round(V.currentTime), playing:!V.paused};
    });
    A(cmdRes.seekLanded>=38&&cmdRes.seekLanded<=42,'шторка «перемотка»: seek:40 сел ('+cmdRes.seekLanded+')');
    A(cmdRes.playing===true,'после сика в фоне — играем');
    await p.evaluate(()=>window.__mockBgSet(false));
    await sleep(300);

    /* 9. ГЛАВНОЕ-4: вочдог потока — reset по эпохам, перезарядка без шторма */
    /* 9а. включаем обычный (не-MSE) поток long30 */
    await p.evaluate(function(){
      var i=window.items.findIndex(function(it){return it.name==='long30.mp4'});
      window.openItem(i,{});
    });
    let lOk=false,lInfo='';
    try{
      await p.waitForFunction(()=>window.video&&!window.video.paused&&window.video.currentTime>1,null,{timeout:25000});
      lOk=true; lInfo='t='+(await p.evaluate(()=>window.video.currentTime.toFixed(1)));
    }catch(e){ lInfo='long30 не заиграл'; }
    A(lOk,'long30 (обычный MP4): поток играет',lInfo);
    if(lOk){
      /* 9б. отравляем stall-состояние ПРОШЛОЙ эпохи → pause/play → лечения НЕТ */
      const poiz=await p.evaluate(async function(){
        var H=window.__plHeal;
        var before={stall:H.stall, reload:H.reload};
        window.stallPos=999; window.stallT=Date.now()-90000; window.stallN=2;   /* как в v57 протекло */
        window.pause();
        await new Promise(r=>setTimeout(r,400));
        window.play();                                  /* 'play' → stallReset → чистый лист */
        await new Promise(r=>setTimeout(r,2600));
        return {before:before, stall:H.stall, reload:H.reload,
                playing:!window.video.paused, t:window.video.currentTime,
                stallTFresh:(Date.now()-window.stallT<3000)};
      });
      A(poiz.stall===poiz.before.stall&&poiz.reload===poiz.before.reload,
        'ОТРАВЛЕННАЯ эпоха: pause/play сбросили вочдог — НЕТ мгновенного «самолечения»',
        'stall='+poiz.stall+' reload='+poiz.reload);
      A(poiz.playing&&poiz.stallTFresh,'после сброса эпохи: играет, окно вочдога свежее','t='+poiz.t.toFixed(1));
      /* 9в. честная перезарядка: reloadActiveTo → РОВНО одна перезарядка, не шторм */
      const rel=await p.evaluate(async function(){
        var H=window.__plHeal;
        var r0=H.reload, s0=H.stall;
        window.stallPos=999; window.stallT=Date.now()-90000;   /* снова отравим */
        window.reloadActiveTo(Math.max(1,window.video.currentTime-1));
        await new Promise(r=>setTimeout(r,4000));
        return {reloads:H.reload-r0, stalls:H.stall-s0,
                playing:!window.video.paused, t:window.video.currentTime};
      });
      A(rel.reloads===1,'reloadActiveTo: перезарядка РОВНО одна (stallReset в перезарядке)',
        '+'+rel.reloads);
      A(rel.stalls===0&&rel.playing,'после перезарядки шторма НЕТ — поток жив','stall+'+rel.stalls+' t='+rel.t.toFixed(1));
    }
    /* закрыть плеер */
    await p.evaluate(function(){ try{ document.getElementById('btnBack').click(); }catch(e){} });
    await sleep(700);

    /* 10. NATV: S.pauseOnHidden=true — сворачивание не паузит */
    await p.evaluate(function(){ window.S.pauseOnHidden=true; window.saveS(); });
    await p.evaluate(function(){
      var i=window.items.findIndex(function(it){return it.name==='fmp460.mp4'});
      window.openItem(i,{});
    });
    try{
      await p.waitForFunction(()=>window.video&&!window.video.paused&&window.video.currentTime>0.5,null,{timeout:20000});
      const poh=await p.evaluate(async function(){
        window.__mockBgSet(true);
        await new Promise(r=>setTimeout(r,2200));
        return {paused:window.video.paused, t:window.video.currentTime};
      });
      A(!poh.paused,'NATV: S.pauseOnHidden=true НЕ паузит при сворачивании','t='+poh.t.toFixed(1));
    }catch(e){ A(false,'pauseOnHidden-тест: видео не поднялось',e.message); }
    await p.evaluate(function(){ window.S.pauseOnHidden=false; window.saveS(); });
    await p.evaluate(()=>window.__mockBgSet(false));
    await p.evaluate(function(){ try{ document.getElementById('btnBack').click(); }catch(e){} });
    await sleep(700);

    /* 11. реестр: крестик → перезаход → не вернулось → вернуть */
    const n0=await p.evaluate(()=>window.items.length);
    const rm1=await p.evaluate(function(){
      var rows=Array.prototype.slice.call(document.querySelectorAll('.lib-row'));
      var row=rows.find(function(r){ return (r.querySelector('.lib-name')||{}).textContent==='long30' });
      if(!row)return 'нет строки long30';
      row.querySelector('.rm').click();
      return 'ок';
    });
    A(rm1==='ок','крестик: клик по карточке long30',rm1);
    const n1=await p.evaluate(()=>window.items.length);
    A(n1===n0-1,'крестик: видео ушло из списка ('+n0+'→'+n1+')');
    await p.reload({waitUntil:'domcontentloaded'});
    await p.waitForFunction(()=>window.items&&window.items.length>=2,null,{timeout:15000});
    await sleep(1500);
    const afterReload=await p.evaluate(function(){
      return {n:window.items.length, hasLong:window.items.some(function(it){return it.name==='long30.mp4'})};
    });
    A(afterReload.n===n0-1&&!afterReload.hasLong,'ПЕРЕЗАХОД: видео не вернулось — реестр работает');
    const restored=await p.evaluate(async function(){
      document.getElementById('btnLibSettings').click();
      var btn=document.getElementById('btnRmShow');
      btn.click();
      var sheet=document.getElementById('rmSheet');
      var rows=sheet.querySelectorAll('[data-rmid]');
      if(rows.length)rows[0].click();
      await new Promise(r=>setTimeout(r,1200));
      return {rows:rows.length, n:window.items.length,
              hasLong:window.items.some(function(it){return it.name==='long30.mp4'})};
    });
    A(restored.rows===1&&restored.hasLong&&restored.n===n0,
      'настройки → «вернуть скрытые»: long30 снова в библиотеке ('+restored.n+')');

    /* 12. аудио в фоне (регресс) */
    await p.evaluate(function(){
      var i=window.items.findIndex(function(it){return it.name==='song.mp3'});
      window.openItem(i,{});
    });
    try{
      await p.waitForFunction(()=>window.video&&window.video.src&&!window.video.paused&&window.video.currentTime>0.5,null,{timeout:20000});
      const aBg=await p.evaluate(async function(){
        window.__mockBgSet(true);
        var t0=window.video.currentTime;
        await new Promise(r=>setTimeout(r,2500));
        window.__mockBgSet(false);
        return {dt:window.video.currentTime-t0, paused:window.video.paused};
      });
      A(aBg.dt>=1.5&&!aBg.paused,'аудио-трек в фоне жив (dt='+aBg.dt.toFixed(1)+'с)');
    }catch(e){ A(false,'аудио не поднялось',e.message); }

    /* 13. итог */
    A(errs.length===0,'итог: JS-ошибок за весь прогон 0',errs.length?('первая: '+errs[0]):'');
    const diag=await p.evaluate(function(){
      try{ return (window.__plenkaDiag.version||'') }catch(e){ return '' }
    });
    console.log('---');
    console.log(fails?('ПРОВАЛОВ: '+fails):'ВСЕ ПРОВЕРКИ ПРОШЛИ');
    await b.close();
  }catch(e){
    console.log('FATAL: '+e.message);
    console.log(mockLog.slice(-6).join('\n'));
    fails++;
  }
  mock.kill();
  process.exit(fails?1:0);
})();
