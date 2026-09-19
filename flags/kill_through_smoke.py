"""A kill through a smoke."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'kill_through_smoke'
SIDE = 'play'
RETIRED = "an outcome, not a decision"
TITLE = 'Kill through smoke'
WHY = 'Your kill went through a smoke.'
DO = 'Keep spraying the smoke lines when the enemy is likely to cross.'
BASE = 15


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.kills_of_mine():
            if bool(x.k.thrusmoke): yield x.card(" The shot went through a smoke.")
