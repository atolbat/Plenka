#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""натив 3.9 → 3.10: фоновое воспроизведение БЕЗ PiP (v56).

MainActivity: сворачивание («домой»/рекенты/экран погас) при играющем медиа
поднимает PlenkaService (новый файл — foreground mediaPlayback + медиа-
уведомление + WakeLock). WebView по-прежнему НЕ ставится на паузу никогда.
mediaUpdate запоминает состояние плеера и при живом/нужном фоне прокидывает
его сервису. onResume — сервис гасим (активность снова защищает процесс).
Манифест: FGS-права + <service>. Gradle: versionCode 130 / 3.10.
"""
import sys, io

KT = '/home/z/my-project/plenka-native/app/src/main/java/ru/plenka/app/MainActivity.kt'
MF = '/home/z/my-project/plenka-native/app/src/main/AndroidManifest.xml'
GR = '/home/z/my-project/plenka-native/app/build.gradle.kts'

def patch(path, subs):
    src = io.open(path, encoding='utf-8').read()
    for old, new, what in subs:
        n = src.count(old)
        if n != 1:
            print('FAIL [%s]: якорь %r найден %d раз' % (path.rsplit('/', 1)[-1], what, n)); sys.exit(1)
        src = src.replace(old, new)
        print('ok [%s]: %s' % (path.rsplit('/', 1)[-1], what))
    io.open(path, 'w', encoding='utf-8').write(src)

# ── MainActivity.kt ──────────────────────────────────────────────────────────
patch(KT, [
    # 1. версия + RC_NOTIF + inst
    ("""        private const val APP_VERSION = "PLENKA native 3.9 (v55)"
        private const val RC_PERM = 7
        private const val RC_PICK = 8
        private const val RC_FILE = 9""",
     """        private const val APP_VERSION = "PLENKA native 3.10 (v56)"
        private const val RC_PERM = 7
        private const val RC_PICK = 8
        private const val RC_FILE = 9
        private const val RC_NOTIF = 10""",
     'версия 3.10 + RC_NOTIF'),

    ("""        private val RANGE_RE = Regex("bytes=(\\\\d*)-(\\\\d*)")""",
     """        private val RANGE_RE = Regex("bytes=(\\\\d*)-(\\\\d*)")

        @Volatile var inst: MainActivity? = null   /* 3.10: кнопки фонового сервиса найдут активити */""",
     'companion.inst'),

    # 2. поля состояния фона
    ("""    @Volatile private var lastVideoW = 0   /* 3.7: аспект PiP-окна из текущего видео (mediaState) */
    @Volatile private var lastVideoH = 0""",
     """    @Volatile private var lastVideoW = 0   /* 3.7: аспект PiP-окна из текущего видео (mediaState) */
    @Volatile private var lastVideoH = 0
    /* 3.10: фоновый режим без PiP — зеркало состояния плеера и где активность */
    @Volatile private var lastPlaying = false
    @Volatile private var lastTitle = ""
    @Volatile private var lastArtist = ""
    @Volatile private var lastPosMs = 0L
    @Volatile private var lastDurMs = 0L
    @Volatile private var actFront = true
    @Volatile private var notifAsked = false""",
     'поля фона'),

    # 3. onCreate: inst
    ("""    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        pool = Executors.newCachedThreadPool()""",
     """    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        inst = this                       /* 3.10: фоновый сервис из шторки найдёт активити */

        pool = Executors.newCachedThreadPool()""",
     'onCreate inst'),

    # 4. onResume: actFront + погасить сервис
    ("""    override fun onResume() {
        super.onResume()
        // диалог могли отклонить мимоходом или выдать право в настройках —""",
     """    override fun onResume() {
        super.onResume()
        actFront = true
        if (PlenkaService.running && !inPip) {   /* 3.10: вернулись — процесс снова защищён
            активностью, фоновое медиа-уведомление гасим (звук не трогаем) */
            PlenkaService.stop(this)
            Log.i(TAG, "bg: активность на экране — сервис погашен")
        }
        // диалог могли отклонить мимоходом или выдать право в настройках —""",
     'onResume гасит сервис'),

    # 5. onPause/onStop (новые) перед onDestroy
    ("""    override fun onDestroy() {
        server?.stop()""",
     """    override fun onPause() {
        super.onPause()
        /* 3.10: экран погас или поверх всплыл диалог — onUserLeaveHint сюда НЕ приходит,
           а звук обязан жить. WebView не глушим (как и всегда), процесс держит сервис */
        bgStartIfNeeded("pause")
    }

    override fun onStop() {
        super.onStop()
        actFront = false
    }

    override fun onDestroy() {
        server?.stop()""",
     'onPause/onStop'),

    # 6. onDestroy: стоп сервиса + inst=null
    ("""        try { webView.destroy() } catch (e: Exception) {}
        super.onDestroy()
    }""",
     """        PlenkaService.stop(this)
        try { webView.destroy() } catch (e: Exception) {}
        inst = null
        super.onDestroy()
    }""",
     'onDestroy сервис'),

    # 7. onUserLeaveHint: фон вместо PiP + bgStartIfNeeded
    ("""    override fun onUserLeaveHint() {
        if (pipAuto && !isFinishing && Build.VERSION.SDK_INT >= 26 && !inPip) {
            try { enterPictureInPictureMode(pipParams(true)) }
            catch (e: Exception) { Log.w(TAG, "pip auto: ${e.message}") }
        }
    }""",
     """    override fun onUserLeaveHint() {
        if (pipAuto && !isFinishing && Build.VERSION.SDK_INT >= 26 && !inPip) {
            try { enterPictureInPictureMode(pipParams(true)) }
            catch (e: Exception) { Log.w(TAG, "pip auto: ${e.message}") }
            return
        }
        /* 3.10: сворачивание БЕЗ PiP — «домой»/рекенты при играющем медиа поднимают
           фоновый сервис (шторка/локскрин/WakeLock/незамерзание). Здесь приложение
           ещё считается «на переднем плане» — старт легален всегда */
        bgStartIfNeeded("userLeave")
    }

    /** 3.10: пусть фоновый сервис держит процесс, если что-то играет */
    private fun bgStartIfNeeded(why: String) {
        if (isFinishing || inPip || pipAuto || !lastPlaying) return
        try {
            PlenkaService.push(this, lastPlaying, lastTitle, lastArtist, lastPosMs, lastDurMs)
            Log.i(TAG, "bg: сервис запущен ($why) «${lastTitle.take(32)}» " +
                "${lastPosMs / 1000}с/${lastDurMs / 1000}с")
        } catch (e: Exception) { Log.w(TAG, "bg start ($why): ${e.message}") }
    }""",
     'onUserLeaveHint фон + bgStartIfNeeded'),

    # 8. PiP: сервис не нужен
    ("""        if (isInPictureInPictureMode) {
            // страховка от фриза: активность прошла onPause, но остаётся видимой —""",
     """        if (isInPictureInPictureMode) {
            PlenkaService.stop(this)   /* 3.10: видимое PiP-окно само держит процесс */
            // страховка от фриза: активность прошла onPause, но остаётся видимой —""",
     'PiP гасит сервис'),

    # 9. jsMediaFromBg + mediaToken
    ("""    private fun jsMedia(cmd: String) {""",
     """    /** 3.10: кнопки фонового уведомления (шторка/локскрин) → страница */
    fun jsMediaFromBg(cmd: String) { jsMedia(cmd) }

    /** 3.10: токен MediaSession для MediaStyle-уведомления сервиса */
    fun mediaToken(): android.media.session.MediaSession.Token? =
        try { mediaSession?.sessionToken } catch (e: Exception) { null }

    private fun jsMedia(cmd: String) {""",
     'jsMediaFromBg/mediaToken'),

    # 10. mediaUpdate: запоминание + прокид в сервис
    ("""                val title = o.optString("title", "")
                if (title.isNotEmpty()) {
                    ms.setMetadata(MediaMetadata.Builder()
                        .putString(MediaMetadata.METADATA_KEY_TITLE, title)
                        .putString(MediaMetadata.METADATA_KEY_ARTIST, o.optString("artist", ""))
                        .putLong(MediaMetadata.METADATA_KEY_DURATION, dur)
                        .build())
                }""",
     """                val title = o.optString("title", "")
                if (title.isNotEmpty()) {
                    ms.setMetadata(MediaMetadata.Builder()
                        .putString(MediaMetadata.METADATA_KEY_TITLE, title)
                        .putString(MediaMetadata.METADATA_KEY_ARTIST, o.optString("artist", ""))
                        .putLong(MediaMetadata.METADATA_KEY_DURATION, dur)
                        .build())
                }
                /* 3.10: запоминаем состояние; работаем фоном (или сервис уже жив) —
                   прокидываем в медиа-сервис: шторка обновит кнопки/заголовок,
                   WakeLock сменится, пауза в фоне начнёт отсчёт само-выкл. */
                lastPlaying = playing
                lastPosMs = pos; lastDurMs = dur
                if (title.isNotEmpty()) { lastTitle = title; lastArtist = o.optString("artist", "") }
                maybeBgRefresh()""",
     'mediaUpdate фон'),

    # 11. maybeBgRefresh
    ("""    private fun srvRec(line: String) {""",
     """    /** 3.10: состояние плеера поменялось — жить ли фоновому сервису */
    private fun maybeBgRefresh() {
        if (lastPlaying && actFront && !notifAsked && Build.VERSION.SDK_INT >= 33) {
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
        if (!PlenkaService.running && actFront) return   /* на экране сервис не нужен */
        try { PlenkaService.push(this, lastPlaying, lastTitle, lastArtist, lastPosMs, lastDurMs) }
        catch (e: Exception) { Log.w(TAG, "bg refresh: ${e.message}") }
    }

    private fun srvRec(line: String) {""",
     'maybeBgRefresh'),
])

# ── AndroidManifest.xml ──────────────────────────────────────────────────────
patch(MF, [
    ("""    <!-- 2.4: системные медиа-кнопки (шторка/наушники/локскрин) -->
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />""",
     """    <!-- 2.4: системные медиа-кнопки (шторка/наушники/локскрин) -->
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <!-- 3.10: фоновое воспроизведение без PiP -->
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK" />
    <uses-permission android:name="android.permission.WAKE_LOCK" />""",
     'FGS-права'),

    ("""        </activity>
    </application>""",
     """        </activity>

        <!-- 3.10: фоновый медиа-сервис — сворачивание без PiP -->
        <service
            android:name=".PlenkaService"
            android:exported="false"
            android:foregroundServiceType="mediaPlayback" />
    </application>""",
     'service в манифесте'),
])

# ── app/build.gradle.kts ─────────────────────────────────────────────────────
patch(GR, [
    ("""        versionCode = 120
        versionName = "3.9\"""",
     """        versionCode = 130
        versionName = "3.10\"""",
     'versionCode 130'),
])

print('OK: натив 3.10 пропатчен')
