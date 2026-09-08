#!/usr/bin/env node
/* Смоук v64: два репорта юзера.
   1) «Убери кнопку диагностики»: #plenkaDiagBtn нет (натив-режим мока — раньше
      была ВСЕГДА), окна #plenkaDiag нет, при ошибке JS ничего не всплывает;
      невидимая диагностика жива: __plenkaDiag есть, rec пишет errs, j — журнал.
   2) «Радио-батоны в настройках → выпадающие списки»: все .seg[data-seg] и
      #eqPresets скрыты (.dd-src), перед каждым триггер .dd; тап по .dd
      открывает #segPop (клон .pop, z320 над drawer'ом); выбор щёлкает
      оригинал — S/saveS/applySetting прежним путём; подпись триггера = активная
      опция; закрытие: повторный тап / выбор / тап мимо; смена языка переводит
      подписи; syncSeg обновляет подписи; очередь/субтитры тоже списками;
      эквалайзер: 6 пресетов, «своё»/юзер-пресет в подписи. Регресс: старый
      клик по скрытой кнопке (b.click()) всё ещё применяется; sleep-поп и
      rate-поп живы; 0 JS-ошибок. */
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
  const mock=spawn('python3',['/home/z/my-project/scripts/mock64.py'],{stdio:['ignore','pipe','pipe']});
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
      if(/Failed to load resource.*404/.test(txt))return;   /* 64: медиа-файлы прошлых сессий не сохранились — все 404 ожидаемы */
      errs.push('CONSOLE: '+txt);
    }});
    await p.goto('http://127.0.0.1:8977/',{waitUntil:'domcontentloaded'});
    await p.waitForFunction(()=>window.items&&window.items.length>=4,null,{timeout:15000});
    await sleep(1500);
    A(errs.length===0,'v64 поднялась без JS-ошибок',errs.length?errs[0]:'');
    A((await p.evaluate(()=>window.PlenkaNative.version())).indexOf('3.17')>=0,'мост представился 3.17');

    /* ═══ 1. КНОПКА ДИАГНОСТИКИ УБРАНА ═══ */
    var d1=await p.evaluate(function(){
      return {
        btn:!!document.getElementById('plenkaDiagBtn'),
        ov:!!document.getElementById('plenkaDiag'),
        diag:!!window.__plenkaDiag,
        journal:(window.__plenkaDiag&&window.__plenkaDiag.journal.length>0),
        natv:document.body.classList.contains('natv')
      };
    });
    A(d1.natv,'натив-режим мока (как в APK)');
    A(!d1.btn,'кнопки «ДИАГ» нет (натив — раньше висела всегда)');
    A(!d1.ov,'окна диагностики нет');
    A(d1.diag&&d1.journal,'невидимая диагностика жива: метки/журнал пишутся');

    /* ошибка JS ничего не всплывает, но в errs уходит */
    await p.evaluate(function(){ window.dispatchEvent(new ErrorEvent('error',{message:'тprobe v64'})) });
    await sleep(300);
    var d2=await p.evaluate(function(){
      return {n:window.__plenkaDiag.errs.length,
              btn:!!document.getElementById('plenkaDiagBtn'),
              rep:window.__mockReported().indexOf('тprobe v64')>=0};
    });
    A(d2.n>0&&d2.rep,'ошибка поймана и ушла в report() (logcat)','errs='+d2.n+' rep='+d2.rep);
    A(!d2.btn,'ошибка НЕ вернула кнопку ДИАГ на экран');

    /* ═══ 2. НАСТРОЙКИ: СПИСКИ ВМЕСТО РАДИО ═══ */
    await p.evaluate(function(){ $('#btnSettings')&&$('#btnSettings').click() });
    await sleep(500);
    var s1=await p.evaluate(function(){
      var segs=$$('.seg[data-seg]');
      var eq=document.getElementById('eqPresets');
      return {
        nSeg:segs.length,
        nHidden:segs.filter(function(s){return s.classList.contains('dd-src')}).length,
        eqHidden:eq?eq.classList.contains('dd-src'):null,
        nDD:$$('.dd').length,
        labels:$$('.dd').map(function(d){return d.querySelector('.ddv').textContent}),
        visSegs:segs.filter(function(s){return !s.classList.contains('dd-src')&&s.offsetParent!==null}).length,
        stepLbl:(function(){var d=$('.dd[data-dd],.dd');return 0})()||null
      };
    });
    A(s1.nSeg===13,'сегментов-настроек 13 (настройки+очередь+сабы)','n='+s1.nSeg);
    A(s1.nHidden===13&&s1.eqHidden===true,'все .seg скрыты (.dd-src), вкл. эквалайзер');
    A(s1.nDD===14,'триггеров .dd — 14 (13 сегментов + eq)','n='+s1.nDD);
    A(s1.visSegs===0,'радио-кнопок на экране не осталось');
    A(s1.labels.every(function(x){return x&&x!=='…'}),'у всех триггеров есть подпись',
      s1.labels.filter(function(x){return !x||x==='…'}).length+' пустых');

    /* тап по триггеру шага перемотки → список открыт, 4 опции, активная 10С */
    var stepIdx=await p.evaluate(function(){
      var dds=$$('.dd');
      for(var i=0;i<dds.length;i++){ if(dds[i].nextElementSibling&&dds[i].nextElementSibling.getAttribute('data-seg')==='step')return i }
      return -1;
    });
    A(stepIdx>=0,'триггер «шаг перемотки» найден');
    await p.evaluate(function(i){ $$('.dd')[i].click() },stepIdx);
    await sleep(250);
    var pop1=await p.evaluate(function(){
      var p=document.getElementById('segPop');
      var r=p.getBoundingClientRect();
      var cx=r.left+r.width/2, cy=r.top+Math.min(20,r.height/2);
      var el=document.elementFromPoint(cx,cy);
      return {open:p?p.classList.contains('open'):false,
              n:p?p.querySelectorAll('button').length:0,
              on:p?(p.querySelector('button.on')||{}).textContent:null,
              z:p?getComputedStyle(p).zIndex:null,
              over:(el===p||(el&&p.contains(el)))};
    });
    A(pop1.open&&pop1.n===4,'список шага открыт: 4 опции (5/10/15/30с)','n='+pop1.n);
    A(pop1.on==='10с','активная опция — 10с (дефолт)','on='+pop1.on);
    A(pop1.z==='320','поп поверх drawer (z320)');
    A(pop1.over,'поп реально отрисован (хит-тест по центру)');

    /* выбор 30с → S.step=30, подпись триггера 30С, список закрылся */
    await p.evaluate(function(){ var o=document.querySelector('#segPop button[data-v="30"]'); o&&o.click() });
    await sleep(300);
    var st1=await p.evaluate(function(i){
      var dd=$$('.dd')[i];
      return {step:window.S.step, lbl:dd.querySelector('.ddv').textContent,
              open:document.getElementById('segPop').classList.contains('open'),
              segOn:(function(){var b=document.querySelector('.seg[data-seg="step"] button.on');return b?b.getAttribute('data-v'):null})()};
    },stepIdx);
    A(st1.step===30&&st1.segOn==='30','выбор применён: S.step=30, скрытый .seg обновлён');
    A(st1.lbl==='30с','подпись триггера = «30с»',st1.lbl);
    A(!st1.open,'список закрылся после выбора');

    /* повторный тап — открыл; тап по неактивной метке — закрыл, drawer остался */
    await p.evaluate(function(i){ $$('.dd')[i].click() },stepIdx);
    await sleep(200);
    var lblXY=await p.evaluate(function(){
      var l=document.querySelector('#settingsDrawer .row label');
      var r=l.getBoundingClientRect();
      return {x:r.left+r.width/2,y:r.top+r.height/2, drawer:document.getElementById('settingsDrawer').classList.contains('open')};
    });
    await p.mouse.click(lblXY.x,lblXY.y);
    await sleep(200);
    var st2=await p.evaluate(function(){ return {open:document.getElementById('segPop').classList.contains('open'),
      drawer:document.getElementById('settingsDrawer').classList.contains('open')} });
    A(!st2.open,'тап мимо списка закрывает его (drawer цел)','open='+st2.open+' drawer='+st2.drawer);
    A(st2.drawer,'тап мимо НЕ закрыл панель настроек');

    /* эквалайзер: 6 пресетов, выбор «бас» */
    var eqIdx=await p.evaluate(function(){
      var dds=$$('.dd');
      for(var i=0;i<dds.length;i++){ var n=dds[i].nextElementSibling; if(n&&n.id==='eqPresets')return i }
      return -1;
    });
    A(eqIdx>=0,'триггер пресетов эквалайзера найден');
    var eq1=await p.evaluate(function(i){ return $$('.dd')[i].querySelector('.ddv').textContent },eqIdx);
    A(eq1==='ровно'||eq1==='flat','подпись эквалайзера — активный пресет на ЯЗЫКЕ СТРАНИЦЫ (без рус. остатка)',eq1);
    await p.evaluate(function(i){ var d=$$('.dd')[i]; d.scrollIntoView({block:'center'}); d.click() },eqIdx);
    await sleep(250);
    var eqPop=await p.evaluate(function(){
      var p=document.getElementById('segPop');
      return {open:p.classList.contains('open'),n:p.querySelectorAll('button').length,
              on:(p.querySelector('button.on')||{}).textContent,
              texts:[].map.call(p.querySelectorAll('button'),function(b){return b.textContent}).join('|'),
              lang:window.LANG, nav:navigator.language, drawer:document.getElementById('settingsDrawer').classList.contains('open')};
    });
    A(eqPop.open&&eqPop.n===6&&(eqPop.lang==='ru'?eqPop.on==='ровно':eqPop.on==='flat'),'список пресетов: 6 опций, активная на языке страницы',
      'on='+eqPop.on+' lang='+eqPop.lang+' texts='+eqPop.texts);
    await p.evaluate(function(){ var o=document.querySelector('#segPop button[data-v="bass"]'); o&&o.click() });
    await sleep(300);
    var eq2=await p.evaluate(function(i){
      return {p:window.S.eqPreset, lbl:$$('.dd')[i].querySelector('.ddv').textContent};
    },eqIdx);
    A(eq2.p==='bass'&&(eq2.lbl==='бас'||eq2.lbl==='bass'),'пресет «бас» применён и отражён в подписи',eq2.p+'/'+eq2.lbl);

    /* скрытый клик по оригиналу по-прежнему работает (регресс логики) */
    var st3=await p.evaluate(function(){
      document.querySelector('.seg[data-seg="step"] button[data-v="15"]').click();
      return window.S.step;
    });
    A(st3===15,'скрытая кнопка .seg кликабельна программно (S.step=15)');

    /* смена языка: подписи триггеров переводятся */
    await p.evaluate(function(){ window.S.lang='en'; window.applySetting('lang'); window.saveS() });
    await sleep(400);
    var lang1=await p.evaluate(function(){
      var dds=$$('.dd');
      var out={};
      dds.forEach(function(d){ var n=d.nextElementSibling; if(n&&n.getAttribute)out[n.getAttribute('data-seg')||n.id]=d.querySelector('.ddv').textContent });
      return out;
    });
    A(lang1.step==='15с','после смены языка подпись шага — «15с» (без перевода, как и раньше)',lang1.step);
    A(lang1.loop==='off','повтор — off',lang1.loop);
    A(lang1.eqPresets==='bass','эквалайзер — bass (выбранный ранее пресет, по-английски)',lang1.eqPresets);
    await p.evaluate(function(){ window.S.lang='ru'; window.applySetting('lang'); window.saveS() });
    await sleep(300);

    /* очередь и субтитры — тоже списками (drawer'ы вне настроек) */
    await p.evaluate(function(){ document.getElementById('settingsDrawer').classList.remove('open');
      var q=document.getElementById('queueDrawer'); q.classList.add('open'); });
    await sleep(300);
    var q1=await p.evaluate(function(){
      var seg=document.querySelector('#queueDrawer .seg[data-seg="loop"]');
      return {dd:!!(seg&&seg._dd), hidden:seg?seg.classList.contains('dd-src'):false,
              lbl:seg&&seg._dd?seg._dd.querySelector('.ddv').textContent:null};
    });
    A(q1.dd&&q1.hidden&&q1.lbl==='выкл','очередь: повтор — выпадающий список («выкл»)',q1.lbl);
    await p.evaluate(function(){ document.getElementById('queueDrawer').classList.remove('open');
      document.getElementById('subsDrawer').classList.add('open'); });
    await sleep(300);
    var sub1=await p.evaluate(function(){
      var seg=document.querySelector('#subsDrawer .seg[data-seg="subsColor"]');
      return {dd:!!(seg&&seg._dd), lbl:seg&&seg._dd?seg._dd.querySelector('.ddv').textContent:null};
    });
    A(sub1.dd&&sub1.lbl==='белый','субтитры: цвет — выпадающий список («белый»)',sub1.lbl);

    /* старые поповеры не сломаны: rate-поп открывается и гасит сег-поп */
    await p.evaluate(function(){ document.getElementById('subsDrawer').classList.remove('open') });
    await p.evaluate(function(i){ $$('.dd')[i].click() },stepIdx);
    await sleep(200);
    await p.evaluate(function(){ var r=document.getElementById('btnRate'); if(r)r.click() });
    await sleep(250);
    var pops=await p.evaluate(function(){
      var sp=document.getElementById('segPop'), rp=document.getElementById('ratePop');
      return {seg:sp.classList.contains('open'), rate:rp.classList.contains('open'),
              ddOpen:!!document.querySelector('.dd.pop-open')};
    });
    A(!pops.seg&&!pops.ddOpen,'rate-поп закрыл список и снял «открытость» триггера');
    A(pops.rate,'rate-поп сам открылся');

    /* фильтр библиотеки (data-fseg) НЕ тронут — чипы на месте */
    var f1=await p.evaluate(function(){
      var segs=$$('.seg[data-fseg]');
      var fmt=document.getElementById('fmtSeg');
      return {n:segs.length, hidden:segs.filter(function(s){return s.classList.contains('dd-src')}).length,
              fmtTouched:fmt?fmt.classList.contains('dd-src'):null};
    });
    A(f1.n===2&&f1.hidden===0&&f1.f1!==false,'фильтр библиотеки не тронут: 2 сегмента-чипа без .dd');
    A(f1.fmtTouched===false,'#fmtSeg (форматы) остался чипами, без списка');

    A(errs.length===0,'финал: 0 JS-ошибок',errs.length?errs.join(' | ').slice(0,200):'');
    await b.close();
  }catch(e){
    console.log('[FAIL] исключение: '+e.message);
    fails++;
    if(mockLog.length)console.log('mock tail: '+mockLog.slice(-6).join(' / '));
  }
  mock.kill();
  console.log(fails?('\n★ ПРОВАЛОВ: '+fails):'\n★ v64: все проверки прошли');
  process.exit(fails?1:0);
})();
