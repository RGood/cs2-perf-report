"""When the killer first came into my view within 35 m, my crosshair was more than 15 degrees off them."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx, ang, bearing, dist_m
KIND = 'crosshair_off'
SIDE = 'mistake'
TITLE = 'Crosshair off at first sight'
WHY = ('When an enemy within 35 m first came into your view, your crosshair was more than 15° away from them, and that fight '
       'ended in a kill or death.')
DO = ('Pre-aim the exact spot where the enemy will appear before you swing; moving the crosshair after you see them is the '
      'slowest way to start a duel.')
BASE = 12


def detect(c: Ctx) -> Iterator[Card | None]:
    me = c.me
    for R in c.rounds():
        for x in R.deaths_of_mine():
            if not x.by_enemy: continue
            fs = c.first_seen(me, x.killer, x.t, 6.0)
            if fs is None: continue
            mr0 = c.row(fs, me); kr0 = c.row(fs, x.killer)
            if mr0 is not None and kr0 is not None and mr0['yaw'] == mr0['yaw'] and dist_m((float(mr0.X), float(mr0.Y)), (float(kr0.X), float(kr0.Y))) <= 35:
                off = ang(float(mr0['yaw']), bearing((float(mr0.X), float(mr0.Y)), (float(kr0.X), float(kr0.Y))))
                if off > 15: yield x.card(f" When {x.d.attacker_name} first came into view ({c.rt(fs, R.rn)} s, {dist_m((float(mr0.X), float(mr0.Y)), (float(kr0.X), float(kr0.Y))):.0f} m) your crosshair was {off:.0f}° off them.")
