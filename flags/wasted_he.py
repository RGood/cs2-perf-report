"""After contact, my HE did no damage although an enemy had been spotted within 30 m of me."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx, dist_m
from ._shared import my_pops
KIND = 'wasted_he'
SIDE = 'mistake'
TITLE = 'Wasted HE'
WHY = 'Your HE grenade did no damage, thrown after your team had already spotted the enemy within 30 m.'
DO = 'After contact an HE goes on the stack or the choke the enemy is holding, not into an empty area.'
BASE = 12


def detect(c: Ctx) -> Iterator[Card | None]:
    hurt = c.hurt
    for R in c.rounds():
        contact_t = R.first_contact_tick
        for t, lp, fo, mpos, mplace in my_pops(c, R, 'hegrenade'):
            if not (contact_t is not None and t > contact_t): continue
            dmg = int(hurt[(hurt['total_rounds_played'] == R.rn) & (hurt['attacker_steamid'] == c.me) & (hurt['weapon'] == 'hegrenade') & ((hurt['tick'] - t).abs() <= 8)]['dmg_health'].sum())
            spotted_near = [f for f in fo.itertuples() if bool(f.spotted) and dist_m(mpos, (float(f.X), float(f.Y))) <= 30]
            if dmg == 0 and spotted_near:
                yield c.card(R.rn, R.side, t, mplace, mpos, facts=f"Round {R.rn+1}, {R.side}, {c.rt(t, R.rn)} s. Your HE did no damage; {', '.join(str(f.name) for f in spotted_near[:3])} had been spotted within 30 m when it went off.", extra_pos=lp, extra_label='HE', nades_thrown=[('hegrenade', mpos)])
