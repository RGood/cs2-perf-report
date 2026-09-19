"""A kill in the last 10 s of a lost round, with at most one teammate alive, on a victim carrying 2000 or more."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._shared import equip_at_kill
from ._context import Ctx
KIND = 'exit_frag'
SIDE = 'play'
RETIRED = "an outcome; clutch_exit_kills covers the decision"
TITLE = 'Exit frag'
WHY = ('A kill in the last 10 s of a lost round with at most one teammate alive, on a victim carrying 2000 or more: a weapon '
       'the enemy did not get to save.')
DO = 'Keep taking the exit kill when the round is gone.'
BASE = 25


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.kills_of_mine():
            eq = equip_at_kill(c, x); ma, fo = c.alive_counts(x.t - 1, R.team)
            if eq and not R.won and eq[1] >= 2000 and ma is not None and ma <= 2 and (R.end - x.t) / TICK <= 10:
                yield x.card(f" Round lost; {(R.end - x.t) / TICK:.0f} s before it ended, with {ma - 1} teammates alive, on a player carrying ${eq[1]}.")
