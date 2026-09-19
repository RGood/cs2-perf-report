"""First death of the round on CT, before 30 s."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'lost_opener_ct'
SIDE = 'mistake'
RETIRED = "an outcome, not a decision"
TITLE = 'Lost CT opener'
WHY = ('First death of the round on CT hands the T side a numbers advantage before they have committed anywhere. It is the '
       'most expensive death in the round.')
DO = 'Hold passive angles in the first 30 s with a teammate covering you. Take information from utility, not from a peek.'
BASE = 50


def detect(c: Ctx) -> Iterator[Card | None]:
    for a in c.deaths_in_depth():
        if a.side == 'CT' and a.order == 1 and a.tsec < 30:
            yield a.card(" This was the first death of the round.")
