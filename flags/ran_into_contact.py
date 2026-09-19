"""Running, unspotted, toward an unseen enemy within 20 m in the 3 s before dying; rushes and executes are exempt."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx, dist_m
KIND = 'ran_into_contact'
SIDE = 'mistake'
TITLE = 'Ran into contact'
WHY = ('You were running (over 200 u/s) toward an enemy within 20 m whom nobody on your team had seen yet and who had not seen'
       ' you in the last 8 s, and you lost the fight that followed. Running makes noise the enemy hears before you see them. A'
       ' sighting in the last 8 s still counts as seen even if line of sight broke since; an older one does not. Rushes and '
       'executes are not counted: two or more teammates who were running (over 150 u/s) within 25 m of you at some point in '
       "the 3 s before, which includes the ones ahead of you who had just stopped to fight or died; or two or more of your team's "
       'grenades going off within 30 m of you in the last 6 s.')
DO = 'Walk the last 20 m into any position an enemy could hold. Sound is information you give away.'
BASE = 12

RUN_SPEED = 200         # u/s: faster than this makes footstep noise
NEAR_M = 20
SEEN_MEMORY_S = 8.0     # a sighting this recent still counts as "seen" even if line of sight broke since
RUSH_MATES = 2          # a rush: this many teammates who were within RUSH_M of me and moving faster than RUSH_SPEED ...
RUSH_M = 25             # ... a group strings out along the path, so the radius covers the whole file of players
RUSH_SPEED = 150
RUSH_WINDOW_S = 3       # ... at some sample in this many seconds before: the front of a rush stops to fight, or dies, before the back arrives
EXEC_NADES = 2          # an execute: this many of my team's grenades going off within EXEC_M in the last EXEC_S seconds
EXEC_M = 30
EXEC_S = 6


def detect(c: Ctx) -> Iterator[Card | None]:
    me = c.me; dt_ = c.deton
    for R in c.rounds():
        team = R.team; ft = R.ft
        def seen_recently(a: str, b: str, t_to: int) -> bool:
            """Did a have b in view within the last SEEN_MEMORY_S seconds?"""
            for ct_ in range(max(ft, c.coarse(t_to - int(SEEN_MEMORY_S * TICK)) or ft), t_to + 1, 8):
                rb = c.row(ct_, b)
                if rb is not None and c.sees(rb, a): return True
            return False
        def ran_with_me(ms: str, t_to: int) -> bool:
            """Was this teammate alive, within RUSH_M of me and running at some sample in the RUSH_WINDOW_S seconds up to t_to?"""
            for ct_ in range(max(ft, c.coarse(t_to - RUSH_WINDOW_S * TICK)), t_to + 1, 8):
                rm = c.row(ct_, ms); rme = c.row(ct_, me)
                if rm is None or rme is None or not bool(rm['is_alive']): continue
                if dist_m((float(rme.X), float(rme.Y)), (float(rm.X), float(rm.Y))) <= RUSH_M and c.speed(ct_, ms) > RUSH_SPEED: return True
            return False
        for x in R.deaths_of_mine():
            t = x.t; ran = None
            for ct in range(c.coarse(t - 3 * TICK), t, 8):
                r = c.row(ct, me); g = c.by_tick.get(ct)
                if r is None or g is None or bool(r['spotted']): continue
                if c.speed(ct, me) <= RUN_SPEED: continue
                fo = g[(g['team_num'] != team) & (g['is_alive'] == True) & (g['spotted'] == False)]
                near_f = [f for f in fo.itertuples() if dist_m((float(r.X), float(r.Y)), (float(f.X), float(f.Y))) < NEAR_M
                          and not seen_recently(str(f.steamid), me, ct) and not seen_recently(me, str(f.steamid), ct)]
                if not near_f: continue
                # a rush or an execute is meant to be loud: teammates moving with you, or your team's utility going off around you
                mypos_ = (float(r.X), float(r.Y))
                movers = sum(1 for ms in R.mates if ran_with_me(ms, ct))
                team_ids_ = R.mates | {me}
                util_ = dt_[(dt_['steamid'].isin(team_ids_)) & (dt_['tick'] >= ct - EXEC_S * TICK) & (dt_['tick'] <= ct + TICK)] if len(dt_) else dt_
                util_near = sum(1 for u_ in util_.itertuples() if dist_m(mypos_, (float(u_.x), float(u_.y))) <= EXEC_M)
                if movers >= RUSH_MATES or util_near >= EXEC_NADES: continue
                ran = (ct, near_f[0].name); break
            if ran and x.by_enemy:
                yield x.card(f" {(t - ran[0]) / TICK:.1f} s earlier you were running, unspotted, with {ran[1]} unspotted within 20 m.")
