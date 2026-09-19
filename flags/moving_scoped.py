"""Fired a scoped AWP or Scout shot while moving faster than 50 u/s."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._weapons import wkey
from ._context import Ctx
KIND = 'moving_scoped'
SIDE = 'mistake'
TITLE = 'Moving scoped shot'
WHY = 'You fired a scoped sniper shot while moving. A moving scoped shot is almost random.'
DO = 'Stop fully before the shot, or unscope and reposition.'
BASE = 18


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        rf = R.rf
        for r in rf[rf['weapon'].str.contains('awp|ssg08', na=False)].itertuples():
            t = int(r.tick); xr2 = c.x(t, c.me)
            if xr2 is not None and bool(xr2.is_scoped) and c.speed(c.coarse(t), c.me) > 50 and r.user_X == r.user_X:
                yield c.card(R.rn, R.side, t, str(r.user_last_place_name), (float(r.user_X), float(r.user_Y)), facts=f"Round {R.rn+1}, {R.side}, {c.rt(t, R.rn)} s. A scoped {wkey(r.weapon)} shot while moving at {c.speed(c.coarse(t), c.me):.0f} u/s.")
