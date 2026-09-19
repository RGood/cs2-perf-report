"""My flash blinded an enemy, but nobody on my team came into their view or damaged them within 3 s."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._shared import my_pops, enemies_blinded
from ._context import Ctx
KIND = 'flash_no_swing'
SIDE = 'mistake'
TITLE = 'Flash without a swing'
WHY = ('Your flash blinded an enemy for a second or more, but neither you nor a teammate came into their view within 3 s and '
       'nobody damaged them.')
DO = 'A flash is a timer. Somebody must swing while it runs, or it only tells the enemy where you are.'
BASE = 6


def detect(c: Ctx) -> Iterator[Card | None]:
    hurt = c.hurt; me = c.me
    for R in c.rounds():
        for t, lp, fo, mpos, mplace in my_pops(c, R, 'flashbang'):
            eb = enemies_blinded(c, R, t)
            if not len(eb): continue
            swung = False
            for ct in range(c.coarse(t), t + 3 * TICK, 8):
                g2 = c.by_tick.get(ct)
                if g2 is None: continue
                for x in eb.itertuples():
                    er = g2[g2['steamid'] == str(x.user_steamid)]
                    if len(er) and any(c.sees(er.iloc[0], s) for s in list(R.mates) + [me]): swung = True
            dmg = int(hurt[(hurt['total_rounds_played'] == R.rn) & (hurt['tick'] >= t) & (hurt['tick'] <= t + 3 * TICK) & (hurt['user_steamid'].isin(set(str(x) for x in eb['user_steamid']))) & (hurt['attacker_steamid'].isin(R.mates | {me}))]['dmg_health'].sum())
            if not swung and dmg == 0:
                yield c.card(R.rn, R.side, t, mplace, mpos, facts=f"Round {R.rn+1}, {R.side}, {c.rt(t, R.rn)} s. Your flash blinded {', '.join(f'{x.user_name} ({float(x.blind_duration):.1f} s)' for x in eb.itertuples())}, but nobody on your team came into their view or damaged them in the next 3 s.", extra_pos=lp, extra_label='flash popped', nades_thrown=[('flashbang', mpos)])
