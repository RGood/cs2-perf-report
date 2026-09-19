"""One sentence: what this flag measures. (Copy this file to flags/<kind>.py and fill it in; the leading underscore keeps the template itself from loading.)

A flag measures a decision or a behaviour, not an outcome, from exact demo data: events and sampled tick properties. Judge by evidence
(who saw whom, who shot at whom, what a grenade did), not by raw distance alone, and name every threshold in WHY so the reader can check it.
"""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from ._context import Ctx, dist_m                 # plus ang, bearing, spotters; `from constants import TICK, M` for ticks per second and units to metres

KIND = '_template'                           # must equal the file name
SIDE = 'mistake'                             # 'mistake' (negative impact) or 'play' (positive impact)
TITLE = "Short name shown on the report"
WHY = "What is measured, with every threshold named, and why it matters."
DO = "What to do about it (mistake), or what to keep doing (play)."
BASE = 20                                    # base score 0 to 100; decisions that track winning weigh more
# RETIRED = "why"                            # keep the file for reference but stop reporting the flag
# KEEP_NEAR = True                           # keep the nearest-teammate marker on the card
# SKIP_CONTEXT = {'mates_alive', 'dmg_round', 'equip'}   # death-context modifiers that do not apply to this mistake
# OUTNUMBERED_BONUS = True                   # a play that earns +5 when at most one teammate was alive

NEAR_M = 25                                  # thresholds live here as named constants, not inside the loop


def detect(c: Ctx) -> Iterator[Card | None]:
    """Yield one card per instance. c is the shared context (flags/_context.py): c.rounds(), c.row(), c.sees(), c.first_seen(), c.card() ...
    The registry stamps the kind on each card and drops a card with no position."""
    for R in c.rounds():                                     # every round I played: R.team, R.side, R.rd, R.my_kills, R.rh, R.rf, R.mates, R.foes
        for x in R.deaths_of_mine():                         # my deaths this round: x.t, x.pos, x.killer, x.kpos, x.nm, x.traded, x.by_enemy
            if not x.by_enemy: continue
            if x.kpos and dist_m(x.pos, x.kpos) <= NEAR_M:
                yield x.card(f" One sentence of evidence with the numbers in it: the killer was {dist_m(x.pos, x.kpos):.0f} m away.", my_number=3)
    # a card that is not about a death:
    #   yield c.card(R.rn, R.side, tick, place, (x, y), facts="Round 3, CT, 41.2 s. What happened, with the numbers.", extra_pos=(x2, y2), extra_label='bomb')


def adjust(m: Card, add: Add) -> None:
    """Optional. Flag-specific score modifiers on top of BASE, the round result and (for mistakes) the death context.
    m is a card this flag produced; call add(points, 'reason shown in the arithmetic'). add() ignores zero."""
    add(min(8, 2 * (m.get('my_number') or 0)), f"{m.get('my_number')} of something")
