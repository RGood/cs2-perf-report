"""My first shot of the engagement was aimed at a visible enemy, hit nothing, and I lost the duel."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx, ang, bearing
from ._weapons import wclass, wkey
KIND = 'first_bullet_missed'
SIDE = 'mistake'
TITLE = 'First bullet missed'
WHY = ('Your first shot in the engagement was aimed at a visible enemy, hit nothing, and you lost the duel. The first bullet '
       'is the one fired with the most accuracy and the most surprise.')
DO = 'Slow the first shot down: counter-strafe to a full stop and place it, then let the spray or burst follow.'
BASE = 10


def detect(c: Ctx) -> Iterator[Card | None]:
    hurt = c.hurt
    for R in c.rounds():
        rf = R.rf
        for x in R.deaths_of_mine():
            g4 = rf[(rf['tick'] >= x.t - 4 * TICK) & (rf['tick'] <= x.t)]
            if not (len(g4) and x.by_enemy): continue
            f0 = g4.iloc[0]; hit0 = hurt[(hurt['total_rounds_played'] == R.rn) & (hurt['attacker_steamid'] == c.me) & ((hurt['tick'] - int(f0['tick'])).abs() <= 1)]
            aimed0 = False      # within 12 degrees of an enemy my team had spotted
            g_ = c.by_tick.get(c.coarse(int(f0['tick'])))
            if g_ is not None and f0['user_yaw'] == f0['user_yaw'] and f0['user_X'] == f0['user_X']:
                for f_ in g_[(g_['team_num'] != R.team) & (g_['is_alive'] == True) & (g_['spotted'] == True)].itertuples():
                    if ang(float(f0['user_yaw']), bearing((float(f0['user_X']), float(f0['user_Y'])), (float(f_.X), float(f_.Y)))) < 12: aimed0 = True; break
            if not len(hit0) and aimed0 and wclass(f0['weapon']) != 'other':
                yield x.card(f" Your first shot of the engagement ({wkey(f0['weapon'])}, {c.rt(int(f0['tick']), R.rn)} s) hit nothing.")
