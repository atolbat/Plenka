#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка якорей патчей v53/v54 в базе v51 (из чата)."""
import io

p = io.open('/home/z/my-project/scripts/from_chat_plenka-optimized-51.html', encoding='utf-8').read()

anchors = {
  'версия': "s('версия','страница v51 / оболочка 3.6');",
  'метка карточки': "t(it.picked?'srcFile':'natvSrc')",
  'CSS pip diag btn': "body.pip #plenkaDiagBtn",
  'setVblank def': "function setVblank(it){",
  'posterSrcOf call in setVblank': "var src=(it&&!it.audio)?posterSrcOf(it):null;",
  'VOn waiting': "VOn('waiting',function(){",
  'VOn seeked': "VOn('seeked',function(){",
  'VOn canplay': "VOn('canplay',function(){",
  'natvWakePip def': "function natvWakePip(){",
  'setPipAuto call': "natvCall('setPipAuto',on); natvCall('keepScreenOn',on);",
  'mediaState push': "natvCall('mediaState',JSON.stringify({playing:!!playing,",
  'natvThumbUrl': "natvThumbUrl",
  'resume gate': "natvResAt",
  '__plenkaResume def': "window.__plenkaResume=function(){",
  'NATV-флаг diag': "s('NATV-флаг',fmt(window.NATV))",
  'showPoster(' : "showPoster(",
  'posterUpgrade': "posterUpgrade",
  'hidePosterSoon': "hidePosterSoon",
  'playToken': "playToken",
  'btnFs': "btnFs",
  '#pKnob': "pKnob",
  'loadDot': "loadDot",
}
for name, a in anchors.items():
    print('%-28s %d' % (name, p.count(a)))

# context around label
i = p.find("t(it.picked?'srcFile':'natvSrc')")
print('\n--- карточка/метка (контекст) ---')
print(p[i-400:i+200])
