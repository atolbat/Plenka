#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kotlin 3.12 → 3.13: страница «не замечает» сворачивание, пока играет медиа.

ПРИЧИНА фоновой паузы (репорт v58: «сворачиваю — пауза слишком долгая, ты
отменяешь паузу, и это очень сильно слышно»): Chromium гасит <video> на
скрытой странице. Цепочка (по исходникам Chromium android_webview/
AwContents.java): View.onWindowVisibilityChanged(GONE) при уходе активити →
AwContents.onWindowVisibilityChanged → setWindowVisibilityInternal →
updateWebContentsVisibility → WebContents скрыт → document.hidden=true →
авто-пауза медиа. Оболочка НИКОГДА не зовёт webView.onPause(), но колбэк
видимости окна приезжает сам. JS-сторож v58 ограничил войну 3 попытками —
на слух это заикание и всё равно тишина: причину с страницы не победить.

ЛЕЧЕНИЕ (проверенный хак SO 52028940 / 53723297): subclass WebView,
onWindowVisibilityChanged передаёт super-у ALWAYS View.VISIBLE, пока играет
медиа (lastPlaying из mediaState) и мы не в PiP — Chromium не узнаёт о
скрытии → НЕ гасит элемент вообще: ни паузы, ни заикания, ни войны.
Юзер поставил паузу (шторка/страница) → mediaUpdate → refreshBgPolicy() —
обман снимается, страница честно спрывает окно, батарея не течёт.

Плюс: setRendererPriorityPolicy(RENDERER_PRIORITY_IMPORTANT, false) —
рендерер не демотируется в фоне (медиа-сервис и так держит процесс).
"""
import sys, io

F = '/home/z/my-project/plenka-native/app/src/main/java/ru/plenka/app/MainActivity.kt'
src = io.open(F, encoding='utf-8').read()

def rep(old, new, what, cnt=1):
    global src
    n = src.count(old)
    if n != cnt:
        print('FAIL: якорь %r найден %d раз (ожидалось %d)' % (what, n, cnt))
        sys.exit(1)
    src = src.replace(old, new)
    print('ok: %s' % what)

# ── 1: версия ───────────────────────────────────────────────────────────────
rep('private const val APP_VERSION = "PLENKA native 3.12 (v58)"',
    'private const val APP_VERSION = "PLENKA native 3.13 (v59)"', 'APP_VERSION 3.13')

rep('Log.i(TAG, "native 3.12 started, version=$APP_VERSION sdk=${Build.VERSION.SDK_INT}")',
    'Log.i(TAG, "native 3.13 started, version=$APP_VERSION sdk=${Build.VERSION.SDK_INT}")',
    'стартовый лог 3.13')

# ── 2: PlenkaWebView — окно «остаётся видимым», пока играет медиа ──────────
rep("""        webView = WebView(this)""",
    """        webView = PlenkaWebView(this)""",
    'webView → PlenkaWebView')

# ── 3: класс PlenkaWebView + keepPageVisible ────────────────────────────────
rep("""    override fun onPictureInPictureModeChanged(isInPictureInPictureMode: Boolean, newConfig: Configuration) {""",
    """    /* ═══ 3.13: страница «не замечает» уход окна в фон, пока играет медиа ═══
       AwContents узнаёт о скрытии окна через View.onWindowVisibilityChanged →
       setWindowVisibilityInternal → document.hidden → авто-пауза <video>
       (репорт v58: «сворачиваю — пауза слышна, отмена слышна, потом тишина»;
       JS-сторож воевать с этим не может в принципе). Единственный колбэк,
       через который WebView узнаёт о скрытии, подменяем: окно «остаётся
       видимым», пока играет медиа и мы не в PiP. Хак SO 52028940/53723297,
       механизм сверен с AwContents.java. Пауза юзера → mediaUpdate →
       refreshBgPolicy(): обман снят — страница честно спит. */
    private inner class PlenkaWebView(ctx: Context) : WebView(ctx) {
        @Volatile private var realVis = View.VISIBLE
        override fun onWindowVisibilityChanged(visibility: Int) {
            val prev = realVis
            realVis = visibility
            val lie = visibility != View.VISIBLE && keepPageVisible()
            if (lie && prev == View.VISIBLE)
                Log.i(TAG, "bg: окно скрыто ($visibility), медиа играет — страница остаётся «видимой»")
            if (!lie && prev != View.VISIBLE && visibility != View.VISIBLE)
                Log.i(TAG, "bg: окно скрыто ($visibility), медиа не играет — честно скрываем страницу")
            super.onWindowVisibilityChanged(if (lie) View.VISIBLE else visibility)
        }
        fun refreshBgPolicy() {          /* пауза/старт БЕЗ события окна: пересчёт политики */
            try {
                val lie = realVis != View.VISIBLE && keepPageVisible()
                super.onWindowVisibilityChanged(if (lie) View.VISIBLE else realVis)
            } catch (e: Exception) {}
        }
    }

    fun keepPageVisible(): Boolean = lastPlaying && !inPip && !isFinishing

    override fun onPictureInPictureModeChanged(isInPictureInPictureMode: Boolean, newConfig: Configuration) {""",
    'класс PlenkaWebView')

# ── 4: renderer priority ────────────────────────────────────────────────────
rep("""            setGeolocationEnabled(false)
        }""",
    """            setGeolocationEnabled(false)
            setRendererPriorityPolicy(WebSettings.RENDERER_PRIORITY_IMPORTANT, false)   /* 3.13: рендерер не демотируется в фоне */
        }""",
    'renderer priority IMPORTANT')

# ── 5: mediaUpdate — пересчёт политики фона при смене playing ───────────────
rep("""                lastPlaying = playing
                lastPosMs = pos; lastDurMs = dur""",
    """                lastPlaying = playing
                lastPosMs = pos; lastDurMs = dur
                try { (webView as? PlenkaWebView)?.refreshBgPolicy() } catch (e: Exception) {}   /* 3.13: паузнули в фоне — страницу честно спрятать; заиграли — держать «видимой» */""",
    'mediaUpdate → refreshBgPolicy')

io.open(F, 'w', encoding='utf-8', newline='').write(src)
print('MainActivity.kt: 3.13 записан')

# ── gradle: versionCode 142 / 3.13 ──────────────────────────────────────────
G = '/home/z/my-project/plenka-native/app/build.gradle.kts'
g = io.open(G, encoding='utf-8').read()
assert g.count('versionCode = 141') == 1 and g.count('versionName = "3.12"') == 1
g = g.replace('versionCode = 141', 'versionCode = 142').replace('versionName = "3.12"', 'versionName = "3.13"')
io.open(G, 'w', encoding='utf-8', newline='').write(g)
print('gradle: versionCode=142 / 3.13')

# ── PlenkaService: шапка ────────────────────────────────────────────────────
S = '/home/z/my-project/plenka-native/app/src/main/java/ru/plenka/app/PlenkaService.kt'
s = io.open(S, encoding='utf-8').read()
old = """ * ПЛЁНКА native 3.12: фоновый медиа-сервис — сворачивание БЕЗ PiP.
 * 3.12: страница v58 помирилась с Chromium: гейт «звук после первого кадра»
 * в фоне снимается (muted-видео Chromium гасит легально — был шторм пауз
 * 30Гц), чужие паузы отменяются максимум 3 попытками с шагом 700мс, потом
 * тишина до возврата на экран; сервис не менялся."""
new = """ * ПЛЁНКА native 3.13: фоновый медиа-сервис — сворачивание БЕЗ PiP.
 * 3.13: PlenkaWebView держит страницу «видимой» для Chromium, пока играет
 * медиа (AwContents не узнаёт о скрытии окна → авто-паузы <video> нет
 * ВООБЩЕ — ни войны, ни заикания; хак SO 52028940). 3.12-ограничение
 * «3 попытки» в странице осталось страховкой на случай OEM-причуд.
 * Сервис: как в 3.10 — foreground+MediaStyle+WakeLock."""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(S, 'w', encoding='utf-8', newline='').write(s)
print('PlenkaService.kt: шапка 3.13')
