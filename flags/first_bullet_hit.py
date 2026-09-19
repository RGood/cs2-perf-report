"""My first shot of the engagement (the 4 s before my kill) hit an enemy."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._weapons import wclass
from ._context import Ctx
KIND = 'first_bullet_hit'
SIDE = 'play'
TITLE = 'First bullet hit'
WHY = 'Your first shot in the engagement hit an enemy.'
DO = 'Keep making the first bullet count: stop, place, fire.'
BASE = 10


def detect(c: Ctx) -> Iterator[Card | None]:
    hurt = c.hurt
    for R in c.rounds():
        rf = R.rf
        for x in R.kills_of_mine():
            g4 = rf[(rf['tick'] >= x.t - 4 * TICK) & (rf['tick'] <= x.t)]
            if not len(g4): continue
            f0 = g4.iloc[0]; hit0 = hurt[(hurt['total_rounds_played'] == R.rn) & (hurt['attacker_steamid'] == c.me) & ((hurt['tick'] - int(f0['tick'])).abs() <= 1) & (hurt['user_steamid'].isin(R.foes))]
            if len(hit0) and wclass(f0['weapon']) != 'other':
                yield x.card(f" Your first shot of the engagement ({c.rt(int(f0['tick']), R.rn)} s) hit {hit0.iloc[0]['user_name']}.")
