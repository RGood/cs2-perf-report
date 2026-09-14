"""Impact report: the positive counterpart of mistake_report.py. Flags decisions and plays that produced good outcomes,
scores each 0-100, draws them on the radar, and writes a self-contained HTML.

Usage:
    python impact_report.py <demo.dem> [--player 76561198063294402] [--out report.html]
"""
import sys, os, math, base64, argparse, collections as C
import pandas as pd
from PIL import ImageDraw
from mistake_report import parse, make_map, _font, b64, nade_list, TICK, M, teammate_fights, REACTION_S, PEEK_S

RULES = {
    'clutch': ("Clutch won",
        "You were the last player alive and won the round. Every decision after your last teammate died was correct enough to beat the numbers.",
        "Keep playing clutches slowly: isolate one fight at a time, use the clock, and let the bomb or the defuse force them to come to you."),
    'opening_kill': ("Opening kill",
        "First kill of the round. The enemy started the round a player down before committing, which is the single most valuable kill in the round.",
        "Keep taking the opener from the same kind of spot: a held angle or a peek with utility and a teammate close enough to trade."),
    'retake_kill': ("Retake kill",
        "A kill after the bomb was planted, in a round your team then won. Retakes are lost by going in alone and won by exactly this.",
        "Keep waiting for the group, keep the utility for the retake, and keep taking the first fight from a position the plant forces them to defend."),
    'multi_kill': ("Multi-kill round",
        "Two or more kills in one round. You changed the numbers, not just the scoreline.",
        "Note where you were and what you had: multi-kills come from positions the enemy has to cross in sequence."),
    'flash_kill': ("Kill off your own flash",
        "You blinded the enemy and then killed them while blind. The flash removed the duel and left only the kill.",
        "Keep pop-flashing before the peek. This is the model for every entry: the grenade goes first, then the swing."),
    'flash_assist': ("Flash assist",
        "Your flash blinded an enemy that a teammate then killed. Utility thrown for someone else is the highest-leverage grenade you have.",
        "Keep throwing flashes for the teammate who is peeking, and call it so they swing on it."),
    'trade_kill': ("Trade kill",
        "A teammate died and you killed their killer within 5 seconds. It counts for more when the teammate held the killer's attention: when you first shot at the killer they were still aimed well away from you (30° or more), so you had a free shot. It counts for less when they were already aimed within 15° of you.",
        "Keep positioning inside trade range of the teammate who is about to take the fight, and come in from off their killer's aim."),
    'good_anchor': ("Anchor held with value",
        "Holding a site alone against a hit, you lasted 8 s or more after contact and did damage or used utility in that time. That is the anchor's job done.",
        "Keep this order under pressure: call, delay grenade, damage, fall back. The round is decided by what the retake inherits."),
    'reposition_kill': ("Repositioned after a kill",
        "You got a kill, moved at least 8 metres, and got another. The enemy re-peeked the first spot and you were not there.",
        "Keep moving one position after every kill. The second kill is the payoff for the move."),
    'util_damage': ("Utility damage",
        "An HE or molotov did 30 or more damage this round. Damage from utility is free: no duel, no exposure.",
        "Keep the same throws for the same stacks and chokes. Grenade damage before the fight makes the fight easier."),
    'util_on_signal': ("Utility on a signal",
        "A grenade thrown on information (an enemy your team had spotted near where it landed, enemy gunfire nearby, or an enemy close enough to hear) that then did something measurable: a flash blinded an enemy for a second or more, an HE or molotov did damage, or a smoke or molotov held back enemies who were approaching it and never came through while it was up.",
        "Keep pairing the signal with the throw. Utility thrown on information and landing where the enemy actually is costs them time, health, or vision; the same grenade on the clock costs you the grenade."),
    'survived_damage': ("High damage, survived",
        "100 or more damage in a round you also survived. Damage without a death is the best possible round for the economy and the numbers.",
        "Keep taking fights from positions where losing the first exchange does not mean dying."),
    'saved_rifle': ("Saved the rifle",
        "Your team lost the round and you kept a rifle-value buy alive. Next round starts with a full kit instead of a force.",
        "Keep recognising the lost round early. One saved rifle changes the next round's buy for the whole team."),
    'fight_support': ("Supported the fight",
        "A teammate was fighting an enemy and you put damage on that enemy before the fight was decided. Two guns on one target is how duels stop being coin flips.",
        "Keep joining your teammate's fight from the first shot. Even a few bullets of damage change who wins it."),
    **__import__('positioning').RULES_POS,
    **__import__('flags_extra').RULES_POS,
    'died_tradeable': ("Death traded",
        "You died, and a teammate killed your killer within 5 seconds. It is a real trade when your fight held the killer's attention: when the trader first shot at the killer, the killer was still aimed well away from the trader (30° or more), so the trader had a free shot. It counts for less when the killer was already aimed within 15° of the trader.",
        "Keep dying next to someone, and make the fight last: the longer the killer's aim stays on you, the easier the trade."),
}

BASE_IMPACT = {'clutch': 60, 'opening_kill': 50, 'retake_kill': 50, 'multi_kill': 45, 'flash_kill': 40, 'trade_kill': 42, 'good_anchor': 40,
               'reposition_kill': 20, 'fight_support': 35, 'flash_assist': 32, **__import__('positioning').BASE_POS, **__import__('flags_extra').BASE_POS, 'util_damage': 30, 'survived_damage': 25, 'util_on_signal': 20, 'saved_rifle': 25, 'died_tradeable': 25}


def impact(m):
    k = m['kind']; score = BASE_IMPACT.get(k, 35); br = [f"base {score} for this play type"]
    def add(v, why):
        nonlocal score
        if v:
            score += v; br.append(f"{v:+d} {why}")
    rm = int(round(min(10, max(3, 0.25 * BASE_IMPACT.get(k, 35)))))
    if m.get('won') is True: add(rm, 'round won')
    elif m.get('won') is False: add(-rm, 'round still lost')
    if k == 'clutch': add(12 * (m.get('vs', 1) - 1), f"1v{m.get('vs')}")
    if k == 'multi_kill': add(10 * (m.get('kills', 2) - 2), f"{m.get('kills')} kills")
    if k in ('opening_kill', 'flash_kill', 'trade_kill', 'retake_kill', 'reposition_kill') and m.get('headshot'): add(3, 'headshot')
    if k == 'opening_kill' and (m.get('time') or 99) < 20: add(5, 'before 20 s')
    if k == 'opening_kill' and m.get('supported'): add(5, 'teammate within 15 m')
    if k == 'good_anchor':
        add(min(10, int((m.get('dmg_after') or 0) // 25)), f"{m.get('dmg_after')} damage after contact")
        add(5 if m.get('nades_after') else 0, 'utility thrown after contact')
    if k == 'util_damage': add(min(10, int((m.get('dmg') or 0) // 20)), f"{m.get('dmg')} grenade damage")
    if k in ('died_tradeable', 'trade_kill'):
        if m.get('att_held'): add(10 if k == 'died_tradeable' else 8, f"the killer was aimed {m.get('turn_deg'):.0f}° away from the trader when the trader first shot at them")
        elif m.get('att_prepared'): add(-10 if k == 'died_tradeable' else -8, f"the killer was already aimed within {m.get('turn_deg'):.0f}° of the trader when the trader first shot at them")
    if k == 'util_on_signal':
        add(min(18, 6 * (m.get('n_blinded') or 0)), f"{m.get('n_blinded')} enemies blinded for a second or more")
        add(8 if m.get('killed_blind') else 0, 'an enemy died while blind')
        add(min(12, int((m.get('dmg') or 0) // 10)), f"{m.get('dmg')} damage from it")
        add(min(16, 8 * (m.get('n_held') or 0)), f"held {m.get('n_held')} approaching enemies")
        add(-8 * (m.get('n_mates_blinded') or 0), f"blinded {m.get('n_mates_blinded')} teammates")
        add(-4 * (m.get('n_crossed') or 0), f"{m.get('n_crossed')} enemies pushed through it anyway")
    if k == 'survived_damage': add(min(10, int((m.get('dmg') or 0) // 40)), f"{m.get('dmg')} damage")
    if k == 'flash_kill': add(min(6, int(m.get('kills', 1) - 1) * 6), 'more than one blind kill')
    if k == 'held_angle' and m.get('headshot'): add(3, 'headshot')
    if k == 'rotated_on_info': add(min(10, int((m.get('dmg') or 0) // 25)), f"{m.get('dmg')} damage after arriving")
    if k == 'fight_support':
        add(min(10, int((m.get('dmg') or 0) // 20)), f"{m.get('dmg')} damage during the fight")
        add(8 if m.get('enemy_died') else 0, 'the enemy died in that fight')
        add(5 if m.get('mate_survived') else 0, 'your teammate survived it')
    if m.get('mates_alive') is not None and m.get('mates_alive') <= 1 and k in ('opening_kill', 'trade_kill', 'retake_kill', 'multi_kill', 'reposition_kill'): add(5, 'while outnumbered')
    return max(0, min(100, score)), br


def imp_rgb(score):
    a = (60, 64, 78); b = (60, 190, 90); f = max(0.0, min(1.0, score / 100.0))
    return tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3))

def imp_css(score):
    r, g, b = imp_rgb(score); return f"rgb({r},{g},{b})"


def detect(D):
    me = D['me']; fz = D['fz']; deaths = D['deaths']; snap = D['snap']; hurt = D['hurt']; blind = D['blind']; plant = D['plant']
    from mistake_report import by_tick_of
    by_tick = by_tick_of(D)
    first_tick = int(min(by_tick)); coarse_ticks = sorted(by_tick)
    def coarse(t):
        c = t - ((t - first_tick) % 8)
        return c if c in by_tick else max([x for x in coarse_ticks if x <= t], default=None)
    def wrap(a): return abs(((a + 180) % 360) - 180)
    def spot(v):
        try: return set(str(x) for x in v)
        except TypeError: return set()
    def attention(killer, trader, t_death, t_trade, kname, tname, victim_word):
        """Did the victim hold the killer's attention for the trade? The measure is the angle between the killer's view direction and the
        trader at the tick the trader first got sight of the killer (the killer's approximate_spotted_by lists the trader). A large angle
        means the trader had a free shot at a killer still looking elsewhere; a small one means the killer was already set on them."""
        killer, trader = str(killer), str(trader)
        def off(tick):
            g = by_tick.get(tick) if tick in by_tick else by_tick.get(coarse(tick))
            if g is None: return None
            kr = g[g['steamid'] == killer]; tr = g[g['steamid'] == trader]
            if not len(kr) or not len(tr) or not (kr.iloc[0]['yaw'] == kr.iloc[0]['yaw']): return None
            b = math.degrees(math.atan2(tr.iloc[0].Y - kr.iloc[0].Y, tr.iloc[0].X - kr.iloc[0].X))
            return wrap(b - float(kr.iloc[0]['yaw']))
        # the moment that counts: the trader's first shot aimed within 15 degrees of the killer
        t_spot = None; basis = 'first shot at them'
        gf = D['gunfire']; shots = gf[(gf['user_steamid'] == trader) & (gf['tick'] >= t_death - 3 * TICK) & (gf['tick'] <= t_trade)].sort_values('tick')
        for s_ in shots.itertuples():
            if not (s_.user_yaw == s_.user_yaw): continue
            g = by_tick.get(coarse(int(s_.tick)))
            if g is None: continue
            kr = g[g['steamid'] == killer]
            if not len(kr): continue
            b = math.degrees(math.atan2(kr.iloc[0].Y - s_.user_Y, kr.iloc[0].X - s_.user_X))
            if wrap(b - float(s_.user_yaw)) < 15: t_spot = int(s_.tick); break
        off_end = off(t_trade)
        off_spot = off(t_spot) if t_spot is not None else None
        key = off_spot if off_spot is not None else off_end
        if key is None: return {}, ''
        held = key >= 30; prepared = key < 15
        react = (t_trade - t_spot) / TICK if t_spot is not None else None
        when = '' if t_spot is None else (f"{(t_spot - t_death) / TICK:.1f} s after {victim_word} died" if t_spot >= t_death else f"{(t_death - t_spot) / TICK:.1f} s before {victim_word} died")
        end_txt = f" ({off_end:.0f}° off at the trade shot)" if off_end is not None else ''
        if t_spot is None: txt = f"No shot by {tname} aimed at {kname} was found before the trade; at the trade shot {kname} was aimed {key:.0f}° away from {tname}."
        else: txt = f"When {tname} first shot at {kname} ({when}), {kname} was aimed {off_spot:.0f}° away from {tname}; the trade came {react:.1f} s later{end_txt}."
        return dict(turn_deg=key, view_off_end=off_end, att_react=react, att_held=held, att_prepared=prepared, att_spotted_before=(t_spot is not None and t_spot < t_death)), txt
    mine = snap[snap['steamid'] == me].set_index('tick')
    rt = lambda tick, rn: round((tick - fz[rn]) / TICK, 1) if rn in fz else None
    def path_of(sid, t):
        q = snap[(snap['steamid'] == str(sid)) & (snap['tick'] >= t - 12 * TICK) & (snap['tick'] <= t) & (snap['is_alive'] == True)].sort_values('tick')
        return [(r.X, r.Y) for r in q.itertuples()]
    def state(t, team):
        g = by_tick.get(coarse(t))
        if g is None: return None, None, [], None
        mr = g[g['steamid'] == me]
        mates = g[(g['team_num'] == team) & (g['steamid'] != me) & (g['is_alive'] == True)]
        foes = g[(g['team_num'] != team) & (g['is_alive'] == True)]
        mp = (mr.iloc[0].X, mr.iloc[0].Y) if len(mr) else None
        md = sorted([(math.dist(mp, (x.X, x.Y)) * M, x.name, (x.X, x.Y), x.last_place_name, x.steamid) for x in mates.itertuples()]) if mp else []
        return len(mates), len(foes), md, mp
    out = []
    rend = D.get('round_end', {})
    def end_of(rn): return int(rend.get(rn, fz.get(rn + 1, int(mine.index.max()))))
    my_kills = deaths[deaths['attacker_steamid'] == me]
    my_deaths = deaths[deaths['user_steamid'] == me]

    for rn in sorted(fz):
        ft = fz[rn]; g = by_tick.get(ft)
        if g is None or not (g['steamid'] == me).any(): continue
        me0 = g[g['steamid'] == me].iloc[0]; team = int(me0['team_num']); side = 'CT' if team == 3 else 'T'
        if team not in (2, 3): continue
        won = D['winner'].get(rn) == side
        rd = deaths[deaths['total_rounds_played'] == rn].sort_values('tick')
        rk = rd[rd['attacker_steamid'] == me]; rdm = rd[rd['user_steamid'] == me]
        died = len(rdm) > 0; death_tick = int(rdm.iloc[0]['tick']) if died else None
        h = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me)]
        enemies = set(g[g['team_num'] != team]['steamid'])
        h = h[h['user_steamid'].isin(enemies)]
        dmg = int(h['dmg_health'].clip(upper=100).sum())
        equip = int(me0['current_equip_value'])
        plant_t = int(plant[plant['total_rounds_played'] == rn]['tick'].min()) if (plant['total_rounds_played'] == rn).any() else None
        common = dict(round=rn + 1, side=side, won=won, equip=equip)

        def card(t, kind, pos, victim=None, vpos=None, facts='', **extra):
            if rt(t, rn) is None or rt(t, rn) < 0: return    # pre-round artefacts (pauses, knife rounds)
            ma, fo, md, mp = state(t, team)
            near = md[0] if md else None
            c = dict(common, kind=kind, time=rt(t, rn), pos=pos, place=extra.pop('place', None), victim=victim, vpos=vpos, z=extra.pop('z', None),
                     path=path_of(me, t), victim_path=path_of(extra.pop('victim_sid', None), t) if victim else [],
                     mate_path=path_of(near[4], t) if near else [], near=near, mates_alive=ma, foes_alive=fo,
                     nades_thrown=[(r.weapon.replace('weapon_', ''), (r.user_X, r.user_Y)) for r in D['nades'][(D['nades']['total_rounds_played'] == rn) & (D['nades']['tick'] <= t)].itertuples()],
                     facts=facts, **extra)
            out.append(c)

        # --- kills-based
        for i, k in enumerate(rk.itertuples()):
            t = int(k.tick); pos = (k.attacker_X, k.attacker_Y); vpos = (k.user_X, k.user_Y)
            base_facts = f"Round {rn+1}, {side}, {rt(t, rn)} s. Killed {k.user_name} ({k.weapon}{', headshot' if k.headshot else ''}) at {k.user_last_place_name} from {k.attacker_last_place_name}, {float(k.distance):.0f} m."
            ma, fo, md, mp = state(t, team)
            supported = bool(md and md[0][0] <= 15)
            # opening
            if rd.iloc[0]['tick'] == t:
                card(t, 'opening_kill', pos, k.user_name, vpos, base_facts + f" First kill of the round with {fo} enemies and {ma} teammates alive." + (f" Nearest teammate {md[0][1]} was {md[0][0]:.0f} m away." if md else ''), place=k.attacker_last_place_name, victim_sid=k.user_steamid, headshot=bool(k.headshot), supported=supported, z=float(k.attacker_Z))
            # flash-led kill
            b = blind[(blind['total_rounds_played'] == rn) & (blind['attacker_steamid'] == me) & (blind['user_steamid'] == k.user_steamid) & (blind['tick'] <= t) & (blind['tick'] >= t - 4 * TICK)]
            if len(b) and k.user_flash_duration and k.user_flash_duration > 0:
                card(t, 'flash_kill', pos, k.user_name, vpos, base_facts + f" Your flash blinded them {rt(t, rn) - rt(int(b.iloc[-1]['tick']), rn):.1f} s earlier for {float(b.iloc[-1]['blind_duration']):.1f} s; they still had {float(k.user_flash_duration):.1f} s of blindness when they died.", place=k.attacker_last_place_name, victim_sid=k.user_steamid, headshot=bool(k.headshot), kills=1)
            # trade
            prev = rd[(rd['tick'] < t) & (rd['tick'] >= t - 5 * TICK) & (rd['attacker_steamid'] == k.user_steamid) & (rd['user_team_num'] == team)]
            if len(prev):
                pv = prev.iloc[-1]
                att, atxt = attention(k.user_steamid, me, int(pv['tick']), t, str(k.user_name), 'you', str(pv['user_name']))
                card(t, 'trade_kill', pos, k.user_name, vpos, base_facts + f" They had killed {pv['user_name']} {rt(t, rn) - rt(int(pv['tick']), rn):.1f} s earlier. {atxt}".rstrip() + "", place=k.attacker_last_place_name, victim_sid=k.user_steamid, headshot=bool(k.headshot), extra_pos=(pv['user_X'], pv['user_Y']), extra_label=f"{pv['user_name']} died", **att)
            # retake
            if side == 'CT' and plant_t and t > plant_t and won:
                pr = plant[plant['total_rounds_played'] == rn].iloc[0]
                card(t, 'retake_kill', pos, k.user_name, vpos, base_facts + f" Bomb had been planted {rt(t, rn) - rt(plant_t, rn):.0f} s earlier; the round was won.", place=k.attacker_last_place_name, victim_sid=k.user_steamid, headshot=bool(k.headshot), extra_pos=(pr['user_X'], pr['user_Y']), extra_label='bomb')
            # reposition
            if i > 0:
                pk = rk.iloc[i - 1]
                moved = math.dist((pk['attacker_X'], pk['attacker_Y']), pos) * M
                if moved >= 8:
                    card(t, 'reposition_kill', pos, k.user_name, vpos, base_facts + f" Your previous kill ({pk['user_name']}) was {rt(t, rn) - rt(int(pk['tick']), rn):.0f} s earlier from {pk['attacker_last_place_name']}, {moved:.0f} m away.", place=k.attacker_last_place_name, victim_sid=k.user_steamid, headshot=bool(k.headshot), extra_pos=(pk['attacker_X'], pk['attacker_Y']))
        # multi-kill
        if len(rk) >= 2:
            k = rk.iloc[-1]; t = int(k['tick'])
            card(t, 'multi_kill', (k['attacker_X'], k['attacker_Y']), k['user_name'], (k['user_X'], k['user_Y']),
                 f"Round {rn+1}, {side}. {len(rk)} kills: " + '; '.join(f"{r.user_name} at {rt(int(r.tick), rn)} s from {r.attacker_last_place_name}" for r in rk.itertuples()) + f". {dmg} damage this round." + (" You survived." if not died else ""),
                 place=k['attacker_last_place_name'], victim_sid=k['user_steamid'], kills=len(rk), opponents=[(str(r.user_name), (r.user_X, r.user_Y)) for r in rk.itertuples()])
        # flash assists (teammate kill on an enemy I blinded)
        for k in rd[(rd['attacker_team_num'] == team) & (rd['attacker_steamid'] != me)].itertuples():
            t = int(k.tick)
            b = blind[(blind['total_rounds_played'] == rn) & (blind['attacker_steamid'] == me) & (blind['user_steamid'] == k.user_steamid) & (blind['tick'] <= t) & (blind['tick'] >= t - 4 * TICK)]
            if len(b) and k.user_flash_duration and k.user_flash_duration > 0:
                mp = mine[mine.index <= t]
                mp = (mp.iloc[-1].X, mp.iloc[-1].Y) if len(mp) else (k.attacker_X, k.attacker_Y)
                card(t, 'flash_assist', mp, k.user_name, (k.user_X, k.user_Y), f"Round {rn+1}, {side}, {rt(t, rn)} s. Your flash blinded {k.user_name} for {float(b.iloc[-1]['blind_duration']):.1f} s and {k.attacker_name} killed them at {k.user_last_place_name} while blind.", place=None, victim_sid=k.user_steamid, extra_pos=(k.attacker_X, k.attacker_Y), extra_label=f"{k.attacker_name} killed")
        # clutch
        team_deaths = rd[rd['user_team_num'] == team]
        if won and not died and len(team_deaths) >= 4:
            t4 = int(team_deaths.iloc[3]['tick'])
            ma, fo, md, mp = state(t4 + 8, team)
            if fo and fo >= 1:
                kills_after = int((rk['tick'] > t4).sum())
                last = mine[(mine.index >= t4) & (mine.index <= end_of(rn))]; lp = (last.iloc[-1].X, last.iloc[-1].Y) if len(last) else mp
                gg = by_tick.get(coarse(t4 + 8)); foes_pos = [(str(x.name), (x.X, x.Y)) for x in gg[(gg['team_num'] != team) & (gg['is_alive'] == True)].itertuples()] if gg is not None else []
                card(int(last.index[-1]) if len(last) else t4, 'clutch', lp, None, None, f"Round {rn+1}, {side}. Last alive from {rt(t4, rn)} s against {fo}. {kills_after} kills after that, {dmg} damage in the round, and the round was won.", place=None, vs=fo, kills=kills_after, opponents=foes_pos)
        # utility damage
        hu = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me) & (hurt['user_steamid'].isin(enemies)) & (hurt['weapon'].isin(['hegrenade', 'inferno', 'molotov', 'incgrenade']))]
        if len(hu):
            ud = int(hu['dmg_health'].clip(upper=100).sum())
            if ud >= 30:
                t = int(hu['tick'].min()); mp_ = mine[mine.index <= t]; mp_ = (mp_.iloc[-1].X, mp_.iloc[-1].Y) if len(mp_) else None
                if mp_: card(t, 'util_damage', mp_, None, None, f"Round {rn+1}, {side}. {ud} damage from grenades to {hu['user_name'].nunique()} enemies: " + ', '.join(f"{n} {int(v)}" for n, v in hu.groupby('user_name')['dmg_health'].sum().items()) + '.', place=None, dmg=ud)
        # utility on a signal: thrown on information, and it did something measurable
        from mistake_report import nade_flight, NADE_RADIUS
        fxt = D['fx']; gun_rn = D['gunfire'][D['gunfire']['total_rounds_played'] == rn]
        for r in D['nades'][(D['nades']['total_rounds_played'] == rn) & (D['nades']['weapon'].str.contains('smoke|molotov|incgrenade|flashbang|hegrenade', na=False))].itertuples():
            t0 = int(r.tick)
            if death_tick is not None and t0 > death_tick: continue
            w = r.weapon.replace('weapon_', ''); fl = nade_flight(D, me, t0, w)
            if fl is None: continue
            kind, _path, land, _thr, det = fl
            mypos = (r.user_X, r.user_Y)
            # signal in the 3 s before the throw
            sig = {}   # one signal per enemy: the first seen
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
            sig = list(sig.values())[:3]
            # effect
            eff = []; n_bl = 0; killed_blind = False; dmg = 0; held = []; crossed = []; mates_bl = 0
            fxrow = fxt[(fxt['kind'] == kind) & ((fxt['tick'] - det).abs() <= 2)]
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
                    R = NADE_RADIUS[kind] * M + 0.6
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
                                if math.dist((fr.iloc[0].X, fr.iloc[0].Y), land) * M < R: inside = True; break
                            (crossed if inside else held).append(str(f.name))
                    if held: eff.append(f"held {', '.join(held)} ({'was' if len(held) == 1 else 'were'} approaching it and never came through while it was up)")
                    if crossed: eff.append(f"{', '.join(crossed)} pushed through it anyway")
            effective = n_bl > 0 or dmg > 0 or len(held) > 0
            if not effective: continue
            lname = {'smokegrenade': 'Smoke', 'flashbang': 'Flash', 'hegrenade': 'HE', 'molotov': 'Molotov'}[kind]
            card(t0, 'util_on_signal', mypos, None, None,
                 f"Round {rn+1}, {side}, {rt(t0, rn)} s. {lname} from {r.user_last_place_name}, landed {math.dist(mypos, land) * M:.0f} m away. Signal: {'; '.join(sig)}. Effect: {'; '.join(eff)}.",
                 place=r.user_last_place_name, nade=kind, signal=sig, n_blinded=n_bl, killed_blind=killed_blind, dmg=dmg, n_held=len(held), n_crossed=len(crossed), n_mates_blinded=mates_bl, extra_pos=land, extra_label=f"{lname.lower()} landed")
        # survived with damage / saved rifle
        endpos = mine[(mine.index >= ft) & (mine.index <= end_of(rn))]
        if len(endpos):
            et = int(endpos.index[-1]); lp = (endpos.iloc[-1].X, endpos.iloc[-1].Y)
            if not died and dmg >= 100:
                card(et, 'survived_damage', lp, None, None, f"Round {rn+1}, {side}. {dmg} damage, {len(rk)} kills, survived the round.", place=endpos.iloc[-1].last_place_name, dmg=dmg)
            if not died and not won and equip >= 3000:
                card(et, 'saved_rifle', lp, None, None, f"Round {rn+1}, {side}. Round lost, you survived with ${equip} of equipment bought at freeze time.", place=endpos.iloc[-1].last_place_name)
        # deaths-based: traded death, good anchor
        for d in rdm.itertuples():
            t = int(d.tick); pos = (d.user_X, d.user_Y)
            later = rd[(rd['tick'] > t) & (rd['tick'] <= t + 5 * TICK) & (rd['user_steamid'] == d.attacker_steamid) & (rd['attacker_team_num'] == team)]
            if len(later):
                lt = later.iloc[0]
                att, atxt = attention(d.attacker_steamid, lt['attacker_steamid'], t, int(lt['tick']), str(d.attacker_name), str(lt['attacker_name']), 'you')
                card(t, 'died_tradeable', pos, d.attacker_name, (d.attacker_X, d.attacker_Y), f"Round {rn+1}, {side}, {rt(t, rn)} s. Died at {d.user_last_place_name} to {d.attacker_name}; {lt['attacker_name']} killed them {rt(int(lt['tick']), rn) - rt(t, rn):.1f} s later. {atxt}".strip(), place=d.user_last_place_name, victim_sid=d.attacker_steamid, z=float(d.user_Z), extra_pos=(lt['attacker_X'], lt['attacker_Y']), extra_label=f"{lt['attacker_name']} traded", **att)
            if side == 'CT':
                ma, fo, md, mp = state(t - 1, team)
                if ma is not None and ma >= 2 and md and md[0][0] > 15:
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
                    nades_after = int(((D['nades']['total_rounds_played'] == rn) & (D['nades']['tick'] >= (contact or t)) & (D['nades']['tick'] <= t)).sum())
                    if after >= 8 and (dmg_after >= 50 or nades_after):
                        card(t, 'good_anchor', pos, d.attacker_name, (d.attacker_X, d.attacker_Y), f"Round {rn+1}, {side}, {rt(t, rn)} s at {d.user_last_place_name}. Contact at {rt(contact, rn)} s with up to {foes_peak} attackers within 25 m; you lasted {after:.0f} s, did {dmg_after} damage and threw {nades_after} grenades after contact. Nearest teammate {md[0][1]} was {md[0][0]:.0f} m away.", place=d.user_last_place_name, victim_sid=d.attacker_steamid, dmg_after=dmg_after, nades_after=nades_after)
    # supported a teammate's fight: damage on their opponent before the fight was decided
    by_tick2 = by_tick; first_tick = int(min(by_tick2)); coarse_ticks = sorted(by_tick2)
    def coarse2(tk):
        c = tk - ((tk - first_tick) % 8)
        return c if c in by_tick2 else max([x for x in coarse_ticks if x <= tk], default=first_tick)
    for rn, ft in fz.items():
        g0 = by_tick2.get(ft)
        if g0 is None or not (g0['steamid'] == me).any(): continue
        team = int(g0[g0['steamid'] == me].iloc[0]['team_num']); side = 'CT' if team == 3 else 'T'
        if team not in (2, 3): continue
        won = D['winner'].get(rn) == side
        rd = deaths[deaths['total_rounds_played'] == rn]
        # fights where the teammate died (helper) plus fights the teammate won: approximate the latter from hurt pairs
        hh = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me)]
        seen_pairs = set()
        for f in teammate_fights(D, me, by_tick2, coarse2, rn, team):
            if f['dmg_before'] <= 0: continue
            key = (f['mate_sid'], f['enemy_sid'], f['t_start'] // 64)
            if key in seen_pairs: continue
            seen_pairs.add(key)
            e_died = bool(((rd['user_steamid'] == f['enemy_sid']) & (rd['tick'] <= f['t_death'] + 5 * TICK)).any())
            t = f['t_death']
            card(t, 'fight_support', f['my_pos'], f['enemy'], f['e_pos'],
                 f"Round {rn+1}, {side}, {rt(t, rn)} s. {f['mate']} fought {f['enemy']} for {f['dur']:.1f} s; you did {f['dmg_before']} damage to {f['enemy']} during the fight from {f['min_dist']:.0f} m at {f['my_place']}." + (f" {f['enemy']} died." if e_died else '') + (f" {f['mate']} still died." if True else ''),
                 place=f['my_place'], victim_sid=f['enemy_sid'], dmg=f['dmg_before'], enemy_died=e_died, mate_survived=False, extra_pos=f['mate_pos'], extra_label=f"{f['mate']} died")
    import positioning, flags_extra
    out.extend(positioning.positives(D, me))
    out.extend(flags_extra.positives(D, me))
    KEEP_NEAR = {'fight_support', 'good_anchor', 'died_tradeable'}
    for m in out:
        if m['kind'] not in KEEP_NEAR: m['near'] = None
        if m['kind'] == 'died_tradeable': m['near'] = None   # the trader is shown as its own marker
    return out


def draw_card(base, proj, m):
    img = base.copy(); d = ImageDraw.Draw(img); font = _font(15); small = _font(12)
    for key, col in (('victim_path', (255, 170, 60)), ('mate_path', (80, 140, 255))):
        pp = m.get(key) or []
        if len(pp) > 1:
            pts = [proj(*p) for p in pp]
            for i in range(1, len(pts)):
                f = 0.25 + 0.75 * i / len(pts)
                d.line([pts[i - 1], pts[i]], fill=tuple(int(c * f) for c in col), width=3)
            sx, sy = pts[0]; d.ellipse((sx - 3, sy - 3, sx + 3, sy + 3), outline=col, width=1)
    if len(m.get('path') or []) > 1:
        pts = [proj(*p) for p in m['path']]
        for i in range(1, len(pts)):
            a = int(80 + 175 * i / len(pts)); d.line([pts[i - 1], pts[i]], fill=(60, a, 90), width=3)
    for w, p in m.get('nades_thrown') or []:
        px, py = proj(*p); col = {'flashbang': (250, 240, 120), 'smokegrenade': (200, 200, 200), 'hegrenade': (240, 140, 60), 'molotov': (255, 90, 30), 'incgrenade': (255, 90, 30)}.get(w, (200, 200, 200))
        d.ellipse((px - 5, py - 5, px + 5, py + 5), outline=col, width=2)
    if m.get('near'):
        px, py = proj(*m['near'][2]); d.ellipse((px - 7, py - 7, px + 7, py + 7), fill=(80, 140, 255)); d.text((px + 10, py - 8), f"{m['near'][1]} {m['near'][0]:.0f}m", fill=(150, 190, 255), font=small)
    if m.get('vpos') and m['vpos'][0] is not None and not (isinstance(m['vpos'][0], float) and math.isnan(m['vpos'][0])):
        kx, ky = proj(*m['vpos']); mx, my = proj(*m['pos'])
        d.line([(kx, ky), (mx, my)], fill=(255, 170, 60), width=1)
        d.polygon([(kx, ky - 9), (kx - 8, ky + 6), (kx + 8, ky + 6)], fill=(255, 170, 60)); d.text((kx + 10, ky - 8), f"{m.get('victim') or ''}", fill=(255, 200, 120), font=small)
    if m.get('extra_pos'):
        ex, ey = proj(*m['extra_pos']); d.ellipse((ex - 6, ey - 6, ex + 6, ey + 6), outline=(120, 255, 120), width=2); d.text((ex + 9, ey - 8), m.get('extra_label', 'earlier kill'), fill=(140, 255, 140), font=small)
    mx, my = proj(*m['pos'])
    d.ellipse((mx - 8, my - 8, mx + 8, my + 8), fill=(70, 220, 110), outline=(255, 255, 255), width=2); d.text((mx + 12, my + 4), "you", fill=(150, 255, 170), font=small)
    sc = m.get('impact', 0); col = imp_rgb(sc)
    d.rectangle((0, 0, img.width, 28), fill=tuple(int(c * 0.55) for c in col)); d.rectangle((0, 0, 8, 28), fill=col)
    d.text((16, 6), f"R{m['round']} {m['side']} {m['time']}s  |  {RULES[m['kind']][0]}   impact {sc:+d}", fill=(255, 255, 255), font=font)
    d.text((10, img.height - 22), "green dot you   orange the enemy involved   blue nearest teammate   trails = last 12 s, small ring = start   rings your grenades", fill=(140, 140, 150), font=small)
    return img


def report(D, plays, out_path, demo_name):
    bases, proj, zthr = make_map(D)
    for m in plays:
        m['impact'], m['imp_breakdown'] = impact(m)
    counts = C.Counter(m['kind'] for m in plays)
    tot = {k: sum(m['impact'] for m in plays if m['kind'] == k) for k in counts}
    avg = {k: round(tot[k] / counts[k]) for k in counts}
    order = sorted(counts, key=lambda k: -tot[k])
    name = D['snap'][D['snap']['steamid'] == D['me']]['name'].iloc[0] if (D['snap']['steamid'] == D['me']).any() else D['me']
    h = [f"<!doctype html><html><head><meta charset='utf-8'><title>Impact report {D['map']}</title><style>"
         "body{font-family:Segoe UI,Arial,sans-serif;background:#111318;color:#e6e6e6;margin:0;padding:24px;max-width:1500px}"
         "h1{font-size:22px;margin:0 0 4px}h2{font-size:18px;margin:36px 0 8px;border-bottom:1px solid #333;padding-bottom:6px}"
         ".sum{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}.chip{background:#1d2130;border:1px solid #333;border-radius:8px;padding:8px 12px}"
         ".chip b{font-size:20px;display:block}.why{background:#1a1d26;border-left:4px solid #40b060;padding:10px 14px;margin:6px 0 14px;font-size:14px}"
         ".card{display:grid;grid-template-columns:560px 1fr;gap:18px;background:#171a22;border:1px solid #2a2e3a;border-radius:10px;padding:14px;margin:12px 0}"
         ".card img{width:560px;height:560px;border-radius:6px}.facts{font-size:14px;line-height:1.5}.facts .k{color:#6fd48a;font-weight:600}.facts .f{color:#8fd18f;font-weight:600}"
         ".lost{color:#ff7a7a}.won{color:#8fd18f}small{color:#999}"
         ".imp{display:inline-block;color:#fff;font-weight:700;padding:4px 10px;border-radius:6px;margin-bottom:6px}.impbr{font-size:12px;color:#aaa;margin-bottom:10px}</style></head><body>",
         f"<h1>Impact report: {name} on {D['map']}</h1><small>{demo_name}. {len(plays)} plays over {len(D['fz'])} rounds. The positive counterpart of the mistake report: what worked, why, and what to keep doing.</small>",
         "<div class='sum'>"]
    for k in order:
        h.append(f"<div class='chip' style='border-left:6px solid {imp_css(avg[k])}'><b>{counts[k]}</b>{RULES[k][0]}<br><small>avg impact {avg[k]}</small></div>")
    h.append("</div>")
    grouped = {}
    for m in sorted(plays, key=lambda m: -m['impact']):
        g = grouped.setdefault((m['round'], m['time']), dict(imp=m['impact'], m=m, kinds=[])); g['kinds'].append(RULES[m['kind']][0])
    top = sorted(grouped.values(), key=lambda g: -g['imp'])[:6]
    h.append("<h2>Highest-impact plays</h2><ol>" + ''.join(f"<li><span style='color:{imp_css(g['imp'])};font-weight:700'>{g['imp']}</span> &nbsp; R{g['m']['round']} {g['m']['side']} {g['m']['time']}s{(' at ' + g['m']['place']) if g['m'].get('place') else ''}: {'; '.join(g['kinds'])}</li>" for g in top) + "</ol>")
    for k in order:
        ms = sorted([m for m in plays if m['kind'] == k], key=lambda m: (-m['impact'], m['round'], m['time'] or 0))
        title, why, keep = RULES[k]
        h.append(f"<h2>{title} ({len(ms)})</h2><div class='why'><b>Why it worked:</b> {why}<br><b>Keep doing:</b> {keep}</div>")
        for m in ms:
            lower = bases['lower'] is not None and zthr is not None and m.get('z') is not None and m['z'] < zthr
            img = draw_card(bases['lower'] if lower else bases['upper'], proj, m)
            res = f"<span class='won'>Round won</span>" if m['won'] else f"<span class='lost'>Round lost</span>"
            sc = m['impact']; css = imp_css(sc)
            h.append(f"<div class='card' style='border-left:8px solid {css}'><img src='data:image/png;base64,{b64(img)}'><div class='facts'><div class='imp' style='background:{css}'>Impact {sc} / 100</div><div class='impbr'>{' &middot; '.join(m['imp_breakdown'])}</div><div class='k'>What happened</div>{m['facts']}<br>{res}"
                     f"<div class='k' style='margin-top:12px'>Why it worked</div>{why}<div class='f' style='margin-top:12px'>Keep doing</div>{keep}</div></div>")
    h.append("</body></html>")
    open(out_path, 'w', encoding='utf-8').write('\n'.join(h))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('demo'); ap.add_argument('--player', default='76561198063294402'); ap.add_argument('--out', default=None)
    a = ap.parse_args()
    out = a.out or os.path.splitext(os.path.basename(a.demo))[0] + '_impact.html'
    D = parse(a.demo, a.player)
    plays = detect(D)
    report(D, plays, out, os.path.basename(a.demo))
    print(f"{D['map']}: {len(plays)} plays -> {out}")
    for k, n in C.Counter(m['kind'] for m in plays).most_common(): print(f"  {RULES[k][0]}: {n}")

if __name__ == '__main__':
    main()
