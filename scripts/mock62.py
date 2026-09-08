#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Мок сервера ПЛЁНКА 3.15 (v62): / → v62, /seek → стенд v51, /lab → лаба v51,
/__medialist, /__srvlog; /t/v/1 → X-Plenka-FrameT:0, /t/v/2 → 3600000.
61: /t/a/4 → 404 — аудио без встроенного арта (тест битого плейсхолдера).
Мост-мок 3.13: журнал mediaState/setPipAuto, __mockBgSet(true/false) —
эмуляция document.hidden + visibilitychange. Сервер живёт между
перезагрузками страницы — тесты реестра проверяют «перезаход»."""
import http.server, socketserver, json, os, re, sys, threading, time

PORT = 8977
ROOT = '/home/z/my-project'
HTML = os.path.join(ROOT, 'download', 'plenka-optimized-62.html')
SEEK = os.path.join(ROOT, 'scripts', 'from_chat_plenka-seek-v51.html')
LAB = os.path.join(ROOT, 'scripts', 'from_chat_plenka-lab-v51.html')
FILES = {
    'v/1': (os.path.join(ROOT, 'scripts', 'fmp4_60.mp4'), 'video/mp4'),
    'v/2': (os.path.join(ROOT, 'scripts', 'mock52_long.mp4'), 'video/mp4'),
    'a/3': (os.path.join(ROOT, 'scripts', 'nativemedia', 'song.mp3'), 'audio/mpeg'),
    'a/4': (os.path.join(ROOT, 'scripts', 'nativemedia', 'song.mp3'), 'audio/mpeg'),   # 61: тот же файл, но без арта
}
TINY_JPEG = open(os.path.join(ROOT, 'scripts', 'tiny_thumb.jpg'), 'rb').read()
LIST = {"ok": True, "items": [
    {"k": "v", "id": 1, "n": "fmp460.mp4", "s": 2487646, "d": 60000, "w": 640, "h": 360},
    {"k": "v", "id": 2, "n": "long30.mp4", "s": 2288160, "d": 30000, "w": 640, "h": 360},
    {"k": "a", "id": 3, "n": "song.mp3", "s": 193140, "d": 12000, "w": 0, "h": 0},
    {"k": "a", "id": 4, "n": "noart.mp3", "s": 193140, "d": 12000, "w": 0, "h": 0},   # 61: без обложки
]}
SCAN = {"ok": True, "err": None, "n": 4, "items": LIST["items"], "perm": "ok", "skipN": 0,
        "vols": {"external_primary": 4}, "skipped": []}
SRVLOG = []


def rec(line):
    SRVLOG.append(line)
    if len(SRVLOG) > 60:
        del SRVLOG[:10]


BRIDGE = r"""
<script>
/* MOCK PlenkaNative 3.13 — строгая арность; журнал mediaState/setPipAuto;
   __mockBgSet — подмена document.hidden с событием visibilitychange */
(function(){
  var SCAN=%SCAN%;
  var pipCalls=[], ksoCalls=[], msCalls=[], reports=[], logs=[];
  function arity0(name, impl){
    return function(){
      if(arguments.length>0)throw new Error('Error invoking '+name+': Method not found');
      return impl();
    };
  }
  window.__mockPipCalls=function(){return JSON.stringify(pipCalls)};
  window.__mockKsoCalls=function(){return JSON.stringify(ksoCalls)};
  window.__mockMediaState=function(){return JSON.stringify(msCalls[msCalls.length-1]||null)};
  window.__mockMediaCalls=function(){return JSON.stringify(msCalls)};
  window.__mockReported=function(){return JSON.stringify(reports)};
  window.__mockLog=function(){return logs.join('\n')};
  window.__mockBgSet=function(h){
    try{
      Object.defineProperty(document,'hidden',{configurable:true,get:function(){return !!h}});
      Object.defineProperty(document,'visibilityState',{configurable:true,get:function(){return h?'hidden':'visible'}});
      document.dispatchEvent(new Event('visibilitychange'));
      return 'ok:'+document.hidden;
    }catch(e){ return 'ERR:'+e.message }
  };
  window.PlenkaNative={
    scan:arity0('scan',function(){return JSON.stringify(SCAN)}),
    hasPerm:arity0('hasPerm',function(){return true}),
    requestPerm:arity0('requestPerm',function(){return true}),
    permState:arity0('permState',function(){return JSON.stringify({state:'ok',sdk:34})}),
    pickedList:arity0('pickedList',function(){return '[]'}),
    version:arity0('version',function(){return 'PLENKA native 3.15 (v62, MOCK)'}),
    isPip:arity0('isPip',function(){return false}),
    pipExit:arity0('pipExit',function(){return true}),
    exitApp:arity0('exitApp',function(){return true}),
    srvLog:arity0('srvLog',function(){return '[]'}),
    setPipAuto:function(on){pipCalls.push(!!on);return undefined},
    keepScreenOn:function(on){ksoCalls.push(!!on);return undefined},
    mediaState:function(json){
      try{ var o=JSON.parse(json); msCalls.push({t:Date.now(),playing:!!o.playing,title:o.title||'',pos:o.pos||0}); }
      catch(e){}
    },
    rebridge:function(r){return true},
    report:function(m){reports.push(''+m)},
    logFull:function(m){},
    log:function(m){logs.push(''+m)}
  };
})();
</script>
"""


def bridge_html(path_html):
    b = BRIDGE.replace('%SCAN%', json.dumps(SCAN))
    with open(path_html, encoding='utf-8') as f:
        h = f.read()
    return h.replace('<head>', '<head>\n' + b, 1).encode('utf-8')


PAGE = None
SEEKPAGE = None
LABPAGE = None


class H(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, f, *a):
        sys.stderr.write('ock] %s\n' % (f % a))

    def _send(self, code, ctype, body, extra=None, rng=None):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        if rng:
            self.send_header('Content-Range', rng)
        self.send_header('Accept-Ranges', 'bytes')
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.end_headers()
        try:
            if self.command != 'HEAD':
                self.wfile.write(body)
        except Exception:
            pass
        self.close_connection = True

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        global PAGE, SEEKPAGE, LABPAGE
        path = self.path.split('?')[0]
        if path == '/' or path == '/index.html' or path == '/plenka.html':
            if PAGE is None:
                PAGE = bridge_html(HTML)
            self._send(200, 'text/html; charset=utf-8', PAGE)
            return
        if path == '/seek' or path == '/seek/':
            if SEEKPAGE is None:
                SEEKPAGE = bridge_html(SEEK)
            rec('GET /seek → 200 html')
            self._send(200, 'text/html; charset=utf-8', SEEKPAGE)
            return
        if path == '/lab' or path == '/lab/':
            if LABPAGE is None:
                LABPAGE = bridge_html(LAB)
            rec('GET /lab → 200 html')
            self._send(200, 'text/html; charset=utf-8', LABPAGE)
            return
        if path == '/__medialist':
            b = json.dumps(LIST).encode()
            rec('GET /__medialist → 200')
            self._send(200, 'application/json; charset=utf-8', b, {'Cache-Control': 'no-store'})
            return
        if path == '/__srvlog':
            b = json.dumps({"streams": SRVLOG}).encode()
            self._send(200, 'application/json; charset=utf-8', b, {'Cache-Control': 'no-store'})
            return
        if path == '/list':
            b = json.dumps(LIST).encode()
            self._send(200, 'application/json; charset=utf-8', b, {'Cache-Control': 'no-store'})
            return
        m = re.match(r'^/t/(v|a|c)/(\d+)$', path)
        if m:
            k, iid = m.group(1), m.group(2)
            if k == 'a' and iid == '4':      # 61: аудио без встроенного арта — честный 404
                rec('t /%s/%s → 404 (нет арта)' % (k, iid))
                self._send(404, 'text/plain; charset=utf-8', b'no art', {'X-Plenka-Err': 'no-art'})
                return
            extra = {'ETag': '"th-%s-%s"' % (k, iid), 'Cache-Control': 'max-age=604800'}
            if k == 'v' and iid == '1':
                extra['X-Plenka-FrameT'] = '0'
            if k == 'v' and iid == '2':
                extra['X-Plenka-FrameT'] = '3600000'
            rec('t /%s/%s → 200' % (k, iid))
            self._send(200, 'image/jpeg', TINY_JPEG, extra)
            return
        m = re.match(r'^/(v|a|c)/(\d+)$', path)
        if m:
            key = m.group(1) + '/' + m.group(2)
            if key not in FILES:
                self._send(404, 'text/plain; charset=utf-8', b'not found', {'X-Plenka-Err': 'no-such-file'})
                return
            fp, mime = FILES[key]
            size = os.path.getsize(fp)
            rng = self.headers.get('Range')
            if rng:
                mm = re.match(r'bytes=(\d*)-(\d*)', rng)
                s = int(mm.group(1) or 0) if mm else 0
                e = int(mm.group(2)) if mm and mm.group(2) else size - 1
                e = min(e, size - 1)
                if s > size - 1 or s > e:
                    self.send_response(416)
                    self.send_header('Content-Range', 'bytes */%d' % size)
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    self.close_connection = True
                    return
                rec('GET /%s r=%s → 206' % (key, rng))
                with open(fp, 'rb') as f:
                    f.seek(s)
                    b = f.read(e - s + 1)
                self._send(206, mime, b, extra=None, rng='bytes %d-%d/%d' % (s, e, size))
                return
            rec('GET /%s r=- → 200' % key)
            with open(fp, 'rb') as f:
                b = f.read()
            self._send(200, mime, b)
            return
        self._send(404, 'text/plain; charset=utf-8', b'not found')


class TS(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == '__main__':
    with TS(('127.0.0.1', PORT), H) as httpd:
        print('mock 3.15 on http://127.0.0.1:%d/ (v62)' % PORT, flush=True)
        httpd.serve_forever()
