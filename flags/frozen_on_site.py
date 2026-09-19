"""CT: the bomb was planted elsewhere and I stayed more than 40 m from it for more than 15 s while alive; round lost."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx, dist_m
KIND = 'frozen_on_site'
SIDE = 'mistake'
TITLE = 'Frozen on site'
WHY = ('As CT, the bomb was planted (or two or more enemies were spotted) at the other site, and you stayed more than 40 m '
       'away for more than 15 s while alive. The round was lost.')
DO = ('Once the hit is confirmed elsewhere, rotate. A late retake with one more player is better than a full-health player on'
      ' an empty site.')
BASE = 40


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        if R.side != 'CT' or R.g0 is None or R.won: continue
        pl = c.plant[(c.plant['total_rounds_played'] == R.rn)]
        if not (len(pl) and pl.iloc[0]['user_X'] == pl.iloc[0]['user_X']): continue
        hit_t = int(pl.iloc[0]['tick']); hit_pos = (float(pl.iloc[0]['user_X']), float(pl.iloc[0]['user_Y']))
        far = 0; last_pos = None
        for ct in range(c.coarse(hit_t), min(hit_t + 40 * TICK, R.end), 8):
            r = c.row(ct, c.me)
            if r is None or not bool(r['is_alive']): break
            if dist_m((float(r.X), float(r.Y)), hit_pos) > 40: far += 8; last_pos = (float(r.X), float(r.Y), str(r['last_place_name']))
            else: break
        if far / TICK > 15 and last_pos:
            yield c.card(R.rn, R.side, hit_t, last_pos[2], (last_pos[0], last_pos[1]), facts=f"Round {R.rn+1}, CT, {c.rt(hit_t, R.rn)} s. The bomb was planted {dist_m((last_pos[0], last_pos[1]), hit_pos):.0f} m from you and you stayed more than 40 m away for {far / TICK:.0f} s. Round lost.", extra_pos=hit_pos, extra_label='bomb')
