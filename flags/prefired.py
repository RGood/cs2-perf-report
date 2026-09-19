"""My first hit on the victim came before or within 0.3 s of them becoming visible to me."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx
KIND = 'prefired'
SIDE = 'play'
TITLE = 'Pre-fired the angle'
WHY = 'Your first shot on the victim came before or within 0.3 s of them becoming visible to you, and it hit.'
DO = 'Keep pre-firing the common spots when you know someone is there.'
BASE = 16


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        rh = R.rh
        for x in R.kills_of_mine():
            fs = c.first_seen(c.me, x.victim, x.t, 6.0)
            if fs is None: continue
            hv = rh[(rh['user_steamid'] == x.victim) & (rh['tick'] >= fs - int(0.3 * TICK)) & (rh['tick'] <= x.t)]
            if len(hv):
                t_h = int(hv.iloc[0]['tick'])
                if t_h <= fs + int(0.3 * TICK): yield x.card(f" Your first hit on them came {(t_h - fs) / TICK:+.1f} s from the moment they became visible.")
