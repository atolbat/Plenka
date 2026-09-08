#!/usr/bin/env node
/* Синтакс-чек v58: вытащить все inline <script> из html и node --check каждый */
const fs=require('fs'), path=require('path'), cp=require('child_process'), os=require('os');
const html=fs.readFileSync(process.argv[2]||'/home/z/my-project/download/plenka-optimized-58.html','utf8');
const re=/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi;
let m,i=0,bad=0;
while((m=re.exec(html))){
  i++;
  const f=path.join(os.tmpdir(),'pl58_'+i+'.js');
  fs.writeFileSync(f,m[1]);
  const r=cp.spawnSync(process.execPath,['--check',f],{encoding:'utf8'});
  if(r.status!==0){ bad++; console.log('FAIL script#'+i+':', (r.stderr||'').split('\n').slice(0,4).join(' | ')); }
  fs.unlinkSync(f);
}
console.log(i+' inline скриптов проверено, ошибок: '+bad);
process.exit(bad?1:0);
