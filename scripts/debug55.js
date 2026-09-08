#!/usr/bin/env node
/* Дебаг вочдога на v55: что происходит после зависшего сика на long30. */
const {chromium}=require('/home/z/node_modules/playwright');
const {spawn}=require('child_process');
const http=require('http');
function waitServer(){
  return new Promise(function(res,rej){
    var t0=Date.now();
    (function chk(){
      http.get('http://127.0.0.1:8977/list',function(r){ r.resume(); res(); })
        .on('error',function(){ if(Date.now()-t0>15000)return rej(new Error('up?')); setTimeout(chk,300); });
    })();
  });
}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  const mock=spawn('python3',['/home/z/my-project/scripts/mock55.py'],{stdio:['ignore','pipe','pipe']});
  mock.stderr.on('data',d=>(''+d).trim()&&process.stderr.write('[mock] '+(''+d).trim()+'\n'));
  try{
    await waitServer();
    const b=await chromium.launch({args:['--autoplay-policy=no-user-gesture-required','--mute-audio']});
    const p=await b.newPage({viewport:{width:420,height:900}});
    p.on('pageerror',e=>console.log('PAGEERROR: '+e.message));
    await p.goto('http://127.0.0.1:8977/',{waitUntil:'domcontentloaded'});
    await p.waitForFunction(()=>window.items&&window.items.length>=3,null,{timeout:15000});
    await sleep(1200);
    await p.evaluate(function(){
      var i=window.items.findIndex(function(it){return it.name==='long30.mp4'});
      window.openItem(i,{});
    });
    await p.waitForFunction(()=>window.video&&!window.video.paused&&window.video.currentTime>1.0,null,{timeout:20000});
    console.log('long30 играет, t=',await p.evaluate(()=>window.video.currentTime.toFixed(2)),
      ' _mseb=',await p.evaluate(()=>!!window.video._mseb));
    await p.evaluate(async function(){ await fetch('/hangnext'); window.video.currentTime=28; });
    for(let i=0;i<10;i++){
      await sleep(2000);
      const st=await p.evaluate(function(){
        var V=window.video;
        return {t:V.currentTime.toFixed(2),paused:V.paused,seeking:V.seeking,rs:V.readyState,
                mseb:!!V._mseb,heal:window.__plHeal?JSON.parse(JSON.stringify(window.__plHeal)):null,
                src:(V.currentSrc||V.src||'').slice(-24)};
      });
      console.log('+'+((i+1)*2)+'s',JSON.stringify(st));
      if(st.heal&&st.heal.reload>=1&&i>=1) break;
    }
    const jr=await p.evaluate(function(){
      try{ return (window.__plenkaJ&&window.__plenkaJ()).slice(-40).join('\n'); }catch(e){ return 'journal err: '+e.message }
    });
    console.log('--- журнал (последние 40) ---');
    console.log(jr);
    await b.close();
  }catch(e){ console.log('ERR: '+e.message); }
  finally{ mock.kill('SIGKILL'); }
})();
