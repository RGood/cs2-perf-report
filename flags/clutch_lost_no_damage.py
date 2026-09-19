"""Last alive, round lost, no damage after the last teammate died."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'clutch_lost_no_damage'
SIDE = 'mistake'
RETIRED = "replaced by the positive clutch_exit_kills and saved_rifle"
TITLE = 'Clutch lost without damage'
WHY = 'You were the last player alive, the round was lost, and you did no damage after your last teammate died.'
DO = ('In a clutch, either find the one fight you can win or save the weapon. Doing neither gives the enemy the round and the'
      ' gun.')
BASE = 35


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        rd = R.rd; rdm = R.my_deaths; rh = R.rh
        mates_d = rd[rd['user_team_num'] == R.team]
        if not (not R.won and len(mates_d) >= 4 and not len(rdm[rdm['tick'] <= int(mates_d.iloc[-1]['tick'])]) if len(mates_d) else False): continue
        t_last = int(mates_d.iloc[-1]['tick'])
        if len(mates_d[mates_d['user_steamid'] != c.me]) >= 4:
            after = rh[rh['tick'] > t_last]
            if int(after['dmg_health'].sum()) == 0:
                mr = c.row(t_last, c.me)
                if mr is not None: yield c.card(R.rn, R.side, t_last, str(mr['last_place_name']), (float(mr.X), float(mr.Y)), facts=f"Round {R.rn+1}, {R.side}, {c.rt(t_last, R.rn)} s. Last alive from here; no damage dealt after that and the round was lost.")
