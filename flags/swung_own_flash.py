"""My flash blinded an enemy for a second or more and I came into their view while they were blind."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from constants import TICK
from ._shared import my_enemy_flashes
from ._context import Ctx
KIND = 'swung_own_flash'
SIDE = 'play'
TITLE = 'Swung your own flash'
WHY = 'Your flash blinded an enemy for a second or more and you came into their view while they were blind.'
DO = 'Keep swinging your own flashes; a flash nobody swings only tells the enemy where you are.'
BASE = 25


def detect(c: Ctx) -> Iterator[Card | None]:
    me = c.me; rt = c.rt
    for R in c.rounds():
        rn = R.rn; rd = R.all_deaths
        for t, grp in my_enemy_flashes(c, R):
            swung = None
            for x in grp.itertuples():
                e = str(x.user_steamid); t_end = t + int(float(x.blind_duration) * TICK)
                for ct in range(c.coarse(t) or t, t_end + 1, 8):
                    g = c.by_tick.get(ct)
                    if g is None: continue
                    mr = g[g['steamid'] == me]
                    if len(mr) and bool(mr.iloc[0]['is_alive']):
                        if c.sees(mr.iloc[0], e) and swung is None: swung = (x, ct, (float(mr.iloc[0].X), float(mr.iloc[0].Y)))
            if swung:
                x, ct, mp = swung; kd = rd[(rd['user_steamid'] == str(x.user_steamid)) & (rd['attacker_steamid'] == me) & (rd['tick'] >= t) & (rd['tick'] <= t + int(float(x.blind_duration) * TICK))]
                yield R.play(ct, mp, x.user_name, None, f"Round {rn+1}, {R.side}, {rt(ct, rn)} s. Your flash blinded {x.user_name} for {float(x.blind_duration):.1f} s and you came into their view {(ct - t) / TICK:.1f} s into it." + (" You killed them." if len(kd) else ""), place=None, got_kill=bool(len(kd)))


def adjust(m: Card, add: Add) -> None:
    if m.get('got_kill'): add(8, 'and the kill followed')
