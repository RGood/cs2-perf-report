"""Killed between starting and finishing the plant."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._shared import my_unfinished_plant
from ._context import Ctx
KIND = 'died_planting'
SIDE = 'mistake'
RETIRED = "an outcome; the decision is measured by planted_without_cover"
TITLE = 'Died while planting'
WHY = 'You were killed between starting and finishing the plant.'
DO = 'Plant only when the angles are held or smoked. If an enemy is still watching the site, kill or smoke them first.'
BASE = 40


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.deaths_of_mine():
            t_pb = my_unfinished_plant(c, R, x)
            if t_pb is not None: yield x.card(f" You had started the plant {(x.t - t_pb) / TICK:.1f} s earlier.")
