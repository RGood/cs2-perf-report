"""Crouched at death, visible to the killer for a second or more, killed from 15 m or more."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx
KIND = 'crouch_peek_rifle'
SIDE = 'mistake'
TITLE = 'Crouch-peeked into a rifle'
WHY = 'You were crouched at death, visible to your killer for a second or more, killed from 15 m or more.'
DO = 'Crouching in the open only makes you a slower target. Crouch behind cover, never in a lane.'
BASE = 14


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.deaths_of_mine():
            xd = x.last        # at my last living tick; the death tick itself reads as airborne with no ammo
            if xd is not None and x.by_enemy and bool(xd.ducking) and x.dist >= 15:
                fs = c.first_seen(x.killer, c.me, x.t, 6.0)
                if fs is not None and (x.t - fs) / TICK >= 1.0:
                    yield x.card(f" You were crouched, visible to them for {(x.t - fs) / TICK:.1f} s.")
