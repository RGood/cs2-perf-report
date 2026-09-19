"""Moved into a fight at a distance that favoured their weapon class over mine."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
import pandas as pd
from ._weapons import wclass_loose
from ._context import Ctx
KIND = 'their_range'
SIDE = 'mistake'
TITLE = 'Fought at their range'
WHY = ('You moved into a fight at a distance that favoured their weapon: an SMG or pistol against a rifle past 20 m, or a '
       'rifle against an AWP past 35 m.')
DO = ('Close the distance behind cover or utility before the fight, or make them come to your range. Do not peek a rifle at '
      '25 m with an MP9.')
BASE = 32


def detect(c: Ctx) -> Iterator[Card | None]:
    for s in c.death_sightlines():
        d = s.d; t = s.t; rn = s.rn
        mc = wclass_loose(d.user_active_weapon_name); kc = wclass_loose(d.weapon)
        dist = float(d.distance) if pd.notna(d.distance) else 0
        moving_in = s.first_mutual is not None and c.speed(s.first_mutual[0], c.me) > 100       # only when I moved into their view
        if moving_in and ((mc in ('smg', 'pistol') and kc in ('rifle', 'sniper') and dist >= 20) or (mc == 'rifle' and kc == 'sniper' and dist >= 35)):
            yield dict(s.base, facts=f"Round {rn+1}, {s.side}, {c.rt(t, rn)} s. You moved into view with a {d.user_active_weapon_name} against {d.attacker_name}'s {d.weapon} at {dist:.0f} m and lost. That distance is theirs.", dist_m=dist)
