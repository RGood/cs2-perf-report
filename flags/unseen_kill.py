"""At my kill the victim was looking more than 90 degrees away from me."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx, ang, bearing
KIND = 'unseen_kill'
SIDE = 'play'
RETIRED = "an outcome; the decision is measured at first damage by attacked_off_view"
TITLE = 'Unseen kill'
WHY = 'At your kill the victim was looking more than 90° away from you.'
DO = 'Keep taking the angles the enemy is not watching.'
BASE = 12


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.kills_of_mine():
            vr = c.row(x.t - 1, x.victim)
            if vr is not None and x.vpos and vr['yaw'] == vr['yaw']:
                off = ang(float(vr['yaw']), bearing(x.vpos, x.pos))
                if off > 90: yield x.card(f" They were looking {off:.0f}° away from you.")
