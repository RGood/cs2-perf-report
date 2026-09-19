"""My flash made an enemy turn away before it popped, and my team killed them within 2 s."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from constants import TICK
from ._context import Ctx
KIND = 'flash_turned_kill'
SIDE = 'play'
TITLE = 'Flash turned them for the kill'
WHY = ('Your flash made an enemy turn away from it before it popped (they were facing it at the throw and facing away at the '
       'pop) and your team killed them within 2 s, whether or not they were blinded. Turning an enemy is the flash doing its '
       'job even when the blind misses.')
DO = ('Keep throwing the flash so the enemy has to choose between the blind and the turn; either one is a kill for the '
      'teammate swinging.')
BASE = 28


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        rd = R.rd
        for det, thr, land, turned in R.flash_turns():
            for e, blind_s, dm, off_thr, off_pop in turned:
                kd = rd[(rd['user_steamid'] == str(e.steamid)) & (rd['attacker_team_num'] == R.team) & (rd['tick'] >= det) & (rd['tick'] <= det + 2 * TICK)]
                if not len(kd): continue
                k0 = kd.iloc[0]; mr = c.row(thr, c.me)
                if mr is None or not (mr.X == mr.X): continue
                yield c.card(R.rn, R.side, det, str(mr['last_place_name']), (float(mr.X), float(mr.Y)), facts=f"Round {R.rn+1}, {R.side}, {c.rt(det, R.rn)} s. Your flash popped {dm:.0f} m from {e.name}; they faced it at the throw ({off_thr:.0f}° off) and had turned away by the pop ({off_pop:.0f}° off)" + (f", blinded {blind_s:.1f} s" if blind_s > 0 else ", not blinded") + f". {k0['attacker_name']} killed them {(int(k0['tick']) - det) / TICK:.1f} s after the pop.", got_kill=(str(k0['attacker_steamid']) == c.me), opponents=[(str(e.name), (float(e.X), float(e.Y)))])
                break


def adjust(m: Card, add: Add) -> None:
    if m.get('got_kill'): add(6, 'and you took the kill yourself')
