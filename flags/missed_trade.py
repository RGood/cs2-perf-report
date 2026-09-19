"""A teammate died within 15 m of me, their killer stayed in my view for 1.5 s or more, and I fired nothing for 5 s."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._shared import mate_deaths_nearby
from ._context import Ctx
KIND = 'missed_trade'
SIDE = 'mistake'
TITLE = 'Missed trade'
WHY = ('A teammate died within 15 m of you and their killer stayed in your view for 1.5 s or more afterwards. You fired '
       'nothing and did no damage in the next 5 s.')
DO = 'When a teammate dies next to you, the killer is exposed for a moment. Swing them at once; that moment closes fast.'
BASE = 38


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        rf = R.rf; rh = R.rh
        for d, mr, mpos, dpos, dm in mate_deaths_nearby(c, R):
            t = int(d.tick); killer = str(d.attacker_steamid)
            shots_after = rf[(rf['tick'] > t) & (rf['tick'] <= t + 5 * TICK)]; dmg_after = int(rh[(rh['tick'] > t) & (rh['tick'] <= t + 5 * TICK)]['dmg_health'].sum())
            if not (dm <= 15 and not len(shots_after) and dmg_after == 0): continue
            vis = 0         # how long the killer stayed in my view after the death
            for ct in range(c.coarse(t), t + 5 * TICK, 8):
                kr = c.row(ct, killer)
                if kr is not None and bool(kr['is_alive']) and c.sees(kr, c.me): vis += 8
                elif vis: break
            if vis / TICK >= 1.5:
                yield c.card(R.rn, R.side, t, str(mr['last_place_name']), mpos, facts=f"Round {R.rn+1}, {R.side}, {c.rt(t, R.rn)} s. {d.user_name} died {dm:.0f} m from you to {d.attacker_name}, who stayed in your view for {vis / TICK:.1f} s afterwards. You fired nothing and did no damage in the next 5 s.", extra_pos=dpos, extra_label=f"{d.user_name} died", opponents=[(str(d.attacker_name), (float(d.attacker_X), float(d.attacker_Y)))] if d.attacker_X == d.attacker_X else [])
