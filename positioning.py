"""Positioning flags: fights taken on the enemy's terms, and holds that could not matter.

Negative: died in a crossfire, swung into a held angle, seen first then fought anyway, fought at their range,
held an empty site, absent from the hit.  Positive: held the angle, rotated on info.
All use demo visibility (approximate_spotted_by), velocity, facing, weapons and team-wide spotting.
"""
import math
import pandas as pd
from mistake_report import TICK, M

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
BASE_NEG = {'crossfire': 42, 'swung_into_hold': 45, 'seen_first': 40, 'their_range': 38, 'empty_site': 45, 'absent_hit': 42}
BASE_POS = {'held_angle': 40, 'rotated_on_info': 40}

PISTOLS = ('glock', 'usp', 'p2000', 'p250', 'five', 'tec', 'cz75', 'deagle', 'desert', 'revolver', 'r8', 'elite', 'dual')
SMGS = ('mp9', 'mp7', 'mp5', 'mac', 'ump', 'p90', 'bizon')
SNIPERS = ('awp', 'ssg', 'scar', 'g3sg1')
RIFLES = ('ak', 'm4', 'galil', 'famas', 'aug', 'sg 5', 'sg55')


def wclass(name):
    n = (name or '').lower()
    for cls, keys in (('sniper', SNIPERS), ('rifle', RIFLES), ('smg', SMGS), ('pistol', PISTOLS)):
        if any(k in n for k in keys): return cls
    return 'other'


def ang(a, b):
    return abs((a - b + 180) % 360 - 180)


def bearing(frm, to):
    return math.degrees(math.atan2(to[1] - frm[1], to[0] - frm[0]))


def prepare(D):
    snap = D['snap']
    by_tick = {t: g for t, g in snap.groupby('tick')}
    first = int(min(by_tick)); ticks = sorted(by_tick)
    def coarse(tk):
        c = tk - ((tk - first) % 8)
        return c if c in by_tick else max([x for x in ticks if x <= tk], default=first)
    return by_tick, coarse


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
    by_tick, coarse = prepare(D)
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
            g = by_tick.get(coarse(t - 1)); brs = {}
            for e in recent:
                er = row(g, e) if g is not None else None
                if er is not None and int(er['team_num']) != team: brs[str(er['name'])] = bearing(mypos, (er.X, er.Y))
            names = list(brs)
            spread = max((ang(brs[a], brs[b]) for a in names for b in names if a < b), default=0)
            if len(names) >= 2 and spread >= 45:
                out.append(dict(base, kind='crossfire', facts=f"Round {rn+1}, {side}, {rt(t, rn)} s. Died at {d.user_last_place_name} to {d.attacker_name}. In the last 2 s {', '.join(names)} all had you in view, from angles {spread:.0f}° apart. You fired {shots} shots.", spread=spread, n_seen=len(names)))
        # swung into a held angle
        if first_mutual is not None:
            ct, mr, kr = first_mutual
            dist = math.dist((mr.X, mr.Y), (kr.X, kr.Y)) * M
            my_v = float(mr['velocity'] or 0); k_v = float(kr['velocity'] or 0)
            k_aim = ang(float(kr['yaw']), bearing((kr.X, kr.Y), (mr.X, mr.Y)))
            if my_v > 120 and k_v < 30 and k_aim <= 20 and dist >= 8:
                out.append(dict(base, kind='swung_into_hold', facts=f"Round {rn+1}, {side}, {rt(t, rn)} s. At {rt(ct, rn)} s you and {d.attacker_name} first saw each other at {dist:.0f} m: you were moving at {my_v:.0f} u/s, they were stationary at {d.attacker_last_place_name} with their crosshair {k_aim:.0f}° off you. You died {(t - ct) / TICK:.1f} s later.", k_aim=k_aim, my_v=my_v))
        # seen first, fought anyway
        if k_saw_me_from is not None and (i_saw_k_from is None or i_saw_k_from - k_saw_me_from >= 1.5 * TICK) and shots > 0:
            lead = ((i_saw_k_from if i_saw_k_from is not None else t) - k_saw_me_from) / TICK
            out.append(dict(base, kind='seen_first', facts=f"Round {rn+1}, {side}, {rt(t, rn)} s. {d.attacker_name} had you in view from {rt(k_saw_me_from, rn)} s, {lead:.1f} s before you had them" + (f" at {rt(i_saw_k_from, rn)} s" if i_saw_k_from else " (you never did)") + f". You stayed and fired {shots} shots, and died at {d.user_last_place_name} from {float(d.distance):.0f} m.", lead=lead))
        # fought at their range (only when I moved into view)
        mc = wclass(d.user_active_weapon_name); kc = wclass(d.weapon)
        dist = float(d.distance) if pd.notna(d.distance) else 0
        moving_in = first_mutual is not None and float(first_mutual[1]['velocity'] or 0) > 100
        if moving_in and ((mc in ('smg', 'pistol') and kc in ('rifle', 'sniper') and dist >= 20) or (mc == 'rifle' and kc == 'sniper' and dist >= 35)):
            out.append(dict(base, kind='their_range', facts=f"Round {rn+1}, {side}, {rt(t, rn)} s. You moved into view with a {d.user_active_weapon_name} against {d.attacker_name}'s {d.weapon} at {dist:.0f} m and lost. That distance is theirs.", dist_m=dist))

    # ---------------- round-based: held an empty site (CT), absent from the hit (T)
    for rn, ft in fz.items():
        g0 = by_tick.get(ft)
        if g0 is None or row(g0, me) is None: continue
        team = int(row(g0, me)['team_num']); side = 'CT' if team == 3 else 'T'; won = D['winner'].get(rn) == side
        rd = deaths[deaths['total_rounds_played'] == rn]
        mydeath = rd[rd['user_steamid'] == me]; t_end = int(mydeath['tick'].min()) if len(mydeath) else int(D.get('round_end', {}).get(rn, ft + 115 * TICK))
        h_me = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me)]
        if side == 'CT':
            run = 0; start_ct = None; flagged = False
            for ct in range(ft + 15 * TICK, t_end, 16):
                g = by_tick.get(coarse(ct))
                if g is None: continue
                mr = row(g, me)
                if mr is None or not bool(mr['is_alive']): break
                foes = g[(g['team_num'] != team) & (g['is_alive'] == True) & (g['spotted'] == True)]
                far = [f for f in foes.itertuples() if math.dist((mr.X, mr.Y), (f.X, f.Y)) * M >= 40]
                near = sum(1 for f in g[(g['team_num'] != team) & (g['is_alive'] == True)].itertuples() if math.dist((mr.X, mr.Y), (f.X, f.Y)) * M < 30)
                if len(far) >= 3 and near == 0:
                    if run == 0: start_ct = ct; start_pos = (mr.X, mr.Y); far_centroid = (sum(f.X for f in far) / len(far), sum(f.Y for f in far) / len(far)); far_place = far[0].last_place_name
                    run += 16
                    if run >= 6 * TICK:
                        # did I move toward them within 10 s of the info starting?
                        g2 = by_tick.get(coarse(min(start_ct + 10 * TICK, t_end - 1)))
                        mr2 = row(g2, me) if g2 is not None else None
                        moved = (math.dist(start_pos, far_centroid) - math.dist((mr2.X, mr2.Y), far_centroid)) * M if mr2 is not None else 0
                        dmg = int(h_me[h_me['tick'] <= start_ct + 15 * TICK]['dmg_health'].clip(upper=100).sum())
                        if moved < 10 and dmg == 0 and not won:
                            base = _base(rn, side, won, start_ct, rt, mr['last_place_name'], start_pos); base.update(path=mypath(start_ct + 10 * TICK), extra_pos=far_centroid, extra_label='enemies spotted here')
                            out.append(dict(base, kind='empty_site', facts=f"Round {rn+1}, CT. From {rt(start_ct, rn)} s your team had {len(far)} enemies spotted about {math.dist(start_pos, far_centroid) * M:.0f} m away near {far_place}, for at least 6 s, with nobody near you at {mr['last_place_name']}. Over the next 10 s you closed {max(moved, 0):.0f} m toward them and did no damage. Round lost.", n_far=len(far)))
                            flagged = True; break
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
    by_tick, coarse = prepare(D)
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
        my_v = float(mr['velocity'] or 0); v_v = float(vr['velocity'] or 0); my_aim = ang(float(mr['yaw']), bearing((mr.X, mr.Y), (vr.X, vr.Y)))
        if v_v > 120 and my_v < 30 and my_aim <= 20 and dist >= 8:
            base = _base(rn, side, won, t, rt, d.attacker_last_place_name, (d.attacker_X, d.attacker_Y)); base.update(path=mypath(t), victim=str(d.user_name), vpos=(d.user_X, d.user_Y))
            out.append(dict(base, kind='held_angle', facts=f"Round {rn+1}, {side}, {rt(t, rn)} s. {d.user_name} swung into you at {d.attacker_last_place_name} from {dist:.0f} m while you were stationary with your crosshair {my_aim:.0f}° off their entry. Killed {(t - ct) / TICK:.1f} s after first sight.", headshot=bool(d.headshot)))
    # rotated on info (CT): team spots >= 3 enemies >= 40 m away; I close >= 20 m toward them within 8 s
    for rn, ft in fz.items():
        g0 = by_tick.get(ft)
        if g0 is None or row(g0, me) is None: continue
        team = int(row(g0, me)['team_num']); side = 'CT' if team == 3 else 'T'; won = D['winner'].get(rn) == side
        if side != 'CT': continue
        rd = deaths[deaths['total_rounds_played'] == rn]; mydeath = rd[rd['user_steamid'] == me]
        t_end = int(mydeath['tick'].min()) if len(mydeath) else int(D.get('round_end', {}).get(rn, ft + 115 * TICK))
        for ct in range(ft + 10 * TICK, t_end - 8 * TICK, 32):
            g = by_tick.get(coarse(ct))
            if g is None: continue
            mr = row(g, me)
            if mr is None or not bool(mr['is_alive']): break
            far = [f for f in g[(g['team_num'] != team) & (g['is_alive'] == True) & (g['spotted'] == True)].itertuples() if math.dist((mr.X, mr.Y), (f.X, f.Y)) * M >= 40]
            if len(far) < 3: continue
            cen = (sum(f.X for f in far) / len(far), sum(f.Y for f in far) / len(far))
            g2 = by_tick.get(coarse(min(ct + 8 * TICK, t_end - 1))); mr2 = row(g2, me) if g2 is not None else None
            if mr2 is None: continue
            closed = (math.dist((mr.X, mr.Y), cen) - math.dist((mr2.X, mr2.Y), cen)) * M
            if closed >= 20:
                h = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me) & (hurt['tick'] >= ct)]
                dmg = int(h['dmg_health'].clip(upper=100).sum())
                base = _base(rn, side, won, ct + 8 * TICK, rt, mr2['last_place_name'], (mr2.X, mr2.Y)); base.update(path=mypath(ct + 8 * TICK), extra_pos=cen, extra_label='enemies spotted here')
                out.append(dict(base, kind='rotated_on_info', facts=f"Round {rn+1}, CT, {rt(ct, rn)} s. Your team had {len(far)} enemies spotted about {math.dist((mr.X, mr.Y), cen) * M:.0f} m from you near {far[0].last_place_name}. Within 8 s you closed {closed:.0f} m toward them" + (f" and did {dmg} damage afterwards." if dmg else "."), dmg=dmg))
                break
    return out
