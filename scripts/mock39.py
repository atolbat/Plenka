#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Мок нативного сервера ПЛЁНКА 2.4 для смоук-теста v39 в headless-браузере.

Режимы (arg1):
  full     — мост жив (СТРОГИЙ: 0-арг методы ругаются на лишний аргумент — как
             после PiP-перехода на устройстве; v39 обязан звать ровной арностью),
             скан с файлами, /t/ миниатюры отдаются: полный флоу
  failscan — ПЕРВЫЕ ДВА вызова scan() бросают Java-исключение (реконструкция 2.2)
  permlost — hasPerm()=false до +5с, доставка права не приходит — опрос обязан засинкать
  empty    — скан ок, 0 items + skipN
  nobridge — мост не инжектируется (плашка «мост мёртв»)
Плюс в любом режиме:
  window.__mockPipBreak()  — ломает version() («Method not found»): страница
                             обязана заметить (natvRepair) и вылечить через rebridge()
  /t/<k>/<id>              — миниатюры: JPEG для видео, 404 для audio id=3
                             (проверка мягкого отката карточки на заглушку)
"""
import os, re, json, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
MEDIA = os.path.join(BASE, "nativemedia")
HTML = "/home/z/my-project/download/plenka-optimized-39.html"
PORT = 8977
MODE = sys.argv[1] if len(sys.argv) > 1 else "full"
T0 = time.time()

MEDIA_DB = {}
for i, fn in enumerate(sorted(os.listdir(MEDIA)), start=1):
    p = os.path.join(MEDIA, fn)
    kind = "a" if fn.endswith((".mp3", ".m4a", ".flac", ".wav", ".ogg")) else "v"
    st = os.stat(p)
    MEDIA_DB[f"{kind}:{i}"] = {
        "k": kind, "id": i, "n": fn, "m": "audio/mpeg" if kind == "a" else "video/mp4",
        "d": 8000 if kind == "v" else 12000, "w": 640 if kind == "v" else 0,
        "h": 360 if kind == "v" else 0, "s": st.st_size, "t": int(st.st_mtime),
        "path": p,
    }

PICKED_DB = {}
for seq, (fk, fn) in {101: ("v", "extra_clip.mp4"), 102: ("a", "extra_song.mp3")}.items():
    src = next(v for v in MEDIA_DB.values() if v["k"] == fk)
    PICKED_DB[seq] = {
        "seq": seq, "k": fk, "n": fn,
        "m": "video/mp4" if fk == "v" else "audio/mpeg",
        "d": 7333 if fk == "v" else 9500,
        "w": 854 if fk == "v" else 0, "h": 480 if fk == "v" else 0,
        "s": src["s"], "t": 1700000000,
    }

SRV_LOG = []          # реальные запросы — в stdout мока
THUMB_HITS = {"v": 0, "a": 0, "c": 0, "404": 0}

# 32×32 валидный JPEG (PIL) — карточке достаточно загрузиться
TINY_JPEG = open(os.path.join(BASE, "tiny_thumb.jpg"), "rb").read()


def scan_envelope():
    if MODE == "empty":
        return {"ok": True, "err": None, "n": 0, "items": [], "perm": "ok", "skipN": 5,
                "vols": {"external_primary": 0},
                "skipped": ["hawaii_trip.mkv", "game_record.ts", "old_cam.avi"]}
    items = [{k: v[k] for k in ("k", "id", "n", "m", "d", "w", "h", "s", "t")}
             for v in MEDIA_DB.values()]
    return {"ok": True, "err": None, "n": len(items), "items": items, "perm": "ok",
            "skipN": 0, "vols": {"external_primary": len(items)}, "skipped": []}


def picked_envelope():
    return [{"id": r["seq"], "k": r["k"], "n": r["n"], "m": r["m"], "d": r["d"],
             "w": r["w"], "h": r["h"], "s": r["s"], "t": r["t"]}
            for r in PICKED_DB.values()]


MOCK_BRIDGE = """
<script>
/* MOCK PlenkaNative — мост 2.4: СТРОГИЙ по арности (как после PiP на устройстве:
   0-арг методы, вызванные с лишним undefined, падают «Method not found») */
(function(){
  var SCAN=%SCAN%, PICKED=%PICKED%, MODE='%MODE%';
  var reported=[], nextSeq=100;
  var scanCalls=0, scanFailLeft=0, versionBroken=false, rebridged=0;
  var calls={scan:0,setPipAuto:0,keepScreenOn:0,mediaState:0};
  if(MODE==='failscan')scanFailLeft=2;
  var permFrom=5.0;
  function arity0(name, impl){         /* строгий диспетчер JavaBridge после PiP */
    return function(){
      if(arguments.length>0)throw new Error('Error invoking '+name+': Method not found');
      return impl();
    };
  }
  window.__mockReported=reported;
  window.__mockCalls=function(){return JSON.stringify(calls)};
  window.__mockScanCalls=function(){return scanCalls};
  window.__mockRebridgedCount=function(){return rebridged};
  window.__mockPipBreak=function(){ versionBroken=true; return 'broken' };   /* имитация PiP-поломки v38 */
  window.__mockMediaState=function(){ return window.__msData||null };
  window.PlenkaNative={
    scan:arity0('scan',function(){
      scanCalls++;
      if(scanFailLeft>0){ scanFailLeft--; throw new Error('JavaBridge NPE (мок)') }
      calls.scan++;
      return JSON.stringify(SCAN)
    }),
    hasPerm:arity0('hasPerm',function(){ return (MODE==='permlost')?((Date.now()-%T0JS%)>permFrom*1000):true }),
    requestPerm:arity0('requestPerm',function(){ return true }),
    permState:arity0('permState',function(){ return JSON.stringify({state:'ok',sdk:34}) }),
    pickedList:arity0('pickedList',function(){ return JSON.stringify(PICKED) }),
    pipExit:arity0('pipExit',function(){ try{console.log('[mock] pipExit')}catch(e){} }),
    isPip:arity0('isPip',function(){ return false }),
    exitApp:arity0('exitApp',function(){ try{console.log('[mock] exitApp')}catch(e){} }),
    version:arity0('version',function(){
      if(versionBroken)throw new Error('Error invoking version: Method not found');
      return 'PLENKA native 2.4 (v39, MOCK)'
    }),
    srvLog:arity0('srvLog',function(){
      return JSON.stringify(['GET /v/1 r=bytes=0- → 206 12КБ/45МБ 340мс',
        'GET /v/2 r=bytes=1048576- → 206 64КБ/1ГБ 22мс','t /v/3 → 200 15КБ 210мс'])
    }),
    rebridge:function(reason){ rebridged++; versionBroken=false;
      try{console.log('[mock] rebridge: '+reason)}catch(e){} return true },
    mediaState:function(json){ calls.mediaState++; try{window.__msData=JSON.parse(json)}catch(e){} },
    report:function(msg){ reported.push(''+msg); try{console.log('[mock report] '+msg)}catch(e){} },
    logFull:function(msg){ try{console.log('[mock logFull] '+(''+msg).substring(0,400))}catch(e){} },
    log:function(msg){ try{console.log('[J] '+msg)}catch(e){} },
    pick:function(){
      setTimeout(function(){
        var fresh=[{id:101,k:'v',n:'extra_clip.mp4',m:'video/mp4',d:7333,w:854,h:480,s:%EXTRA_SIZE%,t:1700000000},
                   {id:102,k:'a',n:'extra_song.mp3',m:'audio/mpeg',d:9500,w:0,h:0,s:%EXTRA_A_SIZE%,t:1700000001}];
        fresh.forEach(function(f){
          var hit=PICKED.filter(function(p){return p.id===f.id})[0];
          if(!hit)PICKED.push(f);
        });
        window.__plenkaPicked&&window.__plenkaPicked(JSON.stringify(fresh));
      },250);
      return true
    },
    unpick:function(seq){ try{console.log('[mock] unpick '+seq)}catch(e){} return true },
    pipEnter:function(a){ try{console.log('[mock] pipEnter '+a)}catch(e){} },
    setPipAuto:function(on){ calls.setPipAuto++ },
    keepScreenOn:function(on){ calls.keepScreenOn++ },
    immersive:function(on){},
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
            v0 = next(v for v in MEDIA_DB.values() if v["k"] == "v")
            a0 = next(v for v in MEDIA_DB.values() if v["k"] == "a")
            if MODE != "nobridge":
                bridge = (MOCK_BRIDGE
                          .replace("%SCAN%", json.dumps(scan_envelope()))
                          .replace("%PICKED%", json.dumps(picked_envelope()))
                          .replace("%MODE%", MODE)
                          .replace("%T0JS%", str(int(T0 * 1000)))
                          .replace("%EXTRA_SIZE%", str(v0["s"]))
                          .replace("%EXTRA_A_SIZE%", str(a0["s"])))
                html = html.replace("<head>", "<head>\n" + bridge, 1)
            body = html.encode()
            self._send_head(200, "text/html; charset=utf-8", len(body))
            if not head:
                self.wfile.write(body)
            return

        # 2.4: миниатюры /t/<k>/<id>[?r=]
        t = re.match(r"^/t/(v|a|c)/(\d+)$", path)
        if t:
            k, tid = t.group(1), int(t.group(2))
            ok = not (k == "a")          # аудио без арта → 404 → карточка падает на заглушку
            self._rec(f"t /{k}/{tid} → {'200' if ok else '404'}")
            THUMB_HITS[k if ok else "404"] = THUMB_HITS.get(k if ok else "404", 0) + 1
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
    print(f"mode={MODE} media db: {[v['n'] for v in MEDIA_DB.values()]}", flush=True)
    print(f"mock server 2.4 on http://127.0.0.1:{PORT}/", flush=True)
    TS(("", PORT), H).serve_forever()
