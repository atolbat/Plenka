#!/usr/bin/env node
/* Отладка: почему аудио не поднялось после цикла реестра */
const {chromium}=require('/home/z/node_modules/playwright');
const {spawn}=require('child_process');
const http=require('http');
function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }
(async()=>{
  const mock=spawn('python3',['/home/z/my-project/scripts/mock57.py'],{stdio:['ignore','pipe','pipe']});
  try{
    await new Promise(function(res,rej){ var t0=Date.now();
      (function chk(){ http.get('http://127.0.0.1:8977/list',function(r){ r.resume(); res(); }).on('error',function(){ if(Date.now()-t0>15000)return rej(new Error('no server')); setTimeout(chk,300); }); })();
    });
    const b=await chromium.launch({args:['--autoplay-policy=no-user-gesture-required','--mute-audio']});
    const p=await (await b.newContext({viewport:{width:420,height:900}})).newPage();
    const errs=[];
    p.on('pageerror',e=>errs.push('PAGEERROR: '+e.message));
    p.on('console',m=>{ if(m.type()==='error')errs.push('CONSOLE: '+m.text()); });
    await p.goto('http://127.0.0.1:8977/',{waitUntil:'domcontentloaded'});
    await p.waitForFunction(()=>window.items&&window.items.length>=3,null,{timeout:15000});
    await sleep(1000);

    /* открыть аудио сразу — работает? (как в check56) */
    await p.evaluate(function(){ var i=window.items.findIndex(function(it){return it.name==='song.mp3'}); window.openItem(i,{}); });
    let ok1=false; try{ await p.waitForFunction(()=>window.video&&window.video.src&&!window.video.paused&&window.video.currentTime>0.3,null,{timeout:8000}); ok1=true; }catch(e){}
    console.log('аудио сразу после старта:', ok1?'ИГРАЕТ':'не играет');
    await p.evaluate(function(){ try{ document.getElementById('btnBack').click(); }catch(e){} });
    await sleep(500);

    /* удалить песню крестиком + вернуть — и снова открыть */
    await p.evaluate(function(){
      var rows=Array.prototype.slice.call(document.querySelectorAll('.lib-row'));
      var row=rows.find(function(r){ return (r.querySelector('.lib-name')||{}).textContent==='song' });
      if(row)row.querySelector('.rm').click();
    });
    await sleep(700);
    await p.evaluate(async function(){
      document.getElementById('btnLibSettings').click();
      document.getElementById('btnRmShow').click();
      var rows=document.querySelectorAll('#rmSheet [data-rmid]');
      if(rows.length)rows[0].click();
      await new Promise(r=>setTimeout(r,1200));
    });
    const st1=await p.evaluate(function(){
      return {n:window.items.length, hasSong:window.items.some(function(it){return it.name==='song.mp3'}),
              libHidden:document.getElementById('lib').hidden, playerHidden:document.getElementById('player').hidden};
    });
    console.log('после возврата:', JSON.stringify(st1));
    /* выходим из настроек */
    await p.evaluate(function(){ try{ document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true})); }catch(e){} });
    await sleep(300);

    await p.evaluate(function(){ var i=window.items.findIndex(function(it){return it.name==='song.mp3'}); console.log('idx='+i); window.openItem(i,{}); });
    let ok2=false; try{ await p.waitForFunction(()=>window.video&&window.video.src&&!window.video.paused&&window.video.currentTime>0.3,null,{timeout:8000}); ok2=true; }catch(e){}
    const st2=await p.evaluate(function(){
      var V=window.video;
      return {src:(V.src||'').slice(0,40), paused:V.paused, ct:V.currentTime, ready:V.readyState, err:(V.error&&V.error.code)||null, playerHidden:document.getElementById('player').hidden};
    });
    console.log('аудио после цикла реестра:', ok2?'ИГРАЕТ':'не играет', JSON.stringify(st2));
    if(errs.length)console.log('ошибки:', errs.slice(0,5));
    await b.close();
  }catch(e){ console.log('fatal', e.message); }
  finally{ mock.kill('SIGKILL'); }
})();
