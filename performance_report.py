"""Performance report for every player in a demo, one page, one tab per player.

One metric: impact. Good plays count positive, mistakes negative; each player's headline is average impact per round.
Cards are drawn as a shared radar background plus a small inline SVG overlay, so a ten-player page stays small.

Usage:
    python performance_report.py <demo.dem> [--player 76561198063294402] [--out report.html]
"""
from __future__ import annotations
from typing import Any
from report_types import Card, Demo, Proj, Rules, XY
import sys, os, re, argparse, html, json, time, math, pickle, tempfile, collections as C
import concurrent.futures as CF
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')    # player names can contain any Unicode; the pipe to the app is UTF-8
    except Exception: pass
import mistake_report as MR
import impact_report as IR
from mistake_report import parse, make_map, b64, for_player, nade_flight

_T0 = time.time(); _EXPECTED = None
TIMINGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'timings.json')


def progress(pct: float, msg: str) -> None:
    """Print a machine-readable progress line: PROGRESS <pct> <elapsed_s> <eta_s> <message>."""
    el = time.time() - _T0
    prop = el / pct * (100 - pct) if pct > 0 else 0
    eta = max(_EXPECTED - el, prop if pct >= 40 else 0) if _EXPECTED else prop
    print(f"PROGRESS {int(pct)} {el:.0f} {max(0, eta):.0f} {msg}", flush=True)


def expected_seconds(rounds: int, mb: float) -> float:
    """Estimate total build time from previous runs (seconds per round), falling back to a rule of thumb."""
    try:
        hist = json.load(open(TIMINGS))
        rates = [h['seconds'] / max(h['rounds'], 1) for h in hist[-8:]]
        return sum(rates) / len(rates) * rounds
    except Exception:
        return 1.6 * rounds + 0.03 * mb


def remember_timing(rounds: int, mb: float, seconds: float) -> None:
    try:
        hist = json.load(open(TIMINGS)) if os.path.exists(TIMINGS) else []
    except Exception:
        hist = []
    hist.append(dict(rounds=rounds, mb=round(mb), seconds=round(seconds, 1)))
    json.dump(hist[-30:], open(TIMINGS, 'w'))

CSS = """
body{font-family:Segoe UI,Arial,sans-serif;background:#111318;color:#e6e6e6;margin:0;padding:24px;max-width:1500px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:20px;margin:40px 0 10px;padding-bottom:6px;border-bottom:2px solid #333}
h3{font-size:17px;margin:28px 0 8px;border-bottom:1px solid #2a2e3a;padding-bottom:5px;scroll-margin-top:12px}
html{scroll-behavior:smooth}small{color:#999}
.teams{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:16px 0}
.team{background:#171a22;border:1px solid #2a2e3a;border-radius:10px;padding:12px 14px}
.team .th{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px}
.team .th b{font-size:18px}.team .th .rw{font-size:26px;font-weight:700}
.tabs{display:flex;flex-wrap:wrap;gap:8px}
.tab{background:#1d2130;border:1px solid #333;border-radius:8px;padding:8px 12px;min-width:120px;cursor:pointer;text-align:left}
.tab:hover{border-color:#666;background:#232838}.tab.on{border-color:#e6e6e6;background:#262b3a}
.tab .nm{font-weight:700;display:block}.tab .ai{font-size:18px;font-weight:700}.tab small{display:block}
.player[hidden]{display:none}
.score{display:grid;grid-template-columns:1.2fr 1fr 1fr;gap:16px;margin:18px 0}
.box{background:#171a22;border:1px solid #2a2e3a;border-radius:10px;padding:14px 16px}
.box .big{font-size:34px;font-weight:700}.box .mid{font-size:26px;font-weight:700}
.summary{font-size:15px;line-height:1.6;background:#171a22;border:1px solid #2a2e3a;border-radius:10px;padding:14px 18px;margin:16px 0 4px}
.strip{display:flex;flex-wrap:wrap;gap:4px;margin:10px 0 4px}
.rd{width:50px;background:#1d2130;border:1px solid #333;border-radius:6px;padding:4px 0;text-align:center;font-size:11px}
.rd .n{font-weight:700;font-size:12px}.rd .w{color:#8fd18f}.rd .l{color:#ff7a7a}.rd .net{font-weight:700;font-size:11px}
.rd .dots{display:flex;justify-content:center;gap:2px;margin-top:3px;min-height:8px}.dot{width:7px;height:7px;border-radius:50%}
.sum{display:flex;flex-wrap:wrap;gap:10px;margin:12px 0}.chip{background:#1d2130;border:1px solid #333;border-radius:8px;padding:8px 12px;min-width:150px;color:inherit;text-decoration:none;cursor:pointer}
.chip:hover{border-color:#666;background:#232838}.chip b{font-size:20px;display:block}.chip .v{font-weight:700}.chip.on{border-color:#8fa3d8;background:#232838}
.chipl{display:none;flex-basis:100%;width:100%;background:#171a22;border:1px solid #2a2e3a;border-radius:10px;padding:10px 14px;margin:0 0 4px}.chipl.on{display:block}
.chipl .lh{font-size:13px;color:#9aa0ad;margin-bottom:6px}.chipl .li{display:block;color:inherit;text-decoration:none;background:#1a1d26;border-radius:6px;padding:6px 10px;margin:4px 0;font-size:13px}
.chipl .li:hover{background:#232838}.chipl .li .badge{padding:1px 7px;margin:0 4px 0 0;font-size:12px}.chipl .sn{color:#aab0bd;font-size:12px}
.why{background:#1a1d26;padding:10px 14px;margin:6px 0 14px;font-size:14px}
.card{display:grid;grid-template-columns:560px 1fr;gap:18px;background:#171a22;border:1px solid #2a2e3a;border-radius:10px;padding:14px;margin:12px 0}
.map{width:560px;height:560px;border-radius:6px;background-color:#111318;background-size:100% 100%;position:relative}
.map svg{position:absolute;inset:0;width:100%;height:100%}
.mapw{width:560px}.ctl{display:flex;gap:8px;align-items:center;margin-top:6px;font-size:12px;color:#9aa0ad}
.ctl input[type=range]{flex:1;accent-color:#7a86a8}.ctl .tl{min-width:52px;text-align:right;font-variant-numeric:tabular-nums;color:#cfd3dc}
.ctl button,.ctl select{background:#2a2e3a;color:#dfe3ea;border:0;border-radius:4px;padding:3px 9px;cursor:pointer;font-size:12px}.ctl button{min-width:34px}
.rlk{font-size:11px;color:#6f7482;margin-top:3px}
.viewsel{margin:12px 0 16px}.showsel span.sv{border-left-color:#8fa3d8}#playersview .showsel{margin:0 0 16px}
.rsel{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0}.rb{background:#1d2130;border:1px solid #333;border-radius:6px;color:#dfe3ea;padding:5px 9px;cursor:pointer;font-size:13px;text-align:left}
.rb small{display:block;color:#9aa0ad;font-size:10px}.rb.on{background:#2a3044;border-color:#8fa3d8}.rb:hover{background:#232838}
.kf{font-size:13px;padding:3px 0;border-bottom:1px solid #22262f}.kf .kt{color:#9aa0ad;display:inline-block;min-width:52px;font-variant-numeric:tabular-nums}
.showsel{display:flex;gap:10px;margin:12px 0 0}.showsel label{cursor:pointer}.showsel input{display:none}
.showsel span{display:block;background:#1d2130;border:1px solid #333;border-left:6px solid #555;border-radius:8px;padding:8px 14px;min-width:150px;color:#cfd3dc}
.showsel span b{display:block;font-size:14px}.showsel span small{color:#9aa0ad}.showsel span:hover{border-color:#666;background:#232838}
.showsel span.sp{border-left-color:#3c8c4c}.showsel span.sm{border-left-color:#8c3c3c}
.showsel input:checked+span{background:#2a3044;border-color:#8fa3d8;color:#fff}.showsel input:checked+span small{color:#cfd3dc}
body.show-p .side-m,body.show-m .side-p{display:none !important}body.show-p .card.nosides,body.show-m .card.nosides{display:none}
.jb{background:#2a2e3a;color:#dfe3ea;border:0;border-radius:4px;padding:1px 7px;margin-left:6px;cursor:pointer;font-size:11px}.jb:hover{background:#3a4052}
.facts{font-size:14px;line-height:1.5}.k{font-weight:600}
.badge{display:inline-block;color:#fff;font-weight:700;padding:4px 10px;border-radius:6px;margin-bottom:6px}
.br{font-size:12px;color:#aaa;margin-bottom:10px}.lost{color:#ff7a7a}.won{color:#8fd18f}
.two{display:grid;grid-template-columns:1fr 1fr;gap:24px}ol{margin:6px 0 0 18px;padding:0}li{margin:3px 0}
.flag{background:#1a1d26;border-radius:6px;padding:8px 12px;margin:8px 0}.flag .facts{margin-top:4px}.mh{font-size:15px;margin-bottom:6px}a.g{color:#9aa0ad;font-size:12px;margin-left:8px}.card{scroll-margin-top:12px}.why{scroll-margin-top:12px}
"""

JS = """
function showPlayer(id){
  document.querySelectorAll('.player').forEach(e=>e.hidden=true);
  document.querySelectorAll('.tab').forEach(e=>e.classList.remove('on'));
  var p=document.getElementById(id); if(!p) return; p.hidden=false;
  var t=document.getElementById('tab-'+id); if(t) t.classList.add('on');
  if(location.hash.replace('#','')!==id && !document.getElementById(location.hash.replace('#','')) ) history.replaceState(null,'','#'+id);
  window.scrollTo(0,0);
}
function goHash(){
  var h=location.hash.replace('#',''); if(!h) return;
  var el=document.getElementById(h); if(!el) return;
  var pl=el.closest('.player'); if(pl && pl.hidden){ if(pl.id==='rounds') setView('rounds'); else { var pv=document.getElementById('playersview'); if(pv && pv.hidden) setView('players'); showPlayer(pl.id); } }
  el.scrollIntoView({behavior:'smooth',block:'start'});
}
window.addEventListener('hashchange', goHash);
function showRound(n){
  document.querySelectorAll('.roundv').forEach(function(e){ e.hidden=true; }); document.querySelectorAll('.rb').forEach(function(e){ e.classList.remove('on'); });
  var v=document.getElementById('round-'+n); if(!v) return; v.hidden=false; var b=document.getElementById('rb-'+n); if(b) b.classList.add('on');
  var map=v.querySelector('.map');
  if(map && !map._rp){ try{ rpGet(map); }catch(e){ console.error('round '+n+' replay failed', e); } }
  else if(map && map._rp){ rpDraw(map._rp); }
}
function ensureRound(){
  // a round must be visible whenever the Rounds view is: if none is (the view was opened before the page finished loading, or
  // the selection was lost), open the first
  var cur=document.querySelector('.roundv:not([hidden])');
  if(!cur){ var f=document.querySelector('.rb'); if(f) showRound(parseInt(f.id.replace('rb-',''))); return; }
  var map=cur.querySelector('.map'); if(map && !map._rp){ try{ rpGet(map); }catch(e){ console.error('round replay failed', e); } }
}
var _lastPlayer=null;
function setView(v){
  var pv=document.getElementById('playersview'); var r=document.querySelector("input[name='view'][value='"+v+"']"); if(r) r.checked=true;
  if(v==='rounds'){ if(pv) pv.hidden=true; showPlayer('rounds'); ensureRound(); }
  else { if(pv) pv.hidden=false; var first=document.querySelector('.player:not(#rounds)'); showPlayer(_lastPlayer || (first ? first.id : null)); }
  try{ localStorage.setItem('cs2report-view', v); }catch(e){}
}
function setShow(v){
  document.body.classList.remove('show-p','show-m'); if(v==='p'||v==='m') document.body.classList.add('show-'+v);
  document.querySelectorAll('.card').forEach(function(c){ var s=c.getAttribute('data-sides')||''; c.classList.toggle('nosides', (v==='p'||v==='m') && s.indexOf(v)<0); });
  try{ localStorage.setItem('cs2report-show', v); }catch(e){}
  var r=document.querySelector("input[name='show'][value='"+v+"']"); if(r) r.checked=true;
}
function toggleList(id, chip){
  var el=document.getElementById(id); if(!el) return false;
  var open=!el.classList.contains('on');
  var pl=el.closest('.player'); if(pl){ pl.querySelectorAll('.chipl.on').forEach(function(x){ x.classList.remove('on'); }); pl.querySelectorAll('.chip.on').forEach(function(x){ x.classList.remove('on'); }); }
  if(open){ el.classList.add('on'); if(chip) chip.classList.add('on'); el.scrollIntoView({behavior:'smooth',block:'nearest'}); }
  return false;
}
var NS='http://www.w3.org/2000/svg';
function rpEl(n,a){var e=document.createElementNS(NS,n);for(var k in a)e.setAttribute(k,a[k]);return e}
function rpGet(node){
  var w=node.closest('.mapw'),map=w.querySelector('.map'); if(map._rp) return map._rp;
  var d=JSON.parse(map.dataset.rp),svg=map.querySelector('svg'),st=svg.querySelector('g.st'),layer=rpEl('g',{'class':'rl'}); svg.appendChild(layer);
  var NC={flashbang:'#faf078',smokegrenade:'#c8c8c8',hegrenade:'#f08c3c',molotov:'#ff5a1e',decoy:'#a0a0a0'};
  var gl=(d.g||[]).map(function(n){var col=NC[n.w]||'#c8c8c8',g=rpEl('g',{});var tr=rpEl('polyline',{fill:'none',stroke:col,'stroke-width':1.5,'stroke-opacity':'0.7','stroke-dasharray':'3,3'});var mk=rpEl('circle',{r:4,fill:col,stroke:'#000','stroke-width':0.5});g.appendChild(tr);g.appendChild(mk);layer.appendChild(g);return {n:n,g:g,tr:tr,mk:mk}});
  var fxg=rpEl('g',{'class':'fxg'}); layer.insertBefore(fxg, layer.firstChild);
  var shg=rpEl('g',{'class':'shg'}); layer.appendChild(shg);
  var pl=d.p.map(function(p){
    var col=p.me?d.mc:(p.m?'#508cff':'#ffaa3c'), g=rpEl('g',{});
    var ar=rpEl('polygon',{fill:col,'fill-opacity':'0.95'});
    var mk=rpEl('circle',{r:p.me?8:5,fill:col,stroke:p.me?'#fff':'none','stroke-width':2});
    var tx=rpEl('text',{fill:col,'font-size':p.me?13:11,'font-weight':p.me?'bold':'normal'}); tx.textContent=p.n;
    var xx=rpEl('path',{stroke:col,'stroke-width':p.me?4:3,fill:'none'}); xx.style.display='none';
    var fr=rpEl('circle',{r:(p.me?8:5)+4,fill:'none',stroke:'#ffffff','stroke-width':2.5}); fr.style.display='none';
    if(p.d){ var L=p.me?8:6,dx=p.d[1],dy=p.d[2]; xx.setAttribute('d','M'+(dx-L)+','+(dy-L)+' L'+(dx+L)+','+(dy+L)+' M'+(dx-L)+','+(dy+L)+' L'+(dx+L)+','+(dy-L)); }
    g.appendChild(ar); g.appendChild(mk); g.appendChild(fr); g.appendChild(tx); g.appendChild(xx); layer.appendChild(g);
    return {p:p,g:g,ar:ar,mk:mk,tx:tx,xx:xx,fr:fr};
  });
  map._rp={d:d,st:st,layer:layer,shg:shg,fxg:fxg,gl:gl,pl:pl,t:Math.min(Math.max(0,d.t0),d.end),playing:false,started:false,raf:0,last:0,sc:w.querySelector('.sc'),tl:w.querySelector('.tl'),pb:w.querySelector('.pb'),sp:w.querySelector('.sp')};
  rpDraw(map._rp); return map._rp;
}
function rpPos(s,t){
  if(!s.length||t<s[0][0]-0.3||t>s[s.length-1][0]+0.4) return null;   // samples are 0.25 s apart: hold the last one to the end of the window
  if(t<=s[0][0]) return s[0];
  var lo=0,hi=s.length-1; while(hi-lo>1){var m=(lo+hi)>>1; if(s[m][0]<=t) lo=m; else hi=m;}
  var a=s[lo],b=s[hi]; if(t>=b[0]) return b;
  var f=(t-a[0])/(b[0]-a[0]), dy=((b[3]-a[3]+540)%360)-180;
  return [t,a[1]+(b[1]-a[1])*f,a[2]+(b[2]-a[2])*f,a[3]+dy*f,a[4]||0];
}
function rpDraw(r){
  var t=r.t,d=r.d;
  r.sc.value=t; r.tl.textContent=(d.rt+t).toFixed(1)+' s'; r.pb.innerHTML=r.playing?'&#10074;&#10074;':'&#9654;';
  r.pl.forEach(function(q){
    var s=q.p.s,c=rpPos(s,t),dead=q.p.d&&t>=q.p.d[0];
    if(dead){ q.g.style.display=''; q.ar.style.display='none'; q.mk.style.display='none'; q.fr.style.display='none'; q.xx.style.display=''; q.tx.setAttribute('x',q.p.d[1]+9); q.tx.setAttribute('y',q.p.d[2]+4); return; }
    q.xx.style.display='none'; q.ar.style.display=''; q.mk.style.display='';
    if(!c){q.g.style.display='none';return;} q.g.style.display='';
    var x=c[1],y=c[2],a=c[3]*Math.PI/180,ux=Math.cos(a),uy=-Math.sin(a),L=q.p.me?20:14,W=q.p.me?5:4;
    var tx=x+ux*L,ty=y+uy*L,bx=x+ux*(L-8),by=y+uy*(L-8),px=-uy*W,py=ux*W;
    q.ar.setAttribute('points',tx.toFixed(1)+','+ty.toFixed(1)+' '+(bx+px).toFixed(1)+','+(by+py).toFixed(1)+' '+(bx-px).toFixed(1)+','+(by-py).toFixed(1));
    q.mk.setAttribute('cx',x); q.mk.setAttribute('cy',y);
    var frac=0; (q.p.fl||[]).forEach(function(b){ if(t>=b[0]&&t<=b[0]+b[1]) frac=Math.max(frac,1-(t-b[0])/b[1]); });
    if(frac>0.005){ var R=(q.p.me?8:5)+4, L=2*Math.PI*R; q.fr.style.display=''; q.fr.setAttribute('cx',x); q.fr.setAttribute('cy',y); q.fr.setAttribute('stroke-dasharray',(L*frac).toFixed(1)+' '+L.toFixed(1)); q.fr.setAttribute('transform','rotate(-90 '+x+' '+y+')'); } else q.fr.style.display='none';
    if(!q.p.m&&!q.p.me){ var sc=c[4]?'#ffd070':'#ffaa3c'; q.mk.setAttribute('fill',sc); q.ar.setAttribute('fill',sc); q.tx.setAttribute('fill',sc); }
    q.tx.setAttribute('x',x+9); q.tx.setAttribute('y',y+4);
  });
  while(r.fxg.firstChild) r.fxg.removeChild(r.fxg.firstChild);
  var FXR={smokegrenade:144,molotov:150,hegrenade:350,c4:1750}, u=d.u||0.9, fx=d.fx||[];
  for(var i=0;i<fx.length;i++){
    var e=fx[i],age=t-e[0],life=e[4]-e[0]; if(age<0||t>e[4]) continue;
    var x=e[2],y=e[3],k=e[1];
    if(k==='smokegrenade'){ var f=Math.min(1,age/1.0),fade=Math.min(1,Math.max(0,(e[4]-t)/2.0));
      r.fxg.appendChild(rpEl('circle',{cx:x,cy:y,r:(FXR[k]*u*f).toFixed(1),fill:'#c8c8c8','fill-opacity':(0.42*fade).toFixed(2),stroke:'#e0e0e0','stroke-opacity':(0.6*fade).toFixed(2)})); }
    else if(k==='molotov'){ var f=Math.min(1,age/0.7),fade=Math.min(1,Math.max(0,(e[4]-t)/0.5)),fl=0.85+0.15*Math.sin(t*23);
      r.fxg.appendChild(rpEl('circle',{cx:x,cy:y,r:(FXR[k]*u*f).toFixed(1),fill:'#ff5a1e','fill-opacity':(0.32*fade*fl).toFixed(2),stroke:'#ffb060','stroke-opacity':(0.7*fade).toFixed(2)})); }
    else if(k==='hegrenade'){ var f=Math.min(1,age/0.45);
      r.fxg.appendChild(rpEl('circle',{cx:x,cy:y,r:(FXR[k]*u*f).toFixed(1),fill:'none',stroke:'#f08c3c','stroke-width':3,'stroke-opacity':(1-f).toFixed(2)}));
      r.fxg.appendChild(rpEl('circle',{cx:x,cy:y,r:(FXR[k]*u*0.25*(1-f)+3).toFixed(1),fill:'#fff','fill-opacity':(0.9*(1-f)).toFixed(2)})); }
    else if(k==='flashbang'){ var f=Math.min(1,age/0.3),rr=8+30*f;
      r.fxg.appendChild(rpEl('circle',{cx:x,cy:y,r:rr.toFixed(1),fill:'#ffffff','fill-opacity':(0.9*(1-f)).toFixed(2)}));
      for(var s=0;s<8;s++){ var a=s*Math.PI/4,L1=rr+4,L2=rr+10+26*f; r.fxg.appendChild(rpEl('line',{x1:(x+Math.cos(a)*L1).toFixed(1),y1:(y+Math.sin(a)*L1).toFixed(1),x2:(x+Math.cos(a)*L2).toFixed(1),y2:(y+Math.sin(a)*L2).toFixed(1),stroke:'#fff59a','stroke-width':2,'stroke-opacity':(1-f).toFixed(2)})); } }
    else if(k==='c4'){ var f=Math.min(1,age/1.0),fade=1-age/life;
      r.fxg.appendChild(rpEl('circle',{cx:x,cy:y,r:(FXR[k]*u*f).toFixed(1),fill:'#ff8c1e','fill-opacity':(0.22*fade).toFixed(2),stroke:'#ffb347','stroke-width':4,'stroke-opacity':fade.toFixed(2)}));
      r.fxg.appendChild(rpEl('circle',{cx:x,cy:y,r:(FXR[k]*u*f*0.55).toFixed(1),fill:'none',stroke:'#fff','stroke-width':2,'stroke-opacity':(0.8*fade).toFixed(2)}));
      var tx=rpEl('text',{x:x+8,y:y-8,fill:'#ffd28a','font-size':13,'font-weight':'bold'}); tx.textContent='C4'; r.fxg.appendChild(tx); }
  }
  r.gl.forEach(function(q){
    var s=q.n.s; if(t<s[0][0]||t>s[s.length-1][0]+0.3){q.g.style.display='none';return;} q.g.style.display='';
    var c=rpPos(s.map(function(v){return [v[0],v[1],v[2],0];}),Math.min(t,s[s.length-1][0]));
    var pts=[]; for(var i=0;i<s.length;i++){ if(s[i][0]<=t) pts.push(s[i][1]+','+s[i][2]); } pts.push(c[1]+','+c[2]);
    q.tr.setAttribute('points',pts.join(' ')); q.mk.setAttribute('cx',c[1]); q.mk.setAttribute('cy',c[2]);
  });
  while(r.shg.firstChild) r.shg.removeChild(r.shg.firstChild);
  var sh=d.sh||[];
  for(var i=0;i<sh.length;i++){
    var s=sh[i],age=t-s[0]; if(age<0||age>0.4) continue;
    var op=(1-age/0.4)*(s[5]?1:0.45);
    var ln=rpEl('line',{x1:s[1],y1:s[2],x2:s[3],y2:s[4],stroke:'#ffffff','stroke-width':s[5]?2:1,'stroke-opacity':op.toFixed(2)});
    r.shg.appendChild(ln);
    if(s[5]) r.shg.appendChild(rpEl('circle',{cx:s[3],cy:s[4],r:4,fill:'#fff','fill-opacity':op.toFixed(2)}));
  }
}
function rpToggle(b){
  var r=rpGet(b);
  if(r.playing){ r.playing=false; cancelAnimationFrame(r.raf); rpDraw(r); return; }
  if(!r.started||r.t>=r.d.end-0.02) r.t=r.d.t0;
  r.started=true; r.playing=true; r.last=performance.now();
  function step(now){
    if(!r.playing) return;
    var sp=parseFloat(r.sp.value||'1'); r.t=Math.min(r.d.end,r.t+(now-r.last)/1000*sp); r.last=now; rpDraw(r);
    if(r.t>=r.d.end){ r.playing=false; rpDraw(r); return; }
    r.raf=requestAnimationFrame(step);
  }
  r.raf=requestAnimationFrame(step);
}
function rpSeek(i){ var r=rpGet(i); r.playing=false; r.started=true; cancelAnimationFrame(r.raf); r.t=parseFloat(i.value); rpDraw(r); }
function rpJump(b,rel){ var card=b.closest('.card'), map=card.querySelector('.map'); var r=rpGet(map); r.playing=false; r.started=true; cancelAnimationFrame(r.raf); r.t=Math.min(r.d.end,Math.max(r.d.t0,rel)); rpDraw(r); }
function rpInitAll(){
  // draw every card's frame at the moment, in small batches so the page stays responsive
  var maps=Array.prototype.slice.call(document.querySelectorAll('.map[data-rp]')).filter(function(m){ return !m.closest('.roundv'); }), i=0;
  function batch(){ var n=0; while(i<maps.length && n<25){ if(!maps[i]._rp) rpGet(maps[i]); i++; n++; } if(i<maps.length) setTimeout(batch,0); }
  batch();
}
window.addEventListener('DOMContentLoaded',function(){
  rpInitAll();
  try{ var sv=localStorage.getItem('cs2report-show'); if(sv==='p'||sv==='m') setShow(sv); }catch(e){}
  var h=location.hash.replace('#',''), first=document.querySelector('.player');
  var rb0=document.querySelector('.rb'); if(rb0 && !document.querySelector('.roundv:not([hidden])')) { var n0=rb0.id.replace('rb-',''); document.getElementById('round-'+n0).hidden=false; rb0.classList.add('on'); }
  var rv=document.querySelector("input[name='view']:checked"); if(rv && rv.value==='rounds') setView('rounds');
  if(!window._spWrapped){ var _sp=showPlayer; window.showPlayer=function(id){ if(!id) return; _sp(id); if(id!=='rounds') _lastPlayer=id; }; window._spWrapped=true; }
  if(h && document.getElementById(h) && document.getElementById(h).classList.contains('player') && h!=='rounds') showPlayer(h);
  else if(first){ showPlayer(first.id); if(h) goHash(); }
});
"""


def css_for(v: float) -> str:
    return MR.sev_css(-v) if v < 0 else IR.imp_css(v)


def esc(s: Any) -> str:
    return html.escape(str(s if s is not None else ''))


ME_COL = '#e05cff'       # the selected player, the same on every card whatever the flag


def arrow(x: float, y: float, yaw: float, col: str, L: float = 14, W: float = 4, opacity: float = 1.0) -> str:
    """Facing marker: a small triangle in front of a player's dot, pointing along their view yaw (radar y points down)."""
    ux, uy = math.cos(math.radians(yaw)), -math.sin(math.radians(yaw))
    tx, ty = x + ux * L, y + uy * L; bx, by = x + ux * (L - 8), y + uy * (L - 8); px, py = -uy * W, ux * W
    return f"<polygon points='{tx:.1f},{ty:.1f} {bx+px:.1f},{by+py:.1f} {bx-px:.1f},{by-py:.1f}' fill='{col}' fill-opacity='{opacity}'/>"


def svg_card(m: Card, proj: Proj, title: str, colour: tuple[int, ...], positive: bool) -> str:
    """Overlay for one moment. m may carry lists: opponents=[(name,(x,y))], extras=[((x,y),label)]. Coordinates in the 900x900 radar frame."""
    def P(p: XY) -> XY:
        x, y = proj(*p); return (round(x, 1), round(y, 1))
    s = ["<svg viewBox='0 0 900 900' xmlns='http://www.w3.org/2000/svg' font-family='Segoe UI,Arial' font-size='12'><g class='st'>"]
    # no static annotations on the map: everything a card shows comes from the replay frame, and the facts text carries the details
    s.append("</g>")
    r, g, b = colour
    s.append(f"<rect x='0' y='0' width='900' height='28' fill='rgb({int(r*.55)},{int(g*.55)},{int(b*.55)})'/><rect x='0' y='0' width='8' height='28' fill='rgb({r},{g},{b})'/>")
    s.append(f"<text x='16' y='19' fill='#fff' font-size='15'>{esc(title)}</text>")
    s.append(f"<text x='10' y='888' fill='#8c8c96' font-size='11'>paused at the moment; press play for the 12 s before it.   {esc(m.get('me_name', 'you'))} = violet   blue = teammates   orange = enemies (lighter = in view)   arrow = facing   white ring = flash time left   X = died   white = shot</text>")
    s.append("</svg>")
    return ''.join(s)


# ----------------------------------------------------------------------------- per-player body
def summary(name: str, mapname: str, rounds: list[tuple[int, str, bool | None]], wins: int, losses: int, net: int, pos: int, neg: int, mistakes: list[Card], plays: list[Card],
            cat: dict[tuple[str, str], list[int]], allrules: dict[tuple[str, str], tuple[str, str, str]], by_round: dict[int, list[int]]) -> str:
    n = max(len(rounds), 1); avg = net / n
    side_net = {'CT': 0, 'T': 0}; side_n = {'CT': 0, 'T': 0}
    for rn, side, won in rounds:
        side_net[side] += sum(by_round.get(rn, [])); side_n[side] += 1
    pos_cats = sorted([k for k in cat if k[0] == 'p'], key=lambda k: -sum(cat[k]))[:2]
    neg_cats = sorted([k for k in cat if k[0] == 'm'], key=lambda k: sum(cat[k]))[:2]
    rnet = {rn: sum(by_round.get(rn, [])) for rn, _, _ in rounds}
    best = max(rnet, key=lambda r: rnet[r]) if rnet else None; worst = min(rnet, key=lambda r: rnet[r]) if rnet else None
    quiet = sum(1 for v in rnet.values() if v == 0)
    def catstr(k: tuple[str, str]) -> str: return f"{allrules[k][0].lower()} ({len(cat[k])}, {sum(cat[k]):+d})"
    verdict = ('a strongly positive game' if avg >= 15 else 'a positive game' if avg >= 5 else 'a roughly neutral game' if avg > -5 else 'a negative game' if avg > -15 else 'a strongly negative game')
    s = [f"{name} finished {wins}-{losses} on {mapname} with an average impact of {avg:+.1f} per round, {verdict}: {len(plays)} plays worth {pos:+d} against {len(mistakes)} mistakes worth {neg:+d}."]
    if pos_cats: s.append("The positive side was driven by " + " and ".join(catstr(k) for k in pos_cats) + ".")
    if neg_cats: s.append("The biggest costs were " + " and ".join(catstr(k) for k in neg_cats) + ".")
    if side_n['CT'] and side_n['T']:
        ct, t = side_net['CT'] / side_n['CT'], side_net['T'] / side_n['T']
        s.append(f"By side, {ct:+.0f} per round on CT and {t:+.0f} per round on T, so the {'CT' if ct > t else 'T'} half carried the game.")
    if best is not None and worst is not None and best != worst:
        s.append(f"The best round was R{best} ({rnet[best]:+d}) and the worst was R{worst} ({rnet[worst]:+d}); {quiet} rounds produced nothing either way.")
    if neg_cats: s.append(f"Removing the {allrules[neg_cats[0]][0].lower()} flags alone would have moved the average to {(net - sum(cat[neg_cats[0]])) / n:+.1f} per round.")
    return ' '.join(s)


def ranked(items: list[Card], rules: Rules, title: str, positive: bool) -> str:
    grouped: dict[Any, dict[str, Any]] = {}
    for m in items:
        g = grouped.setdefault((m['round'], m['time']), dict(v=0, m=m, kinds=[])); g['v'] += m['impact']; g['kinds'].append(rules[m['kind']][0])
    top = sorted(grouped.values(), key=lambda g: -g['v'] if positive else g['v'])[:6]
    return f"<div class='box'><b>{title}</b><ol>" + ''.join(f"<li><span style='color:{css_for(g['v'])};font-weight:700'>{g['v']:+d}</span> &nbsp; R{g['m']['round']} {g['m']['side']} {g['m']['time']}s{(' at ' + esc(g['m']['place'])) if g['m'].get('place') else ''}: {esc('; '.join(g['kinds']))}</li>" for g in top) + "</ol></div>"


def merge_moment(flags: list[Card]) -> Card:
    """One drawable dict for all flags that happened at the same moment."""
    base = dict(flags[0])
    opps: list[Any] = []; extras: list[Any] = []; nades: list[Any] = []
    for f in flags:
        cands = list(f.get('opponents') or [])
        o = f.get('vpos') or f.get('kpos'); n = f.get('victim') or f.get('killer')
        if o and o[0] is not None and o[0] == o[0] and not cands: cands.append((n, o))
        for n, o in cands:
            if o and o[0] is not None and o[0] == o[0] and (n, tuple(o)) not in [(a, tuple(b)) for a, b in opps]: opps.append((n, o))
        if f.get('extra_pos'): extras.append((f['extra_pos'], f.get('extra_label', 'earlier')))
        for w, q in f.get('nades_thrown') or []:
            if (w, tuple(q)) not in [(a, tuple(b)) for a, b in nades]: nades.append((w, q))
        for key in ('path', 'mate_path', 'killer_path', 'victim_path', 'near'):
            if not base.get(key) and f.get(key): base[key] = f[key]
    base['opponents'] = opps; base['extras'] = extras; base['nades_thrown'] = nades
    return base


def player_body(pid: str, E: Demo, mistakes: list[Card], plays: list[Card], proj: Proj, zthr: float | None, name: str) -> tuple[str, dict[str, Any]]:
    for m in mistakes:
        sev, br = MR.severity(m); m['severity'] = sev; m['impact'] = -sev; m['imp_breakdown'] = br + [f"= severity {sev}, counted as impact {-sev:+d}"]; m['side_kind'] = 'm'
    for m in plays:
        v, br = IR.impact(m); m['impact'] = v; m['imp_breakdown'] = br + [f"= impact {v:+d}"]; m['side_kind'] = 'p'
    snap = E['snap']; fz = E['fz']
    rounds = []
    for rn in sorted(fz):
        g = snap[(snap['tick'] == fz[rn]) & (snap['steamid'] == E['me'])]
        if not len(g): continue
        side = 'CT' if int(g.iloc[0]['team_num']) == 3 else 'T'
        w = E['winner'].get(rn); rounds.append((rn + 1, side, (w == side) if w in ('CT', 'T') else None))
    wins = sum(1 for r in rounds if r[2]); losses = sum(1 for r in rounds if r[2] is False)
    neg = sum(m['impact'] for m in mistakes); pos = sum(m['impact'] for m in plays); net = pos + neg; n = max(len(rounds), 1)
    by_round = C.defaultdict(list)
    for m in mistakes + plays: by_round[m['round']].append(m['impact'])
    allrules = {**{('m', k): v for k, v in MR.RULES.items()}, **{('p', k): v for k, v in IR.RULES.items()}}
    cat = C.defaultdict(list)
    for m in mistakes: cat[('m', m['kind'])].append(m['impact'])
    for m in plays: cat[('p', m['kind'])].append(m['impact'])
    cat_order = sorted(cat, key=lambda k: sum(cat[k]))
    # ---- moments: every flag grouped by (round, time), ordered by round then time
    moments = C.defaultdict(list)
    for m in mistakes + plays:
        moments[(m['round'], round(m['time'] or 0, 1))].append(m)
    keys = sorted(moments)
    # grenade flights for the throws on a moment (a timer flag lists throws from several rounds; all are drawn), and how far past the
    # moment its replay should run so a grenade thrown at it is seen going off
    an = E['all_nades']; mine_n = an[an['user_steamid'] == E['me']]
    TAIL = {'flashbang': 1.0, 'hegrenade': 1.0, 'smokegrenade': 3.0, 'molotov': 4.0, 'decoy': 1.0}
    def flights_post(fl: list[Card], tk: int | None) -> tuple[list[Any], float]:
        merged0 = merge_moment(fl); flights = []
        for w, q in merged0.get('nades_thrown') or []:
            cand = mine_n[(mine_n['user_X'] == q[0]) & (mine_n['user_Y'] == q[1])]
            if not len(cand) and len(mine_n):
                cand = mine_n[((mine_n['user_X'] - q[0]) ** 2 + (mine_n['user_Y'] - q[1]) ** 2) <= 4]
            for r in cand.itertuples():
                flt = nade_flight(E, E['me'], int(r.tick), r.weapon)
                if flt: flights.append(flt)
        post = 0.0
        if tk is not None:
            for w, _path, _end, thr, det in flights:
                if tk - 12 * 64 <= thr <= tk + 64 and det > tk: post = max(post, (det - tk) / 64 + TAIL.get(w, 1.0))
        return flights, min(max(post, 0.5), 8.0)
    info: dict[Any, dict[str, Any]] = {}
    for k in keys:
        rn0 = k[0] - 1; tk = int(fz[rn0] + (k[1] or 0) * 64) if rn0 in fz else None
        flights, post = flights_post(moments[k], tk)
        info[k] = dict(tk=tk, flights=flights, post=post, end=(tk + int(post * 64)) if tk is not None else None)
    # moments in the same round whose replay windows overlap share one card, whatever mix of plays and mistakes they are
    clusters: list[Any] = []
    for k in keys:
        if clusters:
            prev = clusters[-1]; ends = [info[x]['end'] for x in prev if info[x]['end'] is not None]
            if prev[0][0] == k[0] and info[k]['tk'] is not None and ends and info[k]['tk'] - 12 * 64 <= max(ends):
                prev.append(k); continue
        clusters.append([k])
    mid = {}
    for i, ks in enumerate(clusters):
        for k in ks: mid[k] = f"{pid}-m{i}"
    first_of_kind: dict[Any, Any] = {}
    for k in keys:
        for f in moments[k]:
            first_of_kind.setdefault((f['side_kind'], f['kind']), mid[k])
    def title_of(f: Card) -> str: return allrules[(f['side_kind'], f['kind'])][0]

    h = [f"<div class='player' id='{pid}' hidden>",
         f"<p class='summary'>{esc(summary(name, E['map'], rounds, wins, losses, net, pos, neg, mistakes, plays, cat, allrules, by_round))}</p>",
         "<div class='score'>",
         f"<div class='box' style='border-left:8px solid {css_for(80 if net >= 0 else -80)}'><small>Average impact per round</small><div class='big' style='color:{css_for(90 if net >= 0 else -90)}'>{net / n:+.1f}</div><small>net {net:+d} over {len(rounds)} rounds: {pos:+d} from {len(plays)} plays, {neg:+d} from {len(mistakes)} mistakes</small></div>",
         f"<div class='box' style='border-left:8px solid {IR.imp_css(70)}'><small>Things to keep doing</small><div class='mid'>{len(plays)}</div><small>impact {pos:+d}, average {round(pos / len(plays)) if plays else 0:+d}</small></div>",
         f"<div class='box' style='border-left:8px solid {MR.sev_css(70)}'><small>Things to improve</small><div class='mid'>{len(mistakes)}</div><small>impact {neg:+d}, average {round(neg / len(mistakes)) if mistakes else 0:+d}</small></div>",
         "</div><div class='box'><b>Round by round</b> <small>net impact per round; green dots = plays, red dots = mistakes; click a round to jump to it</small><div class='strip'>"]
    round_anchor: dict[int, str] = {}
    for k in keys:
        round_anchor.setdefault(k[0], mid[k])
    for rn, side, won in rounds:
        res = "<span class='w'>W</span>" if won else ("<span class='l'>L</span>" if won is False else "-")
        vals = sorted(by_round[rn], key=lambda v: -abs(v)); rnet = sum(vals)
        dots = ''.join(f"<span class='dot' style='background:{css_for(v)}'></span>" for v in vals[:8])
        href = f" onclick=\"location.hash='{round_anchor[rn]}'\" style='cursor:pointer'" if rn in round_anchor else ''
        h.append(f"<div class='rd'{href}><div class='n'>R{rn}</div>{side} {res}<div class='net' style='color:{css_for(rnet) if rnet else '#999'}'>{rnet:+d}</div><div class='dots'>{dots}</div></div>")
    h.append("</div></div><div class='sum'>")
    # every instance of each flag, in round order, for the expandable list under the chips
    inst = C.defaultdict(list)
    for k in keys:
        for f in moments[k]:
            inst[(f['side_kind'], f['kind'])].append((k, f))
    lists: list[str] = []
    for key in cat_order:
        vals = cat[key]; t = sum(vals); a = round(t / len(vals)); lid = f"{pid}-list-{key[0]}-{key[1]}"
        h.append(f"<a class='chip side-{key[0]}' href='#' onclick=\"return toggleList('{lid}', this)\" style='border-left:6px solid {css_for(a)}'><b>{len(vals)}</b>{esc(allrules[key][0])}<br><small>impact <span class='v' style='color:{css_for(t)}'>{t:+d}</span> &middot; avg {a:+d} &middot; {len(vals)} instance{'s' if len(vals) != 1 else ''}</small></a>")
        rows = []
        for k, f in inst[key]:
            snippet = esc(f['facts'])
            head = snippet.split('. ', 1)[1] if '. ' in snippet else snippet
            rows.append(f"<a class='li' href='#{mid[k]}' style='border-left:4px solid {css_for(f['impact'])}'><span class='badge' style='background:{css_for(f['impact'])}'>{f['impact']:+d}</span> <b>Round {k[0]}, {esc(f['side'])}, {k[1]} s</b>{(' at ' + esc(f['place'])) if f.get('place') else ''} <span class='sn'>{head[:220]}</span></a>")
        # the panel sits right after its chip inside the flex row and spans the full width, so it opens directly under the chip's row
        h.append(f"<div class='chipl side-{key[0]}' id='{lid}'><div class='lh'><b>{esc(allrules[key][0])}</b> &middot; {len(vals)} instance{'s' if len(vals) != 1 else ''}, in round order &middot; click one to open its card <a href='#{pid}-guide-{key[0]}-{key[1]}' class='g'>what to do</a></div>{''.join(rows)}</div>")
    h.append("</div>")
    # ranked lists link to moments
    def ranked_m(positive: bool, title: str) -> str:
        items = sorted(keys, key=lambda k: (-sum(f['impact'] for f in moments[k]) if positive else sum(f['impact'] for f in moments[k])))
        items = [k for k in items if (sum(f['impact'] for f in moments[k]) > 0) == positive][:6]
        return f"<div class='box side-{'p' if positive else 'm'}'><b>{title}</b><ol>" + ''.join(f"<li><a href='#{mid[k]}' style='color:inherit;text-decoration:none'><span style='color:{css_for(sum(f['impact'] for f in moments[k]))};font-weight:700'>{sum(f['impact'] for f in moments[k]):+d}</span> &nbsp; R{k[0]} {moments[k][0]['side']} {k[1]}s{(' at ' + esc(moments[k][0]['place'])) if moments[k][0].get('place') else ''}: {esc('; '.join(title_of(f) for f in moments[k]))}</a></li>" for k in items) + "</ol></div>"
    h.append("<div class='two'>" + ranked_m(False, 'Biggest negative moments') + ranked_m(True, 'Biggest positive moments') + "</div>")
    # ---- timeline
    h.append(f"<h2>Timeline ({len(keys)} moments in {len(clusters)} cards, in order)</h2>")
    for ks in clusters:
        k = ks[0]
        fl = sorted([f for kk in ks for f in moments[kk]], key=lambda f: (round(f['time'] or 0, 1), f['impact']))
        mnet = sum(f['impact'] for f in fl); positive = not any(f['side_kind'] == 'm' for f in fl)
        merged = merge_moment(fl); merged['me_name'] = name
        merged['flights'] = [x for kk in ks for x in info[kk]['flights']]
        rn0 = k[0] - 1; tk = info[k]['tk']
        tke = max([info[kk]['end'] for kk in ks if info[kk]['end'] is not None], default=None)
        post = ((tke - tk) / 64) if (tk is not None and tke is not None) else 0.5
        marks = [round((info[kk]['tk'] - tk) / 64, 2) for kk in ks if info[kk]['tk'] is not None and tk is not None]
        my_team = int(snap[(snap['tick'] == fz[rn0]) & (snap['steamid'] == E['me'])].iloc[0]['team_num']) if (rn0 in fz and ((snap['tick'] == fz[rn0]) & (snap['steamid'] == E['me'])).any()) else None
        dth = E['deaths']
        def sees_me(v: Any) -> bool:
            try: return E['me'] in set(str(x) for x in v)
            except TypeError: return False
        # replay: every player's last 12 s at 0.25 s steps plus every shot, in radar coordinates, for the in-page player
        rp: dict[str, Any] = dict(t0=-12.0, end=round(post, 2), rt=round(k[1] or 0, 1), mc=ME_COL, p=[], sh=[], marks=marks)
        if tk is not None:
            dwin = dth[(dth['tick'] >= tk - 12 * 64) & (dth['tick'] <= tke + 8)]
            dead_at = {str(r.user_steamid): (int(r.tick), (float(r.user_X), float(r.user_Y))) for r in dwin.itertuples() if r.user_X == r.user_X and r.user_Y == r.user_Y}
            wall = snap[(snap['tick'] >= tk - 12 * 64) & (snap['tick'] <= tke) & (snap['is_alive'] == True)]
            team_of = {}
            for sid, g in wall.groupby('steamid'):
                g = g.sort_values('tick'); team_of[str(sid)] = int(g['team_num'].iloc[-1])
                rows = list(g.itertuples())
                keep = rows[::2] + ([rows[-1]] if (len(rows) - 1) % 2 else [])
                smp = []
                enemy = team_of[str(sid)] != my_team
                for r in keep:
                    if not (r.X == r.X and r.Y == r.Y): continue
                    x, y = proj(r.X, r.Y); yaw = r.yaw if r.yaw == r.yaw else 0.0
                    smp.append([round((int(r.tick) - tk) / 64, 2), x, y, int(yaw), int(enemy and sees_me(r.approximate_spotted_by))])
                if len(smp) < 2 and str(sid) not in dead_at: continue      # a single sample only matters when it ends in a death marker
                ent = dict(n=str(g['name'].iloc[-1]), m=int(team_of[str(sid)] == my_team), me=int(sid == E['me']), s=smp)
                bl = E['blind']; bw = bl[(bl['user_steamid'] == str(sid)) & (bl['tick'] >= tk - 12 * 64 - 6 * 64) & (bl['tick'] <= tke)]
                if len(bw): ent['fl'] = [[round((int(r.tick) - tk) / 64, 2), round(float(r.blind_duration), 2)] for r in bw.itertuples() if float(r.blind_duration) > 0]
                if str(sid) in dead_at:
                    dtk, dpos = dead_at[str(sid)]; dts = (dtk - tk) / 64
                    if 0 < dts <= 8 / 64: dts = 0.0                     # the moment's time is rounded; this death is the moment itself
                    ent['d'] = [min(round(dts, 2), round(post, 2)), *proj(dpos[0], dpos[1])]
                rp['p'].append(ent)
            # players who died earlier in the round than the window: no samples, but they stay on the card as an X at their death spot
            have = {str(sid) for sid in wall['steamid'].unique()}
            g_start = snap[snap['tick'] == fz[rn0]]
            early = dth[(dth['tick'] >= fz[rn0]) & (dth['tick'] < tk - 12 * 64) & dth['user_X'].notna() & dth['user_Y'].notna()]
            for r in early.itertuples():
                sid = str(r.user_steamid)
                if sid in have: continue
                have.add(sid)
                row = g_start[g_start['steamid'] == sid]
                tn_ = int(row.iloc[0]['team_num']) if len(row) and row.iloc[0]['team_num'] == row.iloc[0]['team_num'] else -1
                rp['p'].append(dict(n=str(r.user_name), m=int(tn_ == my_team), me=int(sid == E['me']), s=[], d=[round((int(r.tick) - tk) / 64, 2), *proj(float(r.user_X), float(r.user_Y))]))
            pr = E['proj']; inwin = pr[(pr['tick'] >= tk - 12 * 64) & (pr['tick'] <= tke) & (pr['tick'] % 8 == 0) & pr['x'].notna() & pr['y'].notna()]
            rp['g'] = []
            for (ent, kind), g in inwin.groupby(['grenade_entity_id', 'kind']):
                g = g.sort_values('tick'); ticks = g['tick'].to_numpy()
                # split reused entity ids at gaps longer than a second
                cuts = [0] + [i for i in range(1, len(ticks)) if ticks[i] - ticks[i - 1] > 64] + [len(ticks)]
                dt_ = E['deton']
                for a, b in zip(cuts[:-1], cuts[1:]):
                    seg = g.iloc[a:b]
                    dd = dt_[(dt_['steamid'] == str(seg['steamid'].iloc[0])) & (dt_['kind'] == kind) & (dt_['tick'] >= int(seg['tick'].iloc[0]) - 2) & (dt_['tick'] <= int(seg['tick'].iloc[-1]) + 2)]
                    if len(dd): seg = seg[seg['tick'] <= int(dd.iloc[0]['tick'])]
                    if len(seg) < 2: continue
                    rp['g'].append(dict(w=kind, m=int(team_of.get(str(seg['steamid'].iloc[0]), -1) == my_team),
                                        s=[[round((int(r.tick) - tk) / 64, 2), *proj(float(r.x), float(r.y))] for r in seg.itertuples()]))
            fx = E['fx']; fxw = fx[(fx['end'] >= tk - 12 * 64) & (fx['tick'] <= tke) & fx['x'].notna() & fx['y'].notna()]
            rp['fx'] = [[round((int(r.tick) - tk) / 64, 2), r.kind, *proj(float(r.x), float(r.y)), round((int(r.end) - tk) / 64, 2)] for r in fxw.itertuples()]
            cx, cy = merged['pos']; rp['u'] = round((proj(cx + 100, cy)[0] - proj(cx, cy)[0]) / 100, 4)   # radar px per world unit
            gf = E['gunfire']; hurt = E['hurt']
            shots = gf[(gf['tick'] >= tk - 12 * 64) & (gf['tick'] <= tke)]
            hits = hurt[(hurt['tick'] >= tk - 12 * 64 - 2) & (hurt['tick'] <= tke + 2)]
            for r in shots.itertuples():
                if not (r.user_X == r.user_X and r.user_yaw == r.user_yaw): continue
                hh = hits[(hits['attacker_steamid'] == r.user_steamid) & ((hits['tick'] - int(r.tick)).abs() <= 1)]
                hh = hh[hh['user_X'].notna() & hh['user_Y'].notna()]
                if len(hh):
                    x2, y2 = proj(float(hh.iloc[0]['user_X']), float(hh.iloc[0]['user_Y'])); hit = 1
                x1, y1 = proj(r.user_X, r.user_Y)
                if not len(hh):
                    # a miss: the demo stores only the aim direction, so run the ray to the first wall on the radar (60 m at most)
                    e = ray_end(x1, y1, float(r.user_yaw), getattr(r, 'user_Z', None), 60 / 0.0254 * rp['u'])
                    if e is None:
                        ray = 10 / 0.0254; e = proj(r.user_X + math.cos(math.radians(r.user_yaw)) * ray, r.user_Y + math.sin(math.radians(r.user_yaw)) * ray)
                    x2, y2 = e; hit = 0
                rp['sh'].append([round((int(r.tick) - tk) / 64, 2), x1, y1, x2, y2, hit, int(team_of.get(str(r.user_steamid), -1) == my_team)])
        rp_json = esc(json.dumps(rp, separators=(',', ':')))
        lower = zthr is not None and merged.get('z') is not None and merged['z'] < zthr
        css = css_for(mnet); col = MR.sev_rgb(-mnet) if mnet < 0 else IR.imp_rgb(mnet)
        res = '' if merged.get('won') is None else ("<span class='won'>Round won</span>" if merged['won'] else "<span class='lost'>Round lost</span>")
        titles = ', '.join(dict.fromkeys(title_of(f) for f in fl))
        times = ' + '.join(f"{kk[1]}s" for kk in ks)
        svg = svg_card(merged, proj, f"R{k[0]} {merged['side']} {times}  |  {titles}   net {mnet:+d}", col, positive)
        blocks = []
        for f in fl:
            fc = css_for(f['impact'])
            note = f"<div class='br'>{esc(f['util_note'])}</div>" if f.get('util_note') else ''
            rel = round((round(f['time'] or 0, 1)) - (k[1] or 0), 2)
            jump = f"<button class='jb' onclick='rpJump(this, {rel})' title='Show the replay at this moment'>&#9654; {round(f['time'] or 0, 1)} s</button>" if len(ks) > 1 else ''
            blocks.append(f"<div class='flag side-{f['side_kind']}' style='border-left:4px solid {fc}'><div><span class='badge' style='background:{fc}'>{f['impact']:+d}</span> <b>{esc(title_of(f))}</b> {jump}<a href='#{pid}-guide-{f['side_kind']}-{f['kind']}' class='g'>what to do</a></div>"
                          f"<div class='br'>{esc(' · '.join(f['imp_breakdown']))}</div><div class='facts'>{esc(f['facts'])}</div>{note}</div>")
        ctl = (f"<div class='ctl'><button class='pb' onclick='rpToggle(this)' title='Replay the last 12 s'>&#9654;</button>"
               f"<input type='range' class='sc' min='{rp['t0']}' max='{rp['end']}' step='0.05' value='0' oninput='rpSeek(this)' list='tk-{mid[k]}'><datalist id='tk-{mid[k]}'>{''.join(f'<option value=\"{mk}\"></option>' for mk in marks)}</datalist>"
               f"<span class='tl'>{rp['rt']:.1f} s</span><select class='sp' title='Playback speed'><option value='0.25'>&#188;&#215;</option><option value='0.5'>&#189;&#215;</option><option value='1' selected>1&#215;</option><option value='2'>2&#215;</option></select></div>"
               f"<div class='rlk'>replay: arrow = facing &middot; X = died &middot; white line = shot, bright to the player it hit, faint = a miss, drawn to the nearest wall on the radar &middot; small dots = grenades in flight, with their effects while they last</div>")
        sides = ''.join(sorted(set(f['side_kind'] for f in fl)))
        h.append(f"<div class='card' id='{mid[k]}' data-sides='{sides}' style='border-left:8px solid {css}'><div class='mapw'><div class='map {'l' if lower else 'u'}' data-rp='{rp_json}'>{svg}</div>{ctl}</div><div class='facts'>"
                 f"<div class='mh'><span class='badge' style='background:{css}'>Net {mnet:+d}</span> <b>Round {k[0]}, {merged['side']}, {' + '.join(f'{kk[1]} s' for kk in ks)}</b>{(' at ' + esc(merged['place'])) if merged.get('place') else ''} &nbsp; {res}</div>{''.join(blocks)}</div></div>")
    # ---- flag guide, once per kind
    h.append("<h2>Flag guide</h2><small>Why each flag matters and what to do about it, once per flag. Timeline entries link here.</small>")
    for key in cat_order:
        title, why, do = allrules[key]; positive = key[0] == 'p'; accent = IR.imp_css(80) if positive else MR.sev_css(80)
        h.append(f"<div class='why side-{key[0]}' id='{pid}-guide-{key[0]}-{key[1]}' style='border-left:4px solid {accent}'><b>{esc(title)}</b> ({len(cat[key])}, impact {sum(cat[key]):+d})<br><b>{'Why it worked' if positive else 'Why it is a mistake'}:</b> {esc(why)}<br><b>{'Keep doing' if positive else 'What to do instead'}:</b> {esc(do)}</div>")
    h.append("</div>")
    return '\n'.join(h), dict(net=net, n=len(rounds), wins=wins, losses=losses, avg=net / n)


# ----------------------------------------------------------------------------- page
_OCC: dict[str, Any] = {}


def set_occluder(bases: dict[str, Any], D: Demo, proj: Proj, zthr: float | None) -> None:
    """Walkable-pixel masks from the radar images, used to stop a missed shot at the first wall. The threshold is taken from
    the radar brightness under real player positions in this demo (2nd percentile, scaled), so it adapts to each map's palette."""
    import numpy as np
    snap = D['snap']; s = snap[snap['is_alive'] == True].iloc[::9]
    masks = {}
    for key in ('upper', 'lower'):
        im = bases.get(key)
        if im is None: continue
        L = np.asarray(im.convert('L'), dtype=np.float32); H, W = L.shape
        sel = s if key == 'upper' or zthr is None else s[s['Z'] < zthr] if 'Z' in s.columns else s
        xy = np.array([proj(x, y) for x, y in zip(sel['X'], sel['Y'])], dtype=int) if len(sel) else np.zeros((0, 2), int)
        if len(xy):
            xy = xy[(xy[:, 0] >= 0) & (xy[:, 0] < W) & (xy[:, 1] >= 0) & (xy[:, 1] < H)]
        thr = float(np.clip(0.8 * np.percentile(L[xy[:, 1], xy[:, 0]], 2), 12, 45)) if len(xy) > 50 else 30.0
        masks[key] = L > thr
    _OCC.clear(); _OCC.update(masks); _OCC['zthr'] = zthr


def ray_end(x0: float, y0: float, yaw_deg: float, z: float | None, max_px: float) -> XY | None:
    """Radar point where a ray from (x0, y0) in the aim direction first leaves the walkable area (approximate: the radar has no height)."""
    import numpy as np
    mask = _OCC.get('lower') if (z is not None and z == z and _OCC.get('zthr') is not None and z < _OCC['zthr'] and _OCC.get('lower') is not None) else _OCC.get('upper')
    if mask is None: return None
    H, W = mask.shape
    ux, uy = math.cos(math.radians(yaw_deg)), -math.sin(math.radians(yaw_deg))
    n = max(8, int(max_px)); d = np.arange(1, n + 1)
    fx, fy = x0 + d * ux, y0 + d * uy
    inb = (fx >= 0) & (fx < W) & (fy >= 0) & (fy < H)
    xs = np.clip(fx.astype(int), 0, W - 1); ys = np.clip(fy.astype(int), 0, H - 1)
    walk = mask[ys, xs] & inb
    if not walk[:8].any(): stop = 8                     # shooter drawn on a dark edge: give the ray a few pixels
    else:
        s0 = int(np.argmax(walk[:8])); bad = ~walk[s0:]
        nw = np.where(bad[:-1] & bad[1:])[0]                 # a wall is two dark pixels in a row; one-pixel outlines (stairs, edges) are not
        stop = s0 + int(nw[0]) if len(nw) else n
    return (round(x0 + stop * ux, 1), round(y0 + stop * uy, 1))


_W: dict[str, Any] = {}


def _worker_init(pickle_path: str) -> None:
    with open(pickle_path, 'rb') as f: D = pickle.load(f)
    bases, proj, zthr = make_map(D)
    if bases['lower'] is None: zthr = None
    set_occluder(bases, D, proj, zthr)
    _W.update(D=D, proj=proj, zthr=zthr)
    MR.PROGRESS = lambda *a, **k: None


def _analyse(tn: int, sid: str, name: str) -> tuple[str, str, dict[str, Any]]:
    D = _W['D']; E = for_player(D, sid)
    mistakes = MR.detect(E); plays = IR.detect(E)
    pid = f"p{sid[-6:]}"
    body, st = player_body(pid, E, mistakes, plays, _W['proj'], _W['zthr'], name)
    return sid, body, dict(st, pid=pid, name=name, team=tn)


def worker_count(n_players: int) -> int:
    """Processes for the per-player analysis: CS2REPORT_WORKERS overrides (1 = sequential), else one per player up to the core count."""
    env = os.environ.get('CS2REPORT_WORKERS')
    if env and env.strip().isdigit(): return max(1, min(int(env), n_players))
    return max(1, min(n_players, os.cpu_count() or 1))


def round_replay(D: Demo, rn: int, proj: Proj) -> tuple[dict[str, Any], list[Any], float | None]:
    """Replay data for a whole round: freeze end (t = 0) to the round end plus 3 s. Same format as the card replays."""
    snap = D['snap']; fz = D['fz']; ft = int(fz[rn]); end = int(D.get('round_end', {}).get(rn, fz.get(rn + 1, int(snap['tick'].max())))) + 3 * 64
    T = lambda tick: round((int(tick) - ft) / 64, 2)
    rp: dict[str, Any] = dict(t0=0.0, end=T(end), rt=0.0, mc='#e05cff', p=[], sh=[], marks=[], g=[], fx=[])
    win = snap[(snap['tick'] >= ft) & (snap['tick'] <= end) & (snap['is_alive'] == True)]
    dth = D['deaths']; dwin = dth[(dth['tick'] >= ft) & (dth['tick'] <= end + 8) & dth['user_X'].notna()]
    dead_at = {str(r.user_steamid): (int(r.tick), (float(r.user_X), float(r.user_Y))) for r in dwin.itertuples()}
    bl = D['blind']
    for sid, g in win.groupby('steamid'):
        g = g.sort_values('tick'); tn = int(g['team_num'].iloc[-1])
        if tn not in (2, 3): continue
        rows = list(g.itertuples()); keep = rows[::2] + ([rows[-1]] if (len(rows) - 1) % 2 else [])
        smp = [[T(r.tick), *proj(r.X, r.Y), int(r.yaw if r.yaw == r.yaw else 0), 0] for r in keep if r.X == r.X]
        if len(smp) < 2 and str(sid) not in dead_at: continue
        ent = dict(n=str(g['name'].iloc[-1]), m=int(tn == 3), me=0, s=smp)
        bw = bl[(bl['user_steamid'] == str(sid)) & (bl['tick'] >= ft - 6 * 64) & (bl['tick'] <= end)] if len(bl) else bl
        if len(bw): ent['fl'] = [[T(r.tick), round(float(r.blind_duration), 2)] for r in bw.itertuples() if float(r.blind_duration) > 0]
        if str(sid) in dead_at:
            dtk, dpos = dead_at[str(sid)]; ent['d'] = [T(dtk), *proj(*dpos)]
        rp['p'].append(ent)
    team_of = {str(sid): int(g['team_num'].iloc[-1]) for sid, g in win.groupby('steamid')}
    pr = D['proj']; inwin = pr[(pr['tick'] >= ft) & (pr['tick'] <= end) & (pr['tick'] % 8 == 0) & pr['x'].notna() & pr['y'].notna()]
    dt_ = D['deton']
    for (ent_id, kind), g in inwin.groupby(['grenade_entity_id', 'kind']):
        g = g.sort_values('tick'); ticks = g['tick'].to_numpy()
        cuts = [0] + [i for i in range(1, len(ticks)) if ticks[i] - ticks[i - 1] > 64] + [len(ticks)]
        for a, b in zip(cuts[:-1], cuts[1:]):
            seg = g.iloc[a:b]
            dd = dt_[(dt_['steamid'] == str(seg['steamid'].iloc[0])) & (dt_['kind'] == kind) & (dt_['tick'] >= int(seg['tick'].iloc[0]) - 2) & (dt_['tick'] <= int(seg['tick'].iloc[-1]) + 2)]
            if len(dd): seg = seg[seg['tick'] <= int(dd.iloc[0]['tick'])]
            if len(seg) < 2: continue
            rp['g'].append(dict(w=kind, m=int(team_of.get(str(seg['steamid'].iloc[0]), 0) == 3), s=[[T(r.tick), *proj(float(r.x), float(r.y))] for r in seg.itertuples()]))
    fx = D['fx']; fxw = fx[(fx['end'] >= ft) & (fx['tick'] <= end) & fx['x'].notna() & fx['y'].notna()]
    rp['fx'] = [[T(r.tick), r.kind, *proj(float(r.x), float(r.y)), T(r.end)] for r in fxw.itertuples()]
    rp['u'] = round((proj(100, 0)[0] - proj(0, 0)[0]) / 100, 4)
    gf = D['gunfire']; hurt = D['hurt']
    shots = gf[(gf['tick'] >= ft) & (gf['tick'] <= end)]; hits = hurt[(hurt['tick'] >= ft - 2) & (hurt['tick'] <= end + 2)]
    for r in shots.itertuples():
        if not (r.user_X == r.user_X and r.user_yaw == r.user_yaw): continue
        hh = hits[(hits['attacker_steamid'] == r.user_steamid) & ((hits['tick'] - int(r.tick)).abs() <= 1)]
        hh = hh[hh['user_X'].notna() & hh['user_Y'].notna()]
        x1, y1 = proj(r.user_X, r.user_Y)
        if len(hh): x2, y2 = proj(float(hh.iloc[0]['user_X']), float(hh.iloc[0]['user_Y'])); hit = 1
        else:
            e = ray_end(x1, y1, float(r.user_yaw), getattr(r, 'user_Z', None), 60 / 0.0254 * rp['u'])
            if e is None:
                ray = 10 / 0.0254; e = proj(r.user_X + math.cos(math.radians(r.user_yaw)) * ray, r.user_Y + math.sin(math.radians(r.user_yaw)) * ray)
            x2, y2 = e; hit = 0
        rp['sh'].append([T(r.tick), x1, y1, x2, y2, hit, int(team_of.get(str(r.user_steamid), 0) == 3)])
    pl = D['plant'][D['plant']['total_rounds_played'] == rn]
    if len(pl): rp['marks'].append(T(pl.iloc[0]['tick']))
    # kill feed and round facts
    feed = []
    for r in dwin.sort_values('tick').itertuples():
        if int(r.tick) > end - 3 * 64: continue
        feed.append((T(r.tick), str(r.attacker_name) if r.attacker_name == r.attacker_name else 'world', str(r.user_name), (r.weapon or '').replace('weapon_', ''), int(team_of.get(str(r.attacker_steamid), 0)) if r.attacker_steamid == r.attacker_steamid else 0))
    return rp, feed, (T(pl.iloc[0]['tick']) if len(pl) else None)


def build(D: Demo, out_path: str, demo_name: str, focus: str | None = None) -> tuple[dict[str, dict[str, Any]], dict[int, int]]:
    bases, proj, zthr = make_map(D)
    im = bases['upper'].convert('RGB'); w, h = im.size
    corners = [im.getpixel((x, y)) for x in (2, w - 3) for y in (2, h - 3)]
    bg = tuple(sorted(c[i] for c in corners)[len(corners) // 2] for i in range(3))   # median corner colour of the (dimmed) radar
    bg_css = f".map{{background-color:rgb({bg[0]},{bg[1]},{bg[2]})}}.map.u{{background-image:url(data:image/png;base64,{b64(bases['upper'])})}}"
    if bases['lower'] is not None:
        bg_css += f".map.l{{background-image:url(data:image/png;base64,{b64(bases['lower'])})}}"
    else:
        zthr = None
    set_occluder(bases, D, proj, zthr)
    snap = D['snap']; fz = D['fz']; first = min(fz.values())
    roster = snap[snap['tick'] == first][['steamid', 'name', 'team_num']].drop_duplicates('steamid')
    teams: dict[int, list[Any]] = {2: [], 3: []}
    for r in roster.itertuples():
        if r.team_num == r.team_num and int(r.team_num) in teams: teams[int(r.team_num)].append((str(r.steamid), str(r.name)))   # NaN = not on a team at the first freeze
    team_wins = {}
    for tn, members in teams.items():
        w = 0
        if members:
            sid = members[0][0]
            for rn in sorted(fz):
                g = snap[(snap['tick'] == fz[rn]) & (snap['steamid'] == sid)]
                if len(g):
                    side = 'CT' if int(g.iloc[0]['team_num']) == 3 else 'T'
                    if D['winner'].get(rn) == side: w += 1
        team_wins[tn] = w
    bodies = {}; stats = {}
    players = [(tn, sid, name) for tn in (3, 2) for sid, name in teams[tn]]
    total_players = len(players) or 1; done = 0
    workers = worker_count(total_players)
    if workers > 1:
        # every player is independent: analyse them in parallel processes, each loading the parsed demo once
        progress(34, f'analysing {total_players} players on {workers} processes')
        fd, pk = tempfile.mkstemp(prefix='cs2report_', suffix='.pkl'); os.close(fd)
        for var in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'): os.environ.setdefault(var, '1')
        try:
            with open(pk, 'wb') as f: pickle.dump(D, f, protocol=pickle.HIGHEST_PROTOCOL)
            for attempt in (1, 2):      # a worker can die in a native parser crash; a second pool usually completes the rest
                todo = [(tn, sid, name) for tn, sid, name in players if sid not in bodies]
                if not todo: break
                try:
                    with CF.ProcessPoolExecutor(max_workers=min(workers, len(todo)), initializer=_worker_init, initargs=(pk,)) as ex:
                        futs = {ex.submit(_analyse, tn, sid, name): (tn, sid, name) for tn, sid, name in todo}
                        for fut in CF.as_completed(futs):
                            sid, body, st = fut.result(); bodies[sid] = body; stats[sid] = st; done += 1
                            progress(34 + 60 * done / total_players, f"analysed {st['name']} ({done} of {total_players})")
                except CF.process.BrokenProcessPool as e:
                    print(f"worker pool broke ({e}); " + ("starting a new pool for the remaining players" if attempt == 1 else "finishing the remaining players in this process"), file=sys.stderr)
                    progress(34 + 60 * done / total_players, f"a worker crashed; {'retrying the rest' if attempt == 1 else 'finishing in one process'}")
        except Exception as e:
            print(f"worker pool failed ({e}); finishing the remaining players in this process", file=sys.stderr)
        finally:
            try: os.remove(pk)
            except OSError: pass
    if len(bodies) < len(players):
        for tn, sid, name in players:
            if sid in bodies: continue
            step = 60 / total_players; base_pct = 34 + step * done
            progress(base_pct, f'analysing {name} ({done + 1} of {total_players}): mistakes')
            E = for_player(D, sid)
            mistakes = MR.detect(E)
            progress(base_pct + step * 0.45, f'analysing {name} ({done + 1} of {total_players}): plays')
            plays = IR.detect(E)
            progress(base_pct + step * 0.8, f'analysing {name} ({done + 1} of {total_players}): page')
            done += 1
            pid = f"p{sid[-6:]}"
            body, st = player_body(pid, E, mistakes, plays, proj, zthr, name)
            bodies[sid] = body; stats[sid] = dict(st, pid=pid, name=name, team=tn)
    winner_tn = max(team_wins, key=lambda tn: team_wins[tn]) if team_wins[2] != team_wins[3] else None
    h = [f"<!doctype html><html><head><meta charset='utf-8'><title>Performance report {D['map']}</title><style>{CSS}{bg_css}</style><script>{JS}</script></head><body>",
         f"<h1>Performance report: {D['map']}</h1><small>{esc(demo_name)}. {len(fz)} rounds. One metric, impact: good plays positive, mistakes negative, every number shows its arithmetic. Pick a player.</small>",
                  "<div class='showsel viewsel'><label><input type='radio' name='view' value='players' checked onchange='setView(this.value)'><span><b>Players</b><small>one player's flags, cards and replays</small></span></label>"
         "<label><input type='radio' name='view' value='rounds' onchange='setView(this.value)'><span class='sv'><b>Rounds</b><small>every round in full, nobody in focus</small></span></label></div>",
         "<div id='playersview'><div class='teams'>"]
    for tn in (3, 2):
        members = sorted(teams[tn], key=lambda x: -stats[x[0]]['avg'])
        won = winner_tn == tn; tie = winner_tn is None
        col = '#999' if tie else (IR.imp_css(85) if won else MR.sev_css(85))
        label = 'Started CT' if tn == 3 else 'Started T'
        h.append(f"<div class='team' style='border-left:8px solid {col}'><div class='th'><b>{label}</b><span class='rw' style='color:{col}'>{team_wins[tn]} rounds{'' if tie else (' &middot; won' if won else ' &middot; lost')}</span></div><div class='tabs'>")
        for sid, name in members:
            st = stats[sid]; a = st['avg']
            h.append(f"<div class='tab' id='tab-{st['pid']}' onclick=\"showPlayer('{st['pid']}')\" style='border-left:5px solid {css_for(a * 4)}'><span class='nm'>{esc(name)}</span><span class='ai' style='color:{css_for(a * 4)}'>{a:+.1f}</span><small>avg impact / round &middot; net {st['net']:+d}</small></div>")
        h.append("</div></div>")
    h.append("</div>" + "<div class='showsel'><label><input type='radio' name='show' value='all' checked onchange='setShow(this.value)'><span><b>Everything</b><small>plays and mistakes</small></span></label>"
         "<label><input type='radio' name='show' value='p' onchange='setShow(this.value)'><span class='sp'><b>Things to keep doing</b><small>plays only</small></span></label>"
         "<label><input type='radio' name='show' value='m' onchange='setShow(this.value)'><span class='sm'><b>Things to improve</b><small>mistakes only</small></span></label></div>" + "</div>")   # close teams, then the show selector under the players, then close the players view
    # rounds tab: every round in full, nobody in focus
    progress(95, 'building the round replays')
    rr = ["<div class='player' id='rounds' hidden><h2>Rounds</h2><small>Every round from freeze end to the end, all ten players, nobody highlighted. Blue = CT, orange = T. Pick a round; play or scrub.</small><div class='rsel'>"]
    rounds_html = []
    for rn in sorted(fz):
        try:
            rp, feed, t_plant = round_replay(D, rn, proj)
        except Exception as e:
            print(f"round {rn + 1} replay skipped ({e})", file=sys.stderr); continue
        w = D['winner'].get(rn); reason = D.get('round_reason', {}).get(rn, '')
        col = '#508cff' if w == 'CT' else ('#ffaa3c' if w == 'T' else '#999')
        rr.append(f"<button class='rb' id='rb-{rn}' onclick='showRound({rn})' style='border-left:5px solid {col}'>R{rn + 1}<small>{esc(w or '?')} · {esc(str(reason).replace('_', ' '))}</small></button>")
        rows = ''.join(f"<div class='kf'><span class='kt'>{t:.1f} s</span> <span style='color:{'#508cff' if tn == 3 else ('#ffaa3c' if tn == 2 else '#aaa')}'>{esc(a)}</span> &rarr; {esc(v)} <small>{esc(wp)}</small></div>" for t, a, v, wp, tn in feed)
        plant_line = f"<div class='kf'><span class='kt'>{t_plant:.1f} s</span> bomb planted</div>" if t_plant is not None else ''
        ctl = (f"<div class='ctl'><button class='pb' onclick='rpToggle(this)' title='Play the round'>&#9654;</button>"
               f"<input type='range' class='sc' min='0' max='{rp['end']}' step='0.05' value='0' oninput='rpSeek(this)' list='tk-round-{rn}'><datalist id='tk-round-{rn}'>{''.join(f'<option value=\"{mk}\"></option>' for mk in rp['marks'])}</datalist>"
               f"<span class='tl'>0.0 s</span><select class='sp' title='Playback speed'><option value='0.25'>&#188;&#215;</option><option value='0.5'>&#189;&#215;</option><option value='1' selected>1&#215;</option><option value='2'>2&#215;</option><option value='4'>4&#215;</option></select></div>")
        svg = "<svg viewBox='0 0 900 900' xmlns='http://www.w3.org/2000/svg' font-family='Segoe UI,Arial' font-size='12'><g class='st'></g></svg>"
        rounds_html.append(f"<div class='roundv' id='round-{rn}' hidden><div class='card' style='border-left:8px solid {col}'><div class='mapw'><div class='map u' data-rp='{esc(json.dumps(rp, separators=(',', ':')))}'>{svg}</div>{ctl}</div>"
                           f"<div class='facts'><div class='mh'><b>Round {rn + 1}</b> &nbsp; <span style='color:{col}'>{esc(w or '?')} won</span> &middot; {esc(str(reason).replace('_', ' '))} &middot; {rp['end'] - 3:.0f} s</div>{plant_line}{rows if rows else '<div class=kf>no deaths</div>'}</div></div></div>")
    rr.append("</div>" + ''.join(rounds_html) + "</div>")
    order = ([focus] if focus in bodies else []) + [s for s in bodies if s != focus]
    h.extend(bodies[s] for s in order); h.extend(rr); h.append("</body></html>")
    progress(96, 'writing the page')
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    open(out_path, 'w', encoding='utf-8').write('\n'.join(h))
    progress(100, 'done')
    return stats, team_wins


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument('demo'); ap.add_argument('--player', default=''); ap.add_argument('--out', default=None)
    a = ap.parse_args()
    out = a.out or os.path.splitext(os.path.basename(a.demo))[0] + '_performance.html'
    global _EXPECTED
    MR.PROGRESS = progress
    mb = os.path.getsize(a.demo) / 1e6
    progress(1, f'starting ({mb:.0f} MB demo)')
    D = parse(a.demo, a.player)
    _EXPECTED = expected_seconds(len(D['fz']), mb)
    progress(32, f"{len(D['fz'])} rounds; expected total about {_EXPECTED:.0f} s")
    stats, team_wins = build(D, out, re.sub(r'^tmp_\d+_', '', os.path.basename(a.demo)), focus=a.player or None)   # drop the runner's temp prefix
    remember_timing(len(D['fz']), mb, time.time() - _T0)
    print(f"built in {time.time() - _T0:.0f} s")
    print(f"{D['map']}: started-CT {team_wins[3]} rounds, started-T {team_wins[2]} rounds -> {out}")
    for sid, st in sorted(stats.items(), key=lambda kv: (-kv[1]['team'], -kv[1]['avg'])):
        print(f"  {'CT' if st['team'] == 3 else 'T '} {st['name']:<16} avg impact/round {st['avg']:+6.1f}  net {st['net']:+5d}")

if __name__ == '__main__':
    main()
