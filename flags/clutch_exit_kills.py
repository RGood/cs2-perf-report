"""Last alive in a lost round, and still took kills after the last teammate died."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from ._context import Ctx
KIND = 'clutch_exit_kills'
SIDE = 'play'
TITLE = 'Exit kills in a lost clutch'
WHY = ('You were the last player alive, the round was lost, and you still took kills after your last teammate died. Kills at '
       'that point cost the enemy weapons and money for the next round.')
DO = 'Keep finding the fight you can win when the round is gone; each kill there is a saved weapon denied.'
BASE = 18


def detect(c: Ctx) -> Iterator[Card | None]:
    rt = c.rt
    for R in c.rounds():
        rn = R.rn; rd = R.all_deaths; rk = R.all_my_kills; rdm = R.all_my_deaths
        team_deaths = rd[rd['user_team_num'] == R.team]
        if R.won or len(team_deaths) < 4: continue
        others_dead = team_deaths[team_deaths['user_steamid'] != c.me]
        if len(others_dead) < 4: continue
        t_last = int(others_dead.iloc[3]['tick'])
        if len(rdm) and int(rdm.iloc[0]['tick']) <= t_last: continue      # I died before the last teammate: never the last alive
        k_after = rk[rk['tick'] > t_last]
        if len(k_after):
            k0 = k_after.iloc[0]
            yield R.play(int(k0['tick']), (k0['attacker_X'], k0['attacker_Y']), str(k0['user_name']), (k0['user_X'], k0['user_Y']), f"Round {rn+1}, {R.side}. Last alive from {rt(t_last, rn)} s; the round was lost, and you killed {', '.join(k_after['user_name'])} after that.",
                         place=k0['attacker_last_place_name'], victim_sid=k0['user_steamid'], kills=len(k_after))


def adjust(m: Card, add: Add) -> None:
    add(min(16, 8 * (m.get('kills', 1) - 1)), f"{m.get('kills')} kills after the last teammate died")
