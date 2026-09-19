"""Last alive, and the round was won."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from ._context import Ctx
KIND = 'clutch'
SIDE = 'play'
RETIRED = "an outcome, not a decision"
TITLE = 'Clutch won'
WHY = ('You were the last player alive and won the round. Every decision after your last teammate died was correct enough to '
       'beat the numbers.')
DO = ('Keep playing clutches slowly: isolate one fight at a time, use the clock, and let the bomb or the defuse force them to'
      ' come to you.')
BASE = 60


def detect(c: Ctx) -> Iterator[Card | None]:
    rt = c.rt; mine = c.mine
    for R in c.rounds():
        rn = R.rn; rd = R.all_deaths; rk = R.all_my_kills
        team_deaths = rd[rd['user_team_num'] == R.team]
        if not (R.won and not R.died and len(team_deaths) >= 4): continue
        t4 = int(team_deaths.iloc[3]['tick'])
        ma, fo, md, mp = R.state(t4 + 8)
        if fo and fo >= 1:
            kills_after = int((rk['tick'] > t4).sum())
            end = int(c.rend.get(rn, c.fz.get(rn + 1, int(mine.index.max()))))
            last = mine[(mine.index >= t4) & (mine.index <= end)]; lp = (last.iloc[-1].X, last.iloc[-1].Y) if len(last) else mp
            gg = c.by_tick.get(c.coarse(t4 + 8)); foes_pos = [(str(x.name), (x.X, x.Y)) for x in gg[(gg['team_num'] != R.team) & (gg['is_alive'] == True)].itertuples()] if gg is not None else []
            yield R.play(int(last.index[-1]) if len(last) else t4, lp, None, None, f"Round {rn+1}, {R.side}. Last alive from {rt(t4, rn)} s against {fo}. {kills_after} kills after that, {R.dmg_to_enemies} damage in the round, and the round was won.", place=None, vs=fo, kills=kills_after, opponents=foes_pos)


def adjust(m: Card, add: Add) -> None:
    add(12 * (m.get('vs', 1) - 1), f"1v{m.get('vs')}")
