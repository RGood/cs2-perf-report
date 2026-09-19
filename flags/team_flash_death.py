"""A teammate died blind from my flash. Now a modifier on team_flash rather than a flag of its own, so nothing is detected here."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'team_flash_death'
SIDE = 'mistake'
RETIRED = "merged into team_flash, which adds the death as a modifier"
TITLE = 'Teammate died blind from your flash'
WHY = ('Your flashbang blinded a teammate and an enemy killed them while they were still blind. That is a kill you handed '
       'over.')
DO = ('Before the throw, know where every teammate is looking. If a teammate is holding the angle the flash will pop over, '
      'tell them to look away or do not throw it.')
BASE = 48


def detect(c: Ctx) -> Iterator[Card | None]:
    return iter(())
