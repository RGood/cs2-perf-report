"""CT post-plant: my smoke landed within 12 m of the bomb and a teammate or I entered the site within 8 s of it."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx, dist_m
from ._shared import first_plant
KIND = 'retake_smoke'
SIDE = 'play'
TITLE = 'Smoke for the retake'
WHY = 'CT post-plant: your smoke landed within 12 m of the bomb and your team entered the site within 8 s of it.'
DO = 'Keep leading the retake with the smoke.'
BASE = 15


def detect(c: Ctx) -> Iterator[Card | None]:
    dt = c.deton
    for R in c.rounds():
        p = first_plant(c, R)
        if not p or R.side == 'T': continue
        t_pl, bpos = p
        sm = dt[(dt['steamid'] == c.me) & (dt['kind'] == 'smokegrenade') & (dt['tick'] > t_pl) & (dt['tick'] < R.end)] if len(dt) else dt
        for s_ in sm.itertuples():
            sp = (float(s_.x), float(s_.y))
            if dist_m(sp, bpos) > 12: continue
            entered = None
            for ct in range(c.coarse(int(s_.tick)), int(s_.tick) + 8 * TICK, 16):
                g = c.by_tick.get(ct)
                if g is None: continue
                for m_ in g[(g['team_num'] == R.team) & (g['is_alive'] == True)].itertuples():
                    if dist_m((float(m_.X), float(m_.Y)), bpos) <= 15: entered = (ct, str(m_.name)); break
                if entered: break
            if entered:
                yield c.card(R.rn, R.side, int(s_.tick), 'bomb site', sp, facts=f"Round {R.rn+1}, CT, {c.rt(int(s_.tick), R.rn)} s. Your smoke landed {dist_m(sp, bpos):.0f} m from the bomb; {entered[1]} entered the site {(entered[0] - int(s_.tick)) / TICK:.0f} s later.", extra_pos=bpos, extra_label='bomb', nades_thrown=[('smokegrenade', sp)])
