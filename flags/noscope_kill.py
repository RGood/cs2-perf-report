"""A sniper kill without the scope."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._weapons import wclass
from ._context import Ctx
KIND = 'noscope_kill'
SIDE = 'play'
RETIRED = "an outcome, not a decision"
TITLE = 'Noscope kill'
WHY = 'A sniper kill without the scope.'
DO = 'Keep it for the close fights where scoping would be too slow.'
BASE = 10


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.kills_of_mine():
            if bool(x.k.noscope) and wclass(x.k.weapon) == 'sniper': yield x.card(" No scope.")
