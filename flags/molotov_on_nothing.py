"""After contact, my molotov burned out with no enemy ever within 12 m of it."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx, dist_m
from ._shared import my_pops
KIND = 'molotov_on_nothing'
SIDE = 'mistake'
TITLE = 'Molotov on nothing'
WHY = ('Your molotov burned for its whole duration with no enemy within 12 m of it, thrown after your team had already seen '
       'the enemy.')
DO = 'After contact, throw the molotov where the enemy is or must pass, not where they might have been.'
BASE = 14


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        contact_t = R.first_contact_tick
        for t, lp, fo, mpos, mplace in my_pops(c, R, 'molotov'):
            if not (contact_t is not None and t > contact_t): continue
            fxr = c.fx[(c.fx['kind'] == 'molotov') & ((c.fx['tick'] - t).abs() <= 2)]
            e_t = int(fxr.iloc[0]['end']) if len(fxr) else t + 7 * TICK
            close = False
            for ct in range(c.coarse(t), e_t, 16):
                g2 = c.by_tick.get(ct)
                if g2 is None: continue
                if any(dist_m(lp, (float(f.X), float(f.Y))) <= 12 for f in g2[(g2['team_num'] != R.team) & (g2['is_alive'] == True)].itertuples()): close = True; break
            if not close:
                yield c.card(R.rn, R.side, t, mplace, mpos, facts=f"Round {R.rn+1}, {R.side}, {c.rt(t, R.rn)} s. Your molotov burned {(e_t - t) / TICK:.0f} s with no enemy within 12 m, thrown {(t - contact_t) / TICK:.0f} s after your team first saw the enemy.", extra_pos=lp, extra_label='molotov', nades_thrown=[('molotov', mpos)])
