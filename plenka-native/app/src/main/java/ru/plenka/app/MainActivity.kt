package ru.plenka.app

import android.annotation.SuppressLint
import android.app.Activity
import android.app.PictureInPictureParams
import android.content.ClipData
import android.content.ContentUris
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.AssetFileDescriptor
import android.content.res.Configuration
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.ParcelFileDescriptor
import android.provider.MediaStore
import android.provider.OpenableColumns
import android.util.Log
import android.util.Rational
import android.view.View
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.view.WindowManager
import android.system.Os
import android.widget.Toast
import android.webkit.ConsoleMessage
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.nio.ByteBuffer
import java.util.Locale
import android.graphics.Bitmap
import android.graphics.Matrix
import android.media.MediaMetadata
import android.media.session.MediaSession
import android.media.session.PlaybackState
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.Future
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * ПЛЁНКА native 2.1 — оболочка APK.
 *
 * Архитектура:
 *  - WebView грузит приложение с собственного HTTP-сервера (127.0.0.1:8977):
 *    стабильный origin → IndexedDB (библиотека, позиции, плейлисты) переживает
 *    любые перезапуски, как в браузере;
 *  - медиафайлы НЕ копируются: /v/<id> и /a/<id> резолвятся в ContentResolver
 *    по id MediaStore при каждом запросе, отдача — потоком с Range. Реестра
 *    нет в принципе → «рестарт ломает видео» исчезает как класс;
 *  - /c/<id> — файлы, добавленные вручную через SAF: content-URI лежит в
 *    персистентном реестре (filesDir/picked.json + takePersistableUriPermission),
 *    переживает рестарты; длительность/размеры — MediaMetadataRetriever при выборе;
 *  - скан библиотеки — запрос к MediaStore ВСЕХ томов (внутренний + SD),
 *    фильтр по браузерно-играбельным контейнерам (ts/mkv/avi… отрезаны);
 *  - 2.1: разрешение на медиа оболочка просит САМА при старте и на каждом
 *    onResume (раньше просила страница — цепочка могла порваться тихо);
 *    скан возвращает конверт {ok,err,n,items} — пусто из-за права ≠ пусто
 *    по факту, страница больше не молчит;
 *  - onShowFileChooser: <input type=file> в WebView без него не открывается
 *    вовсе — теперь работает как запасной путь;
 *  - PiP — режим активности: WebView продолжает рендерить (мы НИКОГДА не
 *    вызываем webView.onPause), страница по __pipMode схлопывает UI до видео;
 *  - системный «назад» — страница (__plenkaBack) закрывает верхний слой,
 *    затем WebView-стек (history), только потом приложение уходит в фон.
 */
class MainActivity : Activity() {

    companion object {
        private const val TAG = "PLENKA"
        private const val PORT = 8977
        private const val APP_VERSION = "PLENKA native 3.13 (v59)"
        private const val RC_PERM = 7
        private const val RC_PICK = 8
        private const val RC_FILE = 9

        /* контейнеры, которые Chromium в WebView реально декодирует */
        private val VIDEO_EXT = setOf("mp4", "m4v", "webm", "mov", "3gp", "3g2", "3gpp")
        private val AUDIO_EXT = setOf("mp3", "m4a", "aac", "ogg", "oga", "opus", "wav", "flac", "m4b")
        /* контейнеры, которые телефон считает видео, но браузер не откроет — отрезаем сразу */
        private val DEAD_EXT = setOf(
            "ts", "mts", "m2ts", "mkv", "mka", "avi", "wmv", "flv", "f4v",
            "vob", "mpg", "mpeg", "m1v", "m2v", "asf", "rm", "rmvb", "divx", "amr", "wma"
        )
        private val MEDIA_ID = Regex("^/(v|a|c)/(\\d+)$")
        private val THUMB_ID = Regex("^/t/(v|a|c)/(\\d+)$")
        private val RANGE_RE = Regex("bytes=(\\d*)-(\\d*)")

        @Volatile var inst: MainActivity? = null   /* 3.10: кнопки фонового сервиса найдут активити */
    }

    private lateinit var webView: WebView
    private var server: PlenkaServer? = null
    private lateinit var pool: ExecutorService
    private lateinit var thumbPool: ExecutorService     /* 2.4: генерация миниатюр — отдельно от раздачи */
    private lateinit var nativeBridge: NativeBridge     /* 2.4: единственный экземпляр моста — для rebridge */
    private var mediaSession: MediaSession? = null      /* 2.4: системные медиа-кнопки (шторка/наушники/локскрин) */
    private val srvRing = ArrayDeque<String>()          /* 2.4: журнал HTTP-сервера — виден в ДИАГ; 2.5: 160 строк */
    @Volatile private var lastScanJson: String? = null /* 3.5: /list отдаёт последний скан — без пересканирования */
    @Volatile private var lastScanAt = 0L               /* 3.8: конверт моложе 2с — из кэша (бут синкает дважды) */
    @Volatile private var lastResumePush = 0L           /* 3.8: PiP-циклы дёргают onResume каждые 5-8с */
    private val thumbInflight = ConcurrentHashMap<String, Future<ThumbRes>>()

    /* ═══ 3.9: ovh — кэш дескрипторов для MSE-фетчей страницы (как в 3.6) ═══
       Мост страницы качает гигантов сотнями коротких Range-запросов (?ovh=0):
       без кэша каждый заново открывает дескриптор через ContentResolver/FUSE.
       Os.pread не двигает позицию fd и не закрывает его — параллельные Range
       на один файл не ломают друг друга, канал не закрывается (в отличие от
       FileChannel.close(), который гасит fd наглухо). LRU 6, простой 45с. */
    private class FdEntry(val afd: AssetFileDescriptor, val size: Long, val mime: String, val etag: String) {
        @Volatile var last: Long = System.currentTimeMillis()
    }
    private val fdLock = Any()
    private val fdCache = HashMap<String, FdEntry>()

    private fun fdGet(key: String): FdEntry? = synchronized(fdLock) {
        val now = System.currentTimeMillis()
        val iter = fdCache.entries.iterator()
        while (iter.hasNext()) {                        /* 45с без запросов — закрываем */
            val en = iter.next()
            if (now - en.value.last > 45_000) {
                try { en.value.afd.close() } catch (e: Exception) {}
                srvRec("fd-cache: ${en.key} закрыт по простою 45с")
                iter.remove()
            }
        }
        fdCache[key]
    }
    private fun fdPut(key: String, e: FdEntry) {
        synchronized(fdLock) {
            val old = fdCache.put(key, e)
            if (old != null && old !== e) { try { old.afd.close() } catch (ex: Exception) {} }
            if (fdCache.size > 6) {                     /* LRU: выкидываем самый холодный */
                var minK: String? = null
                var minV = Long.MAX_VALUE
                for ((k, v) in fdCache) if (v.last < minV) { minV = v.last; minK = k }
                val v = minK?.let { fdCache.remove(it) }
                if (v != null) { try { v.afd.close() } catch (ex: Exception) {} }
            }
        }
    }
    private fun fdDrop(key: String) {
        synchronized(fdLock) {
            val v = fdCache.remove(key) ?: return
            try { v.afd.close() } catch (e: Exception) {}
        }
    }

    @Volatile private var pipAuto = false   // видео играет → home-жест сворачивает в PiP
    @Volatile private var inPip = false
    @Volatile private var permDialogUp = false
    @Volatile private var lastVideoW = 0   /* 3.7: аспект PiP-окна из текущего видео (mediaState) */
    @Volatile private var lastVideoH = 0
    /* 3.10: фоновый режим без PiP — зеркало состояния плеера и где активность */
    @Volatile private var lastPlaying = false
    @Volatile private var lastTitle = ""
    @Volatile private var lastArtist = ""
    @Volatile private var lastPosMs = 0L
    @Volatile private var lastDurMs = 0L
    @Volatile private var actFront = true
    private var pendingFcb: ValueCallback<Array<Uri>>? = null

    /* ═══ реестр ручного выбора (SAF) — переживает рестарты ═══ */

    private class PReg(
        val seq: Long, val uri: Uri,
        var name: String, var mime: String, var size: Long,
        var dur: Long, var w: Int, var h: Int, var t: Long, val k: String
    )

    private val regLock = Any()
    private val pickedReg = ArrayList<PReg>()
    private var regLoaded = false

    private fun regLoad() {
        if (regLoaded) return
        synchronized(regLock) {
            if (regLoaded) return
            try {
                val f = File(filesDir, "picked.json")
                if (f.exists()) {
                    val a = JSONArray(f.readText())
                    for (i in 0 until a.length()) {
                        val o = a.getJSONObject(i)
                        pickedReg.add(PReg(
                            o.getLong("seq"), Uri.parse(o.getString("uri")),
                            o.optString("n", ""), o.optString("m", ""),
                            o.optLong("s", 0), o.optLong("d", 0),
                            o.optInt("w", 0), o.optInt("h", 0), o.optLong("t", 0),
                            if (o.optString("k") == "a") "a" else "v"
                        ))
                    }
                }
            } catch (e: Exception) { Log.w(TAG, "regLoad: ${e.message}") }
            regLoaded = true
        }
    }

    private fun regSave() {
        synchronized(regLock) {
            try {
                val a = JSONArray()
                for (r in pickedReg) a.put(JSONObject()
                    .put("seq", r.seq).put("uri", r.uri.toString())
                    .put("n", r.name).put("m", r.mime).put("s", r.size)
                    .put("d", r.dur).put("w", r.w).put("h", r.h).put("t", r.t).put("k", r.k))
                File(filesDir, "picked.json").writeText(a.toString())
            } catch (e: Exception) { Log.w(TAG, "regSave: ${e.message}") }
        }
    }

    private val readPerms: Array<String>
        get() = if (Build.VERSION.SDK_INT >= 33)
            arrayOf(android.Manifest.permission.READ_MEDIA_VIDEO, android.Manifest.permission.READ_MEDIA_AUDIO)
        else arrayOf(android.Manifest.permission.READ_EXTERNAL_STORAGE)

    /** ok — всё выдано; partial — Android 14 «только выбранные» или половина прав (скан видит часть);
        none — не видно ничего, надо просить. 2.2: partial больше не считается «нет прав» —
        скан честно отдаёт выбранное, без вечного переспрашивания */
    private fun mediaPermState(): String {
        fun granted(p: String) = checkSelfPermission(p) == PackageManager.PERMISSION_GRANTED
        if (Build.VERSION.SDK_INT >= 33) {
            val v = granted(android.Manifest.permission.READ_MEDIA_VIDEO)
            val a = granted(android.Manifest.permission.READ_MEDIA_AUDIO)
            if (v && a) return "ok"
            var partial = v || a
            if (Build.VERSION.SDK_INT >= 34) {
                try {
                    if (granted(android.Manifest.permission.READ_MEDIA_VISUAL_USER_SELECTED)) partial = true
                } catch (e: Exception) {}
            }
            return if (partial) "partial" else "none"
        }
        return if (granted(android.Manifest.permission.READ_EXTERNAL_STORAGE)) "ok" else "none"
    }

    fun hasMediaPerm(): Boolean = mediaPermState() != "none"

    /* ═══════════════ жизненный цикл ═══════════════ */

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        inst = this                       /* 3.10: фоновый сервис из шторки найдёт активити */

        pool = Executors.newCachedThreadPool()
        thumbPool = Executors.newFixedThreadPool(2)
        server = PlenkaServer(this).also { it.start() }

        webView = PlenkaWebView(this)
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true            // IndexedDB приложения
            mediaPlaybackRequiresUserGesture = false
            setSupportZoom(false)
            builtInZoomControls = false
            textZoom = 100                      // системный масштаб шрифта не ломает вёрстку
            cacheMode = WebSettings.LOAD_DEFAULT
            allowFileAccess = false
            allowContentAccess = true     /* 2.2: <input type=file>-фолбэк получает content:// — без этого WebView их не читает */
            setGeolocationEnabled(false)
        }
        webView.setRendererPriorityPolicy(WebView.RENDERER_PRIORITY_IMPORTANT, false)   /* 3.13: рендерер не демотируется в фоне — медиа живёт */
        webView.setBackgroundColor(0xFF0D0B09.toInt())
        webView.overScrollMode = View.OVER_SCROLL_NEVER

        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val u = request.url
                // наружу приложение не ходит: только собственный сервер
                val mine = "http".equals(u.scheme, ignoreCase = true) && "127.0.0.1".equals(u.host) && u.port == PORT
                return !mine
            }
            override fun onReceivedError(view: WebView, errorCode: Int, description: String?, failingUrl: String?) {
                if (failingUrl?.startsWith("http://127.0.0.1") == true) {
                    Log.e(TAG, "webview err $errorCode $description @ $failingUrl")
                }
            }
            /* 2.2: зонд живости после загрузки — если главный скрипт или мост мертвы,
               пользователь узнает тостом (ошибка больше не может быть «тихой»),
               а если всё живо — сразу толкаем синк, закрывая гонку «право выдано до загрузки» */
            override fun onPageFinished(view: WebView, url: String) {
                super.onPageFinished(view, url)
                Log.i(TAG, "page loaded: $url")
                webView.evaluateJavascript(
                    "(function(){try{return{diag:!!window.__plenkaDiag," +
                        "main:!!(window.__plenkaDiag&&window.__plenkaDiag.marks['main-start'])," +
                        "bridge:typeof window.PlenkaNative}}catch(e){return{diag:false,main:false,bridge:'ERR'}}})()"
                ) { res ->
                    var diag = false
                    var main = false
                    var bridge = "?"
                    try {
                        val s = res?.trim()
                        if (!s.isNullOrEmpty() && s != "null") {
                            val o = JSONObject(s)
                            diag = o.optBoolean("diag")
                            main = o.optBoolean("main")
                            bridge = o.optString("bridge")
                        }
                    } catch (e: Exception) { Log.w(TAG, "probe parse: ${e.message}") }
                    Log.i(TAG, "probe: diag=$diag main=$main bridge=$bridge")
                    if (diag && main && bridge == "object") {
                        webView.evaluateJavascript("window.__plenkaResume&&window.__plenkaResume()", null)
                    } else {
                        val why = when {
                            bridge != "object" -> "мост не виден странице ($bridge)"
                            !main -> "главный скрипт страницы не поднялся"
                            else -> "диагностика недоступна"
                        }
                        Log.e(TAG, "PAGE NOT ALIVE: $why")
                        runOnUiThread {
                            try {
                                Toast.makeText(applicationContext,
                                    "ПЛЁНКА: $why — нажмите «ДИАГ» справа вверху и пришлите отчёт",
                                    Toast.LENGTH_LONG).show()
                            } catch (e: Exception) {}
                        }
                    }
                }
            }
        }
        webView.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(m: ConsoleMessage): Boolean {
                Log.d(TAG, "js: ${m.message()} @${m.sourceId()}:${m.lineNumber()}")
                return true
            }
            /* 2.1: <input type=file> в WebView без этого метода не открывается ВООБЩЕ —
               главный «вручную пикер не открывается». Запасной путь для браузерного режима */
            override fun onShowFileChooser(
                wv: WebView, cb: ValueCallback<Array<Uri>>, params: FileChooserParams
            ): Boolean {
                pendingFcb?.onReceiveValue(null)
                pendingFcb = cb
                var i = try { params.createIntent() } catch (e: Exception) { null }
                if (i == null) try {            /* 2.2: свой интент, если системный не собрался */
                    i = Intent(Intent.ACTION_GET_CONTENT)
                    i.type = "*/*"
                    i.putExtra(Intent.EXTRA_MIME_TYPES, arrayOf("video/*", "audio/*"))
                } catch (e: Exception) {}
                if (i != null) {
                    i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
                    try { startActivityForResult(i, RC_FILE); return true }
                    catch (e: Exception) { Log.w(TAG, "filechoose: ${e.message}") }
                }
                pendingFcb = null
                return false
            }
        }
        nativeBridge = NativeBridge()
        webView.addJavascriptInterface(nativeBridge, "PlenkaNative")
        setContentView(webView)
        mediaInit()

        // сервер уже слушает (bind синхронный в start()) — страница не получит connection refused
        webView.loadUrl("http://127.0.0.1:$PORT/")
        Log.i(TAG, "native 3.13 started, version=$APP_VERSION sdk=${Build.VERSION.SDK_INT}")

        // 2.1: право просит сама оболочка, не полагаясь на цепочку страница→мост
        maybeAskPerm()
    }

    override fun onResume() {
        super.onResume()
        actFront = true
        // 3.12: страховка — WebView мы НИКОГДА не ставим на паузу сами, но OEM-глушилки
        // (HiOS/энергосбережение) иногда гасят рендер/звук за нас; onResume выводит
        // его из чужой паузы — цена вызова нулевая, картинка/звук оживают сразу
        try { webView.onResume() } catch (e: Exception) {}
        if (PlenkaService.running && !inPip) {   /* 3.10: вернулись — процесс снова защищён
            активностью, фоновое медиа-уведомление гасим (звук не трогаем) */
            PlenkaService.stop(this)
            Log.i(TAG, "bg: активность на экране — сервис погашен")
        }
        // диалог могли отклонить мимоходом или выдать право в настройках —
        // на каждом возврате: спрашиваем, пока не выдано; пересканируем, если выдано
        maybeAskPerm()
        if (hasMediaPerm()) {
            val now = System.currentTimeMillis()
            if (now - lastResumePush >= 6000) {       /* 3.8: PiP-циклы будят активность каждые
                5-8с — полный синк страницы каждый раз и был «лагами»; толкаем не чаще 6с */
                lastResumePush = now
                webView.post {
                    webView.evaluateJavascript("window.__plenkaResume?window.__plenkaResume():'нет'") { res ->
                        Log.i(TAG, "resume push → ${res?.take(40)}")
                    }
                }
            }
        }
    }

    override fun onPause() {
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
        server?.stop()
        server = null
        synchronized(fdLock) {                          /* 3.9: ovh-дескрипторы не утекают */
            for ((_, v) in fdCache) { try { v.afd.close() } catch (e: Exception) {} }
            fdCache.clear()
        }
        pool.shutdownNow()
        thumbPool.shutdownNow()
        try { mediaSession?.release() } catch (e: Exception) {}
        mediaSession = null
        PlenkaService.stop(this)
        try { webView.destroy() } catch (e: Exception) {}
        inst = null
        super.onDestroy()
    }

    /* WebView НЕ ставим на паузу НИКОГДА: и в PiP, и в фоне должен идти рендер/звук.
       ( webView.onPause() — та самая причина «в PiP только звук, картинка висит» ) */

    /* ═══════════════ права на медиа ═══════════════ */

    private fun maybeAskPerm() {
        // partial (Android 14 «выбранные фото/видео») не переспрашиваем — скан покажет выбранное
        if (mediaPermState() != "none" || permDialogUp || isFinishing) return
        permDialogUp = true
        runOnUiThread {
            try { requestPermissions(readPerms, RC_PERM) }
            catch (e: Exception) { permDialogUp = false; Log.w(TAG, "perm: ${e.message}") }
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == RC_PERM) {
            val ok = grantResults.isNotEmpty() &&
                permissions.indices.all { grantResults.getOrNull(it) == PackageManager.PERMISSION_GRANTED }
            permDialogUp = false
            Log.i(TAG, "perm result: ok=$ok perms=${permissions.joinToString()}")
            // страница могла ещё не подняться, когда упал первый результат —
            // 2.3: доставляем 6 раз, КАЖДУЮ доставку логируем вместе с квитанцией JS
            // (что страница реально приняла — видно в logcat, «тихая потеря» исключена)
            for (attempt in 0..5) {
                webView.postDelayed({
                    try {
                        webView.evaluateJavascript(
                            "(window.__plenkaPermResult?window.__plenkaPermResult($ok):'нет обработчика')"
                        ) { res ->
                            Log.i(TAG, "permResult#$attempt → ${res?.take(40)}")
                        }
                    } catch (e: Exception) { Log.w(TAG, "permResult#$attempt push: ${e.message}") }
                }, attempt * 700L)
            }
        }
    }

    /* ═══════════════ результаты системных пикеров ═══════════════ */

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        val uris = collectUris(data)
        /* 2.3: результат системного пикера логируется ВСЕГДА — в т.ч. отмена:
           «пикер не выбирается» больше не может быть невидимым (rc/result/количество) */
        Log.i(TAG, "activity result: rc=$requestCode result=$resultCode uris=${uris.size}" +
            (if (uris.isEmpty()) " (отмена или пустой выбор)" else " [${uris.first()}]"))
        when (requestCode) {
            RC_PICK -> if (uris.isNotEmpty()) pool.execute { registerPicked(uris) }
            RC_FILE -> {
                val cb = pendingFcb
                pendingFcb = null
                cb?.onReceiveValue(if (uris.isEmpty()) null else uris.toTypedArray())
            }
        }
    }

    private fun collectUris(data: Intent?): List<Uri> {
        val out = ArrayList<Uri>()
        if (data == null) return out
        val cd: ClipData? = data.clipData
        if (cd != null && cd.itemCount > 0) {
            for (i in 0 until cd.itemCount) cd.getItemAt(i).uri?.let { out.add(it) }
        }
        if (out.isEmpty()) data.data?.let { out.add(it) }
        return out
    }

    /** ручной выбор SAF: метаданные без копирования, реестр переживает рестарты */
    private fun registerPicked(uris: List<Uri>) {
        Log.i(TAG, "registerPicked: ${uris.size} uri")
        regLoad()
        val fresh = JSONArray()
        for (u in uris) {
            try { contentResolver.takePersistableUriPermission(u, Intent.FLAG_GRANT_READ_URI_PERMISSION) }
            catch (e: Exception) { Log.w(TAG, "persist uri: ${e.message}") }

            var name = ""; var mime = ""; var size = 0L
            try {
                contentResolver.query(u, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { c ->
                    if (c.moveToFirst()) { name = c.getString(0) ?: ""; size = c.getLong(1) }
                }
            } catch (e: Exception) {}
            try { mime = contentResolver.getType(u) ?: "" } catch (e: Exception) {}
            if (name.isEmpty()) name = u.lastPathSegment ?: ("file " + System.currentTimeMillis())

            val ext = name.substringAfterLast('.', "").lowercase(Locale.US)
            if (ext in DEAD_EXT) { Log.i(TAG, "picked skipped (dead ext): $name"); continue }

            var dur = 0L; var w = 0; var h = 0
            var mmr: MediaMetadataRetriever? = null
            try {
                mmr = MediaMetadataRetriever()
                mmr.setDataSource(this, u)
                dur = mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull() ?: 0L
                w = mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)?.toIntOrNull() ?: 0
                h = mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT)?.toIntOrNull() ?: 0
            } catch (e: Exception) { Log.w(TAG, "retr: ${e.message}") }
            finally { try { mmr?.release() } catch (e: Exception) {} }

            val k = if (mime.startsWith("audio/") || ext in AUDIO_EXT) "a" else "v"
            val t = System.currentTimeMillis() / 1000
            val entry: PReg
            synchronized(regLock) {
                val old = pickedReg.find { it.uri == u }
                if (old != null) {
                    old.name = name; old.mime = mime; old.size = size
                    old.dur = dur; old.w = w; old.h = h; old.t = t
                    entry = old
                } else {
                    entry = PReg((pickedReg.maxOfOrNull { it.seq } ?: 0L) + 1, u, name, mime, size, dur, w, h, t, k)
                    pickedReg.add(entry)
                }
            }
            fresh.put(JSONObject()
                .put("id", entry.seq).put("k", entry.k).put("n", entry.name).put("m", entry.mime)
                .put("d", entry.dur).put("w", entry.w).put("h", entry.h)
                .put("s", entry.size).put("t", entry.t))
            Log.i(TAG, "picked: #${entry.seq} $name mime=$mime size=$size dur=$dur ${w}x${h} [${entry.k}]")
        }
        regSave()
        val regSize: Int
        synchronized(regLock) { regSize = pickedReg.size }
        Log.i(TAG, "registerPicked done: fresh=${fresh.length()} реестр=$regSize")
        if (fresh.length() > 0) {
            val payload = fresh.toString()
            runOnUiThread {
                val quoted = JSONObject.quote(payload)
                webView.evaluateJavascript("window.__plenkaPicked&&window.__plenkaPicked($quoted)") { res ->
                    Log.i(TAG, "__plenkaPicked → ${res?.take(60)}")
                }
            }
        }
    }

    /* ═══════════════ системный «назад»: стек, а не выход ═══════════════ */

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        // 1) страница закрывает верхний слой (попап/шит/драйвер/скрытый список)
        webView.evaluateJavascript("(window.__plenkaBack?window.__plenkaBack():'nav')") { res ->
            val r = res?.trim()
            if (r == null || r == "\"nav\"" || r == "'nav'") {
                // 2) иначе — история страницы (popstate: плеер → библиотека)
                if (webView.canGoBack()) webView.goBack()
                // 3) в корне — приложение в фон, звук мини-панели продолжает играть
                else moveTaskToBack(true)
            }
        }
    }

    /* ═══════════════ PiP ═══════════════ */

    /* 3.7: параметры PiP-окна — аспект текущего видео (вертикальное видео → вертикальное
       окно) + автозаход системным жестом «домой», когда видео играет */
    private fun pipParams(autoEnter: Boolean): PictureInPictureParams {
        val b = PictureInPictureParams.Builder()
        try {
            if (Build.VERSION.SDK_INT >= 31) b.setAutoEnterEnabled(autoEnter)
        } catch (e: Exception) { Log.w(TAG, "pipAutoEnter: ${e.message}") }
        try {
            val w = lastVideoW; val h = lastVideoH
            if (w > 0 && h > 0) {
                var ratio = w.toDouble() / h.toDouble()
                if (ratio < 0.41841) ratio = 0.41841   // системные границы PiP
                if (ratio > 2.39) ratio = 2.39
                b.setAspectRatio(Rational((ratio * 1000).toInt(), 1000))
            }
        } catch (e: Exception) {}
        return b.build()
    }

    private fun pipAutoSet(on: Boolean) {
        pipAuto = on
        runOnUiThread {
            /* 3.7: авто-вход в PiP по системному жесту — сам системный переход (без чёрного
               кадра от «активность onPause → PiP»); фолбэк для старых API — onUserLeaveHint */
            if (Build.VERSION.SDK_INT >= 31 && !isFinishing) {
                try { setPictureInPictureParams(pipParams(on)) } catch (e: Exception) { Log.w(TAG, "pip params: ${e.message}") }
            }
        }
    }

    override fun onUserLeaveHint() {
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
    }

    /* ═══ 3.13: страница «не замечает» уход окна в фон, пока играет медиа ═══
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

    override fun onPictureInPictureModeChanged(isInPictureInPictureMode: Boolean, newConfig: Configuration) {
        super.onPictureInPictureModeChanged(isInPictureInPictureMode, newConfig)
        inPip = isInPictureInPictureMode
        if (isInPictureInPictureMode) {
            PlenkaService.stop(this)   /* 3.10: видимое PiP-окно само держит процесс */
            // страховка от фриза: активность прошла onPause, но остаётся видимой —
            // WebView обязан быть resumed, иначе кадр не обновляется при живом звуке
            webView.post { try { webView.onResume() } catch (e: Exception) {} }
        }
        webView.post {
            webView.evaluateJavascript(
                "window.__pipMode&&window.__pipMode(${isInPictureInPictureMode})", null
            )
        }
        // 2.4: PiP-переход ронял JavaBridge («Method not found» на 0-арг методах) —
        // пересоздаём интерфейс с обеих сторон, мост живёт столько же, сколько страница
        webView.postDelayed({ rebridgeInternal("pip-" + if (isInPictureInPictureMode) "enter" else "exit") }, 400)
    }

    private fun enterPip(aspect: String?) {
        runOnUiThread {
            if (Build.VERSION.SDK_INT < 26 || isFinishing) return@runOnUiThread
            try {
                val b = PictureInPictureParams.Builder()
                var w = 0; var h = 0
                if (aspect != null) {
                    val p = aspect.split(":")
                    if (p.size == 2) { w = p[0].toIntOrNull() ?: 0; h = p[1].toIntOrNull() ?: 0 }
                }
                if (w > 0 && h > 0) {
                    var ratio = w.toDouble() / h.toDouble()
                    if (ratio < 0.41841) ratio = 0.41841   // системные границы PiP
                    if (ratio > 2.39) ratio = 2.39
                    try { b.setAspectRatio(Rational((ratio * 1000).toInt(), 1000)) } catch (e: Exception) {}
                }
                enterPictureInPictureMode(b.build())
            } catch (e: Exception) { Log.w(TAG, "pipEnter: ${e.message}") }
        }
    }

    private fun exitPip() {
        runOnUiThread {
            if (isInPictureInPictureMode) {
                // единственный документированный способ «развернуть» окно PiP:
                // поднять свою же задачу на передний план
                try {
                    startActivity(Intent(this@MainActivity, MainActivity::class.java)
                        .addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT))
                } catch (e: Exception) { Log.w(TAG, "pipExit: ${e.message}") }
            }
        }
    }

    /* ═══════════════ 2.4: ремонт моста + медиа-кнопки + миниатюры + лог сервера ═══════════════ */

    /** 2.4: пересоздание JS-интерфейса — лечение моста после PiP-переходов.
        remove+add с одним и тем же экземпляром: страница дереференсит window.PlenkaNative
        при каждом вызове, так что новый врапер подхватывается сразу */
    private fun rebridgeInternal(why: String) {
        runOnUiThread {
            try { webView.removeJavascriptInterface("PlenkaNative") } catch (e: Exception) {}
            try {
                webView.addJavascriptInterface(nativeBridge, "PlenkaNative")
                Log.i(TAG, "rebridge: ok ($why)")
            } catch (e: Exception) { Log.w(TAG, "rebridge: ${e.message}") }
            try {
                webView.evaluateJavascript("window.__plenkaRebridged&&window.__plenkaRebridged()", null)
            } catch (e: Exception) {}
        }
    }

    private fun mediaInit() {
        if (mediaSession != null) return
        try {
            val ms = MediaSession(this, "plenka")
            ms.setCallback(object : MediaSession.Callback() {
                override fun onPlay() { jsMedia("play") }
                override fun onPause() { jsMedia("pause") }
                override fun onSkipToNext() { jsMedia("next") }
                override fun onSkipToPrevious() { jsMedia("prev") }
                override fun onSeekTo(pos: Long) { jsMedia("seek:$pos") }
            })
            ms.setActive(true)
            mediaSession = ms
            Log.i(TAG, "media session active")
        } catch (e: Exception) { Log.w(TAG, "mediaInit: ${e.message}") }
    }

    /** 3.10: кнопки фонового уведомления (шторка/локскрин) → страница */
    fun jsMediaFromBg(cmd: String) { jsMedia(cmd) }

    /** 3.10: токен MediaSession для MediaStyle-уведомления сервиса */
    fun mediaToken(): android.media.session.MediaSession.Token? =
        try { mediaSession?.sessionToken } catch (e: Exception) { null }

    private fun jsMedia(cmd: String) {
        runOnUiThread {
            try {
                val q = JSONObject.quote(cmd)
                webView.evaluateJavascript("window.__plenkaMedia&&window.__plenkaMedia($q)") { res ->
                    Log.i(TAG, "media[$cmd] → ${res?.take(30)}")
                }
            } catch (e: Exception) {}
        }
    }

    /** 2.4: состояние плеера → PlaybackState+Metadata; системные кнопки (шторка/наушники)
        работают даже в PiP, где тачи забирает система. Позицию ОС экстраполирует сама */
    private fun mediaUpdate(json: String?) {
        runOnUiThread {
            try {
                /* 3.7: аспект PiP-окна обновляется из состояния плеера — окно принимает
                   форму вертикального/горизонтального видео до жеста «домой» */
                val o0 = JSONObject(json ?: "{}")
                val vw = o0.optInt("w", 0); val vh = o0.optInt("h", 0)
                if (vw > 0 && vh > 0 && (vw != lastVideoW || vh != lastVideoH)) {
                    lastVideoW = vw; lastVideoH = vh
                    if (pipAuto && Build.VERSION.SDK_INT >= 31 && !isFinishing) {
                        try { setPictureInPictureParams(pipParams(true)) } catch (e: Exception) {}
                    }
                }
                val ms = mediaSession ?: return@runOnUiThread
                val o = o0
                val playing = o.optBoolean("playing", false)
                val pos = o.optLong("pos", 0L) * 1000L
                val dur = o.optLong("dur", 0L) * 1000L
                ms.setPlaybackState(PlaybackState.Builder()
                    .setActions(PlaybackState.ACTION_PLAY or PlaybackState.ACTION_PAUSE or
                        PlaybackState.ACTION_PLAY_PAUSE or PlaybackState.ACTION_SKIP_TO_NEXT or
                        PlaybackState.ACTION_SKIP_TO_PREVIOUS or PlaybackState.ACTION_SEEK_TO)
                    .setState(if (playing) PlaybackState.STATE_PLAYING else PlaybackState.STATE_PAUSED,
                        pos, if (playing) 1f else 0f)
                    .build())
                val title = o.optString("title", "")
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
                try { (webView as? PlenkaWebView)?.refreshBgPolicy() } catch (e: Exception) {}   /* 3.13: паузнули в фоне — страницу честно спрятать; заиграли — держать «видимой» */
                if (title.isNotEmpty()) { lastTitle = title; lastArtist = o.optString("artist", "") }
                maybeBgRefresh()
            } catch (e: Exception) { Log.w(TAG, "mediaUpdate: ${e.message}") }
        }
    }

    /** 3.10: состояние плеера поменялось — жить ли фоновому сервису */
    private fun maybeBgRefresh() {
        /* 3.11: диалог POST_NOTIFICATIONS убрали — он всплывал при ПЕРВОЙ игре и
           паузил активити в самый неподходящий момент; MediaStyle-уведомлениям
           право не нужно (media exempt), шторка живёт и так */
        if (!PlenkaService.running && actFront) return   /* на экране сервис не нужен */
        try { PlenkaService.push(this, lastPlaying, lastTitle, lastArtist, lastPosMs, lastDurMs) }
        catch (e: Exception) { Log.w(TAG, "bg refresh: ${e.message}") }
    }

    private fun srvRec(line: String) {
        try {
            synchronized(srvRing) {
                srvRing.addLast(line)
                while (srvRing.size > 160) srvRing.removeFirst()
            }
        } catch (e: Exception) {}
        Log.i(TAG, line)
    }

    private fun videoCollection(vol: String?): Uri =
        if (vol != null && Build.VERSION.SDK_INT >= 29) MediaStore.Video.Media.getContentUri(vol)
        else MediaStore.Video.Media.EXTERNAL_CONTENT_URI

    private fun audioCollection(vol: String?): Uri =
        if (vol != null && Build.VERSION.SDK_INT >= 29) MediaStore.Audio.Media.getContentUri(vol)
        else MediaStore.Audio.Media.EXTERNAL_CONTENT_URI

    private fun safeFrame(mmr: MediaMetadataRetriever, us: Long): Bitmap? = safeFrameOpt(mmr, us, MediaMetadataRetriever.OPTION_CLOSEST_SYNC)

    /* 3.7: лестница «первых кадров» — OPTION_CLOSEST на 0/16/50/150мс декодирует кадр ровно
       от первого кейфрейма (t=0 практически у всех видео начинается кейфреймом); CLOSEST на мелких
       временах иногда не даётся декодеру — тогда SYNC-лестница (кейфрейм) и честная метка
       «не первый». Возврат: us ≥ 0 — время взятого кадра (первый), -1 — дальний/синковый,
       -2 — аудио (без заголовка) */
    private fun safeFrameOpt(mmr: MediaMetadataRetriever, us: Long, option: Int): Bitmap? = try {
        mmr.getFrameAtTime(us, option)
    } catch (e: Exception) { null }

    private fun firstFrameLadder(mmr: MediaMetadataRetriever): Pair<Bitmap?, Long> {
        val closestUs = longArrayOf(0L, 16_000L, 50_000L, 150_000L)   /* ≤150мс = «первый кадр» */
        val syncUs = longArrayOf(0L, 400_000L, 1_000_000L)            /* фолбэк: кейфрейм (карточке достаточно) */
        for (us in closestUs) {
            val b = safeFrameOpt(mmr, us, MediaMetadataRetriever.OPTION_CLOSEST)
            if (b != null) return Pair(b, us)
        }
        for (us in syncUs) {
            val b = safeFrameOpt(mmr, us, MediaMetadataRetriever.OPTION_CLOSEST_SYNC)
            if (b != null) return Pair(b, if (us == 0L) 0L else -1L)  /* sync@0 — первый кейфрейм; 0.4/1с — дальний */
        }
        /* 3.8: файлы, где декодер не даёт кадр у старта (MMR устройства не любит первый
           GOP 4K-файла), раньше сдавались → 404 → карточка без обложки ВООБЩЕ. Дальняя
           лестница 2/5/12с: карточке нужен любой кадр; метка -1 «дальний» → подложка
           остаётся чёрной, карточка прикрыта */
        for (us in longArrayOf(2_000_000L, 5_000_000L, 12_000_000L)) {
            var b = safeFrameOpt(mmr, us, MediaMetadataRetriever.OPTION_CLOSEST_SYNC)
            if (b == null) b = safeFrameOpt(mmr, us, MediaMetadataRetriever.OPTION_CLOSEST)
            if (b != null) return Pair(b, -1L)
        }
        return Pair(null, -1L)
    }

    /** 2.4: байты миниатюры: диск-кэш → генерация в thumbPool (дедупликация in-flight,
        негативный кэш не гоняет генерацию по безнадёжным файлам снова) */
    /* 3.5: негативный кэш с TTL 40с — транзиентный сбой MMR (тяжёлый 4K-файл под
       нагрузкой) больше не хоронит обложку до конца сессии: «кадр показывается,
       через секунду заменяется заглушкой» */
    private val thumbDead = java.util.Collections.synchronizedMap(HashMap<String, Long>())

    /* 3.7: результат миниатюры — байты + метка кадра для заголовка X-Plenka-FrameT:
       us ≥ 0 — кадр с t=us/1000 мс (первый, лестница 0/16/50/150мс);
       -1 — дальний/синковый фолбэк («не первый» → страница кладёт чёрный в подложку);
       -2 — аудио/неизвестно (заголовок не пишем) */
    class ThumbRes(val bytes: ByteArray?, val frameUs: Long)

    @Volatile private var thumbSweepDone = false

    private fun thumbBytes(kind: String, id: Long, vol: String?, rev: String): ThumbRes {
        val dir = File(cacheDir, "thumbs")
        try { if (!dir.exists()) dir.mkdirs() } catch (e: Exception) {}
        if (!thumbSweepDone) {
            thumbSweepDone = true
            try {   // 3.7: разовая зачистка кэша генерации 1 (t_*) — без метки кадра
                dir.listFiles { x -> x.name.startsWith("t_") }?.forEach { it.delete() }
            } catch (e: Exception) {}
        }
        val base = "t2_${kind}_${vol ?: "p"}_${id}"
        var frameUs = -2L
        var f: File? = null
        try {   // кэш генерации 2: имя несёт метку кадра — заголовок читается без состояния
            val hits = dir.listFiles { x -> x.name.startsWith(base + "_" + rev + "_") }
            if (hits != null && hits.isNotEmpty()) {
                f = hits[0]
                val tag = hits[0].name.removeSuffix(".jpg").substringAfterLast('_')
                frameUs = when (tag) {
                    "s" -> -1L
                    "n" -> -2L
                    else -> tag.toLongOrNull() ?: -2L
                }
            }
        } catch (e: Exception) {}
        if (f != null && f!!.length() > 0) {
            try { return ThumbRes(f!!.readBytes(), frameUs) } catch (e: Exception) {}
        }
        try {   // старые ревизии этого же файла не копятся
            dir.listFiles { x -> x.name.startsWith(base + "_") }?.forEach { it.delete() }
        } catch (e: Exception) {}
        val key = "$base/$rev"
        val deadAt = thumbDead[key]
        if (deadAt != null) {
            if (System.currentTimeMillis() - deadAt < 40_000) return ThumbRes(null, -2L)
            thumbDead.remove(key)                    /* TTL истёк — генерации дают ещё шанс */
        }
        val fut: Future<ThumbRes> = thumbInflight[key]?.takeIf { !it.isDone } as? Future<ThumbRes>
            ?: thumbPool.submit<ThumbRes> { generateThumb(kind, id, vol, base, rev, dir) }
                .also { thumbInflight[key] = it }
        return try {
            val b = fut.get(25, TimeUnit.SECONDS)
            thumbInflight.remove(key)
            if (b.bytes == null) thumbDead[key] = System.currentTimeMillis()   // 40с — и снова попробуем
            b
        } catch (e: Exception) {
            thumbInflight.remove(key)
            ThumbRes(null, -2L)
        }
    }

    /** 3.7: видео — первый кадр (лестница 0/16/50/150мс, фолбэк кейфрейм 0.4с/1с) с поворотом
        и масштабом ≤384; аудио — встроенный арт. Метка кадра — в имя кэш-файла */
    private fun generateThumb(kind: String, id: Long, vol: String?, base: String, rev: String, dir: File): ThumbRes {
        try {
            var rec: PReg? = null
            val uri: Uri = when (kind) {
                "v" -> ContentUris.withAppendedId(videoCollection(vol), id)
                "a" -> ContentUris.withAppendedId(audioCollection(vol), id)
                "c" -> {
                    regLoad()
                    rec = synchronized(regLock) { pickedReg.find { it.seq == id } }
                    if (rec == null) return ThumbRes(null, -2L)
                    rec.uri
                }
                else -> return ThumbRes(null, -2L)
            }
            val isAudio = (kind == "a") || (rec != null && rec.k == "a")
            val mmr = MediaMetadataRetriever()
            try {
                mmr.setDataSource(this, uri)
                if (isAudio) {
                    var pic = try { mmr.embeddedPicture } catch (e: Exception) { null }
                    if (pic == null || pic.size <= 64) {
                        /* 3.8: встроенной обложки нет — системный арт альбома
                           (content://media/external/audio/albumart/<albumId>): часть mp3
                           без ID3-арта имеет обложку в медиатеке телефона */
                        try {
                            var albumId = -1L
                            contentResolver.query(audioCollection(vol), arrayOf(MediaStore.Audio.Media.ALBUM_ID),
                                "${MediaStore.Audio.Media._ID}=?", arrayOf("$id"), null)?.use { c ->
                                if (c.moveToFirst()) albumId = c.getLong(0)
                            }
                            if (albumId > 0) {
                                val au = ContentUris.withAppendedId(
                                    Uri.parse("content://media/external/audio/albumart"), albumId)
                                val b2 = try { contentResolver.openInputStream(au)?.use { it.readBytes() } } catch (e: Exception) { null }
                                if (b2 != null && b2.size > 64 &&
                                    ((b2[0] == 0xFF.toByte() && b2[1] == 0xD8.toByte()) ||
                                        (b2[0] == 'P'.code.toByte() && b2[1] == 'N'.code.toByte()))) {
                                    pic = b2
                                }
                            }
                        } catch (e: Exception) {}
                    }
                    if (pic != null && pic.size > 64) {
                        try { File(dir, "${base}_${rev}_n.jpg").writeBytes(pic) } catch (e: Exception) {}
                        return ThumbRes(pic, -2L)
                    }
                    return ThumbRes(null, -2L)
                }
                val lr = firstFrameLadder(mmr)
                var frameUs = lr.second
                var bmp0: Bitmap? = lr.first
                if (bmp0 == null) {
                    /* 3.8: MMR не дал ни одного кадра (4K с «неудобным» первым GOP —
                       регресс «отсутствие обложек») — системная миниатюра MediaStore
                       как последний шанс; метка «дальний»: карточка прикрыта,
                       подложка по-прежнему честный чёрный */
                    try {
                        if (Build.VERSION.SDK_INT >= 29) {
                            val th = contentResolver.loadThumbnail(uri, android.util.Size(384, 384), null)
                            if (th != null) { bmp0 = th; frameUs = -1L }
                        }
                    } catch (e: Exception) { Log.w(TAG, "thumb sys $kind/$id: ${e.javaClass.simpleName}") }
                }
                val bFirst: Bitmap = bmp0 ?: return ThumbRes(null, -1L)
                val tag = if (frameUs >= 0) "$frameUs" else "s"   /* s — синковый/дальний фолбэк */
                var bmp: Bitmap = bFirst
                val rot = try {
                    mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_ROTATION)?.toIntOrNull() ?: 0
                } catch (e: Exception) { 0 }
                if (rot == 90 || rot == 270) {
                    try {
                        val r = Bitmap.createBitmap(bmp, 0, 0, bmp.width, bmp.height,
                            Matrix().apply { postRotate(rot.toFloat()) }, true)
                        if (r != null && r != bmp) {
                            val old = bmp; bmp = r
                            try { old.recycle() } catch (e: Exception) {}
                        }
                    } catch (e: Exception) {}
                }
                var b2: Bitmap = bmp
                val maxSide = 384
                if (bmp.width > maxSide || bmp.height > maxSide) {
                    val sc = maxSide.toFloat() / maxOf(bmp.width, bmp.height)
                    try {
                        val r2 = Bitmap.createScaledBitmap(bmp, Math.max(2, (bmp.width * sc).toInt()),
                            Math.max(2, (bmp.height * sc).toInt()), true)
                        if (r2 != null && r2 != bmp) {
                            b2 = r2
                            try { bmp.recycle() } catch (e: Exception) {}
                        }
                    } catch (e: Exception) {}
                }
                val bos = java.io.ByteArrayOutputStream()
                b2.compress(Bitmap.CompressFormat.JPEG, 80, bos)
                val bytes = bos.toByteArray()
                val w2 = b2.width; val h2 = b2.height
                try { b2.recycle() } catch (e: Exception) {}
                try { File(dir, "${base}_${rev}_${tag}.jpg").writeBytes(bytes) } catch (e: Exception) { Log.w(TAG, "thumb cache write: ${e.message}") }
                try {   // гигиена кэша
                    val fs = dir.listFiles()
                    if (fs != null && fs.size > 600) fs.sortedBy { it.lastModified() }.take(fs.size - 500).forEach { it.delete() }
                } catch (e: Exception) {}
                Log.i(TAG, "thumb $kind/$id: ${bytes.size / 1024}КБ ${w2}x${h2} rot=$rot frameT=${if (frameUs >= 0) "${frameUs / 1000}мс(первый)" else "дальний"}")
                return ThumbRes(bytes, frameUs)
            } finally { try { mmr.release() } catch (e: Exception) {} }
        } catch (e: Exception) { Log.w(TAG, "thumb $kind/$id: ${e.message}") }
        return ThumbRes(null, -2L)
    }

    /* ═══════════════ прочие системные штуки ═══════════════ */

    private fun setImmersiveMode(on: Boolean) {
        runOnUiThread {
            if (Build.VERSION.SDK_INT >= 30) {
                val c = window.insetsController
                if (c != null) {
                    if (on) {
                        c.hide(WindowInsets.Type.systemBars())
                        c.systemBarsBehavior = WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
                    } else {
                        c.show(WindowInsets.Type.systemBars())
                    }
                }
            } else {
                @Suppress("DEPRECATION")
                window.decorView.systemUiVisibility =
                    if (on) (View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                        or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        or View.SYSTEM_UI_FLAG_FULLSCREEN
                        or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                        or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                        or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN)
                    else (View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                        or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                        or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN)
            }
        }
    }

    private fun keepScreen(on: Boolean) {
        runOnUiThread {
            if (on) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    /* ═══════════════ мост JS ↔ Kotlin (поток JavaBridge) ═══════════════ */

    inner class NativeBridge {
        /** скан MediaStore: конверт {ok,err,n,items:[{k,id,n,m,d,w,h,s,t[,vol]}]} — без чтения файлов.
            2.1: пусто из-за права ≠ пусто по факту — страница видит причину */
        /* 2.4: каждый метод получил парную перегрузку (0-арг ↔ 1-арг). Причина: после
           первого PiP-перехода JavaBridge на Android 14 перестаёт прощать вызов
           безаргументного метода с лишним undefined-аргументом («Method not found») */
        @JavascriptInterface fun scan(): String = scanMediaJson()
        @JavascriptInterface fun scan(unused: String?): String = scanMediaJson()
        @JavascriptInterface fun hasPerm(): Boolean = hasMediaPerm()
        @JavascriptInterface fun hasPerm(unused: String?): Boolean = hasMediaPerm()
        /** true — диалог показан (придёт __plenkaPermResult), false — запросить нельзя */
        @JavascriptInterface fun requestPerm(): Boolean {
            Log.i(TAG, "bridge requestPerm")
            if (hasMediaPerm()) return true
            runOnUiThread { requestPermissions(readPerms, RC_PERM) }
            return true
        }
        @JavascriptInterface fun requestPerm(unused: String?): Boolean = requestPerm()
        /** системный SAF-пикер (мультивыбор, видео+аудио); результат придёт __plenkaPicked.
            2.2: OPEN_DOCUMENT может отсутствовать на экзотических прошивках — фолбэк GET_CONTENT;
            2.3: каждый шаг запуска пишется в logcat — «пикер не открывается» виден сразу */
        @JavascriptInterface fun pick(): Boolean {
            runOnUiThread {
                var started = false
                try {
                    val i = Intent(Intent.ACTION_OPEN_DOCUMENT)
                    i.addCategory(Intent.CATEGORY_OPENABLE)
                    i.type = "*/*"
                    i.putExtra(Intent.EXTRA_MIME_TYPES, arrayOf("video/*", "audio/*"))
                    i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
                    startActivityForResult(i, RC_PICK)
                    started = true
                    Log.i(TAG, "pick: ACTION_OPEN_DOCUMENT запущен")
                } catch (e: Exception) { Log.w(TAG, "pick open_doc: ${e.message}") }
                if (!started) try {
                    val i2 = Intent(Intent.ACTION_GET_CONTENT)
                    i2.type = "*/*"
                    i2.putExtra(Intent.EXTRA_MIME_TYPES, arrayOf("video/*", "audio/*"))
                    i2.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true)
                    startActivityForResult(i2, RC_PICK)
                    started = true
                    Log.i(TAG, "pick: фолбэк ACTION_GET_CONTENT запущен")
                } catch (e: Exception) { Log.w(TAG, "pick get_content: ${e.message}") }
                if (!started) {
                    Log.e(TAG, "pick: НЕ ЗАПУСТИЛСЯ — системного выбора файлов нет")
                    try { Toast.makeText(applicationContext, "ПЛЁНКА: системный выбор файлов не найден", Toast.LENGTH_LONG).show() } catch (e: Exception) {}
                }
            }
            return true
        }
        @JavascriptInterface fun pick(unused: String?): Boolean = pick()
        /** реестр ручного выбора: [{id,k,n,m,d,w,h,s,t}] — как items скана */
        @JavascriptInterface fun pickedList(): String {
            regLoad()
            val a = JSONArray()
            synchronized(regLock) {
                for (r in pickedReg) a.put(JSONObject()
                    .put("id", r.seq).put("k", r.k).put("n", r.name).put("m", r.mime)
                    .put("d", r.dur).put("w", r.w).put("h", r.h)
                    .put("s", r.size).put("t", r.t))
            }
            Log.i(TAG, "pickedList: ${a.length()} записей")
            return a.toString()
        }
        @JavascriptInterface fun pickedList(unused: String?): String = pickedList()
        /** убрать из реестра (карточка удалена в библиотеке) */
        @JavascriptInterface fun unpick(seq: Long): Boolean {
            Log.i(TAG, "unpick($seq)")
            regLoad()
            var removed = false
            synchronized(regLock) {
                val rec = pickedReg.find { it.seq == seq }
                if (rec != null) {
                    removed = pickedReg.remove(rec)
                    if (removed) {
                        try { contentResolver.releasePersistableUriPermission(rec.uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) }
                        catch (e: Exception) {}
                    }
                }
            }
            if (removed) regSave()
            return removed
        }
        @JavascriptInterface fun unpick(): Boolean = false   /* 2.4: страховка от 0-арг вызова */
        @JavascriptInterface fun pipEnter(aspect: String?) { pipAuto = true; enterPip(aspect) }
        @JavascriptInterface fun pipEnter() { pipAuto = true; enterPip(null) }
        @JavascriptInterface fun pipExit() { exitPip() }
        @JavascriptInterface fun pipExit(unused: String?) { exitPip() }
        @JavascriptInterface fun setPipAuto(on: Boolean) { pipAutoSet(on) }
        @JavascriptInterface fun setPipAuto() { /* 2.4: 0-арг страховка */ }
        @JavascriptInterface fun isPip(): Boolean = inPip
        @JavascriptInterface fun isPip(unused: String?): Boolean = inPip
        @JavascriptInterface fun immersive(on: Boolean) { setImmersiveMode(on) }
        @JavascriptInterface fun immersive() { /* 2.4 */ }
        @JavascriptInterface fun keepScreenOn(on: Boolean) { keepScreen(on) }
        @JavascriptInterface fun keepScreenOn() { /* 2.4 */ }
        @JavascriptInterface fun exitApp() { runOnUiThread { moveTaskToBack(true) } }
        @JavascriptInterface fun exitApp(unused: String?) { runOnUiThread { moveTaskToBack(true) } }
        @JavascriptInterface fun version(): String = APP_VERSION
        @JavascriptInterface fun version(unused: String?): String = APP_VERSION
        /** диагностика 2.2: короткое сообщение из страницы — в logcat и тостом (видно даже при мёртвом UI) */
        @JavascriptInterface fun report(msg: String?) {
            val m = (msg ?: "").take(180)
            Log.w(TAG, "diag: $m")
            runOnUiThread {
                try { Toast.makeText(applicationContext, "ПЛЁНКА: $m", Toast.LENGTH_LONG).show() } catch (e: Exception) {}
            }
        }
        /** полный отчёт диагностики — только в logcat (adb logcat -s PLENKA) */
        @JavascriptInterface fun logFull(msg: String?) {
            Log.i(TAG, "DIAG REPORT:\n${msg ?: ""}")
        }
        /** состояние прав для страницы: {state: ok|partial|none, sdk} */
        @JavascriptInterface fun permState(): String =
            JSONObject().put("state", mediaPermState()).put("sdk", Build.VERSION.SDK_INT).toString()
        @JavascriptInterface fun permState(unused: String?): String = permState()
        /** 2.4: ремонт моста после PiP — пересоздать интерфейс (страница пробует и пишет в журнал) */
        @JavascriptInterface fun rebridge(reason: String?) { rebridgeInternal(reason ?: "page") }
        @JavascriptInterface fun rebridge() { rebridgeInternal("page0") }
        /** 2.4: журнал HTTP-сервера для ДИАГ — последние запросы: статусы/Range/байты/мс */
        @JavascriptInterface fun srvLog(): String {
            val a = JSONArray()
            synchronized(srvRing) { for (l in srvRing) a.put(l) }
            return a.toString()
        }
        @JavascriptInterface fun srvLog(unused: String?): String = srvLog()
        /** 2.4: состояние плеера → системные медиа-кнопки (шторка/наушники/локскрин) */
        @JavascriptInterface fun mediaState(json: String?) { mediaUpdate(json) }
        @JavascriptInterface fun mediaState() { /* 2.4 */ }
        @JavascriptInterface fun log(msg: String?) { Log.d(TAG, "page: $msg") }
        @JavascriptInterface fun log() { /* 2.4 */ }
    }

    /* ═══════════════ скан MediaStore ═══════════════ */

    private fun playable(name: String, mime: String, video: Boolean): Boolean {
        val ext = name.substringAfterLast('.', "").lowercase(Locale.US)
        if (ext.isNotEmpty()) {
            if (ext in DEAD_EXT) return false
            val okExt = if (video) ext in VIDEO_EXT else ext in AUDIO_EXT
            if (okExt) return true
        }
        // 2.1: расширения нет/нестандартное — верим любому video/* или audio/*
        // (раньше был узкий белый список и часть реальных видео терялась)
        val m = mime.lowercase(Locale.US)
        return if (video) m.startsWith("video/")
        else (m.startsWith("audio/") || m == "application/ogg")
    }

    private class SkipStats(
        var dead: Int = 0, var tiny: Int = 0, var shortDur: Int = 0,
        val deadNames: ArrayList<String> = ArrayList()
    )

    private fun scanMediaJson(): String {
        /* 3.8: бут синкает дважды (init + resume/вочдог) с интервалом в сотни мс —
           MediaStore гонять дважды незачем: свежий конверт отдаём из кэша */
        val c = lastScanJson
        if (c != null && System.currentTimeMillis() - lastScanAt < 2000) return c
        val t0 = System.currentTimeMillis()
        /* 2.3: любое исключение Java больше не пробивается через мост молча —
           страница получает конверт с причиной и ретраит; трейс — в logcat.
           (подозреваемый сценарий 2.2: срыв запроса MediaStore на старте →
           natvCall глушил исключение → «пусто и без ошибок») */
        return try {
            val r = scanMediaJsonInner()
            Log.i(TAG, "scan: ${System.currentTimeMillis() - t0}мс, конверт ${r.length} байт")
            r
        } catch (e: Exception) {
            Log.e(TAG, "scan FAILED за ${System.currentTimeMillis() - t0}мс", e)
            JSONObject()
                .put("ok", false).put("err", "scan").put("msg", "${e.javaClass.simpleName}: ${e.message}")
                .put("n", 0).put("items", JSONArray()).toString()
        }
    }

    private fun scanMediaJsonInner(): String {
        val out = JSONArray()
        val state = mediaPermState()
        if (state == "none") {
            Log.w(TAG, "scan: no permission")
            return JSONObject()
                .put("ok", false).put("err", "perm").put("n", 0).put("items", out)
                .toString()
        }
        val vols = mediaVolumes()
        val volCounts = JSONObject()
        val st = SkipStats()
        for (vol in vols) {
            val before = out.length()
            scanVolume(vol, out, st)
            volCounts.put(vol, out.length() - before)
        }
        val skippedTotal = st.dead + st.tiny + st.shortDur
        Log.i(TAG, "scan: ${out.length()} playable items in ${vols.size} volumes: $vols; skipped dead=${st.dead} tiny=${st.tiny} short=${st.shortDur}")
        val env = JSONObject()
            .put("ok", true).put("n", out.length()).put("items", out)
            .put("perm", state)
            .put("skipN", skippedTotal)
            .put("vols", volCounts)
        val sk = JSONArray()
        for (n in st.deadNames) sk.put(n)
        env.put("skipped", sk)
        val s = env.toString()
        lastScanJson = s                            /* 3.5: /list — из кэша, мгновенно */
        lastScanAt = System.currentTimeMillis()     /* 3.8: и сам скан кэшируется 2с */
        return s
    }

    /** все тома хранилища: внутренний + SD-карта (2.1: видео на SD раньше не существовали) */
    private fun mediaVolumes(): List<String> {
        val vols = ArrayList<String>()
        if (Build.VERSION.SDK_INT >= 29) {
            try {
                for (name in MediaStore.getExternalVolumeNames(this)) {
                    if (!vols.contains(name)) vols.add(name)
                }
            } catch (e: Exception) { Log.w(TAG, "volumes: ${e.message}") }
        }
        if (vols.isEmpty()) vols.add(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        return vols
    }

    private fun scanVolume(vol: String, out: JSONArray, st: SkipStats) {
        val cr = contentResolver
        val primary = vol == MediaStore.VOLUME_EXTERNAL_PRIMARY

        val vProj = arrayOf(
            MediaStore.Video.Media._ID,
            MediaStore.Video.Media.DISPLAY_NAME,
            MediaStore.Video.Media.MIME_TYPE,
            MediaStore.Video.Media.DURATION,
            MediaStore.Video.Media.WIDTH,
            MediaStore.Video.Media.HEIGHT,
            MediaStore.Video.Media.SIZE,
            MediaStore.Video.Media.DATE_MODIFIED
        )
        try {
            val vu = if (Build.VERSION.SDK_INT >= 29) MediaStore.Video.Media.getContentUri(vol)
            else MediaStore.Video.Media.EXTERNAL_CONTENT_URI
            cr.query(vu, vProj, null, null, "date_modified DESC")?.use { c ->
                while (c.moveToNext()) {
                    val name = c.getString(1) ?: continue
                    val mime = c.getString(2) ?: ""
                    val dur = c.getLong(3)
                    val size = c.getLong(6)
                    if (!playable(name, mime, video = true)) {
                        st.dead++                                       /* 2.2: показываем, ЧТО отфильтровано — пустота объясняет себя */
                        if (st.deadNames.size < 12 && !name.startsWith(".")) st.deadNames.add(name)
                        continue
                    }
                    if (size < 10240) { st.tiny++; continue }            // системный мусор <10КБ
                    if (dur in 1 until 1000) { st.shortDur++; continue } // <1с — стикеры/моушн-обрезки
                    val o = JSONObject()
                        .put("k", "v").put("id", c.getLong(0))
                        .put("n", name).put("m", mime).put("d", dur)
                        .put("w", c.getInt(4)).put("h", c.getInt(5))
                        .put("s", size).put("t", c.getLong(7))
                    if (!primary) o.put("vol", vol)              // URL будет /v/<id>?vol=<том>
                    out.put(o)
                }
            }
        } catch (e: Exception) { Log.w(TAG, "scan video[$vol]: ${e.message}") }

        val aProj = arrayOf(
            MediaStore.Audio.Media._ID,
            MediaStore.Audio.Media.DISPLAY_NAME,
            MediaStore.Audio.Media.MIME_TYPE,
            MediaStore.Audio.Media.DURATION,
            MediaStore.Audio.Media.SIZE,
            MediaStore.Audio.Media.DATE_MODIFIED
        )
        try {
            val au = if (Build.VERSION.SDK_INT >= 29) MediaStore.Audio.Media.getContentUri(vol)
            else MediaStore.Audio.Media.EXTERNAL_CONTENT_URI
            cr.query(au, aProj, null, null, "date_modified DESC")?.use { c ->
                while (c.moveToNext()) {
                    val name = c.getString(1) ?: continue
                    val mime = c.getString(2) ?: ""
                    val dur = c.getLong(3)
                    val size = c.getLong(4)
                    if (!playable(name, mime, video = false)) {
                        st.dead++
                        if (st.deadNames.size < 12 && !name.startsWith(".")) st.deadNames.add(name)
                        continue
                    }
                    if (size < 2048) { st.tiny++; continue }
                    if (dur in 1 until 500) { st.shortDur++; continue }  // системные писки
                    val o = JSONObject()
                        .put("k", "a").put("id", c.getLong(0))
                        .put("n", name).put("m", mime).put("d", dur)
                        .put("w", 0).put("h", 0)
                        .put("s", size).put("t", c.getLong(5))
                    if (!primary) o.put("vol", vol)
                    out.put(o)
                }
            }
        } catch (e: Exception) { Log.w(TAG, "scan audio[$vol]: ${e.message}") }
    }

    /* ═══════════════ HTTP-сервер (127.0.0.1:8977) ═══════════════
       Свой, без зависимостей: GET/HEAD, keep-alive, Range (206/416).
       /                  → приложение (plenka.html из assets, кэш в памяти)
       /v/<id>[?vol=том]  → видео из MediaStore (ContentResolver, живой резолв)
       /a/<id>[?vol=том]  → аудио из MediaStore
       /c/<id>            → файл ручного выбора (SAF-реестр, живой резолв) */

    private inner class PlenkaServer(private val ctx: Context) {
        private var srv: ServerSocket? = null
        private val alive = AtomicBoolean(false)
        @Volatile private var htmlCache: ByteArray? = null

        fun start() {
            try {
                val s = ServerSocket()
                s.reuseAddress = true
                s.bind(InetSocketAddress(InetAddress.getByName("127.0.0.1"), PORT), 16)
                srv = s
                alive.set(true)
                Thread({
                    while (alive.get()) {
                        try {
                            val sock = srv?.accept() ?: break
                            pool.execute { serveSocket(sock) }
                        } catch (e: Exception) {
                            if (alive.get()) Log.w(TAG, "accept: ${e.message}")
                        }
                    }
                }, "plenka-http-accept").start()
                Log.i(TAG, "server listening 127.0.0.1:$PORT")
            } catch (e: Exception) {
                Log.e(TAG, "server start FAIL: ${e.message}")
            }
        }

        fun stop() {
            alive.set(false)
            try { srv?.close() } catch (e: Exception) {}
            srv = null
        }

        private val assetCache = HashMap<String, ByteArray>()   /* 3.9: стенды из assets — как главный ассет */
        private fun assetBytes(name: String): ByteArray? {
            synchronized(assetCache) {
                val c = assetCache[name]
                if (c != null) return if (c.isEmpty()) null else c
                val b = try { ctx.assets.open(name).use { it.readBytes() } } catch (e: Exception) { null } ?: ByteArray(0)
                assetCache[name] = b
                return if (b.isEmpty()) null else b
            }
        }
        private fun htmlBytes(): ByteArray? {
            htmlCache?.let { return it }
            return try {
                ctx.assets.open("plenka.html").use { it.readBytes() }.also { htmlCache = it }
            } catch (e: Exception) { Log.e(TAG, "html asset: ${e.message}"); null }
        }

        private fun serveSocket(sock: Socket) {
            var lastReq: Request? = null
            try {
                sock.tcpNoDelay = true
                sock.soTimeout = 30000   /* 2.4: медленные Range-пробы гигантов не рвут соединение */
                val input = BufferedInputStream(sock.getInputStream(), 16384)
                val out = BufferedOutputStream(sock.getOutputStream(), 65536)
                while (alive.get()) {
                    val req = parseRequest(input) ?: break
                    lastReq = req
                    val closeConn = serve(out, req)
                    out.flush()
                    if (closeConn) break
                }
            } catch (e: Exception) {
                // обрыв сокета — рабочая тишина
            } finally {
                try {
                    if (lastReq?.rst == true) sock.setSoLinger(true, 0)   /* 3.8: RST вместо FIN — клиент НЕ висит на обещании */
                    sock.close()
                } catch (e: Exception) {}
            }
        }

        private fun readLine(input: InputStream): String? {
            val sb = StringBuilder()
            while (true) {
                val c = input.read()
                if (c < 0) return if (sb.isEmpty()) null else sb.toString()
                if (c == '\n'.code) break
                if (c != '\r'.code) sb.append(c.toChar())
                if (sb.length > 16384) return null
            }
            return sb.toString()
        }

        private fun parseRequest(input: InputStream): Request? {
            try {
                var line: String? = null
                var guard = 0
                while (guard++ < 16) {                       // пустые строки до запроса пропускаем
                    line = readLine(input) ?: return null
                    if (line.isNotEmpty()) break
                }
                if (line.isNullOrEmpty()) return null
                val parts = line.split(" ")
                if (parts.size < 3) return null
                val method = parts[0].uppercase(Locale.US)
                if (method != "GET" && method != "HEAD") return null
                val headers = HashMap<String, String>()
                var guard2 = 0
                while (guard2++ < 128) {
                    val h = readLine(input) ?: break
                    if (h.isEmpty()) break
                    val i = h.indexOf(':')
                    if (i > 0) headers[h.substring(0, i).trim().lowercase(Locale.US)] = h.substring(i + 1).trim()
                }
                return Request(method, parts[1], headers)
            } catch (e: Exception) { return null }
        }

        private inner class Request(val method: String, val rawPath: String, val headers: Map<String, String>) {
            var rst = false   /* 3.8: ответ оборвался короче Content-Length — сокет рвём RST, клиент перепросит */
            val path: String get() = rawPath.substringBefore('?')
            val range: String? get() = headers["range"]
            val keepAlive: Boolean
                get() = (headers["connection"] ?: "").lowercase(Locale.US) != "close"
        }

        /** @return закрывать ли соединение после ответа */
        private fun serve(out: OutputStream, req: Request): Boolean {
            val path = req.path
            if (path == "/seek" || path == "/seek/") {   /* 3.9: стенд перемотки — ассет v51 (вернули из 3.6):
                                                            список файлов стенд берёт сам (/__medialist), сики меряет мост страницы */
                val html = assetBytes("plenka-seek.html")
                if (html == null) {
                    writeSimple(out, 500, "text/plain; charset=utf-8", "app asset missing")
                    return true
                }
                writeHead(out, 200, "text/html; charset=utf-8", html.size.toLong(), null, null)
                if (req.method == "GET") out.write(html)
                srvRec("GET /seek → 200 html ${html.size / 1024}КБ")
                return true
            }
            if (path == "/lab" || path == "/lab/") {     /* 3.9: видео-лаборатория — ассет v51 (вернули из 3.6) */
                val html = assetBytes("plenka-lab.html")
                if (html == null) {
                    writeSimple(out, 500, "text/plain; charset=utf-8", "app asset missing")
                    return true
                }
                writeHead(out, 200, "text/html; charset=utf-8", html.size.toLong(), null, null)
                if (req.method == "GET") out.write(html)
                srvRec("GET /lab → 200 html ${html.size / 1024}КБ")
                return true
            }
            if (path == "/__medialist") {                /* 3.9: стенд v51 берёт список файлов отсюда (в Chrome моста нет) */
                serveList(out, req)
                return true
            }
            if (path == "/__srvlog") {                   /* 3.9: стенд v51 подтягивает журнал сервера в отчёт */
                val a = JSONArray()
                synchronized(srvRing) { for (l in srvRing) a.put(l) }
                val b = JSONObject().put("streams", a).toString().toByteArray(Charsets.UTF_8)
                try {
                    writeHead(out, 200, "application/json; charset=utf-8", b.size.toLong(), null, null)
                    if (req.method == "GET") out.write(b)
                } catch (e: Exception) {}
                srvRec("GET /__srvlog → 200 ${b.size / 1024}КБ")
                return true
            }
            if (path == "/list") {                       /* 3.5: список медиа — лаборатории не нужен мост */
                serveList(out, req)
                return true
            }
            if (path == "/" || path == "/index.html" || path == "/plenka.html") {
                val html = htmlBytes()
                if (html == null) {
                    writeSimple(out, 500, "text/plain; charset=utf-8", "app asset missing")
                    return true
                }
                writeHead(out, 200, "text/html; charset=utf-8", html.size.toLong(), null, null)
                if (req.method == "GET") out.write(html)
                return true                                       // статику отдаём в один коннект
            }
            val tm = THUMB_ID.find(path)                       /* 2.4: /t/<k>/<id> — миниатюры */
            if (tm != null) {
                serveThumb(out, req, tm.groupValues[1], tm.groupValues[2].toLongOrNull() ?: -1L)
                return true
            }
            val m = MEDIA_ID.find(path)
            if (m != null) {
                serveMedia(out, req, m.groupValues[1], m.groupValues[2].toLongOrNull() ?: -1L)
                return true   // заголовок говорит Connection: close — закрываем честно; loopback-коннект стоит ~0
            }
            if (path == "/favicon.ico") {
                writeHead(out, 204, "image/x-icon", 0, null, null)
                return true
            }
            writeSimple(out, 404, "text/plain; charset=utf-8", "not found")
            return true
        }

        private fun statusText(status: Int): String = when (status) {
            200 -> "OK"; 204 -> "No Content"; 206 -> "Partial Content"
            404 -> "Not Found"; 416 -> "Range Not Satisfiable"; 500 -> "Server Error"
            else -> "Error"
        }

        private fun writeHead(out: OutputStream, status: Int, type: String, len: Long, contentRange: String?, etag: String?, extra: String? = null) {
            val sb = StringBuilder(256)
            sb.append("HTTP/1.1 ").append(status).append(' ').append(statusText(status)).append("\r\n")
            sb.append("Content-Type: ").append(type).append("\r\n")
            if (len > 0 || status == 204 || status == 404 || status == 500) sb.append("Content-Length: ").append(len).append("\r\n")
            if (len > 0 && status != 204) sb.append("Accept-Ranges: bytes\r\n")
            if (contentRange != null) sb.append("Content-Range: ").append(contentRange).append("\r\n")
            if (etag != null) sb.append("ETag: \"").append(etag).append("\"\r\n")
            if (extra != null) sb.append(extra.replace("\r", " ").replace("\n", " ")).append("\r\n")
            sb.append("Cache-Control: no-cache\r\n")
            sb.append("Connection: close\r\n")
            sb.append("\r\n")
            out.write(sb.toString().toByteArray(Charsets.ISO_8859_1))
        }

        private fun writeSimple(out: OutputStream, status: Int, type: String, body: String) {
            try {
                writeHead(out, status, type, body.length.toLong(), null, null)
                out.write(body.toByteArray())
            } catch (e: Exception) {}
        }

        private fun qParam(raw: String, key: String): String? {
            val q = raw.substringAfter('?', "")
            if (q.isEmpty()) return null
            for (p in q.split('&')) {
                val kv = p.split('=', limit = 2)
                if (kv.size == 2 && kv[0] == key) {
                    return try { java.net.URLDecoder.decode(kv[1], "UTF-8") } catch (e: Exception) { kv[1] }
                }
            }
            return null
        }

        private fun mimeFor(name: String, stored: String, video: Boolean): String {
            val m = stored.lowercase(Locale.US)
            if (m.startsWith("video/") || m.startsWith("audio/")) return stored
            // MediaStore иногда лжёт (application/octet-stream) — спасает расширение
            val ext = name.substringAfterLast('.', "").lowercase(Locale.US)
            val byExt = when (ext) {
                "mp4", "m4v", "mp4v" -> "video/mp4"
                "webm" -> "video/webm"
                "mov" -> "video/quicktime"
                "3gp", "3gpp" -> "video/3gpp"
                "3g2" -> "video/3gpp2"
                "mp3" -> "audio/mpeg"
                "m4a", "m4b" -> "audio/mp4"
                "aac" -> "audio/aac"
                "ogg", "oga", "opus" -> "audio/ogg"
                "wav" -> "audio/wav"
                "flac" -> "audio/flac"
                else -> if (video) "video/mp4" else "audio/mpeg"
            }
            return byExt
        }

        /** 2.4: /t/<k>/<id> — миниатюра: видео = первый кадр (MediaMetadataRetriever),
            аудио = встроенная обложка. Диск-кэш, генерация в thumbPool;
            r=<размер>-<mtime> в URL — смена файла = новая ревизия (кэш не врёт) */
        /** 3.5: /list — JSON всех медиа (последний скан медиатеки + ручной выбор).
            Лаборатория /seek работает даже в Chrome без моста: цель выбирается из списка */
        private fun serveList(out: OutputStream, req: Request) {
            val t0 = System.currentTimeMillis()
            val json = try { listJson() } catch (e: Exception) {
                Log.w(TAG, "list: ${e.javaClass.simpleName}: ${e.message}")
                JSONObject().put("ok", false).put("err", "list")
                    .put("msg", "${e.javaClass.simpleName}: ${e.message}").toString()
            }
            val b = json.toByteArray(Charsets.UTF_8)
            try {
                writeHead(out, 200, "application/json; charset=utf-8", b.size.toLong(), null, null)
                if (req.method == "GET") out.write(b)
            } catch (e: Exception) {}
            srvRec("GET /list → 200 ${b.size / 1024}КБ ${System.currentTimeMillis() - t0}мс")
        }
        private fun listJson(): String {
            val items = JSONArray()
            var scan: String? = lastScanJson
            if (scan == null) scan = scanMediaJson()
            try {
                val arr = JSONObject(scan ?: "null").optJSONArray("items")
                if (arr != null) for (i in 0 until arr.length()) items.put(arr.get(i))
            } catch (e: Exception) {}
            try {
                regLoad()
                val regs = synchronized(regLock) { ArrayList(pickedReg) }
                for (r in regs) items.put(JSONObject()
                    .put("k", "c").put("id", r.seq).put("n", r.name)
                    .put("s", r.size).put("d", r.dur).put("w", r.w).put("h", r.h))
            } catch (e: Exception) {}
            return JSONObject().put("ok", true).put("items", items).toString()
        }
        private fun serveThumb(out: OutputStream, req: Request, kind: String, id: Long) {
            if (id < 0) { writeSimple(out, 404, "image/jpeg", "bad id"); return }
            val vol = qParam(req.rawPath, "vol")
            val rev = qParam(req.rawPath, "r") ?: "0"
            val etag = "th-$kind-${vol ?: "p"}-$id-$rev"
            val t0 = System.currentTimeMillis()
            val inm = req.headers["if-none-match"]
            if (inm != null && inm.contains(etag)) {
                try {
                    out.write(("HTTP/1.1 304 Not Modified\r\nETag: \"$etag\"\r\n" +
                        "Cache-Control: max-age=604800\r\nConnection: close\r\n\r\n")
                        .toByteArray(Charsets.ISO_8859_1))
                } catch (e: Exception) {}
                srvRec("t /$kind/$id → 304 (кэш) ${System.currentTimeMillis() - t0}мс")
                return
            }
            val res = thumbBytes(kind, id, vol, rev)
            val bytes = res.bytes
            if (bytes == null) {
                srvRec("t /$kind/$id → 404 (нет кадра/арта) ${System.currentTimeMillis() - t0}мс")
                writeSimple(out, 404, "image/jpeg", "no art")
                return
            }
            val mime = if (bytes.size > 4 && bytes[0].toInt() == 0x89 && bytes[1] == 'P'.code.toByte()) "image/png" else "image/jpeg"
            try {
                val sb = StringBuilder(256)
                sb.append("HTTP/1.1 200 OK\r\nContent-Type: ").append(mime).append("\r\n")
                    .append("Content-Length: ").append(bytes.size).append("\r\n")
                    .append("ETag: \"").append(etag).append("\"\r\n")
                /* 3.7: метка кадра для подложки: мс от старта (первый кадр = 0..150мс) или
                   3600000 — «не первый» (дальний фолбэк) — страница кладёт чистый чёрный */
                if (kind == "v" || (kind == "c" && res.frameUs != -2L)) {
                    val ms = if (res.frameUs >= 0) res.frameUs / 1000 else 3600000
                    sb.append("X-Plenka-FrameT: ").append(ms).append("\r\n")
                }
                sb.append("Cache-Control: max-age=604800\r\nConnection: close\r\n\r\n")
                out.write(sb.toString().toByteArray(Charsets.ISO_8859_1))
                if (req.method == "GET") out.write(bytes)
            } catch (e: Exception) {}
            srvRec("t /$kind/$id → 200 ${bytes.size / 1024}КБ ${if (res.frameUs >= 0) "кадр ${res.frameUs / 1000}мс" else if (res.frameUs == (-1).toLong()) "дальний" else "арт"} ${System.currentTimeMillis() - t0}мс")
        }

        private fun serveMedia(out: OutputStream, req: Request, kind: String, id: Long) {
            if (id < 0) { writeSimple(out, 404, "text/plain; charset=utf-8", "bad id"); return }
            if (kind == "c") { servePicked(out, req, id); return }

            val vol = qParam(req.rawPath, "vol")
            val collection: Uri = when {
                kind == "v" && vol != null && Build.VERSION.SDK_INT >= 29 ->
                    MediaStore.Video.Media.getContentUri(vol)
                kind == "v" -> MediaStore.Video.Media.EXTERNAL_CONTENT_URI
                vol != null && Build.VERSION.SDK_INT >= 29 ->
                    MediaStore.Audio.Media.getContentUri(vol)
                else -> MediaStore.Audio.Media.EXTERNAL_CONTENT_URI
            }
            val uri = ContentUris.withAppendedId(collection, id)

            /* ═══ 3.9: ovh-кэш — hit без запроса к MediaStore и без открытия ═══ */
            if (qParam(req.rawPath, "ovh") != null) {
                val okey = "pl-$kind-${vol ?: "p"}-$id"
                val hit = fdGet(okey)
                if (hit != null) {
                    hit.last = System.currentTimeMillis()
                    if (serveOvh(out, req, hit)) return
                    fdDrop(okey)     /* дескриптор мёртв/не читается pread'ом — открываем заново */
                }
            }

            var size = -1L
            var storedMime = ""
            var name = ""
            var dataPath: String? = null
            try {
                contentResolver.query(uri, arrayOf(
                    MediaStore.MediaColumns.DISPLAY_NAME,
                    MediaStore.MediaColumns.MIME_TYPE,
                    MediaStore.MediaColumns.SIZE,
                    MediaStore.MediaColumns.DATA      /* 2.5: для фолбэка прямым путём */
                ), null, null, null)?.use { c ->
                    if (c.moveToFirst()) {
                        name = c.getString(0) ?: ""
                        storedMime = c.getString(1) ?: ""
                        size = c.getLong(2)
                        dataPath = try { c.getString(3) } catch (e: Exception) { null }
                    }
                }
            } catch (e: Exception) { Log.w(TAG, "meta /$kind/$id: ${e.javaClass.simpleName}: ${e.message}") }

            /* ═══ 2.5: цепочка открытий ═══ AFD → PFD → прямой путь (DATA).
               Диагноз 2.4: /v/1000008277 стабильно отдавал «404 gone» — исключение
               ContentResolver глоталось молча (ни причины, ни запасного пути).
               FUSE/MediaProvider на части файлов кидает FileNotFoundException при
               живом файле — прямой путь открывает его мимо провайдера; какая ветка
               сработала и почему — в журнал (srvRec/ДИАГ) и в заголовок X-Plenka-Err */
            var afd: AssetFileDescriptor? = null
            var openNote = ""
            var firstErr: Exception? = null
            try {
                afd = contentResolver.openAssetFileDescriptor(uri, "r")
            } catch (e: Exception) { firstErr = e }
            if (afd == null) {
                openNote = "afd:" + (firstErr?.javaClass?.simpleName ?: "null")
                if (name.isEmpty() && firstErr == null) openNote = "row-gone"
                try {
                    val pfd = contentResolver.openFileDescriptor(uri, "r")
                    if (pfd != null) {
                        afd = AssetFileDescriptor(pfd, 0L, pfd.statSize)
                        openNote = "pfd-fallback"
                    } else openNote += " pfd:null"
                } catch (e2: Exception) { openNote += " pfd:${e2.javaClass.simpleName}" }
            }
            if (afd == null && dataPath != null) {
                try {
                    val f = File(dataPath!!)
                    if (f.exists() && f.canRead()) {
                        val pfd = ParcelFileDescriptor.open(f, ParcelFileDescriptor.MODE_READ_ONLY)
                        afd = AssetFileDescriptor(pfd, 0L, f.length())
                        openNote += " raw-path-opened(" + f.length() / 1048576 + "MB)"
                        if (size <= 0) size = f.length()
                    } else openNote += " path:${if (f.exists()) "no-read" else "file-missing"}"
                } catch (e3: Exception) { openNote += " path:${e3.javaClass.simpleName}" }
            }
            if (afd != null) {
                if (openNote.isNotEmpty()) srvRec("${req.method} /$kind/$id → 200/206 через $openNote")
                val fbHdr = if (openNote.isNotEmpty()) "X-Plenka-Fallback: " + asciiOnly(openNote) else null   /* 2.5: префлайт страницы увидит и залогирует */
                val mimeC = mimeFor(name, storedMime, kind == "v")
                val etagC = "pl-$kind-${vol ?: "p"}-$id"
                if (qParam(req.rawPath, "ovh") != null && size > 0) {
                    /* 3.9: дескриптор — в ovh-кэш; следующие сотни Range-фетчей моста
                       возьмут его hit'ом, без ContentResolver/FUSE */
                    val okey = etagC
                    val ent = FdEntry(afd, size, mimeC, etagC)
                    fdPut(okey, ent)
                    if (serveOvh(out, req, ent)) return
                    /* pread не вышел (провайдер отдал pipe?) — выкидываем из кэша БЕЗ
                       закрытия: ниже afd отдастся serveAfd и закроется штатно */
                    synchronized(fdLock) { if (fdCache[okey] === ent) fdCache.remove(okey) }
                }
                try {
                    serveAfd(out, req, afd, mimeC, size, etagC, fbHdr)
                } finally {
                    try { afd.close() } catch (e: Exception) {}
                }
                return
            }
            /* полное фиаско: причина — в тело ответа, заголовок и журнал (ДИАГ покажет) */
            val why = firstErr?.let { "${it.javaClass.simpleName}: ${it.message?.take(90) ?: ""}" }
                ?: if (name.isEmpty()) "no MediaStore row" else "fd=null"
            srvRec("${req.method} /$kind/$id → 404 gone ($openNote · $why)")
            Log.w(TAG, "open /$kind/$id failed: $openNote · $why", firstErr)
            try { writeErr(out, 404, "gone", "$openNote $why") } catch (e: Exception) {}
        }

        /** 3.9: Range-раздача из ovh-кэша. Os.pread не двигает позицию fd и не закрывает
            его — поток-безопасно без замков. Проба 1 байтом ДО головы: мёртвый fd/pipe —
            уходим в обычный путь без единого отосланного байта. */
        private fun serveOvh(out: OutputStream, req: Request, e: FdEntry): Boolean {
            val t0 = System.currentTimeMillis()
            val total = e.size
            if (total <= 0) return false
            var start = 0L
            var endIncl = total - 1
            var partial = false
            val rng = req.range
            if (rng != null) {
                val mm = RANGE_RE.find(rng.trim())
                if (mm != null) {
                    val a = mm.groupValues[1]
                    val b = mm.groupValues[2]
                    if (a.isEmpty() && b.isNotEmpty()) {
                        val n = (b.toLongOrNull() ?: 0L).coerceAtMost(total)
                        start = total - n; endIncl = total - 1
                    } else if (a.isNotEmpty()) {
                        start = a.toLongOrNull() ?: 0L
                        if (b.isNotEmpty()) endIncl = (b.toLongOrNull() ?: 0L).coerceAtMost(total - 1)
                    }
                    if (start >= total) {
                        val sb = StringBuilder(128)
                        sb.append("HTTP/1.1 416 Range Not Satisfiable\r\n")
                            .append("Content-Range: bytes */").append(total).append("\r\n")
                            .append("Content-Length: 0\r\nConnection: close\r\n\r\n")
                        try { out.write(sb.toString().toByteArray()) } catch (er: Exception) {}
                        srvRec("${req.method} /${e.etag} r=$rng → 416 (start=$start ≥ total=$total) ovh")
                        return true
                    }
                    if (start > endIncl) endIncl = total - 1
                    partial = true
                }
            }
            val fd = e.afd.fileDescriptor
            val base = e.afd.startOffset
            val len = endIncl - start + 1
            val probe = try { Os.pread(fd, ByteBuffer.wrap(ByteArray(1)), base + start) } catch (er: Exception) { -1 }
            if (probe < 0) return false                    /* fd мёртв или не умеет pread — обычный путь */
            writeHead(out, if (partial) 206 else 200, e.mime, len,
                if (partial) "bytes $start-$endIncl/$total" else null, e.etag)
            var written = 0L
            if (req.method == "GET" && len > 0) {
                val buf = ByteArray(64 * 1024)
                var pos = base + start
                var remaining = len
                var shortRead = false
                while (remaining > 0) {
                    val want = minOf(buf.size.toLong(), remaining).toInt()
                    val n = try { Os.pread(fd, ByteBuffer.wrap(buf, 0, want), pos) } catch (er: Exception) { -1 }
                    if (n <= 0) { shortRead = true; break }
                    try { out.write(buf, 0, n) } catch (ew: Exception) { shortRead = true; break }
                    pos += n; remaining -= n; written += n
                }
                if (shortRead && written < len) {
                    req.rst = true                        /* обещание не выполнено — RST, клиент перепросит (как в 3.8) */
                    srvRec("${req.method} /${e.etag} r=${req.range ?: "-"} → 206 ОБРЫВ(ovh): обещано ${len / 1024}КБ, прочитано ${written / 1024}КБ — RST")
                }
            }
            srvRec("${req.method} /${e.etag} r=${req.range ?: "-"} → ${if (partial) 206 else 200} " +
                "${(if (req.method == "GET") written else len) / 1024}КБ/${total / 1024}КБ ${System.currentTimeMillis() - t0}мс ovh")
            return true
        }

        /** 2.5: HTTP-заголовки обязаны быть ASCII (кириллица в ISO-8859-1 превращается в мусор) */
        private fun asciiOnly(s: String): String {
            val sb = StringBuilder(s.length)
            for (c in s) when {
                c.code in 32..126 -> sb.append(c)
                c == '·' -> sb.append("|")
                else -> if (sb.isEmpty() || sb[sb.length - 1] != ' ') sb.append(' ')
            }
            return sb.toString().trim()
        }

        /** 2.5: ошибка с причиной — заголовок X-Plenka-Err читает префлайт страницы,
            тело короткое (медиа-элемент на 404 всё равно погаснет) */
        private fun writeErr(out: OutputStream, status: Int, body: String, detail: String?) {
            try {
                val b = body.toByteArray(Charsets.UTF_8)
                val sb = StringBuilder(256)
                sb.append("HTTP/1.1 ").append(status).append(' ').append(statusText(status)).append("\r\n")
                sb.append("Content-Type: text/plain; charset=utf-8\r\n")
                sb.append("Content-Length: ").append(b.size).append("\r\n")
                if (detail != null) sb.append("X-Plenka-Err: ")
                    .append(detail.replace("\r", " ").replace("\n", " ").take(120)).append("\r\n")
                sb.append("Cache-Control: no-store\r\nConnection: close\r\n\r\n")
                sb.replace(0, sb.length, asciiOnly(sb.toString()))   /* заголовки — только ASCII */
                out.write(sb.toString().toByteArray(Charsets.ISO_8859_1))
                out.write(b)
            } catch (e: Exception) {}
        }

        /** файл ручного выбора: content-URI из реестра, живой резолв */
        private fun servePicked(out: OutputStream, req: Request, seq: Long) {
            regLoad()
            val rec = synchronized(regLock) { pickedReg.find { it.seq == seq } }
            if (rec == null) { writeErr(out, 404, "gone", "реестр ручного выбора вычищен") ; return }
            var afd: AssetFileDescriptor? = null
            try {
                afd = contentResolver.openAssetFileDescriptor(rec.uri, "r")
                    ?: throw IOException("fd null")
                serveAfd(out, req, afd, mimeFor(rec.name, rec.mime, rec.k == "v"), rec.size, "pl-c-$seq")
            } catch (e: Exception) {
                // право/файл умерли — запись реестра вычищаем, чтобы не висела мёртвой
                srvRec("${req.method} /c/$seq → 404 gone (${e.javaClass.simpleName}: ${e.message?.take(80)}) — реестр вычищен")
                synchronized(regLock) { pickedReg.removeAll { it.seq == seq } }
                regSave()
                try { writeErr(out, 404, "gone", "${e.javaClass.simpleName}: ${e.message?.take(90)}") } catch (e2: Exception) {}
            } finally {
                try { afd?.close() } catch (e: Exception) {}
            }
        }

        /** общее ядро: Range-раздача AssetFileDescriptor без копирования */
        private fun serveAfd(out: OutputStream, req: Request, afd: AssetFileDescriptor, mime: String, sizeHint: Long, etag: String, extra: String? = null) {
            val t0 = System.currentTimeMillis()      /* 2.4: каждая выдача — в журнал (ДИАГ/logcat) */
            var total = sizeHint
            if (total <= 0) total = afd.length
            if (total <= 0) {
                try { total = FileInputStream(afd.fileDescriptor).channel.size() - afd.startOffset } catch (e: Exception) {}
            }
            if (total <= 0) {
                writeSimple(out, 500, "text/plain; charset=utf-8", "unknown size")
                srvRec("${req.method} /$etag → 500 unknown size")
                return
            }

            var start = 0L
            var endIncl = total - 1
            var partial = false
            val rng = req.range
            if (rng != null) {
                val mm = RANGE_RE.find(rng.trim())
                if (mm != null) {
                    val a = mm.groupValues[1]
                    val b = mm.groupValues[2]
                    if (a.isEmpty() && b.isNotEmpty()) {
                        val n = (b.toLongOrNull() ?: 0L).coerceAtMost(total)
                        start = total - n; endIncl = total - 1
                    } else if (a.isNotEmpty()) {
                        start = a.toLongOrNull() ?: 0L
                        if (b.isNotEmpty()) endIncl = (b.toLongOrNull() ?: 0L).coerceAtMost(total - 1)
                    }
                    if (start >= total) {
                        val sb = StringBuilder(128)
                        sb.append("HTTP/1.1 416 Range Not Satisfiable\r\n")
                            .append("Content-Range: bytes */").append(total).append("\r\n")
                            .append("Content-Length: 0\r\nConnection: close\r\n\r\n")
                        try { out.write(sb.toString().toByteArray()) } catch (e: Exception) {}
                        srvRec("${req.method} /$etag r=$rng → 416 (start=$start ≥ total=$total)")
                        return
                    }
                    if (start > endIncl) endIncl = total - 1
                    partial = true
                }
            }

            val len = endIncl - start + 1
            writeHead(out, if (partial) 206 else 200, mime, len,
                if (partial) "bytes $start-$endIncl/$total" else null, etag, extra)

            var written = 0L
            if (req.method == "GET" && len > 0) {
                val ch = FileInputStream(afd.fileDescriptor).channel
                try {
                    ch.position(afd.startOffset + start)      // lseek: дальний seek не читает гигабайты
                    var remaining = len
                    val buf = ByteArray(64 * 1024)
                    val bb = ByteBuffer.wrap(buf)
                    var shortRead = false
                    while (remaining > 0) {
                        bb.clear()
                        bb.limit(minOf(buf.size.toLong(), remaining).toInt())
                        val n = ch.read(bb)
                        if (n < 0) { shortRead = true; break }   /* EOF раньше обещанного */
                        if (n == 0) continue
                        out.write(buf, 0, n)
                        remaining -= n
                        written += n
                    }
                    /* 3.8: FUSE/MediaProvider на гигантах иногда отдаёт МЕНЬШЕ обещанного
                       Content-Length — клиент тогда висит на обещании ВЕЧНО («сик завис»,
                       «чёрный экран так долго, что думал зависло»). Голову уже не отозвать:
                       рвём сокет RST — Chromium считает это сетным сбоем и сам перепрашивает
                       диапазон; причина честно пишется в журнал/ДИАГ */
                    if (shortRead && written < len) {
                        req.rst = true
                        srvRec("${req.method} /$etag r=${req.range ?: "-"} → 206 ОБРЫВ: обещано ${len / 1024}КБ, прочитано ${written / 1024}КБ — RST, клиент перепросит")
                    }
                } finally {
                    try { ch.close() } catch (e: Exception) {}
                }
            }
            srvRec("${req.method} /$etag r=${req.range ?: "-"} → ${if (partial) 206 else 200} " +
                "${(if (req.method == "GET") written else len) / 1024}КБ/${total / 1024}КБ ${System.currentTimeMillis() - t0}мс")
        }
    }
}
