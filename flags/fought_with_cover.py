"""When I first damaged an enemy, a teammate within 20 m also had them in view."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from ._context import Ctx, dist_m
from ._shared import fights_started
KIND = 'fought_with_cover'
SIDE = 'play'
TITLE = 'Fought with cover'
WHY = ('When you first damaged an enemy, a teammate within 20 m also had them in view: a crossfire set before the fight, not '
       'after it.')
DO = 'Keep setting crossfires with a teammate rather than holding alone.'
BASE = 14


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for t, hh, mpos, vpos, vr, mr, killed, kw, head in fights_started(c, R):
            g = c.by_tick.get(c.coarse(t - 1))
            if g is None or vr is None: continue
            cover = [m_ for m_ in g[(g['team_num'] == R.team) & (g['is_alive'] == True) & (g['steamid'] != c.me)].itertuples() if dist_m(mpos, (float(m_.X), float(m_.Y))) <= 20 and c.sees(vr, str(m_.steamid))]
            if cover: yield c.card(R.rn, R.side, t, str(mr['last_place_name']) if mr is not None else None, mpos, facts=head + f": {cover[0].name}, {dist_m(mpos, (float(cover[0].X), float(cover[0].Y))):.0f} m from you, also had them in view." + (" You got the kill." if killed else ""), **kw)


def adjust(m: Card, add: Add) -> None:
    if m.get('got_kill'): add(8, 'and the kill followed')
