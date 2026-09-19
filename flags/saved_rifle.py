"""Survived a lost round with 1000 or more of equipment (not a T who let the clock run out)."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from ._shared import round_end_spot
from ._context import Ctx
KIND = 'saved_rifle'
SIDE = 'play'
TITLE = 'Saved equipment'
WHY = ('You survived a lost round and kept your equipment for the next one. Worth a little, more the more you kept. Not '
       'counted for a T who let the clock run out, which forfeits the loss bonus.')
DO = 'Keep making the save call early enough to actually get out with the gun.'
BASE = 12


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        spot = round_end_spot(c, R)
        if not spot: continue
        timed_out = c.D.get('round_reason', {}).get(R.rn) in ('target_saved', 'time_ran_out')       # a T alive at the time-out forfeits the loss bonus
        if not R.died and not R.won and R.equip0 >= 1000 and not (R.side == 'T' and timed_out):
            et, lp, place = spot
            yield R.play(et, lp, None, None, f"Round {R.rn+1}, {R.side}. Round lost, you survived with ${R.equip0} of equipment bought at freeze time, kept for the next round.", place=place, saved=R.equip0)


def adjust(m: Card, add: Add) -> None:
    add(min(14, int((m.get('saved') or 0) // 350)), f"${m.get('saved')} of equipment kept")
