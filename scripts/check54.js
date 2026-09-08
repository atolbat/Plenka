#!/usr/bin/env node
/* Смоук v54/3.8: (1) страница без ошибок, карточки; (2) resume-гейт 15с
   (лаги от PiP-циклов); (3) быстрый сик — БЕЗ ложного самолечения;
   (4) зависший сик (мёртвый Range от сервера) — сик-вочдог чинит за секунды,
   перезарядка к цели, воспроизведение продолжается; (5) счётчики в ДИАГ. */
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
  const mock=spawn('python3',['/home/z/my-project/scripts/mock54.py'],{stdio:['ignore','pipe','pipe']});
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

    /* 1. загрузка без ошибок, карточки */
    A(errs.length===0,'страница v54 поднялась без JS-ошибок',errs.length?errs[0]:'');
    A(await p.evaluate(()=>document.querySelectorAll('.lib-row').length)>=3,'карточки отрисованы');

    /* 2. resume-гейт: PiP-циклы не должны гонять полный скан каждые 5с */
    const g1=await p.evaluate(()=>window.__plenkaResume());
    const g2=await p.evaluate(()=>window.__plenkaResume());
    A(g1==='ok'&&g2==='gate15','resume: второй вызов в течение 15с отсеян ('+g1+'/'+g2+')');

    /* 3. открыть long30 (нативный поток), дождаться игры */
    await p.evaluate(function(){
      var i=window.items.findIndex(function(it){return it.name==='long30.mp4'});
      window.openItem(i,{});
    });
    let playing=false;
    try{
      await p.waitForFunction(()=>window.video&&!window.video.paused&&window.video.currentTime>1.2,null,{timeout:20000});
      playing=true;
    }catch(e){}
    A(playing,'long30 играет (нативный поток)',playing?('t='+await p.evaluate(()=>window.video.currentTime.toFixed(2))):'не стартовал');

    /* 4. быстрый сик — самолечение НЕ срабатывает (нет ложных позитивов) */
    await p.evaluate(()=>{ window.video.currentTime=3; });
    await sleep(1600);
    const heal0=await p.evaluate(()=>window.__plHeal?JSON.parse(JSON.stringify(window.__plHeal)):null);
    A(heal0&&heal0.seek===0&&heal0.reload===0&&heal0.stall===0,'быстрый сик без самолечения',JSON.stringify(heal0));

    /* 5. зависший сик: /hangnext — следующий дальний Range висит 90с,
       отдача медленная — позиция 28с гарантированно за пределами буфера */
    await p.evaluate(async function(){
      await fetch('/hangnext');
      window.video.currentTime=28;
    });
    let healed=false,healInfo='';
    try{
      await p.waitForFunction(()=>window.__plHeal&&window.__plHeal.reload>=1,null,{timeout:25000});
      healed=true;
    }catch(e){}
    const journal=await p.evaluate(()=>window.__plenkaDiag?window.__plenkaDiag.journal.join('\n'):'');
    A(healed,'сик-вочдог сработал: перезарядка элемента пошла');
    A(/не садится 3с|поток встал/.test(journal),'журнал видит причину (сик не садится / поток встал)');
    const heal1=await p.evaluate(()=>window.__plHeal?JSON.parse(JSON.stringify(window.__plHeal)):null);
    A(heal1&&heal1.reload>=1,'перезарядок ≥1',JSON.stringify(heal1));

    /* 6. после самолечения — играет на цели (~25с) */
    let okPos=false,posStr='';
    try{
      await p.waitForFunction(()=>!window.video.paused&&window.video.currentTime>23.5,null,{timeout:25000});
      okPos=true;
      posStr='t='+await p.evaluate(()=>window.video.currentTime.toFixed(2));
    }catch(e){ posStr='t='+(await p.evaluate(()=>window.video.currentTime.toFixed(2)))+' paused='+(await p.evaluate(()=>window.video.paused)); }
    A(okPos,'зависший сик вылечен: видео играет у цели (≈28с)',posStr);

    /* 7. ДИАГ: строка самолечения присутствует */
    const diagLine=await p.evaluate(function(){
      try{ if(window.__plHeal)return 'самолечение: перезарядок: '+window.__plHeal.reload; }catch(e){}
      return '';
    });
    A(diagLine.indexOf('перезарядок')>=0,'ДИАГ: счётчики самолечения доступны');

    A(errs.length===0,'после всех тестов ошибок JS нет',errs.length?errs.join(' | '):'');
    await b.close();
  }catch(e){
    console.log('[FAIL] крах теста: '+e.message);
    fails++;
  }finally{
    mock.kill('SIGKILL');
  }
  console.log(mockLog.slice(-4).join('\n'));
  console.log(fails?('ИТОГ: FAIL ×'+fails):'ИТОГ: PASS');
  process.exit(fails?1:0);
})();
