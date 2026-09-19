"""More than half of my shots in the last 4 s were fired on the move with the bullet cone too wide to hit at the target's distance, and I died."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from demolib import bullet_cones
from ._context import Ctx, ang, bearing, dist_m
from ._weapons import wclass, wkey
KIND = 'shot_moving'
SIDE = 'mistake'
TITLE = 'Shot while moving'
WHY = ("Judged from the game's own record of each bullet (its inaccuracy plus spread: the cone the bullet was drawn from), not from speed "
       'alone. A shot counts when you were moving (over 60 u/s, from your positions), the cone at the distance of the enemy you were aiming '
       "at was wider than a 0.3 m radius (about a torso), and it was at least twice that weapon's cone when fired standing at the same "
       'point of a spray (measured from every such bullet in this demo), so the movement is what made it unreliable. More than half of '
       'your shots in the 4 s before the death were like that. Running with a Glock or an SMG at close range keeps the cone tight and is '
       'not counted; a rifle at a full run never is tight. Not measured on demos that do not record per-bullet data.')
DO = 'Counter-strafe: tap the opposite key to stop dead, shoot, then move again. Practice it until it is not a decision.'
BASE = 18

MOVING = 60             # u/s, from positions: slower than this is a shuffle, not movement
UNRELIABLE_M = 0.30     # a cone radius wider than this at the target's distance can miss a torso with perfect aim
MOVEMENT_FACTOR = 2.0   # the cone must be at least this many times the weapon's standing cone, so movement is the cause
AIM_DEG = 12            # a shot is aimed at the enemy nearest its line within this angle; else the killer's distance is used


def detect(c: Ctx) -> Iterator[Card | None]:
    shots_idx, base = bullet_cones(c.D)
    if not shots_idx: return
    me = c.me
    for R in c.rounds():
        rf = R.rf
        for x in R.deaths_of_mine():
            if not x.by_enemy or wclass(x.d.user_active_weapon_name) not in ('rifle', 'smg', 'sniper', 'pistol'): continue
            g4 = rf[(rf['tick'] >= x.t - 4 * TICK) & (rf['tick'] <= x.t)]
            known = 0; bad = []
            for r in g4.itertuples():
                b = shots_idx.get((int(r.tick), me))
                if b is None: continue
                known += 1; cone, bucket, in_air = b
                ct = c.coarse(int(r.tick)); v = c.speed(ct, me)
                if v <= MOVING: continue
                # the distance that matters is to the enemy this shot was aimed at
                d = None; g = c.by_tick.get(ct)
                if g is not None and r.user_yaw == r.user_yaw and r.user_X == r.user_X:
                    best = None
                    for f in g[(g['team_num'] != R.team) & (g['is_alive'] == True)].itertuples():
                        off = ang(float(r.user_yaw), bearing((float(r.user_X), float(r.user_Y)), (float(f.X), float(f.Y))))
                        if off < AIM_DEG and (best is None or off < best[0]): best = (off, dist_m((float(r.user_X), float(r.user_Y)), (float(f.X), float(f.Y))))
                    if best: d = best[1]
                if d is None: d = float(x.dist)
                w = wkey(r.weapon); standing = base.get((w, bucket), base.get((w, None)))
                if d * cone > UNRELIABLE_M and (standing is None or cone >= MOVEMENT_FACTOR * standing):
                    bad.append((d * cone, v, cone, d, w, standing))
            if known >= 3 and len(bad) / known > 0.5:
                rad, v, cone, d, w, standing = max(bad, key=lambda b: b[0])
                yield x.card(f" {len(bad)} of your {known} shots in the last 4 s were fired on the move with the bullet cone wider than {UNRELIABLE_M} m at the target. The widest: moving at {v:.0f} u/s, the game recorded a cone of {cone:.4f} for the {w}, a {rad:.1f} m radius at {d:.0f} m"
                             + (f" (standing, the same weapon's cone in this demo is {standing:.4f})." if standing is not None else "."), n_bad=len(bad), n_shots=known)
