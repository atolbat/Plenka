#!/usr/bin/env node
/* Синтаксис-проверка: все inline <script> из HTML → node --check */
const fs = require('fs');
const { execFileSync } = require('child_process');
const h = fs.readFileSync('/home/z/my-project/download/plenka-optimized-62.html', 'utf8');
const re = /<script>([\s\S]*?)<\/script>/g;
let m, i = 0, bad = 0;
while ((m = re.exec(h))) {
  i++;
  const f = '/home/z/my-project/scripts/_syn62_' + i + '.js';
  fs.writeFileSync(f, m[1]);
  try {
    execFileSync(process.execPath, ['--check', f], { stdio: 'pipe' });
  } catch (e) {
    bad++;
    console.log('[FAIL] script #' + i + ': ' + (e.stderr ? e.stderr.toString().slice(0, 300) : e.message));
  }
  fs.unlinkSync(f);
}
console.log('скриптов: ' + i + ', ошибок: ' + bad);
process.exit(bad ? 1 : 0);
