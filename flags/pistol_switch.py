"""My primary's clip ran out in a fight and I was firing the pistol within 3 s instead of reloading."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from constants import TICK
from ._weapons import wkey, PISTOLS
from ._context import Ctx
KIND = 'pistol_switch'
SIDE = 'play'
TITLE = 'Switched to pistol when dry'
WHY = "Your primary's clip ran out in a fight and you were firing the pistol within 3 s instead of reloading."
DO = 'Keep the switch; a reload in a close fight is a death.'
BASE = 12


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        rf = R.rf; rk = R.my_kills
        last_flag = -10 ** 9
        for r in rf[rf['weapon'].str.contains('|'.join(PISTOLS), na=False)].itertuples():
            t = int(r.tick)
            if t - last_flag < 5 * TICK: continue
            prim = rf[(rf['tick'] >= t - 3 * TICK) & (rf['tick'] < t) & (~rf['weapon'].str.contains('|'.join(PISTOLS), na=False))]
            if not len(prim): continue
            xr2 = c.x(int(prim.iloc[-1]['tick']), c.me)
            if xr2 is None or not (xr2.active_weapon_ammo == xr2.active_weapon_ammo) or float(xr2.active_weapon_ammo) > 1: continue
            mr = c.row(t, c.me)
            if mr is None or not (r.user_X == r.user_X): continue
            killed = bool(len(rk[(rk['tick'] >= t) & (rk['tick'] <= t + 3 * TICK) & (rk['weapon'].str.contains('|'.join(PISTOLS), na=False))]))
            last_flag = t
            yield c.card(R.rn, R.side, t, str(r.user_last_place_name), (float(r.user_X), float(r.user_Y)), facts=f"Round {R.rn+1}, {R.side}, {c.rt(t, R.rn)} s. Your {wkey(prim.iloc[-1]['weapon'])} ran dry and you were firing the {wkey(r.weapon)} {(t - int(prim.iloc[-1]['tick'])) / TICK:.1f} s later." + (" You got the kill." if killed else ""), got_kill=killed)


def adjust(m: Card, add: Add) -> None:
    if m.get('got_kill'): add(8, 'and the kill followed')
