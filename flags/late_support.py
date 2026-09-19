"""A teammate's fight I could have joined, engaged only after they had died."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
import math
from constants import TICK, M, REACTION_S, PEEK_S, SUPPORT_RANGE_M, PEEK_RANGE_M
from ._context import Ctx
KIND = 'late_support'
SIDE = 'mistake'
KEEP_NEAR = True
TITLE = 'Late support'
WHY = ('A teammate was fighting an enemy you could have shot. You waited, they died, and only then did you engage the same '
       'enemy. Allowing 0.4 s to react and 0.6 s to swing, there was still time to help before they died.')
DO = ('When a teammate takes a fight you can see or peek, you are in that fight from the first shot. Joining a second earlier'
      ' turns a death into a 2v1.')
BASE = 40


def detect(c: Ctx) -> Iterator[Card | None]:
    rt = c.rt
    for R in c.rounds():
        rn = R.rn
        for f in R.teammate_fights():
            usable = f['dur'] - REACTION_S - PEEK_S                 # time left to help after reacting and swinging
            if usable < 0.4 or f['busy'] or f['blind'] or f['min_dist'] is None or f['min_dist'] > SUPPORT_RANGE_M: continue
            if f['dmg_before'] > 0 or not f['t_engage']: continue   # helped during the fight, or never engaged at all (that is sat_out)
            saw = f['saw_from'] is not None
            if not saw and f['min_dist'] > PEEK_RANGE_M: continue
            t = f['t_death']
            facts = (f"Round {rn+1}, {R.side}, {rt(t, rn)} s. {f['mate']} fought {f['enemy']} for {f['dur']:.1f} s ({rt(f['t_start'], rn)} s to {rt(t, rn)} s) and died at {f['mate_place']}. "
                     f"You were {f['min_dist']:.0f} m from {f['enemy']} at {f['my_place']}, not in a fight (no damage given or taken, nobody shooting at you, you shooting at nobody) and not flashed. "
                     + (f"{f['enemy']} had you in view from {rt(f['saw_from'], rn)} s. " if saw else f"You had no line of sight but were within {PEEK_RANGE_M} m and could have peeked. ")
                     + f"You did no damage during the fight and first engaged {f['enemy']} {(f['t_engage'] - t) / TICK:.1f} s after {f['mate']} died"
                     + (f"; {f['enemy']} had {f['enemy_hp']} hp left." if f['enemy_hp'] is not None else '.'))
            yield dict(round=rn + 1, side=R.side, time=rt(t, rn), z=None, place=f['my_place'], pos=f['my_pos'], killer=f['enemy'], kpos=f['e_pos'], kplace=None,
                       weapon=None, my_weapon=None, dist=round(f['min_dist'], 1), near=(math.dist(f['my_pos'], f['mate_pos']) * M, f['mate'], f['mate_pos'], f['mate_place']),
                       path=c.my_path(t), killer_path=[], mate_path=[], mates_alive=None, nades_thrown=[], won=R.won,
                       facts=facts, saw=saw, spare_s=usable, enemy_hp=f['enemy_hp'], extra_pos=f['mate_pos'], extra_label=f"{f['mate']} died")


def adjust(m: Card, add: Add) -> None:
    add(6 if m.get('saw') else 0, 'you had the enemy in view during the fight')
    add(min(8, int((m.get('spare_s') or 0) * 4)), f"{m.get('spare_s', 0):.1f} s of usable time before the death")
    add(5 if (m.get('enemy_hp') or 0) >= 80 else 0, 'the enemy was barely damaged when your teammate died')
