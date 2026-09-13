"""Performance report for every player in a demo, one page, one tab per player.

One metric: impact. Good plays count positive, mistakes negative; each player's headline is average impact per round.
Cards are drawn as a shared radar background plus a small inline SVG overlay, so a ten-player page stays small.

Usage:
    python performance_report.py <demo.dem> [--player 76561198063294402] [--out report.html]
"""
import sys, os, argparse, html, json, time, collections as C
import mistake_report as MR
import impact_report as IR
from mistake_report import parse, make_map, b64, for_player

_T0 = time.time(); _EXPECTED = None
TIMINGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'timings.json')


def progress(pct, msg):
    """Print a machine-readable progress line: PROGRESS <pct> <elapsed_s> <eta_s> <message>."""
    el = time.time() - _T0
    prop = el / pct * (100 - pct) if pct > 0 else 0
    eta = max(_EXPECTED - el, prop if pct >= 40 else 0) if _EXPECTED else prop
    print(f"PROGRESS {int(pct)} {el:.0f} {max(0, eta):.0f} {msg}", flush=True)


def expected_seconds(rounds, mb):
    """Estimate total build time from previous runs (seconds per round), falling back to a rule of thumb."""
    try:
        hist = json.load(open(TIMINGS))
        rates = [h['seconds'] / max(h['rounds'], 1) for h in hist[-8:]]
        return sum(rates) / len(rates) * rounds
    except Exception:
        return 1.6 * rounds + 0.03 * mb


def remember_timing(rounds, mb, seconds):
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
.chip:hover{border-color:#666;background:#232838}.chip b{font-size:20px;display:block}.chip .v{font-weight:700}
.why{background:#1a1d26;padding:10px 14px;margin:6px 0 14px;font-size:14px}
.card{display:grid;grid-template-columns:560px 1fr;gap:18px;background:#171a22;border:1px solid #2a2e3a;border-radius:10px;padding:14px;margin:12px 0}
.map{width:560px;height:560px;border-radius:6px;background-color:#111318;background-size:100% 100%;position:relative}
.map svg{position:absolute;inset:0;width:100%;height:100%}
.facts{font-size:14px;line-height:1.5}.k{font-weight:600}
.badge{display:inline-block;color:#fff;font-weight:700;padding:4px 10px;border-radius:6px;margin-bottom:6px}
.br{font-size:12px;color:#aaa;margin-bottom:10px}.lost{color:#ff7a7a}.won{color:#8fd18f}
.two{display:grid;grid-template-columns:1fr 1fr;gap:24px}ol{margin:6px 0 0 18px;padding:0}li{margin:3px 0}
"""

JS = """
function showPlayer(id){
  document.querySelectorAll('.player').forEach(e=>e.hidden=true);
  document.querySelectorAll('.tab').forEach(e=>e.classList.remove('on'));
  var p=document.getElementById(id); if(!p) return; p.hidden=false;
  var t=document.getElementById('tab-'+id); if(t) t.classList.add('on');
  history.replaceState(null,'','#'+id); window.scrollTo(0,0);
}
window.addEventListener('DOMContentLoaded',function(){
  var h=location.hash.replace('#','');
  if(h && document.getElementById(h) && h.indexOf('cat-')<0) showPlayer(h); else showPlayer(document.querySelector('.player').id);
});
"""


def css_for(v):
    return MR.sev_css(-v) if v < 0 else IR.imp_css(v)


def esc(s):
    return html.escape(str(s if s is not None else ''))


# ----------------------------------------------------------------------------- SVG cards
NADE_COL = {'flashbang': '#faf078', 'smokegrenade': '#c8c8c8', 'hegrenade': '#f08c3c', 'molotov': '#ff5a1e', 'incgrenade': '#ff5a1e'}


def trail(pts, rgb, width=3):
    out = []
    n = len(pts)
    for i in range(1, n):
        f = 0.25 + 0.75 * i / n
        (x1, y1), (x2, y2) = pts[i - 1], pts[i]
        out.append(f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='rgb{rgb}' stroke-opacity='{f:.2f}' stroke-width='{width}'/>")
    if pts:
        out.append(f"<circle cx='{pts[0][0]}' cy='{pts[0][1]}' r='3' fill='none' stroke='rgb{rgb}'/>")
    return ''.join(out)


def svg_card(m, proj, title, colour, positive):
    """Overlay for one card. Coordinates in the 900x900 radar frame."""
    P = lambda p: proj(*p)
    s = ["<svg viewBox='0 0 900 900' xmlns='http://www.w3.org/2000/svg' font-family='Segoe UI,Arial' font-size='12'>"]
    for key, rgb in (('victim_path', (255, 170, 60)), ('killer_path', (255, 170, 60)), ('mate_path', (80, 140, 255))):
        pp = m.get(key) or []
        if len(pp) > 1: s.append(trail([P(p) for p in pp], rgb))
    pp = m.get('path') or []
    if len(pp) > 1: s.append(trail([P(p) for p in pp], (70, 220, 110) if positive else (230, 70, 70)))
    for w, p in m.get('nades_thrown') or []:
        x, y = P(p); s.append(f"<circle cx='{x}' cy='{y}' r='5' fill='none' stroke='{NADE_COL.get(w, '#c8c8c8')}' stroke-width='2'/>")
    if m.get('near'):
        x, y = P(m['near'][2]); mx, my = P(m['pos'])
        s.append(f"<line x1='{x}' y1='{y}' x2='{mx}' y2='{my}' stroke='#508cff' stroke-width='1'/><circle cx='{x}' cy='{y}' r='7' fill='#508cff'/><text x='{x+10}' y='{y+4}' fill='#96beff'>{esc(m['near'][1])} {m['near'][0]:.0f}m</text>")
    opp = m.get('vpos') or m.get('kpos'); oname = m.get('victim') or m.get('killer')
    if opp and opp[0] is not None and opp[0] == opp[0]:
        x, y = P(opp); mx, my = P(m['pos'])
        s.append(f"<line x1='{x}' y1='{y}' x2='{mx}' y2='{my}' stroke='#ffaa3c' stroke-width='1'/><polygon points='{x},{y-9} {x-8},{y+6} {x+8},{y+6}' fill='#ffaa3c'/><text x='{x+10}' y='{y+4}' fill='#ffc878'>{esc(oname)}</text>")
    if m.get('extra_pos'):
        x, y = P(m['extra_pos']); s.append(f"<circle cx='{x}' cy='{y}' r='6' fill='none' stroke='#78ff78' stroke-width='2'/><text x='{x+9}' y='{y+4}' fill='#8cff8c'>{esc(m.get('extra_label', 'earlier'))}</text>")
    mx, my = P(m['pos'])
    if positive:
        s.append(f"<circle cx='{mx}' cy='{my}' r='8' fill='#46dc6e' stroke='#fff' stroke-width='2'/>")
    else:
        s.append(f"<line x1='{mx-9}' y1='{my-9}' x2='{mx+9}' y2='{my+9}' stroke='#ff3c3c' stroke-width='4'/><line x1='{mx-9}' y1='{my+9}' x2='{mx+9}' y2='{my-9}' stroke='#ff3c3c' stroke-width='4'/>")
    s.append(f"<text x='{mx+12}' y='{my+14}' fill='{'#96ffaa' if positive else '#ff7878'}'>you</text>")
    r, g, b = colour
    s.append(f"<rect x='0' y='0' width='900' height='28' fill='rgb({int(r*.55)},{int(g*.55)},{int(b*.55)})'/><rect x='0' y='0' width='8' height='28' fill='rgb({r},{g},{b})'/>")
    s.append(f"<text x='16' y='19' fill='#fff' font-size='15'>{esc(title)}</text>")
    s.append("<text x='10' y='888' fill='#8c8c96' font-size='11'>marker = you   orange = the enemy involved   blue = nearest teammate   trails = last 12 s, ring = start   rings = your grenades</text>")
    s.append("</svg>")
    return ''.join(s)


# ----------------------------------------------------------------------------- per-player body
def summary(name, mapname, rounds, wins, losses, net, pos, neg, mistakes, plays, cat, allrules, by_round):
    n = max(len(rounds), 1); avg = net / n
    side_net = {'CT': 0, 'T': 0}; side_n = {'CT': 0, 'T': 0}
    for rn, side, won in rounds:
        side_net[side] += sum(by_round.get(rn, [])); side_n[side] += 1
    pos_cats = sorted([k for k in cat if k[0] == 'p'], key=lambda k: -sum(cat[k]))[:2]
    neg_cats = sorted([k for k in cat if k[0] == 'm'], key=lambda k: sum(cat[k]))[:2]
    rnet = {rn: sum(by_round.get(rn, [])) for rn, _, _ in rounds}
    best = max(rnet, key=rnet.get) if rnet else None; worst = min(rnet, key=rnet.get) if rnet else None
    quiet = sum(1 for v in rnet.values() if v == 0)
    def catstr(k): return f"{allrules[k][0].lower()} ({len(cat[k])}, {sum(cat[k]):+d})"
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


def ranked(items, rules, title, positive):
    grouped = {}
    for m in items:
        g = grouped.setdefault((m['round'], m['time']), dict(v=0, m=m, kinds=[])); g['v'] += m['impact']; g['kinds'].append(rules[m['kind']][0])
    top = sorted(grouped.values(), key=lambda g: -g['v'] if positive else g['v'])[:6]
    return f"<div class='box'><b>{title}</b><ol>" + ''.join(f"<li><span style='color:{css_for(g['v'])};font-weight:700'>{g['v']:+d}</span> &nbsp; R{g['m']['round']} {g['m']['side']} {g['m']['time']}s{(' at ' + esc(g['m']['place'])) if g['m'].get('place') else ''}: {esc('; '.join(g['kinds']))}</li>" for g in top) + "</ol></div>"


def player_body(pid, E, mistakes, plays, proj, zthr, name):
    for m in mistakes:
        sev, br = MR.severity(m); m['severity'] = sev; m['impact'] = -sev; m['imp_breakdown'] = br + [f"= severity {sev}, counted as impact {-sev:+d}"]
    for m in plays:
        v, br = IR.impact(m); m['impact'] = v; m['imp_breakdown'] = br + [f"= impact {v:+d}"]
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
    anchor = lambda key: f"{pid}-cat-{key[0]}-{key[1]}"

    h = [f"<div class='player' id='{pid}' hidden>",
         f"<p class='summary'>{esc(summary(name, E['map'], rounds, wins, losses, net, pos, neg, mistakes, plays, cat, allrules, by_round))}</p>",
         "<div class='score'>",
         f"<div class='box' style='border-left:8px solid {css_for(80 if net >= 0 else -80)}'><small>Average impact per round</small><div class='big' style='color:{css_for(90 if net >= 0 else -90)}'>{net / n:+.1f}</div><small>net {net:+d} over {len(rounds)} rounds: {pos:+d} from {len(plays)} plays, {neg:+d} from {len(mistakes)} mistakes</small></div>",
         f"<div class='box' style='border-left:8px solid {IR.imp_css(70)}'><small>Things to keep doing</small><div class='mid'>{len(plays)}</div><small>impact {pos:+d}, average {round(pos / len(plays)) if plays else 0:+d}</small></div>",
         f"<div class='box' style='border-left:8px solid {MR.sev_css(70)}'><small>Things to improve</small><div class='mid'>{len(mistakes)}</div><small>impact {neg:+d}, average {round(neg / len(mistakes)) if mistakes else 0:+d}</small></div>",
         "</div><div class='box'><b>Round by round</b> <small>net impact per round; green dots = plays, red dots = mistakes</small><div class='strip'>"]
    for rn, side, won in rounds:
        res = "<span class='w'>W</span>" if won else ("<span class='l'>L</span>" if won is False else "-")
        vals = sorted(by_round[rn], key=lambda v: -abs(v)); rnet = sum(vals)
        dots = ''.join(f"<span class='dot' style='background:{css_for(v)}'></span>" for v in vals[:8])
        h.append(f"<div class='rd'><div class='n'>R{rn}</div>{side} {res}<div class='net' style='color:{css_for(rnet) if rnet else '#999'}'>{rnet:+d}</div><div class='dots'>{dots}</div></div>")
    h.append("</div></div><div class='sum'>")
    for key in cat_order:
        vals = cat[key]; t = sum(vals); a = round(t / len(vals))
        h.append(f"<a class='chip' href='#{anchor(key)}' style='border-left:6px solid {css_for(a)}'><b>{len(vals)}</b>{esc(allrules[key][0])}<br><small>impact <span class='v' style='color:{css_for(t)}'>{t:+d}</span> &middot; avg {a:+d}</small></a>")
    h.append("</div><div class='two'>" + ranked(mistakes, MR.RULES, 'Biggest negative moments', False) + ranked(plays, IR.RULES, 'Biggest positive moments', True) + "</div>")
    items = C.defaultdict(list)
    for m in mistakes: items[('m', m['kind'])].append(m)
    for m in plays: items[('p', m['kind'])].append(m)
    shown = set()
    for key in cat_order:
        positive = key[0] == 'p'; rules = IR.RULES if positive else MR.RULES
        accent = IR.imp_css(80) if positive else MR.sev_css(80)
        lw, ld = ('Why it worked', 'Keep doing') if positive else ('Why it is a mistake', 'What to do instead')
        if key[0] not in shown:
            shown.add(key[0])
            h.append(f"<h2 style='border-color:{accent}'>{'Things to keep doing' if positive else 'Things to improve'} ({len(plays) if positive else len(mistakes)}, impact {pos if positive else neg:+d})</h2>")
        ms = sorted(items[key], key=lambda m: (m['impact'], m['round'], m['time'] or 0))
        title, why, do = rules[key[1]]
        h.append(f"<h3 id='{anchor(key)}'>{esc(title)} ({len(ms)}, impact {sum(m['impact'] for m in ms):+d})</h3><div class='why' style='border-left:4px solid {accent}'><b>{lw}:</b> {esc(why)}<br><b>{ld}:</b> {esc(do)}</div>")
        for m in ms:
            lower = zthr is not None and m.get('z') is not None and m['z'] < zthr
            v = m['impact']; css = css_for(v); col = MR.sev_rgb(-v) if v < 0 else IR.imp_rgb(v)
            res = '' if m.get('won') is None else ("<span class='won'>Round won</span>" if m['won'] else "<span class='lost'>Round lost</span>")
            note = f"<div class='br'>{esc(m['util_note'])}</div>" if m.get('util_note') else ''
            svg = svg_card(m, proj, f"R{m['round']} {m['side']} {m['time']}s  |  {title}   impact {v:+d}", col, positive)
            h.append(f"<div class='card' style='border-left:8px solid {css}'><div class='map {'l' if lower else 'u'}'>{svg}</div><div class='facts'>"
                     f"<div class='badge' style='background:{css}'>Impact {v:+d}</div><div class='br'>{esc(' · '.join(m['imp_breakdown']))}</div>"
                     f"<div class='k' style='color:{accent}'>What happened</div>{esc(m['facts'])}<br>{res}{note}</div></div>")
    h.append("</div>")
    return '\n'.join(h), dict(net=net, n=len(rounds), wins=wins, losses=losses, avg=net / n)


# ----------------------------------------------------------------------------- page
def build(D, out_path, demo_name, focus=None):
    bases, proj, zthr = make_map(D)
    bg_css = f".map.u{{background-image:url(data:image/png;base64,{b64(bases['upper'])})}}"
    if bases['lower'] is not None:
        bg_css += f".map.l{{background-image:url(data:image/png;base64,{b64(bases['lower'])})}}"
    else:
        zthr = None
    snap = D['snap']; fz = D['fz']; first = min(fz.values())
    roster = snap[snap['tick'] == first][['steamid', 'name', 'team_num']].drop_duplicates('steamid')
    teams = {2: [], 3: []}
    for r in roster.itertuples():
        if int(r.team_num) in teams: teams[int(r.team_num)].append((str(r.steamid), str(r.name)))
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
    total_players = sum(len(v) for v in teams.values()) or 1; done = 0
    for tn in (3, 2):
        for sid, name in teams[tn]:
            progress(34 + 60 * done / total_players, f'analysing {name} ({done + 1} of {total_players})')
            E = for_player(D, sid)
            mistakes = MR.detect(E); plays = IR.detect(E)
            done += 1
            pid = f"p{sid[-6:]}"
            body, st = player_body(pid, E, mistakes, plays, proj, zthr, name)
            bodies[sid] = body; stats[sid] = dict(st, pid=pid, name=name, team=tn)
    winner_tn = max(team_wins, key=team_wins.get) if team_wins[2] != team_wins[3] else None
    h = [f"<!doctype html><html><head><meta charset='utf-8'><title>Performance report {D['map']}</title><style>{CSS}{bg_css}</style><script>{JS}</script></head><body>",
         f"<h1>Performance report: {D['map']}</h1><small>{esc(demo_name)}. {len(fz)} rounds. One metric, impact: good plays positive, mistakes negative, every number shows its arithmetic. Pick a player.</small>",
         "<div class='teams'>"]
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
    h.append("</div>")
    order = ([focus] if focus in bodies else []) + [s for s in bodies if s != focus]
    h.extend(bodies[s] for s in order); h.append("</body></html>")
    progress(96, 'writing the page')
    open(out_path, 'w', encoding='utf-8').write('\n'.join(h))
    progress(100, 'done')
    return stats, team_wins


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('demo'); ap.add_argument('--player', default='76561198063294402'); ap.add_argument('--out', default=None)
    a = ap.parse_args()
    out = a.out or os.path.splitext(os.path.basename(a.demo))[0] + '_performance.html'
    global _EXPECTED
    MR.PROGRESS = progress
    mb = os.path.getsize(a.demo) / 1e6
    progress(1, f'starting ({mb:.0f} MB demo)')
    D = parse(a.demo, a.player)
    _EXPECTED = expected_seconds(len(D['fz']), mb)
    progress(32, f"{len(D['fz'])} rounds; expected total about {_EXPECTED:.0f} s")
    stats, team_wins = build(D, out, os.path.basename(a.demo), focus=a.player)
    remember_timing(len(D['fz']), mb, time.time() - _T0)
    print(f"built in {time.time() - _T0:.0f} s")
    print(f"{D['map']}: started-CT {team_wins[3]} rounds, started-T {team_wins[2]} rounds -> {out}")
    for sid, st in sorted(stats.items(), key=lambda kv: (-kv[1]['team'], -kv[1]['avg'])):
        print(f"  {'CT' if st['team'] == 3 else 'T '} {st['name']:<16} avg impact/round {st['avg']:+6.1f}  net {st['net']:+5d}")

if __name__ == '__main__':
    main()
