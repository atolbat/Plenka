#!/usr/bin/env node
/* Стенд /seek v51 через мок 3.11 — регресс перемотки после патчей v57 */
const {chromium}=require('/home/z/node_modules/playwright');
const {spawn}=require('child_process');
const http=require('http');
(async()=>{
  const mock=spawn('python3',['/home/z/my-project/scripts/mock57.py'],{stdio:['ignore','ignore','ignore']});
  try{
    await new Promise(function(res,rej){ var t0=Date.now();
      (function chk(){ http.get('http://127.0.0.1:8977/list',function(r){ r.resume(); res(); }).on('error',function(){ if(Date.now()-t0>15000)return rej(new Error('no server')); setTimeout(chk,300); }); })();
    });
    const b=await chromium.launch({args:['--autoplay-policy=no-user-gesture-required','--mute-audio']});
    const p=await (await b.newContext({viewport:{width:420,height:900}})).newPage();
    await p.goto('http://127.0.0.1:8977/seek?auto=1&id=1&dur=60',{waitUntil:'domcontentloaded'});
    await p.waitForFunction(()=>window.__seekDone&&window.__seekDone.done,null,{timeout:120000});
    const r=await p.evaluate(()=>window.__seekDone);
    console.log('СТЕНД /seek: PASS='+r.pass+' FAIL='+r.fail);
    (r.tests||[]).forEach(function(t){
      var line=(typeof t==='string')?t:JSON.stringify(t);
      if(/fail/i.test(line))console.log('  [FAIL] '+line);
    });
    await b.close();
    process.exit(r.fail>0?1:0);
  }catch(e){ console.log('fatal: '+e.message); process.exit(1); }
  finally{ mock.kill('SIGKILL'); }
})();
