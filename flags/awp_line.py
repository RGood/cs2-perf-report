"""Killed by a sniper from 30 m or more within 2 s of first becoming visible to them."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._weapons import wclass
from ._context import Ctx
KIND = 'awp_line'
SIDE = 'mistake'
TITLE = 'Walked into an AWP line'
WHY = 'You died to a sniper from 30 m or more within 2 s of first becoming visible to them.'
DO = 'Know the AWP lines on every map and cross them behind a smoke or after the shot.'
BASE = 28


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.deaths_of_mine():
            if wclass(x.d.weapon) == 'sniper' and x.dist >= 30 and x.by_enemy:
                fs = c.first_seen(x.killer, c.me, x.t, 6.0)
                if fs is not None and (x.t - fs) / TICK <= 2.0:
                    yield x.card(f" You had been visible to them for {(x.t - fs) / TICK:.1f} s.")
