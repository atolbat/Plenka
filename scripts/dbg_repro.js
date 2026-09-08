const {chromium}=require('/home/z/node_modules/playwright');
const {spawn}=require('child_process');
const http=require('http');
function waitServer(){ return new Promise(function(res,rej){
  var t0=Date.now();
  (function chk(){ http.get('http://127.0.0.1:8978/list',function(r){ r.resume(); res(); })
    .on('error',function(){ if(Date.now()-t0>15000)return rej(new Error('mock not up')); setTimeout(chk,300); }); })();
});}
(async()=>{
  const mock=spawn('python3',['-c',`
import sys; sys.path.insert(0,'/home/z/my-project/scripts')
import mock62
mock62.PORT=8978
mock62.serve()
`],{stdio:['ignore','pipe','pipe']});
  mock.stderr.on('data',d=>console.log('MOCK-ERR:',(''+d).trim()));
  await new Promise(r=>setTimeout(r,800));
  try{
    const b=await chromium.launch({args:['--autoplay-policy=no-user-gesture-required','--mute-audio','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
    const p=await (await b.newContext({viewport:{width:420,height:900}})).newPage();
    p.on('pageerror',e=>console.log('PAGEERR:',e.message));
    p.on('console',m=>console.log('CONS['+m.type()+']:',m.text().slice(0,120)));
    await p.goto('http://127.0.0.1:8978/',{waitUntil:'domcontentloaded'});
    const n=await p.evaluate(()=>({NATV:!!window.NATV,items:(window.items||[]).length,hiddenReady:window.hiddenReady}));
    console.log('STATE:',JSON.stringify(n));
    await b.close();
  }catch(e){console.log('EXC',e.message)}
  finally{mock.kill('SIGKILL')}
})();
