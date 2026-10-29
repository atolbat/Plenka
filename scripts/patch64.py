#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v63 → v64: два репорта юзера.

1) «Убери кнопку диагностики» — экран ДИАГ уходит целиком: кнопка-поплавок,
   оверлей-отчёт (probe/openDiag/mkB/upd/toLog/toClip), плашка «нажмите ДИАГ»
   у мёртвого моста, строки локализации. Невидимая часть остаётся: ловля ошибок
   (rec → report в logcat), журнал тапов/событий (__plenkaJ → PlenkaNative.log),
   метки __plenkaDiag.marks (оболочка опрашивает их из Kotlin-проба).

2) «В настройках вместо кучи радио-бутонов — выпадающие списки» — все
   .seg[data-seg] (настройки/очередь/субтитры: loop, step, seekMode, stripMode,
   fit, interp, lang, toasts, autohide, pauseUi, pinGrace, subsColor) и пресеты
   эквалайзера #eqPresets становятся кнопкой-триггером .dd + общий список
   #segPop (класс .pop — поверх drawers, z320>300). Сами .seg остаются в DOM
   скрытыми (.dd-src): источник опций, data-i-переводов и клик-логики — выбор
   в списке щёлкает оригинальную кнопку, настройки применяются прежним путём.

Патчи (якоря уникальны, каждый проверяется):
  P1  css: убрать body.pip #plenkaDiagBtn
  P2  css: стили .dd / .ddv / .ddc / #segPop
  P3  js  : шапка бутстрап-диагностики (версия v64 / 3.17)
  P4  js  : вырезать блок создания кнопки «ДИАГ»
  P5  js  : rec() без badge()
  P6  js  : вырезать probe→toClip (экран отчёта)
  P7  js  : мёртвый мост — без подсказки про ДИАГ и кнопки отчёта
  P8  loc : убрать natvDiagHint/natvDiagOpen (ru, en)
  P9  js  : openPop — сброс залипших .dd.pop-open
  P10 js  : syncSeg — обновлять подпись триггера .dd
  P11 js  : конвертер .seg/.eqPresets → .dd + #segPop
  P12 js  : case 'lang' — ресинк подписей после смены языка
"""
import sys

SRC = '/home/z/my-project/download/plenka-optimized-63.html'
DST = '/home/z/my-project/download/plenka-optimized-64.html'

src = open(SRC, encoding='utf-8').read()
orig_len = len(src)


def patch(name, anchor, repl, count=1):
    global src
    n = src.count(anchor)
    assert n == count, 'ЯКОРЬ %s: найден %d раз (ожидался %d)' % (name, n, count)
    src = src.replace(anchor, repl, count)
    print('  [%s] ok' % name)


def cut(name, start, end, repl):
    """Вырезать [start..end) по маркерам (end — точный текст, включается)."""
    global src
    i = src.find(start)
    assert i >= 0, '%s: старт-маркер не найден' % name
    j = src.find(end, i)
    assert j >= i, '%s: конец-маркер не найден' % name
    j += len(end)
    src = src[:i] + repl + src[j:]
    print('  [%s] ok (−%d Б)' % (name, j - i - len(repl)))


# ── P1: CSS — правило для кнопки ДИАГ в PiP ──────────────────────────
A = "body.pip #plenkaDiagBtn{display:none!important}        /* 2.4: кнопка диагностики в PiP не нужна */\n"
patch('P1-css-diag-pip', A, '')

# ── P2: CSS — стили выпадающих списков ───────────────────────────────
A = ".seg button.on{color:var(--acc);border-color:var(--acc2);background:var(--bg3)}\n.seg button.on::before{background:var(--acc);border-color:var(--acc)}\n"
R = A + """
/* ═══ 64: радио-сегменты → выпадающие списки ═══
   .seg остаётся в DOM скрытым (.dd-src) — источник опций, data-i-переводов
   и клик-логики; перед ним кнопка-триггер .dd, список — общий поп #segPop */
.seg.dd-src{display:none!important}
.dd{display:inline-flex;align-items:center;gap:9px;max-width:100%;min-width:0;
  background:var(--bg2);border:1px solid var(--line2);border-radius:7px;
  padding:6px 11px;font-family:var(--mono);font-size:10px;letter-spacing:.07em;
  text-transform:uppercase;color:var(--acc);cursor:pointer;
  transition:border-color .12s,background .12s}
.dd:hover{border-color:var(--mut)}
.dd .ddv{color:var(--tx);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dd .ddc{flex:none;display:inline-flex;color:var(--dim);transition:transform .16s,color .12s}
.dd.pop-open{border-color:var(--acc2);background:var(--bg3)}
.dd.pop-open .ddc{transform:rotate(180deg);color:var(--acc)}
#segPop{min-width:150px;max-height:56vh;overflow-y:auto}
#segPop button{display:flex;align-items:center;gap:9px}
#segPop button::before{content:'';flex:none;width:7px;height:7px;border-radius:50%;
  border:1px solid var(--dim);transition:background .12s,border-color .12s}
#segPop button.on{color:var(--acc)}
#segPop button.on::before{background:var(--acc);border-color:var(--acc)}
"""
patch('P2-css-dd', A, R)

# ── P3: шапка бутстрап-диагностики ───────────────────────────────────
A = ("/* ═══ ПЛЁНКА 2.2: бутстрап-диагностика ═══\n"
     "   Отдельный скрипт ДО всего приложения: только ES5, инлайн-стили, ноль зависимостей.\n"
     "   Живёт, даже если главный скрипт мёртв: ловит его ошибки, держит кнопку «ДИАГ»\n"
     "   (в нативе — всегда, в браузере — только при ошибках) и собирает живой отчёт\n"
     "   по мосту/правам/скану — чтобы «тихая пустая библиотека» стала невозможной. */")
R = ("/* ═══ ПЛЁНКА 2.2: бутстрап-диагностика ═══\n"
     "   Отдельный скрипт ДО всего приложения: только ES5, инлайн-стили, ноль зависимостей.\n"
     "   Живёт, даже если главный скрипт мёртв: ловит его ошибки и уводит их в logcat\n"
     "   натива, журнал «куда нажали, что получили» — туда же. Кнопка «ДИАГ» и экран\n"
     "   отчёта убраны в 64 (репорт юзера); страница v64 / оболочка 3.17. */")
patch('P3-boot-header', A, R)

# ── P4: вырезать создание кнопки «ДИАГ» ──────────────────────────────
cut('P4-diag-btn',
    "/* кнопка «ДИАГ»: fixed, выше любых слоёв приложения; тап — живой отчёт */",
    "(document.body||document.documentElement).appendChild(btn);",
    "/* 64: кнопка «ДИАГ» убрана по репорту юзера — диагностика осталась невидимой:\n"
    "   ошибки/журнал уходят в logcat (report/__plenkaJ), метки __plenkaDiag\n"
    "   по-прежнему живы — их опрашивает probe оболочки (Kotlin) */")

# ── P5: rec() без badge() ────────────────────────────────────────────
patch('P5-rec-badge', "    report(s);\n    badge();\n", "    report(s);\n")

# ── P6: вырезать probe→toClip (экран отчёта целиком) ─────────────────
cut('P6-diag-report',
    "/* живой отчёт: всё, что можно узнать без главного скрипта */",
    "function toClip(){\n  try{\n    var txt=probe();\n    if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(txt);\n  }catch(e){}\n}",
    "/* 64: экран диагностики (probe/openDiag/toLog/toClip) убран вместе с кнопкой\n"
    "   «ДИАГ». Невидимая часть жива: ошибки — report() в logcat натива, журнал\n"
    "   тапов/событий — __plenkaJ → PlenkaNative.log, метки — __plenkaDiag.marks */\n")

# ── P7: мёртвый мост — плашка без подсказки/кнопки ДИАГ ──────────────
A = ("      bd.textContent=t('natvNoBridge')+'. '+t('natvDiagHint')+'.';\n"
     "      var bb=document.createElement('button');\n"
     "      bb.type='button';\n"
     "      bb.className='btn sm';\n"
     "      bb.style.cssText='margin-top:9px;display:block';\n"
     "      bb.textContent=t('natvDiagOpen');\n"
     "      bb.addEventListener('click',function(){ try{var d=document.getElementById('plenkaDiagBtn');d&&d.click()}catch(e){} });\n"
     "      bd.appendChild(bb);\n")
R = "      bd.textContent=t('natvNoBridge')+'.';   /* 64: подсказка «нажмите ДИАГ» и кнопка отчёта ушли вместе с кнопкой */\n"
patch('P7-bridge-dead', A, R)

# ── P8: локализация — убрать ключи диагностики ───────────────────────
patch('P8a-loc-ru',
      " natvDiagHint:'нажмите «ДИАГ» в правом верхнем углу и пришлите текст отчёта', natvDiagOpen:'открыть диагностику',\n",
      '')
patch('P8b-loc-en',
      " natvDiagHint:'tap «ДИАГ» in the top right corner and send the report text', natvDiagOpen:'open diagnostics',\n",
      '')

# ── P9: openPop — сброс залипших триггеров .dd ────────────────────────
A = "function openPop(sel,anchor,dir){\n  $$('.pop').forEach(function(p){ p.classList.remove('open') });"
R = (A + "\n  $$('.dd.pop-open').forEach(function(d){ d.classList.remove('pop-open');"
        "d.setAttribute('aria-expanded','false') });   /* 64: триггер списка не должен залипать открытым */")
patch('P9-openpop-dd', A, R)

# ── P10: syncSeg — подпись триггера ──────────────────────────────────
A = ("function syncSeg(key){\n"
     "  $$('.seg[data-seg]').forEach(function(seg){\n"
     "    if(seg.getAttribute('data-seg')!==key)return;\n"
     "    $$('button',seg).forEach(function(b){\n"
     "      var on=String(S[key])===b.getAttribute('data-v'); b.classList.toggle('on',on); b.setAttribute('aria-pressed',String(on));\n"
     "    });\n"
     "  });\n"
     "}")
R = ("function syncSeg(key){\n"
     "  $$('.seg[data-seg]').forEach(function(seg){\n"
     "    if(seg.getAttribute('data-seg')!==key)return;\n"
     "    var onb=null;   /* 64: кнопка-«радио» в состоянии on — с неё берём подпись триггера списка */\n"
     "    $$('button',seg).forEach(function(b){\n"
     "      var on=String(S[key])===b.getAttribute('data-v'); b.classList.toggle('on',on); b.setAttribute('aria-pressed',String(on));\n"
     "      if(on)onb=b;\n"
     "    });\n"
     "    if(seg._dd&&onb)seg._dd.querySelector('.ddv').textContent=onb.textContent;\n"
     "  });\n"
     "}")
patch('P10-syncseg-label', A, R)

# ── P11: конвертер .seg/#eqPresets → выпадающие списки ───────────────
CONVERTER = r"""/* ═══ 64: радио-сегменты → выпадающие списки ═══
   Все .seg[data-seg] (настройки/очередь/субтитры) и #eqPresets получают
   кнопку-триггер .dd; список — общий поп #segPop. Сами .seg остаются в DOM
   скрытыми (.dd-src): источник опций, data-i-переводов и клик-логики.
   Выбор в списке щёлкает ОРИГИНАЛЬНУЮ кнопку в скрытом .seg — настройки
   применяются прежним путём (S → saveS → applySetting). */
(function(){
  var pop=null,cur=null;
  function ensurePop(){
    if(pop)return pop;
    pop=document.createElement('div');
    pop.className='pop';pop.id='segPop';
    document.body.appendChild(pop);
    return pop;
  }
  var CHEV='<svg class="ddc" viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>';
  function makeDD(seg,isCur,fb){
    seg.classList.add('dd-src');
    var dd=document.createElement('button');
    dd.type='button';dd.className='dd';dd.setAttribute('data-popanchor','');
    dd.setAttribute('aria-haspopup','listbox');dd.setAttribute('aria-expanded','false');
    dd.innerHTML='<span class="ddv">…</span>'+CHEV;
    seg._dd=dd;seg._cur=isCur;seg._fb=fb;
    dd.addEventListener('click',function(e){
      e.stopPropagation();
      var p=ensurePop();
      if(p.classList.contains('open')&&cur===seg){closeDD();return}   /* второй тап — закрыть */
      openDD(seg);
    });
    seg.parentNode.insertBefore(dd,seg);
    syncDD(seg);
  }
  function syncDD(seg){
    if(!seg._dd)return;
    var on=null;
    $$('button',seg).forEach(function(b){ if(seg._cur(b))on=b });
    seg._dd.querySelector('.ddv').textContent=on?on.textContent:((seg._fb&&seg._fb())||'…');
  }
  function openDD(seg){
    var p=ensurePop();
    $$('.pop').forEach(function(x){x.classList.remove('open')});
    $$('.dd.pop-open').forEach(function(d){d.classList.remove('pop-open');d.setAttribute('aria-expanded','false')});
    p.innerHTML='';
    $$('button',seg).forEach(function(b){
      var o=document.createElement('button');
      o.type='button';
      if(b.classList.contains('on'))o.classList.add('on');
      o.setAttribute('data-v',b.getAttribute('data-v')||b.getAttribute('data-p'));   /* удобно тестам/DevTools */
      o.appendChild(document.createTextNode(b.textContent));
      o.addEventListener('click',function(ev){
        ev.stopPropagation();
        closeDD();
        b.click();                    /* оригинал в скрытом .seg — вся логика как раньше */
      });
      p.appendChild(o);
    });
    cur=seg;
    p.classList.add('open');
    seg._dd.classList.add('pop-open');
    seg._dd.setAttribute('aria-expanded','true');
    var r=seg._dd.getBoundingClientRect();
    p.style.minWidth=Math.max(r.width,120)+'px';
    var left=clamp(r.left+r.width/2-p.offsetWidth/2,8,innerWidth-p.offsetWidth-8);
    p.style.left=left+'px';
    var below=r.bottom+7,h=p.offsetHeight;   /* не влезает вниз — раскрываем вверх */
    p.style.top=((below+h>innerHeight-8)&&(r.top-h-8>8))?(r.top-h-7)+'px':below+'px';
  }
  function closeDD(){
    if(pop)pop.classList.remove('open');
    $$('.dd.pop-open').forEach(function(d){d.classList.remove('pop-open');d.setAttribute('aria-expanded','false')});
    cur=null;
  }
  window.__ddResync=function(){ $$('.seg.dd-src').forEach(syncDD) };   /* смена языка → перевести подписи триггеров */
  $$('.seg[data-seg]').forEach(function(seg){
    var k=seg.getAttribute('data-seg');
    makeDD(seg,function(b){return b.getAttribute('data-v')===String(S[k])},null);
  });
  var eq=document.getElementById('eqPresets');   /* пресеты эквалайзера — тем же списком */
  if(eq)makeDD(eq,function(b){return b.getAttribute('data-p')===S.eqPreset},function(){return S.eqPreset});
  var _eqSync=syncEqUI;
  syncEqUI=function(){ _eqSync.apply(this,arguments); try{syncDD(document.getElementById('eqPresets'))}catch(e){} };
})();
"""
A = "\n $$('.sw[data-sw]').forEach(function(b){\n  b.addEventListener('click',function(){\n    var k=b.getAttribute('data-sw');\n    if(k==='pinLock')"
patch('P11-dd-converter', A, "\n" + CONVERTER + "\n $$('.sw[data-sw]').forEach(function(b){\n  b.addEventListener('click',function(){\n    var k=b.getAttribute('data-sw');\n    if(k==='pinLock')")

# ── P12: смена языка — ресинк подписей триггеров ─────────────────────
A = "    case 'lang': applyI18n();\n      stripSig=null;"
R = ("    case 'lang': applyI18n();\n"
     "      try{ window.__ddResync() }catch(e){}   /* 64: подписи триггеров списков — на новом языке */\n"
     "      stripSig=null;")
patch('P12-lang-resync', A, R)

# ── P13: старт — подписи триггеров ПОСЛЕ applyI18n ────────────────────
# initSettingsUI (syncSeg/syncEqUI→syncDD) бегает РАНЬШЕ applyI18n: в EN-режиме
# кнопки .seg переводятся уже после того, как триггеры взяли русские подписи.
A = "  applyI18n(); initA11y();"
R = ("  applyI18n();\n"
     "  try{ window.__ddResync() }catch(e){}   /* 64: кнопки .seg только что перевелись — подписи триггеров берём заново */\n"
     "  initA11y();")
patch('P13-boot-resync', A, R)

# ── самопроверка ─────────────────────────────────────────────────────
assert 'plenkaDiagBtn' not in src, 'остались упоминания plenkaDiagBtn'
assert 'natvDiagHint' not in src and 'natvDiagOpen' not in src, 'остались лок-ключи ДИАГ'
assert 'function probe(){' not in src and 'function openDiag(){' not in src, 'остался экран отчёта'
assert src.count('segPop') >= 4 and src.count('makeDD') >= 3, 'конвертер не встал'
assert 'v64 / оболочка 3.17' in src, 'версия не отмечена'
assert len(src) > orig_len * 0.97, 'файл подозрительно уменьшился'
open(DST, 'w', encoding='utf-8').write(src)
print('ГОТОВО: %s (%d Б, было %d Б, %+d)' % (DST, len(src), orig_len, len(src) - orig_len))
