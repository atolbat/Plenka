#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v40 → v52: нативный поток (MSE-мост не восстанавливаем — v52 играется как file://),
старт-гейт play, хвостовые отсрочки в ended, sticky-обложка, лаборатория /seek (стенд 2)."""
import sys, io, os

SRC='/home/z/my-project/download/plenka-optimized-40.html'
DST='/home/z/my-project/download/plenka-optimized-52.html'
LABJS='/home/z/my-project/scripts/lab52.js'

html=io.open(SRC,encoding='utf-8').read()
lab=io.open(LABJS,encoding='utf-8').read()
assert 'var __LAB=false' in lab

def rep(old,new,what,cnt=1):
    global html
    n=html.count(old)
    if n!=cnt:
        print('FAIL: якорь %r найден %d раз (ожидалось %d)'%(what,n,cnt)); sys.exit(1)
    html=html.replace(old,new)
    print('ok: %s'%what)

# ── P1: версия ──────────────────────────────────────────────────────────────
rep("s('версия','страница v40 / оболочка 2.5');",
    "s('версия','страница v52 / оболочка 3.5');",'версия')

# ── P2: старт-гейт (заикание ~200мс в начале) ───────────────────────────────
GATE='''
function gateStart(my){
  /* 52: старт-гейт — играем с запасом данных. Жалоба: «в начале видно, как играет
     несколько мс, потом пауза ~200мс, потом играет» = старт по HAVE_CURRENT_DATA
     (1 кадр) с пустым буфером вперёд. Локальный сервер даёт данные почти мгновенно,
     поэтому ожидание HAVE_FUTURE_DATA стоит десятки мс; кап 900мс — гиганты и
     медленные файлы стартуют как раньше (постер/маски прикрывают ожидание) */
  return new Promise(function(res){
    var t0=performance.now();
    (function chk(){
      if(my!=null&&my!==playToken)return res();          /* открытие перебито */
      if(!video.paused||video.readyState>=3||video.error||video.ended||(!video.src&&!video.currentSrc))return res();
      if(performance.now()-t0>900)return res();
      setTimeout(chk,45);
    })();
  });
}
function play(){ if(!video.src)return;'''
rep("\nfunction play(){ if(!video.src)return;",GATE,'gateStart перед play()')

OLD_PLAY='''  if(opts.autoplay!==false){
    playIntent='ctl';
    var wasPl=video.paused;      /* muted-прогрев мог уже играть: перехода paused→playing нет, события 'play' не будет */
    play();
    if(!wasPl&&!video.paused)playFx();
  }'''
NEW_PLAY='''  if(opts.autoplay!==false){
    playIntent='ctl';
    var wasPl=video.paused;      /* muted-прогрев мог уже играть: перехода paused→playing нет, события 'play' не будет */
    gateStart(my).then(function(){                /* 52: старт только с запасом данных — без заикания */
      if(my!==playToken)return;                   /* перебито следующим открытием — оно само стартует */
      play();
      if(!wasPl&&!video.paused)playFx();
    });
  }'''
rep(OLD_PLAY,NEW_PLAY,'гейт в openItem')

# ── P3: ended — ничего тяжёлого в момент последнего кадра ───────────────────
OLD_END='''  playIntent='auto';                              /* перезапуск цикла не продлевает таймер UI */
  PERF._endedT=performance.now();               /* метка для бенчмарка склейки */
  savePos(0); ab={a:null,b:null}; updAB();
  updStateBadge();'''
NEW_END='''  playIntent='auto';                              /* перезапуск цикла не продлевает таймер UI */
  PERF._endedT=performance.now();               /* метка для бенчмарка склейки */
  /* 52: хвостовое «дёргание» — запись позиции (IDB) и пересборку полос убираем
     из обработчика ended: последний кадр сначала отрисовывается, работа — следом */
  setTimeout(function(){ if(playIntent!=='auto')return; savePos(0); ab={a:null,b:null}; updAB(); },320);
  updStateBadge();'''
rep(OLD_END,NEW_END,'ended: отсрочка тяжёлой работы')

OLD_CARD='''  $('#endCard').classList.add('show');
  bumpCtl();
});'''
NEW_CARD='''  requestAnimationFrame(function(){ $('#endCard').classList.add('show'); bumpCtl(); });   /* 52: DOM — после отрисовки финального кадра */
});'''
rep(OLD_CARD,NEW_CARD,'ended: endCard через rAF')

# ── P4: обложка — sticky-кадр + фолбэк на fframe вместо заглушки ───────────
OLD_TH='''        ig3.loading='lazy';
        ig3.setAttribute('data-audio',it3.audio?'1':'0');
        ig3.onerror=function(){
          var su=(''+this.getAttribute('src')||'');
          if(su.indexOf('/t/')>0&&((+this.dataset.rt)||0)<2){   /* ретрай: 800мс / 2.6с */
            this.dataset.rt=String((+this.dataset.rt||0)+1);
            var self=this,dly=((+this.dataset.rt)===1)?800:2600;
            setTimeout(function(){ try{ self.src=su }catch(e){} },dly);
            return;
          }
          this.onerror=null;
          try{ this.outerHTML=(this.getAttribute('data-audio')==='1')?PH_MUSIC:PH_SVG }
          catch(e){ this.style.visibility='hidden' } };
        ig3.src=thumbUrl(it3);'''
NEW_TH='''        ig3.loading='lazy';
        ig3.setAttribute('data-audio',it3.audio?'1':'0');
        ig3.onload=function(){ this.dataset.ok='1' };   /* 52: кадр однажды показан — в этой
           сессии НИКОГДА не меняем его на заглушку (жалоба: «кадр показывается, через
           ~секунду заменяется заглушка» — ререндер + сбой /t/ больше не оголяет карточку) */
        ig3.onerror=function(){
          var su=(''+this.getAttribute('src')||'');
          if(this.dataset.ok==='1')return;               /* 52: успешная загрузка уже была — не трогаем */
          if(su.indexOf('/t/')>0&&((+this.dataset.rt)||0)<2){   /* ретрай: 800мс / 2.6с */
            this.dataset.rt=String((+this.dataset.rt||0)+1);
            var self=this,dly=((+this.dataset.rt)===1)?800:2600;
            setTimeout(function(){ try{ self.src=su }catch(e){} },dly);
            return;
          }
          this.onerror=null;
          /* 52: серверный кадр не дал себя — последний шанс: РЕАЛЬНЫЙ кадр из
             fframe/fthumb (снимок постера), и только потом абстрактная заглушка */
          var fb=(it3.fframe||it3.fthumb||'');
          if(fb&&(''+fb).indexOf('data:')===0){
            try{ this.onload=function(){ this.dataset.ok='1' }; this.src=fb; return; }catch(e){}
          }
          try{ this.outerHTML=(this.getAttribute('data-audio')==='1')?PH_MUSIC:PH_SVG }
          catch(e){ this.style.visibility='hidden' } };
        ig3.src=thumbUrl(it3);'''
rep(OLD_TH,NEW_TH,'обложка: sticky + фолбэк')

# ── P5: лаборатория /seek ───────────────────────────────────────────────────
REP_ANCHOR='/* ═══ запуск ═══ */'
rep(REP_ANCHOR,lab+'\n'+REP_ANCHOR,'вставка модуля лаборатории')

OLD_INIT='''(async function init(){
  if(!window.showDirectoryPicker)$('#btnPickFolder').hidden=true;'''
NEW_INIT='''(async function init(){
  if(__LAB){ try{ __plenkaLabBoot(); }catch(e){ try{ document.body.textContent='lab crash: '+(e&&e.message||e) }catch(e2){} } return; }   /* 52: /seek — режим лаборатории, приложение не поднимаем */
  if(!window.showDirectoryPicker)$('#btnPickFolder').hidden=true;'''
rep(OLD_INIT,NEW_INIT,'guard лаборатории в init')

io.open(DST,'w',encoding='utf-8').write(html)
print('размер: %d байт (v40 был %d)'%(len(html.encode('utf-8')),os.path.getsize(SRC)))
print('OK →',DST)
