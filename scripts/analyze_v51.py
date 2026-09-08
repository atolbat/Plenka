#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Анализ страницы v51 (база 3.6): мост, роуты, MSE-механика."""
import re, sys

p = open('/home/z/my-project/scripts/from_chat_plenka-optimized-51.html', encoding='utf-8').read()
print('page length:', len(p))

calls = set(re.findall(r"natvCall\('([a-zA-Z]+)", p))
print('natvCall methods:', sorted(calls))

direct = set(re.findall(r'PlenkaNative\.([a-zA-Z]+)', p))
print('direct PlenkaNative:', sorted(direct))

routes = set(re.findall(r"['\"](/(?:v|a|t|c|lab|seek|list)/[^'\"]{0,40})", p))
print('routes:', sorted(routes))

for m in re.findall(r'страница v[0-9]+[^<"\']{0,30}', p)[:3]:
    print('VER:', m)

keys = ['msebOpen', 'msebFetch', 'msebParseMoov', 'msebCall', 'anchorMap', 'anchor',
        'не сел', 'бэкфилл', 'пересборка', 'sidx', 'mvex', 'webgen', 'fframe',
        'techPaused', 'rVFC', 'сторож', 'watchdog', 'Приложение', '__plenkaResume',
        'posterFirst', 'X-Plenka-FrameT', 'нативный поток', 'мост']
for key in keys:
    print('count %-24s %d' % (key, p.count(key)))

# i18n метки
for lbl in ['natvSrc', 'srcFile', 'медиатека']:
    print('label %-10s %d' % (lbl, p.count(lbl)))
