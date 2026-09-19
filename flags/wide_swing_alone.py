"""Died at full speed, closing on the killer over the last second, with no teammate within 15 m."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx, dist_m
KIND = 'wide_swing_alone'
SIDE = 'mistake'
TITLE = 'Wide swing alone'
WHY = 'You died at full speed, closing on your killer over the last second, with no teammate within 15 m to trade.'
DO = 'Wide swings work with a trade partner or a flash. Alone, shoulder-peek for information instead.'
BASE = 34


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.deaths_of_mine():
            nm = x.nm; spd = c.speed(c.coarse(x.t), c.me)
            if spd > 200 and x.kpos and (nm is None or nm[0] > 15) and x.by_enemy:
                p1 = c.row(x.t - TICK, c.me)
                if p1 is not None and dist_m((float(p1.X), float(p1.Y)), x.kpos) - dist_m(x.pos, x.kpos) > 1.0:
                    yield x.card(f" You were moving at {spd:.0f} u/s toward them" + (f", nearest teammate {nm[0]:.0f} m away." if nm else ", no teammate alive nearby."))
