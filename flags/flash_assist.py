"""A teammate killed an enemy who was still blind from my flash."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx
KIND = 'flash_assist'
SIDE = 'play'
RETIRED = "an outcome; the decision is measured by flash_in_fight"
TITLE = 'Flash assist'
WHY = ('Your flash blinded an enemy that a teammate then killed. Utility thrown for someone else is the highest-leverage '
       'grenade you have.')
DO = 'Keep throwing flashes for the teammate who is peeking, and call it so they swing on it.'
BASE = 32


def detect(c: Ctx) -> Iterator[Card | None]:
    blind = c.blind; rt = c.rt; mine = c.mine
    for R in c.rounds():
        rn = R.rn; rd = R.all_deaths
        for k in rd[(rd['attacker_team_num'] == R.team) & (rd['attacker_steamid'] != c.me)].itertuples():
            t = int(k.tick)
            b = blind[(blind['total_rounds_played'] == rn) & (blind['attacker_steamid'] == c.me) & (blind['user_steamid'] == k.user_steamid) & (blind['tick'] <= t) & (blind['tick'] >= t - 4 * TICK)]
            if len(b) and k.user_flash_duration and k.user_flash_duration > 0:
                mp = mine[mine.index <= t]
                mp = (mp.iloc[-1].X, mp.iloc[-1].Y) if len(mp) else (k.attacker_X, k.attacker_Y)
                yield R.play(t, mp, k.user_name, (k.user_X, k.user_Y), f"Round {rn+1}, {R.side}, {rt(t, rn)} s. Your flash blinded {k.user_name} for {float(b.iloc[-1]['blind_duration']):.1f} s and {k.attacker_name} killed them at {k.user_last_place_name} while blind.",
                             place=None, victim_sid=k.user_steamid, extra_pos=(k.attacker_X, k.attacker_Y), extra_label=f"{k.attacker_name} killed")
