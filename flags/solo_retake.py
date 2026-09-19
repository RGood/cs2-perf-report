"""CT post-plant: came within 20 m of the bomb with no teammate within 15 m and died, unless the solo retake was the right call."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
from constants import TICK
from ._context import Ctx, dist_m
KIND = 'solo_retake'
SIDE = 'mistake'
TITLE = 'Solo retake'
WHY = ('As CT after the plant you came within 20 m of the bomb with no teammate within 15 m and died. Not counted when the '
       'solo retake was the right call or not a choice: you were the last alive against a single enemy; the last alive with '
       'less equipment to save than the loss bonus pays anyway; or you had gone in with a teammate who died in the last 8 s '
       'while you were already committed to the site. Counted, but lightly, when you were last alive with a gun worth saving '
       'against two or more.')
DO = 'Retake together. One player into a post-plant is a free kill and no defuse.'
BASE = 40

BOMB_M = 20             # this close to the bomb is "retaking"
ALONE_M = 15            # no teammate within this
COMMIT_S = 8            # a partner who died this recently ...
COMMIT_BOMB_M = 25      # ... within this of the bomb, while I was this close to the bomb ...
COMMIT_MATE_M = 15      # ... or this close to them, means I was already committed


def detect(c: Ctx) -> Iterator[Card | None]:
    me = c.me
    for R in c.rounds():
        if R.side != 'CT': continue
        rn = R.rn; rd = R.rd
        for x in R.deaths_of_mine():
            if not x.by_enemy: continue
            t = x.t; pos = x.pos; nm = x.nm
            pl = c.plant[(c.plant['total_rounds_played'] == rn) & (c.plant['tick'] < t)]
            if not (len(pl) and pl.iloc[-1]['user_X'] == pl.iloc[-1]['user_X']): continue
            bpos = (float(pl.iloc[-1]['user_X']), float(pl.iloc[-1]['user_Y']))
            if not (dist_m(pos, bpos) <= BOMB_M and (nm is None or nm[0] > ALONE_M)): continue
            ma_, fo_ = c.alive_counts(t - 1, R.team); mr = c.row(t - 1, me)
            eq_ = int(mr['current_equip_value']) if mr is not None and mr['current_equip_value'] == mr['current_equip_value'] else 0
            bonus_ = c.loss_bonus(rn)
            last_alive = (ma_ is not None and ma_ <= 1)
            # a two-man retake where the partner died first: if you were already committed when they died, the solo part was not your decision
            committed_with = None
            for md_ in rd[(rd['user_team_num'] == R.team) & (rd['user_steamid'] != me) & (rd['tick'] < t) & (rd['tick'] >= t - COMMIT_S * TICK)].itertuples():
                if not (md_.user_X == md_.user_X): continue
                mdp = (float(md_.user_X), float(md_.user_Y)); me_then = c.row(int(md_.tick), me)
                if me_then is None or not (me_then.X == me_then.X): continue
                mp_then = (float(me_then.X), float(me_then.Y))
                if dist_m(mdp, bpos) <= COMMIT_BOMB_M and (dist_m(mp_then, bpos) <= COMMIT_BOMB_M or dist_m(mp_then, mdp) <= COMMIT_MATE_M):
                    committed_with = (str(md_.user_name), round((t - int(md_.tick)) / TICK, 1)); break
            # the right call, or not a choice: last alive against one enemy, with less to save than the loss bonus pays, or already committed
            if last_alive and (fo_ == 1 or eq_ < bonus_ or committed_with): continue
            yield x.card(f" Post-plant, {dist_m(pos, bpos):.0f} m from the bomb, " + (f"nearest teammate {nm[0]:.0f} m away." if nm else "no teammate alive.") + (f" You were the last alive against {fo_} enemies with ${eq_} of equipment (the loss bonus was ${bonus_})." if last_alive else ""),
                         last_alive=last_alive, foes_left=fo_, equip_kept=eq_, extra_pos=bpos, extra_label='bomb')


def adjust(m: Card, add: Add) -> None:
    if m.get('last_alive'): add(-15, f"last alive against {m.get('foes_left')}: a save was the only alternative")
