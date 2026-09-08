#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kotlin 3.10 → 3.11 (v57).

1) Убираем диалог POST_NOTIFICATIONS: он всплывал поверх активити при
   ПЕРВОЙ игре (maybeBgRefresh) — активити уходила в onPause в момент
   старта воспроизведения, а на Android 14 диалог вообще не нужен:
   MediaStyle-уведомления показываются и без права (media exempt).
2) Версия 3.11 / v57, versionCode 140.

Фоновый сторож (пауза не от юзера → немедленно играем дальше) живёт в
странице v57: у JS есть и состояние юзерского намерения (обёртки
play()/pause()), и событие 'pause' от Chromium. Оболочке менять больше
нечего: WebView и так никогда не ставится на паузу, процесс в фоне
держит PlenkaService (mediaPlayback FGS + WakeLock).
"""
import sys, io

MAIN = '/home/z/my-project/plenka-native/app/src/main/java/ru/plenka/app/MainActivity.kt'
SRV = '/home/z/my-project/plenka-native/app/src/main/java/ru/plenka/app/PlenkaService.kt'
GRADLE = '/home/z/my-project/plenka-native/app/build.gradle.kts'

def patch(path, pairs):
    src = io.open(path, encoding='utf-8').read()
    for old, new, what in pairs:
        n = src.count(old)
        if n != 1:
            print('FAIL [%s]: якорь %r найден %d раз' % (path.split('/')[-1], what, n)); sys.exit(1)
        src = src.replace(old, new)
        print('ok [%s]: %s' % (path.split('/')[-1], what))
    io.open(path, 'w', encoding='utf-8').write(src)

patch(MAIN, [
    ('        private const val APP_VERSION = "PLENKA native 3.10 (v56)"',
     '        private const val APP_VERSION = "PLENKA native 3.11 (v57)"',
     'APP_VERSION 3.11/v57'),
    ('        private const val RC_NOTIF = 10\n',
     '',
     'RC_NOTIF убран (диалога больше нет)'),
    ('    @Volatile private var actFront = true\n    @Volatile private var notifAsked = false\n',
     '    @Volatile private var actFront = true\n',
     'notifAsked убран'),
    ('''        if (lastPlaying && actFront && !notifAsked && Build.VERSION.SDK_INT >= 33) {
            notifAsked = true
            try {
                if (checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)
                    != PackageManager.PERMISSION_GRANTED) {
                    /* разово и только по факту игры: медиа-панель в шторке на 13+
                       живёт и без права (MediaStyle exempt), спрашиваем для надёжности */
                    runOnUiThread {
                        try { requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), RC_NOTIF) }
                        catch (e: Exception) {}
                    }
                }
            } catch (e: Exception) {}
        }
''',
     '''        /* 3.11: диалог POST_NOTIFICATIONS убрали — он всплывал при ПЕРВОЙ игре и
           паузил активити в самый неподходящий момент; MediaStyle-уведомлениям
           право не нужно (media exempt), шторка живёт и так */
''',
     'диалог POST_NOTIFICATIONS убран'),
    ('        Log.i(TAG, "native 3.9 started, version=$APP_VERSION sdk=${Build.VERSION.SDK_INT}")',
     '        Log.i(TAG, "native 3.11 started, version=$APP_VERSION sdk=${Build.VERSION.SDK_INT}")',
     'стартовый лог 3.11'),
])

patch(SRV, [
    (' * ПЛЁНКА native 3.10: фоновый медиа-сервис — сворачивание БЕЗ PiP.',
     ' * ПЛЁНКА native 3.11: фоновый медиа-сервис — сворачивание БЕЗ PiP.\n * 3.11: страницу v57 сторожит видео от фоновых пауз Chromium сам (обёртки\n * play()/pause() метят юзерское намерение); сервис меняется только версией.',
     'заголовок 3.11'),
])

patch(GRADLE, [
    ('        versionCode = 130\n        versionName = "3.10"',
     '        versionCode = 140\n        versionName = "3.11"',
     'versionCode 140 / 3.11'),
])

print('OK: 3.11 (v57)')
