#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Патч натива 3.17 → 3.18 (v65): безопасность и устойчивость оболочки.

  N01 Токен локального моста: SecureRandom, хранится в filesDir; все пути данных
      (/v,/a,/c,/t,/list,/__medialist,/__srvlog) отвечают 404 без валидного токена;
      страница грузится с ?tok=… (в HTML — natvTok, build65.py). Плюс проверка Host.
  N02 Порт-фолбэк: 8977 занят → пробуем 8978..8986; фактический порт — в SRV_PORT.
  N03 ovh-кэш: счётчик пользователей FdEntry — закрытие вытесненного/простаивавшего
      дескриптора больше не рвёт чужой pread (гонка fdGet/fdPut vs serveOvh).
  N04 serveAfd: двойной close fd устранён (Os.lseek+Os.pread вместо FileInputStream.
      channel, чей close() гасил fd, принадлежащий AssetFileDescriptor).
  N05 regSave атомарно: tmp+rename (краш посреди записи больше не теряет реестр).
  N06 MediaSession: активна с первого mediaState(playing=true), а не с onCreate —
      пустая сессия больше не перехватывает кнопки чужих плееров.
  N07 POST_NOTIFICATIONS: один раз после 20с воспроизведения (урок 3.11 учтён —
      не в момент старта).
  N08 Цикл диалогов прав: после отказа в рамках сессии диалог не открывается снова.
  N09 WakeLock: таймаут 5 мин с автопродлением (зависший playing не держит CPU вечно).
  N10 Версия: APP_VERSION 3.18 (v65), versionCode 147.
  N11 build.gradle.kts: пароли keystore из окружения (PLENKA_KS_PATH/ALIAS/PASS),
      в git больше не лежат; без env — unsigned-сборка (подписывает apksigner).
  N12 Манифест: usesCleartextTraffic → network_security_config (cleartext только
      для 127.0.0.1/localhost).
  N13 build_apk61..64.sh: --ks-pass env: вместо env:PLENKA_KS_PASS.
  N14 mock_native_server.py: bind 127.0.0.1 вместо 0.0.0.0.
  N15 .gitignore: *.keystore/*.jks/node_modules и пр.
"""
import sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def patch_file(path, fixes, label):
    p = os.path.join(ROOT, path)
    src = open(p, encoding='utf-8').read()
    ok = True
    for name, old, new in fixes:
        n = src.count(old)
        if n != 1:
            print(f"[FAIL] {label} :: {name}: якорь найден {n} раз(а)")
            ok = False
            continue
        src = src.replace(old, new)
        print(f"[OK]   {label} :: {name}")
    if ok:
        open(p, 'w', encoding='utf-8').write(src)
    return ok

# ═══════════════════════════ MainActivity.kt ═══════════════════════════
MA = []

MA.append(('N01 companion: SRV_PORT/SRV_TOKEN/RC_NOTIF + версия',
"""        private const val TAG = "PLENKA"
        private const val PORT = 8977
        private const val APP_VERSION = "PLENKA native 3.17 (v64)"
        private const val RC_PERM = 7""",
"""        private const val TAG = "PLENKA"
        private const val PORT = 8977
        private const val APP_VERSION = "PLENKA native 3.18 (v65)"
        private const val RC_PERM = 7
        private const val RC_NOTIF = 10

        /* 3.18: фактические параметры локального моста. Токен закрывает главный
           аудит-риск: loopback 127.0.0.1 на Android ОБЩИЙ для всех приложений —
           без токена любое соседнее приложение с обычным INTERNET-разрешением
           выкачивало всю медиатеку (/list + Range по /v/<id>) без единого
           разрешения. Токен персистентный (filesDir/srvtoken): URL в IDB
           переживают рестарт, страница получает его через ?tok= в loadUrl. */
        @Volatile var SRV_PORT: Int = PORT
        @Volatile var SRV_TOKEN: String = ""
"""))

MA.append(('N03 FdEntry: users/zombie',
"""    private class FdEntry(val afd: AssetFileDescriptor, val size: Long, val mime: String, val etag: String) {
        @Volatile var last: Long = System.currentTimeMillis()
    }""",
"""    private class FdEntry(val afd: AssetFileDescriptor, val size: Long, val mime: String, val etag: String) {
        @Volatile var last: Long = System.currentTimeMillis()
        /* 3.18: сколько потоков сейчас читает через serveOvh. Закрытие вытесненного/
           простаивавшего дескриптора под живым pread давало RST и «заикания» MSE:
           теперь закрываем только при users==0, иначе закрывает последний читатель */
        @Volatile var users: Int = 0
        @Volatile var zombie: Boolean = false
    }

    /* 3.18: закрыть выведенную из кэша запись, если её никто не читает;
       читающие закроют сами при обнулении счётчика */
    private fun fdRetire(e: FdEntry) {
        synchronized(fdLock) {
            e.zombie = true
            if (e.users <= 0) { try { e.afd.close() } catch (ex: Exception) {} }
        }
    }"""))

MA.append(('N03 fdGet: простой без закрытия под pread',
"""        while (iter.hasNext()) {                        /* 45с без запросов — закрываем */
            val en = iter.next()
            if (now - en.value.last > 45_000) {
                try { en.value.afd.close() } catch (e: Exception) {}
                srvRec("fd-cache: ${en.key} закрыт по простою 45с")
                iter.remove()
            }
        }""",
"""        while (iter.hasNext()) {                        /* 45с без запросов — закрываем */
            val en = iter.next()
            if (now - en.value.last > 45_000) {
                iter.remove()
                fdRetire(en.value)                      /* 3.18: не рвём чужой pread */
                srvRec("fd-cache: ${en.key} выведен по простою 45с")
            }
        }"""))

MA.append(('N03 fdPut: вытеснение/коллизия без закрытия под pread',
"""    private fun fdPut(key: String, e: FdEntry) {
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
    }""",
"""    private fun fdPut(key: String, e: FdEntry) {
        synchronized(fdLock) {
            val old = fdCache.put(key, e)
            if (old != null && old !== e) fdRetire(old)     /* 3.18: не рвём чужой pread */
            if (fdCache.size > 6) {                     /* LRU: выкидываем самый холодный */
                var minK: String? = null
                var minV = Long.MAX_VALUE
                for ((k, v) in fdCache) if (v.last < minV) { minV = v.last; minK = k }
                val v = minK?.let { fdCache.remove(it) }
                if (v != null) fdRetire(v)                  /* 3.18 */
            }
        }
    }"""))

MA.append(('N03 fdDrop: мягко',
"""    private fun fdDrop(key: String) {
        synchronized(fdLock) {
            val v = fdCache.remove(key) ?: return
            try { v.afd.close() } catch (e: Exception) {}
        }
    }""",
"""    private fun fdDrop(key: String) {
        synchronized(fdLock) {
            val v = fdCache.remove(key) ?: return
            fdRetire(v)                                     /* 3.18: не рвём чужой pread */
        }
    }"""))

MA.append(('N05 regSave атомарно',
"""                File(filesDir, "picked.json").writeText(a.toString())""",
"""                /* 3.18: атомарная запись — краш посреди writeText делал битый JSON,
                   и весь реестр ручного выбора молча исчезал на следующем старте */
                val f = File(filesDir, "picked.json")
                val tmp = File(filesDir, "picked.json.tmp")
                tmp.writeText(a.toString())
                if (!tmp.renameTo(f)) {
                    f.delete()
                    if (!tmp.renameTo(f)) tmp.delete()
                }"""))

MA.append(('N02+N01 start(): фолбэк портов + токен',
"""        fun start() {
            try {
                val s = ServerSocket()
                s.reuseAddress = true
                s.bind(InetSocketAddress(InetAddress.getByName("127.0.0.1"), PORT), 16)
                srv = s
                alive.set(true)""",
"""        fun start() {
            /* 3.18: токен моста — персистентный, читается до bind */
            try {
                val tf = File(ctx.filesDir, "srvtoken")
                var t = try { tf.readText().trim() } catch (e: Exception) { "" }
                if (t.length < 32) {
                    val ab = ByteArray(24)
                    java.security.SecureRandom().nextBytes(ab)
                    t = ab.joinToString("") { "%02x".format(it) }
                    try { tf.writeText(t) } catch (e: Exception) {}
                }
                MainActivity.SRV_TOKEN = t
            } catch (e: Exception) { Log.e(TAG, "token: ${e.message}") }
            /* 3.18: порт занят (зомби-процесс и т.п.) — раньше сервер молча не вставал,
               а страница всё равно грузилась: вечный «чёрный экран». Теперь пробуем соседи */
            for (p in PORT..PORT + 9) {
                try {
                    val s = ServerSocket()
                    s.reuseAddress = true
                    s.bind(InetSocketAddress(InetAddress.getByName("127.0.0.1"), p), 16)
                    srv = s
                    MainActivity.SRV_PORT = p
                    break
                } catch (e: Exception) {
                    Log.w(TAG, "bind $p: ${e.message}")
                }
            }
            try {
                if (srv == null) {
                    Log.e(TAG, "server start FAIL: все порты $PORT..${PORT + 9} заняты")
                    return
                }
                alive.set(true)"""))

MA.append(('N02 start(): хвост (accept-поток + лог)',
"""                    while (alive.get()) {
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
        }""",
"""                    while (alive.get()) {
                        try {
                            val sock = srv?.accept() ?: break
                            pool.execute { serveSocket(sock) }
                        } catch (e: Exception) {
                            if (alive.get()) Log.w(TAG, "accept: ${e.message}")
                        }
                    }
                }, "plenka-http-accept").start()
                Log.i(TAG, "server listening 127.0.0.1:${MainActivity.SRV_PORT}")
            } catch (e: Exception) {
                Log.e(TAG, "server start FAIL: ${e.message}")
                srv = null
            }
        }"""))

MA.append(('N01 Request: разбор токена',
"""        private inner class Request(val method: String, val rawPath: String, val headers: Map<String, String>) {
            var rst = false   /* 3.8: ответ оборвался короче Content-Length — сокет рвём RST, клиент перепросит */
            val path: String get() = rawPath.substringBefore('?')
            val range: String? get() = headers["range"]""",
"""        private inner class Request(val method: String, val rawPath: String, val headers: Map<String, String>) {
            var rst = false   /* 3.8: ответ оборвался короче Content-Length — сокет рвём RST, клиент перепросит */
            val path: String get() = rawPath.substringBefore('?')
            val range: String? get() = headers["range"]
            /* 3.18: tok= из query — единственный ключ к данным моста */
            val tok: String?
                get() = rawPath.substringAfter('?', "").split('&')
                    .firstOrNull { it.startsWith("tok=") }?.substring(4)"""))

MA.append(('N01 serve(): гейт токена + Host',
"""        /** @return закрывать ли соединение после ответа */
        private fun serve(out: OutputStream, req: Request): Boolean {
            val path = req.path""",
"""        /** @return закрывать ли соединение после ответа */
        private fun serve(out: OutputStream, req: Request): Boolean {
            val path = req.path
            /* 3.18: гейт доступа. Статику (/,/seek,/lab,/favicon) отдаём всем — данных в ней нет;
               всё остальное — только с валидным токеном и с loopback-Host: чужое приложение
               (или страница из интернета, открытая в любом браузере устройства) данные не получит */
            if (path != "/" && path != "/index.html" && path != "/plenka.html" &&
                path != "/favicon.ico" && path != "/seek" && path != "/seek/" &&
                path != "/lab" && path != "/lab/") {
                val tok = req.tok
                val host = req.headers["host"]
                if (tok == null || tok != MainActivity.SRV_TOKEN ||
                    (host != null && !host.startsWith("127.0.0.1") && !host.startsWith("localhost"))) {
                    srvRec("${req.method} $path → 404 (доступ без токена/чужой Host)")
                    writeSimple(out, 404, "text/plain; charset=utf-8", "not found")
                    return true
                }
            }"""))

MA.append(('N02 PlenkaServer.listening(): наружный статус',
"""        fun stop() {
            alive.set(false)
            try { srv?.close() } catch (e: Exception) {}
            srv = null
        }""",
"""        fun stop() {
            alive.set(false)
            try { srv?.close() } catch (e: Exception) {}
            srv = null
        }

        fun listening(): Boolean = srv != null && alive.get()   /* 3.18: наружный статус для loadUrl */"""))

MA.append(('N02 loadUrl: фактический порт + токен',
"""        // сервер уже слушает (bind синхронный в start()) — страница не получит connection refused
        webView.loadUrl("http://127.0.0.1:$PORT/")
        Log.i(TAG, "native 3.17 started, version=$APP_VERSION sdk=${Build.VERSION.SDK_INT}")""",
"""        // сервер уже слушает (bind синхронный в start()) — страница не получит connection refused.
        // 3.18: токен моста в URL страницы; если bind так и не встал — честный тост вместо чёрного экрана
        if (SRV_TOKEN.isNotEmpty() && server?.listening() == true) {
            webView.loadUrl("http://127.0.0.1:$SRV_PORT/?tok=$SRV_TOKEN")
        } else {
            webView.loadDataWithBaseURL(null,
                "<html><body style=\\"background:#1d1810;color:#e8a33d;font-family:monospace;display:flex;align-items:center;justify-content:center;height:90%\\">ПЛЁНКА: локальный сервер не поднялся — перезапустите приложение</body></html>",
                "text/html; charset=utf-8", null, null)
            Toast.makeText(this, "ПЛЁНКА: локальный сервер не поднялся", Toast.LENGTH_LONG).show()
        }
        Log.i(TAG, "native 3.18 started, version=$APP_VERSION port=$SRV_PORT sdk=${Build.VERSION.SDK_INT}")"""))

MA.append(('N06+N07 mediaUpdate: активация сессии + разовое уведомление',
"""                val ms = mediaSession ?: return@runOnUiThread
                val o = o0
                val playing = o.optBoolean("playing", false)""",
"""                val ms = mediaSession ?: return@runOnUiThread
                val o = o0
                val playing = o.optBoolean("playing", false)
                if (playing) {
                    /* 3.18: сессия активна только пока реально играет — пустая активная сессия
                       с onCreate перехватывала медиа-кнопки наушников у чужих плееров */
                    if (!ms.isActive) { try { ms.setActive(true) } catch (e: Exception) {} }
                    notifAskTick()
                }"""))

MA.append(('N06 mediaInit: не активна до первой игры',
"""            ms.setActive(true)
            mediaSession = ms
            Log.i(TAG, "media session active")""",
"""            ms.setActive(false)                           /* 3.18: активация — по факту воспроизведения */
            mediaSession = ms
            Log.i(TAG, "media session created (inactive until first play)")"""))

MA.append(('N07+N08 поля: firstPlayingAt/notifAsked/permDeniedSession',
"""    @Volatile private var pipAuto = false   // видео играет → home-жест сворачивает в PiP
    @Volatile private var inPip = false
    @Volatile private var permDialogUp = false""",
"""    @Volatile private var pipAuto = false   // видео играет → home-жест сворачивает в PiP
    @Volatile private var inPip = false
    @Volatile private var permDialogUp = false
    @Volatile private var permDeniedSession = false   /* 3.18: отказ в рамках сессии — диалог не каруселим */
    @Volatile private var firstPlayingAt = 0L         /* 3.18: когда началась первая игра (для нотиф-диалога) */
    @Volatile private var notifAsked = false

    /* 3.18: POST_NOTIFICATIONS — один раз, после 20с воспроизведения (урок 3.11:
       диалог в момент первой игры срывал старт). До разрешения MediaStyle может
       не показаться в шторке на Android 13+ — тогда фоновые кнопки недоступны */
    private fun notifAskTick() {
        if (notifAsked || Build.VERSION.SDK_INT < 33) return
        if (firstPlayingAt == 0L) firstPlayingAt = System.currentTimeMillis()
        if (System.currentTimeMillis() - firstPlayingAt < 20_000L) return
        notifAsked = true
        try {
            if (checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                Log.i(TAG, "perm: POST_NOTIFICATIONS — запрос после 20с воспроизведения")
                runOnUiThread {
                    try { requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), RC_NOTIF) }
                    catch (e: Exception) { Log.w(TAG, "perm notif: ${e.message}") }
                }
            }
        } catch (e: Exception) {}
    }"""))

MA.append(('N08 maybeAskPerm: гвард сессионного отказа',
"""    private fun maybeAskPerm() {
        // partial (Android 14 «выбранные фото/видео») не переспрашиваем — скан покажет выбранное
        if (mediaPermState() != "none" || permDialogUp || isFinishing) return""",
"""    private fun maybeAskPerm() {
        // partial (Android 14 «выбранные фото/видео») не переспрашиваем — скан покажет выбранное.
        // 3.18: после отказа в этой сессии диалог не открываем снова — иначе onResume
        // открывал его бесконечной каруселью до системного «больше не спрашивать»
        if (mediaPermState() != "none" || permDialogUp || permDeniedSession || isFinishing) return"""))

MA.append(('N08 результат прав: фиксация отказа',
"""            val ok = grantResults.isNotEmpty() &&
                permissions.indices.all { grantResults.getOrNull(it) == PackageManager.PERMISSION_GRANTED }
            permDialogUp = false
            Log.i(TAG, "perm result: ok=$ok perms=${permissions.joinToString()}")""",
"""            val ok = grantResults.isNotEmpty() &&
                permissions.indices.all { grantResults.getOrNull(it) == PackageManager.PERMISSION_GRANTED }
            permDialogUp = false
            if (requestCode == RC_NOTIF) {
                Log.i(TAG, "perm result: NOTIFICATIONS ok=$ok")   /* 3.18: отдельный ветка — не мешает медиа-правам */
                return
            }
            permDeniedSession = !ok
            Log.i(TAG, "perm result: ok=$ok perms=${permissions.joinToString()}")"""))

MA.append(('N04 serveAfd: чтение через Os.lseek+Os.pread (двойной close устранён)',
"""            var written = 0L
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
                    }""",
"""            var written = 0L
            if (req.method == "GET" && len > 0) {
                /* 3.18: FileInputStream(...).channel.close() в finally закрывал fd,
                   ВЛАДЕЛЬЦЕМ которого является AssetFileDescriptor (второй close —
                   в serveMedia/servePicked): классический fd-reuse race. Читаем
                   через Os.lseek+Os.pread — fd остаётся в собственности afd */
                try {
                    val fdp = afd.fileDescriptor
                    var pos = afd.startOffset + start         // lseek: дальний seek не читает гигабайты
                    var remaining = len
                    val buf = ByteArray(64 * 1024)
                    var shortRead = false
                    while (remaining > 0) {
                        val want = minOf(buf.size.toLong(), remaining).toInt()
                        val n = Os.pread(fdp, ByteBuffer.wrap(buf, 0, want), pos)
                        if (n < 0) { shortRead = true; break }   /* EOF раньше обещанного */
                        if (n == 0) { shortRead = true; break }
                        out.write(buf, 0, n)
                        pos += n
                        remaining -= n
                        written += n
                    }"""))

MA.append(('N04 serveAfd: finally без close канала',
"""                    if (shortRead && written < len) {
                        req.rst = true
                        srvRec("${req.method} /$etag r=${req.range ?: "-"} → 206 ОБРЫВ: обещано ${len / 1024}КБ, прочитано ${written / 1024}КБ — RST, клиент перепросит")
                    }
                } finally {
                    try { ch.close() } catch (e: Exception) {}
                }
            }""",
"""                    if (shortRead && written < len) {
                        req.rst = true
                        srvRec("${req.method} /$etag r=${req.range ?: "-"} → 206 ОБРЫВ: обещано ${len / 1024}КБ, прочитано ${written / 1024}КБ — RST, клиент перепросит")
                    }
                } catch (e: Exception) {
                    srvRec("${req.method} /$etag чтение: ${e.javaClass.simpleName}: ${e.message?.take(80)}")
                }
            }"""))

MA.append(('N03 serveOvh: счётчик читателей',
"""        private fun serveOvh(out: OutputStream, req: Request, e: FdEntry): Boolean {
            val t0 = System.currentTimeMillis()
            val total = e.size
            if (total <= 0) return false""",
"""        private fun serveOvh(out: OutputStream, req: Request, e: FdEntry): Boolean {
            val t0 = System.currentTimeMillis()
            val total = e.size
            if (total <= 0) return false
            synchronized(fdLock) { e.users++ }                /* 3.18: закрытие под pread невозможно */
            try {
                return serveOvhInner(out, req, e)
            } finally {
                synchronized(fdLock) {
                    e.users--
                    if (e.zombie && e.users <= 0) { try { e.afd.close() } catch (ex: Exception) {} }
                }
            }
        }

        private fun serveOvhInner(out: OutputStream, req: Request, e: FdEntry): Boolean {
            val t0 = System.currentTimeMillis()
            val total = e.size"""))

# ═══════════════════════════ PlenkaService.kt ═══════════════════════════
SV = []

SV.append(('N09 WakeLock: таймаут + автопродление',
"""    private fun wlApply() {
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
    }""",
"""    private fun wlApply() {
        if (stPlaying) {
            if (wl == null) {
                try {
                    val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
                    wl = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "plenka:bgplay")
                        .also { it.setReferenceCounted(false) }
                } catch (e: Exception) { Log.w(TAG, "wl new: ${e.message}") }
            }
            try {
                wl?.let {
                    /* 3.18: acquire без таймаута держал CPU вечно, если playing застревал
                       при мёртвой странице. Берём на 5 минут и продлеваем циклом ниже */
                    if (!it.isHeld) { it.acquire(WL_RENEW_MS + 60_000L); Log.i(TAG, "bg: wakeLock взят (5мин+продление)") }
                }
            } catch (e: Exception) {}
            hd.removeCallbacks(wlRenew)
            hd.postDelayed(wlRenew, WL_RENEW_MS)
        } else {
            hd.removeCallbacks(wlRenew)
            try { wl?.let { if (it.isHeld) { it.release(); Log.i(TAG, "bg: wakeLock отпущен") } } }
            catch (e: Exception) {}
        }
    }

    /* 3.18: пока играет — продлеваем WakeLock каждые 3 минуты */
    private val wlRenew = Runnable {
        if (!running || !stPlaying) return@Runnable
        try { wl?.let { if (!it.isHeld) it.acquire(WL_RENEW_MS + 60_000L) } } catch (e: Exception) {}
        hd.postDelayed(wlRenew, WL_RENEW_MS)
    }"""))

SV.append(('N09 константа WL_RENEW_MS',
"""        private const val PAUSE_GRACE_MS = 60_000L""",
"""        private const val PAUSE_GRACE_MS = 60_000L
        private const val WL_RENEW_MS = 180_000L   /* 3.18: продление WakeLock каждые 3 минуты */"""))

SV.append(('N09 onDestroy: снять wlRenew',
"""    override fun onDestroy() {
        running = false
        hd.removeCallbacksAndMessages(null)""",
"""    override fun onDestroy() {
        running = false
        hd.removeCallbacksAndMessages(null)   /* 3.18: и wlRenew тоже */"""))

# ═══════════════════════════ Manifest / gradle / скрипты ═══════════════════════════
ok = True
ok = patch_file("plenka-native/app/src/main/java/ru/plenka/app/MainActivity.kt", MA, "MainActivity") and ok
ok = patch_file("plenka-native/app/src/main/java/ru/plenka/app/PlenkaService.kt", SV, "PlenkaService") and ok

ok = patch_file("plenka-native/app/src/main/AndroidManifest.xml", [
    ('N12 network security config',
"""    <application
        android:label="ПЛЁНКА"
        android:icon="@mipmap/ic_launcher"
        android:theme="@style/AppTheme"
        android:usesCleartextTraffic="true"
        android:hardwareAccelerated="true"
        android:allowBackup="true">""",
"""    <application
        android:label="ПЛЁНКА"
        android:icon="@mipmap/ic_launcher"
        android:theme="@style/AppTheme"
        android:networkSecurityConfig="@xml/network_security_config"
        android:hardwareAccelerated="true"
        android:allowBackup="true">"""),
], "Manifest") and ok

open(os.path.join(ROOT, "plenka-native/app/src/main/res/xml/network_security_config.xml"), "w", encoding="utf-8").write(
"""<?xml version="1.0" encoding="utf-8"?>
<!-- 3.18: cleartext разрешён ТОЛЬКО локальному мосту; глобальный
     usesCleartextTraffic="true" больше не ослабляет весь WebView -->
<network-security-config>
    <base-config cleartextTrafficPermitted="false" />
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="false">127.0.0.1</domain>
        <domain includeSubdomains="false">localhost</domain>
    </domain-config>
</network-security-config>
""")
print("[OK]   network_security_config.xml создан")

ok = patch_file("plenka-native/app/build.gradle.kts", [
    ('N10 версия 147/3.18',
"""        versionCode = 146
        versionName = "3.17\"""",
"""        versionCode = 147
        versionName = "3.18\""""),
    ('N11 пароли из окружения',
"""    signingConfigs {
        create("release") {
            storeFile = file("../plenka.keystore")
            storePassword = System.getenv("PLENKA_KS_PASS")   /* 3.19: литерал убран из git */
            keyAlias = "plenka"
            keyPassword = System.getenv("PLENKA_KS_PASS")   /* 3.19: литерал убран из git */
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            isShrinkResources = false
            signingConfig = signingConfigs.getByName("release")
        }""",
"""    signingConfigs {
        create("release") {
            /* 3.18: секреты больше не в git (аудит): путь/пароль — из окружения.
               Экспорт перед сборкой: PLENKA_KS_PATH/PLENKA_KS_ALIAS/PLENKA_KS_PASS.
               Без env — unsigned-сборка (подписывает apksigner отдельно) */
            storeFile = file(System.getenv("PLENKA_KS_PATH") ?: "../plenka.keystore")
            storePassword = System.getenv("PLENKA_KS_PASS")
            keyAlias = System.getenv("PLENKA_KS_ALIAS") ?: "plenka"
            keyPassword = System.getenv("PLENKA_KS_PASS")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            isShrinkResources = false
            signingConfig = if (System.getenv("PLENKA_KS_PASS") != null) signingConfigs.getByName("release") else null
        }"""),
], "gradle") and ok

import glob
for sh in sorted(glob.glob(os.path.join(ROOT, "scripts/build_apk6*.sh"))):
    src = open(sh, encoding='utf-8').read()
    if "env:PLENKA_KS_PASS" in src:
        src = src.replace(
            "--ks-pass env:PLENKA_KS_PASS --ks-key-alias plenka --key-pass env:PLENKA_KS_PASS",
            "--ks-pass env:PLENKA_KS_PASS --ks-key-alias \"${PLENKA_KS_ALIAS:-plenka}\" --key-pass env:PLENKA_KS_PASS")
        # guard: пароль обязан быть в окружении
        if "PLENKA_KS_PASS" not in src.split("\n\n")[0] and "PLENKA_KS_PASS=" not in src:
            lines = src.split("\n")
            for i, l in enumerate(lines):
                if l.startswith("set -e") or l.startswith("#!/"):
                    lines.insert(i + 1, ": \"${PLENKA_KS_PASS:?экспортируйте PLENKA_KS_PASS (и опц. PLENKA_KS_ALIAS/PLENKA_KS_PATH) перед сборкой}\"")
                    break
            src = "\n".join(lines)
        open(sh, 'w', encoding='utf-8').write(src)
        print(f"[OK]   {os.path.basename(sh)}: пароль из env")
    else:
        print(f"[SKIP] {os.path.basename(sh)}: env:PLENKA_KS_PASS не найден")

ok = patch_file("scripts/mock_native_server.py", [
    ('N14 bind 127.0.0.1',
"""    TS(("", PORT), H).serve_forever()""",
"""    TS(("127.0.0.1", PORT), H).serve_forever()   /* 3.18/аудит: мок отдаёт локальные файлы — слушаем только loopback */"""),
], "mock_native_server") and ok

gi_path = os.path.join(ROOT, ".gitignore")
gi = open(gi_path, encoding='utf-8').read()
need = ["*.keystore", "*.jks", "node_modules/", ".idea/", ".vscode/"]
add = [x for x in need if x not in gi]
if add:
    gi = gi.rstrip("\n") + "\n\n# 3.18/аудит: секреты и мусор не должны уехать в git никогда\n" + "\n".join(add) + "\n"
    open(gi_path, 'w', encoding='utf-8').write(gi)
    print("[OK]   .gitignore: добавлено " + ", ".join(add))

if not ok:
    print("\nЕсть неприменённые фиксы — патч натива НЕ полный.")
    sys.exit(1)
print("\nПатч натива 3.18 применён полностью.")
