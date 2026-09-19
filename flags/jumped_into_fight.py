"""In the air at my death with the killer within 15 m."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'jumped_into_fight'
SIDE = 'mistake'
TITLE = 'Jumped into a fight'
WHY = ('You were off the ground (a jump, or a drop off a ledge) at the last tick you were alive, with the killer within 15 m. '
       'Read one tick before the death: at the death tick itself the demo marks about half of all dead players as airborne.')
DO = 'Jumping into a duel gives up accuracy and movement. Land first, then fight.'
BASE = 14


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.deaths_of_mine():
            xd = x.last        # at my last living tick; the death tick itself reads as airborne with no ammo
            if xd is not None and x.by_enemy and bool(xd.is_airborne) and x.dist <= 15:
                yield x.card(" You were in the air when you died.")
