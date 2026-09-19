"""Started a defuse with an enemy alive and stopped it: a fake that forces them to peek."""
from __future__ import annotations
from typing import Iterator
import pandas as pd
from report_types import Add, Card
from constants import TICK
from ._context import Ctx
KIND = 'defuse_fake'
SIDE = 'play'
TITLE = 'Defuse fake'
WHY = ('You started a defuse with an enemy alive and stopped it without finishing: a fake that forces them to peek. Counts '
       'more when an enemy died to your team within 3 s of it.')
DO = 'Keep faking when the enemy is holding the bomb from a spot a teammate can punish.'
BASE = 30


def detect(c: Ctx) -> Iterator[Card | None]:
    db = c.D.get('defuse_begin'); dfd = c.D.get('defused'); me = c.me
    if db is None or not len(db): return
    for R in c.rounds():
        rn = R.rn; rd = R.rd; rdm = R.my_deaths
        def finished(t: int) -> bool: return bool(dfd is not None and len(dfd) and ((dfd['total_rounds_played'] == rn) & (dfd['tick'] >= t) & (dfd['tick'] <= t + 11 * TICK)).any())
        def punished(t: int) -> pd.DataFrame: return rd[(rd['tick'] > t) & (rd['tick'] <= t + 3 * TICK) & (rd['user_team_num'] != R.team) & (rd['attacker_team_num'] == R.team)]
        # a fake that was punished: I stopped the defuse, stayed alive, and an enemy died to my team within 3 s of its start
        for r in db[(db['total_rounds_played'] == rn) & (db['user_steamid'] == me)].itertuples():
            t = int(r.tick)
            if finished(t): continue
            alive_me = (not len(rdm)) or int(rdm.iloc[0]['tick']) > t + 3 * TICK
            kd = punished(t)
            if alive_me and len(kd):
                mr = c.row(t, me)
                if mr is not None: yield c.card(rn, R.side, t, str(mr['last_place_name']), (float(mr.X), float(mr.Y)), facts=f"Round {rn+1}, CT, {c.rt(t, rn)} s. You started the defuse, stopped, and {kd.iloc[0]['user_name']} died to {kd.iloc[0]['attacker_name']} {(int(kd.iloc[0]['tick']) - t) / TICK:.1f} s later.", extra_pos=(float(kd.iloc[0]['user_X']), float(kd.iloc[0]['user_Y'])) if kd.iloc[0]['user_X'] == kd.iloc[0]['user_X'] else None, extra_label=f"{kd.iloc[0]['user_name']} died")
        # every stopped defuse with an enemy alive, punished or not (a defuse that finished, or that I died in, is committed_defuse)
        for r in db[db['total_rounds_played'] == rn].itertuples():
            t = int(r.tick)
            if str(r.user_steamid) != me: continue
            ma, fo = c.alive_counts(t - 1, R.team); mr = c.row(t, me)
            if mr is None or not bool(mr['is_alive']) or not fo: continue
            died_soon = bool(len(rdm) and t < int(rdm.iloc[0]['tick']) <= t + 11 * TICK)
            if finished(t) or died_soon: continue
            kd = punished(t)
            yield c.card(rn, R.side, t, str(mr['last_place_name']), (float(mr.X), float(mr.Y)), facts=f"Round {rn+1}, CT, {c.rt(t, rn)} s. Started a defuse with {fo} enemies alive and stopped it." + (f" {kd.iloc[0]['user_name']} died to {kd.iloc[0]['attacker_name']} {(int(kd.iloc[0]['tick']) - t) / TICK:.1f} s later." if len(kd) else " Nobody was punished for peeking it."), punished=bool(len(kd)))


def adjust(m: Card, add: Add) -> None:
    if m.get('punished'): add(10, 'an enemy died peeking it')
