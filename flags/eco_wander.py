"""Died on a pistol or eco round more than 25 m from every teammate."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'eco_wander'
SIDE = 'mistake'
KEEP_NEAR = True
SKIP_CONTEXT = {'equip'}        # the flag is already about the eco
TITLE = 'Alone on eco'
WHY = ('On a pistol or eco round your value is the exit kill or the weapon pickup, and both need the group. Alone you die for '
       'nothing. Not counted when a teammate died in the same fight just before you, or when a teammate had your killer in '
       'view.')
DO = 'Stack with the team on a save. Play for the exit kill together, or hide and save the pistol and armor.'
BASE = 20


def detect(c: Ctx) -> Iterator[Card | None]:
    for a in c.deaths_in_depth():
        if a.equip < 1500 and a.near and a.near[0] > 25 and not a.shared and not a.mate_los:
            yield a.card(f" Equipment value ${a.equip}.")
