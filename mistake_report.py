"""Mistake report: parse a CS2 demo, flag one player's mistakes with rules, draw each on a map, write an HTML report.

Usage:
    python mistake_report.py <demo.dem> [--player 76561198063294402] [--out report.html]

The map background is built from the demo itself (every player position in the match), so no radar files are needed.
Requires: pip install demoparser2 pandas numpy pillow
"""
import sys, os, math, json, base64, argparse, collections as C
from io import BytesIO
import numpy as np, pandas as pd
from PIL import Image, ImageDraw, ImageFont
from demoparser2 import DemoParser

TICK = 64
M = 0.0254  # units -> metres
CONT_GAP = 10   # ticks (~0.16 s): shots closer together than this are one continuous run (AK/M4 cycle ~6-7 ticks)
SPRAY_RUN = 7   # a continuous run this long or longer is a spray; shorter runs are bursts
SAFE_WINDOW = 1.5  # seconds after contact during which no enemy could engage you, needed before a held grenade counts as usable

# ----------------------------------------------------------------------------- rules text
RULES = {
    'util_unused': ("Died with usable utility",
        "Only counted when three things were true after contact: there was time (2 s for a flash or HE with the killer inside 30 m, 4 s for a smoke or molotov), there was a safe throw window of at least 1.5 s in which no nearby enemy was visible to your team, you were not visible to theirs, and you were not being hit, and the grenade would have done something. If the enemy could engage you the whole time, throwing would have been the mistake, and the grenade is not counted.",
        "Once contact is called and you are delaying, the usable grenades go out in the first seconds, not after the fight is lost. Flash the choke, HE the stack, molotov the entrance, then fight."),
    'util_too_early': ("Utility thrown too early",
        "A smoke or molotov thrown with no enemy within 30 m, none spotted by your team, and usually before the T side could even reach that choke. Later in the same round you were in contact for 4 s or more with no delay grenade left. The throw was on the clock, not on information.",
        "Hold the delay grenade until one of these exists: enemies seen or heard at the choke, a teammate's call, or the enemy's timing from earlier rounds. Before the earliest possible T arrival at that choke, nothing you throw is reacting to anything."),
    'separated_from_team': ("Isolated before dying",
        "In the 10 s before this death you and your nearest teammate moved apart, with two or more teammates still alive. This is the avoidable kind of untraded death: the gap was created by movement, not by the round state.",
        "When you move, move toward or with a teammate. If you have to go alone, go for a delay or information, not a duel."),
    'held_alone': ("Died anchoring",
        "Sometimes unavoidable: the anchor dies when three players hit the site. It still costs the round when it happens early, without damage, or without a call.",
        "Delay rather than duel: utility first, fall back to a crossfire spot, call the rotate at the first sound, and make them spend time on you."),
    'spray_at_range': ("Long-distance spray missed",
        "Only counted when the shots in the 4 s before the death include a continuous run of 7 or more at the weapon's cycle rate, at 20 m or more, with 20 damage or less to the killer. Bursts and taps are a different flag.",
        "Past 20 m fire 2 to 3 bullets, stop, counter-strafe, fire again. Never more than 4 without a reset."),
    'missed_at_range': ("Bursts missed at range",
        "You fired in bursts or taps, which is the right pattern, and still did 20 damage or less at 20 m or more. That is not spray control. It is the first bullets of each burst missing: crosshair placement before the peek, or the burst starting before the crosshair is on the target.",
        "Crosshair at head height on the exact corner before you swing it. Start the burst only when the crosshair is on the body, not while it is still moving. Yprac prefire and far-wall one-taps target this."),
    'kill_then_die': ("Traded by enemy",
        "After a kill everyone knows where you are, and the next enemy is already aiming at that spot. Re-peeking or staying is the deadliest 50-50 in the game.",
        "After every kill, move at least one position before the next fight. Take the trade only if a teammate is already swinging with you."),
    'early_solo_contact': ("Early solo T contact",
        "Contact before 20 s with nobody near you means the CT is set up and you are not. You had dealt no damage, so the round started a man down with no information.",
        "No contact in the first 20 s unless the team's utility has landed and a teammate is on your shoulder."),
    'lost_opener_ct': ("Lost CT opener",
        "First death of the round on CT hands the T side a numbers advantage before they have committed anywhere. It is the most expensive death in the round.",
        "Hold passive angles in the first 30 s with a teammate covering you. Take information from utility, not from a peek."),
    'died_blind': ("Died flashed",
        "A blinded player is a free kill. Either you pushed through a flash you saw coming, or a teammate blinded you.",
        "When a flash is thrown at your position, turn away and hold the corner. Call 'flashing' before your own throws and do not walk into teammates' flashes."),
    'eco_wander': ("Alone on eco",
        "On a pistol or eco round your value is the exit kill or the weapon pickup, and both need the group. Alone you die for nothing.",
        "Stack with the team on a save. Play for the exit kill together, or hide and save the pistol and armor."),
    'util_on_timer': ("Utility on a timer",
        "The same grenade from the same spot at the same second every round tells the enemy where you stand and when the choke is covered. They time their push to it.",
        "Throw on sound and on information, not on the clock. Some rounds throw nothing before 20 s and hold the angle instead."),
    'zero_impact_full_buy': ("Full buy, zero impact",
        "A full buy that ends with no damage and no grenades thrown is the most expensive possible round. The money was spent and nothing was bought with it.",
        "If the round is going badly, your grenades still have value: throw them for a teammate or for the retake. Get damage in before you die."),
}

# ----------------------------------------------------------------------------- parsing
def parse(path, me):
    p = DemoParser(path)
    mapname = p.parse_header().get('map_name', '?')
    ms = p.parse_event("round_announce_match_start")
    start = int(ms['tick'].max()) if len(ms) else 0

    def ev(name, **kw):
        d = p.parse_event(name, other=["total_rounds_played"], **kw)
        d = d[d['tick'] >= start].copy()
        for c in d.columns:
            if c.endswith('steamid'):
                d[c] = d[c].astype(str)
        return d

    freeze = ev("round_freeze_end"); rend = ev("round_end")
    fz = {int(r.total_rounds_played): int(r.tick) for r in freeze.itertuples()}
    winner = {int(r.total_rounds_played) - 1: r.winner for r in rend.itertuples()}
    deaths = ev("player_death", player=["X", "Y", "Z", "last_place_name", "team_num", "flash_duration", "active_weapon_name"]).sort_values('tick')
    hurt = ev("player_hurt")
    fire = ev("weapon_fire", player=["X", "Y", "last_place_name"])
    blind = ev("player_blind", player=["team_num"])
    plant = ev("bomb_planted", player=["X", "Y"])
    nade_re = 'grenade|molotov|flashbang|incgrenade|decoy'
    is_nade = fire['weapon'].str.contains(nade_re, na=False)
    all_nades = fire[is_nade]
    nades = all_nades[all_nades['user_steamid'] == me]
    gunfire = fire[~is_nade & ~fire['weapon'].str.contains('knife', na=False)]

    # coarse ticks for silhouette and paths (every 8 ticks), exact ticks for death snapshots
    death_ticks = [int(t) - 1 for t in deaths['tick']]
    coarse = list(range(start, int(deaths['tick'].max()) + 1, 8))
    nade_ticks = [int(t) for t in all_nades['tick']]
    snap = p.parse_ticks(["X", "Y", "is_alive", "team_num", "last_place_name", "inventory", "current_equip_value", "spotted"], ticks=sorted(set(coarse + death_ticks + nade_ticks + list(fz.values()))))
    snap['steamid'] = snap['steamid'].astype(str)
    round_end = {int(r.total_rounds_played) - 1: int(r.tick) for r in rend.itertuples()}
    return dict(map=mapname, fz=fz, winner=winner, round_end=round_end, deaths=deaths, hurt=hurt, gunfire=gunfire, nades=nades, all_nades=all_nades, blind=blind, plant=plant, snap=snap, me=me)


def for_player(D, sid):
    """Return a shallow copy of a parsed demo focused on another player (same snapshot, their grenades)."""
    E = dict(D); E['me'] = str(sid); E['nades'] = D['all_nades'][D['all_nades']['user_steamid'] == str(sid)]
    return E

# ----------------------------------------------------------------------------- mistake detection
def nade_list(inv):
    try:
        return [x for x in inv if any(k in str(x) for k in ('Grenade', 'Molotov', 'Incendiary', 'Flashbang', 'Smoke', 'Decoy'))]
    except TypeError:
        return []

def detect(D):
    me = D['me']; fz = D['fz']; deaths = D['deaths']; snap = D['snap']
    by_tick = {t: g for t, g in snap.groupby('tick')}
    mine = snap[snap['steamid'] == me].set_index('tick')
    out = []
    rt = lambda tick, rn: round((tick - fz[rn]) / TICK, 1) if rn in fz else None

    for d in deaths[deaths['user_steamid'] == me].itertuples():
        rn = int(d.total_rounds_played); t = int(d.tick); tsec = rt(t, rn)
        if tsec is None or tsec < 0: continue
        s = by_tick.get(t - 1)
        if s is None: continue
        team = int(d.user_team_num); side = 'CT' if team == 3 else 'T'
        me_row = s[s['steamid'] == me]
        me_row = me_row.iloc[0] if len(me_row) else None
        mates = s[(s['team_num'] == team) & (s['steamid'] != me) & (s['is_alive'] == True)]
        pos = (d.user_X, d.user_Y); kpos = (d.attacker_X, d.attacker_Y) if pd.notna(d.attacker_X) else None
        md = sorted([(math.dist(pos, (m.X, m.Y)) * M, m.name, (m.X, m.Y), m.last_place_name) for m in mates.itertuples()])
        near = md[0] if md else None
        later = deaths[(deaths['tick'] > t) & (deaths['tick'] <= t + 5 * TICK) & (deaths['user_steamid'] == d.attacker_steamid) & (deaths['total_rounds_played'] == rn)]
        traded = bool(len(later)) and bool((later['attacker_team_num'] == team).any())
        h = D['hurt'][(D['hurt']['total_rounds_played'] == rn) & (D['hurt']['attacker_steamid'] == me) & (D['hurt']['tick'] <= t)]
        dmg_round = int(h['dmg_health'].clip(upper=100).sum()); dmg_k = int(h[h['user_steamid'] == d.attacker_steamid]['dmg_health'].clip(upper=100).sum())
        shots = int(((D['gunfire']['total_rounds_played'] == rn) & (D['gunfire']['user_steamid'] == me) & (D['gunfire']['tick'] <= t)).sum())
        g4 = D['gunfire'][(D['gunfire']['total_rounds_played'] == rn) & (D['gunfire']['user_steamid'] == me) & (D['gunfire']['tick'] <= t) & (D['gunfire']['tick'] >= t - 4 * TICK)]
        shots4 = int(len(g4)); dmg_k4 = int(h[(h['user_steamid'] == d.attacker_steamid) & (h['tick'] >= t - 4 * TICK)]['dmg_health'].clip(upper=100).sum())
        hits4 = int(len(h[h['tick'] >= t - 4 * TICK]))
        tk = sorted(int(x) for x in g4['tick']); runs = []
        for x in tk:
            if runs and x - runs[-1][-1] <= CONT_GAP: runs[-1].append(x)
            else: runs.append([x])
        run_lens = [len(r) for r in runs]; longest = max(run_lens) if run_lens else 0
        pattern = 'no shots' if not run_lens else ('a continuous spray of ' + str(longest) if longest >= SPRAY_RUN else ('bursts of ' + ', '.join(map(str, run_lens)) if longest >= 2 else str(len(run_lens)) + ' single taps'))
        c10 = t - 640; c10 = c10 - ((c10 - int(min(by_tick))) % 8)
        s10 = by_tick.get(c10); moved10 = None; mate10 = None
        if s10 is not None and (s10['steamid'] == me).any():
            m10 = s10[s10['steamid'] == me].iloc[0]; moved10 = math.dist(pos, (m10.X, m10.Y)) * M
            mm = s10[(s10['team_num'] == team) & (s10['steamid'] != me) & (s10['is_alive'] == True)]
            md10 = [math.dist((m10.X, m10.Y), (x.X, x.Y)) * M for x in mm.itertuples()]; mate10 = min(md10) if md10 else None
        rd = deaths[deaths['total_rounds_played'] == rn]
        order = int((rd['tick'] < t).sum()) + 1
        held = nade_list(me_row['inventory']) if me_row is not None else []
        # contact: first tick in the last 15 s with an enemy within 25 m of me (coarse ticks)
        contact = None; foes_peak = 0
        hurt_me_ticks = set(int(x) for x in D['hurt'][(D['hurt']['total_rounds_played'] == rn) & (D['hurt']['user_steamid'] == me)]['tick'])
        safe_run = 0; best_safe = 0; best_safe_end = None
        for ct in range(t - 15 * TICK, t, 8):
            g = by_tick.get(ct)
            if g is None: continue
            mr = g[g['steamid'] == me]
            if not len(mr): continue
            mp = (mr.iloc[0].X, mr.iloc[0].Y)
            foes_near = [f for f in g[(g['team_num'] != team) & (g['is_alive'] == True)].itertuples() if math.dist(mp, (f.X, f.Y)) * M < 25]
            n = len(foes_near)
            if n and contact is None: contact = ct
            foes_peak = max(foes_peak, n)
            if contact is not None:
                # a safe throw moment: nobody near is visible to my team, I am not visible to theirs, and I am not being hit
                me_seen = bool(mr.iloc[0]['spotted']); near_seen = any(bool(f.spotted) for f in foes_near)
                being_hit = any(h in hurt_me_ticks for h in range(ct - 8, ct + 1))
                if not me_seen and not near_seen and not being_hit:
                    safe_run += 1
                    if safe_run > best_safe: best_safe = safe_run; best_safe_end = ct
                else:
                    safe_run = 0
        after = (t - contact) / TICK if contact else 0.0
        safe_s = best_safe * 8 / TICK
        kd_m = float(d.distance) if pd.notna(d.distance) else 0
        usable = [n for n in held if after >= 2 and safe_s >= SAFE_WINDOW and ((('Flash' in n or 'High Explosive' in n) and kd_m <= 30) or (('Smoke' in n or 'Molotov' in n or 'Incendiary' in n) and after >= 4))]
        # my throws this round with signals at the throw
        throw_info = []
        thrown = D['nades'][(D['nades']['total_rounds_played'] == rn) & (D['nades']['tick'] <= t)]
        for r in thrown.itertuples():
            g = by_tick.get(int(r.tick)); nr = None; sp = None
            if g is not None:
                foes = g[(g['team_num'] != team) & (g['is_alive'] == True)]
                nr = sum(1 for f in foes.itertuples() if math.dist((r.user_X, r.user_Y), (f.X, f.Y)) * M < 30); sp = int(foes['spotted'].astype(bool).sum())
            throw_info.append(dict(t=rt(int(r.tick), rn), nade=r.weapon.replace('weapon_', ''), place=r.user_last_place_name, near=nr, spotted=sp,
                                   blind=(nr == 0 and sp == 0), pre=(contact is None or r.tick < contact)))
        equip = int(me_row['current_equip_value']) if me_row is not None else 0
        dist = float(d.distance) if pd.notna(d.distance) else 0
        # path: my positions in the last 12 s
        pt = mine[(mine.index >= t - 12 * TICK) & (mine.index <= t - 1)]
        path = [(r.X, r.Y) for r in pt.itertuples()]
        def path_of(sid):
            if sid is None: return []
            q = snap[(snap['steamid'] == str(sid)) & (snap['tick'] >= t - 12 * TICK) & (snap['tick'] <= t - 1) & (snap['is_alive'] == True)].sort_values('tick')
            return [(r.X, r.Y) for r in q.itertuples()]
        killer_path = path_of(d.attacker_steamid) if pd.notna(d.attacker_steamid) else []
        mate_sid = None
        if md:
            mrow = mates[mates['name'] == md[0][1]]
            mate_sid = mrow.iloc[0]['steamid'] if len(mrow) else None
        mate_path = path_of(mate_sid)
        thrown = D['nades'][(D['nades']['total_rounds_played'] == rn) & (D['nades']['tick'] <= t)]
        base = dict(round=rn + 1, side=side, time=tsec, z=float(d.user_Z) if pd.notna(d.user_Z) else None, order=order, dmg_round=dmg_round, equip=equip, after=after, foes_peak=foes_peak, moved10=moved10, n_usable=len(usable), place=d.user_last_place_name, pos=pos, killer=d.attacker_name, kpos=kpos, kplace=d.attacker_last_place_name,
                    weapon=d.weapon, my_weapon=d.user_active_weapon_name, dist=round(dist, 1), near=near, path=path, killer_path=killer_path, mate_path=mate_path, mates_alive=len(mates),
                    nades_thrown=[(r.weapon.replace('weapon_', ''), (r.user_X, r.user_Y)) for r in thrown.itertuples()], won=D['winner'].get(rn) == side)
        facts = f"Round {rn+1}, {side}, {tsec}s. Died at {d.user_last_place_name} to {d.attacker_name} ({d.weapon}) from {d.attacker_last_place_name}, {dist:.0f} m."
        if near: facts += f" Nearest teammate {near[1]} was {near[0]:.0f} m away at {near[3]}."
        facts += f" In the 4 s before you died you fired {shots4} shots as {pattern}, {hits4} of them hit anyone, and you did {dmg_k4} damage to your killer ({shots} shots, {dmg_k} damage over the whole round)."

        if usable and tsec > 10:
            win_end = rt(best_safe_end, rn) if best_safe_end else None
            out.append(dict(base, kind='util_unused', facts=facts + f" Contact began {after:.0f} s before you died with up to {foes_peak} attackers within 25 m. In that time you had a {safe_s:.1f} s window ending at {win_end} s where no nearby enemy was visible to your team, you were not visible to theirs, and you were not being hit. Usable and unthrown: {', '.join(usable)}." + (f" Not counted (no time or out of range): {', '.join(n for n in held if n not in usable)}." if len(held) > len(usable) else "")))
        elif held and tsec > 10 and contact is not None and after >= 2 and safe_s < SAFE_WINDOW:
            base['util_note'] = f"Held {', '.join(held)} at death, not counted: from contact at {rt(contact, rn)} s the enemy could engage you the whole time (longest safe window {safe_s:.1f} s), so throwing would have been the mistake."
        early = [x for x in throw_info if x['blind'] and x['pre'] and x['nade'] in ('smokegrenade', 'molotov', 'incgrenade')]
        if early and after >= 4 and not any(('Smoke' in n or 'Molotov' in n or 'Incendiary' in n) for n in held):
            e = early[0]
            out.append(dict(base, kind='util_too_early', facts=facts + f" At {e['t']} s you threw a {e['nade']} from {e['place']} with no enemy within 30 m and none spotted by your team. Contact came at {rt(contact, rn)} s and lasted {after:.0f} s; you had no smoke or molotov left for it." + (f" Throws that did have a signal: " + '; '.join(f"{x['nade']} at {x['t']} s with {x['near']} enemies within 30 m" for x in throw_info if not x['blind']) + '.' if any(not x['blind'] for x in throw_info) else "")))
        if len(mates) >= 2 and near and near[0] > 15 and not traded:
            sep = (moved10 is not None and moved10 > 12) or (mate10 is not None and mate10 < 15)
            gap = f" {len(mates)} teammates alive, nearest {near[0]:.0f} m away, nobody traded you."
            if sep:
                ten = f" Ten seconds earlier you were {moved10:.0f} m from this spot" + (f" and the nearest teammate was {mate10:.0f} m away." if mate10 is not None else ".")
                out.append(dict(base, kind='separated_from_team', facts=facts + gap + ten))
            else:
                out.append(dict(base, kind='held_alone', facts=facts + gap + " You had been in this area for at least 10 s with no teammate within 15 m."))
        if shots4 >= 6 and dmg_k4 <= 20 and dist >= 20:
            out.append(dict(base, kind='spray_at_range' if longest >= SPRAY_RUN else 'missed_at_range', facts=facts + f" Longest continuous run: {longest} shots (spray threshold {SPRAY_RUN})."))
        mk = deaths[(deaths['attacker_steamid'] == me) & (deaths['total_rounds_played'] == rn) & (deaths['tick'] < t) & (deaths['tick'] >= t - 5 * TICK)]
        if len(mk):
            k = mk.iloc[-1]
            if pd.notna(k['attacker_X']) and math.dist(pos, (k['attacker_X'], k['attacker_Y'])) * M < 8:
                out.append(dict(base, kind='kill_then_die', facts=facts + f" You killed {k['user_name']} {round((t - k['tick']) / TICK, 1)} s earlier from within 8 m of where you died.", extra_pos=(k['user_X'], k['user_Y'])))
        if side == 'T' and tsec < 20 and near and near[0] > 10 and dmg_round == 0:
            out.append(dict(base, kind='early_solo_contact', facts=facts))
        if side == 'CT' and order == 1 and tsec < 30:
            out.append(dict(base, kind='lost_opener_ct', facts=facts + " This was the first death of the round."))
        if d.user_flash_duration and d.user_flash_duration > 0:
            b = D['blind'][(D['blind']['total_rounds_played'] == rn) & (D['blind']['user_steamid'] == me) & (D['blind']['tick'] <= t) & (D['blind']['tick'] >= t - 6 * TICK)]
            who = 'unknown'
            if len(b):
                bb = b.iloc[-1]; who = f"{bb['attacker_name']} ({'teammate' if int(bb['attacker_team_num']) == team else 'enemy'})" if 'attacker_team_num' in b.columns and pd.notna(bb.get('attacker_team_num')) else str(bb['attacker_name'])
            out.append(dict(base, kind='died_blind', facts=facts + f" You had {d.user_flash_duration:.1f} s of flash left. Flashed by {who}."))
        if equip < 1500 and near and near[0] > 25:
            out.append(dict(base, kind='eco_wander', facts=facts + f" Equipment value ${equip}."))

    # per-round: full buy, zero damage, zero nades thrown, died
    for rn, ft in fz.items():
        s = by_tick.get(ft)
        if s is None: continue
        r = s[s['steamid'] == me]
        if not len(r): continue
        r = r.iloc[0]; team = int(r['team_num']); side = 'CT' if team == 3 else 'T'
        h = D['hurt'][(D['hurt']['total_rounds_played'] == rn) & (D['hurt']['attacker_steamid'] == me)]
        thrown = D['nades'][D['nades']['total_rounds_played'] == rn]
        died = deaths[(deaths['total_rounds_played'] == rn) & (deaths['user_steamid'] == me)]
        if int(r['current_equip_value']) >= 3700 and int(h['dmg_health'].sum()) == 0 and not len(thrown) and len(died):
            dd = died.iloc[0]
            out.append(dict(round=rn + 1, side=side, time=rt(int(dd['tick']), rn), z=float(dd['user_Z']), place=dd['user_last_place_name'], pos=(dd['user_X'], dd['user_Y']), killer=dd['attacker_name'],
                            kpos=(dd['attacker_X'], dd['attacker_Y']), kplace=dd['attacker_last_place_name'], weapon=dd['weapon'], my_weapon=dd['user_active_weapon_name'], dist=0, near=None,
                            path=[(x.X, x.Y) for x in mine[(mine.index >= ft) & (mine.index <= int(dd['tick']))].itertuples()][::4], mates_alive=None, nades_thrown=[], won=D['winner'].get(rn) == side,
                            kind='zero_impact_full_buy', facts=f"Round {rn+1}, {side}. Equipment ${int(r['current_equip_value'])}, {len(nade_list(r['inventory']))} grenades bought, none thrown, 0 damage, died at {dd['user_last_place_name']} at {rt(int(dd['tick']), rn)} s."))

    # utility on a timer: same nade type + place + side, within 1.5 s spread, in >= 4 rounds
    groups = C.defaultdict(list)
    for r in D['nades'].itertuples():
        rn = int(r.total_rounds_played)
        if rn not in fz: continue
        s = by_tick.get(fz[rn]); side = None
        if s is not None:
            m = s[s['steamid'] == me]
            if len(m): side = 'CT' if int(m.iloc[0]['team_num']) == 3 else 'T'
        groups[(side, r.weapon.replace('weapon_', ''), r.user_last_place_name)].append((rn + 1, rt(int(r.tick), rn), (r.user_X, r.user_Y)))
    for (side, w, place), items in groups.items():
        times = [x[1] for x in items if x[1] is not None and x[1] > 0]
        if len(items) >= 4 and len(times) >= 4 and (max(times) - min(times)) <= 3.0:
            out.append(dict(round=items[0][0], side=side, time=round(float(np.mean(times)), 1), place=place, pos=items[0][2], killer=None, kpos=None, kplace=None, weapon=None, my_weapon=None, dist=0, near=None,
                            path=[], mates_alive=None, nades_thrown=[(w, x[2]) for x in items], won=None, kind='util_on_timer', repeats=len(items),
                            facts=f"{side} side: {w} thrown from {place} in {len(items)} rounds ({', '.join('R'+str(x[0]) for x in items)}) at {min(times)} to {max(times)} s every time."))
    return out

# ----------------------------------------------------------------------------- severity
BASE_SEVERITY = {
    'zero_impact_full_buy': 55, 'lost_opener_ct': 55, 'separated_from_team': 50, 'early_solo_contact': 50,
    'kill_then_die': 42, 'util_too_early': 42, 'util_unused': 38, 'spray_at_range': 38, 'died_blind': 36, 'util_on_timer': 38,
    'missed_at_range': 33, 'held_alone': 32, 'eco_wander': 28,
}

def severity(m):
    """0-100. Base weight for the mistake type, then context modifiers. Returns (score, breakdown list)."""
    k = m['kind']; score = BASE_SEVERITY.get(k, 40); br = [f"base {score} for this mistake type"]
    def add(v, why):
        nonlocal score
        if v:
            score += v; br.append(f"{v:+d} {why}")
    if m.get('won') is False: add(10, 'round lost')
    elif m.get('won') is True: add(-10, 'round won anyway')
    ma = m.get('mates_alive')
    if ma is not None and k != 'util_on_timer':
        add({4: 10, 3: 7, 2: 3}.get(ma, 0), f'{ma} teammates still alive')
    if m.get('order') == 1: add(8, 'first death of the round')
    if m.get('dmg_round') == 0 and k not in ('util_on_timer', 'zero_impact_full_buy'): add(8, 'no damage dealt that round')
    eq = m.get('equip')
    if eq is not None and k not in ('eco_wander', 'util_on_timer'):
        if eq >= 3700: add(6, 'full buy lost')
        elif eq < 1500: add(-8, 'eco round')
    if k == 'util_unused':
        add(min(8, 4 * (m.get('n_usable', 1) - 1)), 'more than one usable grenade held')
        add(4 if (m.get('after') or 0) >= 8 else 0, '8 s or more of contact to use it')
    if k == 'separated_from_team' and m.get('moved10'): add(min(8, int(m['moved10'] // 4)), f"moved {m['moved10']:.0f} m away in the last 10 s")
    if k == 'util_on_timer': add(min(16, 4 * (m.get('repeats', 4) - 4)), f"repeated in {m.get('repeats')} rounds")
    if k in ('spray_at_range', 'missed_at_range', 'held_alone') and (m.get('foes_peak') or 0) >= 3: add(-5, 'outnumbered 3+ at the time')
    score = max(0, min(100, score))
    return score, br

def sev_rgb(score):
    a = (60, 64, 78); b = (225, 55, 55); f = max(0.0, min(1.0, score / 100.0))
    return tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3))

def sev_css(score):
    r, g, b = sev_rgb(score); return f"rgb({r},{g},{b})"

# ----------------------------------------------------------------------------- drawing
def make_map(D, size=900):
    """Returns (bases, proj, threshold_z). bases = {'upper': img, 'lower': img or None}.
    Uses the map's radar image + the game's overview offsets when tools/maps/<map>.png exists; otherwise a silhouette built from the demo."""
    here = os.path.dirname(os.path.abspath(__file__)); mdir = os.path.join(here, 'maps')
    offs = {}
    if os.path.exists(os.path.join(mdir, 'offsets.json')):
        offs = json.load(open(os.path.join(mdir, 'offsets.json')))
    snap = D['snap']
    pts = snap[snap['is_alive'] == True][['X', 'Y', 'last_place_name']].dropna()
    name = D['map']
    if name in offs and os.path.exists(os.path.join(mdir, name + '.png')):
        o = offs[name]; k = size / 1024.0
        def proj(x, y):
            return (int((x - o['pos_x']) / o['scale'] * k), int((o['pos_y'] - y) / o['scale'] * k))
        def load(fn):
            im = Image.open(fn).convert('RGB').resize((size, size), Image.LANCZOS)
            return Image.eval(im, lambda v: int(v * 0.72))
        bases = {'upper': load(os.path.join(mdir, name + '.png')),
                 'lower': load(os.path.join(mdir, name + '_lower.png')) if os.path.exists(os.path.join(mdir, name + '_lower.png')) else None}
        zthr = o.get('threshold_z') if bases['lower'] is not None else None
        font = _font(11)
        for key, im in bases.items():
            if im is None: continue
            d2 = ImageDraw.Draw(im)
            for place, g in pts.groupby('last_place_name'):
                if len(g) < 200 or not place: continue
                px, py = proj(g['X'].median(), g['Y'].median())
                d2.text((px + 1, py + 1), str(place), fill=(0, 0, 0), font=font, anchor='mm')
                d2.text((px, py), str(place), fill=(225, 228, 235), font=font, anchor='mm')
        return bases, proj, zthr
    # fallback: silhouette from the demo's own positions
    xmin, xmax = pts['X'].quantile(0.002), pts['X'].quantile(0.998); ymin, ymax = pts['Y'].quantile(0.002), pts['Y'].quantile(0.998)
    pad = 0.04 * max(xmax - xmin, ymax - ymin)
    xmin -= pad; xmax += pad; ymin -= pad; ymax += pad
    span = max(xmax - xmin, ymax - ymin)
    def proj(x, y):
        return (int((x - xmin) / span * size), int((ymax - y) / span * size))
    img = Image.new('RGB', (size, size), (18, 20, 24))
    layer = Image.new('RGBA', (size, size), (0, 0, 0, 0)); dr = ImageDraw.Draw(layer)
    sub = pts.iloc[::3]
    for x, y in zip(sub['X'].values, sub['Y'].values):
        px, py = proj(x, y); dr.ellipse((px - 2, py - 2, px + 2, py + 2), fill=(120, 130, 150, 28))
    img.paste(layer, (0, 0), layer)
    font = _font(13)
    d2 = ImageDraw.Draw(img)
    for place, g in pts.groupby('last_place_name'):
        if len(g) < 200 or not place: continue
        px, py = proj(g['X'].median(), g['Y'].median())
        d2.text((px, py), str(place), fill=(170, 175, 185), font=font, anchor='mm')
    return {'upper': img, 'lower': None}, proj, None

def _font(sz):
    for f in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, sz)
    return ImageFont.load_default()

def draw_card(base, proj, m):
    img = base.copy(); d = ImageDraw.Draw(img); font = _font(15); small = _font(12)
    # killer and nearest-teammate paths, last 12 s, fading toward the death tick
    for key, col in (('killer_path', (255, 170, 60)), ('mate_path', (80, 140, 255))):
        pp = m.get(key) or []
        if len(pp) > 1:
            pts = [proj(*p) for p in pp]
            for i in range(1, len(pts)):
                f = 0.25 + 0.75 * i / len(pts)
                d.line([pts[i - 1], pts[i]], fill=tuple(int(c * f) for c in col), width=3)
            sx, sy = pts[0]; d.ellipse((sx - 3, sy - 3, sx + 3, sy + 3), outline=col, width=1)
    # path
    if len(m['path']) > 1:
        pts = [proj(*p) for p in m['path']]
        for i in range(1, len(pts)):
            a = int(60 + 195 * i / len(pts))
            d.line([pts[i - 1], pts[i]], fill=(a, 60, 60), width=3)
    for w, p in m['nades_thrown']:
        px, py = proj(*p); col = {'flashbang': (250, 240, 120), 'smokegrenade': (200, 200, 200), 'hegrenade': (240, 140, 60), 'molotov': (255, 90, 30), 'incgrenade': (255, 90, 30)}.get(w, (200, 200, 200))
        d.ellipse((px - 5, py - 5, px + 5, py + 5), outline=col, width=2)
    if m.get('near'):
        px, py = proj(*m['near'][2]); mx, my = proj(*m['pos'])
        d.line([(px, py), (mx, my)], fill=(80, 140, 255), width=1)
        d.ellipse((px - 7, py - 7, px + 7, py + 7), fill=(80, 140, 255))
        d.text((px + 10, py - 8), f"{m['near'][1]} {m['near'][0]:.0f}m", fill=(150, 190, 255), font=small)
    if m.get('kpos') and m['kpos'][0] is not None and not (isinstance(m['kpos'][0], float) and math.isnan(m['kpos'][0])):
        kx, ky = proj(*m['kpos']); mx, my = proj(*m['pos'])
        d.line([(kx, ky), (mx, my)], fill=(255, 170, 60), width=1)
        d.polygon([(kx, ky - 9), (kx - 8, ky + 6), (kx + 8, ky + 6)], fill=(255, 170, 60))
        d.text((kx + 10, ky - 8), f"{m['killer']}", fill=(255, 200, 120), font=small)
    if m.get('extra_pos'):
        ex, ey = proj(*m['extra_pos']); d.ellipse((ex - 6, ey - 6, ex + 6, ey + 6), outline=(120, 255, 120), width=2); d.text((ex + 9, ey - 8), "your kill", fill=(140, 255, 140), font=small)
    mx, my = proj(*m['pos'])
    d.line([(mx - 9, my - 9), (mx + 9, my + 9)], fill=(255, 60, 60), width=4); d.line([(mx - 9, my + 9), (mx + 9, my - 9)], fill=(255, 60, 60), width=4)
    d.text((mx + 12, my + 4), "you", fill=(255, 120, 120), font=small)
    title = f"R{m['round']} {m['side']} {m['time']}s  |  {RULES[m['kind']][0]}"
    sc = m.get('severity', 0); col = sev_rgb(sc)
    d.rectangle((0, 0, img.width, 28), fill=tuple(int(c * 0.55) for c in col)); d.rectangle((0, 0, 8, 28), fill=col)
    label = f"impact {m['impact']:+d}" if 'impact' in m else f"severity {sc}"
    d.text((16, 6), f"{title}   {label}", fill=(255, 255, 255), font=font)
    d.text((10, img.height - 22), "red X you   orange killer   blue nearest teammate   trails = last 12 s, small ring = start   rings your grenades", fill=(140, 140, 150), font=small)
    return img

def b64(img):
    buf = BytesIO(); img.convert('RGB').save(buf, format='PNG', optimize=True); return base64.b64encode(buf.getvalue()).decode()

# ----------------------------------------------------------------------------- report
def report(D, mistakes, out_path, demo_name):
    bases, proj, zthr = make_map(D)
    order = ['separated_from_team', 'held_alone', 'util_unused', 'util_too_early', 'spray_at_range', 'missed_at_range', 'kill_then_die', 'early_solo_contact', 'lost_opener_ct', 'died_blind', 'eco_wander', 'util_on_timer', 'zero_impact_full_buy']
    for m in mistakes:
        m['severity'], m['sev_breakdown'] = severity(m)
    counts = C.Counter(m['kind'] for m in mistakes)
    totsev = {k: sum(m['severity'] for m in mistakes if m['kind'] == k) for k in counts}
    avgsev = {k: round(totsev[k] / counts[k]) for k in counts}
    order = sorted(counts, key=lambda k: -totsev[k])   # categories by cumulative severity, highest first
    name = D['snap'][D['snap']['steamid'] == D['me']]['name'].iloc[0] if (D['snap']['steamid'] == D['me']).any() else D['me']
    h = [f"<!doctype html><html><head><meta charset='utf-8'><title>Mistake report {D['map']}</title><style>"
         "body{font-family:Segoe UI,Arial,sans-serif;background:#111318;color:#e6e6e6;margin:0;padding:24px;max-width:1500px}"
         "h1{font-size:22px;margin:0 0 4px}h2{font-size:18px;margin:36px 0 8px;border-bottom:1px solid #333;padding-bottom:6px}"
         ".sum{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}.chip{background:#1d2130;border:1px solid #333;border-radius:8px;padding:8px 12px}"
         ".chip b{font-size:20px;display:block}.why{background:#1a1d26;border-left:4px solid #e0a040;padding:10px 14px;margin:6px 0 14px;font-size:14px}"
         ".card{display:grid;grid-template-columns:560px 1fr;gap:18px;background:#171a22;border:1px solid #2a2e3a;border-radius:10px;padding:14px;margin:12px 0}"
         ".card img{width:560px;height:560px;border-radius:6px}.facts{font-size:14px;line-height:1.5}.facts .k{color:#e0a040;font-weight:600}.facts .f{color:#8fd18f;font-weight:600}"
         ".lost{color:#ff7a7a}.won{color:#8fd18f}small{color:#999}"
         ".sev{display:inline-block;color:#fff;font-weight:700;padding:4px 10px;border-radius:6px;margin-bottom:6px}.sevbr{font-size:12px;color:#aaa;margin-bottom:10px}</style></head><body>",
         f"<h1>Mistake report: {name} on {D['map']}</h1><small>{demo_name}. {len(mistakes)} flags over {len(D['fz'])} rounds. Rules are heuristics; each card shows the data so you can judge it.</small>",
         "<div class='sum'>"]
    for k in order:
        if counts[k]: h.append(f"<div class='chip' style='border-left:6px solid {sev_css(avgsev[k])}'><b>{counts[k]}</b>{RULES[k][0]}<br><small>avg severity {avgsev[k]}</small></div>")
    h.append("</div>")
    grouped = {}
    for m in sorted(mistakes, key=lambda m: -m['severity']):
        key = (m['round'], m['time']); g = grouped.setdefault(key, dict(sev=m['severity'], m=m, kinds=[]))
        g['kinds'].append(RULES[m['kind']][0])
    top = sorted(grouped.values(), key=lambda g: -g['sev'])[:6]
    h.append("<h2>Most severe deaths</h2><ol>" + ''.join(f"<li><span style='color:{sev_css(g['sev'])};font-weight:700'>{g['sev']}</span> &nbsp; R{g['m']['round']} {g['m']['side']} {g['m']['time']}s at {g['m']['place']}: {'; '.join(g['kinds'])}</li>" for g in top) + "</ol>")
    for k in order:
        ms = sorted([m for m in mistakes if m['kind'] == k], key=lambda m: (-m['severity'], m['round'], m['time'] or 0))
        if not ms: continue
        title, why, fix = RULES[k]
        h.append(f"<h2>{title} ({len(ms)})</h2><div class='why'><b>Why it matters:</b> {why}<br><b>Do instead:</b> {fix}</div>")
        for m in ms:
            lower = bases['lower'] is not None and zthr is not None and m.get('z') is not None and m['z'] < zthr
            img = draw_card(bases['lower'] if lower else bases['upper'], proj, m)
            res = '' if m['won'] is None else (f"<span class='won'>Round won</span>" if m['won'] else f"<span class='lost'>Round lost</span>")
            sc = m['severity']; css = sev_css(sc)
            h.append(f"<div class='card' style='border-left:8px solid {css}'><img src='data:image/png;base64,{b64(img)}'><div class='facts'><div class='sev' style='background:{css}'>Severity {sc} / 100</div><div class='sevbr'>{' &middot; '.join(m['sev_breakdown'])}</div><div class='k'>What happened</div>{m['facts']}<br>{res}"
                     f"<div class='k' style='margin-top:12px'>Why it is a mistake</div>{why}<div class='f' style='margin-top:12px'>What to do instead</div>{fix}</div></div>")
    h.append("</body></html>")
    open(out_path, 'w', encoding='utf-8').write('\n'.join(h))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('demo'); ap.add_argument('--player', default='76561198063294402'); ap.add_argument('--out', default=None)
    a = ap.parse_args()
    out = a.out or os.path.splitext(os.path.basename(a.demo))[0] + '_mistakes.html'
    D = parse(a.demo, a.player)
    mistakes = detect(D)
    report(D, mistakes, out, os.path.basename(a.demo))
    print(f"{D['map']}: {len(mistakes)} flags -> {out}")
    for k, n in C.Counter(m['kind'] for m in mistakes).most_common(): print(f"  {RULES[k][0]}: {n}")

if __name__ == '__main__':
    main()
