"""Killed a defuser during their defuse."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx
KIND = 'stopped_defuse'
SIDE = 'play'
RETIRED = "an outcome; the decision is measured by watched_bomb"
TITLE = 'Stopped the defuse'
WHY = 'You killed a defuser during their defuse.'
DO = 'Keep watching the bomb from a spot you can shoot it from.'
BASE = 55


def detect(c: Ctx) -> Iterator[Card | None]:
    db = c.D.get('defuse_begin'); dfd = c.D.get('defused')
    if db is None or not len(db): return
    for R in c.rounds():
        rn = R.rn
        for x in R.kills_of_mine():
            t = x.t
            vd = db[(db['total_rounds_played'] == rn) & (db['user_steamid'] == x.victim) & (db['tick'] <= t) & (db['tick'] >= t - 10 * TICK)]
            if len(vd) and not (dfd is not None and len(dfd) and ((dfd['total_rounds_played'] == rn) & (dfd['tick'] <= t) & (dfd['tick'] >= int(vd.iloc[-1]['tick']))).any()):
                yield x.card(f" They had started the defuse {(t - int(vd.iloc[-1]['tick'])) / TICK:.1f} s earlier.")
