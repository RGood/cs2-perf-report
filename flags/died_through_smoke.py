"""Killed by a shot that came through a smoke."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'died_through_smoke'
SIDE = 'mistake'
TITLE = 'Died through smoke'
WHY = 'You were killed by a shot through a smoke. Standing where a smoke can be sprayed is a free kill for the enemy.'
DO = 'Never stand in the line a smoke covers unless you are the one shooting it. Cross it, or hold off it.'
BASE = 16


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.deaths_of_mine():
            if bool(x.d.thrusmoke) and x.by_enemy:
                yield x.card(" The killing shot came through a smoke.")
