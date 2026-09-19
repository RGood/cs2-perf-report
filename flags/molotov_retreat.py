"""My molotov landed within 8 m of an enemy who then moved more than 5 m away from it or took damage within 3 s."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx, dist_m
from ._shared import my_pops
KIND = 'molotov_retreat'
SIDE = 'play'
RETIRED = "an outcome; the decision is measured by util_on_signal"
TITLE = 'Molotov forced a retreat'
WHY = ('Your molotov landed with an enemy within 8 m of it, and within 3 s they moved more than 5 m away from it or took '
       'damage.')
DO = 'Keep using fire to move enemies off the spots they hold.'
BASE = 15


def detect(c: Ctx) -> Iterator[Card | None]:
    hurt = c.hurt
    for R in c.rounds():
        for t, lp, fo, mpos, mplace in my_pops(c, R, 'molotov'):
            near = [f for f in fo.itertuples() if dist_m(lp, (float(f.X), float(f.Y))) <= 8]
            for f in near:
                d0 = dist_m(lp, (float(f.X), float(f.Y))); r3 = c.row(t + 3 * TICK, str(f.steamid))
                dmg = int(hurt[(hurt['attacker_steamid'] == c.me) & (hurt['user_steamid'] == str(f.steamid)) & (hurt['weapon'] == 'inferno') & (hurt['tick'] >= t) & (hurt['tick'] <= t + 3 * TICK)]['dmg_health'].sum())
                moved = (dist_m(lp, (float(r3.X), float(r3.Y))) - d0) if r3 is not None else 0
                if moved > 5 or dmg > 0:
                    yield c.card(R.rn, R.side, t, mplace, mpos, facts=f"Round {R.rn+1}, {R.side}, {c.rt(t, R.rn)} s. Your molotov landed {d0:.0f} m from {f.name}; within 3 s they " + (f"moved {moved:.0f} m away" if moved > 5 else f"took {dmg} damage") + ".", extra_pos=lp, extra_label='molotov', nades_thrown=[('molotov', mpos)], opponents=[(str(f.name), (float(f.X), float(f.Y)))])
                    break
