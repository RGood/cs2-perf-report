"""Performance report: one page, one metric. Mistakes count as negative impact, good plays as positive impact,
and the page carries an overall net impact score for the game.

Usage:
    python performance_report.py <demo.dem> [--player 76561198063294402] [--out report.html]
"""
import sys, os, argparse, collections as C
import mistake_report as MR
import impact_report as IR
from mistake_report import parse, make_map, b64

CSS = """
body{font-family:Segoe UI,Arial,sans-serif;background:#111318;color:#e6e6e6;margin:0;padding:24px;max-width:1500px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:20px;margin:40px 0 10px;padding-bottom:6px;border-bottom:2px solid #333}
h3{font-size:17px;margin:28px 0 8px;border-bottom:1px solid #2a2e3a;padding-bottom:5px}
.score{display:grid;grid-template-columns:1.2fr 1fr 1fr;gap:16px;margin:18px 0}
.box{background:#171a22;border:1px solid #2a2e3a;border-radius:10px;padding:14px 16px}
.box .big{font-size:34px;font-weight:700}.box .mid{font-size:26px;font-weight:700}.box small{color:#999}
.strip{display:flex;flex-wrap:wrap;gap:4px;margin:10px 0 4px}
.rd{width:50px;background:#1d2130;border:1px solid #333;border-radius:6px;padding:4px 0;text-align:center;font-size:11px}
.rd .n{font-weight:700;font-size:12px}.rd .w{color:#8fd18f}.rd .l{color:#ff7a7a}.rd .net{font-weight:700;font-size:11px}
.rd .dots{display:flex;justify-content:center;gap:2px;margin-top:3px;min-height:8px}.dot{width:7px;height:7px;border-radius:50%}
.sum{display:flex;flex-wrap:wrap;gap:10px;margin:12px 0}.chip{background:#1d2130;border:1px solid #333;border-radius:8px;padding:8px 12px;min-width:150px}
.chip b{font-size:20px;display:block}.chip .v{font-weight:700}a.chip{color:inherit;text-decoration:none;cursor:pointer}a.chip:hover{border-color:#666;background:#232838}
html{scroll-behavior:smooth}h3{scroll-margin-top:12px}
.why{background:#1a1d26;padding:10px 14px;margin:6px 0 14px;font-size:14px}
.card{display:grid;grid-template-columns:560px 1fr;gap:18px;background:#171a22;border:1px solid #2a2e3a;border-radius:10px;padding:14px;margin:12px 0}
.card img{width:560px;height:560px;border-radius:6px}.facts{font-size:14px;line-height:1.5}
.k{font-weight:600}.badge{display:inline-block;color:#fff;font-weight:700;padding:4px 10px;border-radius:6px;margin-bottom:6px}
.br{font-size:12px;color:#aaa;margin-bottom:10px}.lost{color:#ff7a7a}.won{color:#8fd18f}small{color:#999}
.two{display:grid;grid-template-columns:1fr 1fr;gap:24px}
ol{margin:6px 0 0 18px;padding:0}li{margin:3px 0}
.summary{font-size:15px;line-height:1.6;background:#171a22;border:1px solid #2a2e3a;border-radius:10px;padding:14px 18px;margin:16px 0 4px}
"""


def css_for(v):
    """Colour for a signed impact value: red gradient below zero, green above, neutral at zero."""
    return MR.sev_css(-v) if v < 0 else IR.imp_css(v)


def anchor(key):
    return f"cat-{key[0]}-{key[1]}"


def category(h, key, ms, rules, bases, proj, zthr, draw, label_why, label_do, accent):
    ms = sorted(ms, key=lambda m: (m['impact'], m['round'], m['time'] or 0))   # lowest impact first
    tot = sum(m['impact'] for m in ms)
    title, why, do = rules[key[1]]
    h.append(f"<h3 id='{anchor(key)}'>{title} ({len(ms)}, impact {tot:+d})</h3><div class='why' style='border-left:4px solid {accent}'><b>{label_why}:</b> {why}<br><b>{label_do}:</b> {do}</div>")
    for m in ms:
        lower = bases['lower'] is not None and zthr is not None and m.get('z') is not None and m['z'] < zthr
        img = draw(bases['lower'] if lower else bases['upper'], proj, m)
        res = '' if m.get('won') is None else ("<span class='won'>Round won</span>" if m['won'] else "<span class='lost'>Round lost</span>")
        v = m['impact']; css = css_for(v)
        note = f"<div class='br'>{m['util_note']}</div>" if m.get('util_note') else ''
        h.append(f"<div class='card' style='border-left:8px solid {css}'><img src='data:image/png;base64,{b64(img)}'><div class='facts'>"
                 f"<div class='badge' style='background:{css}'>Impact {v:+d}</div><div class='br'>{' &middot; '.join(m['imp_breakdown'])}</div>"
                 f"<div class='k' style='color:{accent}'>What happened</div>{m['facts']}<br>{res}{note}"
                 f"<div class='k' style='color:{accent};margin-top:12px'>{label_why}</div>{why}<div class='k' style='color:{accent};margin-top:12px'>{label_do}</div>{do}</div></div>")


def ranked(items, rules, title, positive):
    grouped = {}
    for m in items:
        g = grouped.setdefault((m['round'], m['time']), dict(v=0, m=m, kinds=[])); g['v'] += m['impact']; g['kinds'].append(rules[m['kind']][0])
    top = sorted(grouped.values(), key=lambda g: -g['v'] if positive else g['v'])[:6]
    return f"<div class='box'><b>{title}</b><ol>" + ''.join(f"<li><span style='color:{css_for(g['v'])};font-weight:700'>{g['v']:+d}</span> &nbsp; R{g['m']['round']} {g['m']['side']} {g['m']['time']}s{(' at ' + g['m']['place']) if g['m'].get('place') else ''}: {'; '.join(g['kinds'])}</li>" for g in top) + "</ol></div>"



def summary(name, mapname, rounds, wins, losses, net, pos, neg, mistakes, plays, cat, allrules, by_round):
    """One paragraph on the player's overall impact, built from the report's own numbers."""
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
    if pos_cats:
        s.append("The positive side was driven by " + " and ".join(catstr(k) for k in pos_cats) + ".")
    if neg_cats:
        s.append("The biggest costs were " + " and ".join(catstr(k) for k in neg_cats) + ".")
    ct, t = side_net['CT'], side_net['T']
    if side_n['CT'] and side_n['T']:
        stronger = 'CT' if ct / side_n['CT'] > t / side_n['T'] else 'T'
        s.append(f"By side, {ct / side_n['CT']:+.0f} per round on CT and {t / side_n['T']:+.0f} per round on T, so the {stronger} half carried the game.")
    if best is not None and worst is not None and best != worst:
        s.append(f"The best round was R{best} ({rnet[best]:+d}) and the worst was R{worst} ({rnet[worst]:+d}); {quiet} rounds produced nothing either way.")
    if neg_cats:
        s.append(f"Removing the {allrules[neg_cats[0]][0].lower()} flags alone would have moved the average to {(net - sum(cat[neg_cats[0]])) / n:+.1f} per round.")
    return ' '.join(s)

def build(D, mistakes, plays, out_path, demo_name):
    bases, proj, zthr = make_map(D)
    for m in mistakes:
        sev, br = MR.severity(m); m['severity'] = sev; m['impact'] = -sev; m['imp_breakdown'] = br + [f"= severity {sev}, counted as impact {-sev:+d}"]
    for m in plays:
        v, br = IR.impact(m); m['impact'] = v; m['imp_breakdown'] = br + [f"= impact {v:+d}"]
    for m in mistakes:
        pass
    # draw_card in mistake_report reads m['severity'] for its title bar; impact_report reads m['impact'] (positive). Both set above.
    name = D['snap'][D['snap']['steamid'] == D['me']]['name'].iloc[0] if (D['snap']['steamid'] == D['me']).any() else D['me']
    snap = D['snap']; fz = D['fz']
    rounds = []
    for rn in sorted(fz):
        g = snap[(snap['tick'] == fz[rn]) & (snap['steamid'] == D['me'])]
        if not len(g): continue
        side = 'CT' if int(g.iloc[0]['team_num']) == 3 else 'T'
        w = D['winner'].get(rn); rounds.append((rn + 1, side, (w == side) if w in ('CT', 'T') else None))
    wins = sum(1 for r in rounds if r[2]); losses = sum(1 for r in rounds if r[2] is False)
    neg = sum(m['impact'] for m in mistakes); pos = sum(m['impact'] for m in plays); net = pos + neg
    everything = mistakes + plays
    by_round = C.defaultdict(list)
    for m in everything: by_round[m['round']].append(m['impact'])
    # combined categories
    allrules = {**{('m', k): v for k, v in MR.RULES.items()}, **{('p', k): v for k, v in IR.RULES.items()}}
    cat = C.defaultdict(list)
    for m in mistakes: cat[('m', m['kind'])].append(m['impact'])
    for m in plays: cat[('p', m['kind'])].append(m['impact'])
    cat_order = sorted(cat, key=lambda k: sum(cat[k]))   # lowest (most negative) first: improvements before accolades

    h = [f"<!doctype html><html><head><meta charset='utf-8'><title>Performance report {D['map']}</title><style>{CSS}</style></head><body>",
         f"<h1>Performance report: {name} on {D['map']}</h1><small>{demo_name}. {len(rounds)} rounds, {wins}-{losses}. One metric: impact. Good plays count positive, mistakes count negative, and every number shows its arithmetic.</small>",
         f"<p class='summary'>{summary(name, D['map'], rounds, wins, losses, net, pos, neg, mistakes, plays, cat, allrules, by_round)}</p>",
         "<div class='score'>",
         f"<div class='box' style='border-left:8px solid {css_for(80 if net >= 0 else -80)}'><small>Average impact per round</small><div class='big' style='color:{css_for(90 if net >= 0 else -90)}'>{net / max(len(rounds), 1):+.1f}</div><small>net {net:+d} over {len(rounds)} rounds: {pos:+d} from {len(plays)} plays, {neg:+d} from {len(mistakes)} mistakes</small></div>",
         f"<div class='box' style='border-left:8px solid {IR.imp_css(70)}'><small>Things to keep doing</small><div class='mid'>{len(plays)}</div><small>impact {pos:+d}, average {round(pos / len(plays)) if plays else 0:+d}</small></div>",
         f"<div class='box' style='border-left:8px solid {MR.sev_css(70)}'><small>Things to improve</small><div class='mid'>{len(mistakes)}</div><small>impact {neg:+d}, average {round(neg / len(mistakes)) if mistakes else 0:+d}</small></div>",
         "</div>",
         "<div class='box'><b>Round by round</b> <small>net impact per round; green dots = plays, red dots = mistakes, shade follows the value</small><div class='strip'>"]
    for rn, side, won in rounds:
        res = "<span class='w'>W</span>" if won else ("<span class='l'>L</span>" if won is False else "-")
        vals = sorted(by_round[rn], key=lambda v: -abs(v)); rnet = sum(vals)
        dots = ''.join(f"<span class='dot' style='background:{css_for(v)}'></span>" for v in vals[:8])
        h.append(f"<div class='rd'><div class='n'>R{rn}</div>{side} {res}<div class='net' style='color:{css_for(rnet) if rnet else '#999'}'>{rnet:+d}</div><div class='dots'>{dots}</div></div>")
    h.append("</div></div>")
    h.append("<div class='sum'>")
    for key in cat_order:
        vals = cat[key]; t = sum(vals); a = round(t / len(vals))
        h.append(f"<a class='chip' href='#{anchor(key)}' style='border-left:6px solid {css_for(a)}'><b>{len(vals)}</b>{allrules[key][0]}<br><small>impact <span class='v' style='color:{css_for(t)}'>{t:+d}</span> &middot; avg {a:+d}</small></a>")
    h.append("</div>")
    h.append("<div class='two'>" + ranked(mistakes, MR.RULES, 'Biggest negative moments', False) + ranked(plays, IR.RULES, 'Biggest positive moments', True) + "</div>")
    items_by_key = C.defaultdict(list)
    for m in mistakes: items_by_key[('m', m['kind'])].append(m)
    for m in plays: items_by_key[('p', m['kind'])].append(m)
    shown = set()
    for key in cat_order:
        if key[0] == 'm' and 'm' not in shown:
            shown.add('m'); h.append(f"<h2 style='border-color:{MR.sev_css(80)}'>Things to improve ({len(mistakes)}, impact {neg:+d})</h2>")
        if key[0] == 'p' and 'p' not in shown:
            shown.add('p'); h.append(f"<h2 style='border-color:{IR.imp_css(80)}'>Things to keep doing ({len(plays)}, impact {pos:+d})</h2>")
        if key[0] == 'm':
            category(h, key, items_by_key[key], MR.RULES, bases, proj, zthr, MR.draw_card, 'Why it is a mistake', 'What to do instead', MR.sev_css(80))
        else:
            category(h, key, items_by_key[key], IR.RULES, bases, proj, zthr, IR.draw_card, 'Why it worked', 'Keep doing', IR.imp_css(80))
    h.append("</body></html>")
    open(out_path, 'w', encoding='utf-8').write('\n'.join(h))
    return net, pos, neg


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('demo'); ap.add_argument('--player', default='76561198063294402'); ap.add_argument('--out', default=None)
    a = ap.parse_args()
    out = a.out or os.path.splitext(os.path.basename(a.demo))[0] + '_performance.html'
    D = parse(a.demo, a.player)
    mistakes = MR.detect(D); plays = IR.detect(D)
    net, pos, neg = build(D, mistakes, plays, out, os.path.basename(a.demo))
    print(f"{D['map']}: average impact per round {net / max(len(D['fz']), 1):+.1f} (net {net:+d}: {pos:+d} from {len(plays)} plays, {neg:+d} from {len(mistakes)} mistakes) -> {out}")
    for k, n in C.Counter(m['kind'] for m in plays).most_common(): print(f"  + {IR.RULES[k][0]}: {n}")
    for k, n in C.Counter(m['kind'] for m in mistakes).most_common(): print(f"  - {MR.RULES[k][0]}: {n}")

if __name__ == '__main__':
    main()
