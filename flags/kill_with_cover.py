"""At my kill a teammate within 20 m also had the victim in view."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx, dist_m
KIND = 'kill_with_cover'
SIDE = 'play'
RETIRED = "an outcome; the decision is measured at first damage by fought_with_cover"
TITLE = 'Kill with cover'
WHY = 'At your kill a teammate within 20 m also had the victim in view: a crossfire that was actually set.'
DO = 'Keep setting crossfires with a teammate rather than holding alone.'
BASE = 12


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        for x in R.kills_of_mine():
            vr = c.row(x.t - 1, x.victim)
            if not (vr is not None and x.vpos and vr['yaw'] == vr['yaw']): continue
            g = c.by_tick.get(c.coarse(x.t - 1))
            if g is None: continue
            cover = [m_ for m_ in g[(g['team_num'] == R.team) & (g['is_alive'] == True) & (g['steamid'] != c.me)].itertuples() if dist_m(x.pos, (float(m_.X), float(m_.Y))) <= 20 and c.sees(vr, str(m_.steamid))]
            if cover: yield x.card(f" {cover[0].name}, {dist_m(x.pos, (float(cover[0].X), float(cover[0].Y))):.0f} m from you, also had them in view.", extra_pos=(float(cover[0].X), float(cover[0].Y)), extra_label=f"{cover[0].name} covering")
