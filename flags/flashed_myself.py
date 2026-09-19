"""My own flashbang blinded me for more than 2 s."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'flashed_myself'
SIDE = 'mistake'
TITLE = 'Flashed myself'
WHY = 'Your own flashbang blinded you for more than 2 s.'
DO = 'Turn away or throw it further ahead; a self-flash gives the enemy a free peek.'
BASE = 12

MIN_BLIND_S = 2.0


def detect(c: Ctx) -> Iterator[Card | None]:
    bl = c.blind
    if not len(bl): return
    for R in c.rounds():
        sf = bl[(bl['total_rounds_played'] == R.rn) & (bl['attacker_steamid'] == c.me) & (bl['user_steamid'] == c.me) & (bl['blind_duration'] > MIN_BLIND_S)]
        for r in sf.itertuples():
            mr = c.row(int(r.tick), c.me)
            if mr is not None:
                yield c.card(R.rn, R.side, int(r.tick), str(mr['last_place_name']), (float(mr.X), float(mr.Y)), facts=f"Round {R.rn+1}, {R.side}, {c.rt(int(r.tick), R.rn)} s. Your own flash blinded you for {float(r.blind_duration):.1f} s.")
