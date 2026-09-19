"""Died with 3700 or more of equipment to a player carrying under 1500."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'lost_full_buy_to_pistol'
SIDE = 'mistake'
RETIRED = "an outcome, not a decision"
TITLE = 'Lost a full buy to a pistol'
WHY = 'You died with 3700 or more of equipment to a player with under 1500. The eco player took your rifle.'
DO = 'Against pistols hold range, hold together, and do not peek into a doorway where a pistol can get close.'
BASE = 20


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.deaths_of_mine():
            mr = c.row(x.t - 1, c.me); kr = c.row(x.t - 1, x.killer) if x.killer else None
            if mr is not None and kr is not None and x.by_enemy:
                my_eq = int(mr['current_equip_value']) if mr['current_equip_value'] == mr['current_equip_value'] else 0
                k_eq = int(kr['current_equip_value']) if kr['current_equip_value'] == kr['current_equip_value'] else 0
                if my_eq >= 3700 and k_eq < 1500:
                    yield x.card(f" You carried ${my_eq} of equipment; they carried ${k_eq}.", equip=my_eq)
