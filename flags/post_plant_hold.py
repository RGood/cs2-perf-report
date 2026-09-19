"""T: survived 20 s or more after the plant while enemies were alive to retake."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._shared import first_plant
from ._context import Ctx
KIND = 'post_plant_hold'
SIDE = 'play'
TITLE = 'Post-plant hold'
WHY = 'After the plant you survived 20 s or more in a post-plant position while enemies were alive to retake.'
DO = 'Keep the post-plant positions that make the retake cost players.'
BASE = 35


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        p = first_plant(c, R)
        if not p or R.side != 'T': continue
        t_pl, bpos = p; rdm = R.my_deaths; rk = R.my_kills
        alive_at = (not len(rdm)) or int(rdm.iloc[0]['tick']) > t_pl + 20 * TICK
        ma0, fo0 = c.alive_counts(t_pl, R.team)
        if alive_at and fo0 and (t_pl + 20 * TICK) < R.end:
            k_after = rk[rk['tick'] > t_pl]; ex = c.D.get('exploded'); boom = ex is not None and len(ex) and ((ex['total_rounds_played'] == R.rn)).any()
            mr = c.row(t_pl + 20 * TICK, c.me)
            if mr is not None:
                yield c.card(R.rn, R.side, t_pl + 20 * TICK, str(mr['last_place_name']), (float(mr.X), float(mr.Y)), facts=f"Round {R.rn+1}, T, plant at {c.rt(t_pl, R.rn)} s with {fo0} enemies alive. You survived 20 s after it" + (f"; {len(k_after)} kill(s) followed" if len(k_after) else "") + (" and the bomb exploded." if boom else "."), extra_pos=bpos, extra_label='bomb')
