"""CT: three or more enemies spotted 40 m or more away for 6 s with nobody near me, and I stayed put; round lost."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
import math
import numpy as np
from constants import TICK, M
from ._context import Ctx
KIND = 'empty_site'
SIDE = 'mistake'
TITLE = 'Held an empty site'
WHY = ('Your team had three or more enemies spotted far from you for six seconds and you stayed put. The information said the '
       'round was elsewhere.')
DO = ('When the team has three spotted at the other site, your site is no longer the round. Move toward the fight, or at '
      'least to where the retake starts.')
BASE = 38


def detect(c: Ctx) -> Iterator[Card | None]:
    tab = c.tab; coarse = c.coarse; me = c.me; rt = c.rt
    for R in c.rounds():
        if R.side != 'CT': continue
        rn = R.rn; ft = R.ft; team = R.team; won = R.won
        mydeath = R.all_my_deaths; t_end = int(mydeath['tick'].min()) if len(mydeath) else int(c.D.get('round_end', {}).get(rn, ft + 115 * TICK))
        h_me = R.rh
        run = 0; start_ct = 0
        for ct in range(ft + 15 * TICK, t_end, 16):
            k = coarse(ct); i, foes = c.me_and_foes(k, team)
            if i is None: continue
            r = tab[k]
            if not r['alive'][i]: break
            dist = np.hypot(r['X'] - r['X'][i], r['Y'] - r['Y'][i]) * M
            far = foes & r['spotted'] & (dist >= 40); near = int((foes & (dist < 30)).sum())
            if far.sum() >= 3 and near == 0:
                if run == 0:
                    start_ct = k; start_pos = (r['X'][i], r['Y'][i]); far_centroid = (float(r['X'][far].mean()), float(r['Y'][far].mean())); far_place = r['place'][far][0]; start_place = r['place'][i]; n_far = int(far.sum())
                run += 16
                if run >= 6 * TICK:
                    c2 = coarse(min(start_ct + 10 * TICK, t_end - 1)); i2, _ = c.me_and_foes(c2, team)
                    moved = (math.dist(start_pos, far_centroid) - math.dist((tab[c2]['X'][i2], tab[c2]['Y'][i2]), far_centroid)) * M if i2 is not None else 0
                    dmg = int(h_me[h_me['tick'] <= start_ct + 15 * TICK]['dmg_health'].clip(upper=100).sum())
                    if moved < 10 and dmg == 0 and not won:
                        base = c.position_card(rn, R.side, won, start_ct, start_place, start_pos); base.update(path=c.my_path(start_ct + 10 * TICK), extra_pos=far_centroid, extra_label='enemies spotted here')
                        yield dict(base, facts=f"Round {rn+1}, CT. From {rt(start_ct, rn)} s your team had {n_far} enemies spotted about {math.dist(start_pos, far_centroid) * M:.0f} m away near {far_place}, for at least 6 s, with nobody near you at {start_place}. Over the next 10 s you closed {max(moved, 0):.0f} m toward them and did no damage. Round lost.", n_far=n_far)
                    break
            else:
                run = 0
