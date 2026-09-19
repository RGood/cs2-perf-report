"""My HE damaged two or more enemies."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._context import Ctx
KIND = 'he_stack'
SIDE = 'play'
RETIRED = "an outcome; the decision is measured by util_on_signal"
TITLE = 'HE on a stack'
WHY = 'Your HE damaged two or more enemies.'
DO = 'Keep throwing the HE where they group.'
BASE = 18


def detect(c: Ctx) -> Iterator[Card | None]:
    hurt = c.hurt; dt = c.deton
    for R in c.rounds():
        dt_r = dt[(dt['steamid'] == c.me) & (dt['tick'] >= R.ft) & (dt['tick'] < R.end)] if len(dt) else dt
        for r in dt_r.itertuples():
            if r.kind != 'hegrenade': continue
            t = int(r.tick); lp = (float(r.x), float(r.y)); mr = c.row(t, c.me)
            mpos = (float(mr.X), float(mr.Y)) if mr is not None else lp; mplace = str(mr['last_place_name']) if mr is not None else None
            hh = hurt[(hurt['total_rounds_played'] == R.rn) & (hurt['attacker_steamid'] == c.me) & (hurt['weapon'] == 'hegrenade') & ((hurt['tick'] - t).abs() <= 8) & (hurt['user_steamid'].isin(R.foes))]
            if hh['user_steamid'].nunique() >= 2:
                yield c.card(R.rn, R.side, t, mplace, mpos, facts=f"Round {R.rn+1}, {R.side}, {c.rt(t, R.rn)} s. Your HE hit " + ', '.join(f"{n} ({int(v)})" for n, v in hh.groupby('user_name')['dmg_health'].sum().items()) + ".", extra_pos=lp, extra_label='HE', nades_thrown=[('hegrenade', mpos)], dmg=int(hh['dmg_health'].sum()))
