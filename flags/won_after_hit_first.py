"""The victim damaged me before I damaged them, and I still got the kill."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx
KIND = 'won_after_hit_first'
SIDE = 'play'
RETIRED = "an outcome, not a decision"
TITLE = 'Won after being hit first'
WHY = 'The enemy damaged you before you damaged them, and you still got the kill.'
DO = 'Keep the composure. Return fire on target rather than moving off it.'
BASE = 15


def detect(c: Ctx) -> Iterator[Card | None]:
    hurt = c.hurt
    for R in c.rounds():
        rh = R.rh
        for x in R.kills_of_mine():
            t = x.t
            hm = hurt[(hurt['total_rounds_played'] == R.rn) & (hurt['attacker_steamid'] == x.victim) & (hurt['user_steamid'] == c.me) & (hurt['tick'] >= t - 6 * TICK) & (hurt['tick'] <= t)]
            hv = rh[(rh['user_steamid'] == x.victim) & (rh['tick'] >= t - 6 * TICK) & (rh['tick'] <= t)]
            if len(hm) and len(hv) and int(hm.iloc[0]['tick']) < int(hv.iloc[0]['tick']):
                yield x.card(f" They hit you first ({int(hm['dmg_health'].sum())} damage) and you still won the duel.")
