"""A CT kill after the plant in a round that was then won."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from ._shared import kill_facts
from ._context import Ctx
KIND = 'retake_kill'
SIDE = 'play'
RETIRED = "an outcome, not a decision"
OUTNUMBERED_BONUS = True
TITLE = 'Retake kill'
WHY = ('A kill after the bomb was planted, in a round your team then won. Retakes are lost by going in alone and won by '
       'exactly this.')
DO = ('Keep waiting for the group, keep the utility for the retake, and keep taking the first fight from a position the plant'
      ' forces them to defend.')
BASE = 50


def detect(c: Ctx) -> Iterator[Card | None]:
    plant = c.plant; rt = c.rt
    for R in c.rounds():
        rn = R.rn; plant_t = R.plant_tick
        if not (R.side == 'CT' and plant_t and R.won): continue
        for k in R.all_my_kills.itertuples():
            t = int(k.tick)
            if t <= plant_t: continue
            pr = plant[plant['total_rounds_played'] == rn].iloc[0]
            yield R.play(t, (k.attacker_X, k.attacker_Y), k.user_name, (k.user_X, k.user_Y), kill_facts(c, R, k) + f" Bomb had been planted {rt(t, rn) - rt(plant_t, rn):.0f} s earlier; the round was won.",
                         place=k.attacker_last_place_name, victim_sid=k.user_steamid, headshot=bool(k.headshot), extra_pos=(pr['user_X'], pr['user_Y']), extra_label='bomb')


def adjust(m: Card, add: Add) -> None:
    if m.get('headshot'): add(3, 'headshot')
