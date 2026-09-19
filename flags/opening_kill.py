"""The first kill of the round."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from ._shared import kill_facts
from ._context import Ctx
KIND = 'opening_kill'
SIDE = 'play'
RETIRED = "an outcome, not a decision"
OUTNUMBERED_BONUS = True
TITLE = 'Opening kill'
WHY = ('First kill of the round. The enemy started the round a player down before committing, which is the single most '
       'valuable kill in the round.')
DO = ('Keep taking the opener from the same kind of spot: a held angle or a peek with utility and a teammate close enough to '
      'trade.')
BASE = 50


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        rd = R.all_deaths
        for k in R.all_my_kills.itertuples():
            t = int(k.tick)
            if rd.iloc[0]['tick'] != t: continue
            ma, fo, md, mp = R.state(t)
            supported = bool(md and md[0][0] <= 15)
            yield R.play(t, (k.attacker_X, k.attacker_Y), k.user_name, (k.user_X, k.user_Y), kill_facts(c, R, k) + f" First kill of the round with {fo} enemies and {ma} teammates alive." + (f" Nearest teammate {md[0][1]} was {md[0][0]:.0f} m away." if md else ''),
                         place=k.attacker_last_place_name, victim_sid=k.user_steamid, headshot=bool(k.headshot), supported=supported, z=float(k.attacker_Z))


def adjust(m: Card, add: Add) -> None:
    if m.get('headshot'): add(3, 'headshot')
    if (m.get('time') or 99) < 20: add(5, 'before 20 s')
    if m.get('supported'): add(5, 'teammate within 15 m')
