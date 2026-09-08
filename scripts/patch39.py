#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kotlin 3.8 → 3.9 (страница v55 — база v51 из чата).

1) /seek — отдельный ассет plenka-seek.html (стенд v51, из 3.6): список файлов
   страница берёт сама с /__medialist (в Chrome моста нет);
2) /lab — ассет plenka-lab.html (видео-лаборатория v51, из 3.6);
3) /__medialist, /__srvlog — эндпоинты стенда v51;
4) ovh-кэш дескрипторов (как в 3.6): MSE-мост фетчит гигант сотнями коротких
   Range-запросов с ?ovh=0 — держим дескриптор открытым (LRU 6, простой 45с),
   чтение Os.pread (позиция fd не трогается, канал не закрывается);
5) версия 3.9 / v55, versionCode 120 (поверх 2.0–3.8)."""
import sys, io

SRC = '/home/z/my-project/plenka-native/app/src/main/java/ru/plenka/app/MainActivity.kt'
p = io.open(SRC, encoding='utf-8').read()

def rep(old, new, what, cnt=1):
    global p
    n = p.count(old)
    if n != cnt:
        print('FAIL: якорь %r найден %d раз (ожидалось %d)' % (what, n, cnt)); sys.exit(1)
    p = p.replace(old, new)
    print('ok: %s' % what)

# ── K1: версия ───────────────────────────────────────────────────────────────
rep('private const val APP_VERSION = "PLENKA native 3.8 (v54)"',
    'private const val APP_VERSION = "PLENKA native 3.9 (v55)"', 'APP_VERSION')

rep('Log.i(TAG, "native 3.8 started, version=$APP_VERSION sdk=${Build.VERSION.SDK_INT}")',
    'Log.i(TAG, "native 3.9 started, version=$APP_VERSION sdk=${Build.VERSION.SDK_INT}")',
    'стартовый лог')

# ── K2: import Os ────────────────────────────────────────────────────────────
rep('import android.view.WindowManager',
    'import android.view.WindowManager\nimport android.system.Os',
    'import Os')

# ── K3: поля ovh-кэша (активность) ──────────────────────────────────────────
rep('''    private val thumbInflight = ConcurrentHashMap<String, Future<ThumbRes>>()''',
    '''    private val thumbInflight = ConcurrentHashMap<String, Future<ThumbRes>>()

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
                srvRec("fd-cache: ${en.key} закрыт по простолю 45с")
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
    }''',
    'поля ovh-кэша')

# ── K4: onDestroy — закрыть кэш ──────────────────────────────────────────────
rep('''    override fun onDestroy() {
        server?.stop()
        server = null
        pool.shutdownNow()''',
    '''    override fun onDestroy() {
        server?.stop()
        server = null
        synchronized(fdLock) {                          /* 3.9: ovh-дескрипторы не утекают */
            for ((_, v) in fdCache) { try { v.afd.close() } catch (e: Exception) {} }
            fdCache.clear()
        }
        pool.shutdownNow()''',
    'onDestroy: закрыть ovh-кэш')

# ── K5: роуты /seek, /lab, /__medialist, /__srvlog ───────────────────────────
rep('''            if (path == "/seek" || path == "/seek/") {   /* 3.5: лаборатория перемотки — тот же ассет, страница сама видит путь */
                val html = htmlBytes()
                if (html == null) {
                    writeSimple(out, 500, "text/plain; charset=utf-8", "app asset missing")
                    return true
                }
                writeHead(out, 200, "text/html; charset=utf-8", html.size.toLong(), null, null)
                if (req.method == "GET") out.write(html)
                srvRec("GET /seek → 200 html ${html.size / 1024}КБ")
                return true
            }''',
    '''            if (path == "/seek" || path == "/seek/") {   /* 3.9: стенд перемотки — ассет v51 (вернули из 3.6):
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
            }''',
    'роуты /seek /lab /__medialist /__srvlog')

# ── K6: assetBytes (generic, рядом с htmlBytes) ──────────────────────────────
rep('''        private fun htmlBytes(): ByteArray? {''',
    '''        private val assetCache = HashMap<String, ByteArray>()   /* 3.9: стенды из assets — как главный ассет */
        private fun assetBytes(name: String): ByteArray? {
            synchronized(assetCache) {
                val c = assetCache[name]
                if (c != null) return if (c.isEmpty()) null else c
                val b = try { ctx.assets.open(name).use { it.readBytes() } } catch (e: Exception) { null } ?: ByteArray(0)
                assetCache[name] = b
                return if (b.isEmpty()) null else b
            }
        }
        private fun htmlBytes(): ByteArray? {''',
    'assetBytes')

# ── K7: serveMedia — ovh hit ─────────────────────────────────────────────────
rep('''            val uri = ContentUris.withAppendedId(collection, id)

            var size = -1L''',
    '''            val uri = ContentUris.withAppendedId(collection, id)

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

            var size = -1L''',
    'serveMedia: ovh hit')

# ── K8: serveMedia — ovh put перед serveAfd ─────────────────────────────────
rep('''            if (afd != null) {
                if (openNote.isNotEmpty()) srvRec("${req.method} /$kind/$id → 200/206 через $openNote")
                val fbHdr = if (openNote.isNotEmpty()) "X-Plenka-Fallback: " + asciiOnly(openNote) else null   /* 2.5: префлайт страницы увидит и залогирует */
                try {
                    serveAfd(out, req, afd, mimeFor(name, storedMime, kind == "v"), size, "pl-$kind-${vol ?: "p"}-$id", fbHdr)
                } finally {
                    try { afd.close() } catch (e: Exception) {}
                }
                return
            }''',
    '''            if (afd != null) {
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
            }''',
    'serveMedia: ovh put')

# ── K9: serveOvh ─────────────────────────────────────────────────────────────
rep('''        /** 2.5: HTTP-заголовки обязаны быть ASCII (кириллица в ISO-8859-1 превращается в мусор) */''',
    '''        /** 3.9: Range-раздача из ovh-кэша. Os.pread не двигает позицию fd и не закрывает
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
                        sb.append("HTTP/1.1 416 Range Not Satisfiable\\r\\n")
                            .append("Content-Range: bytes */").append(total).append("\\r\\n")
                            .append("Content-Length: 0\\r\\nConnection: close\\r\\n\\r\\n")
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

        /** 2.5: HTTP-заголовки обязаны быть ASCII (кириллица в ISO-8859-1 превращается в мусор) */''',
    'serveOvh')

io.open(SRC, 'w', encoding='utf-8').write(p)
print('OK →', SRC)

# ── K10: gradle versionCode/versionName ──────────────────────────────────────
g = io.open('/home/z/my-project/plenka-native/app/build.gradle.kts', encoding='utf-8').read()
assert g.count('versionCode = 110') == 1 and g.count('versionName = "3.8"') == 1, 'gradle anchors'
g = g.replace('versionCode = 110', 'versionCode = 120').replace('versionName = "3.8"', 'versionName = "3.9"')
io.open('/home/z/my-project/plenka-native/app/build.gradle.kts', 'w', encoding='utf-8').write(g)
print('ok: gradle 120 / 3.9')
