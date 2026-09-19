"""My flash popped near an enemy who had been facing it, turned away before the pop, and was not punished within 2 s."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from constants import TICK
from ._context import Ctx
KIND = 'flash_reacted'
SIDE = 'mistake'
TITLE = 'Flash they turned away from'
WHY = ('Your flash popped within 25 m of an enemy who had been facing it at the throw, and they turned away or ducked before '
       'it popped (blinded for under a second, or not at all), then were not punished within 2 s. The flash was readable: too '
       'long in the air, or thrown where they could see it coming.')
DO = ('Pop flashes faster and higher, or from behind cover so the enemy does not see the throw. A flash the enemy can turn '
      'from only costs you the grenade.')
BASE = 14


def detect(c: Ctx) -> Iterator[Card | None]:
    for R in c.rounds():
        rd = R.rd
        for det, thr, land, turned in R.flash_turns():
            for e, blind_s, dm, off_thr, off_pop in turned:
                if blind_s >= 1.0: continue                 # it still blinded them: not a read flash
                kd = rd[(rd['user_steamid'] == str(e.steamid)) & (rd['attacker_team_num'] == R.team) & (rd['tick'] >= det) & (rd['tick'] <= det + 2 * TICK)]
                if len(kd): continue                        # the turn was punished: that is flash_turned_kill
                mr = c.row(thr, c.me)
                if mr is None or not (mr.X == mr.X): continue
                yield c.card(R.rn, R.side, det, str(mr['last_place_name']), (float(mr.X), float(mr.Y)), facts=f"Round {R.rn+1}, {R.side}, {c.rt(det, R.rn)} s. Your flash was in the air {(det - thr) / TICK:.1f} s and popped {dm:.0f} m from {e.name}, who faced it at the throw ({off_thr:.0f}° off) and away from it at the pop ({off_pop:.0f}° off)" + (f", blinded only {blind_s:.1f} s" if blind_s > 0 else ", not blinded at all") + ". Nobody punished the turn within 2 s.", air_s=round((det - thr) / TICK, 2), opponents=[(str(e.name), (float(e.X), float(e.Y)))])
                break


def adjust(m: Card, add: Add) -> None:
    add(min(8, int((m.get('air_s') or 0) * 3)), f"{m.get('air_s')} s in the air")
