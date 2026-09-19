"""A continuous spray at enemies 20 m or more away that did almost no damage and got no kill."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from constants import SPRAY_RUN
from ._shared import missed_at_range, miss_card
from ._context import Ctx
KIND = 'spray_at_range'
SIDE = 'mistake'
TITLE = 'Long-distance spray missed'
WHY = ("Only counted when the shots in the 4 s before the death include a continuous run of 7 or more at the weapon's cycle "
       'rate, aimed at enemies 20 m or more away, and those shots did 20 damage or less to anyone and got no kill. Shots that '
       'hit someone else are not misses. Bursts and taps are a different flag.')
DO = 'Past 20 m fire 2 to 3 bullets, stop, counter-strafe, fire again. Never more than 4 without a reset.'
BASE = 24


def detect(c: Ctx) -> Iterator[Card | None]:
    for a in c.deaths_in_depth():
        if missed_at_range(a) and a.longest >= SPRAY_RUN: yield miss_card(a)


def adjust(m: Card, add: Add) -> None:
    if (m.get('foes_peak') or 0) >= 3: add(-5, 'outnumbered 3+ at the time')
