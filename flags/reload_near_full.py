"""Reloaded with an enemy within 25 m while the clip still held enough for a kill."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx, dist_m
from ._weapons import enough_for_kill
from ._shared import my_reloads_near_enemy
KIND = 'reload_near_full'
SIDE = 'mistake'
TITLE = 'Reloaded with a kill still in the clip'
WHY = ('You reloaded while an enemy was within 25 m with enough ammo left to plausibly get a kill: about twice the hits that '
       'weapon needs, at a typical hit rate.')
DO = 'Reload after fights, not during them. A near-full reload throws away the seconds a fight is decided in.'
BASE = 10


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for t, mr, mpos, near_f in my_reloads_near_enemy(c, R):
            xr2 = c.x(t, c.me)
            if xr2 is None or not (xr2.active_weapon_ammo == xr2.active_weapon_ammo): continue
            enough_, btk_, need_ = enough_for_kill(str(xr2.active_weapon_name), float(xr2.active_weapon_ammo))
            if enough_:
                yield c.card(R.rn, R.side, t, str(mr['last_place_name']), mpos, facts=f"Round {R.rn+1}, {R.side}, {c.rt(t, R.rn)} s. You reloaded your {xr2.active_weapon_name} with {int(xr2.active_weapon_ammo)} rounds left while {near_f[0].name} was {dist_m(mpos, (float(near_f[0].X), float(near_f[0].Y))):.0f} m away; about {btk_} hits kill with it, so roughly {need_} shots would have done.")
