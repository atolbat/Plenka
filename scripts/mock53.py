#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Мок сервера ПЛЁНКА 3.7: / и /seek → v53 + МОК-мост (строгая арность);
/t/v/1 → X-Plenka-FrameT:0 (первый кадр); /t/v/2 → 3600000 (дальний — кейс 4K);
/t/a/3 → арт без заголовка; /v/ /a/ с Range; /list."""
import http.server, socketserver, json, os, re, sys

PORT=8977
ROOT='/home/z/my-project'
HTML=os.path.join(ROOT,'download','plenka-optimized-53.html')
FILES={
  'v/1':(os.path.join(ROOT,'scripts','nativemedia','clip.mp4'),'video/mp4'),
  'v/2':(os.path.join(ROOT,'scripts','mock52_long.mp4'),'video/mp4'),
  'a/3':(os.path.join(ROOT,'scripts','nativemedia','song.mp3'),'audio/mpeg'),
}
TINY_JPEG=open(os.path.join(ROOT,'scripts','tiny_thumb.jpg'),'rb').read()
LIST={"ok":True,"items":[
  {"k":"v","id":1,"n":"firstframe.mp4","s":134811,"d":5000,"w":640,"h":360},
  {"k":"v","id":2,"n":"long30.mp4","s":2288160,"d":30000,"w":640,"h":360},
  {"k":"a","id":3,"n":"song.mp3","s":193140,"d":12000,"w":0,"h":0},
]}
SCAN={"ok":True,"err":None,"n":3,"items":LIST["items"],"perm":"ok","skipN":0,
      "vols":{"external_primary":3},"skipped":[]}

BRIDGE=r"""
<script>
/* MOCK PlenkaNative 3.7 — строгая арность (как после PiP на устройстве) */
(function(){
  var SCAN=%SCAN%;
  var pipCalls=[], ksoCalls=[], msData=null, reports=[];
  function arity0(name, impl){
    return function(){
      if(arguments.length>0)throw new Error('Error invoking '+name+': Method not found');
      return impl();
    };
  }
  window.__mockPipCalls=function(){return JSON.stringify(pipCalls)};
  window.__mockKsoCalls=function(){return JSON.stringify(ksoCalls)};
  window.__mockMediaState=function(){return JSON.stringify(msData||null)};
  window.__mockReported=function(){return JSON.stringify(reports)};
  window.PlenkaNative={
    scan:arity0('scan',function(){return JSON.stringify(SCAN)}),
    hasPerm:arity0('hasPerm',function(){return true}),
    requestPerm:arity0('requestPerm',function(){return true}),
    permState:arity0('permState',function(){return JSON.stringify({state:'ok',sdk:34})}),
    pickedList:arity0('pickedList',function(){return '[]'}),
    version:arity0('version',function(){return 'PLENKA native 3.7 (v53, MOCK)'}),
    isPip:arity0('isPip',function(){return false}),
    pipExit:arity0('pipExit',function(){return true}),
    exitApp:arity0('exitApp',function(){return true}),
    srvLog:arity0('srvLog',function(){return '[]'}),
    setPipAuto:function(on){pipCalls.push(!!on);return undefined},
    keepScreenOn:function(on){ksoCalls.push(!!on);return undefined},
    mediaState:function(json){try{msData=JSON.parse(json)}catch(e){}},
    rebridge:function(r){return true},
    report:function(m){reports.push(''+m)},
    logFull:function(m){},
    log:function(m){}
  };
})();
</script>
"""

def bridge_html():
    b=BRIDGE.replace('%SCAN%',json.dumps(SCAN))
    with open(HTML,encoding='utf-8') as f: h=f.read()
    return h.replace('<head>','<head>\n'+b,1).encode('utf-8')

PAGE=None

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
        global PAGE
        path=self.path.split('?')[0]
        if path=='/' or path=='/index.html' or path=='/plenka.html' or path=='/seek' or path=='/seek/':
            if PAGE is None: PAGE=bridge_html()
            self._send(200,'text/html; charset=utf-8',PAGE); return
        if path=='/list':
            b=json.dumps(LIST).encode()
            self._send(200,'application/json; charset=utf-8',b,{'Cache-Control':'no-store'}); return
        m=re.match(r'^/t/(v|a|c)/(\d+)$',path)
        if m:
            k,iid=m.group(1),m.group(2)
            extra={'ETag':'"th-%s-%s"'%(k,iid),'Cache-Control':'max-age=604800'}
            if k=='v' and iid=='1': extra['X-Plenka-FrameT']='0'          # первый кадр
            if k=='v' and iid=='2': extra['X-Plenka-FrameT']='3600000'    # дальний (кейс 4K)
            self._send(200,'image/jpeg',TINY_JPEG,extra); return
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
        print('mock 3.7 on http://127.0.0.1:%d/ (и /seek, /list)'%PORT,flush=True)
        httpd.serve_forever()
