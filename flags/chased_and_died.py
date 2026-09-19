"""After a kill, pushed more than 15 m toward the remaining enemies within 5 s and died."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx, dist_m
KIND = 'chased_and_died'
SIDE = 'mistake'
TITLE = 'Chased and died'
WHY = 'After a kill you pushed more than 15 m toward the remaining enemies within 5 s and died.'
DO = 'After a kill, reset. The enemy knows where you are; let them come to you or re-peek with a teammate.'
BASE = 34


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        rk = R.my_kills
        for x in R.deaths_of_mine():
            t = x.t
            mk = rk[(rk['tick'] < t) & (rk['tick'] >= t - 5 * TICK)]
            if not (len(mk) and x.by_enemy): continue
            k0 = mk.iloc[-1]; p0 = (float(k0['attacker_X']), float(k0['attacker_Y'])) if k0['attacker_X'] == k0['attacker_X'] else None
            g = c.by_tick.get(c.coarse(int(k0['tick'])))
            if p0 and g is not None:
                fo = g[(g['team_num'] != R.team) & (g['is_alive'] == True) & (g['steamid'] != str(k0['user_steamid']))]
                if len(fo):
                    cen = (float(fo['X'].mean()), float(fo['Y'].mean()))
                    adv = dist_m(p0, cen) - dist_m(x.pos, cen)
                    if adv > 15: yield x.card(f" {(t - int(k0['tick'])) / TICK:.1f} s after killing {k0['user_name']} you had pushed {adv:.0f} m toward the remaining enemies.")
