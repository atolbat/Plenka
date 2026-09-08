#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Мок сервера ПЛЁНКА 3.5: / и /seek → v52; /list; /v/<id> (Range); /t/ → 404."""
import http.server, socketserver, json, os, re, sys, threading

PORT=8977
ROOT='/home/z/my-project'
HTML=os.path.join(ROOT,'download','plenka-optimized-52.html')
FILES={
  'v/1000008396':(os.path.join(ROOT,'upload','sMXH5OPvSBCWBxJo.mp4'),'video/mp4'),
  'v/2':(os.path.join(ROOT,'scripts','mock52_long.mp4'),'video/mp4'),
  'v/1':(os.path.join(ROOT,'scripts','nativemedia','clip.mp4'),'video/mp4'),
}
LIST={"ok":True,"items":[
  {"k":"v","id":1000008396,"n":"sMXH5OPvSBCWBxJo.mp4","s":9144787,"d":4504,"w":2160,"h":3840},
  {"k":"v","id":2,"n":"mock52_long.mp4","s":0,"d":30000,"w":640,"h":360},
  {"k":"v","id":1,"n":"clip.mp4","s":134811,"d":5000,"w":0,"h":0},
]}

class H(http.server.BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,f,*a):
        sys.stderr.write('[mock] %s\n'%(f%a))
    def _send(self,code,ctype,body,extra=None,rng=None):
        self.send_response(code)
        self.send_header('Content-Type',ctype)
        if rng:
            self.send_header('Content-Range',rng)
        self.send_header('Accept-Ranges','bytes')
        if extra:
            for k,v in extra.items(): self.send_header(k,v)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Connection','close')
        self.end_headers()
        try:
            if self.command!='HEAD': self.wfile.write(body)
        except Exception: pass
        self.close_connection=True
    def do_HEAD(self): self.do_GET()
    def do_GET(self):
        path=self.path.split('?')[0]
        if path=='/' or path=='/index.html' or path=='/plenka.html':
            with open(HTML,'rb') as f: b=f.read()
            self._send(200,'text/html; charset=utf-8',b); return
        if path=='/seek' or path=='/seek/':
            with open(HTML,'rb') as f: b=f.read()
            self._send(200,'text/html; charset=utf-8',b); return
        if path=='/list':
            b=json.dumps(LIST).encode()
            self._send(200,'application/json; charset=utf-8',b,{'Cache-Control':'no-store'}); return
        if path.startswith('/t/'):
            self._send(404,'image/jpeg',b'no art'); return
        m=re.match(r'^/(v|a|c)/(\d+)$',path)
        if m:
            key=m.group(1)+'/'+m.group(2)
            if key not in FILES:
                self._send(404,'text/plain; charset=utf-8',b'not found',{'X-Plenka-Err':'no-such-file'}); return
            fp,mime=FILES[key]
            size=os.path.getsize(fp)
            rng=self.headers.get('Range')
            if rng:
                mm=re.match(r'bytes=(\d*)-(\d*)',rng)
                s=int(mm.group(1) or 0) if mm else 0
                e=int(mm.group(2)) if mm and mm.group(2) else size-1
                e=min(e,size-1)
                if s>size-1 or s>e:
                    self.send_response(416); self.send_header('Content-Range','bytes */%d'%size)
                    self.send_header('Connection','close'); self.end_headers(); self.close_connection=True; return
                with open(fp,'rb') as f:
                    f.seek(s); b=f.read(e-s+1)
                self._send(206,mime,b,rng='bytes %d-%d/%d'%(s,e,size)); return
            with open(fp,'rb') as f: b=f.read()
            self._send(200,mime,b); return
        self._send(404,'text/plain; charset=utf-8',b'not found')

class TS(socketserver.ThreadingTCPServer):
    allow_reuse_address=True
    daemon_threads=True

if __name__=='__main__':
    with TS(('127.0.0.1',PORT),H) as httpd:
        print('mock 3.5 on http://127.0.0.1:%d/ (and /seek, /list)'%PORT,flush=True)
        httpd.serve_forever()
