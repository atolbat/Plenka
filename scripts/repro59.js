#!/usr/bin/env node
/* Репродукция жалобы v58/3.12 №2: «открываю видео — кадр первого видео висит,
   само не играет, пока вручную плей не нажму». Устройство: серия быстрых
   открытий + фон→возврат между ними. Мок v58 + desktop Chromium. */
const {chromium}=require('/home/z/node_modules/playwright');
const {spawn}=require('child_process');
const http=require('http');

function waitServer(){ return new Promise(function(res,rej){
  var t0=Date.now();
  (function chk(){ http.get('http://127.0.0.1:8977/list',function(r){ r.resume(); res(); })
    .on('error',function(){ if(Date.now()-t0>15000)return rej(new Error('mock not up')); setTimeout(chk,300); }); })();
});}
function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }

(async()=>{
  const mock=spawn('python3',['/home/z/my-project/scripts/mock58.py'],{stdio:['ignore','pipe','pipe']});
  const mockLog=[]; mock.stderr.on('data',d=>mockLog.push((''+d).trim()));
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

    function snap(){ return p.evaluate(function(){
      var V=window.video;
      var buf=0; try{ if(V.buffered.length)buf=V.buffered.end(V.buffered.length-1) }catch(e){}
      return {src:(''+(V.currentSrc||V.src)).slice(-22), paused:V.paused, t:+V.currentTime.toFixed(2),
              rs:V.readyState, net:V.networkState, buf:+buf.toFixed(1), muted:V.muted,
              tok:window.playToken, sbPid:(window.vStandby&&window.vStandby._pid)||'-'};
    }); }

    /* 1. первое открытие — эталон */
    await p.evaluate(function(){ window.openItem(window.items.findIndex(function(it){return it.name==='fmp460.mp4'}),{}) });
    await sleep(2500);
    console.log('open#1 fmp460:', JSON.stringify(await snap()));

    /* 2. фон 3с → возврат (как на устройстве: сворачивание с паузой, возврат) */
    await p.evaluate(()=>window.__mockBgSet(true));
    await sleep(3000);
    await p.evaluate(()=>window.__mockBgSet(false));
    await sleep(800);
    console.log('после фон→возврат:', JSON.stringify(await snap()));

    /* 3. серия быстрых открытий с паузами ~1.2с (как тапы по библиотеке) */
    var seq=['long30.mp4','fmp460.mp4','long30.mp4','fmp460.mp4','long30.mp4'];
    for(var s=0;s<seq.length;s++){
      await p.evaluate(function(n){ window.openItem(window.items.findIndex(function(it){return it.name===n}),{}) },seq[s]);
      await sleep(1200);
      var st=await snap();
      console.log('open#'+(s+2)+' '+seq[s]+': paused='+st.paused+' t='+st.t+' rs='+st.rs+' net='+st.net+' buf='+st.buf+' sb='+st.sbPid);
    }

    /* 4. последнее открытие ждём 8с — играеть? */
    await p.evaluate(function(){ window.openItem(window.items.findIndex(function(it){return it.name==='fmp460.mp4'}),{}) });
    for(var w=0;w<8;w++){ await sleep(1000);
      var st2=await snap();
      if(st2.t>0.5)break;
    }
    console.log('финал (макс 8с):', JSON.stringify(st2));
    var verdict=await p.evaluate(function(){
      return {autoplayOk:(!window.video.paused&&window.video.currentTime>0.5),
              userPaused:window.userPaused, bgGaveUp:window.bgGaveUp, bgLive:window.bgLive,
              sndGate:window.sndGate, playToken:window.playToken};
    });
    console.log('VERDICT:', JSON.stringify(verdict));

    /* 5. если не играет — давим play() вручную как юзер и смотрим оживает ли */
    if(!verdict.autoplayOk){
      await p.evaluate(function(){ window.play() });
      await sleep(1200);
      console.log('после ручного play():', JSON.stringify(await snap()));
    }

    /* 6. журнал последних строк */
    const tail=await p.evaluate(()=>window.__plenkaDiag.journal.slice(-40).join('\n'));
    console.log('--- журнал (последние 40) ---');
    console.log(tail);
    console.log('--- ошибок JS:', errs.length, errs.slice(0,3).join(' | '));
    await b.close();
  }catch(e){
    console.log('FATAL: '+e.message);
    console.log(mockLog.slice(-6).join('\n'));
  }
  mock.kill();
  process.exit(0);
})();
