"""The flags: one Python file per flag, all with the same small API. See README.md in this folder and _template.py.

A flag file defines

    KIND    = 'ran_into_contact'          the flag's id; must equal the file name
    SIDE    = 'mistake' or 'play'         mistakes count as negative impact, plays as positive
    TITLE   = "Ran into contact"          the name shown on the report
    WHY     = "..."                       what is measured and why it matters, with every threshold named
    DO      = "..."                       what to do about it (mistake) or what to keep doing (play)
    BASE    = 12                          base score, 0 to 100
    def detect(c): ...                    yield one card (a dict) per instance; c is a flags._context.Ctx

and optionally

    def adjust(m, add): ...               flag-specific score modifiers: add(points, "reason") for a card m
    RETIRED = "why"                       the flag is kept for reference but not reported
    KEEP_NEAR = True                      keep the nearest-teammate marker on the card
    SKIP_CONTEXT = {'mates_alive', ...}   death-context modifiers that do not apply to this mistake (see _score.py)
    OUTNUMBERED_BONUS = True              a play that earns +5 when at most one teammate was alive

Files whose names start with an underscore are shared infrastructure, not flags.
"""
from __future__ import annotations
from report_types import Card, Demo, Rules, Scored, Side
from typing import cast
from ._types import FlagModule
import importlib, pkgutil

INCLUDE_RETIRED = False     # set True to run and report the retired flags as well (used when checking them)

ALL: dict[str, FlagModule] = {}     # kind -> module, in file-name order
for _m in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
    if _m.name.startswith('_'): continue
    _mod = importlib.import_module(f'{__name__}.{_m.name}')
    for _attr in ('KIND', 'SIDE', 'TITLE', 'WHY', 'DO', 'BASE', 'detect'):
        if not hasattr(_mod, _attr): raise ImportError(f"flags/{_m.name}.py does not define {_attr}")
    if _mod.KIND != _m.name: raise ImportError(f"flags/{_m.name}.py: KIND is {_mod.KIND!r}; it must equal the file name")
    if _mod.SIDE not in ('mistake', 'play'): raise ImportError(f"flags/{_m.name}.py: SIDE must be 'mistake' or 'play'")
    ALL[_mod.KIND] = cast(FlagModule, _mod)


def is_retired(mod: FlagModule) -> bool:
    return bool(getattr(mod, 'RETIRED', False))


def active(side: Side | None = None) -> list[FlagModule]:
    """The flag modules that are reported, optionally for one side."""
    return [m for m in ALL.values() if (side is None or m.SIDE == side) and (INCLUDE_RETIRED or not is_retired(m))]


def rules(side: Side) -> Rules:
    """{kind: (title, why, do)} for one side, as the report pages read it."""
    return {m.KIND: (m.TITLE, m.WHY, m.DO) for m in active(side)}


def bases(side: Side) -> dict[str, int]:
    return {m.KIND: m.BASE for m in active(side)}


def detect(D: Demo, side: Side) -> list[Card]:
    """Run every active flag of one side for the player D['me']. Returns the list of cards, each stamped with its kind."""
    from ._context import Ctx
    c = Ctx.of(D); out = []
    for mod in active(side):
        for m in mod.detect(c) or ():
            if m is None or m.get('pos') is None: continue      # a card needs a position to be drawn
            m['kind'] = mod.KIND
            if not getattr(mod, 'KEEP_NEAR', False): m['near'] = None
            out.append(m)
    return out


def score(m: Card) -> Scored:
    """(score 0 to 100, breakdown lines) for one card."""
    from ._score import score as _score
    return _score(ALL[m['kind']], m)
