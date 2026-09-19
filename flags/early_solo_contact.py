"""T-side death before 20 s with nobody within 10 m and no damage dealt."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'early_solo_contact'
SIDE = 'mistake'
KEEP_NEAR = True
TITLE = 'Early solo T contact'
WHY = ('Contact before 20 s with nobody near you means the CT is set up and you are not. You had dealt no damage, so the round'
       ' started a man down with no information. Not counted when a teammate died in the same fight just before you, or when a'
       ' teammate had your killer in view.')
DO = "No contact in the first 20 s unless the team's utility has landed and a teammate is on your shoulder."
BASE = 32


def detect(c: Ctx) -> Iterator[Card | None]:
    for a in c.deaths_in_depth():
        if a.side == 'T' and a.tsec < 20 and a.near and a.near[0] > 10 and a.dmg_round == 0 and not a.shared and not a.mate_los:
            yield a.card()
