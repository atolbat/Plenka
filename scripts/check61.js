#!/usr/bin/env node
/* Смоук v61: три фикса репорта + регресс инвариантов v59.
   1) БАГ-1 «на старте на мгновение видны все видео, втч приватные»:
      IDB-чтение hiddenlist искусственно замедлено (init-script, 900мс);
      сразу после загрузки зовём __plenkaResume (как оболочка на
      onPageFinished) — синк+мерж успевают ДО hiddenlist. Инвариант:
      пока hiddenReady=false — в списке 0 строк (гейт рендера);
      после — только публичные, скрытой карточки НЕТ.
   2) БАГ-2 «смотрю приватное, свайп назад → публичная папка»:
      скрыли long30 → вошли в скрытый раздел → открыли его →
      __plenkaBack обязан ответить 'nav' (плеер открыт!) и НЕ выходить
      из раздела; history.back() (то, что делает оболочка) закрывает
      плеер в мини — список остаётся СКРЫТЫМ.
   3) БАГ-3 «аудио без обложки — битый плейсхолдер»:
      noart.mp3 (мок: /t/a/4 → 404) — плеер-арт=винил, мини=нота,
      очередь=плейсхолдер; song.mp3 (арт есть) — в мини живая картинка.
   4) Регресс v59: MSE-мост (fMP4 2.4МБ > гейт 2МБ), мини-цикл юзера
      (след. видео стартует САМО), фон (время едет, возврат — играет),
      ДИАГ v61, 0 JS-ошибок. */
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
  const mock=spawn('python3',['/home/z/my-project/scripts/mock61.py'],{stdio:['ignore','pipe','pipe']});
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
    p.on('console',m=>{ if(m.type()==='error'){
      var txt=m.text();
      if(/Failed to load resource/.test(txt)){       /* 404 обложки без арта — ожидаемая сеть, не JS-ошибка */
        try{ var loc=m.location()||{}; if(loc.url&&(''+loc.url).indexOf('/t/')>0)return; }catch(e){}
      }
      errs.push('CONSOLE: '+txt);
    }});
    await p.goto('http://127.0.0.1:8977/',{waitUntil:'domcontentloaded'});
    await p.waitForFunction(()=>window.items&&window.items.length>=4,null,{timeout:15000});
    await sleep(1400);
    A(errs.length===0,'v61 поднялась без JS-ошибок',errs.length?errs[0]:'');
    A((await p.evaluate(()=>window.PlenkaNative.version())).indexOf('3.13')>=0,'мост представился 3.13');
    function open(name){ return p.evaluate(function(n){
      window.openItem(window.items.findIndex(function(it){return it.name===n}),{});
    },name); }
    async function waitPlaying(sec){ var t0=Date.now();
      while(Date.now()-t0<(sec||6000)*1000){
        var st=await p.evaluate(()=>({p:window.video.paused,t:window.video.currentTime}));
        if(!st.p&&st.t>0.4)return st; await sleep(250);
      } return null; }

    /* ═══ 3. БАГ-3: аудио без обложки ═══ */
    open('noart.mp3');
    var au1=await waitPlaying(8);
    A(!!au1,'аудио без арта играет',au1?('t='+au1.t.toFixed(1)):'не поднялось');
    await sleep(900);                       /* 404 арта успевает прилететь и обработаться */
    var art=await p.evaluate(function(){
      var d=document.querySelector('#audioArt .aa-disc');
      var im=d?d.querySelector('img'):null;
      return {vinyl:d?d.classList.contains('vinyl'):false,
              src:im?((im.src||'').slice(0,22)):'—',
              broken:im?(!im.complete||im.naturalWidth===0):false};
    });
    A(art.vinyl||art.src.indexOf('data:image/svg')===0,'плеер-арт: винил вместо битой картинки',
      'vinyl='+art.vinyl+' src='+art.src);
    A(!art.broken,'плеер-арт: картинка не битая','broken='+art.broken);
    await p.evaluate(()=>window.closePlayerView({}));   /* вниз — мини-панель */
    await sleep(900);
    var m1=await p.evaluate(function(){
      var mt=document.getElementById('miniThumb');
      var im=mt.querySelector('img');
      return {hasSvg:mt.innerHTML.indexOf('<svg')>=0,
              img:!!im,fb:im?!!im._fb:false,
              broken:im?(!im.complete||im.naturalWidth===0):false};
    });
    A(!m1.img||(m1.fb&&m1.hasSvg),'мини-панель: 404 арта → нота, не битая иконка',
      'img='+m1.img+' fb='+m1.fb+' svg='+m1.hasSvg);
    A(!m1.broken,'мини-панель: картинка не битая');
    var q1=await p.evaluate(function(){
      window.renderQueue(true);
      var rows=document.querySelectorAll('#qList .q-item');
      var bad=0,tot=0;
      rows.forEach(function(r){
        var im=r.querySelector('.qi-thumb img'); if(!im)return; tot++;
        var st=''+(im.src||'');
        if((!im.complete||im.naturalWidth===0)&&st.indexOf('data:')!==0&&!im._fb)bad++;
      });
      return {rows:rows.length,bad:bad,tot:tot};
    });
    await sleep(900);
    var q2=await p.evaluate(function(){
      var rows=document.querySelectorAll('#qList .q-item');
      var bad=0,ph=0;
      rows.forEach(function(r){
        var im=r.querySelector('.qi-thumb img'); if(!im)return;
        var st=''+(im.src||'');
        if(st.indexOf('data:')===0||im._fb)ph++;
        else if(!im.complete||im.naturalWidth===0)bad++;
      });
      return {rows:rows.length,bad:bad,ph:ph};
    });
    A(q2.rows>=4,'очередь: построена ('+q2.rows+' строк)');
    A(q2.bad===0,'очередь: битых картинок 0 (404 → плейсхолдер)','bad='+q2.bad+' плейсхолдеров='+q2.ph);
    var g1=await p.evaluate(function(){
      var rows=document.querySelectorAll('#libList .lib-row');
      var bad=0;
      rows.forEach(function(r){
        var im=r.querySelector('.lib-thumb img'); if(!im)return;
        var st=''+(im.src||'');
        if(st.indexOf('data:')!==0&&!im._fb&&(!im.complete||im.naturalWidth===0))bad++;
      });
      return {rows:rows.length,bad:bad};
    });
    A(g1.bad===0,'библиотека: битых превью 0','rows='+g1.rows+' bad='+g1.bad);
    /* контраст: аудио С артом — в мини живая картинка */
    open('song.mp3');
    var au2=await waitPlaying(8);
    A(!!au2,'аудио с артом играет');
    await p.evaluate(()=>window.closePlayerView({}));
    await sleep(900);
    var m2=await p.evaluate(function(){
      var im=document.getElementById('miniThumb').querySelector('img');
      return im?{ok:im.complete&&im.naturalWidth>0,broken:im.naturalWidth===0}:{ok:false};
    });
    A(m2.ok,'аудио с артом: в мини живая обложка (контраст)','naturalWidth>0='+m2.ok);
    await p.evaluate(function(){ document.getElementById('miniClose').click(); });
    await sleep(400);

    /* ═══ 2. БАГ-2: назад из приватного видео ═══ */
    var hid=await p.evaluate(function(){
      var it=window.items.filter(function(i){return i.name==='long30.mp4'})[0];
      window.toggleHide(it);
      return {hid:!!window.hiddenSet[it.id],rows:document.querySelectorAll('#libList .lib-row').length};
    });
    A(hid.hid,'long30 скрыт (жест сохранён в IDB)');
    A(!hid.rows||hid.rows<=3,'публичный список: скрытой карточки нет','rows='+hid.rows);
    await p.evaluate(()=>window.setHiddenView(true));
    await sleep(300);
    var hv=await p.evaluate(function(){
      var names=[].map.call(document.querySelectorAll('#libList .lib-name'),function(e){return e.textContent});
      return {hv:window.hiddenView,n:names.length,has:names.indexOf('long30')>=0};
    });
    A(hv.hv&&hv.has&&hv.n===1,'скрытый раздел: только long30','n='+hv.n+' has='+hv.has);
    open('long30.mp4');
    var pl=await waitPlaying(8);
    A(!!pl,'приватное видео играет',pl?('t='+pl.t.toFixed(1)):'не поднялось');
    var bk=await p.evaluate(()=>window.__plenkaBack());
    A(bk==='nav','НАЗАД при открытом плеере: ответ \"nav\" (закрыть плеер), не \"ui\"','отв='+bk);
    var stB=await p.evaluate(()=>({hv:window.hiddenView,open:!window.player.hidden}));
    A(stB.hv&&stB.open,'после «назад»: плеер открыт, скрытый раздел НЕ покинут','hv='+stB.hv+' player='+stB.open);
    await p.evaluate(()=>history.back());      /* оболочка после 'nav' делает goBack() */
    await sleep(700);
    var stM=await p.evaluate(function(){
      var names=[].map.call(document.querySelectorAll('#libList .lib-name'),function(e){return e.textContent});
      return {hv:window.hiddenView,mini:!document.getElementById('miniBar').hidden,
              plHidden:window.player.hidden,n:names.length,has:names.indexOf('long30')>=0,
              pub:names.indexOf('fmp460')>=0};
    });
    A(stM.plHidden&&stM.mini,'плеер закрылся в мини-панель (шаг истории)');
    A(stM.hv&&stM.has&&!stM.pub,'СВИП НАЗАД ИЗ ПРИВАТНОГО: список остался СКРЫТЫМ (публичной папки нет)',
      'hv='+stM.hv+' long30='+stM.has+' fmp460='+stM.pub+' n='+stM.n);
    var bk2=await p.evaluate(()=>window.__plenkaBack());
    var stE=await p.evaluate(function(){
      var names=[].map.call(document.querySelectorAll('#libList .lib-name'),function(e){return e.textContent});
      return {hv:window.hiddenView,n:names.length,has:names.indexOf('long30')>=0};
    });
    A(bk2==='ui'&&stE.hv===false,'следующий «назад» (плеер закрыт): выход из скрытого — как прежде','отв='+bk2+' hv='+stE.hv);
    A(!stE.has,'публичная папка после выхода: скрытых нет','n='+stE.n);
    await p.evaluate(function(){ try{localStorage.setItem('__testIdbDelay','1')}catch(e){} });

    /* ═══ 1. БАГ-1: флэш скрытых на старте ═══ */
    await p.addInitScript(function(){
      if(localStorage.getItem('__testIdbDelay')!=='1')return;
      var origOpen=indexedDB.open.bind(indexedDB);       /* задержка onsuccess 900мс —
          воспроизводит «IDB холодный, синк оболочки быстрее» */
      indexedDB.open=function(name,ver){
        var req=origOpen(name,ver);
        try{
          Object.defineProperty(req,'onsuccess',{
            configurable:true,
            get:function(){ return null },
            set:function(f){
              req.addEventListener('success',function(ev){
                setTimeout(function(){ try{ f.call(req,ev) }catch(e2){} },900);
              },{once:true});
            }
          });
        }catch(e){}
        return req;
      };
    });
    await p.reload({waitUntil:'domcontentloaded'});
    var race=await p.evaluate(function(){
      window.__plenkaResume();          /* оболочка onPageFinished: синк+мерж СРАЗУ */
      return {ready:window.hiddenReady,
              items:window.items.length,
              rows:document.querySelectorAll('#libList .lib-row').length,
              names:[].map.call(document.querySelectorAll('#libList .lib-name'),function(e){return e.textContent})};
    });
    A(race.items>=4,'гонка: синк оболочки пришёл ДО hiddenlist (items='+race.items+')');
    A(race.ready===false,'гонка: hiddenReady ещё false (IDB замедлен)','ready='+race.ready);
    A(race.rows===0,'ГЕЙТ: пока скрытые не прочитаны — список НЕ рендерится (флэша нет)',
      'rows='+race.rows+' ['+race.names.join(',')+']');
    await p.waitForFunction(()=>window.hiddenReady===true,null,{timeout:9000});
    await sleep(500);
    var after=await p.evaluate(function(){
      var names=[].map.call(document.querySelectorAll('#libList .lib-name'),function(e){return e.textContent});
      return {rows:names.length,has:names.indexOf('long30')>=0,
              skel:document.getElementById('libSkel').hidden,
              strip:document.querySelectorAll('#strip .st-card').length};
    });
    A(after.rows===3,'после чтения hiddenlist: ровно 3 публичные карточки','rows='+after.rows);
    A(!after.has,'скрытое видео НЕ показано на старте (приватность цела)');
    A(after.skel,'скелетон убран — список живой');
    await p.evaluate(function(){ try{localStorage.removeItem('__testIdbDelay')}catch(e){} });

    /* ═══ 4. Регресс инвариантов v59 ═══ */
    open('fmp460.mp4');
    var v1=await waitPlaying(8);
    A(!!v1,'fMP4: MSE-мост играет (2.4МБ > гейт 2МБ)',v1?('t='+v1.t.toFixed(1)):'не поднялось');
    var mse=await p.evaluate(()=>({src:(''+(window.video.src||'')).slice(0,5)}));
    A(mse.src==='blob:','fMP4: источник — blob (MSE)','src='+mse.src);
    var cycle=await p.evaluate(async function(){
      window.closePlayerView({});
      await new Promise(r=>setTimeout(r,350));
      document.getElementById('miniClose').click();
      await new Promise(r=>setTimeout(r,200));
      return {cur:window.currentIdx};
    });
    A(cycle.cur===-1,'мини-цикл: панель закрыта, библиотека чистая');
    open('fmp460.mp4');
    var v2=await waitPlaying(8);
    A(!!v2,'МИНИ-ЦИКЛ: следующее видео стартует САМО (инвариант v59)',
      v2?('t='+v2.t.toFixed(1)):'так и не заиграло');
    await p.evaluate(function(){ window.__mockBgSet(true); });
    var tA=await p.evaluate(()=>window.video.currentTime);
    await sleep(2600);
    var tB=await p.evaluate(()=>window.video.currentTime);
    A(tB-tA>1.5,'фон: время едет под скрытой вкладкой','+'+(tB-tA).toFixed(1)+'с');
    await p.evaluate(function(){ window.__mockBgSet(false); });
    await sleep(900);
    var st3=await p.evaluate(()=>({p:window.video.paused,t:window.video.currentTime}));
    A(!st3.p&&st3.t>0.4,'возврат из фона: видео играет без паузы','t='+st3.t.toFixed(1));
    var diag=await p.evaluate(function(){
      var bb=document.getElementById('plenkaDiagBtn'); if(bb)bb.click();
      var pre=document.getElementById('plenkaDiagPre');
      return pre?pre.textContent:'';
    });
    A(/v61/.test(diag),'ДИАГ: версия v61');
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
