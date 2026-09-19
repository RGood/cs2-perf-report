"""Clip empty at death after firing in the last 2 s."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._weapons import wclass
from ._context import Ctx
KIND = 'died_empty_clip'
SIDE = 'mistake'
TITLE = 'Died with an empty clip'
WHY = 'Your clip was empty at death after firing in the last 2 s: you sprayed dry.'
DO = 'Count the spray. Stop at a third of the clip and reset, or switch to the pistol.'
BASE = 16


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        rf = R.rf
        for x in R.deaths_of_mine():
            xd = x.last        # at my last living tick; the death tick itself reads as airborne with no ammo
            if xd is None or not x.by_enemy: continue
            ammo = float(xd.active_weapon_ammo) if xd.active_weapon_ammo == xd.active_weapon_ammo else None
            if ammo == 0 and len(rf[(rf['tick'] >= x.t - 2 * TICK) & (rf['tick'] <= x.t)]) and wclass(x.d.user_active_weapon_name) in ('rifle', 'smg', 'pistol'):
                yield x.card(" Your clip was empty when you died.")
