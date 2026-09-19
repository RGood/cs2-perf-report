"""Bursts or taps (the right pattern) at enemies 20 m or more away that still did almost no damage and got no kill."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from constants import SPRAY_RUN
from ._shared import missed_at_range, miss_card
from ._context import Ctx
KIND = 'missed_at_range'
SIDE = 'mistake'
TITLE = 'Bursts missed at range'
WHY = ('You fired in bursts or taps, which is the right pattern, and still did 20 damage or less to anyone, with no kill, at '
       'enemies 20 m or more away. That is not spray control. It is the first bullets of each burst missing: crosshair '
       'placement before the peek, or the burst starting before the crosshair is on the target.')
DO = ('Crosshair at head height on the exact corner before you swing it. Start the burst only when the crosshair is on the '
      'body, not while it is still moving. Yprac prefire and far-wall one-taps target this.')
BASE = 26


def detect(c: Ctx) -> Iterator[Card | None]:
    for a in c.deaths_in_depth():
        if missed_at_range(a) and a.longest < SPRAY_RUN: yield miss_card(a)


def adjust(m: Card, add: Add) -> None:
    if (m.get('foes_peak') or 0) >= 3: add(-5, 'outnumbered 3+ at the time')
