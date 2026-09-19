"""CT holding alone against a hit: lasted 8 s or more after contact and did damage or used utility in that time."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
import math
from constants import TICK, M
from ._context import Ctx
KIND = 'good_anchor'
SIDE = 'play'
KEEP_NEAR = True
TITLE = 'Anchor held with value'
WHY = ('Holding a site alone against a hit, you lasted 8 s or more after contact and did damage or used utility in that time. '
       "That is the anchor's job done.")
DO = ('Keep this order under pressure: call, delay grenade, damage, fall back. The round is decided by what the retake '
      'inherits.')
BASE = 40


def detect(c: Ctx) -> Iterator[Card | None]:
    me = c.me; rt = c.rt; by_tick = c.by_tick
    for R in c.rounds():
        if R.side != 'CT': continue
        rn = R.rn; team = R.team; h = R.hits_on_enemies
        for d in R.all_my_deaths.itertuples():
            t = int(d.tick)
            ma, fo, md, mp = R.state(t - 1)
            if not (ma is not None and ma >= 2 and md and md[0][0] > 15): continue
            # contact: the first sample in the last 15 s with an enemy within 25 m
            contact = None; foes_peak = 0
            for ct in range(t - 15 * TICK, t, 8):
                gg = by_tick.get(ct)
                if gg is None: continue
                mr = gg[gg['steamid'] == me]
                if not len(mr): continue
                n = sum(1 for f in gg[(gg['team_num'] != team) & (gg['is_alive'] == True)].itertuples() if math.dist((mr.iloc[0].X, mr.iloc[0].Y), (f.X, f.Y)) * M < 25)
                if n and contact is None: contact = ct
                foes_peak = max(foes_peak, n)
            after = (t - contact) / TICK if contact else 0
            dmg_after = int(h[h['tick'] >= (contact or t)]['dmg_health'].clip(upper=100).sum())
            nades_after = int(((c.nades['total_rounds_played'] == rn) & (c.nades['tick'] >= (contact or t)) & (c.nades['tick'] <= t)).sum())
            if contact is not None and after >= 8 and (dmg_after >= 50 or nades_after):
                yield R.play(t, (d.user_X, d.user_Y), d.attacker_name, (d.attacker_X, d.attacker_Y), f"Round {rn+1}, {R.side}, {rt(t, rn)} s at {d.user_last_place_name}. Contact at {rt(contact, rn)} s with up to {foes_peak} attackers within 25 m; you lasted {after:.0f} s, did {dmg_after} damage and threw {nades_after} grenades after contact. Nearest teammate {md[0][1]} was {md[0][0]:.0f} m away.",
                             place=d.user_last_place_name, victim_sid=d.attacker_steamid, dmg_after=dmg_after, nades_after=nades_after)


def adjust(m: Card, add: Add) -> None:
    add(min(10, int((m.get('dmg_after') or 0) // 25)), f"{m.get('dmg_after')} damage after contact")
    add(5 if m.get('nades_after') else 0, 'utility thrown after contact')
