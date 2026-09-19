"""A kill while my team had one fewer alive than theirs."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'kill_down_a_man'
SIDE = 'play'
RETIRED = "an outcome, not a decision"
TITLE = 'Kill while down a man'
WHY = 'Your kill came while your team had fewer players alive than theirs, and it evened or flipped the count.'
DO = 'Keep finding the fight that resets the round when the team is behind.'
BASE = 40


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.kills_of_mine():
            ma, fo = c.alive_counts(x.t - 1, R.team)
            if ma is not None and fo is not None and ma < fo and ma >= fo - 1:
                yield x.card(f" Your team was {ma} to {fo} before it; {ma} to {fo - 1} after.")
