"""My flash blinded an enemy for a second or more and a teammate damaged them while they were blind."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from constants import TICK
from ._shared import my_enemy_flashes
from ._context import Ctx
KIND = 'flash_in_fight'
SIDE = 'play'
TITLE = 'Flash blinded an enemy in a fight'
WHY = 'Your flash blinded an enemy for a second or more and a teammate damaged them while they were blind.'
DO = 'Keep throwing the flash for the teammate who is about to swing.'
BASE = 20


def detect(c: Ctx) -> Iterator[Card | None]:
    me = c.me; rt = c.rt; hurt = c.hurt; mine = c.mine
    for R in c.rounds():
        rn = R.rn; rd = R.all_deaths
        for t, grp in my_enemy_flashes(c, R):
            fought = None
            for x in grp.itertuples():
                e = str(x.user_steamid); t_end = t + int(float(x.blind_duration) * TICK)
                hm = hurt[(hurt['total_rounds_played'] == rn) & (hurt['user_steamid'] == e) & (hurt['tick'] >= t) & (hurt['tick'] <= t_end) & (hurt['attacker_steamid'] != me) & (hurt['attacker_steamid'].isin(R.mates))]
                if len(hm) and fought is None: fought = (x, hm.iloc[0])
            if fought:
                x, h0 = fought; kd = rd[(rd['user_steamid'] == str(x.user_steamid)) & (rd['attacker_team_num'] == R.team) & (rd['tick'] >= t) & (rd['tick'] <= t + int(float(x.blind_duration) * TICK))]
                mp = mine[mine.index <= t]; mp = (mp.iloc[-1].X, mp.iloc[-1].Y) if len(mp) else None
                if mp is not None:
                    yield R.play(t, mp, x.user_name, None, f"Round {rn+1}, {R.side}, {rt(t, rn)} s. Your flash blinded {x.user_name} for {float(x.blind_duration):.1f} s and {h0['attacker_name']} hit them {(int(h0['tick']) - t) / TICK:.1f} s into it." + (f" {kd.iloc[0]['attacker_name']} killed them." if len(kd) else ""), place=None, got_kill=bool(len(kd)))


def adjust(m: Card, add: Add) -> None:
    if m.get('got_kill'): add(8, 'and the kill followed')
