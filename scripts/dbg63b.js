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
  const mock=spawn('python3',['/home/z/my-project/scripts/mock63.py'],{stdio:['ignore','pipe','pipe']});
  try{
    await waitServer();
    const b=await chromium.launch({args:['--autoplay-policy=no-user-gesture-required','--mute-audio','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
    const ctx=await b.newContext({viewport:{width:420,height:900}});
    const p=await ctx.newPage();
    p.on('pageerror',e=>console.log('PAGEERR:',e.message.slice(0,200)));
    await p.goto('http://127.0.0.1:8977/',{waitUntil:'domcontentloaded'});
    await p.waitForFunction(()=>window.items&&window.items.length>=4,null,{timeout:15000});
    await p.evaluate(function(){ window.openItem(window.items.findIndex(function(it){return it.name==='fmp460.mp4'}),{}) });
    await sleep(2500);
    await p.evaluate(function(){
      window.closePlayerView({});
    });
    await sleep(700);
    await p.evaluate(function(){ document.getElementById('miniClose').click(); });
    await sleep(600);
    // init-script: лог вызовов
    await p.addInitScript(function(){
      window.__mergeLog=[];
      var t=Date.now();
      var om=window.natvMerge;
      // natvMerge объявлен позже скрипта? тогда перехват на свойстве
      try{
        var _nm;
        Object.defineProperty(window,'natvMerge',{
          configurable:true,
          get:function(){ return _nm },
          set:function(f){
            _nm=function(a,r){
              window.__mergeLog.push('natvMerge t+'+(Date.now()-t)+'ms items='+((window.items||[]).length)+' arr='+((a||[]).length));
              return f.apply(this,arguments);
            };
          }
        });
      }catch(e){}
      var _ns;
      try{
        Object.defineProperty(window,'nativeSync',{
          configurable:true,
          get:function(){ return _ns },
          set:function(f){
            _ns=function(a){
              window.__mergeLog.push('nativeSync('+(a===true?'true':a===false?'false':a)+') t+'+(Date.now()-t)+'ms REG='+(window.REG_READY===undefined?'?':window.REG_READY)+' items='+((window.items||[]).length));
              return f.apply(this,arguments);
            };
          }
        });
      }catch(e){}
    });
    // замедлить IDB
    await p.evaluate(function(){ try{localStorage.setItem('__testIdbDelay','1')}catch(e){} });
    await p.reload({waitUntil:'domcontentloaded'});
    await p.evaluate(function(){ window.__plenkaResume(); });
    await sleep(3000);
    var log=await p.evaluate(()=>window.__mergeLog);
    console.log('MERGE LOG:'); (log||[]).forEach(function(l){ console.log('  '+l) });
    var st=await p.evaluate(function(){
      var f=null; window.items.forEach(function(x){ if(x&&x.name==='fmp460.mp4')f=x });
      return {pos:f?(f.position||0):0, n:window.items.length, REG:window.REG_READY,
        idbDelay:localStorage.getItem('__testIdbDelay')};
    });
    console.log('STATE:', JSON.stringify(st));
    await b.close();
  }catch(e){ console.log('EXC:',e.message); }
  finally{ mock.kill('SIGKILL'); }
})();
