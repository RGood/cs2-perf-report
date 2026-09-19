"""Killed a teammate's killer within 5 s; worth more when the killer was still aimed away from me at my first shot."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from constants import TICK
from ._shared import kill_facts
from ._context import Ctx
KIND = 'trade_kill'
SIDE = 'play'
OUTNUMBERED_BONUS = True
TITLE = 'Trade kill'
WHY = ("A teammate died and you killed their killer within 5 seconds. It counts for more when the teammate held the killer's "
       'attention: when you first shot at the killer they were still aimed well away from you (30° or more), so you had a free'
       ' shot. It counts for less when they were already aimed within 15° of you.')
DO = ('Keep positioning inside trade range of the teammate who is about to take the fight, and come in from off their '
      "killer's aim.")
BASE = 36


def detect(c: Ctx) -> Iterator[Card | None]:
    rt = c.rt
    for R in c.rounds():
        rn = R.rn; rd = R.all_deaths
        for k in R.all_my_kills.itertuples():
            t = int(k.tick)
            prev = rd[(rd['tick'] < t) & (rd['tick'] >= t - 5 * TICK) & (rd['attacker_steamid'] == k.user_steamid) & (rd['user_team_num'] == R.team)]
            if not len(prev): continue
            pv = prev.iloc[-1]
            att, atxt = c.attention(k.user_steamid, c.me, int(pv['tick']), t, str(k.user_name), 'you', str(pv['user_name']))
            yield R.play(t, (k.attacker_X, k.attacker_Y), k.user_name, (k.user_X, k.user_Y), kill_facts(c, R, k) + f" They had killed {pv['user_name']} {rt(t, rn) - rt(int(pv['tick']), rn):.1f} s earlier. {atxt}".rstrip(),
                         place=k.attacker_last_place_name, victim_sid=k.user_steamid, headshot=bool(k.headshot), extra_pos=(pv['user_X'], pv['user_Y']), extra_label=f"{pv['user_name']} died", **att)


def adjust(m: Card, add: Add) -> None:
    if m.get('headshot'): add(3, 'headshot')
    if m.get('att_held'): add(8, f"the killer was aimed {m.get('turn_deg'):.0f}° away from the trader when the trader first shot at them")
    elif m.get('att_prepared'): add(-8, f"the killer was already aimed within {m.get('turn_deg'):.0f}° of the trader when the trader first shot at them")
