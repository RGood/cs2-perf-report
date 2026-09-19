"""Dropped the bomb and nobody picked it up for 15 s while I was alive and more than 10 m from it."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx, dist_m
KIND = 'bomb_abandoned'
SIDE = 'mistake'
TITLE = 'Bomb abandoned'
WHY = 'You dropped the bomb and nobody picked it up for 15 s while you were alive and more than 10 m away from it.'
DO = 'If you drop the bomb on purpose, call it. If it is dropped by accident, go back for it.'
BASE = 34


def detect(c: Ctx) -> Iterator[Card | None]:
    bd = c.D.get('bomb_drop'); bp = c.D.get('bomb_pick')
    if bd is None or not len(bd): return
    for R in c.rounds():
        rdm = R.my_deaths
        for r in bd[(bd['user_steamid'] == c.me) & (bd['tick'] >= R.ft) & (bd['tick'] < R.end)].itertuples():
            t = int(r.tick)
            picked = bp is not None and len(bp) and ((bp['tick'] > t) & (bp['tick'] <= t + 15 * TICK)).any()
            r15 = c.row(min(t + 15 * TICK, R.end - 1), c.me); dpos = (float(r.user_X), float(r.user_Y)) if r.user_X == r.user_X else None
            if not picked and dpos and r15 is not None and bool(r15['is_alive']) and dist_m((float(r15.X), float(r15.Y)), dpos) > 10 and (not len(rdm) or int(rdm.iloc[0]['tick']) > t + 15 * TICK):
                yield c.card(R.rn, R.side, t, str(r.user_last_place_name) if 'user_last_place_name' in bd.columns else None, dpos, facts=f"Round {R.rn+1}, T, {c.rt(t, R.rn)} s. You dropped the bomb here; nobody picked it up for 15 s while you were alive {dist_m((float(r15.X), float(r15.Y)), dpos):.0f} m away.", extra_pos=dpos, extra_label='bomb dropped')
