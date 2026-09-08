#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kotlin 3.7 → 3.8 (v54). Регрессы из репорта v53/3.7:
  1) «отсутствие обложек» — лестница первых кадров сдавалась на файлах, где MMR
     устройства не декодирует старт (4K): SYNC-фолбэки 0.4с/1с цеплялись за тот же
     битый первый GOP → 404 → карточка без обложки ВООБЩЕ. Лечение: дальняя лестница
     2/5/12с + системная миниатюра loadThumbnail — карточке нужен ЛЮБОЙ кадр,
     метка «дальний» (-1) → подложка остаётся чёрной (как просил пользователь);
     у аудио без встроенного арта — системный арт альбома (albumart/<albumId>);
  2) «длинное видео не работает / перемотка» — сервер мог отдать Range-ответ КОРОЧЕ
     обещанного Content-Length (FUSE/MediaProvider на гигантах): клиент висел на
     обещании вечно, без error-события. Лечение: обрыв читается честно, сокет рвётся
     RST (SO_LINGER 0) — Chromium перепрашивает диапазон сам; в журнале «ОБРЫВ»;
  3) «лаги» — PiP-циклы будят активность каждые 5-8с → каждый resume = полный скан
     MediaStore + мерж. Лечение: скан-конверт моложе 2с отдаётся из кэша (бут
     синкает дважды подряд), resume-push не чаще 6с;
  4) версии: 3.8 / v54, versionCode 110."""
import io, sys

KT = '/home/z/my-project/plenka-native/app/src/main/java/ru/plenka/app/MainActivity.kt'
src = io.open(KT, encoding='utf-8').read()

def rep(old, new, what):
    global src
    n = src.count(old)
    if n != 1:
        print('FAIL: %r найден %d раз' % (what, n)); sys.exit(1)
    src = src.replace(old, new)
    print('ok: %s' % what)

# ── 1) версии ───────────────────────────────────────────────────────────────
rep('private const val APP_VERSION = "PLENKA native 3.7 (v53)"',
    'private const val APP_VERSION = "PLENKA native 3.8 (v54)"', 'APP_VERSION')
rep('Log.i(TAG, "native 3.7 started, version=$APP_VERSION sdk=${Build.VERSION.SDK_INT}")',
    'Log.i(TAG, "native 3.8 started, version=$APP_VERSION sdk=${Build.VERSION.SDK_INT}")', 'старт-лог')

# ── 2) поля: метка кэша скана + троттл resume-push ──────────────────────────
rep('''    @Volatile private var lastScanJson: String? = null /* 3.5: /list отдаёт последний скан — без пересканирования */''',
    '''    @Volatile private var lastScanJson: String? = null /* 3.5: /list отдаёт последний скан — без пересканирования */
    @Volatile private var lastScanAt = 0L               /* 3.8: конверт моложе 2с — из кэша (бут синкает дважды) */
    @Volatile private var lastResumePush = 0L           /* 3.8: PiP-циклы дёргают onResume каждые 5-8с */''',
    'поля lastScanAt/lastResumePush')

# ── 3) скан-конверт из кэша ≤2с ─────────────────────────────────────────────
rep('''    private fun scanMediaJson(): String {
        val t0 = System.currentTimeMillis()''',
    '''    private fun scanMediaJson(): String {
        /* 3.8: бут синкает дважды (init + resume/вочдог) с интервалом в сотни мс —
           MediaStore гонять дважды незачем: свежий конверт отдаём из кэша */
        val c = lastScanJson
        if (c != null && System.currentTimeMillis() - lastScanAt < 2000) return c
        val t0 = System.currentTimeMillis()''',
    'скан: кэш 2с')

rep('''        val s = env.toString()
        lastScanJson = s                            /* 3.5: /list — из кэша, мгновенно */
        return s''',
    '''        val s = env.toString()
        lastScanJson = s                            /* 3.5: /list — из кэша, мгновенно */
        lastScanAt = System.currentTimeMillis()     /* 3.8: и сам скан кэшируется 2с */
        return s''',
    'скан: метка времени')

# ── 4) resume-push не чаще 6с ───────────────────────────────────────────────
rep('''        if (hasMediaPerm()) {
            webView.post {
                webView.evaluateJavascript("window.__plenkaResume?window.__plenkaResume():'нет'") { res ->
                    Log.i(TAG, "resume push → ${res?.take(40)}")
                }
            }
        }''',
    '''        if (hasMediaPerm()) {
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
        }''',
    'onResume: троттл 6с')

# ── 5) лестница первых кадров: дальний выход ────────────────────────────────
rep('''        for (us in syncUs) {
            val b = safeFrameOpt(mmr, us, MediaMetadataRetriever.OPTION_CLOSEST_SYNC)
            if (b != null) return Pair(b, if (us == 0L) 0L else -1L)  /* sync@0 — первый кейфрейм; 0.4/1с — дальний */
        }
        return Pair(null, -1L)
    }''',
    '''        for (us in syncUs) {
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
    }''',
    'лестница: дальние 2/5/12с')

# ── 6) generateThumb: системная миниатюра + арт альбома ─────────────────────
rep('''                val (ladderBmp, frameUs) = firstFrameLadder(mmr)
                val bmp0: Bitmap = ladderBmp ?: return ThumbRes(null, -1L)
                val tag = if (frameUs >= 0) "$frameUs" else "s"   /* s — синковый/дальний фолбэк */
                var bmp: Bitmap = bmp0''',
    '''                val lr = firstFrameLadder(mmr)
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
                var bmp: Bitmap = bFirst''',
    'generateThumb: loadThumbnail-фолбэк')

rep('''                if (isAudio) {
                    val pic = try { mmr.embeddedPicture } catch (e: Exception) { null }
                    if (pic != null && pic.size > 64) {
                        try { File(dir, "${base}_${rev}_n.jpg").writeBytes(pic) } catch (e: Exception) {}
                        return ThumbRes(pic, -2L)
                    }
                    return ThumbRes(null, -2L)
                }''',
    '''                if (isAudio) {
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
                }''',
    'generateThumb: арт альбума')

# ── 7) Request.rst + честный короткий Range-ответ ───────────────────────────
rep('''        private inner class Request(val method: String, val rawPath: String, val headers: Map<String, String>) {
            val path: String get() = rawPath.substringBefore('?')
            val range: String? get() = headers["range"]''',
    '''        private inner class Request(val method: String, val rawPath: String, val headers: Map<String, String>) {
            var rst = false   /* 3.8: ответ оборвался короче Content-Length — сокет рвём RST, клиент перепросит */
            val path: String get() = rawPath.substringBefore('?')
            val range: String? get() = headers["range"]''',
    'Request.rst')

rep('''        private fun serveSocket(sock: Socket) {
            try {
                sock.tcpNoDelay = true
                sock.soTimeout = 30000   /* 2.4: медленные Range-пробы гигантов не рвут соединение */
                val input = BufferedInputStream(sock.getInputStream(), 16384)
                val out = BufferedOutputStream(sock.getOutputStream(), 65536)
                while (alive.get()) {
                    val req = parseRequest(input) ?: break
                    val closeConn = serve(out, req)
                    out.flush()
                    if (closeConn) break
                }
            } catch (e: Exception) {
                // обрыв сокета — рабочая тишина
            } finally {
                try { sock.close() } catch (e: Exception) {}
            }
        }''',
    '''        private fun serveSocket(sock: Socket) {
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
        }''',
    'serveSocket: RST-финал')

rep('''            if (req.method == "GET" && len > 0) {
                val ch = FileInputStream(afd.fileDescriptor).channel
                try {
                    ch.position(afd.startOffset + start)      // lseek: дальний seek не читает гигабайты
                    var remaining = len
                    val buf = ByteArray(64 * 1024)
                    val bb = ByteBuffer.wrap(buf)
                    while (remaining > 0) {
                        bb.clear()
                        bb.limit(minOf(buf.size.toLong(), remaining).toInt())
                        val n = ch.read(bb)
                        if (n < 0) break
                        out.write(buf, 0, n)
                        remaining -= n
                    }
                } finally {
                    try { ch.close() } catch (e: Exception) {}
                }
            }
            srvRec("${req.method} /$etag r=${req.range ?: "-"} → ${if (partial) 206 else 200} " +
                "${len / 1024}КБ/${total / 1024}КБ ${System.currentTimeMillis() - t0}мс")''',
    '''            var written = 0L
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
                "${(if (req.method == "GET") written else len) / 1024}КБ/${total / 1024}КБ ${System.currentTimeMillis() - t0}мс")''',
    'serveAfd: честный обрыв + счётчик записанного')

io.open(KT, 'w', encoding='utf-8').write(src)
print('OK →', KT)

# gradle: versionCode/Name
GR = '/home/z/my-project/plenka-native/app/build.gradle.kts'
g = io.open(GR, encoding='utf-8').read()
assert g.count('versionCode = 100') == 1 and g.count('versionName = "3.7"') == 1, 'gradle якоря не найдены'
g = g.replace('versionCode = 100', 'versionCode = 110').replace('versionName = "3.7"', 'versionName = "3.8"')
io.open(GR, 'w', encoding='utf-8').write(g)
print('OK →', GR, '(versionCode 110, versionName 3.8)')
