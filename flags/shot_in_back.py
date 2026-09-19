"""At my death I was looking more than 100 degrees away from my killer."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx, ang, bearing
KIND = 'shot_in_back'
SIDE = 'mistake'
TITLE = 'Shot in the back'
WHY = ('At your death you were looking more than 100° away from your killer. The flank was not covered and nobody was watching'
       ' it.')
DO = 'Clear behind you before you commit forward, and ask a teammate to watch the flank you cannot.'
BASE = 30


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.deaths_of_mine():
            mr = c.row(x.t, c.me)
            if mr is not None and x.kpos and mr['yaw'] == mr['yaw'] and x.by_enemy:
                off = ang(float(mr['yaw']), bearing(x.pos, x.kpos))
                if off > 100: yield x.card(f" You were looking {off:.0f}° away from your killer.")
