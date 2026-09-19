"""Died with two or more enemies having me in view from bearings 45 degrees or more apart in the last 2 s."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from constants import TICK
from ._context import Ctx, ang, bearing
KIND = 'crossfire'
SIDE = 'mistake'
TITLE = 'Died in a crossfire'
WHY = ('Two or more enemies had you in view from different angles in the last 2 s. You can only aim at one of them, so the '
       'fight was theirs before it started.')
DO = ('Clear one angle at a time. If a second enemy can see the spot you are about to stand in, it is not a spot, it is a '
      'lane.')
BASE = 36


def detect(c: Ctx) -> Iterator[Card | None]:
    for s in c.death_sightlines():
        d = s.d; t = s.t; rn = s.rn
        recent = [e for e, ct in s.seen_by.items() if ct >= t - 2 * TICK and e != c.me]
        if len(recent) < 2: continue
        g = c.by_tick.get(c.coarse(t - 1)); brs = {}; opps = []
        for e in recent:
            er = g[g['steamid'] == e] if g is not None else None
            er = er.iloc[0] if er is not None and len(er) else None
            if er is not None and int(er['team_num']) != s.team: brs[str(er['name'])] = bearing(s.mypos, (er.X, er.Y)); opps.append((str(er['name']), (er.X, er.Y)))
        names = list(brs)
        spread = max((ang(brs[a], brs[b]) for a in names for b in names if a < b), default=0)
        if len(names) >= 2 and spread >= 45:
            yield dict(s.base, facts=f"Round {rn+1}, {s.side}, {c.rt(t, rn)} s. Died at {d.user_last_place_name} to {d.attacker_name}. In the last 2 s {', '.join(names)} all had you in view, from angles {spread:.0f}° apart. You fired {s.shots} shots.", spread=spread, n_seen=len(names), opponents=opps)


def adjust(m: Card, add: Add) -> None:
    add(min(8, 4 * (m.get('n_seen', 2) - 2)), f"{m.get('n_seen')} enemies had you in view")
