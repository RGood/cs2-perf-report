"""Died holding a grenade there was the time, the safety and the target to throw."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from ._context import Ctx
KIND = 'util_unused'
SIDE = 'mistake'
TITLE = 'Died with usable utility'
WHY = ('Only counted when three things were true after contact: there was time (2 s for a flash or HE with the killer inside '
       '30 m, 4 s for a smoke or molotov), there was a safe throw window of at least 1.5 s in which no nearby enemy was '
       'visible to your team, you were not visible to theirs, and you were not being hit, and the grenade would have done '
       'something. If the enemy could engage you the whole time, throwing would have been the mistake, and the grenade is not '
       'counted.')
DO = ('Once contact is called and you are delaying, the usable grenades go out in the first seconds, not after the fight is '
      'lost. Flash the choke, HE the stack, molotov the entrance, then fight.')
BASE = 34


def detect(c: Ctx) -> Iterator[Card | None]:
    for a in c.deaths_in_depth():
        if a.usable and a.tsec > 10:
            win_end = c.rt(a.best_safe_end, a.rn) if a.best_safe_end else None
            yield a.card(f" Contact began {a.after:.0f} s before you died with up to {a.foes_peak} attackers within 25 m. In that time you had a {a.safe_s:.1f} s window ending at {win_end} s where no nearby enemy was visible to your team, you were not visible to theirs, and you were not being hit. Usable and unthrown: {', '.join(a.usable)}."
                         + (f" Not counted (no time or out of range): {', '.join(n for n in a.held if n not in a.usable)}." if len(a.held) > len(a.usable) else ""))


def adjust(m: Card, add: Add) -> None:
    add(min(8, 4 * (m.get('n_usable', 1) - 1)), 'more than one usable grenade held')
    add(4 if (m.get('after') or 0) >= 8 else 0, '8 s or more of contact to use it')
