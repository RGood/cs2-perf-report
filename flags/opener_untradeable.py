"""First death of the round with no teammate within 15 m and no trade within 5 s."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'opener_untradeable'
SIDE = 'mistake'
TITLE = 'Untradeable opener'
WHY = ("You were the round's first death with no teammate within 15 m, and nobody traded you within 5 s. The opening duel was "
       'taken from a spot where losing it cost a full player.')
DO = 'Take the first fight of the round inside trade range, or take it with utility so a loss still gives information.'
BASE = 42


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.deaths_of_mine():
            if x.first_death and x.by_enemy and not x.traded and (x.nm is None or x.nm[0] > 15):
                nm = x.nm
                yield x.card(f" First death of the round; nearest teammate {nm[0]:.0f} m away ({nm[1]}); nobody traded you within 5 s." if nm else " First death of the round with no teammate alive nearby; not traded.")
