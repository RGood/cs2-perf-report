"""Helpers that two or more flags use. A flag file never imports another flag file: what they share lives here (or in _context.py when it
is demo context computed once per player), so the flags have no dependencies on each other and no import loops are possible.

Import order inside the package is one-way:  constants -> demolib -> _weapons / _context / _economy -> _shared -> the flag files."""
from __future__ import annotations
from typing import Any, Iterator
from report_types import Card, EventRow, Row, XY
import pandas as pd
from constants import TICK, SPRAY_RUN
from ._context import Ctx, Death, DeathInDepth, Kill, Round, dist_m
from ._weapons import wkey

# from attacked_off_view
def fights_started(c: Ctx, R: Round) -> Iterator[tuple[int, EventRow, XY, XY, Row | None, Row | None, bool, dict[str, Any], str]]:
    """My first damage on each enemy this round (a new fight after 6 s without hitting them):
    (tick, hurt row, my pos, their pos, their row, my row, did I kill them within 6 s, card fields, opening sentence)."""
    last_hit: dict[str, int] = {}
    for hh in R.rh[R.rh['user_steamid'].isin(R.foes)].sort_values('tick').itertuples():
        t = int(hh.tick); v = str(hh.user_steamid)
        if v in last_hit and t - last_hit[v] <= 6 * TICK: last_hit[v] = t; continue
        last_hit[v] = t
        if not (hh.attacker_X == hh.attacker_X and hh.user_X == hh.user_X): continue
        mpos = (float(hh.attacker_X), float(hh.attacker_Y)); vpos = (float(hh.user_X), float(hh.user_Y)); vr = c.row(t - 1, v); mr = c.row(t - 1, c.me)
        killed = bool(len(R.my_kills[(R.my_kills['user_steamid'] == v) & (R.my_kills['tick'] >= t) & (R.my_kills['tick'] <= t + 6 * TICK)]))
        kw = dict(victim=str(hh.user_name), vpos=vpos, victim_sid=v, got_kill=killed)
        head = f"Round {R.rn+1}, {R.side}, {c.rt(t, R.rn)} s. First damage on {hh.user_name} ({wkey(hh.weapon)}, {dist_m(mpos, vpos):.0f} m)"
        yield t, hh, mpos, vpos, vr, mr, killed, kw, head


# from defused_under_fire
def my_defuses(c: Ctx, R: Round) -> Iterator[tuple[int, int | None, Row, XY]]:
    """(tick, enemies alive, my row, my position) for each defuse I finished this round."""
    dfd = c.D.get('defused')
    if dfd is None or not len(dfd): return
    for r in dfd[(dfd['total_rounds_played'] == R.rn) & (dfd['user_steamid'] == c.me)].itertuples():
        t = int(r.tick); ma, fo = c.alive_counts(t - 1, R.team); mr = c.row(t - 1, c.me)
        if mr is None: continue
        yield t, fo, mr, (float(mr.X), float(mr.Y))


# from died_planting
def my_unfinished_plant(c: Ctx, R: Round, x: Death) -> int | None:
    """The tick I started a plant in the 4 s before death x without finishing it, or None."""
    pb = c.D.get('plant_begin')
    if pb is None or not len(pb): return None
    mine_pb = pb[(pb['total_rounds_played'] == R.rn) & (pb['user_steamid'] == c.me) & (pb['tick'] <= x.t) & (pb['tick'] >= x.t - 4 * TICK)]
    planted = c.plant[(c.plant['total_rounds_played'] == R.rn) & (c.plant['user_steamid'] == c.me) & (c.plant['tick'] <= x.t)]
    return int(mine_pb.iloc[-1]['tick']) if len(mine_pb) and not len(planted) else None


# from flash_blinded_nobody
def my_pops(c: Ctx, R: Round, kind: str) -> Iterator[tuple[int, XY, pd.DataFrame, XY, str | None]]:
    """My grenades of one kind that went off this round: (tick, landing point, enemies alive then, my position, my place)."""
    dt = c.deton; dt_r = dt[(dt['steamid'] == c.me) & (dt['tick'] >= R.ft) & (dt['tick'] < R.end)] if len(dt) else dt
    for r in dt_r.itertuples():
        if r.kind != kind: continue
        t = int(r.tick); lp = (float(r.x), float(r.y)); g = c.by_tick.get(c.coarse(t))
        if g is None: continue
        fo = g[(g['team_num'] != R.team) & (g['is_alive'] == True)]
        mr = c.row(t, c.me); mpos = (float(mr.X), float(mr.Y)) if mr is not None else lp; mplace = str(mr['last_place_name']) if mr is not None else None
        yield t, lp, fo, mpos, mplace


# from flash_blinded_nobody
def enemies_blinded(c: Ctx, R: Round, t: int, min_s: float = 0.5) -> pd.DataFrame:
    """The blind rows of my pop at tick t for enemies blinded min_s or longer."""
    bl = c.blind
    b = bl[(bl['attacker_steamid'] == c.me) & ((bl['tick'] - t).abs() <= 2)] if len(bl) else bl
    return b[(b['user_team_num'] != R.team) & (b['blind_duration'] >= min_s)] if len(b) else b


# from killed_full_buy_on_eco
def equip_at_kill(c: Ctx, x: Kill) -> tuple[int, int] | None:
    """(my equipment, the victim's equipment) just before kill x, or None."""
    mr = c.row(x.t - 1, c.me); vr1 = c.row(x.t - 1, x.victim)
    if mr is None or vr1 is None: return None
    my_eq = int(mr['current_equip_value']) if mr['current_equip_value'] == mr['current_equip_value'] else 0
    v_eq = int(vr1['current_equip_value']) if vr1['current_equip_value'] == vr1['current_equip_value'] else 0
    return my_eq, v_eq


# from missed_trade
def mate_deaths_nearby(c: Ctx, R: Round) -> Iterator[tuple[EventRow, Row, XY, XY, float]]:
    """Teammate deaths to an enemy this round that I was alive for (and did not die within 5 s of): (death row, my row, my pos, their pos, metres)."""
    rdm = R.my_deaths
    for d in R.rd[(R.rd['user_team_num'] == R.team) & (R.rd['user_steamid'] != c.me)].itertuples():
        t = int(d.tick); killer = str(d.attacker_steamid) if pd.notna(d.attacker_steamid) else None
        if killer not in R.foes or not (d.user_X == d.user_X): continue
        mr = c.row(t, c.me)
        if mr is None or not bool(mr['is_alive']) or (len(rdm) and int(rdm.iloc[0]['tick']) <= t + 5 * TICK and int(rdm.iloc[0]['tick']) >= t): continue
        mpos = (float(mr.X), float(mr.Y)); dpos = (float(d.user_X), float(d.user_Y))
        yield d, mr, mpos, dpos, dist_m(mpos, dpos)


# from opening_kill
def kill_facts(c: Ctx, R: Round, k: EventRow) -> str:
    """The opening sentence the original kill plays share."""
    t = int(k.tick)
    return f"Round {R.rn+1}, {R.side}, {c.rt(t, R.rn)} s. Killed {k.user_name} ({k.weapon}{', headshot' if k.headshot else ''}) at {k.user_last_place_name} from {k.attacker_last_place_name}, {float(k.distance):.0f} m."


# from plant_under_pressure
def my_plants(c: Ctx, R: Round) -> Iterator[tuple[int, XY]]:
    """(tick, bomb position) of each plant of mine this round."""
    pl = c.plant[(c.plant['total_rounds_played'] == R.rn)]
    for r in pl[pl['user_steamid'] == c.me].itertuples():
        if r.user_X == r.user_X: yield int(r.tick), (float(r.user_X), float(r.user_Y))


# from post_plant_hold
def first_plant(c: Ctx, R: Round) -> tuple[int, XY] | None:
    """(tick, bomb position) of the round's plant, or None."""
    pl = c.plant[(c.plant['total_rounds_played'] == R.rn)]
    if len(pl) and pl.iloc[0]['user_X'] == pl.iloc[0]['user_X']: return int(pl.iloc[0]['tick']), (float(pl.iloc[0]['user_X']), float(pl.iloc[0]['user_Y']))
    return None


# from reloaded_in_open
def my_reloads_near_enemy(c: Ctx, R: Round) -> Iterator[tuple[int, Row, XY, list[Any]]]:
    """My reloads this round with a living enemy within 25 m: (tick, my row, my pos, the near enemies)."""
    rl = c.D.get('reloads')
    if rl is None or not len(rl): return
    for r in rl[(rl['user_steamid'] == c.me) & (rl['tick'] >= R.ft) & (rl['tick'] < R.end)].itertuples():
        t = int(r.tick); mr = c.row(t, c.me); g = c.by_tick.get(c.coarse(t))
        if mr is None or g is None or not bool(mr['is_alive']): continue
        mpos = (float(mr.X), float(mr.Y)); fo = g[(g['team_num'] != R.team) & (g['is_alive'] == True)]
        near_f = [f for f in fo.itertuples() if dist_m(mpos, (float(f.X), float(f.Y))) <= 25]
        if near_f: yield t, mr, mpos, near_f


# from separated_from_team
def isolated(a: DeathInDepth) -> bool:
    """The condition shared with held_alone: nobody near, nobody traded, no shared fight, no teammate with the killer in view."""
    return bool(len(a.mates) >= 2 and a.near and a.near[0] > 15 and not a.traded and not a.shared and not a.mate_los)


# from separated_from_team
def by_movement(a: DeathInDepth) -> bool:
    """Isolated by movement (this flag) rather than by holding a spot (held_alone)."""
    return (a.moved10 is not None and a.moved10 > 12) or (a.mate10 is not None and a.mate10 < 15)


# from separated_from_team
def gap_text(a: DeathInDepth) -> str:
    near_m = a.near[0] if a.near else 0.0       # isolated(a) has already required a nearest teammate
    return f" {len(a.mates)} teammates alive, nearest {near_m:.0f} m away, nobody traded you."


# from spray_at_range
def missed_at_range(a: DeathInDepth) -> bool:
    """The condition shared with missed_at_range: 6 or more shots in the last 4 s, 20 damage or less to anyone, no kill, aimed 20 m or more away."""
    return a.shots4 >= 6 and a.dmg_any4 <= 20 and a.kills4 == 0 and a.aim_range >= 20


# from spray_at_range
def miss_card(a: DeathInDepth) -> Card:
    tgt = f"the enemies you were aiming at were about {a.aim_range:.0f} m away" if a.aimed else f"your killer was {a.dist:.0f} m away"
    return a.card(f" Those shots did {a.dmg_any4} damage to anyone and got no kill; {tgt}. Longest continuous run: {a.longest} shots (spray threshold {SPRAY_RUN}).", aim_range=a.aim_range)


# from survived_damage
def round_end_spot(c: Ctx, R: Round) -> tuple[int, XY, str] | None:
    """(tick, (x, y), place) of my last sampled position in the round, or None."""
    end = int(c.rend.get(R.rn, c.fz.get(R.rn + 1, int(c.mine.index.max()))))
    endpos = c.mine[(c.mine.index >= R.ft) & (c.mine.index <= end)]
    if not len(endpos): return None
    return int(endpos.index[-1]), (endpos.iloc[-1].X, endpos.iloc[-1].Y), endpos.iloc[-1].last_place_name


# from swung_own_flash
def my_enemy_flashes(c: Ctx, R: Round) -> list[tuple[int, pd.DataFrame]]:
    """My flash pops this round that blinded an enemy for a second or more: (pop tick, the blind rows of that pop)."""
    blind = c.blind
    myb = blind[(blind['total_rounds_played'] == R.rn) & (blind['attacker_steamid'] == c.me) & (blind['user_team_num'] != R.team) & (blind['blind_duration'] >= 1.0)]
    return [(int(tick_), grp) for tick_, grp in myb.groupby('tick')]


# from team_flash
def team_at(c: Ctx, rn: int, sid: str) -> int | None:
    g0 = c.by_tick.get(c.fz[rn]); r0 = g0[g0['steamid'] == str(sid)] if g0 is not None else None
    return int(r0.iloc[0]['team_num']) if r0 is not None and len(r0) and r0.iloc[0]['team_num'] == r0.iloc[0]['team_num'] else None
