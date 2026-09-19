"""Killed the planter between the start and the end of the plant."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx
KIND = 'killed_planter'
SIDE = 'play'
RETIRED = "an outcome; the decision is measured by held_plant_spot"
TITLE = 'Killed the planter'
WHY = 'You killed the planter between the start and the end of the plant.'
DO = 'Keep holding the plant spot rather than the site entrance.'
BASE = 45


def detect(c: Ctx) -> Iterator[Card | None]:
    pb = c.D.get('plant_begin'); plant = c.plant
    if pb is None or not len(pb): return
    for R in c.rounds():
        rn = R.rn
        for x in R.kills_of_mine():
            t = x.t
            vp = pb[(pb['total_rounds_played'] == rn) & (pb['user_steamid'] == x.victim) & (pb['tick'] <= t) & (pb['tick'] >= t - 4 * TICK)]
            planted = plant[(plant['total_rounds_played'] == rn) & (plant['tick'] <= t) & (plant['tick'] >= (int(vp.iloc[-1]['tick']) if len(vp) else t))]
            if len(vp) and not len(planted): yield x.card(f" They had started the plant {(t - int(vp.iloc[-1]['tick'])) / TICK:.1f} s earlier.")
