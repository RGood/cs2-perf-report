"""Spent 3500 or more while the team averaged under 2000 of equipment."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._economy import freeze_economy
from ._context import Ctx
KIND = 'bought_vs_save'
SIDE = 'mistake'
TITLE = 'Bought against a team save'
WHY = ('You spent 3500 or more while your team averaged under 2000 of equipment. One rifle among pistols does not win the '
       'round; it loses a rifle.')
DO = 'Buy with the team. If the team saves, save.'
BASE = 25


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        e = freeze_economy(c, R)
        if e and e.spent >= 3500 and e.avg < 2000 and len(e.team_eq) >= 3:
            yield c.card(R.rn, R.side, R.ft, 'spawn', e.spawn, facts=f"Round {R.rn+1}, {R.side}. You spent ${e.spent} while your teammates averaged ${e.avg:.0f} of equipment.")
