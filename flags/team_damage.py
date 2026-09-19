"""Damaged a teammate with a gun (5 damage or more in the round)."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._weapons import wkey
from ._context import Ctx
KIND = 'team_damage'
SIDE = 'mistake'
TITLE = 'Team damage'
WHY = 'You did damage to a teammate with a gun.'
DO = 'Check the crossfire lines before you fire, and do not shoot past a teammate.'
BASE = 14


def detect(c: Ctx) -> Iterator[Card | None]:
    hurt = c.hurt
    for R in c.rounds():
        td = hurt[(hurt['total_rounds_played'] == R.rn) & (hurt['attacker_steamid'] == c.me) & (hurt['user_steamid'].isin(R.mates)) & (~hurt['weapon'].isin(['hegrenade', 'inferno']))]
        if not len(td): continue
        dmg = int(td['dmg_health'].clip(upper=100).sum()); t = int(td.iloc[0]['tick']); mr = c.row(t, c.me)
        if dmg >= 5 and mr is not None:
            yield c.card(R.rn, R.side, t, str(mr['last_place_name']), (float(mr.X), float(mr.Y)), facts=f"Round {R.rn+1}, {R.side}, {c.rt(t, R.rn)} s. {dmg} damage to " + ', '.join(f"{n} ({int(v)})" for n, v in td.groupby('user_name')['dmg_health'].sum().items()) + f" with {', '.join(sorted(set(wkey(w) for w in td['weapon'])))}.", dmg=dmg)
