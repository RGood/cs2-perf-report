"""Killed a player carrying 3700 or more while carrying under 1500."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._shared import equip_at_kill
from ._context import Ctx
KIND = 'killed_full_buy_on_eco'
SIDE = 'play'
RETIRED = "an outcome, not a decision"
TITLE = 'Killed a full buy on eco'
WHY = 'You killed a player carrying 3700 or more of equipment while carrying under 1500.'
DO = 'Keep taking the eco fights up close, where the pistol wins.'
BASE = 30


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.kills_of_mine():
            eq = equip_at_kill(c, x)
            if eq and eq[1] >= 3700 and eq[0] < 1500: yield x.card(f" They carried ${eq[1]}; you carried ${eq[0]}.")
