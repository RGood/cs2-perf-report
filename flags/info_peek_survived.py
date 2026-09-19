"""In an enemy's view for under half a second within 30 m; they fired, I took no damage and backed off more than 3 m."""
from __future__ import annotations
from typing import Iterator
from typing import Collection
from report_types import Card, Row
from constants import TICK
from ._context import Ctx, dist_m
KIND = 'info_peek_survived'
SIDE = 'play'
TITLE = 'Info peek survived'
WHY = ("You were in an enemy's view for under half a second within 30 m, they fired, you took no damage and backed off more "
       'than 3 m.')
DO = 'Keep the shoulder peeks short and the retreat immediate.'
BASE = 14


def seers(row: Row | None, among: Collection[str] | None) -> list[str]:
    try: s = [str(v) for v in row['approximate_spotted_by']] if row is not None else []
    except TypeError: s = []
    return [v for v in s if v in among] if among is not None else s


def detect(c: Ctx) -> Iterator[Card | None]:
    me = c.me; fire = c.fire; hurt = c.hurt
    for R in c.rounds():
        for ct in range(R.ft, R.end, 8):
            mr = c.row(ct, me)
            if mr is None or not bool(mr['is_alive']): continue
            now = seers(mr, R.foes)
            if not now: continue
            if any(s in seers(c.row(ct - 8, me), None) for s in now): continue        # not the first sample in their view
            n = 0       # how long it lasted
            for ct2 in range(ct, ct + 2 * TICK, 8):
                if any(s in seers(c.row(ct2, me), None) for s in now): n += 8
                else: break
            if n / TICK >= 0.5: continue
            e = now[0]; er = c.row(ct, e)
            if er is None or dist_m((float(mr.X), float(mr.Y)), (float(er.X), float(er.Y))) > 30: continue
            ef = fire[(fire['user_steamid'] == e) & (fire['tick'] >= ct) & (fire['tick'] <= ct + TICK)]
            if not len(ef): continue
            hit = hurt[(hurt['user_steamid'] == me) & (hurt['tick'] >= ct) & (hurt['tick'] <= ct + 2 * TICK)]
            r3 = c.row(ct + 2 * TICK, me)
            if not len(hit) and r3 is not None and dist_m((float(r3.X), float(r3.Y)), (float(mr.X), float(mr.Y))) > 3:
                yield c.card(R.rn, R.side, ct, str(mr['last_place_name']), (float(mr.X), float(mr.Y)), facts=f"Round {R.rn+1}, {R.side}, {c.rt(ct, R.rn)} s. You were in {c.names.get(e, e)}'s view for {n / TICK:.2f} s at {dist_m((float(mr.X), float(mr.Y)), (float(er.X), float(er.Y))):.0f} m; they fired {len(ef)} shots, you took no damage and backed off {dist_m((float(r3.X), float(r3.Y)), (float(mr.X), float(mr.Y))):.0f} m.", opponents=[(c.names.get(e, e), (float(er.X), float(er.Y)))])
                break       # one per round
