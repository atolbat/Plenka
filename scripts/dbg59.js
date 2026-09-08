#!/usr/bin/env node
/* Отладка 4а: почему wrapper-play + мгновенная пауза не даёт AbortError-лог */
const {chromium}=require('/home/z/node_modules/playwright');
const {spawn}=require('child_process');
const http=require('http');
function waitServer(){ return new Promise(function(res,rej){
  var t0=Date.now();
  (function chk(){ http.get('http://127.0.0.1:8977/list',function(r){ r.resume(); res(); })
    .on('error',function(){ if(Date.now()-t0>15000)return rej(new Error('no')); setTimeout(chk,300); }); })();
});}
(async()=>{
  const mock=spawn('python3',['/home/z/my-project/scripts/mock59.py'],{stdio:['ignore','ignore','ignore']});
  try{
    await waitServer();
    const b=await chromium.launch({args:['--autoplay-policy=no-user-gesture-required','--mute-audio']});
    const p=await (await b.newContext({viewport:{width:420,height:900}})).newPage();
    await p.goto('http://127.0.0.1:8977/',{waitUntil:'domcontentloaded'});
    await p.waitForFunction(()=>window.items&&window.items.length>=3,null,{timeout:15000});
    await p.evaluate(function(){ window.openItem(0,{}) });   /* fmp460 */
    await new Promise(r=>setTimeout(r,2500));
    var out=await p.evaluate(async function(){
      var V=window.video, log=[];
      /* 1) прямой промис */
      try{ V.pause() }catch(e){}
      await new Promise(r=>setTimeout(r,150));
      var pr=V.play();
      log.push('тип промиса: '+(pr&&typeof pr.then));
      try{ V.pause() }catch(e){}
      var r1=await pr.then(function(){ return 'RESOLVED' },function(e){ return 'REJECT '+e.name });
      log.push('прямой play+pause: '+r1);
      /* 2) обёртка window.play() */
      try{ V.pause() }catch(e){}
      await new Promise(r=>setTimeout(r,150));
      window.play();
      try{ V.pause() }catch(e){}
      await new Promise(r=>setTimeout(r,400));
      var j=window.__plenkaDiag.journal;
      log.push('журнал хвост: '+j.slice(-4).join(' | '));
      return log;
    });
    console.log(out.join('\n'));
    await b.close();
  }catch(e){ console.log('FATAL '+e.message); }
  mock.kill(); process.exit(0);
})();
