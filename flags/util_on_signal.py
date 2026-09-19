"""A grenade thrown on information that then did something measurable: blinded, damaged, or held back approaching enemies."""
from __future__ import annotations
from typing import Iterator
from report_types import Add, Card
import math
from constants import TICK, M, NADE_RADIUS
from demolib import nade_flight
from ._context import Ctx
KIND = 'util_on_signal'
SIDE = 'play'
TITLE = 'Utility on a signal'
WHY = ('A grenade thrown on information (an enemy your team had spotted near where it landed, enemy gunfire nearby, or an '
       'enemy close enough to hear) that then did something measurable: a flash blinded an enemy for a second or more, an HE '
       'or molotov did damage, or a smoke or molotov held back enemies who were approaching it and never came through while it'
       ' was up.')
DO = ('Keep pairing the signal with the throw. Utility thrown on information and landing where the enemy actually is costs '
      'them time, health, or vision; the same grenade on the clock costs you the grenade.')
BASE = 26


def detect(c: Ctx) -> Iterator[Card | None]:
    D = c.D; me = c.me; by_tick = c.by_tick; coarse = c.coarse; blind = c.blind; hurt = c.hurt; rt = c.rt
    for R in c.rounds():
        rn = R.rn; team = R.team; rd = R.all_deaths; enemies = R.not_my_team; death_tick = R.death_tick
        gun_rn = c.fire[c.fire['total_rounds_played'] == rn]
        for r in c.nades[(c.nades['total_rounds_played'] == rn) & (c.nades['weapon'].str.contains('smoke|molotov|incgrenade|flashbang|hegrenade', na=False))].itertuples():
            t0 = int(r.tick)
            if death_tick is not None and t0 > death_tick: continue
            w = r.weapon.replace('weapon_', ''); fl = nade_flight(D, me, t0, w)
            if fl is None: continue
            kind, _path, land, _thr, det = fl
            mypos = (r.user_X, r.user_Y)
            # ---- the signal, in the 3 s before the throw: one per enemy, the first seen
            sig: dict[str, str] = {}
            for ct in range(coarse(t0 - 3 * TICK) or t0, t0 + 1, 8):
                gg = by_tick.get(ct)
                if gg is None: continue
                for f in gg[(gg['team_num'] != team) & (gg['is_alive'] == True)].itertuples():
                    dl = math.dist((f.X, f.Y), land) * M; dm = math.dist((f.X, f.Y), mypos) * M
                    if bool(f.spotted) and dl < 40: sig.setdefault(str(f.name), f"{f.name} spotted by your team {dl:.0f} m from where it landed")
                    elif dm < 15: sig.setdefault(str(f.name), f"{f.name} within {dm:.0f} m of you")
            for g_ in gun_rn[(gun_rn['tick'] >= t0 - 3 * TICK) & (gun_rn['tick'] <= t0)].itertuples():
                if str(g_.user_steamid) in enemies:
                    dg = math.dist((g_.user_X, g_.user_Y), mypos) * M
                    if dg < 30: sig.setdefault(str(g_.user_name), f"{g_.user_name} firing {dg:.0f} m from you")
            if not sig: continue
            signals = list(sig.values())[:3]
            # ---- the effect
            eff = []; n_bl = 0; killed_blind = False; dmg = 0; held: list[str] = []; crossed: list[str] = []; mates_bl = 0
            fxrow = c.fx[(c.fx['kind'] == kind) & ((c.fx['tick'] - det).abs() <= 2)]
            end = int(fxrow.iloc[0]['end']) if len(fxrow) else det + 7 * TICK
            if kind == 'flashbang':
                b = blind[(blind['attacker_steamid'] == me) & ((blind['tick'] - det).abs() <= 2)]
                for x in b.itertuples():
                    dur = float(x.blind_duration)
                    if str(x.user_steamid) in enemies:
                        if dur >= 1.0:
                            n_bl += 1; eff.append(f"blinded {x.user_name} for {dur:.1f} s")
                            kd = rd[(rd['user_steamid'] == x.user_steamid) & (rd['tick'] >= det) & (rd['tick'] <= det + dur * TICK) & (rd['attacker_team_num'] == team)]
                            if len(kd): killed_blind = True; eff.append(f"{x.user_name} was killed while blind")
                    elif str(x.user_steamid) != me and dur >= 1.0:
                        mates_bl += 1; eff.append(f"but blinded teammate {x.user_name} for {dur:.1f} s")
            else:
                wname = {'hegrenade': 'hegrenade', 'molotov': 'inferno'}.get(kind)
                if wname:
                    hh = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me) & (hurt['weapon'] == wname) & (hurt['tick'] >= det - 2) & (hurt['tick'] <= end + 2) & (hurt['user_steamid'].isin(enemies))]
                    dmg = int(hh['dmg_health'].clip(upper=100).sum())
                    if dmg: eff.append(f"{dmg} damage to {', '.join(sorted(set(hh['user_name'])))}")
                if kind in ('smokegrenade', 'molotov'):
                    # held: an enemy who was approaching it (closed 2 m or more in the 3 s before, within 20 m) and never came through while it was up
                    radius = NADE_RADIUS[kind] * M + 0.6
                    before = by_tick.get(coarse(det - 3 * TICK)); at = by_tick.get(coarse(det))
                    if before is not None and at is not None:
                        for f in at[(at['team_num'] != team) & (at['is_alive'] == True)].itertuples():
                            d_at = math.dist((f.X, f.Y), land) * M
                            fb = before[before['steamid'] == f.steamid]
                            d_before = math.dist((fb.iloc[0].X, fb.iloc[0].Y), land) * M if len(fb) else d_at
                            if d_at > 20 or d_before - d_at < 2: continue        # not approaching it
                            inside = False
                            for ct in range(coarse(det), end + 1, 16):
                                gg = by_tick.get(ct)
                                if gg is None: continue
                                fr = gg[gg['steamid'] == f.steamid]
                                if not len(fr) or not bool(fr.iloc[0]['is_alive']): break
                                if math.dist((fr.iloc[0].X, fr.iloc[0].Y), land) * M < radius: inside = True; break
                            (crossed if inside else held).append(str(f.name))
                    if held: eff.append(f"held {', '.join(held)} ({'was' if len(held) == 1 else 'were'} approaching it and never came through while it was up)")
                    if crossed: eff.append(f"{', '.join(crossed)} pushed through it anyway")
            if not (n_bl > 0 or dmg > 0 or len(held) > 0): continue
            lname = {'smokegrenade': 'Smoke', 'flashbang': 'Flash', 'hegrenade': 'HE', 'molotov': 'Molotov'}[kind]
            yield R.play(t0, mypos, None, None,
                         f"Round {rn+1}, {R.side}, {rt(t0, rn)} s. {lname} from {r.user_last_place_name}, landed {math.dist(mypos, land) * M:.0f} m away. Signal: {'; '.join(signals)}. Effect: {'; '.join(eff)}.",
                         place=r.user_last_place_name, nade=kind, signal=signals, n_blinded=n_bl, killed_blind=killed_blind, dmg=dmg, n_held=len(held), n_crossed=len(crossed), n_mates_blinded=mates_bl, extra_pos=land, extra_label=f"{lname.lower()} landed")


def adjust(m: Card, add: Add) -> None:
    add(min(18, 6 * (m.get('n_blinded') or 0)), f"{m.get('n_blinded')} enemies blinded for a second or more")
    add(8 if m.get('killed_blind') else 0, 'an enemy died while blind')
    add(min(12, int((m.get('dmg') or 0) // 10)), f"{m.get('dmg')} damage from it")
    add(min(16, 8 * (m.get('n_held') or 0)), f"held {m.get('n_held')} approaching enemies")
    add(-8 * (m.get('n_mates_blinded') or 0), f"blinded {m.get('n_mates_blinded')} teammates")
    add(-4 * (m.get('n_crossed') or 0), f"{m.get('n_crossed')} enemies pushed through it anyway")
