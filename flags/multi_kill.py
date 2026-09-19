"""Two or more kills in one round."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from ._context import Ctx
KIND = 'multi_kill'
SIDE = 'play'
RETIRED = "an outcome, not a decision"
OUTNUMBERED_BONUS = True
TITLE = 'Multi-kill round'
WHY = 'Two or more kills in one round. You changed the numbers, not just the scoreline.'
DO = 'Note where you were and what you had: multi-kills come from positions the enemy has to cross in sequence.'
BASE = 45


def detect(c: Ctx) -> Iterator[Card | None]:
    rt = c.rt
    for R in c.rounds():
        rn = R.rn; rk = R.all_my_kills
        if len(rk) < 2: continue
        k = rk.iloc[-1]; t = int(k['tick'])
        yield R.play(t, (k['attacker_X'], k['attacker_Y']), k['user_name'], (k['user_X'], k['user_Y']),
                     f"Round {rn+1}, {R.side}. {len(rk)} kills: " + '; '.join(f"{r.user_name} at {rt(int(r.tick), rn)} s from {r.attacker_last_place_name}" for r in rk.itertuples()) + f". {R.dmg_to_enemies} damage this round." + (" You survived." if not R.died else ""),
                     place=k['attacker_last_place_name'], victim_sid=k['user_steamid'], kills=len(rk), opponents=[(str(r.user_name), (r.user_X, r.user_Y)) for r in rk.itertuples()])


def adjust(m: Card, add: Add) -> None:
    add(10 * (m.get('kills', 2) - 2), f"{m.get('kills')} kills")
