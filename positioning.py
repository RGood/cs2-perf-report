"""Positioning flags: fights taken on the enemy's terms, and holds that could not matter.

Negative: died in a crossfire, swung into a held angle, seen first then fought anyway, fought at their range,
held an empty site, absent from the hit.  Positive: held the angle, rotated on info.
All use demo visibility (approximate_spotted_by), velocity, facing, weapons and team-wide spotting.
"""
import math
import pandas as pd
import numpy as np
TICK = 64
M = 0.0254

RULES_NEG = {
    'crossfire': ("Died in a crossfire",
        "Two or more enemies had you in view from different angles in the last 2 s. You can only aim at one of them, so the fight was theirs before it started.",
        "Clear one angle at a time. If a second enemy can see the spot you are about to stand in, it is not a spot, it is a lane."),
    'swung_into_hold': ("Swung into a held angle",
        "When you and the killer first saw each other, you were moving and they were stationary with their crosshair already on you. That is the peeker's disadvantage against a set enemy.",
        "Either make them move first (utility, a teammate's peek, sound) or hold your own angle and let them swing you."),
    'seen_first': ("Seen first, fought anyway",
        "The killer had you in view for 1.5 s or more before you had them. They knew where you were; you did not know where they were, and you took the fight anyway.",
        "When you are spotted without seeing anyone, break the line first. Reposition, then take the fight from a spot they have not pre-aimed."),
    'their_range': ("Fought at their range",
        "You moved into a fight at a distance that favoured their weapon: an SMG or pistol against a rifle past 20 m, or a rifle against an AWP past 35 m.",
        "Close the distance behind cover or utility before the fight, or make them come to your range. Do not peek a rifle at 25 m with an MP9."),
    'empty_site': ("Held an empty site",
        "Your team had three or more enemies spotted far from you for six seconds and you stayed put. The information said the round was elsewhere.",
        "When the team has three spotted at the other site, your site is no longer the round. Move toward the fight, or at least to where the retake starts."),
    'absent_hit': ("Absent from the hit",
        "Three teammates hit a site and two of them died while you were 40 m or more away with no damage and no kill afterwards. A lurk that never pays off is one player short on the execute.",
        "A lurk has to produce something: a kill on the rotation, a late flank, or a plant. If none of that is coming, be on the site when the team goes."),
}
RULES_POS = {
    'held_angle': ("Held the angle",
        "The enemy swung into you while you were set and already aiming at their entry. You won a fight that was yours on the numbers.",
        "Keep letting them come to your crosshair. Patience at a good angle wins more duels than any amount of aim."),
    'rotated_on_info': ("Rotated on info",
        "Your team spotted enemies away from you, and you moved toward them within a few seconds. You put yourself where the round was.",
        "Keep reacting to the team's information. The first player to arrive at the real fight is usually the one who decides it."),
}
BASE_NEG = {'crossfire': 36, 'swung_into_hold': 38, 'seen_first': 34, 'their_range': 32, 'empty_site': 38, 'absent_hit': 38}
BASE_POS = {'held_angle': 25, 'rotated_on_info': 30}

PISTOLS = ('glock', 'usp', 'p2000', 'p250', 'five', 'tec', 'cz75', 'deagle', 'desert', 'revolver', 'r8', 'elite', 'dual')
SMGS = ('mp9', 'mp7', 'mp5', 'mac', 'ump', 'p90', 'bizon')
SNIPERS = ('awp', 'ssg', 'scar', 'g3sg1')
RIFLES = ('ak', 'm4', 'galil', 'famas', 'aug', 'sg 5', 'sg55')


def wclass(name):
    n = (name or '').lower().replace('weapon_', '').replace('-', '').replace(' ', '').replace('_', '')
    n = {'deserteagle': 'deagle', 'r8revolver': 'revolver', 'dualberettas': 'elite'}.get(n, n)
    for cls, keys in (('sniper', SNIPERS), ('rifle', RIFLES), ('smg', SMGS), ('pistol', PISTOLS)):
        if any(k in n for k in keys): return cls
    return 'other'


def ang(a, b):
    return abs((a - b + 180) % 360 - 180)


def bearing(frm, to):
    return math.degrees(math.atan2(to[1] - frm[1], to[0] - frm[0]))


def prepare(D):
    from mistake_report import by_tick_of
    by_tick = by_tick_of(D)
    if '_coarse_ticks' not in D:
        D['_coarse_ticks'] = sorted(by_tick)
    first = int(D['_coarse_ticks'][0]); ticks = D['_coarse_ticks']
    def coarse(tk):
        c = tk - ((tk - first) % 8)
        return c if c in by_tick else max([x for x in ticks if x <= tk], default=first)
    return by_tick, coarse


def me_and_foes(tab, t, me, team):
    """From the compact table at tick t: my index and a mask of alive enemies. Returns (i, mask) or (None, None)."""
    r = tab.get(t)
    if r is None: return None, None
    idx = np.where(r['sid'] == me)[0]
    if not len(idx): return None, None
    return int(idx[0]), (r['team'] != team) & r['alive']


def speed(tab, c, sid):
    """Horizontal speed in units/s from the position change over the previous coarse tick (8 ticks = 0.125 s)."""
    r = tab.get(c); q = tab.get(c - 8)
    if r is None or q is None: return 0.0
    i = np.where(r['sid'] == sid)[0]; j = np.where(q['sid'] == sid)[0]
    if not len(i) or not len(j): return 0.0
    return float(math.hypot(r['X'][i[0]] - q['X'][j[0]], r['Y'][i[0]] - q['Y'][j[0]]) / 0.125)


def row(g, sid):
    r = g[g['steamid'] == sid]
    return r.iloc[0] if len(r) else None


def sees(r, sid):
    try:
        return sid in [str(x) for x in r['approximate_spotted_by']]
    except TypeError:
        return False


def _base(rn, side, won, t, rt, place, pos):
    return dict(round=rn + 1, side=side, won=won, time=rt(t, rn), z=None, place=place, pos=pos, near=None, path=[], mate_path=[], killer_path=[], victim_path=[],
                mates_alive=None, foes_alive=None, nades_thrown=[], order=None, dmg_round=None, equip=None)


def negatives(D, me):
    from mistake_report import ticktab_of
    by_tick, coarse = prepare(D); tab = ticktab_of(D)
    deaths = D['deaths']; hurt = D['hurt']; fire = D['gunfire']; fz = D['fz']; snap = D['snap']
    mine = snap[snap['steamid'] == me].set_index('tick')
    rt = lambda tick, rn: round((tick - fz[rn]) / TICK, 1) if rn in fz else None
    out = []
    mypath = lambda t: [(r.X, r.Y) for r in mine[(mine.index >= t - 12 * TICK) & (mine.index <= t)].itertuples()]

    # ---------------- death-based: crossfire, swung into hold, seen first, their range
    for d in deaths[deaths['user_steamid'] == me].itertuples():
        rn = int(d.total_rounds_played); t = int(d.tick)
        if rn not in fz or t < fz[rn]: continue
        team = int(d.user_team_num); side = 'CT' if team == 3 else 'T'; won = D['winner'].get(rn) == side
        if team not in (2, 3): continue
        K = str(d.attacker_steamid)
        if K in ('nan', 'None', '') or K == me: continue
        mypos = (d.user_X, d.user_Y); kpos = (d.attacker_X, d.attacker_Y)
        base = _base(rn, side, won, t, rt, d.user_last_place_name, mypos)
        base.update(path=mypath(t), killer=str(d.attacker_name), kpos=kpos, dist=round(float(d.distance), 1) if pd.notna(d.distance) else 0)
        shots = int(((fire['total_rounds_played'] == rn) & (fire['user_steamid'] == me) & (fire['tick'] >= t - 4 * TICK) & (fire['tick'] <= t)).sum())
        # scan the last 3 s
        seen_by = {}; first_mutual = None; k_saw_me_from = None; i_saw_k_from = None
        for ct in range(coarse(t - 3 * TICK), t + 1, 8):
            g = by_tick.get(ct)
            if g is None: continue
            mr = row(g, me); kr = row(g, K)
            if mr is None: continue
            try:
                for e in mr['approximate_spotted_by']:
                    seen_by.setdefault(str(e), ct)
            except TypeError:
                pass
            if kr is not None:
                k_sees = sees(mr, K); i_see = sees(kr, me)
                if k_sees and k_saw_me_from is None: k_saw_me_from = ct
                if i_see and i_saw_k_from is None: i_saw_k_from = ct
                if k_sees and i_see and first_mutual is None: first_mutual = (ct, mr, kr)
        # crossfire: >= 2 enemies saw me in the last 2 s from bearings >= 45 deg apart
        recent = [e for e, ct in seen_by.items() if ct >= t - 2 * TICK and e != me]
        if len(recent) >= 2:
            g = by_tick.get(coarse(t - 1)); brs = {}; opps = []
            for e in recent:
                er = row(g, e) if g is not None else None
                if er is not None and int(er['team_num']) != team: brs[str(er['name'])] = bearing(mypos, (er.X, er.Y)); opps.append((str(er['name']), (er.X, er.Y)))
            names = list(brs)
            spread = max((ang(brs[a], brs[b]) for a in names for b in names if a < b), default=0)
            if len(names) >= 2 and spread >= 45:
                out.append(dict(base, kind='crossfire', facts=f"Round {rn+1}, {side}, {rt(t, rn)} s. Died at {d.user_last_place_name} to {d.attacker_name}. In the last 2 s {', '.join(names)} all had you in view, from angles {spread:.0f}° apart. You fired {shots} shots.", spread=spread, n_seen=len(names), opponents=opps))
        # swung into a held angle
        if first_mutual is not None:
            ct, mr, kr = first_mutual
            dist = math.dist((mr.X, mr.Y), (kr.X, kr.Y)) * M
            my_v = speed(tab, ct, me); k_v = speed(tab, ct, K)
            k_aim = ang(float(kr['yaw']), bearing((kr.X, kr.Y), (mr.X, mr.Y)))
            if my_v > 120 and k_v < 30 and k_aim <= 20 and dist >= 8:
                out.append(dict(base, kind='swung_into_hold', facts=f"Round {rn+1}, {side}, {rt(t, rn)} s. At {rt(ct, rn)} s you and {d.attacker_name} first saw each other at {dist:.0f} m: you were moving at {my_v:.0f} u/s, they were stationary at {d.attacker_last_place_name} with their crosshair {k_aim:.0f}° off you. You died {(t - ct) / TICK:.1f} s later.", k_aim=k_aim, my_v=my_v))
        # seen first, fought anyway
        lead = ((i_saw_k_from if i_saw_k_from is not None else t) - k_saw_me_from) / TICK if k_saw_me_from is not None else 0
        if k_saw_me_from is not None and lead >= 1.5 and shots > 0:
            out.append(dict(base, kind='seen_first', facts=f"Round {rn+1}, {side}, {rt(t, rn)} s. {d.attacker_name} had you in view from {rt(k_saw_me_from, rn)} s, {lead:.1f} s before you had them" + (f" at {rt(i_saw_k_from, rn)} s" if i_saw_k_from else " (you never did)") + f". You stayed and fired {shots} shots, and died at {d.user_last_place_name} from {float(d.distance):.0f} m.", lead=lead))
        # fought at their range (only when I moved into view)
        mc = wclass(d.user_active_weapon_name); kc = wclass(d.weapon)
        dist = float(d.distance) if pd.notna(d.distance) else 0
        moving_in = first_mutual is not None and speed(tab, first_mutual[0], me) > 100
        if moving_in and ((mc in ('smg', 'pistol') and kc in ('rifle', 'sniper') and dist >= 20) or (mc == 'rifle' and kc == 'sniper' and dist >= 35)):
            out.append(dict(base, kind='their_range', facts=f"Round {rn+1}, {side}, {rt(t, rn)} s. You moved into view with a {d.user_active_weapon_name} against {d.attacker_name}'s {d.weapon} at {dist:.0f} m and lost. That distance is theirs.", dist_m=dist))

    # ---------------- round-based: held an empty site (CT), absent from the hit (T)
    for rn, ft in fz.items():
        g0 = by_tick.get(ft)
        if g0 is None or row(g0, me) is None: continue
        team = int(row(g0, me)['team_num']); side = 'CT' if team == 3 else 'T'; won = D['winner'].get(rn) == side
        if team not in (2, 3): continue
        rd = deaths[deaths['total_rounds_played'] == rn]
        mydeath = rd[rd['user_steamid'] == me]; t_end = int(mydeath['tick'].min()) if len(mydeath) else int(D.get('round_end', {}).get(rn, ft + 115 * TICK))
        h_me = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me)]
        if side == 'CT':
            run = 0; start_ct = None
            for ct in range(ft + 15 * TICK, t_end, 16):
                c = coarse(ct); i, foes = me_and_foes(tab, c, me, team)
                if i is None: continue
                r = tab[c]
                if not r['alive'][i]: break
                dist = np.hypot(r['X'] - r['X'][i], r['Y'] - r['Y'][i]) * M
                far = foes & r['spotted'] & (dist >= 40); near = int((foes & (dist < 30)).sum())
                if far.sum() >= 3 and near == 0:
                    if run == 0:
                        start_ct = c; start_pos = (r['X'][i], r['Y'][i]); far_centroid = (float(r['X'][far].mean()), float(r['Y'][far].mean())); far_place = r['place'][far][0]; start_place = r['place'][i]; n_far = int(far.sum())
                    run += 16
                    if run >= 6 * TICK:
                        c2 = coarse(min(start_ct + 10 * TICK, t_end - 1)); i2, _ = me_and_foes(tab, c2, me, team)
                        moved = (math.dist(start_pos, far_centroid) - math.dist((tab[c2]['X'][i2], tab[c2]['Y'][i2]), far_centroid)) * M if i2 is not None else 0
                        dmg = int(h_me[h_me['tick'] <= start_ct + 15 * TICK]['dmg_health'].clip(upper=100).sum())
                        if moved < 10 and dmg == 0 and not won:
                            base = _base(rn, side, won, start_ct, rt, start_place, start_pos); base.update(path=mypath(start_ct + 10 * TICK), extra_pos=far_centroid, extra_label='enemies spotted here')
                            out.append(dict(base, kind='empty_site', facts=f"Round {rn+1}, CT. From {rt(start_ct, rn)} s your team had {n_far} enemies spotted about {math.dist(start_pos, far_centroid) * M:.0f} m away near {far_place}, for at least 6 s, with nobody near you at {start_place}. Over the next 10 s you closed {max(moved, 0):.0f} m toward them and did no damage. Round lost.", n_far=n_far))
                        break
                else:
                    run = 0
        else:
            # T: cluster of >= 3 teammates within 25 m of each other, >= 2 of them die within 10 s, me >= 40 m away
            mates_deaths = rd[(rd['user_team_num'] == team) & (rd['user_steamid'] != me)].sort_values('tick')
            for i in range(len(mates_deaths) - 1):
                d1 = mates_deaths.iloc[i]; d2 = mates_deaths.iloc[i + 1]
                if int(d2['tick']) - int(d1['tick']) > 10 * TICK: continue
                t1 = int(d1['tick']); g = by_tick.get(coarse(t1 - 8))
                if g is None: continue
                mr = row(g, me)
                if mr is None or not bool(mr['is_alive']): continue
                mates = g[(g['team_num'] == team) & (g['steamid'] != me) & (g['is_alive'] == True)]
                if len(mates) < 3: continue
                cx, cy = mates['X'].mean(), mates['Y'].mean()
                if max(math.dist((cx, cy), (m.X, m.Y)) * M for m in mates.itertuples()) > 25: continue
                my_d = math.dist((mr.X, mr.Y), (cx, cy)) * M
                if my_d < 40: continue
                dmg = int(h_me[h_me['tick'] <= int(d2['tick'])]['dmg_health'].clip(upper=100).sum())
                later_kill = bool(((rd['attacker_steamid'] == me) & (rd['tick'] > t1) & (rd['tick'] <= t1 + 15 * TICK)).any())
                if dmg == 0 and not later_kill:
                    base = _base(rn, side, won, t1, rt, mr['last_place_name'], (mr.X, mr.Y)); base.update(path=mypath(t1), extra_pos=(cx, cy), extra_label='the hit')
                    out.append(dict(base, kind='absent_hit', facts=f"Round {rn+1}, T, {rt(t1, rn)} s. Three teammates were together near {d1['user_last_place_name']} and {d1['user_name']} and {d2['user_name']} died within {(int(d2['tick']) - t1) / TICK:.0f} s of each other. You were {my_d:.0f} m away at {mr['last_place_name']} with no damage in the round and no kill in the next 15 s.", my_d=my_d))
                    break
    return out


def positives(D, me):
    from mistake_report import ticktab_of
    by_tick, coarse = prepare(D); tab = ticktab_of(D)
    deaths = D['deaths']; hurt = D['hurt']; fz = D['fz']; snap = D['snap']
    mine = snap[snap['steamid'] == me].set_index('tick')
    rt = lambda tick, rn: round((tick - fz[rn]) / TICK, 1) if rn in fz else None
    out = []
    mypath = lambda t: [(r.X, r.Y) for r in mine[(mine.index >= t - 12 * TICK) & (mine.index <= t)].itertuples()]
    # held the angle: my kill where at first mutual visibility the victim was moving and I was set and aimed
    for d in deaths[deaths['attacker_steamid'] == me].itertuples():
        rn = int(d.total_rounds_played); t = int(d.tick)
        if rn not in fz or t < fz[rn]: continue
        team = int(d.attacker_team_num); side = 'CT' if team == 3 else 'T'; won = D['winner'].get(rn) == side
        if team not in (2, 3): continue
        V = str(d.user_steamid)
        fm = None
        for ct in range(coarse(t - 3 * TICK), t + 1, 8):
            g = by_tick.get(ct)
            if g is None: continue
            mr = row(g, me); vr = row(g, V)
            if mr is None or vr is None: continue
            if sees(mr, V) and sees(vr, me): fm = (ct, mr, vr); break
        if fm is None: continue
        ct, mr, vr = fm
        dist = math.dist((mr.X, mr.Y), (vr.X, vr.Y)) * M
        my_v = speed(tab, ct, me); v_v = speed(tab, ct, V); my_aim = ang(float(mr['yaw']), bearing((mr.X, mr.Y), (vr.X, vr.Y)))
        if v_v > 120 and my_v < 30 and my_aim <= 20 and dist >= 8:
            base = _base(rn, side, won, t, rt, d.attacker_last_place_name, (d.attacker_X, d.attacker_Y)); base.update(path=mypath(t), victim=str(d.user_name), vpos=(d.user_X, d.user_Y))
            out.append(dict(base, kind='held_angle', facts=f"Round {rn+1}, {side}, {rt(t, rn)} s. {d.user_name} swung into you at {d.attacker_last_place_name} from {dist:.0f} m while you were stationary with your crosshair {my_aim:.0f}° off their entry. Killed {(t - ct) / TICK:.1f} s after first sight.", headshot=bool(d.headshot)))
    # rotated on info (CT): team spots >= 3 enemies >= 40 m away; I close >= 20 m toward them within 8 s
    for rn, ft in fz.items():
        g0 = by_tick.get(ft)
        if g0 is None or row(g0, me) is None: continue
        team = int(row(g0, me)['team_num']); side = 'CT' if team == 3 else 'T'; won = D['winner'].get(rn) == side
        if team not in (2, 3): continue
        if side != 'CT': continue
        rd = deaths[deaths['total_rounds_played'] == rn]; mydeath = rd[rd['user_steamid'] == me]
        t_end = int(mydeath['tick'].min()) if len(mydeath) else int(D.get('round_end', {}).get(rn, ft + 115 * TICK))
        for ct in range(ft + 10 * TICK, t_end - 8 * TICK, 32):
            c = coarse(ct); i, foes = me_and_foes(tab, c, me, team)
            if i is None: continue
            r = tab[c]
            if not r['alive'][i]: break
            dist = np.hypot(r['X'] - r['X'][i], r['Y'] - r['Y'][i]) * M
            far = foes & r['spotted'] & (dist >= 40)
            if far.sum() < 3: continue
            cen = (float(r['X'][far].mean()), float(r['Y'][far].mean())); mypos0 = (r['X'][i], r['Y'][i])
            c2 = coarse(min(ct + 8 * TICK, t_end - 1)); i2, _ = me_and_foes(tab, c2, me, team)
            if i2 is None: continue
            p2 = (tab[c2]['X'][i2], tab[c2]['Y'][i2])
            closed = (math.dist(mypos0, cen) - math.dist(p2, cen)) * M
            if closed >= 20:
                h = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me) & (hurt['tick'] >= ct)]
                dmg = int(h['dmg_health'].clip(upper=100).sum())
                base = _base(rn, side, won, ct + 8 * TICK, rt, tab[c2]['place'][i2], p2); base.update(path=mypath(ct + 8 * TICK), extra_pos=cen, extra_label='enemies spotted here')
                out.append(dict(base, kind='rotated_on_info', facts=f"Round {rn+1}, CT, {rt(ct, rn)} s. Your team had {int(far.sum())} enemies spotted about {math.dist(mypos0, cen) * M:.0f} m from you near {r['place'][far][0]}. Within 8 s you closed {closed:.0f} m toward them" + (f" and did {dmg} damage afterwards." if dmg else "."), dmg=dmg))
                break
    return out
