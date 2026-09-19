"""Shared read-only helpers over the parsed demo dict D (see mistake_report.parse): per-demo caches, grenade flights,
and the teammate-fight analysis. The flags package and the report modules both import from here."""
from __future__ import annotations
from typing import Any, Collection
from report_types import ByTick, Coarse, Demo, TickTable, XY
import math
import pandas as pd
from constants import TICK, M, REACTION_S, STANDING_SPEED, RECOIL_BUCKETS


def nade_flight(D: Demo, steamid: str, throw_tick: int, weapon: str, max_s: float = 8.0) -> tuple[str, list[XY], XY, int, int] | None:
    """Flight of one thrown grenade: (kind, [(x, y), ...], end_xy) from the projectile table, ended at the detonation. None if no projectile was found."""
    kind = {'molotov': 'molotov', 'incgrenade': 'molotov', 'flashbang': 'flashbang', 'smokegrenade': 'smokegrenade', 'hegrenade': 'hegrenade', 'decoy': 'decoy'}.get(weapon.replace('weapon_', ''))
    if kind is None: return None
    pr = D['proj']; dt = D['deton']
    q = pr[(pr['steamid'] == str(steamid)) & (pr['kind'] == kind) & (pr['tick'] >= throw_tick - 2) & (pr['tick'] <= throw_tick + max_s * TICK)]
    if not len(q): return None
    # the entity that appears first after the throw
    first = q.groupby('grenade_entity_id')['tick'].min(); ent = first.idxmin()
    if first.min() > throw_tick + TICK: return None
    q = q[q['grenade_entity_id'] == ent].sort_values('tick')
    d = dt[(dt['steamid'] == str(steamid)) & (dt['kind'] == kind) & (dt['tick'] >= throw_tick) & (dt['tick'] <= throw_tick + max_s * TICK)]
    if len(d):
        end_tick = int(d.iloc[0]['tick']); end = (float(d.iloc[0]['x']), float(d.iloc[0]['y'])); q = q[q['tick'] <= end_tick]
    else:
        end_tick = int(q.iloc[-1]['tick']); end = (float(q.iloc[-1]['x']), float(q.iloc[-1]['y']))
    path = [(float(r.x), float(r.y)) for r in q.itertuples()][::2]
    if not path or path[-1] != end: path.append(end)
    return (kind, path, end, int(throw_tick), end_tick)


def for_player(D: Demo, sid: str) -> Demo:
    """Return a shallow copy of a parsed demo focused on another player (same snapshot, their grenades)."""
    by_tick_of(D); ticktab_of(D); bullet_cones(D)      # build the per-demo caches once, so every player's copy shares them
    E = dict(D); E.pop('_ctx', None); E['me'] = str(sid); E['nades'] = D['all_nades'][D['all_nades']['user_steamid'] == str(sid)]
    return E


# ----------------------------------------------------------------------------- teammate-fight analysis (shared by both sides)


def aimed_shots(D: Demo, by_tick: ByTick, coarse: Coarse, rn: int, t0: int, t1: int, shooters: Collection[str], targets: Collection[str], max_m: float = 60.0, deg: float = 10.0) -> int:
    """Shots in [t0, t1] by any of `shooters` aimed within `deg` degrees of any of `targets` (alive, within max_m). A shot fired at
    a player is a fight whether or not it lands, which player_hurt alone would miss."""
    fire = D['gunfire']; sh = fire[(fire['total_rounds_played'] == rn) & (fire['tick'] >= t0) & (fire['tick'] <= t1) & (fire['user_steamid'].isin(shooters))]
    n = 0
    for s in sh.itertuples():
        if not (s.user_X == s.user_X and s.user_yaw == s.user_yaw): continue
        g = by_tick.get(coarse(int(s.tick)))
        if g is None: continue
        for tr in g[(g['steamid'].isin(targets)) & (g['is_alive'] == True)].itertuples():
            d = math.dist((s.user_X, s.user_Y), (tr.X, tr.Y)) * M
            if d > max_m: continue
            off = abs(((math.degrees(math.atan2(tr.Y - s.user_Y, tr.X - s.user_X)) - float(s.user_yaw) + 180) % 360) - 180)
            if off < deg: n += 1; break
    return n


def teammate_fights(D: Demo, me: str, by_tick: ByTick, coarse: Coarse, rn: int, team: int) -> list[dict[str, Any]]:
    """For each teammate death in round rn: the fight window, my ability to help, and when I actually engaged the killer.
    Returns a list of dicts (one per teammate death where the killer is an enemy)."""
    deaths = D['deaths']; hurt = D['hurt']; fire = D['gunfire']
    rd = deaths[(deaths['total_rounds_played'] == rn)].sort_values('tick')
    out = []
    for d in rd[(rd['user_team_num'] == team) & (rd['user_steamid'] != me)].itertuples():
        E = str(d.attacker_steamid); T = str(d.user_steamid); t_death = int(d.tick)
        if E in ('nan', 'None', '') or E == T: continue
        # was I alive at the death?
        g = by_tick.get(coarse(t_death - 1))
        if g is None: continue
        mr = g[g['steamid'] == me]
        if not len(mr) or not bool(mr.iloc[0]['is_alive']): continue
        # fight window: first damage between T and E in the 6 s before the death
        hh = hurt[(hurt['total_rounds_played'] == rn) & (hurt['tick'] >= t_death - 6 * TICK) & (hurt['tick'] <= t_death) &
                  (((hurt['attacker_steamid'] == E) & (hurt['user_steamid'] == T)) | ((hurt['attacker_steamid'] == T) & (hurt['user_steamid'] == E)))]
        t_start = int(hh['tick'].min()) if len(hh) else t_death
        dur = (t_death - t_start) / TICK
        # my own fights during the window (excluding E): hurt events with me as attacker or victim, other party not E
        mine = hurt[(hurt['total_rounds_played'] == rn) & (hurt['tick'] >= t_start - TICK) & (hurt['tick'] <= t_death) &
                    (((hurt['attacker_steamid'] == me) & (hurt['user_steamid'] != E)) | ((hurt['user_steamid'] == me) & (hurt['attacker_steamid'] != E)))]
        busy = len(mine) > 0
        if not busy:
            g0_ = by_tick.get(coarse(t_start)); foe_ids_ = set(str(x) for x in g0_[(g0_['team_num'] != team) & (g0_['team_num'] > 1)]['steamid']) if g0_ is not None else set()
            others_ = foe_ids_ - {E}
            if aimed_shots(D, by_tick, coarse, rn, t_start - TICK, t_death, foe_ids_, {me}) or (others_ and aimed_shots(D, by_tick, coarse, rn, t_start - TICK, t_death, {me}, others_)): busy = True
        # my damage on E before the death, and my first engagement of E (damage, or a shot while E was in my view)
        dmg_before = int(hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me) & (hurt['user_steamid'] == E) & (hurt['tick'] >= t_start) & (hurt['tick'] < t_death)]['dmg_health'].clip(upper=100).sum())
        after = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me) & (hurt['user_steamid'] == E) & (hurt['tick'] >= t_death) & (hurt['tick'] <= t_death + 4 * TICK)]
        t_engage = int(after['tick'].min()) if len(after) else None
        # my situation across the window, sampled on coarse ticks
        saw_from = None; min_dist = None; blind = False; my_pos = None; my_place = None; e_pos = None
        for ct in range(coarse(t_start), t_death + 1, 8):
            g = by_tick.get(ct)
            if g is None: continue
            mr = g[g['steamid'] == me]; er = g[g['steamid'] == E]
            if not len(mr) or not len(er): continue
            mr = mr.iloc[0]; er = er.iloc[0]
            dist = math.dist((mr.X, mr.Y), (er.X, er.Y)) * M
            if min_dist is None or dist < min_dist: min_dist = dist
            if (mr['flash_duration'] or 0) > 0.5: blind = True
            spot = er['approximate_spotted_by']
            try:
                seen = me in [str(x) for x in spot]
            except TypeError:
                seen = False
            if seen and saw_from is None and ct >= t_start + int(REACTION_S * TICK) and ct <= t_death - int(0.5 * TICK): saw_from = ct
            my_pos = (mr.X, mr.Y); my_place = mr['last_place_name']; e_pos = (er.X, er.Y)
        if not t_engage:
            # a shot fired at E counts as engaging if E was in my view at the time
            ff = fire[(fire['total_rounds_played'] == rn) & (fire['user_steamid'] == me) & (fire['tick'] >= t_death) & (fire['tick'] <= t_death + 4 * TICK)]
            for r in ff.itertuples():
                g = by_tick.get(coarse(int(r.tick))); er = g[g['steamid'] == E] if g is not None else None
                if er is not None and len(er):
                    try:
                        if me in [str(x) for x in er.iloc[0]['approximate_spotted_by']]: t_engage = int(r.tick); break
                    except TypeError:
                        pass
        out.append(dict(mate=str(d.user_name), mate_sid=T, enemy=str(d.attacker_name), enemy_sid=E, t_start=t_start, t_death=t_death, dur=dur,
                        busy=busy, blind=blind, dmg_before=dmg_before, t_engage=t_engage, saw_from=saw_from, min_dist=min_dist,
                        my_pos=my_pos, my_place=my_place, e_pos=e_pos, mate_pos=(d.user_X, d.user_Y), mate_place=str(d.user_last_place_name),
                        enemy_hp=int(d.attacker_health) if pd.notna(d.attacker_health) else None))
    return out


def by_tick_of(D: Demo) -> ByTick:
    """Per-demo cache of the snapshot grouped by tick (shared by every detector and every player)."""
    if '_by_tick' not in D:
        D['_by_tick'] = {t: g for t, g in D['snap'].groupby('tick')}
    return D['_by_tick']


def ticktab_of(D: Demo) -> TickTable:
    """Per-demo cache of compact numpy tables per tick: sid, name, team, X, Y, alive, spotted, place."""
    if '_ticktab' not in D:
        import numpy as np
        snap = D['snap'].sort_values('tick')
        ticks = snap['tick'].values
        cols = dict(sid=snap['steamid'].astype(str).values, name=snap['name'].astype(str).values, team=snap['team_num'].values.astype(int),
                    X=snap['X'].values.astype(float), Y=snap['Y'].values.astype(float), alive=snap['is_alive'].values.astype(bool),
                    spotted=snap['spotted'].values.astype(bool), place=snap['last_place_name'].astype(str).values)
        uniq, starts = np.unique(ticks, return_index=True)
        ends = list(starts[1:]) + [len(ticks)]
        D['_ticktab'] = {int(t): {k: v[a:b] for k, v in cols.items()} for t, a, b in zip(uniq, starts, ends)}
    return D['_ticktab']


def teammate_engagements(D: Demo, rn: int, team: int, me: str, gap_s: float = 3.0) -> list[dict[str, Any]]:
    """Windows of damage exchanged between a teammate T and an enemy E in round rn: list of dicts(T, E, t0, t1, T_died, E_died)."""
    hurt = D['hurt']; deaths = D['deaths']
    h = hurt[(hurt['total_rounds_played'] == rn)]
    rd = deaths[deaths['total_rounds_played'] == rn]
    dead_at = {str(r.user_steamid): int(r.tick) for r in rd.itertuples()}
    pairs = {}      # (teammate, enemy) -> damage ticks, whichever of the two was the attacker
    # team membership from the snapshot at the freeze tick
    g = by_tick_of(D).get(D['fz'][rn])
    if g is None: return []
    my_team = set(str(x) for x in g[g['team_num'] == team]['steamid']) - {me}
    foes = set(str(x) for x in g[g['team_num'] != team]['steamid'])
    for r in h.itertuples():
        a, v = str(r.attacker_steamid), str(r.user_steamid)
        if a in my_team and v in foes: key = (a, v)
        elif v in my_team and a in foes: key = (v, a)
        else: continue
        pairs.setdefault(key, []).append(int(r.tick))
    out = []
    for (T, E), ticks in pairs.items():
        ticks.sort(); start = ticks[0]; last = ticks[0]
        for tk in ticks[1:] + [None]:
            if tk is None or tk - last > gap_s * TICK:
                t1 = last
                if T in dead_at and start <= dead_at[T] <= t1 + gap_s * TICK: t1 = max(t1, dead_at[T])
                if E in dead_at and start <= dead_at[E] <= t1 + gap_s * TICK: t1 = max(t1, dead_at[E])
                out.append(dict(T=T, E=E, t0=start, t1=t1, T_died=(T in dead_at and start <= dead_at[T] <= t1), E_died=(E in dead_at and start <= dead_at[E] <= t1)))
                if tk is not None: start = tk
            if tk is not None: last = tk
    return out

# ----------------------------------------------------------------------------- mistake detection
def nade_list(inv: Any) -> list[str]:
    try:
        return [x for x in inv if any(k in str(x) for k in ('Grenade', 'Molotov', 'Incendiary', 'Flashbang', 'Smoke', 'Decoy'))]
    except TypeError:
        return []


def speed_at(tab: TickTable, c: int, sid: str) -> float:
    """Horizontal speed in units/s at sampled tick c, from the position change over the previous sample (the demo's velocity field is unusable)."""
    import numpy as np
    r = tab.get(c); q = tab.get(c - 8)
    if r is None or q is None: return 0.0
    i = np.where(r['sid'] == sid)[0]; j = np.where(q['sid'] == sid)[0]
    if not len(i) or not len(j): return 0.0
    return float(math.hypot(r['X'][i[0]] - q['X'][j[0]], r['Y'][i[0]] - q['Y'][j[0]]) / 0.125)


def recoil_bucket(ri: float) -> int:
    return sum(1 for b in RECOIL_BUCKETS if ri >= b)


def bullet_cones(D: Demo) -> tuple[dict[tuple[int, str], tuple[float, int, bool]], dict[tuple[str, int | None], float]]:
    """Per-demo cache from the game's own record of every bullet (the fire_bullets event): (shots, baseline).

    shots     {(tick, steamid): (cone, recoil bucket, in air)} where cone = inaccuracy + spread, the half-angle (as a tangent) of the cone the
              game drew the bullet from. At d metres the bullet lands within d * cone metres of the point of aim.
    baseline  {(weapon, recoil bucket): median cone of that weapon fired standing still at that point of a spray, by any player in this demo}
              plus {(weapon, None): the same over all buckets}; only where five or more such bullets exist.
    Both are empty when the demo has no fire_bullets event."""
    if '_cones' in D: return D['_cones']
    import numpy as np
    fb = D.get('bullets'); shots = {}; base = {}
    if fb is not None and len(fb) and 'inaccuracy' in fb.columns:
        tab = ticktab_of(D); first = min(tab)
        gf = D['gunfire']; wpn = {(int(t), str(s)): str(w).replace('weapon_', '') for t, s, w in zip(gf['tick'], gf['user_steamid'], gf['weapon'])}
        still = {}
        for r in fb.drop_duplicates(['tick', 'user_steamid']).itertuples():
            if not (r.inaccuracy == r.inaccuracy): continue
            t = int(r.tick); sid = str(r.user_steamid); cone = float(r.inaccuracy) + (float(r.spread) if r.spread == r.spread else 0.0)
            ri = float(r.recoil_index) if r.recoil_index == r.recoil_index else 0.0; air = bool(r.player_inair) if r.player_inair == r.player_inair else False
            b = recoil_bucket(ri); shots[(t, sid)] = (cone, b, air)
            w = wpn.get((t, sid))
            if w and not air and speed_at(tab, t - ((t - first) % 8), sid) < STANDING_SPEED:
                still.setdefault((w, b), []).append(cone); still.setdefault((w, None), []).append(cone)
        base = {k: float(np.median(v)) for k, v in still.items() if len(v) >= 5}
    D['_cones'] = (shots, base)
    return D['_cones']
