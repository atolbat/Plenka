#!/usr/bin/env node
/* Смоук v57/3.11 — «видео в фоне не встаёт» + «реестр убранных крестиком»:
   1) бут без ошибок, карточки, мост 3.11;
   2) MSE-мост играет; setPipAuto НИ РАЗУ не true;
   3) фон: mediaState(playing=true) ушёл, время идёт, качалка качает;
   4) ГЛАВНОЕ: системная пауза в фоне (сырой video.pause(), не от юзера) —
      сторож ВОЗОБНОВЛЯЕТ воспроизведение;
   5) юзерская пауза в фоне (__plenkaMedia — кнопка шторки) — уважается;
   6) сердце фона: mediaState продолжает лететь в фоне;
   7) seek из шторки в фоне садится; возврат — mediaState ушёл;
   8) S.pauseOnHidden=true в NATV: сворачивание НЕ паузит (гейт);
   9) РЕЕСТР: крестик убирает видео → перезагрузка страницы (перезаход) —
      видео НЕ вернулось; настройки → «вернуть скрытые» → вернуть по одному;
      убрать два → «вернуть все» — оба на месте;
   10) аудио в фоне; 11) ДИАГ v57/3.11. */
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

(async()=>{
  const mock=spawn('python3',['/home/z/my-project/scripts/mock57.py'],{stdio:['ignore','pipe','pipe']});
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
    A(errs.length===0,'страница v57 поднялась без JS-ошибок',errs.length?errs[0]:'');
    A(await p.evaluate(()=>document.querySelectorAll('.lib-row').length)>=3,'карточки отрисованы');
    const verOk=await p.evaluate(function(){
      try{ return (window.PlenkaNative.version().indexOf('3.11')>=0); }catch(e){ return false }
    });
    A(verOk,'мост представился 3.11');

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

    /* 3. фон: push наружу + время идёт */
    const msBefore=JSON.parse(await p.evaluate(()=>window.__mockMediaCalls())).length;
    const bgRes=await p.evaluate(()=>window.__mockBgSet(true));
    await sleep(400);
    const msAfterBg=JSON.parse(await p.evaluate(()=>window.__mockMediaCalls()));
    A((''+bgRes).indexOf('ok:true')===0,'__mockBgSet(true) подменил hidden',bgRes);
    A(msAfterBg.length>msBefore&&msAfterBg[msAfterBg.length-1].playing===true,
      'фонд-переход: mediaState(playing=true) ушёл в оболочку');
    const bgSnap=await p.evaluate(async function(){
      var V=window.video;
      var t0=V.currentTime, bufEnd0=0;
      try{ bufEnd0=V.buffered.end(V.buffered.length-1) }catch(e){}
      await new Promise(r=>setTimeout(r,5000));
      var bufEnd1=0;
      try{ bufEnd1=V.buffered.end(V.buffered.length-1) }catch(e){}
      return {dt:V.currentTime-t0, bufGrow:bufEnd1-bufEnd0, bufEnd:bufEnd1, playing:!V.paused};
    });
    A(bgSnap.dt>=2.5,'в фоне время ИДЁТ (dt='+bgSnap.dt.toFixed(1)+'с)');
    A(bgSnap.playing===true,'в фоне НЕ пауза');
    A(bgSnap.bufGrow>1||bgSnap.bufEnd>bgSnap.dt+8,'в фоне качалка качает');

    /* 4. ГЛАВНОЕ: системная пауза в фоне → сторож возобновляет */
    const sysPause=await p.evaluate(async function(){
      var V=window.video;
      V.pause();                        /* сырая пауза «от Chromium/системы», НЕ через обёртку pause() */
      var pausedAt=V.paused;
      await new Promise(r=>setTimeout(r,3000));
      return {pausedAt:pausedAt, pausedAfter3s:V.paused, t:V.currentTime, hidden:document.hidden};
    });
    A(sysPause.pausedAt===true,'системная пауза в фоне: элемент встал (факт)');
    A(sysPause.pausedAfter3s===false,'СТОРОЖ: системная пауза в фоне отменена — видео играет',
      't='+sysPause.t.toFixed(1));
    const resumed=await p.evaluate(async function(){
      var V=window.video, t0=V.currentTime;
      await new Promise(r=>setTimeout(r,2500));
      return {dt:V.currentTime-t0, paused:V.paused};
    });
    A(!resumed.paused&&resumed.dt>=1.5,'после возобновления время продолжает идти (dt='+resumed.dt.toFixed(1)+'с)');

    /* 5. юзерская пауза в фоне — уважается */
    const usrPause=await p.evaluate(async function(){
      window.__plenkaMedia('pause');    /* кнопка шторки — юзерское намерение */
      await new Promise(r=>setTimeout(r,4000));
      var r1={stays:window.video.paused, ms:JSON.parse(window.__mockMediaState())};
      window.__plenkaMedia('play');
      await new Promise(r=>setTimeout(r,800));
      r2: {}
      return r1;
    });
    A(usrPause.stays===true,'юзерская пауза (шторка) в фоне: НЕ отменяется сторожем');
    A(usrPause.ms&&usrPause.ms.playing===false,'пауза юзера: mediaState(false) ушёл');
    const playingAgain=await p.evaluate(()=>!window.video.paused&&window.video.currentTime>0);
    A(playingAgain,'шторка «Играть»: снова играем');

    /* 6. сердце фона: mediaState продолжает лететь */
    const hb0=JSON.parse(await p.evaluate(()=>window.__mockMediaCalls())).length;
    await sleep(12500);
    const hb1=JSON.parse(await p.evaluate(()=>window.__mockMediaCalls())).length;
    A(hb1>hb0,'сердце фона: позиция летит в шторку без экрана (+'+(hb1-hb0)+' push)',
      JSON.stringify(JSON.parse(await p.evaluate(()=>window.__mockMediaState()))));

    /* 7. seek из шторки + возврат */
    const cmdRes=await p.evaluate(async function(){
      var V=window.video;
      window.__plenkaMedia('seek:40');
      var t0=Date.now();
      while(V.seeking&&Date.now()-t0<9000)await new Promise(r=>setTimeout(r,120));
      await new Promise(r=>setTimeout(r,600));
      return {seekLanded:Math.round(V.currentTime), playing:!V.paused};
    });
    A(cmdRes.seekLanded>=38&&cmdRes.seekLanded<=42,'шторка «перемотка»: seek:40 сел ('+cmdRes.seekLanded+')');
    A(cmdRes.playing===true,'после сика в фоне — играем');
    const msLenBack=JSON.parse(await p.evaluate(()=>window.__mockMediaCalls())).length;
    await p.evaluate(()=>window.__mockBgSet(false));
    await sleep(400);
    const msBack=JSON.parse(await p.evaluate(()=>window.__mockMediaCalls()));
    A(msBack.length>msLenBack,'возврат на экран: mediaState ушёл (натив гасит сервис)');

    /* 8. pauseOnHidden=true + NATV: сворачивание не паузит */
    await p.evaluate(function(){ window.S.pauseOnHidden=true; window.saveS(); });
    await p.reload({waitUntil:'domcontentloaded'});
    await p.waitForFunction(()=>window.items&&window.items.length>=3,null,{timeout:15000});
    await sleep(1200);
    const poh=await p.evaluate(async function(){
      var i=window.items.findIndex(function(it){return it.name==='fmp460.mp4'});
      window.openItem(i,{});
      return true;
    });
    try{
      await p.waitForFunction(()=>window.video&&!window.video.paused&&window.video.currentTime>0.5,null,{timeout:20000});
      await p.evaluate(()=>window.__mockBgSet(true));
      await sleep(2500);
      const st=await p.evaluate(()=>({paused:window.video.paused,hidden:document.hidden,dt:window.video.currentTime}));
      A(!st.paused,'NATV: S.pauseOnHidden=true НЕ паузит при сворачивании (гейт 57)','t='+st.dt.toFixed(1));
      const rowHidden=await p.evaluate(function(){
        var b=document.querySelector('[data-sw="pauseOnHidden"]');
        return !!(b&&b.closest('.row')&&b.closest('.row').hidden);
      });
      A(rowHidden,'NATV: переключатель «пауза при сворачивании» скрыт из настроек');
    }catch(e){ A(false,'pauseOnHidden-тест: видео не поднялось',e.message); }
    await p.evaluate(function(){ window.S.pauseOnHidden=false; window.saveS(); });
    await p.evaluate(()=>window.__mockBgSet(false));
    /* закрыть плеер — вернуться в библиотеку */
    await p.evaluate(function(){ try{ document.getElementById('btnBack').click(); }catch(e){} });
    await sleep(700);

    /* 9. РЕЕСТР: крестик → перезаход → не вернулось → вернуть */
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
    const regSaved=await p.evaluate(function(){
      return new Promise(function(res){
        setTimeout(function(){
          try{ window.idbGet('kv','rmreg').then(function(v){ res(JSON.stringify(v)) }) }
          catch(e){ res('ERR:'+e.message) }
        },900);
      });
    });
    A((''+regSaved).indexOf('long30')>=0,'реестр: запись в IDB kv rmreg есть',(''+regSaved).slice(0,90));
    /* перезаход */
    await p.reload({waitUntil:'domcontentloaded'});
    await p.waitForFunction(()=>window.items&&window.items.length>=2,null,{timeout:15000});
    await sleep(1500);
    const afterReload=await p.evaluate(function(){
      return {n:window.items.length, hasLong:window.items.some(function(it){return it.name==='long30.mp4'})};
    });
    A(afterReload.n===n0-1&&!afterReload.hasLong,'ПЕРЕЗАХОД: видео не вернулось ('+afterReload.n+' из '+n0+') — реестр работает');
    /* вернуть через настройки */
    const restored=await p.evaluate(async function(){
      document.getElementById('btnLibSettings').click();
      var btn=document.getElementById('btnRmShow');
      var label=btn.textContent;
      btn.click();
      var sheet=document.getElementById('rmSheet');
      var open=sheet.classList.contains('open');
      var rows=sheet.querySelectorAll('[data-rmid]');
      if(rows.length)rows[0].click();
      await new Promise(r=>setTimeout(r,1200));
      return {label:label, open:open, rows:rows.length,
              closed:!sheet.classList.contains('open'),
              n:window.items.length, hasLong:window.items.some(function(it){return it.name==='long30.mp4'})};
    });
    A(restored.open&&restored.rows===1,'настройки → «вернуть скрытые»: шит открылся, в списке 1 видео (кнопка: «'+restored.label+'»)');
    A(restored.hasLong&&restored.n===n0,'«вернуть»: long30 снова в библиотеке ('+restored.n+')');
    /* убрать два → вернуть все */
    const rm2=await p.evaluate(async function(){
      ['fmp460','song'].forEach(function(nm){
        var rows=Array.prototype.slice.call(document.querySelectorAll('.lib-row'));
        var row=rows.find(function(r){ return (r.querySelector('.lib-name')||{}).textContent===nm });
        if(row)row.querySelector('.rm').click();
      });
      await new Promise(r=>setTimeout(r,600));
      var n1=window.items.length;
      document.getElementById('btnLibSettings').click();
      document.getElementById('btnRmShow').click();
      var all=document.getElementById('rmAllBtn');
      var has=!!all;
      if(all)all.click();
      await new Promise(r=>setTimeout(r,1400));
      return {n1:n1, hasAllBtn:has, n2:window.items.length,
              names:window.items.map(function(it){return it.name}).sort().join(',')};
    });
    A(rm2.n1===n0-2,'убрано ещё два → осталось '+rm2.n1);
    A(rm2.hasAllBtn,'шит: кнопка «вернуть все (2)» есть');
    A(rm2.n2===n0&&rm2.names.indexOf('long30')>=0&&rm2.names.indexOf('fmp460')>=0,
      '«вернуть все»: библиотека снова полная ('+rm2.names+')');

    /* 10. аудио в фоне (регресс) */
    await p.evaluate(function(){
      var i=window.items.findIndex(function(it){return it.name==='song.mp3'});
      window.openItem(i,{});
    });
    try{
      await p.waitForFunction(()=>window.video&&window.video.src&&!window.video.paused&&window.video.currentTime>0.5,null,{timeout:20000});
      await p.evaluate(()=>window.__mockBgSet(true));
      const aBg=await p.evaluate(async function(){
        var V=window.video,t0=V.currentTime;
        await new Promise(r=>setTimeout(r,4000));
        return {dt:V.currentTime-t0,paused:V.paused};
      });
      A(aBg.dt>=2&&!aBg.paused,'аудио в фоне играет (dt='+aBg.dt.toFixed(1)+'с)');
    }catch(e){ A(false,'аудио: не поднялось',e.message); }
    await p.evaluate(()=>window.__mockBgSet(false));

    /* 11. ДИАГ */
    const diag=await p.evaluate(function(){
      try{
        var btn=document.getElementById('plenkaDiagBtn');
        if(btn)btn.click();
        return (document.getElementById('plenkaDiag')||{}).textContent||'';
      }catch(e){ return '' }
    });
    A(diag.indexOf('v57')>=0||diag.indexOf('3.11')>=0,'ДИАГ: версия v57/3.11');

    await b.close();
  }catch(e){
    console.log('[FAIL] fatal: '+e.message);
    fails++;
  }finally{
    mock.kill('SIGKILL');
  }
  console.log(fails===0?'\nИТОГ: все проверки зелёные':'\nИТОГ: провалов — '+fails);
  process.exit(fails===0?0:1);
})();
