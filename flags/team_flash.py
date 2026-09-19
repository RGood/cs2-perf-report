"""My flashbang blinded a teammate for a second or more; far worse when an enemy killed them while blind."""
from __future__ import annotations
from typing import Iterator
from typing import Any
from report_types import Add, Card, XY
from constants import TICK
from ._shared import team_at
from ._context import Ctx
KIND = 'team_flash'
SIDE = 'mistake'
TITLE = 'Flashed a teammate'
WHY = ('Your flashbang blinded a teammate for a second or more. A blind teammate cannot hold their angle, trade, or see the '
       'push, and the blind lasts longer than the pop suggests. It counts far more when an enemy killed them while they were '
       'still blind.')
DO = ("Call the flash, throw it from behind the teammate's line or higher, and keep them out of the pop: a flash that pops "
      'behind cover for your side and in the open for theirs.')
BASE = 14


def detect(c: Ctx) -> Iterator[Card | None]:
    bl = c.blind; deaths = c.deaths; me = c.me; rt = c.rt
    myb = bl[(bl['attacker_steamid'] == me) & (bl['user_steamid'] != me)] if len(bl) else bl
    for tick_, grp in myb.groupby('tick'):                      # one detonation = one flash
        rn = int(grp.iloc[0]['total_rounds_played']); t = int(tick_)
        if rn not in c.fz: continue
        team = team_at(c, rn, me)
        if team not in (2, 3): continue
        side = 'CT' if team == 3 else 'T'
        mates = grp[(grp['user_team_num'] == team) & (grp['blind_duration'] >= 1.0)]
        if not len(mates): continue
        foes = grp[(grp['user_team_num'] != team) & (grp['blind_duration'] >= 1.0)]
        k = c.on_grid(t); g = c.by_tick.get(k) if k is not None else None; mr = g[g['steamid'] == me] if g is not None else None
        my_pos = (float(mr.iloc[0].X), float(mr.iloc[0].Y)) if mr is not None and len(mr) else None
        my_place = str(mr.iloc[0]['last_place_name']) if mr is not None and len(mr) else None
        thr = c.nades[(c.nades['weapon'].str.contains('flashbang', na=False)) & (c.nades['tick'] <= t) & (c.nades['tick'] >= t - 6 * TICK)]
        thrown = [('flashbang', (float(thr.iloc[-1]['user_X']), float(thr.iloc[-1]['user_Y'])))] if len(thr) else []
        if my_pos is None and thrown: my_pos = thrown[0][1]
        if my_pos is None: continue
        parts = []; died: list[dict[str, Any]] = []; extra: tuple[XY, str] | None = None; max_dur = 0.0
        for x in mates.itertuples():
            dur = float(x.blind_duration); max_dur = max(max_dur, dur)
            parts.append(f"{x.user_name} for {dur:.1f} s")
            kd = deaths[(deaths['total_rounds_played'] == rn) & (deaths['user_steamid'] == str(x.user_steamid)) & (deaths['tick'] >= t) & (deaths['tick'] <= t + dur * TICK)]
            kd = kd[kd['attacker_team_num'] != team] if len(kd) else kd
            if len(kd):
                k_ = kd.iloc[0]; after = (int(k_['tick']) - t) / TICK
                died.append(dict(name=str(x.user_name), by=str(k_['attacker_name']), after=after, left=dur - after, pos=(float(k_['user_X']), float(k_['user_Y'])), place=str(k_['user_last_place_name'])))
            elif extra is None and g is not None:
                tr = g[g['steamid'] == str(x.user_steamid)]
                if len(tr): extra = ((float(tr.iloc[0].X), float(tr.iloc[0].Y)), f"{x.user_name} blinded")
        facts = f"Round {rn+1}, {side}, {rt(t, rn)} s. Your flashbang from {my_place or 'unknown'} blinded " + ', '.join(parts) + '.'
        if died:
            d0 = died[0]
            facts += ' ' + ' '.join(f"{d['name']} was killed by {d['by']} at {d['place']} {d['after']:.1f} s later, with {max(0, d['left']):.1f} s of blind still to go." for d in died)
            extra = (d0['pos'], f"{d0['name']} died blind")
        if len(foes): facts += f" It also blinded {', '.join(f'{x.user_name} ({float(x.blind_duration):.1f} s)' for x in foes.itertuples())}."
        else: facts += " It blinded no enemy for a second or more."
        yield dict(round=rn + 1, side=side, time=rt(t, rn), z=None, place=my_place, pos=my_pos, killer=None, kpos=None, kplace=None, weapon=None, my_weapon=None, dist=0, near=None,
                   path=[], mates_alive=None, nades_thrown=thrown, won=c.D['winner'].get(rn) == side, facts=facts, mate_died_blind=bool(died),
                   n_mates=len(mates), max_dur=max_dur, n_foes=len(foes), blind_left=(max(0, died[0]['left']) if died else 0),
                   extra_pos=extra[0] if extra else None, extra_label=extra[1] if extra else None)


def adjust(m: Card, add: Add) -> None:
    add(4 * max(0, (m.get('n_mates') or 1) - 1), f"{m.get('n_mates')} teammates blinded")
    add(min(8, int((m.get('max_dur') or 0) * 2)), f"blinded for up to {m.get('max_dur', 0):.1f} s")
    add(-4 if (m.get('n_foes') or 0) else 0, f"it also blinded {m.get('n_foes')} {'enemy' if m.get('n_foes') == 1 else 'enemies'}")
    if m.get('mate_died_blind'):
        add(26, 'a teammate died while still blind from it')
        add(6 if (m.get('blind_left') or 0) >= 1.0 else 0, f"they still had {m.get('blind_left', 0):.1f} s of blind left when they died")
