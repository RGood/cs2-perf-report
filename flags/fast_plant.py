"""Planted before 35 s of round time."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._shared import my_plants
from ._context import Ctx
KIND = 'fast_plant'
SIDE = 'play'
RETIRED = "an outcome, not a decision"
TITLE = 'Fast plant'
WHY = 'You planted before 35 s of round time.'
DO = 'Keep the fast hits when the read is right.'
BASE = 10


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for t, bpos in my_plants(c, R):
            if c.rt(t, R.rn) < 35: yield c.card(R.rn, R.side, t, 'bomb site', bpos, facts=f"Round {R.rn+1}, T, {c.rt(t, R.rn)} s. Planted at {c.rt(t, R.rn)} s.")
