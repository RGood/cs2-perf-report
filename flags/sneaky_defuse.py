"""Defused with an enemy alive within 25 m who never had me in view during the defuse."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx, dist_m
from ._shared import my_defuses
KIND = 'sneaky_defuse'
SIDE = 'play'
RETIRED = "an outcome; the decision is measured by committed_defuse"
TITLE = 'Sneaky defuse'
WHY = 'You defused with an enemy alive within 25 m who never had you in view during the defuse.'
DO = 'Keep the quiet defuse when the enemy loses track of you.'
BASE = 55


def detect(c: Ctx) -> Iterator[Card | None]:
    db = c.D.get('defuse_begin'); me = c.me
    for R in c.rounds():
        rn = R.rn
        for t, fo, mr, mpos in my_defuses(c, R):
            t0 = int(db[(db['total_rounds_played'] == rn) & (db['user_steamid'] == me) & (db['tick'] <= t)].iloc[-1]['tick']) if db is not None and len(db) and ((db['total_rounds_played'] == rn) & (db['user_steamid'] == me) & (db['tick'] <= t)).any() else t - 10 * TICK
            g = c.by_tick.get(c.coarse(t - 1))
            if g is None or not fo: continue
            close = [f for f in g[(g['team_num'] != R.team) & (g['is_alive'] == True)].itertuples() if dist_m(mpos, (float(f.X), float(f.Y))) <= 25]
            if not close: continue
            seen_any = False
            for ct in range(c.coarse(t0), t, 8):
                r2 = c.row(ct, me)
                if r2 is not None and any(c.sees(r2, str(f.steamid)) for f in close): seen_any = True; break
            if not seen_any:
                yield c.card(rn, R.side, t, str(mr['last_place_name']), mpos, facts=f"Round {rn+1}, CT, {c.rt(t, rn)} s. Defused with {close[0].name} alive {dist_m(mpos, (float(close[0].X), float(close[0].Y))):.0f} m away who never had you in view during the defuse.", opponents=[(str(f.name), (float(f.X), float(f.Y))) for f in close[:2]])
