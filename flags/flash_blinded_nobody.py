"""My flash popped with an enemy within 25 m of it and blinded no enemy for even half a second."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx, dist_m
from ._shared import my_pops, enemies_blinded
KIND = 'flash_blinded_nobody'
SIDE = 'mistake'
TITLE = 'Flash blinded nobody'
WHY = 'Your flashbang popped with an enemy within 25 m of it and blinded nobody on their team for even half a second.'
DO = "Pop flashes go over cover and behind the enemy's line of sight, not in front of them where they can turn away."
BASE = 8


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for t, lp, fo, mpos, mplace in my_pops(c, R, 'flashbang'):
            near = [f for f in fo.itertuples() if dist_m(lp, (float(f.X), float(f.Y))) <= 25]
            eb = enemies_blinded(c, R, t)
            if near and not len(eb) and len(c.blind):      # a demo with no blind events at all cannot say nobody was blinded
                yield c.card(R.rn, R.side, t, mplace, mpos, facts=f"Round {R.rn+1}, {R.side}, {c.rt(t, R.rn)} s. Your flash popped with {', '.join(str(f.name) for f in near[:3])} within 25 m and blinded nobody for half a second.", extra_pos=lp, extra_label='flash popped', nades_thrown=[('flashbang', mpos)])
