"""Died within the first 10 s of the round."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'instant_death'
SIDE = 'mistake'
RETIRED = "an outcome, not a decision"
TITLE = 'Instant death'
WHY = 'You died within the first 10 s of the round.'
DO = 'Nothing is gained in the first 10 s that is worth a player. Take the first fight with utility or a teammate.'
BASE = 18


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.deaths_of_mine():
            if c.rt(x.t, R.rn) < 10 and x.by_enemy:
                yield x.card(f" Only {c.rt(x.t, R.rn)} s into the round.")
