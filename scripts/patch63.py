#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kotlin 3.15 → 3.16: страница v63 + иконка v4 (Ё + перфорация плёнки).

Оболочка функционально НЕ менялась. Фиксы в странице v63: PiP из
миниплеера показывает видео (как из открытого), чистится подложка vblank
после крестика мини, fresh-гейт реестра (рестарт не делает все «новыми»
и не теряет позиции), 4К-буфер шире, индикация подгрузки на линии
перемотки убрана. Иконка: v4-checkers (Ё + янтарные шашки-перфорация).
Здесь: версия 3.16 / versionCode 145, ассет = v63 байт-в-байт.
"""
import io, shutil, sys

ROOT = '/home/z/my-project/plenka-native'
MACT = ROOT + '/app/src/main/java/ru/plenka/app/MainActivity.kt'
MSVC = ROOT + '/app/src/main/java/ru/plenka/app/PlenkaService.kt'
GRAD = ROOT + '/app/build.gradle.kts'
ASSET = ROOT + '/app/src/main/assets/plenka.html'
V63 = '/home/z/my-project/download/plenka-optimized-63.html'


def rep(path, old, new, what, cnt=1):
    src = io.open(path, encoding='utf-8').read()
    n = src.count(old)
    assert n == cnt, 'FAIL: якорь %r найден %d раз (ожидалось %d)' % (what, n, cnt)
    io.open(path, 'w', encoding='utf-8', newline='').write(src.replace(old, new))
    print('ok: %s' % what)


# 1: MainActivity — версия и стартовый лог
rep(MACT, 'private const val APP_VERSION = "PLENKA native 3.15 (v62)"',
    'private const val APP_VERSION = "PLENKA native 3.16 (v63)"', 'APP_VERSION 3.16/v63')
rep(MACT, 'Log.i(TAG, "native 3.15 started, version=$APP_VERSION sdk=${Build.VERSION.SDK_INT}")',
    'Log.i(TAG, "native 3.16 started, version=$APP_VERSION sdk=${Build.VERSION.SDK_INT}")',
    'стартовый лог 3.16')

# 2: PlenkaService — шапка
rep(MSVC, ' * ПЛЁНКА native 3.15: фоновый медиа-сервис — сворачивание БЕЗ PiP (страница v62).',
    ' * ПЛЁНКА native 3.16: фоновый медиа-сервис — сворачивание БЕЗ PiP (страница v63).',
    'шапка сервиса 3.16')

# 3: gradle — versionCode 145 / 3.16
rep(GRAD, 'versionCode = 144', 'versionCode = 145', 'versionCode 145')
rep(GRAD, 'versionName = "3.15"', 'versionName = "3.16"', 'versionName 3.16')

# 4: ассет = v63 байт-в-байт
shutil.copyfile(V63, ASSET)
a = open(ASSET, 'rb').read()
b = open(V63, 'rb').read()
assert a == b and len(a) > 700000
print('ok: assets/plenka.html = v63 (%d байт)' % len(a))
print('ГОТОВО: 3.16 / versionCode 145 / ассет v63 / иконка v4')
