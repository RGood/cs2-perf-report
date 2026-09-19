"""T: my smoke landed within 10 m of the plant spot in the 10 s before the plant."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx, dist_m
from ._shared import first_plant
KIND = 'plant_smoke'
SIDE = 'play'
TITLE = 'Plant smoke'
WHY = 'Your smoke landed within 10 m of the plant spot in the 10 s before the plant.'
DO = 'Keep smoking the plant.'
BASE = 15


def detect(c: Ctx) -> Iterator[Card | None]:
    dt = c.deton
    for R in c.rounds():
        p = first_plant(c, R)
        if not p or R.side != 'T': continue
        t_pl, bpos = p
        sm = dt[(dt['steamid'] == c.me) & (dt['kind'] == 'smokegrenade') & (dt['tick'] >= t_pl - 10 * TICK) & (dt['tick'] <= t_pl)] if len(dt) else dt
        for s_ in sm.itertuples():
            sp = (float(s_.x), float(s_.y))
            if dist_m(sp, bpos) <= 10:
                yield c.card(R.rn, R.side, int(s_.tick), 'bomb site', sp, facts=f"Round {R.rn+1}, T, {c.rt(int(s_.tick), R.rn)} s. Your smoke landed {dist_m(sp, bpos):.0f} m from the plant spot, {(t_pl - int(s_.tick)) / TICK:.0f} s before the plant.", extra_pos=bpos, extra_label='plant', nades_thrown=[('smokegrenade', sp)])
