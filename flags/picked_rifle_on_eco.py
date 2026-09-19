"""Picked up a rifle on a round I started with under 1500 of equipment."""
from __future__ import annotations
from typing import Iterator
from report_types import Card
from ._weapons import RIFLES
from ._context import Ctx
KIND = 'picked_rifle_on_eco'
SIDE = 'play'
TITLE = 'Picked up a rifle on eco'
WHY = 'You picked up a rifle on a round you started with under 1500 of equipment.'
DO = 'Keep collecting the weapons on the floor.'
BASE = 10


def detect(c: Ctx) -> Iterator[Card | None]:
    pk = c.D.get('pickups'); me = c.me
    if pk is None or not len(pk): return
    for R in c.rounds():
        r0 = c.row(R.ft, me)
        my_eq0 = int(r0['current_equip_value']) if r0 is not None and r0['current_equip_value'] == r0['current_equip_value'] else 0
        if my_eq0 >= 1500: continue
        mine_pk = pk[(pk['total_rounds_played'] == R.rn) & (pk['user_steamid'] == me) & (pk['tick'] > R.ft) & (pk['item'].astype(str).str.lower().str.contains('|'.join(RIFLES), na=False))]
        for r in mine_pk.head(1).itertuples():
            mr = c.row(int(r.tick), me)
            if mr is not None: yield c.card(R.rn, R.side, int(r.tick), str(mr['last_place_name']), (float(mr.X), float(mr.Y)), facts=f"Round {R.rn+1}, {R.side}, {c.rt(int(r.tick), R.rn)} s. Picked up a {r.item} on a round you started with ${my_eq0}.")
