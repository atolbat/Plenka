#!/usr/bin/env node
/* Смоук v52: лаборатория /seek в headless Chromium — мок 3.5 (Range, /list, /t/404) */
const {chromium}=require('/home/z/node_modules/playwright');
const {spawn}=require('child_process');
const http=require('http');
const fs=require('fs');

function waitServer(){
  return new Promise(function(res,rej){
    var t0=Date.now();
    (function chk(){
      http.get('http://127.0.0.1:8977/list',function(r){
        r.resume(); res();
      }).on('error',function(){
        if(Date.now()-t0>15000)return rej(new Error('mock server not up'));
        setTimeout(chk,300);
      });
    })();
  });
}
function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }

(async()=>{
  const mock=spawn('python3',['/home/z/my-project/scripts/mock52.py'],{stdio:['ignore','pipe','pipe']});
  const mockLog=[];
  mock.stderr.on('data',d=>mockLog.push((''+d).trim()));
  let ok=true;
  try{
    await waitServer();
    const b=await chromium.launch();
    const p=await b.newPage({viewport:{width:420,height:900}});
    const errs=[];
    p.on('pageerror',e=>errs.push('PAGEERROR: '+e.message));
    p.on('console',m=>{ if(m.type()==='error')errs.push('CONSOLE: '+m.text()); });
    await p.goto('http://127.0.0.1:8977/seek',{waitUntil:'domcontentloaded'});
    await p.waitForSelector('#labRoot',{timeout:8000});
    await p.waitForFunction(()=>(''+document.getElementById('labLog').textContent).includes('лаборатория поднята'),null,{timeout:8000});
    console.log('[ok] лаборатория поднята');
    await p.waitForFunction(()=>document.getElementById('labList').options.length>0,null,{timeout:8000});
    const opts=await p.evaluate(()=>Array.from(document.getElementById('labList').options).map(o=>o.textContent));
    console.log('[ok] /list → select:',JSON.stringify(opts));
    // 1) открытие 4K-файла
    await p.fill('#labId','1000008396');
    await p.click('#labOpenBtn');
    await p.waitForFunction(()=>{var e=document.getElementById('labRep');return e&&!e.hidden&&e.textContent.includes('итог:');},null,{timeout:60000});
    var rep1=await p.textContent('#labRep');
    console.log('=== ОТКРЫТИЕ 4K ===');
    console.log(rep1.split('\n\n— журнал')[0]);
    // 2) полный прогон на 30с ролике
    await p.fill('#labId','2');
    await p.click('#labRun');
    await p.waitForFunction(()=>!document.getElementById('labRun').disabled,null,{timeout:200000});
    var rep2=await p.textContent('#labRep');
    console.log('=== ПОЛНЫЙ ПРОГОН (30с ролик) ===');
    console.log(rep2.split('\n\n— журнал')[0]);
    // 3) полный прогон на 4K (информативно: headless = софт-декод без GPU)
    await p.fill('#labId','1000008396');
    await p.click('#labRun');
    await p.waitForFunction(()=>!document.getElementById('labRun').disabled,null,{timeout:200000});
    var rep3=await p.textContent('#labRep');
    console.log('=== ПОЛНЫЙ ПРОГОН (4K, headless-декод — информативно) ===');
    console.log(rep3.split('\n\n— журнал')[0]);
    await p.screenshot({path:'/home/z/my-project/scripts/v52_lab.png'});
    console.log('[shot] scripts/v52_lab.png');
    if(errs.length){ ok=false; console.log('ОШИБКИ СТРАНИЦЫ ('+errs.length+'):'); errs.slice(0,20).forEach(e=>console.log('  '+e)); }
    else console.log('[ok] ошибок страницы 0');
    fs.writeFileSync('/home/z/my-project/scripts/mock52_result.log',
      '=== ОТКРЫТИЕ 4K ===\n'+rep1+'\n\n=== 30s ===\n'+rep2+'\n\n=== 4K ===\n'+rep3+
      '\n\nERRS:\n'+errs.join('\n')+'\nMOCKLOG:\n'+mockLog.slice(-60).join('\n'));
    await b.close();
  }catch(e){
    ok=false; console.error('FAIL:',e.message);
  }finally{
    mock.kill('SIGKILL');
  }
  process.exit(ok?0:1);
})();
