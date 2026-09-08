#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kotlin 2.5 → 3.5: роуты /seek и /list (лаборатория без моста), TTL негативного
кэша миниатюр, версии. Страница в ассете → v52."""
import io,sys

KT='/home/z/my-project/plenka-native/app/src/main/java/ru/plenka/app/MainActivity.kt'
src=io.open(KT,encoding='utf-8').read()

def rep(old,new,what):
    global src
    n=src.count(old)
    if n!=1:
        print('FAIL: %r найден %d раз'%(what,n)); sys.exit(1)
    src=src.replace(old,new)
    print('ok: %s'%what)

# 1) версии
rep('private const val APP_VERSION = "PLENKA native 2.5 (v40)"',
    'private const val APP_VERSION = "PLENKA native 3.5 (v52)"','APP_VERSION')
rep('Log.i(TAG, "native 2.4 started, version=$APP_VERSION sdk=${Build.VERSION.SDK_INT}")',
    'Log.i(TAG, "native 3.5 started, version=$APP_VERSION sdk=${Build.VERSION.SDK_INT}")','старт-лог')

# 2) кэш последнего скана для /list
rep('''    private val srvRing = ArrayDeque<String>()          /* 2.4: журнал HTTP-сервера — виден в ДИАГ; 2.5: 160 строк */''',
    '''    private val srvRing = ArrayDeque<String>()          /* 2.4: журнал HTTP-сервера — виден в ДИАГ; 2.5: 160 строк */
    @Volatile private var lastScanJson: String? = null /* 3.5: /list отдаёт последний скан — без пересканирования */''',
    'свойство lastScanJson')

rep('''        val sk = JSONArray()
        for (n in st.deadNames) sk.put(n)
        env.put("skipped", sk)
        return env.toString()''',
    '''        val sk = JSONArray()
        for (n in st.deadNames) sk.put(n)
        env.put("skipped", sk)
        val s = env.toString()
        lastScanJson = s                            /* 3.5: /list — из кэша, мгновенно */
        return s''',
    'кэширование скана')

# 3) роуты /seek и /list
rep('''        private fun serve(out: OutputStream, req: Request): Boolean {
            val path = req.path
            if (path == "/" || path == "/index.html" || path == "/plenka.html") {''',
    '''        private fun serve(out: OutputStream, req: Request): Boolean {
            val path = req.path
            if (path == "/seek" || path == "/seek/") {   /* 3.5: лаборатория перемотки — тот же ассет, страница сама видит путь */
                val html = htmlBytes()
                if (html == null) {
                    writeSimple(out, 500, "text/plain; charset=utf-8", "app asset missing")
                    return true
                }
                writeHead(out, 200, "text/html; charset=utf-8", html.size.toLong(), null, null)
                if (req.method == "GET") out.write(html)
                srvRec("GET /seek → 200 html ${html.size / 1024}КБ")
                return true
            }
            if (path == "/list") {                       /* 3.5: список медиа — лаборатории не нужен мост */
                serveList(out, req)
                return true
            }
            if (path == "/" || path == "/index.html" || path == "/plenka.html") {''',
    'роуты /seek + /list')

# 4) serveList/listJson — перед serveThumb
rep('''        private fun serveThumb(out: OutputStream, req: Request, kind: String, id: Long) {''',
    '''        /** 3.5: /list — JSON всех медиа (последний скан медиатеки + ручной выбор).
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
        private fun serveThumb(out: OutputStream, req: Request, kind: String, id: Long) {''',
    'serveList + listJson')

# 5) TTL негативного кэша миниатюр
rep('''    private val thumbDead = java.util.Collections.synchronizedSet(HashSet<String>())''',
    '''    /* 3.5: негативный кэш с TTL 40с — транзиентный сбой MMR (тяжёлый 4K-файл под
       нагрузкой) больше не хоронит обложку до конца сессии: «кадр показывается,
       через секунду заменяется заглушкой» */
    private val thumbDead = java.util.Collections.synchronizedMap(HashMap<String, Long>())''',
    'thumbDead → TTL-карта')

rep('''        val key = "$base/$rev"
        if (key in thumbDead) return null''',
    '''        val key = "$base/$rev"
        val deadAt = thumbDead[key]
        if (deadAt != null) {
            if (System.currentTimeMillis() - deadAt < 40_000) return null
            thumbDead.remove(key)                    /* TTL истёк — генерации дают ещё шанс */
        }''',
    'проверка thumbDead с TTL')

rep('''            if (b == null) thumbDead.add(key)   // сессия больше не пробует этот файл''',
    '''            if (b == null) thumbDead[key] = System.currentTimeMillis()   // 40с — и снова попробуем''',
    'запись в thumbDead')

io.open(KT,'w',encoding='utf-8').write(src)
print('OK →',KT)

# gradle: versionCode/Name
GR='/home/z/my-project/plenka-native/app/build.gradle.kts'
g=io.open(GR,encoding='utf-8').read()
assert g.count('versionCode = 24')==1 and g.count('versionName = "2.4"')==1
g=g.replace('versionCode = 24','versionCode = 50').replace('versionName = "2.4"','versionName = "3.5"')
io.open(GR,'w',encoding='utf-8').write(g)
print('OK →',GR,'(versionCode 50, versionName 3.5)')
