"""Started the defuse with enemies still alive, and either finished it or died on it."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from constants import TICK
from ._context import Ctx
KIND = 'committed_defuse'
SIDE = 'play'
TITLE = 'Committed to the defuse'
WHY = ('You started the defuse with enemies still alive. The card says whether any of them could see you and whether the '
       'defuse finished.')
DO = 'Keep committing when the team has cleared enough, and use the fake when it has not.'
BASE = 45


def detect(c: Ctx) -> Iterator[Card | None]:
    db = c.D.get('defuse_begin'); dfd = c.D.get('defused'); me = c.me
    if db is None or not len(db): return
    for R in c.rounds():
        rn = R.rn; rdm = R.my_deaths
        for r in db[db['total_rounds_played'] == rn].itertuples():
            t = int(r.tick)
            if str(r.user_steamid) != me: continue
            finished = bool(dfd is not None and len(dfd) and ((dfd['total_rounds_played'] == rn) & (dfd['tick'] >= t) & (dfd['tick'] <= t + 11 * TICK)).any())
            ma, fo = c.alive_counts(t - 1, R.team); mr = c.row(t, me)
            if mr is None or not bool(mr['is_alive']) or not fo: continue
            try: seen = [c.names.get(v, v) for v in (str(s) for s in mr['approximate_spotted_by']) if v in R.foes]
            except TypeError: seen = []
            died_soon = bool(len(rdm) and t < int(rdm.iloc[0]['tick']) <= t + 11 * TICK)
            if finished or died_soon:
                yield c.card(rn, R.side, t, str(mr['last_place_name']), (float(mr.X), float(mr.Y)), facts=f"Round {rn+1}, CT, {c.rt(t, rn)} s. Started the defuse with {fo} enemies alive" + (f", in view of {', '.join(seen)}" if seen else ", unseen") + (". It finished." if finished else ". You died before it finished."), finished=finished)


def adjust(m: Card, add: Add) -> None:
    if m.get('finished'): add(10, 'the defuse finished')
