"""Started a reload within 2.5 s of dying and never fired again."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx
KIND = 'died_reloading'
SIDE = 'mistake'
TITLE = 'Died reloading'
WHY = 'You reloaded within 2.5 s of your death and did not fire again before it.'
DO = 'Reload behind cover, and only when the enemy is not about to peek. In contact, switch to the pistol.'
BASE = 32


def detect(c: Ctx) -> Iterator[Card | None]:
    rl_all = c.D.get('reloads')
    for R in c.rounds():
        rf = R.rf
        for x in R.deaths_of_mine():
            t = x.t
            rl = rl_all[(rl_all['user_steamid'] == c.me) & (rl_all['tick'] >= t - int(2.5 * TICK)) & (rl_all['tick'] < t)] if rl_all is not None and len(rl_all) else None
            if rl is not None and len(rl) and x.by_enemy:
                t_rl = int(rl.iloc[-1]['tick'])
                if not len(rf[(rf['tick'] > t_rl) & (rf['tick'] <= t)]):
                    yield x.card(f" You started a reload {(t - t_rl) / TICK:.1f} s before dying and never fired again.")
