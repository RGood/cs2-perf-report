"""My HE or molotov damaged a teammate (one flag per grenade type per round, 5 damage or more)."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from ._shared import team_at
from ._context import Ctx
KIND = 'team_util_damage'
SIDE = 'mistake'
TITLE = 'Utility hurt a teammate'
WHY = ('Your HE or molotov damaged a teammate. Damage from your own utility is free for the enemy and costs the round when it '
       'comes at a bad time.')
DO = ('Check the landing spot for teammates before you throw, and never throw a molotov where a teammate is about to move '
      'through.')
BASE = 20


def detect(c: Ctx) -> Iterator[Card | None]:
    hurt = c.hurt; deaths = c.deaths; me = c.me; rt = c.rt
    hm = hurt[(hurt['attacker_steamid'] == me) & (hurt['user_steamid'] != me) & (hurt['weapon'].isin(['hegrenade', 'inferno']))] if len(hurt) else hurt
    for (rn, wpn), grp in hm.groupby(['total_rounds_played', 'weapon']):
        rn = int(rn)
        if rn not in c.fz: continue
        team = team_at(c, rn, me)
        if team not in (2, 3): continue
        side = 'CT' if team == 3 else 'T'
        grp = grp[[team_at(c, rn, s) == team for s in grp['user_steamid']]]
        if not len(grp): continue
        dmg = int(grp['dmg_health'].clip(upper=100).sum())
        if dmg < 5: continue
        t = int(grp['tick'].min()); k = c.on_grid(t); g = c.by_tick.get(k) if k is not None else None; mr = g[g['steamid'] == me] if g is not None else None
        my_pos = (float(mr.iloc[0].X), float(mr.iloc[0].Y)) if mr is not None and len(mr) else None
        if mr is None or my_pos is None: continue
        victims = grp.groupby('user_name')['dmg_health'].sum().sort_values(ascending=False)
        kd = deaths[(deaths['total_rounds_played'] == rn) & (deaths['attacker_steamid'] == me) & (deaths['weapon'].isin(['hegrenade', 'inferno'])) & (deaths['user_steamid'].isin(grp['user_steamid']))]
        label = 'HE' if wpn == 'hegrenade' else 'molotov'
        first = grp.sort_values('tick').iloc[0]
        vpos = (float(first['user_X']), float(first['user_Y'])) if first['user_X'] == first['user_X'] else None
        facts = (f"Round {rn+1}, {side}, {rt(t, rn)} s. Your {label} did {dmg} damage to " + (', '.join(f"{n} ({int(v)})" for n, v in victims.items()) if len(victims) > 1 else str(victims.index[0])) + '.'
                 + (f" {', '.join(kd['user_name'])} died from it." if len(kd) else ''))
        yield dict(round=rn + 1, side=side, time=rt(t, rn), z=None, place=str(mr.iloc[0]['last_place_name']), pos=my_pos, killer=None, kpos=None, kplace=None, weapon=None, my_weapon=None, dist=0, near=None,
                   path=[], mates_alive=None, nades_thrown=[], won=c.D['winner'].get(rn) == side, facts=facts, dmg=dmg, mate_died=bool(len(kd)),
                   extra_pos=vpos, extra_label=f"{first['user_name']} hit")


def adjust(m: Card, add: Add) -> None:
    add(min(15, int((m.get('dmg') or 0) // 5)), f"{m.get('dmg')} damage to teammates")
    add(20 if m.get('mate_died') else 0, 'a teammate died from it')
