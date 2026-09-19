"""Untraded death with two or more teammates alive, where the gap to the team was created by movement in the last 10 s."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from constants import TICK
from ._shared import isolated, by_movement, gap_text
from ._context import Ctx
KIND = 'separated_from_team'
SIDE = 'mistake'
KEEP_NEAR = True
TITLE = 'Isolated before dying'
WHY = ('In the 10 s before this death you and your nearest teammate moved apart, with two or more teammates still alive. This '
       'is the avoidable kind of untraded death: the gap was created by movement, not by the round state.')
DO = 'When you move, move toward or with a teammate. If you have to go alone, go for a delay or information, not a duel.'
BASE = 30


def detect(c: Ctx) -> Iterator[Card | None]:
    for a in c.deaths_in_depth():
        if not (isolated(a) and by_movement(a)): continue
        ten = f" Ten seconds earlier you were {a.moved10:.0f} m from this spot" + (f" and the nearest teammate was {a.mate10:.0f} m away." if a.mate10 is not None else ".")
        # how long my team had had any information: a CT default is spread out by design until the round gives some
        info_t = None
        for ct_ in range(c.fz[a.rn], a.t, 32):
            g_ = c.by_tick.get(ct_)
            if g_ is not None and ((g_['team_num'] != a.team) & (g_['is_alive'] == True) & (g_['spotted'] == True)).any(): info_t = ct_; break
        info_s = None if info_t is None else round((a.t - info_t) / TICK, 1)
        note = (" Your team had not spotted an enemy before this." if info_t is None else f" Your team first spotted an enemy {info_s} s before you died.")
        yield a.card(gap_text(a) + ten + note, info_s=info_s)


def adjust(m: Card, add: Add) -> None:
    if m.get('moved10'): add(min(8, int(m['moved10'] // 4)), f"moved {m['moved10']:.0f} m away in the last 10 s")
    if m.get('side') == 'CT':
        # a CT default is spread out by design; before the round gives information the spacing is the setup's, not the player's
        if m.get('info_s') is None: add(-20, 'CT before any information: default spacing')
        elif m['info_s'] < 8: add(-12, f"CT with only {m['info_s']} s of information")
