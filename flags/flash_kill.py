"""Killed an enemy who was still blind from my flash."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from constants import TICK
from ._shared import kill_facts
from ._context import Ctx
KIND = 'flash_kill'
SIDE = 'play'
RETIRED = "an outcome; the decision is measured by swung_own_flash"
TITLE = 'Kill off your own flash'
WHY = 'You blinded the enemy and then killed them while blind. The flash removed the duel and left only the kill.'
DO = 'Keep pop-flashing before the peek. This is the model for every entry: the grenade goes first, then the swing.'
BASE = 40


def detect(c: Ctx) -> Iterator[Card | None]:
    blind = c.blind; rt = c.rt
    for R in c.rounds():
        rn = R.rn
        for k in R.all_my_kills.itertuples():
            t = int(k.tick)
            b = blind[(blind['total_rounds_played'] == rn) & (blind['attacker_steamid'] == c.me) & (blind['user_steamid'] == k.user_steamid) & (blind['tick'] <= t) & (blind['tick'] >= t - 4 * TICK)]
            if len(b) and k.user_flash_duration and k.user_flash_duration > 0:
                yield R.play(t, (k.attacker_X, k.attacker_Y), k.user_name, (k.user_X, k.user_Y), kill_facts(c, R, k) + f" Your flash blinded them {rt(t, rn) - rt(int(b.iloc[-1]['tick']), rn):.1f} s earlier for {float(b.iloc[-1]['blind_duration']):.1f} s; they still had {float(k.user_flash_duration):.1f} s of blindness when they died.",
                             place=k.attacker_last_place_name, victim_sid=k.user_steamid, headshot=bool(k.headshot), kills=1)


def adjust(m: Card, add: Add) -> None:
    if m.get('headshot'): add(3, 'headshot')
    add(min(6, int(m.get('kills', 1) - 1) * 6), 'more than one blind kill')
