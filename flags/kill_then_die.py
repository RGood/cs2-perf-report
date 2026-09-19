"""Died within 5 s of a kill, within 8 m of where the kill was taken."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
import math
import pandas as pd
from constants import TICK, M
from ._context import Ctx
KIND = 'kill_then_die'
SIDE = 'mistake'
SKIP_CONTEXT = {'mates_alive', 'equip'}     # being traded says little about either
TITLE = 'Traded after a kill'
WHY = ('You died within 5 s of a kill, near where you got it. Being traded is often the enemy playing well, so this counts for'
       ' little by itself. It counts more when you had the time to move off the kill spot and stayed on it, and less when the '
       'trader already had you in view as you took the kill, because then there was no reset to make.')
DO = 'After a kill, if a second or more passes without a second enemy on you, move a position before the next fight.'
BASE = 10


def detect(c: Ctx) -> Iterator[Card | None]:
    deaths = c.deaths; me = c.me
    for a in c.deaths_in_depth():
        d = a.d; t = a.t
        mk = deaths[(deaths['attacker_steamid'] == me) & (deaths['total_rounds_played'] == a.rn) & (deaths['tick'] < t) & (deaths['tick'] >= t - 5 * TICK)]
        if not len(mk): continue
        k = mk.iloc[-1]
        if not (pd.notna(k['attacker_X']) and math.dist(a.pos, (k['attacker_X'], k['attacker_Y'])) * M < 8): continue
        moved = math.dist(a.pos, (k['attacker_X'], k['attacker_Y'])) * M; gap_s = round((t - int(k['tick'])) / TICK, 1)
        # was the trade already set up when you got the kill? (the trader had you in view at that moment)
        gk = c.by_tick.get(int(k['tick'])) if int(k['tick']) in c.by_tick else c.by_tick.get(int(k['tick']) - ((int(k['tick']) - c.first_tick) % 8))
        trader_saw = False
        if gk is not None:
            mr_ = gk[gk['steamid'] == me]
            if len(mr_):
                try: trader_saw = str(d.attacker_steamid) in [str(x) for x in mr_.iloc[0]['approximate_spotted_by']]
                except TypeError: trader_saw = False
        yield a.card(f" You killed {k['user_name']} {gap_s} s earlier and died {moved:.1f} m from that spot." + (f" {d.attacker_name} already had you in view when you got the kill." if trader_saw else ""),
                     extra_pos=(k['user_X'], k['user_Y']), moved=moved, gap_s=gap_s, trader_saw=trader_saw)


def adjust(m: Card, add: Add) -> None:
    if (m.get('gap_s') or 0) >= 1.5 and (m.get('moved') or 99) < 3: add(10, f"{m.get('gap_s')} s to move and you stayed within {m.get('moved'):.0f} m")
    if (m.get('gap_s') or 0) >= 3 and (m.get('moved') or 99) < 3: add(6, 'three seconds or more on the same spot')
    if m.get('trader_saw'): add(-6, 'the trader already had you in view at the kill')
