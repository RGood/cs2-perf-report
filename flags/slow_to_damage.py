"""More than 0.7 s between an enemy becoming mine to shoot and my first damage on them, and I died to them."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from constants import TICK
from ._weapons import enough_for_kill, wkey
from ._context import Ctx
KIND = 'slow_to_damage'
SIDE = 'mistake'
TITLE = 'Slow to damage'
WHY = ('More than 0.7 s passed between an enemy becoming yours to shoot and your first damage on them, and you died to them. '
       'The clock starts when they came into your view, or later if they were still fighting a teammate at that moment or you '
       'were in a reload you needed. A reload does not excuse the delay when the clip still held enough for a kill (about '
       'twice the hits that weapon needs, at a typical hit rate); then the reload is the cause of it.')
DO = 'Decide before the peek. If the crosshair is placed, the first shot goes out on sight.'
BASE = 14

SLOW_S = 0.7
RELOAD_S = 2.5


def detect(c: Ctx) -> Iterator[Card | None]:
    D = c.D; me = c.me; hurt = c.hurt; rt = c.rt
    for R in c.rounds():
        rn = R.rn; rd = R.rd; rh = R.rh; rf = R.rf; mates = R.mates
        for x in R.deaths_of_mine():
            if not x.by_enemy: continue
            d = x.d; t = x.t; killer = x.killer
            fs = c.first_seen(me, killer, t, 6.0)
            if fs is None: continue
            hk = rh[(rh['user_steamid'] == killer) & (rh['tick'] >= fs)]
            if not (len(hk) and (int(hk.iloc[0]['tick']) - fs) / TICK > SLOW_S): continue
            t_hit = int(hk.iloc[0]['tick']); clock = fs; notes = []
            # the fight was a teammate's first: the clock starts when it became yours (the teammate died or the exchange ended)
            ex = hurt[(hurt['total_rounds_played'] == rn) & (hurt['tick'] >= fs - TICK) & (hurt['tick'] < t_hit) &
                      (((hurt['attacker_steamid'] == killer) & (hurt['user_steamid'].isin(mates))) | ((hurt['user_steamid'] == killer) & (hurt['attacker_steamid'].isin(mates))))]
            if len(ex):
                t_ex = int(ex['tick'].max()); md_ = rd[(rd['attacker_steamid'] == killer) & (rd['user_steamid'].isin(mates)) & (rd['tick'] >= fs) & (rd['tick'] <= t_hit)]
                if len(md_): t_ex = max(t_ex, int(md_.iloc[0]['tick']))
                if t_ex > clock:
                    notes.append(f"{d.attacker_name} was fighting {md_.iloc[0]['user_name']}, who died at {rt(int(md_.iloc[0]['tick']), rn)} s" if len(md_) else f"{d.attacker_name} was trading damage with a teammate until {rt(t_ex, rn)} s")
                    clock = t_ex
            # a reload in progress: you cannot shoot, so its time does not count, unless it was a poorly timed reload
            rl_ = D.get('reloads'); rl_ = rl_[(rl_['user_steamid'] == me) & (rl_['tick'] >= fs - int(RELOAD_S * TICK)) & (rl_['tick'] < t_hit)] if rl_ is not None and len(rl_) else None
            bad_reload = None
            if rl_ is not None and len(rl_):
                t_rl = int(rl_.iloc[-1]['tick']); xr_ = c.x(t_rl, me)
                if not len(rf[(rf['tick'] > t_rl) & (rf['tick'] < t_hit)]) or t_rl >= fs - int(RELOAD_S * TICK):
                    left_ = float(xr_.active_weapon_ammo) if xr_ is not None and xr_.active_weapon_ammo == xr_.active_weapon_ammo else None
                    wpn_ = str(xr_.active_weapon_name) if xr_ is not None else ''
                    enough_, btk_, need_ = enough_for_kill(wpn_, left_) if left_ is not None else (False, None, None)
                    if enough_ and left_ is not None:
                        bad_reload = (t_rl, int(left_), wpn_, btk_, need_)
                    else:
                        clock = max(clock, t_rl + int(RELOAD_S * TICK)); notes.append(f"you were reloading (started {rt(t_rl, rn)} s" + (f" with {int(left_)} rounds left, short of the ~{need_} a kill takes)" if left_ is not None else ")"))
            delay = (t_hit - clock) / TICK
            if bad_reload:
                yield x.card(f" {d.attacker_name} came into your view at {rt(fs, rn)} s; your first damage on them came {(t_hit - fs) / TICK:.1f} s later. You had started a reload at {rt(bad_reload[0], rn)} s with {bad_reload[1]} rounds still in the {wkey(bad_reload[2])}: about {bad_reload[3]} hits kill, so roughly {bad_reload[4]} shots would have done it. The delay came from a reload you did not need yet.", bad_reload=True)
            elif delay > SLOW_S:
                yield x.card(f" {d.attacker_name} came into your view at {rt(fs, rn)} s" + (("; " + '; '.join(notes)) if notes else "") + f". Counting from {rt(clock, rn)} s, your first damage on them came {delay:.1f} s later.")
