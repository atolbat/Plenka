#!/usr/bin/env node
/* Диагностика N3: что в items после гейта, откуда fresh */
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
  let fails=0;
  try{
    await waitServer();
    const b=await chromium.launch({args:['--autoplay-policy=no-user-gesture-required','--mute-audio','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
    const ctx=await b.newContext({viewport:{width:420,height:900}});
    const p=await ctx.newPage();
    p.on('pageerror',e=>console.log('PAGEERR:',e.message.slice(0,150)));
    await p.goto('http://127.0.0.1:8977/',{waitUntil:'domcontentloaded'});
    await p.waitForFunction(()=>window.items&&window.items.length>=4,null,{timeout:15000});
    // посмотреть видео, чтобы записалась позиция
    await p.evaluate(function(){ window.openItem(window.items.findIndex(function(it){return it.name==='fmp460.mp4'}),{}) });
    await sleep(3000);
    await p.evaluate(()=>window.savePos(true));
    var before=await p.evaluate(function(){
      var f=null; window.items.forEach(function(x){ if(x&&x.name==='fmp460.mp4')f=x });
      return {pos:f?(f.position||0):0, items:window.items.map(function(x){return {id:x.id,kind:x.kind,pos:x.position||0,fresh:!!x.fresh}})};
    });
    console.log('BEFORE RELOAD:', JSON.stringify(before));
    // замедлить IDB
    await p.evaluate(function(){ try{localStorage.setItem('__testIdbDelay','1')}catch(e){} });
    await p.addInitScript(function(){
      if(localStorage.getItem('__testIdbDelay')!=='1')return;
      var origOpen=indexedDB.open.bind(indexedDB);
      indexedDB.open=function(name,ver){
        var req=origOpen(name,ver);
        try{
          Object.defineProperty(req,'onsuccess',{
            configurable:true,
            get:function(){ return null },
            set:function(f){
              req.addEventListener('success',function(ev){
                setTimeout(function(){ try{ f.call(req,ev) }catch(e2){} },900);
              },{once:true});
            }
          });
        }catch(e){}
        return req;
      };
    });
    await p.reload({waitUntil:'domcontentloaded'});
    await p.evaluate(function(){ window.__plenkaResume(); });
    await p.waitForFunction(()=>window.hiddenReady===true&&window.REG_READY===true,null,{timeout:12000});
    await sleep(1500);
    var after=await p.evaluate(function(){
      return {items:window.items.map(function(x){return {id:x.id,kind:x.kind,pos:x.position||0,fresh:!!x.fresh,at:x.addedAt}}),
        REG_READY:window.REG_READY, hold:window.natvHold};
    });
    console.log('AFTER GATE:', JSON.stringify(after,null,1));
    // что в IDB реально
    var idb=await p.evaluate(function(){
      return new Promise(function(res){
        try{
          var rq=indexedDB.open('plenka');
          rq.onsuccess=function(){
            var db=rq.result;
            try{
              var tx=db.transaction('items','readonly');
              var st=tx.objectStore('items');
              var g=st.getAll();
              g.onsuccess=function(){ res((g.result||[]).map(function(r){return {id:r.id,pos:r.position||0,fresh:!!r.fresh}})) };
              g.onerror=function(){ res('ERR getAll') };
            }catch(e){ res('ERR tx: '+e.message) }
          };
          rq.onerror=function(){ res('ERR open') };
        }catch(e){ res('ERR: '+e.message) }
      });
    });
    console.log('IDB items:', JSON.stringify(idb));
    await b.close();
  }catch(e){ console.log('EXC:',e.message); fails++; }
  finally{ mock.kill('SIGKILL'); }
})();
