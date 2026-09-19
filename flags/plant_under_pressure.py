"""Planted with an enemy alive within 25 m."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx, dist_m
from ._shared import my_plants
KIND = 'plant_under_pressure'
SIDE = 'play'
TITLE = 'Plant under pressure'
WHY = 'You planted with an enemy alive within 25 m.'
DO = 'Keep getting the plant down under pressure; it turns the round into a retake.'
BASE = 40


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for t, bpos in my_plants(c, R):
            g = c.by_tick.get(c.coarse(t)); near = [f for f in g[(g['team_num'] != R.team) & (g['is_alive'] == True)].itertuples() if dist_m(bpos, (float(f.X), float(f.Y))) <= 25] if g is not None else []
            if near: yield c.card(R.rn, R.side, t, 'bomb site', bpos, facts=f"Round {R.rn+1}, T, {c.rt(t, R.rn)} s. Planted with {', '.join(str(f.name) for f in near[:3])} within 25 m.", opponents=[(str(f.name), (float(f.X), float(f.Y))) for f in near[:3]])
