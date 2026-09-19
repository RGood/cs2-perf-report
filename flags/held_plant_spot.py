"""An enemy started the plant while I was alive and had them in view or within 15 m."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from constants import TICK
from ._context import Ctx, dist_m
KIND = 'held_plant_spot'
SIDE = 'play'
TITLE = 'Held the plant spot'
WHY = ('An enemy started the plant while you were alive and had them in view or within 15 m. You were where the plant happens,'
       ' not at the site entrance.')
DO = 'Keep holding the plant spot itself; it is where the round is decided.'
BASE = 35


def detect(c: Ctx) -> Iterator[Card | None]:
    pb = c.D.get('plant_begin'); me = c.me; plant = c.plant
    if pb is None or not len(pb): return
    for R in c.rounds():
        rn = R.rn; rk = R.my_kills
        for r in pb[(pb['total_rounds_played'] == rn) & (pb['user_steamid'].isin(R.foes))].itertuples():
            t = int(r.tick); who = str(r.user_steamid); mr = c.row(t, me); pr = c.row(t, who)
            if mr is None or not bool(mr['is_alive']) or pr is None: continue
            mpos = (float(mr.X), float(mr.Y)); ppos = (float(pr.X), float(pr.Y)); dm = dist_m(mpos, ppos)
            if c.sees(pr, me) or dm <= 15:
                killed = bool(len(rk[(rk['user_steamid'] == who) & (rk['tick'] >= t) & (rk['tick'] <= t + 5 * TICK)]))
                planted = bool(((plant['total_rounds_played'] == rn) & (plant['tick'] >= t) & (plant['tick'] <= t + 5 * TICK)).any())
                yield c.card(rn, R.side, t, str(mr['last_place_name']), mpos, facts=f"Round {rn+1}, CT, {c.rt(t, rn)} s. {r.user_name} started the plant {dm:.0f} m from you" + (" while you had them in view." if c.sees(pr, me) else ".") + (" You killed them." if killed else (" The plant went down." if planted else " The plant was aborted.")), got_kill=killed, opponents=[(str(r.user_name), ppos)])


def adjust(m: Card, add: Add) -> None:
    if m.get('got_kill'): add(8, 'and the kill followed')
