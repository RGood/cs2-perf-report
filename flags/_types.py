"""The shape of a flag file, as a type. flags/__init__.py checks the same names when it loads the files."""
from __future__ import annotations
from typing import TYPE_CHECKING, Iterable, Protocol
from report_types import Add, Card, Side

if TYPE_CHECKING:
    from ._context import Ctx


class FlagModule(Protocol):
    """What every flags/<kind>.py defines. Optional extras (read with getattr): adjust(m, add), RETIRED, KEEP_NEAR, SKIP_CONTEXT, OUTNUMBERED_BONUS."""
    KIND: str           # the flag's id; equals the file name
    SIDE: Side          # 'mistake' counts as negative impact, 'play' as positive
    TITLE: str          # the name shown on the report
    WHY: str            # what is measured, every threshold named, and why it matters
    DO: str             # what to do about it, or what to keep doing
    BASE: int           # base score, 0 to 100

    @staticmethod
    def detect(c: Ctx) -> Iterable[Card | None]:
        """One card per instance for the player behind c. A None is skipped (Round.play returns None for pre-round artefacts)."""
        ...


class Adjusts(Protocol):
    """The optional scoring hook of a flag file."""
    @staticmethod
    def adjust(m: Card, add: Add) -> None: ...
