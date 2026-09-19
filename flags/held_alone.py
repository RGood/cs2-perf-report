"""Untraded death with two or more teammates alive while holding a spot alone for 10 s or more (not isolated by movement)."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from ._shared import isolated, by_movement, gap_text
from ._context import Ctx
KIND = 'held_alone'
SIDE = 'mistake'
KEEP_NEAR = True
TITLE = 'Died anchoring'
WHY = ('Sometimes unavoidable: the anchor dies when three players hit the site. It still costs the round when it happens '
       'early, without damage, or without a call.')
DO = ('Delay rather than duel: utility first, fall back to a crossfire spot, call the rotate at the first sound, and make '
      'them spend time on you.')
BASE = 26


def detect(c: Ctx) -> Iterator[Card | None]:
    for a in c.deaths_in_depth():
        if isolated(a) and not by_movement(a):
            yield a.card(gap_text(a) + " You had been in this area for at least 10 s with no teammate within 15 m.")


def adjust(m: Card, add: Add) -> None:
    if (m.get('foes_peak') or 0) >= 3: add(-5, 'outnumbered 3+ at the time')
