#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Мок нативного сервера ПЛЁНКА 2.5 для смоук-теста v40 в headless-браузере.

Что проверяет v40 (поверх v39-флоу):
  * разделители дат в списке: mtimes размазаны по сегодня/вчера/неделя/месяц/старые месяцы
  * «фантомный» файл id=77: в скане есть, сервер отвечает 404 + X-Plenka-Err
    → префлайт обязан уронить открытие за миллисекунды (не 16с таймаутом),
      показать тост и убрать карточку пересканом
  * миниатюра /t/ для одного видео отдаётся со второй попытки (транзиентный 404)
    → ретрай с бэкоффом должен довести её до картинки

Режимы (arg1): full (по умолчанию) | nobridge
"""
import os, re, json, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
MEDIA = os.path.join(BASE, "nativemedia")
HTML = "/home/z/my-project/download/plenka-optimized-40.html"
PORT = 8977
MODE = sys.argv[1] if len(sys.argv) > 1 else "full"
T0 = time.time()
NOW = int(time.time())
DAY = 86400

# осознанные даты «сохранения»: сегодня / вчера / 3 дня / 12 дней / 47 дней / 400 дней
DATES = [NOW - 60, NOW - DAY - 3600, NOW - 3 * DAY, NOW - 12 * DAY, NOW - 47 * DAY, NOW - 400 * DAY]
# жёсткая раскладка по файлам (в dir их всего 3): clip=сегодня, reel=вчера, song=3 дня
FORCED_DATES = {"clip.mp4": NOW - 60, "reel.mp4": NOW - DAY - 3600, "song.mp3": NOW - 3 * DAY}

MEDIA_DB = {}
for i, fn in enumerate(sorted(os.listdir(MEDIA)), start=1):
    p = os.path.join(MEDIA, fn)
    kind = "a" if fn.endswith((".mp3", ".m4a", ".flac", ".wav", ".ogg")) else "v"
    st = os.stat(p)
    MEDIA_DB[f"{kind}:{i}"] = {
        "k": kind, "id": i, "n": fn, "m": "audio/mpeg" if kind == "a" else "video/mp4",
        "d": 8000 if kind == "v" else 12000, "w": 640 if kind == "v" else 0,
        "h": 360 if kind == "v" else 0, "s": st.st_size,
        "t": FORCED_DATES.get(fn, DATES[(i - 1) % len(DATES)]),
        "path": p,
    }

# фантом: в MediaStore числится (скан его видит), но открыть нельзя — 803МБ гигант
GHOST = {"k": "v", "id": 77, "n": "ssstwitter.com_1788657235999.mp4", "m": "video/mp4",
         "d": 3600000, "w": 1920, "h": 1080, "s": 803000000, "t": NOW - 30}

# миниатюра, которая сперва падает (генерация не успела), потом отдаётся
FLAKY_THUMB = {"v:2": 0}

SRV_LOG = []
THUMB_HITS = {}

# 32×32 валидный JPEG — карточке достаточно загрузиться
TINY_JPEG = open(os.path.join(BASE, "tiny_thumb.jpg"), "rb").read()


def scan_envelope():
    items = [{k: v[k] for k in ("k", "id", "n", "m", "d", "w", "h", "s", "t")}
             for v in MEDIA_DB.values()]
    items.append(dict(GHOST))
    return {"ok": True, "err": None, "n": len(items), "items": items, "perm": "ok",
            "skipN": 0, "vols": {"external_primary": len(items)}, "skipped": []}


PICKED_DB = {}
for seq, (fk, fn) in {101: ("v", "extra_clip.mp4"), 102: ("a", "extra_song.mp3")}.items():
    src = next(v for v in MEDIA_DB.values() if v["k"] == fk)
    PICKED_DB[seq] = {
        "seq": seq, "k": fk, "n": fn,
        "m": "video/mp4" if fk == "v" else "audio/mpeg",
        "d": 7333 if fk == "v" else 9500,
        "w": 854 if fk == "v" else 0, "h": 480 if fk == "v" else 0,
        "s": src["s"], "t": NOW - 12 * DAY if seq == 101 else NOW - 47 * DAY,
    }


def picked_envelope():
    return [{"id": r["seq"], "k": r["k"], "n": r["n"], "m": r["m"], "d": r["d"],
             "w": r["w"], "h": r["h"], "s": r["s"], "t": r["t"]}
            for r in PICKED_DB.values()]


MOCK_BRIDGE = """
<script>
/* MOCK PlenkaNative — мост 2.5 */
(function(){
  var SCAN=%SCAN%, PICKED=%PICKED%, MODE='%MODE%';
  var reported=[], rebridged=0, scanCalls=0, versionBroken=false;
  var calls={scan:0,setPipAuto:0,keepScreenOn:0,mediaState:0};
  window.__mockReported=reported;
  window.__mockCalls=function(){return JSON.stringify(calls)};
  window.__mockScanCalls=function(){return scanCalls};
  window.__mockPipBreak=function(){ versionBroken=true; return 'broken' };
  window.PlenkaNative={
    scan:function(){ scanCalls++; calls.scan++; return JSON.stringify(SCAN) },
    hasPerm:function(){ return true },
    requestPerm:function(){ return true },
    permState:function(){ return JSON.stringify({state:'ok',sdk:34}) },
    pickedList:function(){ return JSON.stringify(PICKED) },
    pipExit:function(){},
    isPip:function(){ return false },
    exitApp:function(){},
    version:function(){ if(versionBroken)throw new Error('Error invoking version: Method not found');
      return 'PLENKA native 2.5 (v40, MOCK)' },
    srvLog:function(){ return JSON.stringify(%SRVLOG%) },
    rebridge:function(reason){ rebridged++; versionBroken=false; return true },
    mediaState:function(json){ calls.mediaState++ },
    report:function(msg){ reported.push(''+msg); try{console.log('[mock report] '+msg)}catch(e){} },
    logFull:function(msg){},
    log:function(msg){},
    pick:function(){ return true },
    unpick:function(seq){ return true },
    pipEnter:function(a){},
    setPipAuto:function(on){ calls.setPipAuto++ },
    keepScreenOn:function(on){ calls.keepScreenOn++ },
    immersive:function(on){}
  };
})();
</script>
"""


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    log_message = lambda self, *a: None

    def _rec(self, line):
        SRV_LOG.append(line)
        print(f"[srv] {line}", flush=True)

    def _send_head(self, status, ctype, clen, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        if clen is not None:
            self.send_header("Content-Length", str(clen))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Connection", "close")
        self.end_headers()

    def do_HEAD(self):
        self._route(head=True)

    def do_GET(self):
        self._route(head=False)

    def _route(self, head):
        path = urlparse(self.path).path
        if path in ("/", "/index.html", "/plenka.html"):
            html = open(HTML, encoding="utf-8").read()
            if MODE != "nobridge":
                bridge = (MOCK_BRIDGE
                          .replace("%SCAN%", json.dumps(scan_envelope()))
                          .replace("%PICKED%", json.dumps(picked_envelope()))
                          .replace("%MODE%", MODE)
                          .replace("%SRVLOG%", json.dumps(SRV_LOG[-12:])))
                html = html.replace("<head>", "<head>\n" + bridge, 1)
            body = html.encode()
            self._send_head(200, "text/html; charset=utf-8", len(body))
            if not head:
                self.wfile.write(body)
            return

        # /t/<k>/<id>[?r=]
        t = re.match(r"^/t/(v|a|c)/(\d+)$", path)
        if t:
            k, tid = t.group(1), t.group(2)
            ok = k == "v"                     # аудио без арта → 404 → заглушка
            if k == "v":
                key = f"v:{tid}"
                if key in FLAKY_THUMB and FLAKY_THUMB[key] < 1:
                    FLAKY_THUMB[key] += 1     # первая попытка — «генерация не успела»
                    self._rec(f"t /{k}/{tid} → 404 pending")
                    self._send_head(404, "image/jpeg", 6, {"Cache-Control": "no-cache"})
                    if not head:
                        self.wfile.write(b"no art")
                    return
                ok = key in MEDIA_DB and key != "v:77"   # фантом — без превью
            self._rec(f"t /{k}/{tid} → {'200' if ok else '404'}")
            THUMB_HITS.setdefault(f"{k}:{tid}:{'ok' if ok else '404'}", 0)
            THUMB_HITS[f"{k}:{tid}:{'ok' if ok else '404'}"] += 1
            if ok:
                self._send_head(200, "image/jpeg", len(TINY_JPEG),
                                {"ETag": '"mock-thumb"', "Cache-Control": "max-age=604800"})
                if not head:
                    self.wfile.write(TINY_JPEG)
            else:
                self._send_head(404, "image/jpeg", 6, {"Cache-Control": "no-cache"})
                if not head:
                    self.wfile.write(b"no art")
            return

        m = re.match(r"^/(v|a)/(\d+)$", path)
        if m:
            key = f"{m.group(1)}:{m.group(2)}"
            if key == "v:77":                 # фантом 2.5: gone с причиной (как устройство)
                why = "afd:FileNotFoundException pfd:FileNotFoundException path:file-missing | FileNotFoundException: open failed: ENOENT (No such file or directory)"
                self._rec(f"GET /{key} → 404 gone ({why})")
                self._send_head(404, "text/plain; charset=utf-8", 5,
                                {"X-Plenka-Err": why, "Cache-Control": "no-store"})
                if not head:
                    self.wfile.write(b"gone\n")
                return
            rec = MEDIA_DB.get(key)
            if not rec:
                self._rec(f"GET /{key} → 404 gone")
                self._send_head(404, "text/plain; charset=utf-8", 5)
                if not head:
                    self.wfile.write(b"gone\n")
                return
            rng = self.headers.get("Range") or "-"
            self._rec(f"GET /{key} r={rng}")
            self._serve_range(rec["path"], rec, head, etag=f'pl-{rec["k"]}-{rec["id"]}-{rec["s"]}')
            return

        c = re.match(r"^/c/(\d+)$", path)
        if c:
            seq = int(c.group(1))
            v0 = next(v for v in MEDIA_DB.values() if v["k"] == "v")
            a0 = next(v for v in MEDIA_DB.values() if v["k"] == "a")
            rec = v0 if seq == 101 else a0 if seq == 102 else None
            if not rec:
                self._send_head(404, "text/plain; charset=utf-8", 5)
                if not head:
                    self.wfile.write(b"gone\n")
                return
            self._serve_range(rec["path"], rec, head, etag=f"pl-c-{seq}")
            return

        self._send_head(404, "text/plain; charset=utf-8", 9)
        if not head:
            self.wfile.write(b"not found")

    def _serve_range(self, fpath, rec, head, etag):
        total = rec["s"]
        rng = self.headers.get("Range")
        start, end, partial = 0, total - 1, False
        if rng:
            mm = re.match(r"bytes=(\d*)-(\d*)", rng.strip())
            if mm:
                a, b = mm.group(1), mm.group(2)
                if a == "" and b:
                    n = min(int(b), total)
                    start = total - n
                elif a:
                    start = int(a)
                    if b:
                        end = min(int(b), total - 1)
                if start >= total:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{total}")
                    self.send_header("Content-Length", "0")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    return
                if start > end:
                    end = total - 1
                partial = True
        clen = end - start + 1
        extra = {}
        if partial:
            extra["Content-Range"] = f"bytes {start}-{end}/{total}"
        extra["ETag"] = f'"{etag}"'
        extra["Accept-Ranges"] = "bytes"
        self._send_head(206 if partial else 200, rec["m"], clen, extra)
        if head:
            return
        with open(fpath, "rb") as f:
            f.seek(start)
            remaining = clen
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)


class TS(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    print(f"mode={MODE} media: {[(v['n'], v['t'] - NOW) for v in MEDIA_DB.values()]}", flush=True)
    print(f"ghost id=77 (803MB, 404 + X-Plenka-Err)", flush=True)
    print(f"mock server 2.5 on http://127.0.0.1:{PORT}/", flush=True)
    TS(("", PORT), H).serve_forever()
