"""Killed from 15 m or less by a player who was in the air."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'died_to_jumper'
SIDE = 'mistake'
RETIRED = "an outcome, not a decision"
TITLE = 'Died to a jumping player'
WHY = 'Your killer was airborne when they killed you at close range: a jump peek you did not punish.'
DO = 'Hold the crosshair where the jump lands, not where it starts, and shoot as they land.'
BASE = 10


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.deaths_of_mine():
            if bool(x.d.attackerinair) and x.dist <= 15 and x.by_enemy:
                yield x.card(" Your killer was in the air when they fired.")
