"""Had 4750 or more in the bank and under 3000 of equipment on a round the team full-bought."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._economy import freeze_economy
from ._context import Ctx
KIND = 'saved_with_money'
SIDE = 'mistake'
TITLE = 'Saved with money'
WHY = 'You had 4750 or more but under 3000 of equipment on a round where your team full-bought.'
DO = 'When the team buys, buy. Money in the bank does not shoot.'
BASE = 22


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        e = freeze_economy(c, R)
        if e and e.bal >= 4750 and e.my_eq < 3000 and e.avg >= 3500:
            yield c.card(R.rn, R.side, R.ft, 'spawn', e.spawn, facts=f"Round {R.rn+1}, {R.side}. You had ${e.bal} and ${e.my_eq} of equipment while your teammates averaged ${e.avg:.0f}.")
