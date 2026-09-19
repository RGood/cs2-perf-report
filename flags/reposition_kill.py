"""Got a kill, moved 8 m or more, and got another."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
import math
from constants import M
from ._shared import kill_facts
from ._context import Ctx
KIND = 'reposition_kill'
SIDE = 'play'
OUTNUMBERED_BONUS = True
TITLE = 'Repositioned after a kill'
WHY = 'You got a kill, moved at least 8 metres, and got another. The enemy re-peeked the first spot and you were not there.'
DO = 'Keep moving one position after every kill. The second kill is the payoff for the move.'
BASE = 28


def detect(c: Ctx) -> Iterator[Card | None]:
    rt = c.rt
    for R in c.rounds():
        rn = R.rn; rk = R.all_my_kills
        for i, k in enumerate(rk.itertuples()):
            if i == 0: continue
            t = int(k.tick); pos = (k.attacker_X, k.attacker_Y)
            pk = rk.iloc[i - 1]
            moved = math.dist((pk['attacker_X'], pk['attacker_Y']), pos) * M
            if moved >= 8:
                yield R.play(t, pos, k.user_name, (k.user_X, k.user_Y), kill_facts(c, R, k) + f" Your previous kill ({pk['user_name']}) was {rt(t, rn) - rt(int(pk['tick']), rn):.0f} s earlier from {pk['attacker_last_place_name']}, {moved:.0f} m away.",
                             place=k.attacker_last_place_name, victim_sid=k.user_steamid, headshot=bool(k.headshot), extra_pos=(pk['attacker_X'], pk['attacker_Y']))


def adjust(m: Card, add: Add) -> None:
    if m.get('headshot'): add(3, 'headshot')
