"""Bought an SMG as the primary with 3000 or more of equipment while the team averaged a full buy."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._economy import freeze_economy
from ._weapons import wclass
from ._context import Ctx
KIND = 'smg_full_buy'
SIDE = 'mistake'
TITLE = 'SMG on a full-buy round'
WHY = ('You bought an SMG as your primary with 3000 or more of equipment while your team averaged a full buy. Against rifles '
       'at range that is a losing duel every time.')
DO = 'On a full buy, buy the rifle. Save the SMG for anti-eco and force rounds.'
BASE = 16


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        e = freeze_economy(c, R)
        if e and e.my_eq >= 3000 and e.avg >= 4000 and e.prim and all(wclass(w) == 'smg' for w in e.prim):
            yield c.card(R.rn, R.side, R.ft, 'spawn', e.spawn, facts=f"Round {R.rn+1}, {R.side}. You bought {', '.join(e.prim)} with ${e.my_eq} of equipment while your teammates averaged ${e.avg:.0f}.")
