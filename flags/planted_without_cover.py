"""Started the plant with a visible enemy within 25 m and no teammate within 15 m, and died during it."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx, dist_m
from ._shared import my_unfinished_plant
KIND = 'planted_without_cover'
SIDE = 'mistake'
TITLE = 'Planted without cover'
WHY = 'You started the plant with a visible enemy within 25 m and no teammate within 15 m, and died during the plant.'
DO = ('Clear or smoke the angle first, or plant where the enemy cannot see. A plant with an enemy watching is a death, not a '
      'plant.')
BASE = 36


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.deaths_of_mine():
            t_pb = my_unfinished_plant(c, R, x)
            if t_pb is None: continue
            g = c.by_tick.get(c.coarse(t_pb))
            if g is None: continue
            pos = x.pos
            vis = [f for f in g[(g['team_num'] != R.team) & (g['is_alive'] == True)].itertuples() if bool(f.spotted) and dist_m(pos, (float(f.X), float(f.Y))) <= 25]
            nm2 = c.nearest_mate(t_pb, R.team)
            if vis and (nm2 is None or nm2[0] > 15):
                yield c.card(R.rn, R.side, t_pb, x.place, pos, facts=f"Round {R.rn+1}, T, {c.rt(t_pb, R.rn)} s. You started the plant with {vis[0].name} visible {dist_m(pos, (float(vis[0].X), float(vis[0].Y))):.0f} m away and " + (f"the nearest teammate {nm2[0]:.0f} m away" if nm2 else "no teammate alive nearby") + ", and died during the plant.", **x.kw)
