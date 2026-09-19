"""First death of the round, and a teammate killed my killer within 5 s."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._context import Ctx
KIND = 'opener_traded'
SIDE = 'play'
TITLE = 'Opening death traded'
WHY = ("You were the round's first death and a teammate killed your killer within 5 s. The opening still cost a player, but "
       'the spacing was right.')
DO = 'Keep taking the first duel from inside trade range.'
BASE = 25


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        rd = R.rd
        if not (len(rd) and str(rd.iloc[0]['user_steamid']) == c.me and str(rd.iloc[0]['attacker_steamid']) in R.foes): continue
        d = rd.iloc[0]; t = int(d['tick']); later = rd[(rd['tick'] > t) & (rd['tick'] <= t + 5 * TICK) & (rd['user_steamid'] == str(d['attacker_steamid'])) & (rd['attacker_team_num'] == R.team)]
        if len(later) and d['user_X'] == d['user_X']:
            lt = later.iloc[0]
            yield c.card(R.rn, R.side, t, str(d['user_last_place_name']), (float(d['user_X']), float(d['user_Y'])), facts=f"Round {R.rn+1}, {R.side}, {c.rt(t, R.rn)} s. First death of the round, to {d['attacker_name']}; {lt['attacker_name']} traded them {(int(lt['tick']) - t) / TICK:.1f} s later.",
                         killer=str(d['attacker_name']), kpos=(float(d['attacker_X']), float(d['attacker_Y'])) if d['attacker_X'] == d['attacker_X'] else None,
                         extra_pos=(float(lt['attacker_X']), float(lt['attacker_Y'])) if lt['attacker_X'] == lt['attacker_X'] else None, extra_label=f"{lt['attacker_name']} traded")
