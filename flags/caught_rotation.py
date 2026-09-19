"""T-side kill after 30 s on a victim who had moved more than 20 m in 10 s, with no teammate within 40 m of me."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx, dist_m
KIND = 'caught_rotation'
SIDE = 'play'
RETIRED = "an outcome, not a decision"
TITLE = 'Caught the rotation'
WHY = ('A T-side kill after 30 s on a victim who had moved more than 20 m in the last 10 s, with no teammate within 40 m of '
       'you: the lurk caught the rotate.')
DO = 'Keep timing the lurk to the moment the site is hit.'
BASE = 35


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        if R.side != 'T': continue
        for x in R.kills_of_mine():
            nm = c.nearest_mate(x.t - 1, R.team)
            if c.rt(x.t, R.rn) > 30 and (nm is None or nm[0] > 40) and x.vpos:
                v10 = c.row(x.t - 10 * TICK, x.victim)
                if v10 is not None and dist_m((float(v10.X), float(v10.Y)), x.vpos) > 20:
                    yield x.card(f" {x.k.user_name} had moved {dist_m((float(v10.X), float(v10.Y)), x.vpos):.0f} m in the last 10 s; your nearest teammate was " + (f"{nm[0]:.0f} m away." if nm else "not alive."))
