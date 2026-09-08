#!/usr/bin/env node
/* Смоук v53/3.7: метка медиатеки убрана, #btnFs скрыт в natv, подложка только
   с первым кадром (X-Plenka-FrameT: юниты + живое открытие), спиннер перемотки,
   setPipAuto только для видео, mediaState с w/h, ДИАГ v53 */
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
  const mock=spawn('python3',['/home/z/my-project/scripts/mock53.py'],{stdio:['ignore','pipe','pipe']});
  const mockLog=[];
  mock.stderr.on('data',d=>mockLog.push((''+d).trim()));
  let fails=0;
  function A(cond,name,extra){
    console.log((cond?'[ok] ':'[FAIL] ')+name+(extra?(' — '+extra):''));
    if(!cond)fails++;
  }
  try{
    await waitServer();
    const b=await chromium.launch();
    const p=await b.newPage({viewport:{width:420,height:900}});
    const errs=[];
    p.on('pageerror',e=>errs.push('PAGEERROR: '+e.message));
    p.on('console',m=>{ if(m.type()==='error')errs.push('CONSOLE: '+m.text()); });
    await p.goto('http://127.0.0.1:8977/',{waitUntil:'domcontentloaded'});
    await p.waitForFunction(()=>window.items&&window.items.length>=3,null,{timeout:15000});
    await sleep(1200);

    /* 1. загрузка без ошибок */
    A(errs.length===0,'страница поднялась без JS-ошибок',errs.length?errs[0]:'');
    A(await p.evaluate(()=>document.querySelectorAll('.lib-row').length)>=3,'карточки отрисованы');

    /* 2. метка «медиатека телефона» исчезла с карточек */
    const metaTxt=await p.evaluate(()=>''+(document.querySelector('#lib')||document.body).textContent);
    A(metaTxt.indexOf('медиатека телефона')<0,'на карточках нет «медиатека телефона»');

    /* 3. кнопка фулскрина скрыта в андроид-сборке */
    const fsHidden=await p.evaluate(()=>{
      var b=document.body.classList.contains('natv');
      var el=document.getElementById('btnFs');
      return b&&el&&getComputedStyle(el).display==='none';
    });
    A(fsHidden,'body.natv и #btnFs скрыт (display:none)');

    /* 4. ЮНИТЫ: X-Plenka-FrameT читается и гейтит подложку/постер */
    const units=await p.evaluate(async function(){
      var out={};
      function pms(src){ return new Promise(function(res){ posterFirstMs(src,function(ms){res(ms)}) }) }
      out.first1=await pms('http://127.0.0.1:8977/t/v/1?r=1-0&f=2');
      out.first2=await pms('http://127.0.0.1:8977/t/v/2?r=2-0&f=2');
      out.data=await pms('data:image/jpeg;base64,AAAA');
      var fake2={audio:false,kind:'native',w:640,h:360,thumb:'http://127.0.0.1:8977/t/v/2?r=2-0&f=2'};
      var fake1={audio:false,kind:'native',w:640,h:360,thumb:'http://127.0.0.1:8977/t/v/1?r=1-0&f=2'};
      setVblank(fake2);
      await new Promise(r=>setTimeout(r,700));
      out.vblank2=document.getElementById('vblank').style.backgroundImage;
      setVblank(fake1);
      await new Promise(r=>setTimeout(r,700));
      out.vblank1=document.getElementById('vblank').style.backgroundImage;
      showPoster(null);                       /* честная чёрная маска */
      posterUpgrade(fake2,playToken);         /* дальний кадр — НЕ подставляется */
      await new Promise(r=>setTimeout(r,700));
      out.poster2=document.getElementById('poster').style.getPropertyValue('--pi');
      showPoster(null);
      posterUpgrade(fake1,playToken);         /* первый кадр — подставляется */
      await new Promise(r=>setTimeout(r,700));
      out.poster1=document.getElementById('poster').style.getPropertyValue('--pi');
      return out;
    });
    A(units.first1===0,'юнит: FrameT=0 → «первый кадр»',JSON.stringify(units.first1));
    A(units.first2===3600000,'юнит: FrameT=3600000 → «не первый»',JSON.stringify(units.first2));
    A(units.data===0,'юнит: data: (JS-снимок) → первый кадр');
    A((''+units.vblank2).indexOf('/t/v/2')<0&&(''+units.vblank2)==='','юнит: подложка дальнего кадра — чистый чёрный',JSON.stringify(units.vblank2));
    A((''+units.vblank1).indexOf('/t/v/1')>=0,'юнит: подложка первого кадра — URL подставлен',JSON.stringify(units.vblank1).slice(0,90));
    A((''+units.poster2).indexOf('/t/v/2')<0,'юнит: постер дальнего кадра — остаётся чёрная маска',JSON.stringify(units.poster2));
    A((''+units.poster1).indexOf('/t/v/1')>=0,'юнит: постер первого кадра — подставлен',JSON.stringify(units.poster1).slice(0,90));

    /* 5. живое открытие long30 (дальний кадр в /t/): видео играет, чужой кадр не показан */
    await p.click('.lib-row:has-text("long30")');
    await sleep(3200);
    const st2=await p.evaluate(()=>{
      var v=window.video;
      var pEl=document.getElementById('poster');
      return {
        pi:pEl?pEl.style.getPropertyValue('--pi'):'?',
        ready:v?v.readyState:0,
        t:v?v.currentTime:0,
        paused:v?v.paused:true
      };
    });
    A(st2.ready>=2&&st2.t>0,'long30: видео реально играет',JSON.stringify(st2));
    A((''+st2.pi).indexOf('/t/v/2')<0,'long30: дальний кадр НЕ показан в постере',JSON.stringify(st2.pi).slice(0,90));

    /* 6. спиннер перемотки: seeking → loadDot.on; seeked → снят */
    const spin=await p.evaluate(async function(){
      var v=window.video;
      var dot=document.getElementById('loadDot');
      if(!v||!dot)return 'no-video';
      v.dispatchEvent(new Event('seeking'));
      await new Promise(r=>setTimeout(r,300));
      var on1=dot.classList.contains('on');
      v.dispatchEvent(new Event('seeked'));
      await new Promise(r=>setTimeout(r,60));
      return {on1:on1,on2:dot.classList.contains('on')};
    });
    A(spin&&spin.on1===true&&spin.on2===false,'спиннер перемотки: включился и погас',JSON.stringify(spin));

    /* 7. mediaState с w/h; setPipAuto(true) при видео */
    const ms=await p.evaluate(()=>window.__mockMediaState());
    const msJ=JSON.parse(ms||'null');
    A(msJ&&msJ.w>0&&msJ.h>0,'mediaState: w/h передаются',ms);
    const pip1=JSON.parse(await p.evaluate(()=>window.__mockPipCalls())||'[]');
    A(pip1.indexOf(true)>=0,'setPipAuto(true) при играющем видео',JSON.stringify(pip1));

    /* 8. аудио: setPipAuto → false (фон без окна), keepScreenOn — true */
    await p.evaluate(()=>{ try{ closePlayerView() }catch(e){} });
    await sleep(700);
    await p.click('.lib-row:has-text("song")');
    await sleep(2600);
    const pip2=JSON.parse(await p.evaluate(()=>window.__mockPipCalls())||'[]');
    const kso=JSON.parse(await p.evaluate(()=>window.__mockKsoCalls())||'[]');
    A(pip2[pip2.length-1]===false,'после перехода на аудио setPipAuto(false) — PiP-окна не будет',JSON.stringify(pip2));
    A(kso.indexOf(true)>=0,'keepScreenOn(true) работает и для аудио',JSON.stringify(kso));

    /* 9. ДИАГ: версия v53/3.7 + подсказка /seek */
    const diag=await p.evaluate(async function(){
      var btn=document.getElementById('plenkaDiagBtn');
      if(btn)btn.click();
      await new Promise(r=>setTimeout(r,250));
      var pre=document.getElementById('plenkaDiagPre');
      return pre?(''+pre.textContent):'';
    });
    A(diag.indexOf('страница v53')>=0&&diag.indexOf('оболочка 3.7')>=0,'ДИАГ: версия v53 / 3.7');
    A(diag.indexOf('8977/seek')>=0,'ДИАГ: подсказка про стенд /seek');
    A(diag.indexOf('PLENKA native 3.7')>=0,'ДИАГ: версия моста 3.7');

    /* 10. мост без исключений арности */
    A(errs.every(e=>e.indexOf('Method not found')<0),'мост без «Method not found»');

    console.log('\n=== ИТОГ: '+(fails?('FAIL ×'+fails):'ВСЁ ПРОШЛО')+' ===');
    if(errs.length){ console.log('ошибки страницы:'); errs.slice(0,8).forEach(e=>console.log('  '+e)); }
    await b.close();
  }catch(e){
    console.log('[FAIL] крах теста: '+e.message);
    fails++;
  }
  try{ mock.kill('SIGKILL'); }catch(e){}
  if(mockLog.length) console.log('mock log (хвост): '+mockLog.slice(-4).join(' | '));
  process.exit(fails?1:0);
})();
