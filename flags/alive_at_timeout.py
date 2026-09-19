"""T alive when the round timer ran out with no plant: no loss bonus for the round."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from ._context import Ctx
KIND = 'alive_at_timeout'
SIDE = 'mistake'
TITLE = 'Alive when the clock ran out'
WHY = ('As a T you were still alive when the round timer expired with no plant. A T who is alive at the time-out gets no loss '
       "bonus at all, so the round cost the team's economy as well as the round. Worse still if you were then killed after the"
       ' timer, losing the gun too.')
DO = ('Before the last 15 s either plant, force the fight, or make sure you know the timer: a death fighting keeps the loss '
      'bonus; running the clock out throws it away.')
BASE = 55


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        if not (R.side == 'T' and not R.won and c.D.get('round_reason', {}).get(R.rn) in ('target_saved', 'time_ran_out')): continue
        rdm = R.my_deaths; t_end = R.end
        if len(rdm) and int(rdm.iloc[0]['tick']) <= t_end: continue          # died before the timer: the loss bonus is kept
        mr = c.row(t_end, c.me)
        if mr is not None and mr.X == mr.X:
            eq_ = int(mr['current_equip_value']) if mr['current_equip_value'] == mr['current_equip_value'] else 0
            died_after = bool(len(rdm) and int(rdm.iloc[0]['tick']) > t_end)
            bonus = c.loss_bonus(R.rn)
            yield c.card(R.rn, R.side, t_end, str(mr['last_place_name']), (float(mr.X), float(mr.Y)), facts=f"Round {R.rn+1}, T. The timer ran out with you alive and no plant: no loss bonus (it would have been ${bonus}). You were carrying ${eq_} of equipment" + (" and were killed after the timer, so that went too." if died_after else "."), died_after=died_after, bonus=bonus, equip_kept=eq_)


def adjust(m: Card, add: Add) -> None:
    add(10 if m.get('died_after') else 0, 'killed after the timer as well: the gun went too')
    add(min(8, int((m.get('bonus') or 1400) // 500) - 2), f"a ${m.get('bonus')} loss bonus forfeited")
