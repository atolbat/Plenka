#!/bin/bash
# Смоук обычного режима v52 (без /seek): библиотека поднимается, ошибок JS нет
set -u
cd /home/z/my-project
python3 scripts/mock52.py >/tmp/mock52.out 2>&1 &
MOCK=$!
sleep 2
node -e "
const {chromium}=require('/home/z/node_modules/playwright');
(async()=>{
  const b=await chromium.launch();
  const p=await b.newPage({viewport:{width:420,height:900}});
  const errs=[];
  p.on('pageerror',e=>errs.push('PAGEERROR: '+e.message));
  p.on('console',m=>{ if(m.type()==='error')errs.push('CONSOLE: '+m.text()); });
  await p.goto('http://127.0.0.1:8977/',{waitUntil:'domcontentloaded'});
  await new Promise(r=>setTimeout(r,3500));
  const marks=await p.evaluate(()=>{
    var D=(window.__plenkaDiag&&window.__plenkaDiag.marks)||{};
    return {boot:!!D['boot'],main:!!D['main-start'],render:!!D['init-render'],done:!!D['init-done'],
      hasLib:!!(document.querySelector('.lib-body')||document.querySelector('#libSkel')||document.querySelector('#emptyState')),
      bridgeDead:!!document.getElementById('natvBridgeDead'), diagBtn:!!document.getElementById('plenkaDiagBtn')};
  });
  console.log(JSON.stringify(marks));
  console.log('ERRORS:',errs.length?errs.slice(0,8).join(' | '):'none');
  await p.screenshot({path:'/home/z/my-project/scripts/v52_app.png'});
  await b.close();
})().catch(e=>{console.error('FAIL',e.message);process.exit(1)});
"
RC=$?
kill -9 $MOCK 2>/dev/null
pkill -f mock52.py 2>/dev/null
exit $RC
