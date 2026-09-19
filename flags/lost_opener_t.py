"""First death of the round on the T side."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'lost_opener_t'
SIDE = 'mistake'
RETIRED = "an outcome, not a decision"
TITLE = 'Lost T opener'
WHY = 'First death of the round on the T side. The attack starts a man down before any map control is taken.'
DO = 'Open with utility and a teammate on your shoulder, or let a teammate with a better angle take the first duel.'
BASE = 45


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.deaths_of_mine():
            if x.first_death and x.by_enemy and R.side == 'T':
                yield x.card(" This was the first death of the round.", order=1)
