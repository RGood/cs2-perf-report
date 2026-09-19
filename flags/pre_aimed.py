"""When the victim first came into my view within 35 m, my crosshair was already within 5 degrees of them."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx, ang, bearing, dist_m
KIND = 'pre_aimed'
SIDE = 'play'
TITLE = 'Pre-aimed'
WHY = ('When an enemy within 35 m first came into your view, your crosshair was already within 5° of them, and that fight '
       'ended in your kill.')
DO = 'Keep placing the crosshair on the exact spot before the swing.'
BASE = 12


def detect(c: Ctx) -> Iterator[Card | None]:
    me = c.me
    for R in c.rounds():
        for x in R.kills_of_mine():
            fs = c.first_seen(me, x.victim, x.t, 6.0)
            if fs is None: continue
            mr0 = c.row(fs, me); vr0 = c.row(fs, x.victim)
            if mr0 is not None and vr0 is not None and mr0['yaw'] == mr0['yaw'] and dist_m((float(mr0.X), float(mr0.Y)), (float(vr0.X), float(vr0.Y))) <= 35:
                off = ang(float(mr0['yaw']), bearing((float(mr0.X), float(mr0.Y)), (float(vr0.X), float(vr0.Y))))
                if off <= 5: yield x.card(f" When they first came into view ({c.rt(fs, R.rn)} s) your crosshair was {off:.0f}° off them.")
