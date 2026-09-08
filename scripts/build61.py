#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v59 → v61: три бага основного приложения (репорт юзера).

БАГ 1 «на старте на мгновение видны все видео, втч приватные»:
  оболочка на onPageFinished сразу толкает __plenkaResume → nativeSync →
  natvMerge → renderLib/renderStrip — это происходит ДО того, как бут-ифей
  дочитает hiddenlist из IndexedDB → hiddenSet пуст → скрытые отрисованы
  публично на ~сотни мс. Лечится гейтом hiddenReady: рендер списка/ленты
  запрещён, пока hiddenlist не прочитан (или IDB честно отказал).
БАГ 2 «смотрю приватное, свайп назад → публичная папка»:
  __plenkaBack проверял hiddenView РАНЬШЕ того, открыт ли плеер: назад
  при открытом видео выходил из скрытого раздела (а плеер оставался).
  Теперь: плеер открыт → 'nav' (шаг истории закрывает плеер, раздел тот же).
БАГ 3 «аудио без обложки — битый плейсхолдер во многих местах»:
  мини-панель/очередь/remote ставили сетевой /t/ прямо в <img> без
  onerror: 404 (нет встроенного арта) рисовал «битое изображение».
  Теперь: data-fb + глобальный перехват error (capture) → плейсхолдер
  (нота/фильм/мини-обложка), 404 запоминается (thumbDeadAdd).

Патчи (якоря уникальные, каждый проверяется count==1):
  P1  js : var hiddenSet → +hiddenReady
  P2  js : renderLib — гейт
  P3  js : renderStrip — гейт
  P4  js : после чтения R[2] (hiddenlist) → hiddenReady=true
  P5  js : __plenkaBack — проверка плеера ДО hiddenView
  P6  js : глобальный error-перехват data-fb (после cardThumbUpgrade)
  P7  js : miniArtHTML-хелпер (после FILM_SVG)
  P8  js : enterMini — мини-обложка без битой иконки
  P9  js : keepMini (смена трека в мини) — то же
  P10 js : remoteArt — data-fb + thumbDead
  P11 js : renderQueue — плейсхолдер на 404, как в карточках
  P12 js : мини-подложки зеркала (miniStreamFeed/miniMirrorSync) — data-fb
  P13 ver: ДИАГ 'страница v59' → 'страница v61'
"""
import sys

SRC = '/home/z/my-project/download/plenka-optimized-59.html'
DST = '/home/z/my-project/download/plenka-optimized-61.html'

src = open(SRC, encoding='utf-8').read()
orig_len = len(src)


def patch(name, anchor, repl, count=1):
    global src
    n = src.count(anchor)
    assert n == count, 'ЯКОРЬ %s: найден %d раз (ожидался %d)' % (name, n, count)
    src = src.replace(anchor, repl, count)
    print('  [%s] ok' % name)


# ── P1: флаг готовности скрытого списка ──────────────────────────────
A = 'var hiddenSet={},hiddenView=false;        /* скрытый список: id → true; вход — особым жестом */\n'
R = ('var hiddenSet={},hiddenView=false,hiddenReady=false;   /* скрытый список: id → true; вход — особым жестом;'
     ' 61: hiddenReady — список рендерится только после прочтения hiddenlist из IDB */\n')
patch('P1 hiddenReady', A, R)

# ── P2: гейт renderLib ───────────────────────────────────────────────
A = 'function renderLib(){\n  var a=viewItems(); viewCache=a;\n'
R = ('function renderLib(){\n'
     '  if(!hiddenReady)return;                 /* 61: hiddenlist ещё не прочитан — рендер показал бы скрытые'
     ' (синк оболочки приходит раньше IDB: «на мгновение видны все видео, втч приватные») */\n'
     '  var a=viewItems(); viewCache=a;\n')
patch('P2 renderLib gate', A, R)

# ── P3: гейт renderStrip ─────────────────────────────────────────────
A = 'function renderStrip(){\n  var st=$(\'#strip\');\n'
R = ('function renderStrip(){\n'
     '  if(!hiddenReady)return;                 /* 61: тот же гейт — лента из того же вида */\n'
     '  var st=$(\'#strip\');\n')
patch('P3 renderStrip gate', A, R)

# ── P4: hiddenReady=true после чтения hiddenlist ─────────────────────
A = ('  try{\n'
     '    var hl=R[2];\n'
     '    if(hl&&hl.length)hl.forEach(function(id){ hiddenSet[id]=true });\n'
     '  }catch(e){}\n')
R = A + '  hiddenReady=true;                     /* 61: скрытые известны (или IDB отказал) — список можно показывать */\n'
patch('P4 hiddenReady set', A, R)

# ── P5: __plenkaBack — плеер ДО hiddenView ───────────────────────────
A = ("    if(!$('#statsPanel').hidden){ $('#statsPanel').hidden=true; return 'ui'; }\n"
     "    if(hiddenView){ setHiddenView(false,true); return 'ui'; }\n")
R = ("    if(!$('#statsPanel').hidden){ $('#statsPanel').hidden=true; return 'ui'; }\n"
     "    if(!player.hidden)return 'nav';            /* 61: плеер открыт — системный «назад» закрывает плеер"
     " (шаг истории),\n"
     "                                                   а не выходит из скрытого раздела: просмотр приватного"
     " + свайп назад\n"
     "                                                   больше не вываливает в публичную папку */\n"
     "    if(hiddenView){ setHiddenView(false,true); return 'ui'; }\n")
patch('P5 back player first', A, R)

# ── P6: глобальный перехват error у data-fb ──────────────────────────
A = ("  if(img._tuq===url)return; img._tuq=url;   /* 46: один job на URL на элемент */\n"
     "  THUMB_Q=THUMB_Q.filter(function(j){ return j.img.isConnected });   /* 46: мёртвые карточки из очереди — вон */\n"
     "  THUMB_Q.push({img:img,url:url,it:it});\n"
     "  thumbPump();\n"
     "}\n")
R = A + '''/* ═══ 61: битые иконки сетевых обложек — искоренены ═══
   Мини-панель/очередь/remote ставили сетевой /t/ прямо в <img>: 404
   (аудио без встроенного арта) рисовало «битое изображение». Любой
   <img data-fb="note|film|pha|phv"> при ошибке меняется на должный
   плейсхолдер; 404 запоминается (thumbDead) — повторно не долбим. */
document.addEventListener('error',function(e){
  try{
    var el=e.target; if(!el||el.tagName!=='IMG')return;
    var fb=el.getAttribute('data-fb'); if(!fb||el._fb)return;
    var u=''+(el.src||''); if(u.indexOf('/t/')>0){ try{ thumbDeadAdd(u) }catch(e2){} }
    var m=(fb==='note')?NOTE_SVG:(fb==='film')?FILM_SVG:(fb==='pha')?THUMB_PH_A:THUMB_PH_V;
    if(!m)return;
    el._fb=1; el.outerHTML=m;
  }catch(e3){}
},true);
'''
patch('P6 error capture', A, R)

# ── P7: miniArtHTML-хелпер ───────────────────────────────────────────
A = "var FILM_SVG='<svg viewBox=\"0 0 24 24\" width=\"20\" height=\"20\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.5\"><rect x=\"3\" y=\"4\" width=\"18\" height=\"16\" rx=\"2\"/><path d=\"M7.5 4v16M16.5 4v16M3 9h4.5M3 15h4.5M16.5 9H21M16.5 15H21\"/></svg>';\n"
R = A + '''function miniArtHTML(it){                  /* 61: обложка мини-панели — без битой иконки на 404 (нет арта) */
  if(it&&it.thumb){
    var u=''+it.thumb;
    if(u.indexOf('data:')!==0&&thumbDead(u))return NOTE_SVG;
    return '<img src="'+u+'" data-fb="note" alt="">';
  }
  return NOTE_SVG;
}
'''
patch('P7 miniArtHTML', A, R)

# ── P8: enterMini ────────────────────────────────────────────────────
A = ("  if(it.audio){\n"
     "    miniThumb.innerHTML=it.thumb?'<img src=\"'+it.thumb+'\" alt=\"\">':NOTE_SVG;\n"
     "  }else{\n"
     "    miniThumb.innerHTML='';\n"
     "    if(MIRROR.on")
R = ("  if(it.audio){\n"
     "    miniThumb.innerHTML=miniArtHTML(it);   /* 61: 404 арта → нота, не битая иконка */\n"
     "  }else{\n"
     "    miniThumb.innerHTML='';\n"
     "    if(MIRROR.on")
patch('P8 enterMini art', A, R)

# ── P9: keepMini (смена трека при открытой мини) ─────────────────────
A = ("    if(it.audio){ miniThumb.innerHTML=it.thumb?'<img src=\"'+it.thumb+'\" alt=\"\">':NOTE_SVG; }\n"
     "    else{ miniThumb.innerHTML=''; try{ vActive.style.transform=''; }catch(e){} miniThumb.appendChild(vActive); }\n")
R = ("    if(it.audio){ miniThumb.innerHTML=miniArtHTML(it); }   /* 61: 404 арта → нота */\n"
     "    else{ miniThumb.innerHTML=''; try{ vActive.style.transform=''; }catch(e){} miniThumb.appendChild(vActive); }\n")
patch('P9 keepMini art', A, R)

# ── P10: remoteArt ───────────────────────────────────────────────────
A = "  return (it&&it.thumb)?'<img src=\"'+it.thumb+'\" alt=\"\">':(audio?NOTE_SVG:FILM_SVG);\n"
R = ("  if(it&&it.thumb){                     /* 61: 404 обложки — плейсхолдер, не битая иконка */\n"
     "    var u=''+it.thumb;\n"
     "    if(u.indexOf('data:')===0||!thumbDead(u))return '<img src=\"'+u+'\" data-fb=\"'+(audio?'note':'film')+'\" alt=\"\">';\n"
     "  }\n"
     "  return audio?NOTE_SVG:FILM_SVG;\n")
patch('P10 remoteArt', A, R)

# ── P11: renderQueue — плейсхолдер на 404 ────────────────────────────
A = "    if(it7&&it7.thumb){ var ig7=q.children[w7].querySelector('.qi-thumb img'); if(ig7)ig7.src=thumbUrl(it7); }\n"
R = ("    if(it7&&it7.thumb){ var ig7=q.children[w7].querySelector('.qi-thumb img'); if(ig7){   /* 61: 404 — плейсхолдер, как в карточках */\n"
     "      var tu7=thumbUrl(it7);\n"
     "      ig7.setAttribute('data-fb',it7.audio?'pha':'phv');\n"
     "      ig7.src=(tu7&&(''+tu7).indexOf('data:')!==0&&thumbDead(tu7))?(it7.audio?THUMB_PH_A:THUMB_PH_V):tu7;\n"
     "    } }\n")
patch('P11 queue art', A, R)

# ── P12: подложки зеркала в мини ─────────────────────────────────────
A = "  miniThumb.innerHTML=tu?'<img class=\"u\" src=\"'+tu+'\" alt=\"\">':'';\n  var sv=document.createElement('video');\n"
R = "  miniThumb.innerHTML=tu?'<img class=\"u\" src=\"'+tu+'\" data-fb=\"phv\" alt=\"\">':'';\n  var sv=document.createElement('video');\n"
patch('P12 mirror sublayer A', A, R)

A = "    miniThumb.innerHTML=tu?'<img class=\"u\" src=\"'+tu+'\" alt=\"\">':'';   /* подложка: кадр виден, пока зеркало грузится */\n"
R = "    miniThumb.innerHTML=tu?'<img class=\"u\" src=\"'+tu+'\" data-fb=\"phv\" alt=\"\">':'';   /* 61: подложка: кадр виден, пока зеркало грузится; 404 — плейсхолдер */\n"
patch('P12 mirror sublayer B', A, R)

# ── P13: версия ──────────────────────────────────────────────────────
A = "  s('версия','страница v59 / оболочка 3.13');\n"
R = "  s('версия','страница v61 / оболочка 3.13');   /* 61: флэш скрытых на старте; назад из приватного; битые обложки */\n"
patch('P13 version', A, R)

# ── запись ───────────────────────────────────────────────────────────
assert src.count('hiddenReady') >= 5, 'hiddenReady должен встречаться минимум 5 раз'
open(DST, 'w', encoding='utf-8').write(src)
print('OK: %s (%d → %d байт, +%d)' % (DST, orig_len, len(src), len(src) - orig_len))
