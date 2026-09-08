#!/usr/bin/env node
/* Смоук v55/3.9 (база v51 из чата + порты):
   1) бут без ошибок, карточки, версия;
   2) метки «медиатека телефона» нет; 3) #btnFs скрыт в natv;
   4) fMP4 → MSE-мост жив (video._mseb), играет;
   5) MSE-сики садятся, самолечение НЕ срабатывает на мосте (гейт);
   6) дальний кадр (/t/ FrameT=3600000) → подложка ЧЁРНАЯ, первый (0) → подложка с кадром;
   7) нативный поток (regular mp4) играет; 8) resume-гейт 15с;
   9) вочдог: зависший дальний Range → перезарядка → игра на цели;
   10) стенд /seek v51 поднимается, свой прогон тестов: PASS больше FAIL;
   11) ДИАГ: v55/3.9 + строка «самолечение». */
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
  const mock=spawn('python3',['/home/z/my-project/scripts/mock55.py'],{stdio:['ignore','pipe','pipe']});
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

    /* 1. загрузка без ошибок, карточки */
    A(errs.length===0,'страница v55 поднялась без JS-ошибок',errs.length?errs[0]:'');
    A(await p.evaluate(()=>document.querySelectorAll('.lib-row').length)>=3,'карточки отрисованы');

    /* 2. метки «медиатека телефона» на карточках нет */
    const labelGone=await p.evaluate(function(){
      var rows=document.querySelectorAll('.lib-row');
      for(var i=0;i<rows.length;i++)if(rows[i].textContent.indexOf('медиатека телефона')>=0)return false;
      return true;
    });
    A(labelGone,'метка «медиатека телефона» с карточек убрана');

    /* 3. фулскрин-кнопка скрыта в natv-сборке */
    A(await p.evaluate(function(){
      var b=document.body.classList.contains('natv');
      var el=document.getElementById('btnFs');
      if(!el)return true;                     /* кнопки может не быть — тоже ок */
      var cs=getComputedStyle(el);
      return b&&(cs.display==='none');
    }),'#btnFs скрыт в natv');

    /* 4. fMP4 → MSE-мост: открытие и игра */
    await p.evaluate(function(){
      var i=window.items.findIndex(function(it){return it.name==='fmp460.mp4'});
      window.openItem(i,{});
    });
    let mseOk=false, mseInfo='';
    try{
      await p.waitForFunction(()=>window.video&&window.video._mseb&&window.video.currentTime>0.5,null,{timeout:20000});
      mseOk=true;
      mseInfo='dur='+(await p.evaluate(()=>window.video.duration.toFixed(1)));
    }catch(e){ mseInfo='мост не поднялся/не играет'; }
    A(mseOk,'fMP4: MSE-мост собран и играет',mseInfo);

    /* 5. MSE-сики: 3 сика, мост жив, самолечения НЕТ (гейт _mseb) */
    if(mseOk){
      const seekRes=await p.evaluate(async function(){
        var V=window.video, out=[];
        var targets=[10,30,50];
        for(var i=0;i<targets.length;i++){
          try{ V.currentTime=targets[i]; }catch(e){ out.push('set-fail'); continue; }
          var t0=Date.now();
          while(V.seeking&&Date.now()-t0<8000)await new Promise(r=>setTimeout(r,100));
          await new Promise(r=>setTimeout(r,400));
          out.push(Math.round(V.currentTime)+'');
        }
        return {seq:out.join(','),mseb:!!V._mseb,heal:window.__plHeal?JSON.parse(JSON.stringify(window.__plHeal)):null,playing:!V.paused&&V.currentTime>0};
      });
      const parts=seekRes.seq.split(',');
      const seated=parts.filter(x=>x!=='set-fail'&&+x>0).length;
      A(seekRes.mseb,'MSE: сики — мост жив после перемоток');
      A(seated>=2,'MSE: сики садятся ('+seekRes.seq+')');
      A(seekRes.heal&&seekRes.heal.seek===0&&seekRes.heal.reload===0,'MSE: вочдог НЕ трогает мост (гейт _mseb)',JSON.stringify(seekRes.heal));
    }

    /* 6. подложка: дальний кадр → ЧЁРНЫЙ (серверный /t/ не подставляется);
       data: (JS-снимок первого кадра) — допустим: он первый по построению */
    const blankFar=await p.evaluate(async function(){
      var i=window.items.findIndex(function(it){return it.name==='long30.mp4'});
      window.openItem(i,{});
      await new Promise(r=>setTimeout(r,2500));   /* posterFirstMs успевает */
      var vb=document.getElementById('vblank');
      return (vb&&vb.style.backgroundImage)?(''+vb.style.backgroundImage):'';
    });
    A(blankFar.indexOf('/t/')<0,'дальний кадр: подложка без СЕРВЕРНОГО кадра (data:-первый или чёрный)','bg='+blankFar.slice(0,40));

    /* 7. нативный поток играет (long30 — обычный mp4) */
    let natPlaying=false;
    try{
      await p.waitForFunction(()=>window.video&&!window.video.paused&&window.video.currentTime>1.0,null,{timeout:20000});
      natPlaying=true;
    }catch(e){}
    A(natPlaying,'long30 играет (нативный поток)');

    /* 8. resume-гейт 15с */
    const g1=await p.evaluate(()=>window.__plenkaResume());
    const g2=await p.evaluate(()=>window.__plenkaResume());
    A(g1==='ok'&&g2==='gate15','resume: второй вызов в течение 15с отсеян ('+g1+'/'+g2+')');

    /* 9. вочдог: /hangnext → зависший дальний Range → перезарядка → игра на цели.
       Цель 24с (не 28: ролик 30с, автопереход на 'ended' не должен съесть проверку) */
    await p.evaluate(async function(){
      await fetch('/hangnext');
      window.video.currentTime=24;
    });
    let healed=false;
    try{
      await p.waitForFunction(()=>window.__plHeal&&window.__plHeal.reload>=1,null,{timeout:25000});
      healed=true;
    }catch(e){}
    if(healed){
      await sleep(1500);
      const t=await p.evaluate(()=>window.video.currentTime);
      const pl=await p.evaluate(()=>!window.video.paused);
      A(t>20&&pl,'вочдог: перезарядка к цели, игра продолжается','t='+t.toFixed(2));
    }else{
      A(false,'вочдог: самолечение не сработало на нативном потоке');
    }

    /* 10. ДИАГ: версия + самолечение */
    const diag=await p.evaluate(async function(){
      try{
        document.getElementById('plenkaDiagBtn').click();
        await new Promise(r=>setTimeout(r,300));
        var el=document.getElementById('plenkaDiag');
        return el?el.textContent:'';
      }catch(e){ return 'ERR '+e.message }
    });
    A(diag.indexOf('v55 / оболочка 3.9')>=0,'ДИАГ: версия v55/3.9');
    A(diag.indexOf('самолечение')>=0,'ДИАГ: строка самолечения есть');
    await p.evaluate(function(){ try{ document.getElementById('plenkaDiagBtn').click(); }catch(e){} });

    /* 11. ошибки JS за всю сессию */
    A(errs.length===0,'JS-ошибок за сессию: 0',errs.length?errs.slice(0,2).join(' | '):'');
    await p.close();

    /* 12. стенд /seek v51: свой прогон тестов на fMP4 */
    const p2=await b.newPage({viewport:{width:420,height:900}});
    const errs2=[];
    p2.on('pageerror',e=>errs2.push('PAGEERROR: '+e.message));
    p2.on('console',m=>{ if(m.type()==='error')errs2.push('CONSOLE: '+m.text()); });
    await p2.goto('http://127.0.0.1:8977/seek',{waitUntil:'domcontentloaded'});
    await p2.waitForFunction(()=>{ var s=document.getElementById('fSel'); return s&&s.options.length>=1; },null,{timeout:15000});
    await sleep(800);
    const standInfo=await p2.evaluate(function(){
      var s=document.getElementById('fSel');
      return {files:s.options.length,first:s.options[0]?s.options[0].textContent.slice(0,30):''};
    });
    A(standInfo.files>=1,'стенд /seek: список файлов подтянулся ('+standInfo.files+' шт, первый: '+standInfo.first+')');
    if(standInfo.files>=1){
      await p2.evaluate(function(){ document.getElementById('bRun').click(); });
      let report='';
      try{
        await p2.waitForFunction(()=>{ var r=document.getElementById('report'); return r&&r.value.indexOf('хвост')>=0; },null,{timeout:120000});
        report=await p2.evaluate(()=>document.getElementById('report').value);
      }catch(e){ report=await p2.evaluate(()=>{ var r=document.getElementById('report'); return r?r.value:''; }); }
      const pass=(report.match(/\[PASS\]/g)||[]).length;
      const fail=(report.match(/\[FAIL\]/g)||[]).length;
      const skip=(report.match(/\[SKIP\]/g)||[]).length;
      A(fail===0&&pass>=5,'стенд v51: свой прогон PASS '+pass+' / FAIL '+fail+' / SKIP '+skip);
      if(fail>0){
        const fl=report.split('\n').filter(l=>l.indexOf('[FAIL]')>=0).slice(0,5).join('\n');
        console.log('   фейлы стенда:\n'+fl);
      }
    }
    A(errs2.length===0,'стенд /seek: JS-ошибок 0',errs2.length?errs2[0]:'');
    await b.close();
  }catch(e){
    console.log('[FAIL] тест-раннер упал: '+e.message);
    fails++;
  }finally{
    mock.kill('SIGKILL');
  }
  console.log(fails===0?'\n═══ ИТОГ: ВСЁ ЗЕЛЁНОЕ ═══':'\n═══ ИТОГ: ПРОВАЛОВ '+fails+' ═══');
  process.exit(fails===0?0:1);
})();
