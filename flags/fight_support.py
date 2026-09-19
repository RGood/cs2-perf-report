"""Put damage on the enemy a teammate was fighting before that fight was decided."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from constants import TICK
from ._context import Ctx
KIND = 'fight_support'
SIDE = 'play'
KEEP_NEAR = True
TITLE = 'Supported the fight'
WHY = ('A teammate was fighting an enemy and you put damage on that enemy before the fight was decided. Two guns on one target'
       ' is how duels stop being coin flips.')
DO = "Keep joining your teammate's fight from the first shot. Even a few bullets of damage change who wins it."
BASE = 35


def detect(c: Ctx) -> Iterator[Card | None]:
    rt = c.rt
    for R in c.rounds():
        rn = R.rn; rd = R.all_deaths
        seen_pairs = set()
        for f in R.teammate_fights():
            if f['dmg_before'] <= 0: continue
            key = (f['mate_sid'], f['enemy_sid'], f['t_start'] // 64)
            if key in seen_pairs: continue
            seen_pairs.add(key)
            e_died = bool(((rd['user_steamid'] == f['enemy_sid']) & (rd['tick'] <= f['t_death'] + 5 * TICK)).any())
            t = f['t_death']
            yield R.play(t, f['my_pos'], f['enemy'], f['e_pos'],
                         f"Round {rn+1}, {R.side}, {rt(t, rn)} s. {f['mate']} fought {f['enemy']} for {f['dur']:.1f} s; you did {f['dmg_before']} damage to {f['enemy']} during the fight from {f['min_dist']:.0f} m at {f['my_place']}." + (f" {f['enemy']} died." if e_died else '') + f" {f['mate']} still died.",
                         place=f['my_place'], victim_sid=f['enemy_sid'], dmg=f['dmg_before'], enemy_died=e_died, mate_survived=False, extra_pos=f['mate_pos'], extra_label=f"{f['mate']} died")


def adjust(m: Card, add: Add) -> None:
    add(min(10, int((m.get('dmg') or 0) // 20)), f"{m.get('dmg')} damage during the fight")
    add(8 if m.get('enemy_died') else 0, 'the enemy died in that fight')
    add(5 if m.get('mate_survived') else 0, 'your teammate survived it')
