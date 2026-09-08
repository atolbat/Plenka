#!/usr/bin/env node
/* Смоук v63: превью-время при переключении + все фиксы v61 + регресс v59.
   62 «закончили смотреть / свайпнули на соседнее — на контроле мгновение
      висело СТАРОЕ время»: sync-часть openItem (hudPrewind) обязана
      СРАЗУ писать tCur=00:00 (или позицию продолжения, если включено
      «смотреть с момента»), tDur — длительность нового трека, ползунок —
      в стартовую позицию; HUD (rAF) замолкает до склейки (hudHoldId) и
      авторелизится, когда активным стал элемент цели. Проверяем
      СИНХРОННО сразу после switchTo — детерминированно, гонки нет.
   1) БАГ-1 v61 «на старте на мгновение видны все видео, втч приватные»:
      IDB-чтение hiddenlist искусственно замедлено (init-script, 900мс);
      сразу после загрузки зовём __plenkaResume (как оболочка на
      onPageFinished) — синк+мерж успевают ДО hiddenlist. Инвариант:
      пока hiddenReady=false — в списке 0 строк (гейт рендера);
      после — только публичные, скрытой карточки НЕТ.
   2) БАГ-2 v61 «смотрю приватное, свайп назад → публичная папка»:
      скрыли long30 → вошли в скрытый раздел → открыли его →
      __plenkaBack обязан ответить 'nav' (плеер открыт!) и НЕ выходить
      из раздела; history.back() (то, что делает оболочка) закрывает
      плеер в мини — список остаётся СКРЫТЫМ.
   3) БАГ-3 v61 «аудио без обложки — битый плейсхолдер»:
      noart.mp3 (мок: /t/a/4 → 404) — плеер-арт=винил, мини=нота,
      очередь=плейсхолдер; song.mp3 (арт есть) — в мини живая картинка.
   4) Регресс v59: MSE-мост (fMP4 2.4МБ > гейт 2МБ), мини-цикл юзера
      (след. видео стартует САМО), фон (время едет, возврат — играет),
      ДИАГ v63, 0 JS-ошибок. */
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
  const mock=spawn('python3',['/home/z/my-project/scripts/mock63.py'],{stdio:['ignore','pipe','pipe']});
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
    A(errs.length===0,'v63 поднялась без JS-ошибок',errs.length?errs[0]:'');
    A((await p.evaluate(()=>window.PlenkaNative.version())).indexOf('3.16')>=0,'мост представился 3.16');
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
    A(bk==='nav','НАЗАД при открытом плеере: ответ "nav" (закрыть плеер), не "ui"','отв='+bk);
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
    A(race.items===0,'гонка: синк оболочки ПРИДЕРЖАН гейтом (items=0, данные не портятся — 63)','items='+race.items);
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

    /* ═══ 63-N1: PiP из миниплеера — видео, не чёрный (репорт: «pip не совпадают») ═══ */
    open('fmp460.mp4');
    var np0=await waitPlaying(8);
    A(!!np0,'N1: видео играет перед сворачиванием');
    await p.evaluate(()=>window.closePlayerView({}));
    await sleep(900);
    await p.evaluate(()=>window.__pipMode(true));      /* Android: активность вошла в PiP */
    await sleep(350);
    var pip1=await p.evaluate(function(){
      var st=document.getElementById('stage'), pl=document.getElementById('player');
      return {pip:document.body.classList.contains('pip'),
              minist:document.body.classList.contains('minist'),
              playerCSS:pl?getComputedStyle(pl).display:'?',
              stageCSS:st?getComputedStyle(st).display:'?',
              miniShown:pl?(getComputedStyle(document.getElementById('miniBar')).display!=='none'):false,
              hud:pl?(getComputedStyle(document.getElementById('pipHud')).display!=='none'):false,
              playerHiddenAttr:pl?pl.hidden:true};
    });
    A(pip1.pip===true&&pip1.minist===false,'N1: body.pip есть, minist НЕ ставится (63)');
    A(pip1.stageCSS!=='none'&&pip1.playerCSS!=='none','N1: в PiP-окне виден плеер со stage — ВИДЕО',
      'player='+pip1.playerCSS+' stage='+pip1.stageCSS);
    A(pip1.miniShown===false,'N1: мини-панель не торчит в PiP-окне');
    A(pip1.hud===true,'N1: pipHud показан (те же кнопки, что из открытого видео)');
    A(pip1.playerHiddenAttr===true,'N1: логика не тронута — player.hidden как был (после выхода вернёмся в список+мини)');
    await p.evaluate(()=>window.__pipMode(false));
    await sleep(400);
    var pip2=await p.evaluate(()=>({pip:document.body.classList.contains('pip'),
      playerHidden:document.getElementById('player').hidden,
      miniShown:!document.getElementById('miniBar').hidden}));
    A(pip2.pip===false&&pip2.playerHidden===true&&pip2.miniShown===true,
      'N1: после PiP — как до входа: список+мини, видео продолжает играть');

    /* ═══ 63-N2: призрак кадра — vblank чист после крестика мини ═══ */
    await p.evaluate(function(){ document.getElementById('miniClose').click(); });
    await sleep(700);
    var ghost=await p.evaluate(function(){
      return {vblank:(document.getElementById('vblank').style.backgroundImage||''),
              freeze:getComputedStyle(document.getElementById('freeze')).display,
              freezeImg:(document.getElementById('freeze').style.backgroundImage||''),
              miniHidden:document.getElementById('miniBar').hidden,
              vAinStage:document.getElementById('video').parentNode.id,
              vBinStage:document.getElementById('videoB').parentNode.id};
    });
    A(ghost.vblank===''&&ghost.freezeImg==='','N2: крестик мини — vblank/маска ПУСТЫЕ (кадр прошлого видео не останется под следующим)',
      'vblank='+(ghost.vblank?'ЕСТЬ картинка!':'чисто')+' freeze='+ghost.freeze);
    A(ghost.miniHidden===true&&ghost.vAinStage==='stage'&&ghost.vBinStage==='stage',
      'N2: мини закрыта, элементы в stage');
    open('long30.mp4');
    var ng=await waitPlaying(10);
    A(!!ng,'N2: следующее видео поднялось после цикла PiP→мини→закрыть→открыть');
    var ghost2=await p.evaluate(()=>({vblank:(document.getElementById('vblank').style.backgroundImage||''),
      paused:window.video.paused}));
    A(ghost2.paused===false,'N2: играет; подложка не мешает');
    await p.evaluate(function(){ window.closePlayerView({}); });
    await sleep(500);
    await p.evaluate(function(){ document.getElementById('miniClose').click(); });
    await sleep(400);

    /* ═══ 63-N3: fresh-гейт — рестарт не делает все видео «новыми» ═══ */
    var posSaved=await p.evaluate(function(){
      var it=null; window.items.forEach(function(x){ if(x&&x.name==='fmp460.mp4')it=x });
      return {pos:it?(it.position||0):-1, fresh:!!(it&&it.fresh)};
    });
    A(posSaved.pos>2,'N3: позиция просмотра записана (переживёт перезагрузку)','pos='+posSaved.pos.toFixed(1)+'с');
    await p.evaluate(function(){ try{localStorage.setItem('__testIdbDelay','1')}catch(e){} });
    await p.reload({waitUntil:'domcontentloaded'});
    var race63=await p.evaluate(function(){
      window.__plenkaResume();          /* оболочка onPageFinished: синк ДО IDB (замедлен 900мс) */
      return {regReady:window.REG_READY, hold:window.natvHold};
    });
    A(race63.regReady===false&&race63.hold===true,'N3: синк оболочки ПРИДЕРЖАН до чтения реестра (REG_READY-гейт)');
    await p.waitForFunction(()=>window.hiddenReady===true&&window.REG_READY===true,null,{timeout:12000});
    await sleep(1200);
    var fr=await p.evaluate(function(){
      var f=null; window.items.forEach(function(x){ if(x&&x.name==='fmp460.mp4')f=x });
      return {pos:f?(f.position||0):-1, fresh:!!(f&&f.fresh),
              dots:document.querySelectorAll('#libList .lib-row .fresh').length,
              rows:document.querySelectorAll('#libList .lib-row').length};
    });
    A(fr.pos>2,'N3: ПОЗИЦИЯ пережила рестарт с обгоняющим синком (fresh-гейт не дал перезаписать)',
      'pos='+fr.pos.toFixed(1)+'с (v62: 0)');
    A(fr.fresh===false&&fr.dots===0,'N3: точки «новое» нет у просмотренного (и вообще)','dots='+fr.dots);
    A(fr.rows===3,'N3: список отрисован после гейта','rows='+fr.rows);
    await p.evaluate(function(){ try{localStorage.removeItem('__testIdbDelay')}catch(e){} });

    /* ═══ 63-N4: 4K — цель буфера шире (юнит) ═══ */
    var m4=await p.evaluate(function(){
      try{
        return {k60:msebAheadHi({w:3840,h:2160,bps:6250000}),     /* 4К ~50Мбит/с */
                k120:msebAheadHi({w:3840,h:2160,bps:12582912}),    /* 4К ~100Мбит/с */
                p1080:msebAheadHi({w:1920,h:1080,bps:2000000}),    /* 1080p — прежняя формула */
                low:msebAheadHi({w:640,h:360,bps:1500000})};
      }catch(e){ return {err:e.message} }
    });
    A(m4.k60===8,'N4: 4К@6.25МБ/с → запас 8с (было 6)','hi='+m4.k60);
    A(m4.k120===8,'N4: 4К@12МБ/с → floor 8с','hi='+m4.k120);
    A(m4.p1080===9&&m4.low===13,'N4: обычные видео — прежняя формула (9/13с)','1080p='+m4.p1080+' low='+m4.low);

    /* ═══ 63-N5: на линии перемотки НЕТ полос подгрузки ═══ */
    open('fmp460.mp4');
    var nb=await waitPlaying(8);
    A(!!nb,'N5: MSE-видео играет (для проверки полос)');
    await sleep(1800);
    var bars=await p.evaluate(function(){
      return {i:document.getElementById('pBufs').innerHTML.length,
              children:document.getElementById('pBufs').children.length};
    });
    A(bars.i===0&&bars.children===0,'N5: #pBufs пуст — индикации подгрузки НЕТ','children='+bars.children);
    await p.evaluate(function(){ window.closePlayerView({}); });
    await sleep(400);
    await p.evaluate(function(){ document.getElementById('miniClose').click(); });
    await sleep(300);

    /* ═══ 4. Регресс инвариантов v59 ═══ */
    open('fmp460.mp4');
    var v1=await waitPlaying(8);
    A(!!v1,'fMP4: MSE-мост играет (2.4МБ > гейт 2МБ)',v1?('t='+v1.t.toFixed(1)):'не поднялось');
    var mse=await p.evaluate(()=>({src:(''+(window.video.src||'')).slice(0,5)}));
    A(mse.src==='blob:','fMP4: источник — blob (MSE)','src='+mse.src);

    /* ═══ 62: время на панели — ЗАРАНЕЕ позиция нового трека ═══ */
    var sw=await p.evaluate(function(){
      window.S.resume=false;                      /* чистый случай: продолжение выключено */
      var idx=window.items.findIndex(function(i){return i.name==='long30.mp4'});
      window.items[idx].position=0;
      window.switchTo(idx);                       /* свайп: sync-часть openItem уже отработала */
      return {cur:document.getElementById('tCur').textContent,
              dur:document.getElementById('tDur').textContent,
              hold:window.hudHoldId===window.items[idx].id,
              knob:document.getElementById('pKnob').style.left};
    });
    A(sw.cur==='0:00','СВАЙП: tCur сразу 00:00 — не время уходящего видео','tCur='+sw.cur);
    A(sw.dur==='0:30','СВАЙП: tDur сразу длительность нового (0:30)','tDur='+sw.dur);
    A(sw.hold,'СВАЙП: HUD в удержании до склейки (hudHoldId=цель)');
    A(sw.knob==='0%','СВАЙП: ползунок линии сразу в 0%','left='+sw.knob);
    var v3=await waitPlaying(10);
    A(!!v3,'после свайпа: long30 играет',v3?('t='+v3.t.toFixed(1)):'не поднялось');
    await sleep(1200);                            /* время едет — отпускаем порисоваться */
    var rel=await p.evaluate(function(){
      return {hold:window.hudHoldId===null,
              cur:document.getElementById('tCur').textContent,
              dur:document.getElementById('tDur').textContent};
    });
    A(rel.hold,'после склейки: HUD разморожен (авторелиз по vActive._pid)');
    A(/^[0-9]+:[0-9]{2}$/.test(rel.cur)&&rel.cur!=='0:00','после склейки: tCur едет по факту','tCur='+rel.cur);
    A(rel.dur==='0:30','после склейки: tDur нового трека','tDur='+rel.dur);
    var sw2=await p.evaluate(function(){
      window.S.resume=true;                       /* «смотреть с момента» — превью встаёт на позицию */
      var idx=window.items.findIndex(function(i){return i.name==='fmp460.mp4'});
      window.items[idx].position=25;
      window.switchTo(idx);
      return {cur:document.getElementById('tCur').textContent,
              dur:document.getElementById('tDur').textContent,
              hold:window.hudHoldId===window.items[idx].id};
    });
    A(sw2.cur==='0:25','ПРОДОЛЖЕНИЕ: tCur сразу позиция нового (0:25) — не 00:00 и не старое','tCur='+sw2.cur);
    A(sw2.dur==='1:00','ПРОДОЛЖЕНИЕ: tDur нового (1:00)','tDur='+sw2.dur);
    A(sw2.hold,'ПРОДОЛЖЕНИЕ: HUD в удержании');
    var v4=await waitPlaying(12);
    A(!!v4&&Math.abs(v4.t-25)<8,'ПРОДОЛЖЕНИЕ: элемент и правда стартовал с ~0:25','t='+(v4?v4.t.toFixed(1):'-'));
    var rel2=await p.evaluate(()=>window.hudHoldId===null);
    A(rel2,'ПРОДОЛЖЕНИЕ: после склейки HUD разморожен');

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
    A(/v63/.test(diag),'ДИАГ: версия v63');
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
