"""My primary ran dry within 3 s before a kill I got with the pistol."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._weapons import wclass, wkey, PISTOLS
from ._context import Ctx
KIND = 'pistol_switch_won'
SIDE = 'play'
RETIRED = "an outcome; the decision is measured by pistol_switch"
TITLE = 'Switched to pistol and won'
WHY = "Your primary's clip ran out within 3 s before a kill you got with the pistol."
DO = 'Keep the pistol switch instead of the reload in a close fight.'
BASE = 15


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        rf = R.rf
        for x in R.kills_of_mine():
            if wclass(x.k.weapon) != 'pistol': continue
            t = x.t
            prim = rf[(rf['tick'] >= t - 3 * TICK) & (rf['tick'] < t) & (~rf['weapon'].str.contains('|'.join(PISTOLS), na=False))]
            if not len(prim): continue
            xr2 = c.x(int(prim.iloc[-1]['tick']), c.me)
            if xr2 is not None and xr2.active_weapon_ammo == xr2.active_weapon_ammo and float(xr2.active_weapon_ammo) <= 1:
                yield x.card(f" Your {wkey(prim.iloc[-1]['weapon'])} ran dry {(t - int(prim.iloc[-1]['tick'])) / TICK:.1f} s earlier.")
