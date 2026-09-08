#!/usr/bin/env node
/* Смоук v60 (dev: WebGL-рендер видео) — слой #vgl поверх <video>:
   1) бут без ошибок, мост 3.13/v60;
   2) WebGL-слой жив: mode=WebGL, кадры рисуются, канвас непустой (toDataURL),
      источник 640×360, fps>0;
   3) MSE-мост + WebGL вместе (fmp460 2.4МБ > гейт 2МБ);
   4) пауза — кадры останавливаются; сик на паузе — кадр перерисован (dirty);
   5) зум-транспорт: inline-transform копируется на канвас;
   6) аудио — слой гаснет (display:none), обложка на месте;
   7) мини-цикл юзера (инвариант v59) — след. видео стартует САМО,
      слой возвращается к жизни;
   8) фон: время едет, возврат — играет (инвариант v56+);
   9) фолбэк ?vgl=2d — рисует 2D; ?vgl=off — слой выключен, видео играет
      напрямую (классический путь v59);
   10) fx-флаг plenka.vglfx поднимается и живёт после перезагрузки;
   11) ДИАГ: версия v60 + строка «рендер видео (эксперимент)»;
   12) итог: ошибок 0 на всех страницах. */
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
  const mock=spawn('python3',['/home/z/my-project/scripts/mock60.py'],{stdio:['ignore','pipe','pipe']});
  const mockLog=[]; mock.stderr.on('data',d=>mockLog.push((''+d).trim()));
  let fails=0;
  function A(cond,name,extra){ console.log((cond?'[ok] ':'[FAIL] ')+name+(extra?(' — '+extra):'')); if(!cond)fails++; }
  try{
    await waitServer();
    const b=await chromium.launch({args:[
      '--autoplay-policy=no-user-gesture-required','--mute-audio',
      '--enable-unsafe-swiftshader','--use-angle=swiftshader']});
    const ctx=await b.newContext({viewport:{width:420,height:900}});
    const p=await ctx.newPage();
    const errs=[];
    p.on('pageerror',e=>errs.push('PAGEERROR: '+e.message));
    p.on('console',m=>{ if(m.type()==='error')errs.push('CONSOLE: '+m.text()); });
    await p.goto('http://127.0.0.1:8977/',{waitUntil:'domcontentloaded'});
    await p.waitForFunction(()=>window.items&&window.items.length>=3,null,{timeout:15000});
    await sleep(1400);
    A(errs.length===0,'v60 поднялась без JS-ошибок',errs.length?errs[0]:'');
    A((await p.evaluate(()=>window.PlenkaNative.version())).indexOf('3.13')>=0,'мост представился 3.13');

    function open(name){ return p.evaluate(function(n){
      window.openItem(window.items.findIndex(function(it){return it.name===n}),{});
    },name); }
    async function waitPlaying(sec){ var t0=Date.now();
      while(Date.now()-t0<(sec||6000)*1000){
        var st=await p.evaluate(()=>({p:window.video.paused,t:window.video.currentTime}));
        if(!st.p&&st.t>0.4)return st; await sleep(250);
      } return null; }

    /* 2-3. MSE + WebGL: слой жив и рисует */
    open('fmp460.mp4');
    var mse=await waitPlaying(8);
    A(!!mse,'fMP4: MSE-мост играет под WebGL-слоем',mse?('t='+mse.t.toFixed(1)):'не поднялся');
    await sleep(1200);
    var st1=await p.evaluate(function(){
      var c=document.getElementById('vgl');
      return {mode:window.__vgl.mode,drawn:window.__vgl.drawn,fps:window.__vgl.fps,
              fw:window.__vgl.fw,fh:window.__vgl.fh,disp:c.style.display,
              url:c.toDataURL('image/png').length};
    });
    A(/WebGL/.test(st1.mode),'рендер: WebGL',st1.mode);
    A(st1.drawn>5,'кадры рисуются в канвас','drawn='+st1.drawn);
    A(st1.disp==='block','канвас активен (display block)','disp='+st1.disp);
    A(st1.url>4000,'канвас НЕ пустой (кадр виден)','toDataURL='+st1.url+'Б');
    A(st1.fw===640&&st1.fh===360,'источник кадра 640×360',st1.fw+'×'+st1.fh);
    A(st1.fps>0,'fps>0','fps='+st1.fps);

    /* 4. пауза — кадры останавливаются */
    await p.evaluate(()=>window.video.pause());
    await sleep(400);
    var d0=await p.evaluate(()=>window.__vgl.drawn);
    await sleep(700);
    var d1=await p.evaluate(()=>window.__vgl.drawn);
    A(d1-d0<=3,'пауза: слой не молотит вхолостую','+кадров='+(d1-d0));

    /* 5. сик на паузе — кадр перерисован (dirty) */
    await p.evaluate(function(){ return new Promise(function(r){
      var v=window.video; v.addEventListener('seeked',function h(){ v.removeEventListener('seeked',h); r() },{once:true});
      v.currentTime=25;
    }) });
    await sleep(600);
    var d2=await p.evaluate(()=>window.__vgl.drawn);
    A(d2>d1,'сик на паузе: кадр ПЕРЕРИСОВАН (dirty-механика)','+кадров='+(d2-d1));
    var t=await p.evaluate(()=>window.video.currentTime);
    A(Math.abs(t-25)<1.2,'сик сел на ~25с','t='+t.toFixed(1));

    /* 6. зум-транспорт: transform копируется */
    await p.evaluate(function(){ window.video.style.transform='scale(1.33) translateX(10px)'; });
    await sleep(250);
    var tr=await p.evaluate(()=>document.getElementById('vgl').style.transform);
    A(tr==='scale(1.33) translateX(10px)','зум-транспорт перенесён на канвас',tr);
    await p.evaluate(function(){ window.video.style.transform=''; });

    /* 7. аудио: слой гаснет */
    open('song.mp3');
    var au=await waitPlaying(6);
    A(!!au,'аудио играет',au?('t='+au.t.toFixed(1)):'не поднялось');
    await sleep(600);
    var au2=await p.evaluate(function(){
      return {disp:document.getElementById('vgl').style.display,
              art:document.getElementById('audioArt').classList.contains('show')};
    });
    A(au2.disp==='none','аудио: WebGL-слой погашен','disp='+au2.disp);
    A(au2.art,'аудио: обложка на месте');

    /* 8. мини-цикл юзера (инвариант v59) + возвращение слоя */
    open('fmp460.mp4');
    var v1=await waitPlaying(8);
    A(!!v1,'видео снова играет перед мини-циклом');
    var cycle=await p.evaluate(async function(){
      window.closePlayerView({});
      await new Promise(r=>setTimeout(r,350));
      document.getElementById('miniClose').click();
      await new Promise(r=>setTimeout(r,200));
      return {cur:window.currentIdx};
    });
    A(cycle.cur===-1,'мини-цикл: панель закрыта, библиотека чистая');
    open('long30.mp4');
    var after=await waitPlaying(8);
    A(!!after,'МИНИ-ЦИКЛ: следующее видео стартует САМО (инвариант v59)',
      after?('t='+after.t.toFixed(1)):'так и не заиграло');
    await sleep(800);
    var st2=await p.evaluate(function(){
      return {disp:document.getElementById('vgl').style.display,drawn:window.__vgl.drawn};
    });
    A(st2.disp==='block','после мини-цикла слой вернулся (display block)','disp='+st2.disp);
    A(st2.drawn>d2,'кадры снова рисуются','drawn='+st2.drawn+' (было '+d2+')');

    /* 9. фон: время едет, возврат — играет */
    await p.evaluate(function(){ window.__mockBgSet(true); });
    var tA=await p.evaluate(()=>window.video.currentTime);
    await sleep(2600);
    var tB=await p.evaluate(()=>window.video.currentTime);
    A(tB-tA>1.5,'фон: время едет под скрытой вкладкой','+'+(tB-tA).toFixed(1)+'с');
    await p.evaluate(function(){ window.__mockBgSet(false); });
    await sleep(900);
    var st3=await p.evaluate(()=>({p:window.video.paused,t:window.video.currentTime}));
    A(!st3.p&&st3.t>0.4,'возврат из фона: видео играет без паузы','t='+st3.t.toFixed(1));
    var sch=await p.evaluate(()=>window.__vgl.sched);
    A(sch==='rAF','петля рендера проснулась после возврата','sched='+sch);

    /* 10. fx-флаг живёт после перезагрузки */
    await p.evaluate(function(){ try{localStorage.setItem('plenka.vglfx','1')}catch(e){} });
    await p.reload({waitUntil:'domcontentloaded'});
    await p.waitForFunction(()=>window.items&&window.items.length>=3,null,{timeout:15000});
    open('long30.mp4');
    var v2=await waitPlaying(8);
    A(!!v2,'с fx=1 видео играет');
    var fx=await p.evaluate(function(){ return {fx:window.__vgl.fx,url:document.getElementById('vgl').toDataURL('image/png').length} });
    A(fx.fx===1,'флаг плёнки прочитан при загрузке','fx='+fx.fx);
    A(fx.url>4000,'fx=1: шейдер рисует (канвас непустой)','toDataURL='+fx.url+'Б');
    await p.evaluate(function(){ try{localStorage.removeItem('plenka.vglfx')}catch(e){} });

    /* 11. ДИАГ: версия и строка рендера */
    var diag=await p.evaluate(function(){
      var b=document.getElementById('plenkaDiagBtn');
      if(b)b.click();
      var pre=document.getElementById('plenkaDiagPre');
      return pre?pre.textContent:'';
    });
    A(/v60/.test(diag),'ДИАГ: версия v60');
    A(/рендер видео \(эксперимент\)/.test(diag)&&/WebGL/.test(diag),'ДИАГ: строка рендера (WebGL)',
      (diag.match(/рендер видео[^\n]*/)||[''])[0]);

    /* 12. фолбэк ?vgl=2d */
    const p2=await ctx.newPage();
    const errs2=[];
    p2.on('pageerror',e=>errs2.push('PAGEERROR: '+e.message));
    p2.on('console',m=>{ if(m.type()==='error')errs2.push('CONSOLE: '+m.text()); });
    await p2.goto('http://127.0.0.1:8977/?vgl=2d',{waitUntil:'domcontentloaded'});
    await p2.waitForFunction(()=>window.items&&window.items.length>=3,null,{timeout:15000});
    await p2.evaluate(function(n){ window.openItem(window.items.findIndex(function(it){return it.name===n}),{}) },'long30.mp4');
    var v3=await (async function(){ var t0=Date.now();
      while(Date.now()-t0<8000){ var st=await p2.evaluate(()=>({p:window.video.paused,t:window.video.currentTime}));
        if(!st.p&&st.t>0.4)return st; await sleep(250);} return null; })();
    A(!!v3,'?vgl=2d: видео играет');
    await sleep(1500);                        /* дать петле раскрутиться (на главной эту роль играл sleep(1200)) */
    var st4=await p2.evaluate(function(){ return {mode:window.__vgl.mode,drawn:window.__vgl.drawn,
      url:document.getElementById('vgl').toDataURL('image/png').length} });
    var g1=st4.drawn;
    await sleep(700);
    var g2=await p2.evaluate(()=>window.__vgl.drawn);
    A(/2D/.test(st4.mode),'?vgl=2d: режим 2D',st4.mode);
    A(st4.drawn>5&&g2>g1,'?vgl=2d: 2D-канвас рисует кадры','drawn='+st4.drawn+'→'+g2+' url='+st4.url+'Б');
    A(errs2.length===0,'?vgl=2d: 0 JS-ошибок',errs2.length?errs2[0]:'');

    /* 13. фолбэк ?vgl=off — классический путь v59 */
    const p3=await ctx.newPage();
    const errs3=[];
    p3.on('pageerror',e=>errs3.push('PAGEERROR: '+e.message));
    p3.on('console',m=>{ if(m.type()==='error')errs3.push('CONSOLE: '+m.text()); });
    await p3.goto('http://127.0.0.1:8977/?vgl=off',{waitUntil:'domcontentloaded'});
    await p3.waitForFunction(()=>window.items&&window.items.length>=3,null,{timeout:15000});
    var mOff=await p3.evaluate(()=>window.__vgl.mode);
    A(/выключен/.test(mOff),'?vgl=off: слой выключен',mOff);
    await p3.evaluate(function(n){ window.openItem(window.items.findIndex(function(it){return it.name===n}),{}) },'long30.mp4');
    var v4=await (async function(){ var t0=Date.now();
      while(Date.now()-t0<8000){ var st=await p3.evaluate(()=>({p:window.video.paused,t:window.video.currentTime}));
        if(!st.p&&st.t>0.4)return st; await sleep(250);} return null; })();
    A(!!v4,'?vgl=off: видео играет напрямую (путь v59)');
    var dispOff=await p3.evaluate(function(){ var c=document.getElementById('vgl');
      return getComputedStyle(c).display; });
    A(dispOff==='none','?vgl=off: канвас скрыт (computed)','disp='+dispOff);
    A(errs3.length===0,'?vgl=off: 0 JS-ошибок',errs3.length?errs3[0]:'');

    /* 14. итог по главной странице */
    A(errs.length===0,'главная страница: 0 JS-ошибок за весь прогон',errs.length?errs[0]:'');

    await b.close();
  }catch(e){
    console.log('[FAIL] аварийный выход: '+e.message);
    if(mockLog.length)console.log('mock log tail:\n'+mockLog.slice(-8).join('\n'));
    fails++;
  }
  mock.kill();
  console.log(fails?('ИТОГ: FAIL = '+fails):'ИТОГ: ВСЁ ЗЕЛЁНОЕ');
  process.exit(fails?1:0);
})();
