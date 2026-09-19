"""Shown at a spot while spotted, left it, came back to the same spot within 8 s without showing anywhere else, and died there."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx, dist_m
KIND = 'repeek'
SIDE = 'mistake'
TITLE = 'Re-peeked the same angle'
WHY = ('You fired or took damage at a spot while the enemy had you spotted, left it, and came back to the same spot within 8 s'
       ' without showing yourself anywhere else in between, then died there. The enemy was waiting for exactly that. Not '
       'counted when nobody saw you the first time, or when you showed a different angle first. The demo cannot tell whether '
       'another angle existed, so the flag assumes one did; judge that yourself on the map.')
DO = "After showing yourself, change the angle or the timing. Same angle twice is the enemy's easiest kill."
BASE = 36


def detect(c: Ctx) -> Iterator[Card | None]:
    me = c.me; hurt = c.hurt
    for R in c.rounds():
        rn = R.rn; rf = R.rf
        for x in R.deaths_of_mine():
            t = x.t; pos = x.pos
            # the spots where I showed myself in the last 12 s: where I fired or took damage
            ev_pts = [(int(r.tick), (float(r.user_X), float(r.user_Y))) for r in rf[(rf['tick'] < t) & (rf['tick'] >= t - 12 * TICK)].itertuples() if r.user_X == r.user_X]
            ev_pts += [(int(r.tick), (float(r.user_X), float(r.user_Y))) for r in hurt[(hurt['total_rounds_played'] == rn) & (hurt['user_steamid'] == me) & (hurt['tick'] < t) & (hurt['tick'] >= t - 12 * TICK)].itertuples() if r.user_X == r.user_X]
            for t0, P in sorted(ev_pts):
                if dist_m(P, pos) > 2 or (t - t0) / TICK > 8: continue
                # the first appearance must have been seen: an enemy had you in view around it (spotted is sticky for 8 s)
                seen0 = False
                for ct_ in range(c.coarse(t0 - 8 * TICK) or t0, t0 + TICK, 8):
                    r_ = c.row(ct_, me)
                    if r_ is not None and bool(r_['spotted']): seen0 = True; break
                if not seen0: continue
                # between leaving and returning you must not have shown yourself from a different angle (A, B, A is a different pattern)
                far = False; other_angle = False
                for ct in range(c.coarse(t0), t, 8):
                    r = c.row(ct, me)
                    if r is None: continue
                    dP = dist_m((float(r.X), float(r.Y)), P)
                    if dP > 3: far = True
                    if dP > 4 and bool(r['spotted']): other_angle = True; break
                if not other_angle:
                    mid = [(int(s.tick), (float(s.user_X), float(s.user_Y))) for s in rf[(rf['tick'] > t0) & (rf['tick'] < t)].itertuples() if s.user_X == s.user_X]
                    if any(dist_m(q, P) > 4 for _, q in mid): other_angle = True
                if far and not other_angle and x.by_enemy:
                    yield x.card(f" You had fired or been hit here {(t - t0) / TICK:.1f} s earlier, left, and came back to the same spot.")
                    break
