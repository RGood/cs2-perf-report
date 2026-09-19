"""An enemy started a defuse while I was alive and had them in view or within 15 m."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from constants import TICK
from ._context import Ctx, dist_m
KIND = 'watched_bomb'
SIDE = 'play'
TITLE = 'Watched the bomb post-plant'
WHY = ('An enemy started a defuse while you were alive and had them in view or within 15 m. Kill or not, you were in a '
       'position to stop it.')
DO = 'Keep holding a line onto the bomb after the plant rather than hunting for picks.'
BASE = 35


def detect(c: Ctx) -> Iterator[Card | None]:
    db = c.D.get('defuse_begin'); dfd = c.D.get('defused'); me = c.me
    if db is None or not len(db): return
    for R in c.rounds():
        rn = R.rn; rk = R.my_kills
        for r in db[db['total_rounds_played'] == rn].itertuples():
            t = int(r.tick); who = str(r.user_steamid)
            if who not in R.foes: continue
            finished = bool(dfd is not None and len(dfd) and ((dfd['total_rounds_played'] == rn) & (dfd['tick'] >= t) & (dfd['tick'] <= t + 11 * TICK)).any())
            mr = c.row(t, me); dr = c.row(t, who)
            if mr is None or not bool(mr['is_alive']) or dr is None: continue
            mpos = (float(mr.X), float(mr.Y)); dpos = (float(dr.X), float(dr.Y)); dm = dist_m(mpos, dpos)
            if c.sees(dr, me) or dm <= 15:
                killed = bool(len(rk[(rk['user_steamid'] == who) & (rk['tick'] >= t) & (rk['tick'] <= t + 10 * TICK)]))
                yield c.card(rn, R.side, t, str(mr['last_place_name']), mpos, facts=f"Round {rn+1}, CT, {c.rt(t, rn)} s. {r.user_name} started the defuse {dm:.0f} m from you" + (" while you had them in view." if c.sees(dr, me) else ".") + (" You killed them." if killed else (" The defuse finished." if finished else " The defuse was stopped.")), got_kill=killed, opponents=[(str(r.user_name), dpos)])


def adjust(m: Card, add: Add) -> None:
    if m.get('got_kill'): add(8, 'and the kill followed')
