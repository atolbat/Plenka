#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kotlin 3.13 → 3.14: страница v61 (три бага репорта юзера).

Оболочка функционально НЕ менялась — все три фикса в странице v61:
  1) флэш скрытых видео при старте (гейт рендера до чтения hiddenlist);
  2) свайп назад из приватного видео больше не вываливает в публичную папку;
  3) битые плейсхолдеры у аудио без обложки (мини/очередь/remote).
Здесь только: версия 3.14 / versionCode 143, ассет = v61 байт-в-байт.
"""
import io, shutil, sys

ROOT = '/home/z/my-project/plenka-native'
MACT = ROOT + '/app/src/main/java/ru/plenka/app/MainActivity.kt'
MSVC = ROOT + '/app/src/main/java/ru/plenka/app/PlenkaService.kt'
GRAD = ROOT + '/app/build.gradle.kts'
ASSET = ROOT + '/app/src/main/assets/plenka.html'
V61 = '/home/z/my-project/download/plenka-optimized-61.html'


def rep(path, old, new, what, cnt=1):
    src = io.open(path, encoding='utf-8').read()
    n = src.count(old)
    assert n == cnt, 'FAIL: якорь %r найден %d раз (ожидалось %d)' % (what, n, cnt)
    io.open(path, 'w', encoding='utf-8', newline='').write(src.replace(old, new))
    print('ok: %s' % what)


# 1: MainActivity — версия и стартовый лог
rep(MACT, 'private const val APP_VERSION = "PLENKA native 3.13 (v59)"',
    'private const val APP_VERSION = "PLENKA native 3.14 (v61)"', 'APP_VERSION 3.14/v61')
rep(MACT, 'Log.i(TAG, "native 3.13 started, version=$APP_VERSION sdk=${Build.VERSION.SDK_INT}")',
    'Log.i(TAG, "native 3.14 started, version=$APP_VERSION sdk=${Build.VERSION.SDK_INT}")',
    'стартовый лог 3.14')

# 2: PlenkaService — шапка
rep(MSVC, ' * ПЛЁНКА native 3.13: фоновый медиа-сервис — сворачивание БЕЗ PiP.',
    ' * ПЛЁНКА native 3.14: фоновый медиа-сервис — сворачивание БЕЗ PiP (страница v61).',
    'шапка сервиса 3.14')

# 3: gradle — versionCode 143 / 3.14
rep(GRAD, 'versionCode = 142', 'versionCode = 143', 'versionCode 143')
rep(GRAD, 'versionName = "3.13"', 'versionName = "3.14"', 'versionName 3.14')

# 4: ассет = v61 байт-в-байт
shutil.copyfile(V61, ASSET)
a = open(ASSET, 'rb').read()
b = open(V61, 'rb').read()
assert a == b and len(a) > 700000
print('ok: assets/plenka.html = v61 (%d байт)' % len(a))
print('ГОТОВО: 3.14 / versionCode 143 / ассет v61')
