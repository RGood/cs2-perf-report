"""A smoke or molotov thrown on no information that then did nothing, leaving no delay grenade for the contact that came."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'util_too_early'
SIDE = 'mistake'
TITLE = 'Utility thrown too early'
WHY = ('A smoke or molotov thrown with no enemy within 30 m and none spotted by your team, that then did nothing: no teammate '
       'used the space it made (nobody of yours came within 8 m of it while it lasted), no enemy came within 12 m of it, and '
       "it was not a diversion (the round's first fight was not 40 m or more away from it with nobody of yours near it). Later"
       ' in the same round you were in contact for 4 s or more with no delay grenade left. Set-piece smokes the team walks '
       'behind, fakes, and utility that met an enemy are not counted.')
DO = ("Hold the delay grenade until one of these exists: enemies seen or heard at the choke, a teammate's call, or the "
      "enemy's timing from earlier rounds. Before the earliest possible T arrival at that choke, nothing you throw is "
      'reacting to anything.')
BASE = 26


def detect(c: Ctx) -> Iterator[Card | None]:
    for a in c.deaths_in_depth():
        # a throw counts as too early only when it was blind (no enemy within 30 m, none spotted), before contact, and then did nothing:
        # nobody used the space (used), no enemy came near it (touched), and it was not a diversion (fake)
        early = [x for x in a.throw_info if x['blind'] and x['pre'] and x['nade'] in ('smokegrenade', 'molotov', 'incgrenade') and x['land_ok'] and not x['used'] and not x['touched'] and not x['fake']]
        if early and a.contact is not None and a.after >= 4 and not any(('Smoke' in n or 'Molotov' in n or 'Incendiary' in n) for n in a.held):
            e = early[0]; signalled = [x for x in a.throw_info if not x['blind']]
            yield a.card(f" At {e['t']} s you threw a {e['nade']} from {e['place']} with no enemy within 30 m and none spotted by your team. Nobody on your team came within 8 m of where it landed while it lasted, no enemy came within 12 m of it, and the round's first fight was not a diversion away from it"
                         + (f" ({e['fake_d']:.0f} m away)" if e.get('fake_d') is not None else "") + f". Contact came at {c.rt(a.contact, a.rn)} s and lasted {a.after:.0f} s; you had no smoke or molotov left for it."
                         + (" Throws that did have a signal: " + '; '.join(f"{x['nade']} at {x['t']} s with {x['near']} enemies within 30 m" for x in signalled) + '.' if signalled else ""))
