#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kotlin 3.14 → 3.15: страница v62 (превью-время при переключении трека).

Оболочка функционально НЕ менялась — фикс в странице v62: при переключении
(свайп/по концу/сосед) контроль времени СРАЗУ показывает 00:00 или позицию
продолжения нового трека — вместо мигания времени уходящего видео, пока
новый элемент грузится.
Здесь только: версия 3.15 / versionCode 144, ассет = v62 байт-в-байт.
"""
import io, shutil, sys

ROOT = '/home/z/my-project/plenka-native'
MACT = ROOT + '/app/src/main/java/ru/plenka/app/MainActivity.kt'
MSVC = ROOT + '/app/src/main/java/ru/plenka/app/PlenkaService.kt'
GRAD = ROOT + '/app/build.gradle.kts'
ASSET = ROOT + '/app/src/main/assets/plenka.html'
V62 = '/home/z/my-project/download/plenka-optimized-62.html'


def rep(path, old, new, what, cnt=1):
    src = io.open(path, encoding='utf-8').read()
    n = src.count(old)
    assert n == cnt, 'FAIL: якорь %r найден %d раз (ожидалось %d)' % (what, n, cnt)
    io.open(path, 'w', encoding='utf-8', newline='').write(src.replace(old, new))
    print('ok: %s' % what)


# 1: MainActivity — версия и стартовый лог
rep(MACT, 'private const val APP_VERSION = "PLENKA native 3.14 (v61)"',
    'private const val APP_VERSION = "PLENKA native 3.15 (v62)"', 'APP_VERSION 3.15/v62')
rep(MACT, 'Log.i(TAG, "native 3.14 started, version=$APP_VERSION sdk=${Build.VERSION.SDK_INT}")',
    'Log.i(TAG, "native 3.15 started, version=$APP_VERSION sdk=${Build.VERSION.SDK_INT}")',
    'стартовый лог 3.15')

# 2: PlenkaService — шапка
rep(MSVC, ' * ПЛЁНКА native 3.14: фоновый медиа-сервис — сворачивание БЕЗ PiP (страница v61).',
    ' * ПЛЁНКА native 3.15: фоновый медиа-сервис — сворачивание БЕЗ PiP (страница v62).',
    'шапка сервиса 3.15')

# 3: gradle — versionCode 144 / 3.15
rep(GRAD, 'versionCode = 143', 'versionCode = 144', 'versionCode 144')
rep(GRAD, 'versionName = "3.14"', 'versionName = "3.15"', 'versionName 3.15')

# 4: ассет = v62 байт-в-байт
shutil.copyfile(V62, ASSET)
a = open(ASSET, 'rb').read()
b = open(V62, 'rb').read()
assert a == b and len(a) > 700000
print('ok: assets/plenka.html = v62 (%d байт)' % len(a))
print('ГОТОВО: 3.15 / versionCode 144 / ассет v62')
