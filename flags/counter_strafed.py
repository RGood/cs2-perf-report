"""85% or more of my shots in the 4 s before my kill were fired standing still."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._weapons import wclass
from ._context import Ctx
KIND = 'counter_strafed'
SIDE = 'play'
TITLE = 'Counter-strafed engagement'
WHY = '85% or more of your engagement shots were fired while stationary (from your positions), and you got the kill.'
DO = 'Keep the stop-shoot-move rhythm.'
BASE = 10


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        rf = R.rf
        for x in R.kills_of_mine():
            g4 = rf[(rf['tick'] >= x.t - 4 * TICK) & (rf['tick'] <= x.t)]
            if len(g4) < 3: continue
            cls = wclass(x.k.weapon); thr = 90 if cls == 'smg' else 60
            still = sum(1 for r in g4.itertuples() if c.speed(c.coarse(int(r.tick)), c.me) <= thr)
            if still / len(g4) >= 0.85 and cls in ('rifle', 'smg', 'pistol'):
                yield x.card(f" {still} of your {len(g4)} shots in the last 4 s were fired standing still.")
