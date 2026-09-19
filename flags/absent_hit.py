"""T: three teammates hit together and two died within 10 s while I was 40 m or more away with no damage and no kill to follow."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
import math
from constants import TICK, M
from ._context import Ctx
KIND = 'absent_hit'
SIDE = 'mistake'
TITLE = 'Absent from the hit'
WHY = ('Three teammates hit a site and two of them died while you were 40 m or more away with no damage and no kill '
       'afterwards. A lurk that never pays off is one player short on the execute.')
DO = ('A lurk has to produce something: a kill on the rotation, a late flank, or a plant. If none of that is coming, be on '
      'the site when the team goes.')
BASE = 38


def detect(c: Ctx) -> Iterator[Card | None]:
    me = c.me; rt = c.rt
    for R in c.rounds():
        if R.side == 'CT': continue
        rn = R.rn; team = R.team; rd = R.all_deaths; h_me = R.rh
        mates_deaths = rd[(rd['user_team_num'] == team) & (rd['user_steamid'] != me)].sort_values('tick')
        for i in range(len(mates_deaths) - 1):
            d1 = mates_deaths.iloc[i]; d2 = mates_deaths.iloc[i + 1]
            if int(d2['tick']) - int(d1['tick']) > 10 * TICK: continue
            t1 = int(d1['tick']); g = c.by_tick.get(c.coarse(t1 - 8))
            if g is None: continue
            mr = g[g['steamid'] == me]; mr = mr.iloc[0] if len(mr) else None
            if mr is None or not bool(mr['is_alive']): continue
            mates = g[(g['team_num'] == team) & (g['steamid'] != me) & (g['is_alive'] == True)]
            if len(mates) < 3: continue
            cx, cy = mates['X'].mean(), mates['Y'].mean()
            if max(math.dist((cx, cy), (m.X, m.Y)) * M for m in mates.itertuples()) > 25: continue      # not together: not a hit
            my_d = math.dist((mr.X, mr.Y), (cx, cy)) * M
            if my_d < 40: continue
            dmg = int(h_me[h_me['tick'] <= int(d2['tick'])]['dmg_health'].clip(upper=100).sum())
            later_kill = bool(((rd['attacker_steamid'] == me) & (rd['tick'] > t1) & (rd['tick'] <= t1 + 15 * TICK)).any())
            if dmg == 0 and not later_kill:
                base = c.position_card(rn, R.side, R.won, t1, mr['last_place_name'], (mr.X, mr.Y)); base.update(path=c.my_path(t1), extra_pos=(cx, cy), extra_label='the hit')
                yield dict(base, facts=f"Round {rn+1}, T, {rt(t1, rn)} s. Three teammates were together near {d1['user_last_place_name']} and {d1['user_name']} and {d2['user_name']} died within {(int(d2['tick']) - t1) / TICK:.0f} s of each other. You were {my_d:.0f} m away at {mr['last_place_name']} with no damage in the round and no kill in the next 15 s.", my_d=my_d)
                break
