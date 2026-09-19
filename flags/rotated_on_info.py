"""CT: my team spotted three or more enemies 40 m or more away and I closed 20 m or more toward them within 8 s."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
import math
import numpy as np
from constants import TICK, M
from ._context import Ctx
KIND = 'rotated_on_info'
SIDE = 'play'
TITLE = 'Rotated on info'
WHY = ('Your team spotted enemies away from you, and you moved toward them within a few seconds. You put yourself where the '
       'round was.')
DO = ("Keep reacting to the team's information. The first player to arrive at the real fight is usually the one who decides "
      'it.')
BASE = 30


def detect(c: Ctx) -> Iterator[Card | None]:
    tab = c.tab; coarse = c.coarse; me = c.me; rt = c.rt; hurt = c.hurt
    for R in c.rounds():
        if R.side != 'CT': continue
        rn = R.rn; ft = R.ft; team = R.team
        mydeath = R.all_my_deaths
        t_end = int(mydeath['tick'].min()) if len(mydeath) else int(c.D.get('round_end', {}).get(rn, ft + 115 * TICK))
        for ct in range(ft + 10 * TICK, t_end - 8 * TICK, 32):
            k = coarse(ct); i, foes = c.me_and_foes(k, team)
            if i is None: continue
            r = tab[k]
            if not r['alive'][i]: break
            dist = np.hypot(r['X'] - r['X'][i], r['Y'] - r['Y'][i]) * M
            far = foes & r['spotted'] & (dist >= 40)
            if far.sum() < 3: continue
            cen = (float(r['X'][far].mean()), float(r['Y'][far].mean())); mypos0 = (r['X'][i], r['Y'][i])
            c2 = coarse(min(ct + 8 * TICK, t_end - 1)); i2, _ = c.me_and_foes(c2, team)
            if i2 is None: continue
            p2 = (tab[c2]['X'][i2], tab[c2]['Y'][i2])
            closed = (math.dist(mypos0, cen) - math.dist(p2, cen)) * M
            if closed >= 20:
                h = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me) & (hurt['tick'] >= ct)]
                dmg = int(h['dmg_health'].clip(upper=100).sum())
                base = c.position_card(rn, R.side, R.won, ct + 8 * TICK, tab[c2]['place'][i2], p2); base.update(path=c.my_path(ct + 8 * TICK), extra_pos=cen, extra_label='enemies spotted here')
                yield dict(base, facts=f"Round {rn+1}, CT, {rt(ct, rn)} s. Your team had {int(far.sum())} enemies spotted about {math.dist(mypos0, cen) * M:.0f} m from you near {r['place'][far][0]}. Within 8 s you closed {closed:.0f} m toward them" + (f" and did {dmg} damage afterwards." if dmg else "."), dmg=dmg)
                break


def adjust(m: Card, add: Add) -> None:
    add(min(10, int((m.get('dmg') or 0) // 25)), f"{m.get('dmg')} damage after arriving")
