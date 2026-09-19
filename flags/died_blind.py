"""Died while still flashed."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
import pandas as pd
from constants import TICK
from ._context import Ctx
KIND = 'died_blind'
SIDE = 'mistake'
TITLE = 'Died flashed'
WHY = 'A blinded player is a free kill. Either you pushed through a flash you saw coming, or a teammate blinded you.'
DO = ("When a flash is thrown at your position, turn away and hold the corner. Call 'flashing' before your own throws and do "
      "not walk into teammates' flashes.")
BASE = 16


def detect(c: Ctx) -> Iterator[Card | None]:
    bl = c.blind
    for a in c.deaths_in_depth():
        d = a.d
        if not (d.user_flash_duration and d.user_flash_duration > 0): continue
        b = bl[(bl['total_rounds_played'] == a.rn) & (bl['user_steamid'] == c.me) & (bl['tick'] <= a.t) & (bl['tick'] >= a.t - 6 * TICK)]
        who = 'unknown'
        if len(b):
            bb = b.iloc[-1]; who = f"{bb['attacker_name']} ({'teammate' if int(bb['attacker_team_num']) == a.team else 'enemy'})" if 'attacker_team_num' in b.columns and pd.notna(bb.get('attacker_team_num')) else str(bb['attacker_name'])
        yield a.card(f" You had {d.user_flash_duration:.1f} s of flash left. Flashed by {who}.")
