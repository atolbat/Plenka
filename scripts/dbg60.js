#!/usr/bin/env node
/* дебаг v60: почему display уходит в none при живых кадрах */
const {chromium}=require('/home/z/node_modules/playwright');
const {spawn}=require('child_process');
const http=require('http');
function waitServer(){ return new Promise(function(res,rej){
  var t0=Date.now();
  (function chk(){ http.get('http://127.0.0.1:8977/list',function(r){ r.resume(); res(); })
    .on('error',function(){ if(Date.now()-t0>15000)return rej(new Error('no')); setTimeout(chk,300); }); })();
});}
function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }
(async()=>{
  const mock=spawn('python3',['/home/z/my-project/scripts/mock60.py'],{stdio:['ignore','ignore','ignore']});
  try{
    await waitServer();
    const b=await chromium.launch({args:['--autoplay-policy=no-user-gesture-required','--mute-audio','--enable-unsafe-swiftshader','--use-angle=swiftshader']});
    const ctx=await b.newContext({viewport:{width:420,height:900}});
    const p=await ctx.newPage();
    p.on('pageerror',e=>console.log('PAGEERROR:',e.message));
    await p.goto('http://127.0.0.1:8977/',{waitUntil:'domcontentloaded'});
    await p.waitForFunction(()=>window.items&&window.items.length>=3,null,{timeout:15000});
    await p.evaluate(function(n){ window.openItem(window.items.findIndex(function(it){return it.name===n}),{}) },'fmp460.mp4');
    await sleep(3000);
    for(var i=0;i<8;i++){
      var s=await p.evaluate(function(){
        var c=document.getElementById('vgl'),v=window.video;
        return {
          disp:c.style.display||'(нет inline)',
          computed:getComputedStyle(c).display,
          drawn:window.__vgl.drawn,fps:window.__vgl.fps,fw:window.__vgl.fw,fh:window.__vgl.fh,
          cw:c.width,ch:c.height,clientW:c.clientWidth,clientH:c.clientHeight,
          isA:(v===window.videoA),isB:(v===window.videoB),
          parent:(v.parentNode&&v.parentNode.id)||v.parentNode.tagName,
          vis:v.style.visibility,curAudio:(typeof curIsAudio==='function'&&curIsAudio()),
          mirror:(typeof MIRROR!=='undefined'&&MIRROR&&MIRROR.on),
          playerHidden:window.player.hidden,paused:v.paused,rs:v.readyState
        };
      });
      console.log(JSON.stringify(s));
      await sleep(1200);
    }
    /* ДИАГ кнопки */
    var btns=await p.evaluate(function(){
      return [].slice.call(document.querySelectorAll('button')).filter(function(b){
        return (b.textContent||'').indexOf('ДИАГ')>=0;
      }).map(function(b,i){ return {i:i,txt:b.textContent,id:b.id,cls:b.className,visible:!!(b.offsetWidth||b.offsetHeight)} });
    });
    console.log('ДИАГ-кнопки:',JSON.stringify(btns));
    var pre=await p.evaluate(function(){
      var bs=[].slice.call(document.querySelectorAll('button')).filter(function(b){return (b.textContent||'')==='ДИАГ'});
      if(bs.length){bs[bs.length-1].click();}
      var el=document.getElementById('plenkaDiagPre');
      return el?{txt:el.textContent.substring(0,400)}:null;
    });
    console.log('pre:',JSON.stringify(pre));
    await b.close();
  }catch(e){ console.log('ERR',e.message); }
  mock.kill();
})();
