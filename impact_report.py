"""The play side of the flags: thin wrappers over the flags package, plus the green colour scale the page uses."""
from __future__ import annotations
from report_types import Card, Demo, Rules, Scored

import flags

RULES: Rules = flags.rules('play')                  # {kind: (title, why it worked, keep doing)}


def impact(m: Card) -> Scored:
    """0-100. Base weight for the play type, then modifiers. Returns (score, breakdown list)."""
    return flags.score(m)


def imp_rgb(score: float) -> tuple[int, ...]:
    a = (60, 64, 78); b = (60, 190, 90); f = max(0.0, min(1.0, score / 100.0))
    return tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3))

def imp_css(score: float) -> str:
    r, g, b = imp_rgb(score); return f"rgb({r},{g},{b})"


def detect(D: Demo) -> list[Card]:
    """Every play flag for the player D['me']. Each flag lives in its own file under flags/."""
    return flags.detect(D, 'play')
