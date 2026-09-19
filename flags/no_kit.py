"""A CT full buy (3700 or more) without a defuse kit."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._economy import freeze_economy
from ._context import Ctx
KIND = 'no_kit'
SIDE = 'mistake'
TITLE = 'No defuse kit'
WHY = 'A CT full buy without a defuse kit. The kit halves the defuse time and wins post-plants.'
DO = 'Add the kit to every CT full buy. It is the cheapest round-winning item in the game.'
BASE = 8


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        e = freeze_economy(c, R)
        if e and R.side == 'CT' and e.my_eq >= 3700 and e.xr.has_defuser == False:
            yield c.card(R.rn, R.side, R.ft, 'spawn', e.spawn, facts=f"Round {R.rn+1}, CT. ${e.my_eq} of equipment and no defuse kit.")
