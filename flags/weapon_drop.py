"""In freeze time a rifle left my inventory and appeared in a teammate's."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._weapons import wclass
from ._context import Ctx
KIND = 'weapon_drop'
SIDE = 'play'
TITLE = 'Weapon drop'
WHY = "In freeze time a rifle left your inventory and appeared in a teammate's within 3 s."
DO = 'Keep sharing the buy so the team has five guns rather than four.'
BASE = 10


def detect(c: Ctx) -> Iterator[Card | None]:
    me = c.me
    for R in c.rounds():
        ft = R.ft
        r_pre = c.row(ft - 8 * TICK, me); r_at = c.row(ft, me)
        if r_pre is None or r_at is None: continue
        try:
            had = [str(w) for w in r_pre['inventory']]; have = [str(w) for w in r_at['inventory']]
        except TypeError: had, have = [], []
        lost = [w for w in had if wclass(w) == 'rifle' and w not in have]
        if not lost: continue
        g_pre = c.by_tick.get(ft - 8 * TICK); g_at = c.by_tick.get(ft)
        if g_pre is None or g_at is None: continue
        for m_ in g_at[(g_at['team_num'] == R.team) & (g_at['steamid'] != me)].itertuples():
            try:
                before = [str(w) for w in g_pre[g_pre['steamid'] == m_.steamid].iloc[0]['inventory']] if (g_pre['steamid'] == m_.steamid).any() else []
                now = [str(w) for w in m_.inventory]
            except (TypeError, IndexError): continue
            if lost[0] in now and lost[0] not in before:
                yield c.card(R.rn, R.side, ft, 'spawn', (float(r_at.X), float(r_at.Y)) if r_at.X == r_at.X else None, facts=f"Round {R.rn+1}, {R.side}. In freeze time your {lost[0]} went to {m_.name}.")
                break
