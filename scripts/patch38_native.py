#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v38 патч 2: замена блока nativeSync/natvAskPerm/__plenkaPermResult/__plenkaResume
на инструментированную версию с ретрай-лестницей, опросом права и вочдогом.
Работа по номерам строк (строки 1-индексные), с проверкой якорей."""
import io, sys

P = "/home/z/my-project/download/plenka-optimized-38.html"

NEW = r'''/* скан MediaStore → элементы kind:'native'. Идентификатор устойчив (id MediaStore),
   слияние обновляет метаданные, не трогая позиции/плейлисты/просмотры.
   2.3: ни один выход больше не молчит — каждая ветка пишется в журнал; срывы скана
   ретраятся (транзиентные сбои моста на старте), право поллится до 40с,
   а вочдог запрещает «скан видит файлы, а библиотека пуста» */
var natvSyncBusy=false, natvSyncTries=0, natvSyncRetryT=null;
function natvSyncSchedule(ms,rescan,why){
  if(natvSyncRetryT)return;
  NJ('sync','повтор через '+Math.round(ms)+'мс: '+why);
  natvSyncRetryT=setTimeout(function(){ natvSyncRetryT=null; nativeSync(rescan); },ms);
}
function nativeSync(rescan){
  if(!NATV){ NJ('sync','моста нет — выходим'); return; }
  if(natvSyncBusy){ NJ('sync','занят (мердж идёт) — пропуск'); return; }
  var t0=Date.now();
  var hp=natvCall('hasPerm');
  if(hp===false){ NJ('sync','hasPerm=false — просим право и поллим'); natvAskPerm(); natvPermPoll(); return; }
  var raw=natvCall('scan'), env=null, perr=null;
  try{ env=raw?JSON.parse(raw):null }catch(e){ perr=e.message }
  var ms=Date.now()-t0;
  if(perr)NJ('sync','скан вернул не-JSON: '+(''+raw).substring(0,90));
  if(!env){
    NJ('sync','скан НЕ дал конверт за '+ms+'мс');
    if(natvSyncTries<3){ natvSyncTries++; natvSyncSchedule(natvSyncTries*1200,rescan,'скан без конверта (попытка '+natvSyncTries+'/3)'); }
    else NJ('sync','ретраи исчерпаны — ждём вочдог/жест');
    return;
  }
  if(!env.ok){
    NJ('sync','конверт ok=false err='+env.err+(env.msg?(' ('+env.msg+')'):''));
    if(env.err==='perm'){ natvAskPerm(); natvPermPoll(); return; }
    if(natvSyncTries<3){ natvSyncTries++; natvSyncSchedule(natvSyncTries*1200,rescan,'конверт ok=false (попытка '+natvSyncTries+'/3)'); }
    return;
  }
  var arr=env.items||[];
  if(!arr.length){
    NJ('sync','скан: 0 подходящих файлов (skip='+(env.skipN||0)+', perm='+env.perm+')');
    if(rescan)toast(t('addedN',{n:0}));
    /* 2.2: пусто — честно показываем, сколько файлов сидело в медиатеке, но отфильтровано:
       mkv/ts/avi движок WebView не открывает в принципе; права могли выдать частично */
    try{
      var note=$('#natvEmptyNote');
      if(note){
        var extra=(env.skipN>0)?(' '+t('natvSkippedN',{n:env.skipN})):
            ((env.perm&&env.perm!=='ok')?(' '+t('natvPartial')):'');
        if(extra){ note.hidden=false; note.textContent=t('natvEmpty')+extra; }
      }
    }catch(e){}
    return;
  }
  NJ('sync','скан ok: '+arr.length+' файлов за '+ms+'мс — мерджим');
  natvSyncTries=0;
  natvSyncBusy=true;
  try{ natvMerge(arr,rescan); }
  finally{ natvSyncBusy=false }
}
function natvAskPerm(){
  var r=natvCall('requestPerm');
  NJ('perm','requestPerm → '+r);
  if(r===false)toast(t('natvPermDenied'),'err');
}
/* 2.3: доставка результата права (evaluateJavascript оболочки) может потеряться —
   поллим сами каждые 2с до 40с: любое выдание (диалог/настройки/задержка) сходится в ресинк */
var natvPermPollT=null;
function natvPermPoll(){
  if(!NATV||natvPermPollT)return;
  NJ('perm','запуск опроса права: каждые 2с, до 40с');
  var ticks=0;
  natvPermPollT=setInterval(function(){
    ticks++;
    var hp=null;
    try{ hp=window.PlenkaNative?window.PlenkaNative.hasPerm():null }catch(e){ hp=null }
    if(hp===true){
      clearInterval(natvPermPollT); natvPermPollT=null;
      NJ('perm','право появилось на тике '+ticks+' — ресинк');
      nativeSync(true); return;
    }
    if(ticks>=20){ clearInterval(natvPermPollT); natvPermPollT=null; NJ('perm','права нет 40с — ждём вручную/настроек'); return; }
    if(ticks%5===0)NJ('perm','права всё нет (тик '+ticks+'/20)');
  },2000);
}
/* 2.3: вочдог пустой библиотеки — «скан видит файлы, а карточек нет» больше не может
   существовать молча: при пустой библиотеке каждые 7с (до 18 тиков) — проба скана,
   при находке — форс-мердж; без права — опрос. Именно он закрыл бы баг 2.2 */
var natvWdT=null, natvWdN=0;
function natvWatchdogStart(){
  if(natvWdT||!NATV)return;
  NJ('watchdog','старт: следим за пустой библиотекой (7с × 18 тиков)');
  natvWdT=setInterval(function(){
    natvWdN++;
    if(items.length){ clearInterval(natvWdT); natvWdT=null; NJ('watchdog','библиотека заполнена ('+items.length+') — вочдог выключен'); return; }
    if(natvWdN>18){ clearInterval(natvWdT); natvWdT=null; NJ('watchdog','стоп: 18 тиков, библиотека пуста — остаёмся честно пустыми'); return; }
    natvWatchdog();
  },7000);
  setTimeout(natvWatchdog,2500);
}
function natvWatchdog(){
  if(!NATV||items.length)return;
  var hp=null;
  try{ hp=window.PlenkaNative?window.PlenkaNative.hasPerm():null }catch(e){}
  if(hp!==true){ NJ('watchdog','библиотека пуста, права нет — опрос'); if(!natvPermPollT)natvPermPoll(); return; }
  var raw=null;
  try{ raw=window.PlenkaNative.scan() }catch(e){ raw=null }
  var env=null; try{ env=raw?JSON.parse(raw):null }catch(e){}
  if(env&&env.ok&&env.items&&env.items.length){
    NJ('watchdog','скан видит '+env.items.length+', библиотека пуста — форс-мердж');
    try{ natvMerge(env.items,false); }
    catch(e){
      NJ('watchdog','форс-мердж упал: '+e.message);
      try{ var nn=$('#natvEmptyNote'); if(nn){ nn.hidden=false; nn.textContent=t('natvScanMismatch',{n:env.items.length}); } }catch(e2){}
    }
  }else{
    NJ('watchdog','скан пуст/отказ ('+((env===null)?'env=null':('ok='+env.ok+' n='+(env.n||0)))+')');
  }
}
var permResAt=0, permDeniedShown=false;
window.__plenkaPermResult=function(ok){              /* оболочка доставляет с ретраями — гейт от повторов; 2.3: квитанция для logcat */
  var now=Date.now(); if(now-permResAt<2500)return 'gate'; permResAt=now;
  NJ('perm','__plenkaPermResult('+ok+') от оболочки');
  if(ok){ permDeniedShown=false; nativeSync(true); }
  else if(!permDeniedShown){ permDeniedShown=true; toast(t('natvPermDenied'),'err'); }   /* спрашивать будут на каждом возврате — не спамим */
  return 'ok';
};
var natvResAt=0;
window.__plenkaResume=function(){                    /* возврат в приложение: право могли выдать в настройках */
  if(!NATV)return 'nonatv';
  var now=Date.now(); if(now-natvResAt<5000)return 'gate'; natvResAt=now;
  NJ('стр','__plenkaResume — возврат в приложение, синк + тик вочдога');
  nativeSync(false); natvPickedSync(false);
  try{ if(!items.length)natvWatchdog(); }catch(e){}
  return 'ok';
};
'''

ANCHOR_START = "/* скан MediaStore → элементы kind:'native'."
ANCHOR_END = "function natvMerge(arr,rescan){"

with io.open(P, encoding="utf-8") as f:
    lines = f.readlines()

# найдём границы
si = None
for i, ln in enumerate(lines):
    if ln.startswith(ANCHOR_START):
        si = i
        break
if si is None:
    sys.exit("якорь начала не найден")
ei = None
for i in range(si, len(lines)):
    if lines[i].startswith(ANCHOR_END):
        ei = i
        break
if ei is None:
    sys.exit("якорь конца не найден")

# проверим, что внутри старого блока есть ожидаемые маркеры
old_block = "".join(lines[si:ei])
for marker in ("var natvSyncBusy=false;", "window.__plenkaPermResult", "window.__plenkaResume"):
    if marker not in old_block:
        sys.exit("маркер '" + marker + "' не найден в заменяемом блоке — прервано")

lines[si:ei] = [NEW]

with io.open(P, "w", encoding="utf-8") as f:
    f.writelines(lines)

print("OK: блок nativeSync заменён (строки %d..%d, было %d строк, стало %d)" % (si + 1, ei, ei - si, NEW.count("\n")))
