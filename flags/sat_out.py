"""A teammate's fight I knew about, could reach while it lasted, was free to join, and never did."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
import math
from constants import TICK, M, REACTION_S
from demolib import aimed_shots
from ._context import Ctx, spotters
KIND = 'sat_out'
SIDE = 'mistake'
KEEP_NEAR = True
TITLE = "Didn't join the fight"
WHY = ('A teammate was trading damage with an enemy for 1.5 s or more while you were free: alive, not fighting anyone, not '
       'flashed, and not being watched by another enemy. You knew where the fight was and could have established a sightline: '
       'you had the enemy in view during or shortly before it, they had you in view, the teammate beside you had them in view,'
       ' or you could hear the shots from within 40 m. You could have reached it while it was still going (path distance at '
       "run speed plus reaction time, within the fight's length) and no other enemy was covering it. You did nothing for the "
       'whole fight. Distance alone never triggers this.')
DO = ("When a teammate's fight starts within reach, move to it or swing it. Two guns on one enemy is the cheapest advantage "
      'in the game, and standing still while it happens is a free round for the other team.')
BASE = 32

HEARING_M = 40          # gunfire within this distance counts as heard
RUN_SPEED = 5.5         # m/s with a rifle out
PATH_FACTOR = 1.3       # a path is about this much longer than the straight line


def detect(c: Ctx) -> Iterator[Card | None]:
    D = c.D; me = c.me; by_tick = c.by_tick; names = c.names; coarse = c.coarse; rt = c.rt
    for R in c.rounds():
        rn = R.rn; team = R.team; side = R.side
        hurt_rn = c.hurt[c.hurt['total_rounds_played'] == rn]; fire_rn = R.rf
        for e in R.teammate_engagements():
            dur = (e['t1'] - e['t0']) / TICK
            if dur < 1.5: continue
            t0, t1, T, E = e['t0'], e['t1'], e['T'], e['E']
            # my own involvement: damage with anyone, shots at me or by me at someone else, or damage on this enemy, all mean I was not free
            mine_h = hurt_rn[(hurt_rn['tick'] >= t0 - TICK) & (hurt_rn['tick'] <= t1 + TICK) & ((hurt_rn['attacker_steamid'] == me) | (hurt_rn['user_steamid'] == me))]
            if len(mine_h): continue
            if aimed_shots(D, by_tick, coarse, rn, t0 - TICK, t1 + TICK, R.foes, {me}): continue          # shot at: in a fight
            if aimed_shots(D, by_tick, coarse, rn, t0 - TICK, t1 + TICK, {me}, R.foes - {E}): continue    # shooting at someone else
            engaged = hurt_rn[(hurt_rn['tick'] >= t0) & (hurt_rn['tick'] <= t1 + 4 * TICK) & (hurt_rn['attacker_steamid'] == me) & (hurt_rn['user_steamid'] == E)]
            if len(engaged): continue
            ok = True; min_dist = None; d_first = None; d_last = None; my_place = None; my_pos = None; e_pos = None; t_pos = None
            opportunity = None; other_threat = False; covering = False; near_others = False
            for ct in range(coarse(t0), t1 + 1, 16):
                g = by_tick.get(ct)
                if g is None: continue
                mr = g[g['steamid'] == me]; er = g[g['steamid'] == E]; tr = g[g['steamid'] == T]
                if not len(mr) or not len(er): continue
                mr = mr.iloc[0]; er = er.iloc[0]
                if not bool(mr['is_alive']) or (mr['flash_duration'] or 0) > 0.5: ok = False; break
                de = math.dist((mr.X, mr.Y), (er.X, er.Y)) * M
                dt = math.dist((mr.X, mr.Y), (tr.iloc[0].X, tr.iloc[0].Y)) * M if len(tr) and bool(tr.iloc[0]['is_alive']) else 99
                if d_first is None: d_first = de
                d_last = de
                if min_dist is None or de < min_dist: min_dist = de
                who_sees_me = spotters(mr); who_sees_E = spotters(er)
                if who_sees_me - {E}: other_threat = True; break          # another enemy had me in view: a threat of my own
                # other enemies covering the fight: alive, not E, within 25 m of E, or with the teammate in view
                others = g[(g['team_num'] != team) & (g['is_alive'] == True) & (g['steamid'] != E)]
                who_sees_T = spotters(tr.iloc[0]) if len(tr) else set()
                for o in others.itertuples():
                    do_e = math.dist((o.X, o.Y), (er.X, er.Y)) * M; do_me = math.dist((o.X, o.Y), (mr.X, mr.Y)) * M
                    if do_e <= 25 or str(o.steamid) in who_sees_T: covering = True
                    if do_e <= 40 or do_me <= 40: near_others = True
                # evidence that a sightline to E was available to me
                if me in who_sees_E: opportunity = opportunity or 'you had the enemy in view yourself'
                elif T in who_sees_E and dt <= 12: opportunity = opportunity or f'{names.get(T, T)}, {dt:.0f} m from you, had the enemy in view'
                elif E in who_sees_me: opportunity = opportunity or 'the enemy had you in view'
                my_place = mr['last_place_name']; my_pos = (mr.X, mr.Y); e_pos = (er.X, er.Y); t_pos = (tr.iloc[0].X, tr.iloc[0].Y) if len(tr) else None
            if ok and not other_threat and my_pos is not None and not opportunity:
                # awareness without a live sightline: I had the enemy in view within the previous 10 s, or I could hear the fight
                for ct in range(coarse(max(t0 - 10 * TICK, c.first_tick)), t0, 16):
                    g = by_tick.get(ct)
                    if g is None: continue
                    er = g[g['steamid'] == E]
                    if len(er) and me in spotters(er.iloc[0]): opportunity = f'you had the enemy in view {(t0 - ct) / TICK:.0f} s before the fight started'; break
                if not opportunity:
                    shots = c.fire[(c.fire['total_rounds_played'] == rn) & (c.fire['tick'] >= t0) & (c.fire['tick'] <= t1) & (c.fire['user_steamid'].isin([E, T]))]
                    for r in shots.itertuples():
                        g = by_tick.get(coarse(int(r.tick)))
                        if g is None: continue
                        mr = g[g['steamid'] == me]; sr = g[g['steamid'] == str(r.user_steamid)]
                        if len(mr) and len(sr):
                            ds = math.dist((mr.iloc[0].X, mr.iloc[0].Y), (sr.iloc[0].X, sr.iloc[0].Y)) * M
                            if ds <= HEARING_M: opportunity = f'you could hear the fight: {names.get(str(r.user_steamid), "a player")} was shooting {ds:.0f} m from you'; break
            if not ok or other_threat or min_dist is None or my_pos is None or not opportunity: continue
            if min_dist > 45: continue
            if opportunity.startswith('you could hear') and dur < 3.0: continue    # sound alone needs time to hear, react and move
            # reachability: could I have got there while the fight was still on?
            reach_s = (min_dist * PATH_FACTOR) / RUN_SPEED + REACTION_S
            if reach_s > dur: continue
            # risk: another enemy covering the fight makes joining a bad trade; with sound-only evidence, any other enemy nearby rules it out
            if covering: continue
            if opportunity.startswith('you could hear') and near_others: continue
            # was I moving to help? closed 8 m or more toward the enemy over the fight
            if d_first is not None and d_last is not None and d_first - d_last >= 8: continue
            # did I fire at anything (a fight of my own that did no damage)?
            if len(fire_rn[(fire_rn['tick'] >= t0) & (fire_rn['tick'] <= t1)]): continue
            e_hp = None
            gE = by_tick.get(coarse(t1)); erE = gE[gE['steamid'] == E] if gE is not None else None
            if erE is not None and len(erE) and 'health' in erE.columns: e_hp = int(erE.iloc[0]['health'])
            facts = (f"Round {rn+1}, {side}, {rt(t0, rn)} s to {rt(t1, rn)} s. {names.get(T, T)} fought {names.get(E, E)} for {dur:.1f} s"
                     + (" and died" if e['T_died'] else (" and killed them" if e['E_died'] else " and both survived")) + f". You were at {my_place}, alive, not fighting anyone, not flashed, and no other enemy had you in view. Sightline evidence: {opportunity}. Reaching the fight would have taken about {reach_s:.1f} s of its {dur:.1f} s, and no other enemy was covering it. You did not fire, did no damage to {names.get(E, E)}, and did not move toward the fight.")
            yield dict(round=rn + 1, side=side, time=rt(t1, rn), z=None, place=my_place, pos=my_pos, killer=names.get(E, E), kpos=e_pos, kplace=None, weapon=None, my_weapon=None, dist=round(min_dist, 1),
                       near=(math.dist(my_pos, t_pos) * M, names.get(T, T), t_pos, '') if t_pos else None, path=c.my_path(t1),
                       killer_path=[], mate_path=[], mates_alive=None, nades_thrown=[], won=R.won, facts=facts,
                       mate_died=e['T_died'], enemy_hp_after=e_hp, min_dist=min_dist, dur=dur, opportunity=opportunity, extra_pos=t_pos, extra_label=f"{names.get(T, T)} fighting")


def adjust(m: Card, add: Add) -> None:
    add(8 if m.get('mate_died') else 0, 'your teammate died in that fight')
    add(5 if (m.get('enemy_hp_after') or 0) >= 60 else 0, 'the enemy walked away barely hurt')
    add(4 if 'yourself' in (m.get('opportunity') or '') else 0, 'you had the enemy in view yourself')
    add(min(6, int((m.get('dur') or 0))), f"the fight lasted {m.get('dur', 0):.1f} s")
