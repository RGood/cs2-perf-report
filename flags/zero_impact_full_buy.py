"""A full buy that ended with no damage, no grenade thrown, and a death."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from demolib import nade_list
from ._context import Ctx
KIND = 'zero_impact_full_buy'
SIDE = 'mistake'
RETIRED = "an outcome, not a decision"
SKIP_CONTEXT = {'dmg_round'}
TITLE = 'Full buy, zero impact'
WHY = ('A full buy that ends with no damage and no grenades thrown is the most expensive possible round. The money was spent '
       'and nothing was bought with it.')
DO = ('If the round is going badly, your grenades still have value: throw them for a teammate or for the retake. Get damage '
      'in before you die.')
BASE = 50


def detect(c: Ctx) -> Iterator[Card | None]:
    D = c.D; me = c.me
    for R in c.rounds():
        rn = R.rn; r = R.me0
        if r is None: continue
        h = c.hurt[(c.hurt['total_rounds_played'] == rn) & (c.hurt['attacker_steamid'] == me)]
        thrown = c.nades[c.nades['total_rounds_played'] == rn]
        died = R.all_my_deaths
        if int(r['current_equip_value']) >= 3700 and int(h['dmg_health'].sum()) == 0 and not len(thrown) and len(died):
            dd = died.iloc[0]
            yield dict(round=rn + 1, side=R.side, time=c.rt(int(dd['tick']), rn), z=float(dd['user_Z']), place=dd['user_last_place_name'], pos=(dd['user_X'], dd['user_Y']), killer=dd['attacker_name'],
                       kpos=(dd['attacker_X'], dd['attacker_Y']), kplace=dd['attacker_last_place_name'], weapon=dd['weapon'], my_weapon=dd['user_active_weapon_name'], dist=0, near=None,
                       path=[(x.X, x.Y) for x in c.mine[(c.mine.index >= R.ft) & (c.mine.index <= int(dd['tick']))].itertuples()][::4], mates_alive=None, nades_thrown=[], won=R.won,
                       facts=f"Round {rn+1}, {R.side}. Equipment ${int(r['current_equip_value'])}, {len(nade_list(r['inventory']))} grenades bought, none thrown, 0 damage, died at {dd['user_last_place_name']} at {c.rt(int(dd['tick']), rn)} s.")
