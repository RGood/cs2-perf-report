"""Started the defuse with less time on the bomb than the defuse takes."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx
KIND = 'defuse_too_late'
SIDE = 'mistake'
TITLE = 'Defuse started too late'
WHY = 'You started the defuse with less time on the bomb than the defuse takes (10 s, 5 with a kit).'
DO = 'Know the bomb time. If the defuse cannot finish, save the weapon and leave.'
BASE = 18

BOMB_S = 40.0


def detect(c: Ctx) -> Iterator[Card | None]:
    db = c.D.get('defuse_begin')
    if db is None or not len(db): return
    for R in c.rounds():
        for r in db[(db['user_steamid'] == c.me) & (db['tick'] >= R.ft) & (db['tick'] < R.end)].itertuples():
            t = int(r.tick); pl = c.plant[(c.plant['total_rounds_played'] == R.rn) & (c.plant['tick'] < t)]
            if not len(pl): continue
            left = BOMB_S - (t - int(pl.iloc[-1]['tick'])) / TICK; need = 5.0 if bool(r.haskit) else 10.0
            if left < need:
                mr = c.row(t, c.me)
                yield c.card(R.rn, R.side, t, str(mr['last_place_name']) if mr is not None else None, (float(mr.X), float(mr.Y)) if mr is not None else None, facts=f"Round {R.rn+1}, CT, {c.rt(t, R.rn)} s. You started the defuse with {left:.1f} s on the bomb; the defuse takes {need:.0f} s" + (" with a kit." if bool(r.haskit) else " without a kit."))
