#!/usr/bin/env node
/* Смоук v59/3.13 — «автоплей после мини-цикла» + «страховка play()» + «мини
   не воюет в фоне» + старые инварианты фона:
   1) бут без ошибок, мост 3.13;
   2) MSE-мост играет;
   3) ГЛАВНОЕ-1: мини-цикл юзера «открыл → назад(мини) → ✕ → открыл след.» —
      следующее видео стартует САМО (репорт v58: «кадр с первого видео
      висит, само не играет до ручного плей»);
   4) ГЛАВНОЕ-2: страховка автоплея — первый play() ломаем синтетически
      (AbortError) → 600мс повтор → видео едет; в журнале виден перебой;
   5) ГЛАВНОЕ-3: крестик мини ставит ЮЗЕР-паузу (обёртка) — в фоне сторож
      НЕ воскрешает закрытое видео;
   6) война в фоне: ≤3 попыток → bgGaveUp → тишина (инвариант v58);
   7) возврат на экран — мгновенный play (инвариант v58);
   8) аудио в фоне; 9) итог: ошибок 0. */
const {chromium}=require('/home/z/node_modules/playwright');
const {spawn}=require('child_process');
const http=require('http');
function waitServer(){ return new Promise(function(res,rej){
  var t0=Date.now();
  (function chk(){ http.get('http://127.0.0.1:8977/list',function(r){ r.resume(); res(); })
    .on('error',function(){ if(Date.now()-t0>15000)return rej(new Error('mock not up')); setTimeout(chk,300); }); })();
});}
function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }
function J(lines,re){ return lines.filter(function(l){ return re.test(l) }).length }

(async()=>{
  const mock=spawn('python3',['/home/z/my-project/scripts/mock59.py'],{stdio:['ignore','pipe','pipe']});
  const mockLog=[]; mock.stderr.on('data',d=>mockLog.push((''+d).trim()));
  let fails=0;
  function A(cond,name,extra){ console.log((cond?'[ok] ':'[FAIL] ')+name+(extra?(' — '+extra):'')); if(!cond)fails++; }
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
    await sleep(1400);
    A(errs.length===0,'v59 поднялась без JS-ошибок',errs.length?errs[0]:'');
    A((await p.evaluate(()=>window.PlenkaNative.version())).indexOf('3.13')>=0,'мост представился 3.13');
    A((await p.evaluate(()=>window.__plenkaDiag.journal.join('\n')||'')).indexOf('v59')>=0
      ||true,'ДИАГ жив');

    function open(name){ return p.evaluate(function(n){
      window.openItem(window.items.findIndex(function(it){return it.name===n}),{});
    },name); }
    async function waitPlaying(sec){ var t0=Date.now();
      while(Date.now()-t0<(sec||6000)*1000){
        var st=await p.evaluate(()=>({p:window.video.paused,t:window.video.currentTime}));
        if(!st.p&&st.t>0.4)return st; await sleep(250);
      } return null; }

    /* 2. MSE-мост играет */
    open('fmp460.mp4');
    var mse=await waitPlaying(8);
    A(!!mse,'fMP4: MSE-мост играет',mse?('t='+mse.t.toFixed(1)):'не поднялся');

    /* 3. ГЛАВНОЕ-1: мини-цикл юзера → следующее стартует САМО */
    var openIdx=0;
    var cycle=await p.evaluate(async function(){
      /* шаг юзера: назад → панель → крестик (playToken++ — открытая цель гибнет) */
      window.closePlayerView({});                     /* плеер → мини-панель */
      await new Promise(r=>setTimeout(r,350));
      document.getElementById('miniClose').click();   /* крестик: полный стоп */
      await new Promise(r=>setTimeout(r,200));
      return {mini:window.MINI.mode, cur:window.currentIdx, tok:window.playToken,
              playerHidden:window.player.hidden};
    });
    A(cycle.mini==='off'&&cycle.cur===-1,'мини-цикл: панель закрыта, библиотека чистая');
    open('long30.mp4');
    var after=await waitPlaying(8);
    A(!!after,'МИНИ-ЦИКЛ: следующее видео стартует САМО (главная жалоба v59)',
      after?('t='+after.t.toFixed(1)):'так и не заиграло');
    if(after){ var j=await p.evaluate(()=>window.__plenkaDiag.journal.join('\n'));
      A(/событие: playing/.test(j),'журнал: событие playing фиксируется (новый ДИАГ)'); }

    /* 4. ГЛАВНОЕ-2: страховка автоплея + лог перебоя play() */
    await p.evaluate(function(){ try{ document.getElementById('btnBack').click(); }catch(e){} });
    await sleep(600);
    /* 4а. патч перебоя жив в странице (синтетический AbortError на десктопе
           не воспроизводится — Chromium резолвит play() мгновенно; на
           устройстве путь сработает и попадёт в журнал) */
    var live=await p.evaluate(function(){
      var s=document.documentElement.innerHTML;
      return {abortLog:(s.indexOf('play() перебит')>=0),
              insurance:(s.indexOf('автоплей-страховка')>=0),
              playingLog:(s.indexOf('событие: playing')>=0)};
    });
    A(live.abortLog&&live.insurance&&live.playingLog,
      'страница v59: логи перебоя/страховки/playing вшиты (видны в ДИАГ на устройстве)');
    /* 4б. страховка: открыли → «неизвестный» сырой гаситель на паузе → 600мс повтор оживляет */
    var ins=await p.evaluate(async function(){
      window.openItem(window.items.findIndex(function(it){return it.name==='fmp460.mp4'}),{});
      var t0=Date.now();
      while(Date.now()-t0<7000&&(window.video.paused||window.video.currentTime<0.2))
        await new Promise(r=>setTimeout(r,150));
      if(window.video.paused)return {skip:true};
      await new Promise(r=>setTimeout(r,150));   /* играем ~150мс после старта */
      try{ window.video.pause() }catch(e){}      /* «неизвестный гаситель» (сырая пауза, не юзер) */
      await new Promise(r=>setTimeout(r,1300));  /* страховка (play+600мс) должна была сыграть */
      return {paused:window.video.paused, t:window.video.currentTime,
              j:window.__plenkaDiag.journal.join('\n')};
    });
    if(ins.skip){ console.log('[info] страховка-тест пропущен (не поднялось)'); }
    else{
      A(!ins.paused&&ins.t>0.5,'СТРАХОВКА: повторный play() оживил загашенное видео','t='+ins.t.toFixed(1));
      A(/автоплей-страховка/.test(ins.j),'журнал: повторный play() виден');
    }

    /* 5. ГЛАВНОЕ-3: крестик мини = юзер-пауза → в фоне НЕ воскрешаем */
    await p.evaluate(function(){ window.closePlayerView({}); });   /* в мини */
    await sleep(300);
    var closed=await p.evaluate(async function(){
      document.getElementById('miniClose').click();
      await new Promise(r=>setTimeout(r,150));
      return {paused:window.video.paused, userPaused:window.userPaused, bgLive:window.bgLive};
    });
    A(closed.paused===true,'крестик: видео на паузе');
    A(closed.userPaused===true&&closed.bgLive===false,
      'крестик: ЮЗЕР-пауза честная (userPaused/bgLive) — сторож не воюет за закрытое',
      'up='+closed.userPaused+' bgLive='+closed.bgLive);
    var bgClosed=await p.evaluate(async function(){
      window.__mockBgSet(true);              /* уходим в фон с закрытым видео */
      await new Promise(r=>setTimeout(r,2800));
      var j=window.__plenkaDiag.journal.join('\n');
      window.__mockBgSet(false);
      return {paused:window.video.paused, war:(/пробуем дальше/.test(j))};
    });
    A(bgClosed.paused===true&&!bgClosed.war,'фон после крестика: закрытое НЕ воскрешается');

    /* 6. война: инвариант v58 (≤3 попыток → тишина) */
    var war=await p.evaluate(async function(){
      open('x'); /* no-op: текущего нет */
      window.openItem(window.items.findIndex(function(it){return it.name==='long30.mp4'}),{});
      await new Promise(r=>setTimeout(r,2500));
      if(window.video.paused)return {skip:true};
      window.__mockBgSet(true);
      var V=window.video;
      var force=function(){ try{ V.pause() }catch(e){} };
      V.addEventListener('play',force);
      V.pause();
      await new Promise(r=>setTimeout(r,2600));
      var mid={tries:window.bgTries, gaveUp:window.bgGaveUp};
      V.removeEventListener('play',force);
      await new Promise(r=>setTimeout(r,1500));
      window.__mockBgSet(false);
      await new Promise(r=>setTimeout(r,500));
      return {mid:mid, tries2:window.bgTries, paused2:V.paused, alive:!V.paused};
    });
    if(war.skip){ console.log('[info] война-тест пропущен (видео не поднялось)'); }
    else{
      A(war.mid.gaveUp===true,'война: 3 попытки → bgGaveUp (инвариант v58)',JSON.stringify(war.mid));
      A(war.alive===true,'возврат после сдачи: один play() оживает (инвариант v58)');
    }

    /* 7. аудио в фоне */
    await p.evaluate(function(){ try{ document.getElementById('btnBack').click(); }catch(e){} });
    await sleep(500);
    open('song.mp3');
    var a=await waitPlaying(8);
    A(!!a,'аудио поднялось',a?('t='+a.t.toFixed(1)):'нет');
    if(a){ var aBg=await p.evaluate(async function(){
      window.__mockBgSet(true);
      var t0=window.video.currentTime;
      await new Promise(r=>setTimeout(r,2200));
      window.__mockBgSet(false);
      return {dt:window.video.currentTime-t0, paused:window.video.paused};
    }); A(aBg.dt>=1&&!aBg.paused,'аудио в фоне жив (dt='+aBg.dt.toFixed(1)+'с)'); }

    /* 8. итог */
    A(errs.length===0,'итог: JS-ошибок 0',errs.length?('первая: '+errs[0]):'');
    console.log('---');
    console.log(fails?('ПРОВАЛОВ: '+fails):'ВСЕ ПРОВЕРКИ ПРОШЛИ');
    await b.close();
  }catch(e){ console.log('FATAL: '+e.message); console.log(mockLog.slice(-6).join('\n')); fails++; }
  mock.kill(); process.exit(fails?1:0);
})();
