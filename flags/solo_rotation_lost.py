"""CT: entered a bombsite where two or more teammates had already died, with no teammate within 20 m, and died."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'solo_rotation_lost'
SIDE = 'mistake'
TITLE = 'Solo rotation into a lost site'
WHY = ('As CT, two or more teammates had already died at a site, and you entered it alone with no teammate within 20 m and '
       'died.')
DO = 'Wait for the other rotator. Two players retaking together beats two players retaking one after the other.'
BASE = 42


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        if R.side != 'CT': continue
        rd = R.rd
        for x in R.deaths_of_mine():
            if not x.by_enemy: continue
            nm = x.nm
            site_deaths = rd[(rd['tick'] < x.t) & (rd['user_team_num'] == R.team) & (rd['user_last_place_name'] == x.place)]
            if x.place in ('BombsiteA', 'BombsiteB') and len(site_deaths) >= 2 and (nm is None or nm[0] > 20):
                yield x.card(f" {len(site_deaths)} teammates had already died at {x.place}; you entered alone" + (f", nearest teammate {nm[0]:.0f} m away." if nm else "."))
