"""Died, and a teammate killed my killer within 5 s; worth more when my fight held the killer's attention."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from constants import TICK
from ._context import Ctx
KIND = 'died_tradeable'
SIDE = 'play'
TITLE = 'Death traded'
WHY = ("You died, and a teammate killed your killer within 5 seconds. It is a real trade when your fight held the killer's "
       'attention: when the trader first shot at the killer, the killer was still aimed well away from the trader (30° or '
       'more), so the trader had a free shot. It counts for less when the killer was already aimed within 15° of the trader.')
DO = "Keep dying next to someone, and make the fight last: the longer the killer's aim stays on you, the easier the trade."
BASE = 20


def detect(c: Ctx) -> Iterator[Card | None]:
    rt = c.rt
    for R in c.rounds():
        rn = R.rn; rd = R.all_deaths
        for d in R.all_my_deaths.itertuples():
            t = int(d.tick)
            later = rd[(rd['tick'] > t) & (rd['tick'] <= t + 5 * TICK) & (rd['user_steamid'] == d.attacker_steamid) & (rd['attacker_team_num'] == R.team)]
            if not len(later): continue
            lt = later.iloc[0]
            att, atxt = c.attention(d.attacker_steamid, lt['attacker_steamid'], t, int(lt['tick']), str(d.attacker_name), str(lt['attacker_name']), 'you')
            m = R.play(t, (d.user_X, d.user_Y), d.attacker_name, (d.attacker_X, d.attacker_Y), f"Round {rn+1}, {R.side}, {rt(t, rn)} s. Died at {d.user_last_place_name} to {d.attacker_name}; {lt['attacker_name']} killed them {rt(int(lt['tick']), rn) - rt(t, rn):.1f} s later. {atxt}".strip(),
                       place=d.user_last_place_name, victim_sid=d.attacker_steamid, z=float(d.user_Z), extra_pos=(lt['attacker_X'], lt['attacker_Y']), extra_label=f"{lt['attacker_name']} traded", **att)
            yield m


def adjust(m: Card, add: Add) -> None:
    if m.get('att_held'): add(10, f"the killer was aimed {m.get('turn_deg'):.0f}° away from the trader when the trader first shot at them")
    elif m.get('att_prepared'): add(-10, f"the killer was already aimed within {m.get('turn_deg'):.0f}° of the trader when the trader first shot at them")
