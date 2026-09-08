#!/usr/bin/env node
/* Смоук v56/3.10 — ФОН БЕЗ PiP:
   1) бут без ошибок, карточки, версия v56/3.10;
   2) фоновый режим по умолчанию: setPipAuto НИ РАЗУ не true (старое поведение = PiP);
   3) MSE-мост играет; 4) ушли в «фон» (__mockBgSet) — mediaState с playing:true
      улетает в оболочку (натив поднимет сервис);
   5) В ФОНЕ: время идёт, качалка качает (буфер растёт), мост жив, сторож rVFC
      НЕ колотит реанимациями (гейт document.hidden);
   6) в фоне работают кнопки «шторки»: __plenkaMedia pause/play/seek;
   7) возврат из фона — mediaState летит снова (натив гасит сервис);
   8) аудио в фоне тоже играет; 9) msebSleep в фоне — быстрое разрешение;
   10) ДИАГ: v56/3.10. */
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
  const mock=spawn('python3',['/home/z/my-project/scripts/mock56.py'],{stdio:['ignore','pipe','pipe']});
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
    const p=await b.newPage({viewport:{width:420,height:900}});
    const errs=[];
    p.on('pageerror',e=>errs.push('PAGEERROR: '+e.message));
    p.on('console',m=>{ if(m.type()==='error')errs.push('CONSOLE: '+m.text()); });
    await p.goto('http://127.0.0.1:8977/',{waitUntil:'domcontentloaded'});
    await p.waitForFunction(()=>window.items&&window.items.length>=3,null,{timeout:15000});
    await sleep(1500);

    /* 1. бут */
    A(errs.length===0,'страница v56 поднялась без JS-ошибок',errs.length?errs[0]:'');
    A(await p.evaluate(()=>document.querySelectorAll('.lib-row').length)>=3,'карточки отрисованы');
    const verOk=await p.evaluate(function(){
      try{ return (window.PlenkaNative.version().indexOf('3.10')>=0); }catch(e){ return false }
    });
    A(verOk,'мост представился 3.10');

    /* 2. открываем fMP4 (MSE-мост), играем */
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

    /* 3. фон по умолчанию: setPipAuto НИ РАЗУ true */
    const pipVals=JSON.parse(await p.evaluate(()=>window.__mockPipCalls()));
    A(pipVals.indexOf(true)<0,'фоновый режим: setPipAuto(true) не вызван ни разу ('+JSON.stringify(pipVals)+')');

    /* 4. уход в «фон» — state наружу */
    const msBefore=JSON.parse(await p.evaluate(()=>window.__mockMediaCalls())).length;
    const bgRes=await p.evaluate(()=>window.__mockBgSet(true));
    await sleep(400);
    const msAfterBg=JSON.parse(await p.evaluate(()=>window.__mockMediaCalls()));
    A((''+bgRes).indexOf('ok:true')===0,'__mockBgSet(true) подменил hidden',bgRes);
    A(msAfterBg.length>msBefore&&msAfterBg[msAfterBg.length-1].playing===true,
      'фонд-переход: mediaState(playing=true) ушёл в оболочку',
      JSON.stringify(msAfterBg[msAfterBg.length-1]));

    /* 5. в фоне: время идёт, буфер растёт, мост жив, вочдог молчит */
    const bgSnap=await p.evaluate(async function(){
      var V=window.video, b0=V._mseb;
      var t0=V.currentTime, bufEnd0=0;
      try{ bufEnd0=V.buffered.end(V.buffered.length-1) }catch(e){}
      await new Promise(r=>setTimeout(r,6000));
      var bufEnd1=0;
      try{ bufEnd1=V.buffered.end(V.buffered.length-1) }catch(e){}
      return {dt:V.currentTime-t0, bufGrow:bufEnd1-bufEnd0, bufEnd:bufEnd1,
              playing:!V.paused, sameBridge:(V._mseb===b0),
              recoveries:(b0&&b0.recoveries)||0, hidden:document.hidden};
    });
    A(bgSnap.hidden===true,'document.hidden держится', '');
    A(bgSnap.dt>=3,'в фоне время ИДЁТ (dt='+bgSnap.dt.toFixed(1)+'с)');
    A(bgSnap.playing===true,'в фоне НЕ пауза');
    A(bgSnap.bufGrow>1.5||bgSnap.bufEnd>bgSnap.dt+10,'в фоне качалка качает (буфер +'+bgSnap.bufGrow.toFixed(1)+'с, конец '+bgSnap.bufEnd.toFixed(1)+'с)');
    A(bgSnap.sameBridge&&bgSnap.recoveries===0,'вочдог rVFC НЕ реанимирует (гейт hidden)','recoveries='+bgSnap.recoveries);

    /* 6. кнопки «шторки» в фоне: pause → play → seek */
    const cmdRes=await p.evaluate(async function(){
      var V=window.video, out={};
      window.__plenkaMedia('pause');
      await new Promise(r=>setTimeout(r,500));
      out.pausedAfterPause=V.paused;
      out.msLast=JSON.parse(window.__mockMediaState());
      window.__plenkaMedia('play');
      await new Promise(r=>setTimeout(r,800));
      out.playingAfterPlay=!V.paused&&V.currentTime>0;
      window.__plenkaMedia('seek:40');
      var t0=Date.now();
      while(V.seeking&&Date.now()-t0<9000)await new Promise(r=>setTimeout(r,120));
      await new Promise(r=>setTimeout(r,600));
      out.seekLanded=Math.round(V.currentTime);
      out.msAfterSeek=JSON.parse(window.__mockMediaState());
      return out;
    });
    A(cmdRes.pausedAfterPause===true,'шторка «Пауза» в фоне: плеер встал');
    A(cmdRes.msLast&&cmdRes.msLast.playing===false,'пауза в фоне: mediaState(false) ушёл (нотиф. сменит кнопку)');
    A(cmdRes.playingAfterPlay===true,'шторка «Играть» в фоне: плеер пошёл');
    A(cmdRes.seekLanded>=38&&cmdRes.seekLanded<=42,'шторка «перемотка»: seek:40 сел ('+cmdRes.seekLanded+')');
    A(cmdRes.msAfterSeek&&cmdRes.msAfterSeek.playing===true,'после сика: mediaState(true) жив');

    /* 7. возврат из фона — state наружу снова */
    const msLenBeforeBack=JSON.parse(await p.evaluate(()=>window.__mockMediaCalls())).length;
    await p.evaluate(()=>window.__mockBgSet(false));
    await sleep(400);
    const msAfterBack=JSON.parse(await p.evaluate(()=>window.__mockMediaCalls()));
    A(msAfterBack.length>msLenBeforeBack,'возврат на экран: mediaState ушёл (натив гасит сервис)',
      JSON.stringify(msAfterBack[msAfterBack.length-1]));

    /* 8. msebSleep в фоне: разрешается быстро (MessageChannel не троттлится) */
    await p.evaluate(()=>window.__mockBgSet(true));
    const sl=await p.evaluate(async function(){
      var t0=performance.now();
      await window.msebSleep(250);
      return {ms:performance.now()-t0, hidden:document.hidden};
    });
    await p.evaluate(()=>window.__mockBgSet(false));
    A(sl.hidden===true&&sl.ms>=180&&sl.ms<1500,'msebSleep(250) в фоне разрешается быстро ('+sl.ms.toFixed(0)+'мс)');

    /* 9. аудио в фоне играет */
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
        return {dt:V.currentTime-t0,paused:V.paused,hidden:document.hidden};
      });
      A(aBg.hidden===true&&aBg.dt>=2&&!aBg.paused,'аудио в фоне играет (dt='+aBg.dt.toFixed(1)+'с)');
    }catch(e){ A(false,'аудио: не поднялось',e.message); }
    await p.evaluate(()=>window.__mockBgSet(false));

    /* 10. ДИАГ: версия v56/3.10 */
    const diag=await p.evaluate(function(){
      try{
        var btn=document.getElementById('plenkaDiagBtn');
        if(btn)btn.click();
        return (document.getElementById('plenkaDiag')||{}).textContent||'';
      }catch(e){ return '' }
    });
    A(diag.indexOf('v56')>=0||diag.indexOf('3.10')>=0,'ДИАГ: версия v56/3.10',diag?'найдено в панели':'панель пуста');

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
