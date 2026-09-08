package ru.plenka.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.util.Log

/**
 * ПЛЁНКА native 3.16: фоновый медиа-сервис — сворачивание БЕЗ PiP (страница v63).
 * 3.13: PlenkaWebView держит страницу «видимой» для Chromium, пока играет
 * медиа (AwContents не узнаёт о скрытии окна → авто-паузы <video> нет
 * ВООБЩЕ — ни войны, ни заикания; хак SO 52028940). 3.12-ограничение
 * «3 попытки» в странице осталось страховкой на случай OEM-причуд.
 * Сервис: как в 3.10 — foreground+MediaStyle+WakeLock.
 *
 * Активность уходит в фон («домой»/рекенты/экран погас), но WebView остаётся
 * жив (webView.onPause оболочка НЕ вызывает принципиально) — звук и позиция
 * продолжают идти. Чтобы это не разваливалось через минуты, сервис делает
 * три вещи, без которых фон на Android 14 нежизнеспособен:
 *  1) foreground-сервис типа mediaPlayback — процесс НЕ убивается и НЕ
 *     замораживается (Android 12+ «cached app freezer» глушит фон намертво);
 *  2) медиа-уведомление (шторка/локскрин): пауза/играть, треки, стоп —
 *     кнопки возвращаются в активность (jsMediaFromBg → __plenkaMedia),
 *     позиция/заголовок приходят из MediaSession (mediaUpdate);
 *  3) partial WakeLock — экран погас и CPU уснул бы, декодер встал бы:
     держим машину включённой, пока что-то играет.
 *
 * Протокол: MainActivity.push(состояние) на каждом изменении плеера;
 * onStartCommand(ACT_START) идемпотентен (startForeground + refresh);
 * пауза в фоне дольше PAUSE_GRACE_MS — сервис гасит себя сам.
 */
class PlenkaService : Service() {

    companion object {
        private const val TAG = "PLENKA.BG"
        private const val CH_ID = "plenka_playback"
        private const val NID = 1
        private const val PAUSE_GRACE_MS = 60_000L

        const val ACT_START = "ru.plenka.bg.START"
        const val ACT_CMD = "ru.plenka.bg.CMD"
        const val ACT_STOP = "ru.plenka.bg.STOP"
        const val ACT_DELETE = "ru.plenka.bg.DELETE"

        @Volatile var running = false

        /* зеркало состояния плеера — обновляет активность */
        @Volatile var stPlaying = false
        @Volatile var stTitle = ""
        @Volatile var stArtist = ""
        @Volatile var stPosMs = 0L
        @Volatile var stDurMs = 0L

        /** активность зовёт на каждом изменении состояния плеера; сервис ещё
            не жив — поднимаем (startForegroundService), жив — обновляемся */
        fun push(ctx: Context, playing: Boolean, title: String, artist: String, posMs: Long, durMs: Long) {
            stPlaying = playing; stTitle = title; stArtist = artist; stPosMs = posMs; stDurMs = durMs
            val i = Intent(ctx, PlenkaService::class.java).setAction(ACT_START)
            try { ctx.startForegroundService(i) } catch (e: Exception) { Log.w(TAG, "push: ${e.message}") }
        }

        fun stop(ctx: Context) {
            try { ctx.stopService(Intent(ctx, PlenkaService::class.java)) } catch (e: Exception) {}
        }
    }

    private val hd = Handler(Looper.getMainLooper())
    private var wl: PowerManager.WakeLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        running = true
        Log.i(TAG, "bg service: onCreate")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACT_STOP, ACT_DELETE -> {          /* «стоп»/свайп уведомления — глушим звук и сервис */
                try { MainActivity.inst?.jsMediaFromBg("pause") } catch (e: Exception) {}
                stopSelf()
                return START_NOT_STICKY
            }
            ACT_CMD -> {
                val cmd = intent.getStringExtra("cmd")
                if (cmd != null) {
                    try { MainActivity.inst?.jsMediaFromBg(cmd) } catch (e: Exception) {}
                }
            }
        }
        refresh()
        return START_NOT_STICKY
    }

    /** пересборка уведомления + вейклок + отсчёт само-выкл. на паузе */
    private fun refresh() {
        try {
            val n = buildNotif()
            if (Build.VERSION.SDK_INT >= 29)
                startForeground(NID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK)
            else
                startForeground(NID, n)
            nm().notify(NID, n)
        } catch (e: Exception) { Log.w(TAG, "refresh: ${e.message}") }
        wlApply()
        hd.removeCallbacks(stopIfDead)
        if (!stPlaying) hd.postDelayed(stopIfDead, PAUSE_GRACE_MS)
    }

    private val stopIfDead = Runnable {       /* тишина в фоне дольше минуты — сервис не нужен */
        if (!stPlaying) {
            Log.i(TAG, "bg: пауза в фоне ${PAUSE_GRACE_MS / 1000}с — гасим сервис")
            stopSelf()
        } else refresh()
    }

    /* ═══ вейклок: экран погас, CPU не должен уснуть под декодер ═══ */

    private fun wlApply() {
        if (stPlaying) {
            if (wl == null) {
                try {
                    val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
                    wl = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "plenka:bgplay")
                        .also { it.setReferenceCounted(false) }
                } catch (e: Exception) { Log.w(TAG, "wl new: ${e.message}") }
            }
            try { wl?.let { if (!it.isHeld) { it.acquire(); Log.i(TAG, "bg: wakeLock взят") } } }
            catch (e: Exception) {}
        } else {
            try { wl?.let { if (it.isHeld) { it.release(); Log.i(TAG, "bg: wakeLock отпущен") } } }
            catch (e: Exception) {}
        }
    }

    /* ═══ уведомление (платформенный MediaStyle — androidx в проекте нет) ═══ */

    private fun nm(): NotificationManager =
        getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

    private fun ensureChannel() {
        try {
            val ch = NotificationChannel(CH_ID, "Фоновое воспроизведение",
                NotificationManager.IMPORTANCE_LOW)
            ch.description = "ПЛЁНКА: кнопки в шторке, когда приложение свёрнуто"
            ch.setShowBadge(false)
            nm().createNotificationChannel(ch)
        } catch (e: Exception) {}
    }

    private fun pi(action: String, cmd: String?): PendingIntent {
        val i = Intent(this, PlenkaService::class.java).setAction(action)
        if (cmd != null) i.putExtra("cmd", cmd)
        return PendingIntent.getService(this, action.hashCode(), i,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
    }

    @Suppress("DEPRECATION")  /* androidx нет по выбору проекта («ноль зависимостей») */
    private fun buildNotif(): Notification {
        ensureChannel()
        val open = PendingIntent.getActivity(this, 0,
            Intent(this, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

        val b = Notification.Builder(this, CH_ID)
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setContentTitle(if (stTitle.isNotEmpty()) stTitle else "ПЛЁНКА")
            .setContentText(if (stArtist.isNotEmpty()) stArtist else "фоновое воспроизведение")
            .setContentIntent(open)
            .setDeleteIntent(pi(ACT_DELETE, null))
            .setOnlyAlertOnce(true)
            .setOngoing(stPlaying)
            .setVisibility(Notification.VISIBILITY_PUBLIC)
            .setCategory(Notification.CATEGORY_TRANSPORT)

        b.addAction(Notification.Action.Builder(
            android.R.drawable.ic_media_previous, "Пред.", pi(ACT_CMD, "prev")).build())
        b.addAction(Notification.Action.Builder(
            if (stPlaying) android.R.drawable.ic_media_pause else android.R.drawable.ic_media_play,
            if (stPlaying) "Пауза" else "Играть",
            pi(ACT_CMD, if (stPlaying) "pause" else "play")).build())
        b.addAction(Notification.Action.Builder(
            android.R.drawable.ic_media_next, "След.", pi(ACT_CMD, "next")).build())
        b.addAction(Notification.Action.Builder(
            android.R.drawable.ic_delete, "Стоп", pi(ACT_STOP, null)).build())

        try {
            val style = Notification.MediaStyle()
            try { MainActivity.inst?.mediaToken()?.let { style.setMediaSession(it) } } catch (e: Exception) {}
            style.setShowActionsInCompactView(0, 1, 2)
            b.setStyle(style)
        } catch (e: Exception) { Log.w(TAG, "mediastyle: ${e.message}") }

        /* прогресс/время система рисует сама из PlaybackState MediaSession */
        return b.build()
    }

    override fun onDestroy() {
        running = false
        hd.removeCallbacksAndMessages(null)
        try { wl?.let { if (it.isHeld) it.release() } } catch (e: Exception) {}
        wl = null
        Log.i(TAG, "bg service: onDestroy")
        super.onDestroy()
    }
}
