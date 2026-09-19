"""The same grenade from the same place at the same second in four or more rounds."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
import collections
import numpy as np
from ._context import Ctx
KIND = 'util_on_timer'
SIDE = 'mistake'
SKIP_CONTEXT = {'mates_alive', 'dmg_round', 'equip'}       # a habit across rounds, not a death
TITLE = 'Utility on a timer'
WHY = ('The same grenade from the same spot at the same second every round tells the enemy where you stand and when the choke '
       'is covered. They time their push to it.')
DO = 'Throw on sound and on information, not on the clock. Some rounds throw nothing before 20 s and hold the angle instead.'
BASE = 20


def detect(c: Ctx) -> Iterator[Card | None]:
    groups = collections.defaultdict(list)
    for r in c.nades.itertuples():
        rn = int(r.total_rounds_played)
        if rn not in c.fz: continue
        s = c.by_tick.get(c.fz[rn]); side = None
        if s is not None:
            m = s[s['steamid'] == c.me]
            if len(m): side = 'CT' if int(m.iloc[0]['team_num']) == 3 else 'T'
        groups[(side, r.weapon.replace('weapon_', ''), r.user_last_place_name)].append((rn + 1, c.rt(int(r.tick), rn), (r.user_X, r.user_Y)))
    for (side, w, place), items in groups.items():
        times = [x[1] for x in items if x[1] is not None and x[1] > 0]
        if len(items) >= 4 and len(times) >= 4 and (max(times) - min(times)) <= 3.0:
            yield dict(round=items[0][0], side=side, time=round(float(np.mean(times)), 1), place=place, pos=items[0][2], killer=None, kpos=None, kplace=None, weapon=None, my_weapon=None, dist=0, near=None,
                       path=[], mates_alive=None, nades_thrown=[(w, x[2]) for x in items], won=None, repeats=len(items),
                       facts=f"{side} side: {w} thrown from {place} in {len(items)} rounds ({', '.join('R'+str(x[0]) for x in items)}) at {min(times)} to {max(times)} s every time.")


def adjust(m: Card, add: Add) -> None:
    add(min(16, 4 * (m.get('repeats', 4) - 4)), f"repeated in {m.get('repeats')} rounds")
