"""Bought a gun without a helmet, with the money for one, on a buy round, against three or more guns a helmet would have mattered against."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._economy import freeze_economy
from ._weapons import best_gun, norm, wkey, ONE_SHOT_HELMET
from ._context import Ctx
KIND = 'no_helmet'
SIDE = 'mistake'
TITLE = 'No helmet when it mattered'
WHY = ('You bought a gun with no helmet, with the money for one, on a round your team was buying (not a save or eco), while '
       'three or more enemies carried weapons a helmet stops from killing with one headshot: pistols other than the Deagle and'
       ' R8, SMGs, the M4s, Famas, Galil, shotguns, and the AUG beyond mid range. Against an AK, SG 553, AWP, or Scout the '
       'helmet changes nothing, so those rounds are not flagged.')
DO = ('Buy the helmet on every round where the enemy is on pistols, SMGs, or M4-class rifles. It turns their headshot into a '
      'survivable hit.')
BASE = 10


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        e = freeze_economy(c, R)
        # not on a save: you bought a gun this round and the team is not on an eco (a helmet would break the next buy)
        if not (e and e.xr.has_helmet == False and e.bal >= 1000 and e.my_eq >= 1500 and e.avg >= 2000): continue
        g0 = R.g0
        if g0 is None: continue
        sens = []       # enemies whose best gun does not one-shot a helmeted head
        for f_ in g0[(g0['team_num'] != R.team) & (g0['team_num'] > 1)].itertuples():
            try: bg = best_gun([str(w) for w in f_.inventory])
            except TypeError: bg = None
            if bg and not any(k in norm(bg[0]) for k in ONE_SHOT_HELMET): sens.append(f"{f_.name} ({wkey(bg[0])})")
        if len(sens) >= 3:
            yield c.card(R.rn, R.side, R.ft, 'spawn', e.spawn, facts=f"Round {R.rn+1}, {R.side}. No helmet with ${e.bal} in the bank. Enemies carrying guns a helmet stops from one-shotting the head: {', '.join(sens)}.")
