"""At first mutual sight I was moving and the killer was stationary with their crosshair already on me."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
import math
from constants import TICK, M
from ._context import Ctx, ang, bearing
KIND = 'swung_into_hold'
SIDE = 'mistake'
TITLE = 'Swung into a held angle'
WHY = ('When you and the killer first saw each other, you were moving and they were stationary with their crosshair already on'
       " you. That is the peeker's disadvantage against a set enemy.")
DO = "Either make them move first (utility, a teammate's peek, sound) or hold your own angle and let them swing you."
BASE = 38


def detect(c: Ctx) -> Iterator[Card | None]:
    for s in c.death_sightlines():
        if s.first_mutual is None: continue
        d = s.d; t = s.t; rn = s.rn
        ct, mr, kr = s.first_mutual
        dist = math.dist((mr.X, mr.Y), (kr.X, kr.Y)) * M
        my_v = c.speed(ct, c.me); k_v = c.speed(ct, s.K)
        k_aim = ang(float(kr['yaw']), bearing((kr.X, kr.Y), (mr.X, mr.Y)))
        if my_v > 120 and k_v < 30 and k_aim <= 20 and dist >= 8:
            yield dict(s.base, facts=f"Round {rn+1}, {s.side}, {c.rt(t, rn)} s. At {c.rt(ct, rn)} s you and {d.attacker_name} first saw each other at {dist:.0f} m: you were moving at {my_v:.0f} u/s, they were stationary at {d.attacker_last_place_name} with their crosshair {k_aim:.0f}° off you. You died {(t - ct) / TICK:.1f} s later.", k_aim=k_aim, my_v=my_v)


def adjust(m: Card, add: Add) -> None:
    add(5 if (m.get('k_aim') or 99) <= 8 else 0, 'they were already dead-on you')
