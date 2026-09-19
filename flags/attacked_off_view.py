"""When I first damaged an enemy they were looking more than 90 degrees away from me."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from ._context import Ctx, ang, bearing
from ._shared import fights_started
KIND = 'attacked_off_view'
SIDE = 'play'
TITLE = 'Attacked from off their view'
WHY = 'When you first damaged an enemy they were looking more than 90° away from you.'
DO = 'Keep taking the angles the enemy is not watching.'
BASE = 14


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for t, hh, mpos, vpos, vr, mr, killed, kw, head in fights_started(c, R):
            if vr is not None and vr['yaw'] == vr['yaw']:
                off = ang(float(vr['yaw']), bearing(vpos, mpos))
                if off > 90: yield c.card(R.rn, R.side, t, str(mr['last_place_name']) if mr is not None else None, mpos, facts=head + f": they were looking {off:.0f}° away from you." + (" You got the kill." if killed else ""), **kw)


def adjust(m: Card, add: Add) -> None:
    if m.get('got_kill'): add(8, 'and the kill followed')
