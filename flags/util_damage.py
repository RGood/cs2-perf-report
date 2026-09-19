"""30 or more damage from my HE and molotovs in a round."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from ._context import Ctx
KIND = 'util_damage'
SIDE = 'play'
RETIRED = "an outcome; the decision is measured by util_on_signal"
TITLE = 'Utility damage'
WHY = 'An HE or molotov did 30 or more damage this round. Damage from utility is free: no duel, no exposure.'
DO = 'Keep the same throws for the same stacks and chokes. Grenade damage before the fight makes the fight easier.'
BASE = 30


def detect(c: Ctx) -> Iterator[Card | None]:
    hurt = c.hurt; mine = c.mine
    for R in c.rounds():
        rn = R.rn
        hu = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == c.me) & (hurt['user_steamid'].isin(R.not_my_team)) & (hurt['weapon'].isin(['hegrenade', 'inferno', 'molotov', 'incgrenade']))]
        if not len(hu): continue
        ud = int(hu['dmg_health'].clip(upper=100).sum())
        if ud >= 30:
            t = int(hu['tick'].min()); mp_ = mine[mine.index <= t]; mp_ = (mp_.iloc[-1].X, mp_.iloc[-1].Y) if len(mp_) else None
            if mp_: yield R.play(t, mp_, None, None, f"Round {rn+1}, {R.side}. {ud} damage from grenades to {hu['user_name'].nunique()} enemies: " + ', '.join(f"{n} {int(v)}" for n, v in hu.groupby('user_name')['dmg_health'].sum().items()) + '.', place=None, dmg=ud)


def adjust(m: Card, add: Add) -> None:
    add(min(10, int((m.get('dmg') or 0) // 20)), f"{m.get('dmg')} grenade damage")
