"""Died carrying the bomb before 30 s, away from both sites, with no plant started."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'bomb_died_with_me'
SIDE = 'mistake'
TITLE = 'Bomb died with me'
WHY = 'You died carrying the bomb before 30 s, away from either site, with no plant started.'
DO = 'The bomb carrier goes in behind the entry players, never first. If you take the first fight, hand the bomb off.'
BASE = 45


def detect(c: Ctx) -> Iterator[Card | None]:
    pb = c.D.get('plant_begin')
    for R in c.rounds():
        if R.side != 'T': continue
        for x in R.deaths_of_mine():
            mr = c.row(x.t - 1, c.me)
            try: inv = [str(w) for w in (mr['inventory'] if mr is not None else [])]
            except TypeError: inv = []
            if any('c4' in w.lower() for w in inv) and c.rt(x.t, R.rn) < 30 and x.place not in ('BombsiteA', 'BombsiteB'):
                started = pb is not None and len(pb) and ((pb['total_rounds_played'] == R.rn) & (pb['tick'] <= x.t)).any()
                if not started: yield x.card(" You were carrying the bomb, away from both sites, and no plant had started.")
