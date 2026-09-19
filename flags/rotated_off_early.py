"""CT: left my starting spot by more than 30 m before any enemy was within 40 m of it, and enemies reached it within 15 s."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx, dist_m
KIND = 'rotated_off_early'
SIDE = 'mistake'
TITLE = 'Rotated off site early'
WHY = ('As CT you moved more than 30 m from your starting spot before any enemy was within 40 m of it, and enemies then '
       'arrived where you had been within 15 s.')
DO = 'Rotate on information, not on a hunch. If the site is quiet, it still needs someone on it.'
BASE = 34


def detect(c: Ctx) -> Iterator[Card | None]:
    me = c.me
    for R in c.rounds():
        if R.side != 'CT' or R.g0 is None: continue
        ft = R.ft; end = R.end; team = R.team
        r0 = c.row(ft, me)
        if r0 is None or not (r0.X == r0.X): continue
        start = (float(r0.X), float(r0.Y)); left_t = None
        for ct in range(ft, min(ft + 20 * TICK, end), 8):
            r = c.row(ct, me); g = c.by_tick.get(ct)
            if r is None or g is None or not bool(r['is_alive']): break
            fo = g[(g['team_num'] != team) & (g['is_alive'] == True)]
            if any(dist_m(start, (float(f.X), float(f.Y))) < 40 for f in fo.itertuples()): break
            if dist_m(start, (float(r.X), float(r.Y))) > 30: left_t = ct; break
        if left_t is None: continue
        for ct in range(left_t, min(left_t + 15 * TICK, end), 16):
            g = c.by_tick.get(ct); r = c.row(ct, me)
            if g is None or r is None: continue
            fo = g[(g['team_num'] != team) & (g['is_alive'] == True)]
            if any(dist_m(start, (float(f.X), float(f.Y))) < 20 for f in fo.itertuples()) and dist_m(start, (float(r.X), float(r.Y))) > 30:
                yield c.card(R.rn, R.side, left_t, str(r0['last_place_name']), start, facts=f"Round {R.rn+1}, CT, {c.rt(left_t, R.rn)} s. You left your start at {r0['last_place_name']} with no enemy within 40 m of it; enemies reached it {(ct - left_t) / TICK:.0f} s later while you were {dist_m(start, (float(r.X), float(r.Y))):.0f} m away.", extra_pos=(float(r.X), float(r.Y)), extra_label='you, when they arrived')
                break
