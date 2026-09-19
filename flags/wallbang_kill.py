"""A kill through a surface."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'wallbang_kill'
SIDE = 'play'
RETIRED = "an outcome, not a decision"
TITLE = 'Wallbang kill'
WHY = 'Your kill went through a surface.'
DO = 'Keep punishing the common wallbang spots.'
BASE = 15


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.kills_of_mine():
            if int(x.k.penetrated or 0) > 0: yield x.card(" The shot went through a surface.")
