"""Scoring shared by every flag: the base weight, the round result, the death-context modifiers and their cap.
A flag's own modifiers live in its file, in adjust(m, add)."""
from __future__ import annotations
from report_types import Card, Scored
from ._types import FlagModule

CONTEXT_CAP = 10        # the context modifiers describe the death, not the decision: together they may add at most this


def score(mod: FlagModule, m: Card) -> Scored:
    """(score 0 to 100, breakdown). Mistakes: base, round result, death context (capped), the flag's own modifiers.
    Plays: base, round result, the flag's own modifiers, then the outnumbered bonus."""
    mistake = mod.SIDE == 'mistake'
    total = mod.BASE; br = [f"base {total} for this {'mistake' if mistake else 'play'} type"]
    def add(v: int, why: str) -> None:
        nonlocal total
        if v:
            total += v; br.append(f"{v:+d} {why}")
    rm = int(round(min(10, max(3, 0.25 * mod.BASE))))          # the round result counts in proportion to the flag
    if mistake:
        ctx0 = total; skip = getattr(mod, 'SKIP_CONTEXT', ())
        if m.get('won') is False: add(rm, 'round lost')
        elif m.get('won') is True: add(-rm, 'round won anyway')
        ma = m.get('mates_alive')
        if ma is not None and 'mates_alive' not in skip: add({4: 10, 3: 7, 2: 3}.get(ma, 0), f'{ma} teammates still alive')
        if m.get('order') == 1: add(8, 'first death of the round')
        if m.get('dmg_round') == 0 and 'dmg_round' not in skip: add(8, 'no damage dealt that round')
        eq = m.get('equip')
        if eq is not None and 'equip' not in skip:
            if eq >= 3700: add(6, 'full buy lost')
            elif eq < 1500: add(-8, 'eco round')
        if total - ctx0 > CONTEXT_CAP: add(-(total - ctx0 - CONTEXT_CAP), f'context modifiers capped at +{CONTEXT_CAP} in total')
    else:
        if m.get('won') is True: add(rm, 'round won')
        elif m.get('won') is False: add(-rm, 'round still lost')
    if hasattr(mod, 'adjust'): mod.adjust(m, add)
    mates_alive = m.get('mates_alive')
    if not mistake and getattr(mod, 'OUTNUMBERED_BONUS', False) and mates_alive is not None and mates_alive <= 1: add(5, 'while outnumbered')
    return max(0, min(100, total)), br
