#!/usr/bin/env node
/* Репро-Б: флоу с мини-панелью, как на устройстве:
   open → (видео не успело заиграть / заиграло) → браузерный назад → enterMini
   → miniClose (playToken++) → открыть следующее → ждём автоплей.
   Плюс: DOM-перестановки dockVideos на играющем элементе. */
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
    await p.goto('http://127.0.0.1:8977/',{waitUntil:'domcontentloaded'});
    await p.waitForFunction(()=>window.items&&window.items.length>=3,null,{timeout:15000});
    await sleep(1200);

    function snap(){ return p.evaluate(function(){
      var V=window.video;
      var buf=0; try{ if(V.buffered.length)buf=V.buffered.end(V.buffered.length-1) }catch(e){}
      return {paused:V.paused,t:+V.currentTime.toFixed(2),rs:V.readyState,net:V.networkState,
              buf:+buf.toFixed(1),tok:window.playToken,cur:window.currentIdx,
              mini:window.MINI.mode,playerHidden:window.player.hidden};
    }); }
    function open(name){ return p.evaluate(function(n){
      window.openItem(window.items.findIndex(function(it){return it.name===n}),{});
    },name); }

    /* A. открыли — сразу назад (enterMini, как свайп-назад на устройстве) */
    open('fmp460.mp4'); await sleep(400);
    console.log('A1 (0.4с после open):', JSON.stringify(await snap()));
    await p.evaluate(function(){ window.closePlayerView({}); });   /* браузерный назад → enterMini */
    await sleep(300);
    console.log('A2 (после назад→мини):', JSON.stringify(await snap()));
    /* мини-бар видим; через 1с жмём miniClose (playToken++) */
    await sleep(1000);
    await p.evaluate(function(){ document.getElementById('miniClose').click(); });
    await sleep(200);
    console.log('A3 (после miniClose):', JSON.stringify(await snap()));

    /* B. тут же открываем следующее — как юзер. Ждём автоплей 5с */
    open('long30.mp4');
    for(var w=0;w<5;w++){ await sleep(1000); var s=await snap();
      if(s.t>0.4 && !s.paused) break; }
    console.log('B (long30 после мини-цикла, ждали до 5с):', JSON.stringify(s));

    /* C. то же ещё раз: назад сразу, потом open следующего СРАЗУ (0.3с) — гонка с мини */
    await p.evaluate(function(){ window.closePlayerView({}); }); await sleep(250);
    await p.evaluate(function(){ document.getElementById('miniClose').click(); }); await sleep(150);
    open('fmp460.mp4');
    for(var w2=0;w2<5;w2++){ await sleep(1000); var s2=await snap();
      if(s2.t>0.4 && !s2.paused) break; }
    console.log('C (fmp460 сразу после miniClose):', JSON.stringify(s2));

    /* D. открыли, дали заиграть, назад→мини, тап по панели (openMiniPlayer), назад опять */
    open('long30.mp4'); await sleep(2500);
    console.log('D1 (играет 2.5с):', JSON.stringify(await snap()));
    await p.evaluate(function(){ window.closePlayerView({}); }); await sleep(300);   /* в мини */
    await p.evaluate(function(){ window.openMiniPlayer(); }); await sleep(300);      /* обратно в плеер */
    await p.evaluate(function(){ window.closePlayerView({}); }); await sleep(300);   /* снова в мини */
    await p.evaluate(function(){ document.getElementById('miniClose').click(); }); await sleep(200);
    console.log('D2 (мини-цикл туда-сюда + close):', JSON.stringify(await snap()));
    open('fmp460.mp4');
    for(var w3=0;w3<5;w3++){ await sleep(1000); var s3=await snap();
      if(s3.t>0.4 && !s3.paused) break; }
    console.log('D3 (fmp460 после D):', JSON.stringify(s3));

    /* E. чистый стресс: DOM-move играющего элемента (dockVideos-эффект) */
    open('long30.mp4'); await sleep(2200);
    var mv=await p.evaluate(async function(){
      var st=document.getElementById('stage');
      var V=window.video;
      var t0=V.currentTime, paused0=V.paused;
      /* перестановка местами videoA/videoB, как делает dockVideos при возврате из мини */
      st.insertBefore(window.videoB, st.firstChild);
      st.insertBefore(window.videoA, window.videoB.nextSibling);
      await new Promise(r=>setTimeout(r,700));
      return {t0:t0, paused0:paused0, t1:V.currentTime, paused1:V.paused, rs:V.readyState,
              net:V.networkState, buf0:0};
    });
    console.log('E (DOM-move играющего):', JSON.stringify(mv));

    console.log('--- ошибки JS:', errs.length, errs.slice(0,4).join(' | '));
    const tail=await p.evaluate(()=>window.__plenkaDiag.journal.slice(-30).join('\n'));
    console.log('--- журнал ---'); console.log(tail);
    await b.close();
  }catch(e){ console.log('FATAL: '+e.message); console.log(mockLog.slice(-5).join('\n')); }
  mock.kill(); process.exit(0);
})();
