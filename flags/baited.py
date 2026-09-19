"""A teammate died within 10 m of me while I was unspotted; I did not fire within 3 s and moved away from them."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx, dist_m
from ._shared import mate_deaths_nearby
KIND = 'baited'
SIDE = 'mistake'
TITLE = 'Baited a teammate'
WHY = ('A teammate died within 10 m of you while you were unspotted, you did not fire within 3 s, and you moved away from '
       'them.')
DO = 'If you are close enough to be a trade partner, be one. Moving away after their death is the definition of a bait.'
BASE = 42


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        rf = R.rf
        for d, mr, mpos, dpos, dm in mate_deaths_nearby(c, R):
            t = int(d.tick)
            if dm <= 10 and not bool(mr['spotted']) and not len(rf[(rf['tick'] > t - 3 * TICK) & (rf['tick'] <= t + 3 * TICK)]):
                r3 = c.row(t + 3 * TICK, c.me)
                if r3 is not None and dist_m((float(r3.X), float(r3.Y)), dpos) - dm > 5:
                    yield c.card(R.rn, R.side, t, str(mr['last_place_name']), mpos, facts=f"Round {R.rn+1}, {R.side}, {c.rt(t, R.rn)} s. {d.user_name} died {dm:.0f} m from you while you were unspotted; you did not fire and moved {dist_m((float(r3.X), float(r3.Y)), dpos) - dm:.0f} m further away in the next 3 s.", extra_pos=dpos, extra_label=f"{d.user_name} died")
