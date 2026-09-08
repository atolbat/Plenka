#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v59 → v60 (dev-эксперимент): рендер ВИДЕО через WebGL/Canvas.

Слой #vgl — canvas поверх <video> (декодер остаётся прежним: события,
MSE-мост, PiP, сторожа rVFC, двойной буфер, зум-транспорт — не тронуты):
  WebGL (текстура+шейдер) → 2D canvas → родной <video>.
  Компоновка contain — в шейдере/рисовании; зум — копией inline-transform.
  Шейдер: плёночная градация+виньетка, ВЫКЛ по умолчанию (plenka.vglfx=1).
  Слой: ?vgl=off|2d|webgl, localStorage plenka.vgl=off.
  Гаснет в MIRROR/мини/аудио; ДИАГ: «рендер видео (эксперимент)».

Патчи (все якоря уникальные):
  P1 html: <canvas id="vgl"> после #videoB
  P2 css : правила #vgl (z3, pointer-events:none, smooth)
  P3 js  : модуль VGL после блока двойного буфера (якорь «33.3: гасим и звук»)
  P4 ver : ДИАГ 'страница v59' → 'страница v60 (dev: WebGL)'
  P5 diag: строка «рендер видео» в probe() (читает window.__vgl)
  P6 readme: раздел про дев-эксперимент
"""
import re, subprocess, sys

SRC = '/home/z/my-project/download/plenka-optimized-59.html'
DST = '/home/z/my-project/download/plenka-optimized-60.html'
README = '/home/z/my-project/download/README.md'

src = open(SRC, encoding='utf-8').read()
orig_len = len(src)


def patch(name, anchor, repl, count=1):
    global src
    n = src.count(anchor)
    assert n == count, 'ЯКОРЬ %s: найден %d раз (ожидался %d)' % (name, n, count)
    src = src.replace(anchor, repl, count)
    print('  [%s] ok' % name)


# ── P1: canvas в сцену ────────────────────────────────────────────────
A1 = '''    <video id="videoB" playsinline webkit-playsinline preload="auto" aria-hidden="true" tabindex="-1"></video>
'''
R1 = A1 + '''    <canvas id="vgl" aria-hidden="true"></canvas><!-- 60: презентация кадра WebGL/2D (дев-эксперимент) -->
'''
patch('P1 canvas', A1, R1)

# ── P2: CSS слоя ──────────────────────────────────────────────────────
A2 = '#videoB{z-index:1}\n'
R2 = A2 + '''#vgl{position:absolute;inset:0;width:100%;height:100%;z-index:3;pointer-events:none;display:none}   /* 60: кадр активного <video>, нарисованный в канвас; до первого кадра и в фолбэках — видео видно само, как всегда */
#vgl.smooth{transition:transform .28s cubic-bezier(.2,.8,.2,1)}   /* 60: тот же профиль, что у #video.smooth — зум едет синхронно */
'''
patch('P2 css', A2, R2)

# ── P3: модуль рендера ───────────────────────────────────────────────
A3 = '''eachV(function(el){ el.addEventListener('play',function(e){
  if(e.target!==vActive&&!e.target.muted){ try{ e.target.pause(); e.target.muted=true }catch(err){} }   /* 33.3: гасим и звук на будущее */
}) });
'''
MODULE = r'''
/* ═══ 60 (dev-эксперимент): рендер кадра через WebGL/Canvas ═══
   <video> остаётся декодером и хозяином событий (MSE-мост, PiP, сторожа
   rVFC, двойной буфер, зум-транспорт — не задеты); презентацию берёт
   слой #vgl: каждый кадр активного элемента рисуется в canvas ПОВЕРХ
   видео (WebGL-текстура+шейдер; нет WebGL — 2D; нет ни того — видео
   напрямую, как всегда). Компоновка contain — в шейдере/рисовании,
   зум-транспорт — копией inline-transform и класса smooth. Шейдер умеет
   плёночную градацию с виньеткой, по умолчанию ВЫКЛ — включить:
   localStorage plenka.vglfx='1'. Выключить слой: localStorage
   plenka.vgl='off' или ?vgl=off; принудить 2D: ?vgl=2d. Слой гаснет
   в MIRROR/мини/аудио (страницу ведёт старая машина). ДИАГ: строка
   «рендер видео (эксперимент)». */
(function(){
var vglCvs=$('#vgl');
var VGL=window.__vgl={mode:'off',drawn:0,fps:0,fw:0,fh:0,fx:0,sched:'-'};
if(!vglCvs)return;
var QMD='';try{QMD=(location.search.match(/[?&]vgl=(webgl|2d|off)\b/)||[])[1]||''}catch(e){}
try{
  var kill=(QMD==='off')||((localStorage.getItem('plenka.vgl')||'')==='off'&&QMD!=='webgl'&&QMD!=='2d');
  if(kill){VGL.mode='выключен (vgl=off)';return}
}catch(e){}
try{if((localStorage.getItem('plenka.vglfx')||'')==='1')VGL.fx=1}catch(e){}
var gl=null,ctx2=null,tex=null,prog=null,loc={};
var inter=null;                        /* промежуточный canvas: гиганты >1920px режем до аплоада текстуры */
var running=false,dirty=true,frameOk=false,uploadFails=0;
var lastDrawn=0,lastFpsT=0;

var VS='attribute vec2 a_pos;uniform vec4 u_rect;uniform vec2 u_cvs;varying vec2 v_uv;void main(){vec2 p=u_rect.xy+a_pos*u_rect.zw;vec2 c=p/u_cvs*2.0-1.0;gl_Position=vec4(c.x,-c.y,0.0,1.0);v_uv=a_pos;}';
var FS='precision mediump float;varying vec2 v_uv;uniform sampler2D u_tex;uniform float u_fx;uniform vec2 u_res;void main(){vec3 c=texture2D(u_tex,v_uv).rgb;if(u_fx>0.5){c=c*c*(3.0-2.0*c)*0.94+0.017;c+=vec3(0.013,0.004,-0.010);vec2 q=gl_FragCoord.xy/u_res-0.5;c*=clamp(1.0-dot(q,q)*0.62,0.0,1.0);}gl_FragColor=vec4(c,1.0);}';

function sh(t,src){var s=gl.createShader(t);gl.shaderSource(s,src);gl.compileShader(s);
 if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error('шейдер: '+(gl.getShaderInfoLog(s)||'?'));return s}

function glInit(){
  var o={alpha:true,antialias:false,depth:false,stencil:false,preserveDrawingBuffer:true};
  gl=vglCvs.getContext('webgl',o)||vglCvs.getContext('experimental-webgl',o);
  if(!gl)return false;
  prog=gl.createProgram();
  gl.attachShader(prog,sh(gl.VERTEX_SHADER,VS));
  gl.attachShader(prog,sh(gl.FRAGMENT_SHADER,FS));
  gl.linkProgram(prog);
  if(!gl.getProgramParameter(prog,gl.LINK_STATUS))throw new Error('линк: '+(gl.getProgramInfoLog(prog)||'?'));
  gl.useProgram(prog);
  gl.bindBuffer(gl.ARRAY_BUFFER,gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([0,0, 1,0, 0,1, 1,0, 1,1, 0,1]),gl.STATIC_DRAW);
  var ap=gl.getAttribLocation(prog,'a_pos');
  gl.enableVertexAttribArray(ap);
  gl.vertexAttribPointer(ap,2,gl.FLOAT,false,0,0);
  tex=gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D,tex);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
  loc.rect=gl.getUniformLocation(prog,'u_rect');
  loc.cvs=gl.getUniformLocation(prog,'u_cvs');
  loc.res=gl.getUniformLocation(prog,'u_res');
  loc.fx=gl.getUniformLocation(prog,'u_fx');
  return true;
}

try{
  if(QMD==='2d'){
    ctx2=vglCvs.getContext('2d');
    VGL.mode=ctx2?'2D (принудительно, ?vgl=2d)':'нет (2D недоступен)';
  }else{
    var probe=document.createElement('canvas');
    var pg=probe.getContext('webgl')||probe.getContext('experimental-webgl');
    if(pg){try{var lc=pg.getExtension('WEBGL_lose_context');if(lc)lc.loseContext()}catch(e2){}}
    if(pg){
      if(glInit())VGL.mode='WebGL';
      else VGL.mode='нет (WebGL контекст не создан)';
    }else{
      ctx2=vglCvs.getContext('2d');
      VGL.mode=ctx2?'2D (WebGL нет)':'нет (обоих нет)';
    }
  }
}catch(e){
  VGL.mode='ошибка: '+e.message;
  try{if(!ctx2){ctx2=vglCvs.getContext('2d');if(ctx2)VGL.mode='2D (WebGL сбой: '+e.message+')'}}catch(e3){}
}
if(!((gl&&prog)||ctx2)){VGL.mode+=' — слой выключен';return}

function frameSource(el){
  var w=el.videoWidth,h=el.videoHeight;
  if(w>1920){
    if(!inter){inter=document.createElement('canvas');inter._ctx=inter.getContext('2d')}
    var ih=Math.max(2,Math.round(h*1920/w));
    if(inter.width!==1920||inter.height!==ih){inter.width=1920;inter.height=ih}
    inter._ctx.drawImage(el,0,0,1920,ih);
    return {src:inter,w:1920,h:ih};
  }
  return {src:el,w:w,h:h};
}

function fitCanvas(){
  var dpr=Math.min(window.devicePixelRatio||1,2);
  var cw=Math.max(2,Math.round(vglCvs.clientWidth*dpr));
  var ch=Math.max(2,Math.round(vglCvs.clientHeight*dpr));
  if(vglCvs.width!==cw||vglCvs.height!==ch){
    vglCvs.width=cw;vglCvs.height=ch;
    if(gl&&prog)gl.viewport(0,0,cw,ch);
    return true;
  }
  return false;
}

function draw(el){
  try{
    var f=frameSource(el);
    var cw=vglCvs.width,ch=vglCvs.height;
    var s=Math.min(cw/f.w,ch/f.h);
    var rw=Math.max(2,Math.round(f.w*s)),rh=Math.max(2,Math.round(f.h*s));
    var rx=Math.round((cw-rw)/2),ry=Math.round((ch-rh)/2);
    if(gl&&prog){
      gl.viewport(0,0,cw,ch);
      gl.clearColor(0,0,0,0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D,tex);
      gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,f.src);
      gl.uniform4f(loc.rect,rx,ry,rw,rh);
      gl.uniform2f(loc.cvs,cw,ch);
      gl.uniform2f(loc.res,cw,ch);
      gl.uniform1f(loc.fx,VGL.fx?1:0);
      gl.drawArrays(gl.TRIANGLES,0,6);
    }else if(ctx2){
      ctx2.setTransform(1,0,0,1,0,0);
      ctx2.clearRect(0,0,cw,ch);
      try{ctx2.imageSmoothingQuality='high'}catch(e){}
      ctx2.drawImage(f.src,rx,ry,rw,rh);
    }else return false;
    VGL.drawn++;VGL.fw=f.w;VGL.fh=f.h;
    uploadFails=0;frameOk=true;
    return true;
  }catch(e){
    if(++uploadFails>40){VGL.mode+=' · слой погашен ('+e.message+')';gl=null;prog=null;ctx2=null}
    return false;
  }
}

function stageOk(){
  var el=video;
  if(el!==videoA&&el!==videoB)return false;          /* элемент не из сцены (уехал в мини) */
  if(el.parentNode!==stage)return false;
  if(typeof MIRROR!=='undefined'&&MIRROR&&MIRROR.on)return false;   /* зеркалом страницу ведёт своя машина */
  if(typeof curIsAudio==='function'&&curIsAudio())return false;     /* аудио: сцена — обложка, не кадр */
  return true;
}

function tick(){
  if(!running)return;
  var el=video;
  var active=stageOk()&&el.style.visibility!=='hidden';
  var disp=active?'block':'none';   /* block: CSS-база #vgl{display:none} — пустая строка её НЕ перебивает */
  if(vglCvs._d!==disp){vglCvs._d=disp;try{vglCvs.style.display=disp}catch(e){}}
  if(active){
    try{
      var tr=el.style.transform||'';
      if(vglCvs._tr!==tr){vglCvs._tr=tr;vglCvs.style.transform=tr}
      var sm=el.classList.contains('smooth');
      if(vglCvs._sm!==sm){vglCvs._sm=sm;vglCvs.classList.toggle('smooth',sm)}
    }catch(e){}
    var resz=fitCanvas();
    var need=(!el.paused&&!el.ended)||dirty||resz;
    if(need&&el.readyState>=2&&el.videoWidth>0){
      if(draw(el))dirty=false;
    }
  }else{
    frameOk=false;
  }
  var now=performance.now();
  if(now-lastFpsT>=1000){VGL.fps=Math.round((VGL.drawn-lastDrawn)*1000/(now-lastFpsT));lastDrawn=VGL.drawn;lastFpsT=now}
  if(player.hidden){                                  /* плеер закрыт: редкий опрос, петля спит */
    running=false;VGL.sched='парк';
    setTimeout(function(){ if(!running)start() },500);
  }else{
    VGL.sched='rAF';
    requestAnimationFrame(tick);                      /* скрытая вкладка: rAF сам замирает и сам просыпается */
  }
}
function start(){
  if(running)return;
  running=true;dirty=true;
  requestAnimationFrame(tick);
}

eachV(function(el){
  el.addEventListener('emptied',function(){          /* новый src: слой чист до первого кадра НОВОГО ролика — семантика прозрачного постера 31.2 */
    if(el!==video)return;
    frameOk=false;dirty=false;
    try{
      if(gl&&prog){gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT)}
      else if(ctx2)ctx2.clearRect(0,0,vglCvs.width,vglCvs.height);
    }catch(e){}
  });
});
['play','seeked','canplay','loadedmetadata','resize'].forEach(function(ev){ VOn(ev,function(){ dirty=true;start() }) });
window.addEventListener('resize',function(){dirty=true;start()},{passive:true});
document.addEventListener('fullscreenchange',function(){dirty=true;start()});
document.addEventListener('visibilitychange',function(){ if(!document.hidden){dirty=true;start()} });
VGL.start=start;                                     /* тесты/ДИАГ могут поднять петлю рукой */
})();
'''
R3 = A3 + MODULE
patch('P3 модуль VGL', A3, R3)

# ── P4: версия ───────────────────────────────────────────────────────
A4 = "  s('версия','страница v59 / оболочка 3.13');"
R4 = "  s('версия','страница v60 (dev: WebGL-рендер) / оболочка 3.13');"
patch('P4 версия', A4, R4)

# ── P5: строка рендера в ДИАГ ────────────────────────────────────────
A5 = "  s('главный скрипт',men!==undefined?('жив, оценился за '+men+'мс'):(mst!==undefined?('УМЕР после старта, '+mst+'мс'):'НЕ ЗАПУСТИЛСЯ (parse?)'));"
R5 = A5 + '''
  try{ if(window.__vgl){ var G=window.__vgl;                     /* 60 (dev): рендер видео WebGL/2D */
    s('рендер видео (эксперимент)',G.mode+' · кадров '+G.drawn+' · '+G.fps+'к/с'+((G.fw||G.fh)?(' · источник '+G.fw+'×'+G.fh):'')+' · '+G.sched+(G.fx?' · плёнка ВКЛ':'')) } }catch(e){}
'''
patch('P5 ДИАГ', A5, R5)

open(DST, 'w', encoding='utf-8').write(src)
print('OK: %s (%d -> %d байт, +%d)' % (DST, orig_len, len(src), len(src) - orig_len))

# ── P6: README ───────────────────────────────────────────────────────
rd = open(README, encoding='utf-8').read()
A6 = '## Актуальная сборка'
R6 = '''## dev-ветка: эксперимент WebGL (v60)

`plenka-optimized-60.html` — рендер **видео** через WebGL/Canvas (эксперимент):
`<video>` остаётся декодером (MSE-мост, PiP, фоновое воспроизведение, сторожа —
как были), презентацию кадра берёт canvas-слой `#vgl`: WebGL-текстура + шейдер,
фолбэк на 2D-канвас, затем на родной `<video>`. Плёночная градация с виньеткой —
`localStorage plenka.vglfx='1'` (по умолчанию выкл). Выключить слой:
`localStorage plenka.vgl='off'` или `?vgl=off`; принудительный 2D — `?vgl=2d`.
Состояние — в ДИАГ, строка «рендер видео (эксперимент)». В APK пока не собирается.

## Актуальная сборка'''
if rd.count(A6) == 1:
    open(README, 'w', encoding='utf-8').write(rd.replace(A6, R6, 1))
    print('  [P6 readme] ok')
else:
    print('  [P6 readme] ПРОПУЩЕН (якорь не найден: %d)' % rd.count(A6))

# ── синтаксис обоих <script> ─────────────────────────────────────────
ok = True
scripts = re.findall(r'<script\b[^>]*>(.*?)</script>', src, re.S | re.I)
for i, s in enumerate(scripts):
    if not s.strip():
        continue
    p = '/home/z/my-project/scripts/_v60_s%d.js' % i
    with open(p, 'w', encoding='utf-8') as f:
        f.write(s)
    r = subprocess.run(['node', '--check', p], capture_output=True, text=True)
    print('script #%d: %s' % (i, 'OK' if r.returncode == 0 else 'FAIL'))
    if r.returncode:
        print(r.stderr[:2000])
        ok = False
sys.exit(0 if ok else 1)
