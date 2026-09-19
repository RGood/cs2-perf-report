"""Defused with at least one enemy still alive."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._shared import my_defuses
from ._context import Ctx
KIND = 'defused_under_fire'
SIDE = 'play'
RETIRED = "an outcome; the decision is measured by committed_defuse"
TITLE = 'Defused under fire'
WHY = 'You defused with at least one enemy still alive.'
DO = 'Keep committing to the defuse when the team has cleared enough.'
BASE = 55


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for t, fo, mr, mpos in my_defuses(c, R):
            if fo: yield c.card(R.rn, R.side, t, str(mr['last_place_name']), mpos, facts=f"Round {R.rn+1}, CT, {c.rt(t, R.rn)} s. Defused with {fo} enemies alive.")
