"""The killer had me in view 1.5 s or more before I had them, and I stayed and fired anyway."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from constants import TICK
from ._context import Ctx
KIND = 'seen_first'
SIDE = 'mistake'
TITLE = 'Seen first, fought anyway'
WHY = ('The killer had you in view for 1.5 s or more before you had them. They knew where you were; you did not know where '
       'they were, and you took the fight anyway.')
DO = ('When you are spotted without seeing anyone, break the line first. Reposition, then take the fight from a spot they '
      'have not pre-aimed.')
BASE = 34


def detect(c: Ctx) -> Iterator[Card | None]:
    for s in c.death_sightlines():
        d = s.d; t = s.t; rn = s.rn
        lead = ((s.i_saw_k_from if s.i_saw_k_from is not None else t) - s.k_saw_me_from) / TICK if s.k_saw_me_from is not None else 0
        if s.k_saw_me_from is not None and lead >= 1.5 and s.shots > 0:
            yield dict(s.base, facts=f"Round {rn+1}, {s.side}, {c.rt(t, rn)} s. {d.attacker_name} had you in view from {c.rt(s.k_saw_me_from, rn)} s, {lead:.1f} s before you had them" + (f" at {c.rt(s.i_saw_k_from, rn)} s" if s.i_saw_k_from else " (you never did)") + f". You stayed and fired {s.shots} shots, and died at {d.user_last_place_name} from {float(d.distance):.0f} m.", lead=lead)


def adjust(m: Card, add: Add) -> None:
    add(min(8, int((m.get('lead') or 0) * 2)), f"seen {m.get('lead', 0):.1f} s before you saw them")
