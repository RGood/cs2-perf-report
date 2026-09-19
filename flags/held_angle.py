"""My kill where, at first mutual sight, the victim was moving and I was stationary and already aimed at their entry."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
import math
from constants import TICK, M
from ._context import Ctx, ang, bearing
KIND = 'held_angle'
SIDE = 'play'
TITLE = 'Held the angle'
WHY = ('The enemy swung into you while you were set and already aiming at their entry. You won a fight that was yours on the '
       'numbers.')
DO = 'Keep letting them come to your crosshair. Patience at a good angle wins more duels than any amount of aim.'
BASE = 30


def detect(c: Ctx) -> Iterator[Card | None]:
    me = c.me; deaths = c.deaths; fz = c.fz; rt = c.rt
    for d in deaths[deaths['attacker_steamid'] == me].itertuples():
        rn = int(d.total_rounds_played); t = int(d.tick)
        if rn not in fz or t < fz[rn]: continue
        team = int(d.attacker_team_num); side = 'CT' if team == 3 else 'T'; won = c.D['winner'].get(rn) == side
        if team not in (2, 3): continue
        V = str(d.user_steamid)
        fm = None
        for ct in range(c.coarse(t - 3 * TICK), t + 1, 8):
            g = c.by_tick.get(ct)
            if g is None: continue
            mr = g[g['steamid'] == me]; vr = g[g['steamid'] == V]
            if not len(mr) or not len(vr): continue
            mr = mr.iloc[0]; vr = vr.iloc[0]
            if c.sees(mr, V) and c.sees(vr, me): fm = (ct, mr, vr); break
        if fm is None: continue
        ct, mr, vr = fm
        dist = math.dist((mr.X, mr.Y), (vr.X, vr.Y)) * M
        my_v = c.speed(ct, me); v_v = c.speed(ct, V); my_aim = ang(float(mr['yaw']), bearing((mr.X, mr.Y), (vr.X, vr.Y)))
        if v_v > 120 and my_v < 30 and my_aim <= 20 and dist >= 8:
            base = c.position_card(rn, side, won, t, d.attacker_last_place_name, (d.attacker_X, d.attacker_Y)); base.update(path=c.my_path(t), victim=str(d.user_name), vpos=(d.user_X, d.user_Y))
            yield dict(base, facts=f"Round {rn+1}, {side}, {rt(t, rn)} s. {d.user_name} swung into you at {d.attacker_last_place_name} from {dist:.0f} m while you were stationary with your crosshair {my_aim:.0f}° off their entry. Killed {(t - ct) / TICK:.1f} s after first sight.", headshot=bool(d.headshot))


def adjust(m: Card, add: Add) -> None:
    if m.get('headshot'): add(3, 'headshot')
