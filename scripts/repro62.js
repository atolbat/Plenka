#!/usr/bin/env node
/* РЕПРО багов v62: PiP из мини (чёрный + minist) и «призрак кадра снизу»
   после цикла: мини → PiP → закрыл PiP → закрыл видео → открыл видео. */
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
  const mock=spawn('python3',['/home/z/my-project/scripts/mock62.py'],{stdio:['ignore','pipe','pipe']});
  let fails=0;
  function A(cond,name,extra){ console.log((cond?'[ok] ':'[FAIL] ')+name+(extra?(' — '+extra):'')); if(!cond)fails++; }
  try{
    await waitServer();
    const b=await chromium.launch({args:['--autoplay-policy=no-user-gesture-required','--mute-audio',
      '--enable-unsafe-swiftshader','--use-angle=swiftshader']});
    const ctx=await b.newContext({viewport:{width:420,height:900}});
    const p=await ctx.newPage();
    const errs=[];
    p.on('pageerror',e=>errs.push('PAGEERROR: '+e.message));
    p.on('console',m=>{ if(m.type()==='error'&&!/404|Failed to load resource/.test(m.text())) errs.push('CONSOLE: '+m.text()); });
    await p.goto('http://127.0.0.1:8977/',{waitUntil:'domcontentloaded'});
    await p.waitForFunction(()=>window.items&&window.items.length>=4,null,{timeout:15000});
    await sleep(2500);

    // ── открыть видео 1 ──
    await p.evaluate(function(){ window.openItem(window.items.findIndex(function(it){return it.name==='fmp460.mp4'}),{}) });
    var t0=Date.now(); var pl=null;
    while(Date.now()-t0<12000){ var st=await p.evaluate(()=>({p:window.video.paused,t:window.video.currentTime}));
      if(!st.p&&st.t>0.4){pl=st;break} await sleep(250); }
    A(!!pl,'видео 1 играет в плеере',pl?('t='+pl.t.toFixed(1)):'не поднялось');
    await sleep(600);
    const st1=await p.evaluate(()=>({playerHidden:document.getElementById('player').hidden,
      minist:document.body.classList.contains('minist')}));
    A(st1.playerHidden===false,'видео 1 открыто в плеере');

    // ── свернуть в мини (как оболочка: history.back / __plenkaBack 'nav') ──
    await p.evaluate(()=>{ if(window.__plenkaBack)window.__plenkaBack(); });
    await p.evaluate(()=>history.back());
    await sleep(800);
    const st2=await p.evaluate(()=>({playerHidden:document.getElementById('player').hidden,
      miniShown:!document.getElementById('miniBar').hidden,
      miniVidInThumb:!!document.querySelector('#miniThumb video'),
      vA_parent:document.getElementById('video').parentNode.id,
      vB_parent:document.getElementById('videoB').parentNode.id}));
    A(st2.playerHidden===true,'свернулось в мини (player hidden)');
    A(st2.miniShown===true,'мини-панель показана');
    console.log('   mini:', JSON.stringify(st2));

    // ── PiP из мини (как Android: __pipMode(true)) ──
    await p.evaluate(()=>window.__pipMode(true));
    await sleep(400);
    const st3=await p.evaluate(()=>({
      pip:document.body.classList.contains('pip'),
      minist:document.body.classList.contains('minist'),
      playerShownByCSS:getComputedStyle(document.getElementById('player')).display,
      stageShown:getComputedStyle(document.getElementById('stage')).display,
      miniShown:!document.getElementById('miniBar').hidden}));
    console.log('   pip:', JSON.stringify(st3));
    A(st3.pip===true,'body.pip поставлен');
    A(st3.minist===false&&st3.stageShown!=='none','REPRO-1: в PiP виден stage с видео (v62: minist → чёрный)');
    A(st3.miniShown===false,'REPRO-1: мини-панель не торчит в PiP поверх');

    // ── закрыть PiP ──
    await p.evaluate(()=>window.__pipMode(false));
    await sleep(500);
    const st4=await p.evaluate(()=>({pip:document.body.classList.contains('pip'),
      playerHidden:document.getElementById('player').hidden,
      miniShown:!document.getElementById('miniBar').hidden}));
    A(st4.pip===false&&st4.playerHidden===true&&st4.miniShown===true,'после PiP: список+мини, как до входа');

    // ── закрыть видео (крестик мини) ──
    await p.evaluate(()=>document.getElementById('miniClose').click());
    await sleep(700);
    const st5=await p.evaluate(()=>({miniHidden:document.getElementById('miniBar').hidden,
      vA_src:!!document.getElementById('video').getAttribute('src'),
      vB_src:!!document.getElementById('videoB').getAttribute('src'),
      vA_parent:document.getElementById('video').parentNode.id,
      vB_parent:document.getElementById('videoB').parentNode.id,
      freeze:getComputedStyle(document.getElementById('freeze')).display,
      vblankImg:(document.getElementById('vblank').style.backgroundImage||'')}));
    console.log('   after close:', JSON.stringify(st5));
    A(st5.miniHidden===true,'мини закрыта');
    A(st5.vA_parent==='stage'&&st5.vB_parent==='stage','оба видео-элемента в stage (не застряли в miniThumb)');

    // ── открыть видео 2 ──
    await p.evaluate(function(){ window.openItem(window.items.findIndex(function(it){return it.name==='long30.mp4'}),{}) });
    await p.waitForFunction(()=>{ var v=document.getElementById('video'); return v&&(v.readyState>=2) },null,{timeout:12000}).catch(()=>{});
    await sleep(1500);
    const st6=await p.evaluate(()=>{
      function elBox(id){ var e=document.getElementById(id); if(!e)return null; var r=e.getBoundingClientRect();
        return {w:Math.round(r.width),h:Math.round(r.height),disp:getComputedStyle(e).display,vis:getComputedStyle(e).visibility,z:getComputedStyle(e).zIndex}; }
      return {miniHidden:document.getElementById('miniBar').hidden,
        miniVid:!!document.querySelector('#miniThumb video'), miniThumbHTML:(document.getElementById('miniThumb').innerHTML||'').length,
        vA:elBox('video'), vB:elBox('videoB'), vA_src:(document.getElementById('video').currentSrc||document.getElementById('video').getAttribute('src')||'').slice(-30),
        vB_src:(document.getElementById('videoB').currentSrc||document.getElementById('videoB').getAttribute('src')||'').slice(-30),
        freeze:getComputedStyle(document.getElementById('freeze')).display, freezeImg:(document.getElementById('freeze').style.backgroundImage||'').slice(0,40),
        vblankImg:(document.getElementById('vblank').style.backgroundImage||'').slice(0,40),
        posterHidden:document.getElementById('poster').hidden,
        vA_vis_style:document.getElementById('video').style.visibility,
        vB_vis_style:document.getElementById('videoB').style.visibility}});
    console.log('   video2 open:', JSON.stringify(st6));
    A(st6.miniHidden===true&&st6.miniVid===false,'REPRO-2: мини-панель скрыта, живого видео в miniThumb нет');

    await p.screenshot({path:'/home/z/my-project/scripts/repro62_ghost.png'});
    await b.close();
  }catch(e){ console.log('EXC: '+e.message); fails++; }
  finally{ mock.kill('SIGKILL'); }
  console.log(fails?('ИТОГ: '+fails+' ФЕЙЛОВ'):'ИТОГ: ВСЁ ЗЕЛЁНОЕ');
  process.exit(fails?1:0);
})();
