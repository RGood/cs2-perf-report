"""Reloaded while spotted with an enemy within 25 m, and died within 3 s."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx, dist_m
from ._shared import my_reloads_near_enemy
KIND = 'reloaded_in_open'
SIDE = 'mistake'
TITLE = 'Reloaded in the open'
WHY = 'You reloaded while visible to the enemy with one alive within 25 m, and died within 3 s.'
DO = 'Step behind cover before the reload. Every reload in the open is a free peek for the enemy.'
BASE = 28


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        rdm = R.my_deaths
        for t, mr, mpos, near_f in my_reloads_near_enemy(c, R):
            died_soon = len(rdm) and t < int(rdm.iloc[0]['tick']) <= t + 3 * TICK
            if bool(mr['spotted']) and died_soon:
                yield c.card(R.rn, R.side, t, str(mr['last_place_name']), mpos, facts=f"Round {R.rn+1}, {R.side}, {c.rt(t, R.rn)} s. You reloaded while spotted with {near_f[0].name} {dist_m(mpos, (float(near_f[0].X), float(near_f[0].Y))):.0f} m away, and died {(int(rdm.iloc[0]['tick']) - t) / TICK:.1f} s later.")
