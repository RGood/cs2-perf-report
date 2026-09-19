"""100 or more damage in a round I also survived."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from ._shared import round_end_spot
from ._context import Ctx
KIND = 'survived_damage'
SIDE = 'play'
RETIRED = "an outcome, not a decision"
TITLE = 'High damage, survived'
WHY = ('100 or more damage in a round you also survived. Damage without a death is the best possible round for the economy and'
       ' the numbers.')
DO = 'Keep taking fights from positions where losing the first exchange does not mean dying.'
BASE = 25


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        spot = round_end_spot(c, R)
        if spot and not R.died and R.dmg_to_enemies >= 100:
            et, lp, place = spot
            yield R.play(et, lp, None, None, f"Round {R.rn+1}, {R.side}. {R.dmg_to_enemies} damage, {len(R.all_my_kills)} kills, survived the round.", place=place, dmg=R.dmg_to_enemies)


def adjust(m: Card, add: Add) -> None:
    add(min(10, int((m.get('dmg') or 0) // 40)), f"{m.get('dmg')} damage")
