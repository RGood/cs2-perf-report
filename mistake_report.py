"""Mistake report: parse a CS2 demo, flag one player's mistakes with rules, draw each on a map, write an HTML report.

Usage:
    python mistake_report.py <demo.dem> [--player 76561198063294402] [--out report.html]

The map background is built from the demo itself (every player position in the match), so no radar files are needed.
Requires: pip install demoparser2 pandas numpy pillow
"""
import sys, os, math, json, base64, argparse, collections as C
from io import BytesIO
import numpy as np, pandas as pd
from PIL import Image, ImageDraw, ImageFont
from demoparser2 import DemoParser

TICK = 64
M = 0.0254  # units -> metres
PROGRESS = lambda pct, msg: None   # set by the caller to receive (percent, message)
CONT_GAP = 10   # ticks (~0.16 s): shots closer together than this are one continuous run (AK/M4 cycle ~6-7 ticks)
SPRAY_RUN = 7   # a continuous run this long or longer is a spray; shorter runs are bursts
SAFE_WINDOW = 1.5  # seconds after contact during which no enemy could engage you, needed before a held grenade counts as usable
SAT_OUT_DEBUG = []
SHARED_FIGHT_S = 8    # a teammate who died this many seconds before you ...
SHARED_FIGHT_M = 15   # ... within this distance means you died second in a shared fight, not alone

# ----------------------------------------------------------------------------- rules text
RULES = {
    'util_unused': ("Died with usable utility",
        "Only counted when three things were true after contact: there was time (2 s for a flash or HE with the killer inside 30 m, 4 s for a smoke or molotov), there was a safe throw window of at least 1.5 s in which no nearby enemy was visible to your team, you were not visible to theirs, and you were not being hit, and the grenade would have done something. If the enemy could engage you the whole time, throwing would have been the mistake, and the grenade is not counted.",
        "Once contact is called and you are delaying, the usable grenades go out in the first seconds, not after the fight is lost. Flash the choke, HE the stack, molotov the entrance, then fight."),
    'util_too_early': ("Utility thrown too early",
        "A smoke or molotov thrown with no enemy within 30 m, none spotted by your team, and usually before the T side could even reach that choke. Later in the same round you were in contact for 4 s or more with no delay grenade left. The throw was on the clock, not on information.",
        "Hold the delay grenade until one of these exists: enemies seen or heard at the choke, a teammate's call, or the enemy's timing from earlier rounds. Before the earliest possible T arrival at that choke, nothing you throw is reacting to anything."),
    'separated_from_team': ("Isolated before dying",
        "In the 10 s before this death you and your nearest teammate moved apart, with two or more teammates still alive. This is the avoidable kind of untraded death: the gap was created by movement, not by the round state.",
        "When you move, move toward or with a teammate. If you have to go alone, go for a delay or information, not a duel."),
    'held_alone': ("Died anchoring",
        "Sometimes unavoidable: the anchor dies when three players hit the site. It still costs the round when it happens early, without damage, or without a call.",
        "Delay rather than duel: utility first, fall back to a crossfire spot, call the rotate at the first sound, and make them spend time on you."),
    'spray_at_range': ("Long-distance spray missed",
        "Only counted when the shots in the 4 s before the death include a continuous run of 7 or more at the weapon's cycle rate, aimed at enemies 20 m or more away, and those shots did 20 damage or less to anyone and got no kill. Shots that hit someone else are not misses. Bursts and taps are a different flag.",
        "Past 20 m fire 2 to 3 bullets, stop, counter-strafe, fire again. Never more than 4 without a reset."),
    'missed_at_range': ("Bursts missed at range",
        "You fired in bursts or taps, which is the right pattern, and still did 20 damage or less to anyone, with no kill, at enemies 20 m or more away. That is not spray control. It is the first bullets of each burst missing: crosshair placement before the peek, or the burst starting before the crosshair is on the target.",
        "Crosshair at head height on the exact corner before you swing it. Start the burst only when the crosshair is on the body, not while it is still moving. Yprac prefire and far-wall one-taps target this."),
    'kill_then_die': ("Traded by enemy",
        "After a kill everyone knows where you are, and the next enemy is already aiming at that spot. Re-peeking or staying is the deadliest 50-50 in the game.",
        "After every kill, move at least one position before the next fight. Take the trade only if a teammate is already swinging with you."),
    'early_solo_contact': ("Early solo T contact",
        "Contact before 20 s with nobody near you means the CT is set up and you are not. You had dealt no damage, so the round started a man down with no information. Not counted when a teammate died in the same fight just before you, or when a teammate had your killer in view.",
        "No contact in the first 20 s unless the team's utility has landed and a teammate is on your shoulder."),
    'lost_opener_ct': ("Lost CT opener",
        "First death of the round on CT hands the T side a numbers advantage before they have committed anywhere. It is the most expensive death in the round.",
        "Hold passive angles in the first 30 s with a teammate covering you. Take information from utility, not from a peek."),
    'died_blind': ("Died flashed",
        "A blinded player is a free kill. Either you pushed through a flash you saw coming, or a teammate blinded you.",
        "When a flash is thrown at your position, turn away and hold the corner. Call 'flashing' before your own throws and do not walk into teammates' flashes."),
    'eco_wander': ("Alone on eco",
        "On a pistol or eco round your value is the exit kill or the weapon pickup, and both need the group. Alone you die for nothing. Not counted when a teammate died in the same fight just before you, or when a teammate had your killer in view.",
        "Stack with the team on a save. Play for the exit kill together, or hide and save the pistol and armor."),
    'util_on_timer': ("Utility on a timer",
        "The same grenade from the same spot at the same second every round tells the enemy where you stand and when the choke is covered. They time their push to it.",
        "Throw on sound and on information, not on the clock. Some rounds throw nothing before 20 s and hold the angle instead."),
    'sat_out': ("Didn't join the fight",
        "A teammate was trading damage with an enemy for 1.5 s or more while you were free: alive, not fighting anyone, not flashed, and not being watched by another enemy. You knew where the fight was and could have established a sightline: you had the enemy in view during or shortly before it, they had you in view, the teammate beside you had them in view, or you could hear the shots from within 40 m. You could have reached it while it was still going (path distance at run speed plus reaction time, within the fight's length) and no other enemy was covering it. You did nothing for the whole fight. Distance alone never triggers this.",
        "When a teammate's fight starts within reach, move to it or swing it. Two guns on one enemy is the cheapest advantage in the game, and standing still while it happens is a free round for the other team."),
    'team_flash': ("Flashed a teammate",
        "Your flashbang blinded a teammate for a second or more. A blind teammate cannot hold their angle, trade, or see the push, and the blind lasts longer than the pop suggests. It counts far more when an enemy killed them while they were still blind.",
        "Call the flash, throw it from behind the teammate's line or higher, and keep them out of the pop: a flash that pops behind cover for your side and in the open for theirs."),
    'team_flash_death': ("Teammate died blind from your flash",
        "Your flashbang blinded a teammate and an enemy killed them while they were still blind. That is a kill you handed over.",
        "Before the throw, know where every teammate is looking. If a teammate is holding the angle the flash will pop over, tell them to look away or do not throw it."),
    'team_util_damage': ("Utility hurt a teammate",
        "Your HE or molotov damaged a teammate. Damage from your own utility is free for the enemy and costs the round when it comes at a bad time.",
        "Check the landing spot for teammates before you throw, and never throw a molotov where a teammate is about to move through."),
    'late_support': ("Late support",
        "A teammate was fighting an enemy you could have shot. You waited, they died, and only then did you engage the same enemy. Allowing 0.4 s to react and 0.6 s to swing, there was still time to help before they died.",
        "When a teammate takes a fight you can see or peek, you are in that fight from the first shot. Joining a second earlier turns a death into a 2v1."),
    **__import__('positioning').RULES_NEG,
    **__import__('flags_extra').RULES_NEG,
    'zero_impact_full_buy': ("Full buy, zero impact",
        "A full buy that ends with no damage and no grenades thrown is the most expensive possible round. The money was spent and nothing was bought with it.",
        "If the round is going badly, your grenades still have value: throw them for a teammate or for the retake. Get damage in before you die."),
}

# ----------------------------------------------------------------------------- parsing
def parse(path, me, attempts=3):
    """demoparser2 occasionally fails at random on some demos (a race in its threads: a spurious EntityNotFound, or a crash of
    the whole process). A Python-level failure is retried here; a crash is retried by the process runner in cs2report."""
    last = None
    for i in range(attempts):
        try: return _parse(path, me)
        except Exception as e:
            last = e
            if 'demoparser' not in (type(e).__module__ or '').lower() and 'DemoParser' not in type(e).__qualname__ and 'DemoParser' not in str(e): raise
            print(f"demo parser failed ({e}); retrying ({i + 2} of {attempts})", file=sys.stderr, flush=True)
    raise last


def _parse(path, me):
    p = DemoParser(path)
    mapname = p.parse_header().get('map_name', '?')
    PROGRESS(4, 'reading events')
    ms = p.parse_event("round_announce_match_start")
    start = int(ms['tick'].max()) if len(ms) else 0

    # every column any detector reads from an event table; an event the demo does not record (some league servers omit player_blind)
    # comes back as an empty table with these columns instead of a bare list
    EV_COLS = ['tick', 'total_rounds_played', 'user_steamid', 'user_name', 'user_X', 'user_Y', 'user_Z', 'user_team_num', 'user_last_place_name',
               'user_yaw', 'user_pitch', 'user_active_weapon_name', 'user_flash_duration', 'user_health', 'attacker_steamid', 'attacker_name',
               'attacker_X', 'attacker_Y', 'attacker_Z', 'attacker_team_num', 'attacker_last_place_name', 'blind_duration', 'weapon', 'dmg_health',
               'dmg_armor', 'hitgroup', 'health', 'headshot', 'distance', 'penetrated', 'thrusmoke', 'attackerblind', 'noscope', 'x', 'y', 'z',
               'entityid', 'winner', 'reason', 'site', 'silenced']
    def ev(name, **kw):
        d = p.parse_event(name, other=["total_rounds_played"], **kw)
        if not hasattr(d, 'columns'): d = pd.DataFrame(columns=EV_COLS)
        d = d[d['tick'] >= start].copy()
        for c in d.columns:
            if c.endswith('steamid'):
                d[c] = d[c].astype(str)
        return d

    freeze = ev("round_freeze_end"); rend = ev("round_end")
    fz = {int(r.total_rounds_played): int(r.tick) for r in freeze.itertuples()}
    winner = {int(r.total_rounds_played) - 1: r.winner for r in rend.itertuples()}
    deaths = ev("player_death", player=["X", "Y", "Z", "last_place_name", "team_num", "flash_duration", "active_weapon_name", "health"]).sort_values('tick')
    hurt = ev("player_hurt", player=["X", "Y"])
    fire = ev("weapon_fire", player=["X", "Y", "Z", "last_place_name", "yaw"])
    blind = ev("player_blind", player=["team_num"])
    plant = ev("bomb_planted", player=["X", "Y"])
    nade_re = 'grenade|molotov|flashbang|incgrenade|decoy'
    is_nade = fire['weapon'].str.contains(nade_re, na=False)
    all_nades = fire[is_nade]
    nades = all_nades[all_nades['user_steamid'] == me]
    gunfire = fire[~is_nade & ~fire['weapon'].str.contains('knife', na=False)]

    # coarse ticks for silhouette and paths (every 8 ticks), exact ticks for death snapshots
    death_ticks = [int(t) - 1 for t in deaths['tick']]
    coarse = list(range(start, int(deaths['tick'].max()) + 1, 8))
    nade_ticks = [int(t) for t in all_nades['tick']]
    PROGRESS(12, 'reading player positions for every tick')
    snap = p.parse_ticks(["X", "Y", "is_alive", "team_num", "last_place_name", "inventory", "current_equip_value", "spotted", "approximate_spotted_by", "flash_duration", "yaw"], ticks=sorted(set(coarse + death_ticks + nade_ticks + list(fz.values()))))
    # players not on a team at a sampled tick (connecting, spectating) have no team number; use 0 so int() never fails and no side matches
    snap['team_num'] = snap['team_num'].fillna(0)
    for df_ in (deaths, hurt, blind):
        for c_ in [c for c in df_.columns if c.endswith('team_num')]: df_[c_] = df_[c_].fillna(0)
    PROGRESS(30, 'positions read')
    snap['steamid'] = snap['steamid'].astype(str)
    round_end = {int(r.total_rounds_played) - 1: int(r.tick) for r in rend.itertuples()}
    # grenade projectiles: position every 4 ticks for the whole flight (entity ids are reused, so flights are split by tick gaps later)
    PROGRESS(30, 'reading grenade flights')
    gr = p.parse_grenades()
    gr = gr[gr['grenade_type'].str.endswith('Projectile') & gr['x'].notna() & (gr['tick'] >= start) & (gr['tick'] % 4 == 0)].copy()
    gr['kind'] = gr['grenade_type'].map({'CSmokeGrenadeProjectile': 'smokegrenade', 'CFlashbangProjectile': 'flashbang', 'CHEGrenadeProjectile': 'hegrenade',
                                         'CMolotovProjectile': 'molotov', 'CDecoyProjectile': 'decoy'}).fillna('other')
    gr['steamid'] = gr['steamid'].astype(str)
    proj = gr[['tick', 'x', 'y', 'z', 'steamid', 'kind', 'grenade_entity_id']].sort_values('tick').reset_index(drop=True)
    det = []
    for evname, kind in (('flashbang_detonate', 'flashbang'), ('smokegrenade_detonate', 'smokegrenade'), ('hegrenade_detonate', 'hegrenade'), ('inferno_startburn', 'molotov'), ('decoy_started', 'decoy')):
        try:
            e = p.parse_event(evname)
            if len(e): det.append(pd.DataFrame(dict(tick=e['tick'].astype(int), x=e['x'], y=e['y'], steamid=e['user_steamid'].astype(str), kind=kind)))
        except Exception: pass
    deton = pd.concat(det, ignore_index=True).sort_values('tick') if det else pd.DataFrame(columns=['tick', 'x', 'y', 'steamid', 'kind'])
    # effects for the replay: when each grenade went off, where, and when its effect ended (smoke: while its projectile entity lived;
    # fire: until inferno_expire; flash and HE: a short pop). C4: bomb_exploded at the plant position.
    try: expire = p.parse_event('inferno_expire')
    except Exception: expire = None
    try: boom = ev('bomb_exploded')
    except Exception: boom = None
    fx = []
    for r in deton.itertuples():
        t0 = int(r.tick); end = t0 + int(0.3 * TICK)
        if r.kind == 'smokegrenade':
            q = proj[(proj['steamid'] == r.steamid) & (proj['kind'] == 'smokegrenade') & (proj['tick'] >= t0) & (proj['tick'] <= t0 + 30 * TICK)]
            if len(q):
                tk = q['tick'].to_numpy(); cut = len(tk)
                for i in range(1, len(tk)):
                    if tk[i] - tk[i - 1] > TICK: cut = i; break
                end = int(tk[cut - 1])
            else: end = t0 + 18 * TICK
            end = min(end, t0 + 20 * TICK)   # the cloud is gone after 18 s plus its fade; the entity in the demo lingers a few seconds longer
        elif r.kind == 'molotov':
            e = expire[(expire['user_steamid'].astype(str) == r.steamid) & (expire['tick'] >= t0) & (expire['tick'] <= t0 + 12 * TICK)] if expire is not None and len(expire) else None
            end = int(e.iloc[0]['tick']) if e is not None and len(e) else t0 + 7 * TICK
        elif r.kind == 'hegrenade': end = t0 + int(0.5 * TICK)
        fx.append(dict(tick=t0, kind=r.kind, x=float(r.x), y=float(r.y), end=end))
    if boom is not None and len(boom):
        for r in boom.itertuples():
            pl = plant[plant['total_rounds_played'] == r.total_rounds_played]
            if len(pl): fx.append(dict(tick=int(r.tick), kind='c4', x=float(pl.iloc[-1]['user_X']), y=float(pl.iloc[-1]['user_Y']), end=int(r.tick) + int(1.5 * TICK)))
    fx = pd.DataFrame(fx, columns=['tick', 'kind', 'x', 'y', 'end']).sort_values('tick')
    # events for the extra flags (each may be absent in a demo; ev() then returns an empty table)
    reloads = ev("weapon_reload"); defuse_begin = ev("bomb_begindefuse"); defused = ev("bomb_defused"); plant_begin = ev("bomb_beginplant")
    bomb_drop = ev("bomb_dropped", player=["X", "Y", "last_place_name"]); bomb_pick = ev("bomb_pickup"); pickups = ev("item_pickup")
    exploded = boom if (boom is not None and hasattr(boom, 'columns')) else ev("bomb_exploded")
    # tick props sampled only where the extra flags read them: deaths, freeze ends, reloads, sniper shots, defuse starts
    want = sorted(set(death_ticks + list(fz.values()) + [int(t) for t in reloads['tick']] + [int(t) for t in fire[fire['weapon'].str.contains('awp|ssg08', na=False)]['tick']]
                      + [int(t) for t in defuse_begin['tick']] + [int(t) for t in fire['tick']][::1]))
    try:
        xt = p.parse_ticks(["ducking", "is_airborne", "active_weapon_ammo", "active_weapon_name", "is_scoped", "has_defuser", "has_helmet", "balance", "cash_spent_this_round"], ticks=want)
        xt['steamid'] = xt['steamid'].astype(str)
    except Exception:
        xt = pd.DataFrame(columns=['tick', 'steamid', 'ducking', 'is_airborne', 'active_weapon_ammo', 'active_weapon_name', 'is_scoped', 'has_defuser', 'has_helmet', 'balance', 'cash_spent_this_round'])
    return dict(reloads=reloads, defuse_begin=defuse_begin, defused=defused, plant_begin=plant_begin, bomb_drop=bomb_drop, bomb_pick=bomb_pick, pickups=pickups, exploded=exploded, xt=xt,
                map=mapname, fz=fz, winner=winner, round_end=round_end, deaths=deaths, hurt=hurt, gunfire=gunfire, nades=nades, all_nades=all_nades, blind=blind, plant=plant, snap=snap, me=me, proj=proj, deton=deton, fx=fx)


NADE_RADIUS = {'smokegrenade': 144, 'molotov': 150}   # world units: smoke cloud, molotov fire patch (for the landing marker only)


def nade_flight(D, steamid, throw_tick, weapon, max_s=8.0):
    """Flight of one thrown grenade: (kind, [(x, y), ...], end_xy) from the projectile table, ended at the detonation. None if no projectile was found."""
    kind = {'molotov': 'molotov', 'incgrenade': 'molotov', 'flashbang': 'flashbang', 'smokegrenade': 'smokegrenade', 'hegrenade': 'hegrenade', 'decoy': 'decoy'}.get(weapon.replace('weapon_', ''))
    if kind is None: return None
    pr = D['proj']; dt = D['deton']
    q = pr[(pr['steamid'] == str(steamid)) & (pr['kind'] == kind) & (pr['tick'] >= throw_tick - 2) & (pr['tick'] <= throw_tick + max_s * TICK)]
    if not len(q): return None
    # the entity that appears first after the throw
    first = q.groupby('grenade_entity_id')['tick'].min(); ent = first.idxmin()
    if first.min() > throw_tick + TICK: return None
    q = q[q['grenade_entity_id'] == ent].sort_values('tick')
    d = dt[(dt['steamid'] == str(steamid)) & (dt['kind'] == kind) & (dt['tick'] >= throw_tick) & (dt['tick'] <= throw_tick + max_s * TICK)]
    if len(d):
        end_tick = int(d.iloc[0]['tick']); end = (float(d.iloc[0]['x']), float(d.iloc[0]['y'])); q = q[q['tick'] <= end_tick]
    else:
        end_tick = int(q.iloc[-1]['tick']); end = (float(q.iloc[-1]['x']), float(q.iloc[-1]['y']))
    path = [(float(r.x), float(r.y)) for r in q.itertuples()][::2]
    if not path or path[-1] != end: path.append(end)
    return (kind, path, end, int(throw_tick), end_tick)



def for_player(D, sid):
    """Return a shallow copy of a parsed demo focused on another player (same snapshot, their grenades)."""
    E = dict(D); E['me'] = str(sid); E['nades'] = D['all_nades'][D['all_nades']['user_steamid'] == str(sid)]
    return E



# ----------------------------------------------------------------------------- teammate-fight analysis (shared by both sides)
REACTION_S = 0.4      # reasonable reaction time before support could begin
PEEK_S = 0.6          # time to swing and get the crosshair on the enemy
SUPPORT_RANGE_M = 30  # beyond this you could not realistically have joined
PEEK_RANGE_M = 20     # within this you could have peeked even without line of sight


def teammate_fights(D, me, by_tick, coarse, rn, team):
    """For each teammate death in round rn: the fight window, my ability to help, and when I actually engaged the killer.
    Returns a list of dicts (one per teammate death where the killer is an enemy)."""
    deaths = D['deaths']; hurt = D['hurt']; fire = D['gunfire']
    rd = deaths[(deaths['total_rounds_played'] == rn)].sort_values('tick')
    out = []
    for d in rd[(rd['user_team_num'] == team) & (rd['user_steamid'] != me)].itertuples():
        E = str(d.attacker_steamid); T = str(d.user_steamid); t_death = int(d.tick)
        if E in ('nan', 'None', '') or E == T: continue
        # was I alive at the death?
        g = by_tick.get(coarse(t_death - 1))
        if g is None: continue
        mr = g[g['steamid'] == me]
        if not len(mr) or not bool(mr.iloc[0]['is_alive']): continue
        # fight window: first damage between T and E in the 6 s before the death
        hh = hurt[(hurt['total_rounds_played'] == rn) & (hurt['tick'] >= t_death - 6 * TICK) & (hurt['tick'] <= t_death) &
                  (((hurt['attacker_steamid'] == E) & (hurt['user_steamid'] == T)) | ((hurt['attacker_steamid'] == T) & (hurt['user_steamid'] == E)))]
        t_start = int(hh['tick'].min()) if len(hh) else t_death
        dur = (t_death - t_start) / TICK
        # my own fights during the window (excluding E): hurt events with me as attacker or victim, other party not E
        mine = hurt[(hurt['total_rounds_played'] == rn) & (hurt['tick'] >= t_start - TICK) & (hurt['tick'] <= t_death) &
                    (((hurt['attacker_steamid'] == me) & (hurt['user_steamid'] != E)) | ((hurt['user_steamid'] == me) & (hurt['attacker_steamid'] != E)))]
        busy = len(mine) > 0
        # my damage on E before the death, and my first engagement of E (damage, or a shot while E was in my view)
        dmg_before = int(hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me) & (hurt['user_steamid'] == E) & (hurt['tick'] >= t_start) & (hurt['tick'] < t_death)]['dmg_health'].clip(upper=100).sum())
        after = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me) & (hurt['user_steamid'] == E) & (hurt['tick'] >= t_death) & (hurt['tick'] <= t_death + 4 * TICK)]
        t_engage = int(after['tick'].min()) if len(after) else None
        # my situation across the window, sampled on coarse ticks
        saw_from = None; min_dist = None; blind = False; my_pos = None; my_place = None; e_pos = None
        for ct in range(coarse(t_start), t_death + 1, 8):
            g = by_tick.get(ct)
            if g is None: continue
            mr = g[g['steamid'] == me]; er = g[g['steamid'] == E]
            if not len(mr) or not len(er): continue
            mr = mr.iloc[0]; er = er.iloc[0]
            dist = math.dist((mr.X, mr.Y), (er.X, er.Y)) * M
            if min_dist is None or dist < min_dist: min_dist = dist
            if (mr['flash_duration'] or 0) > 0.5: blind = True
            spot = er['approximate_spotted_by']
            try:
                seen = me in [str(x) for x in spot]
            except TypeError:
                seen = False
            if seen and saw_from is None and ct >= t_start + int(REACTION_S * TICK) and ct <= t_death - int(0.5 * TICK): saw_from = ct
            my_pos = (mr.X, mr.Y); my_place = mr['last_place_name']; e_pos = (er.X, er.Y)
        if not t_engage:
            # a shot fired at E counts as engaging if E was in my view at the time
            ff = fire[(fire['total_rounds_played'] == rn) & (fire['user_steamid'] == me) & (fire['tick'] >= t_death) & (fire['tick'] <= t_death + 4 * TICK)]
            for r in ff.itertuples():
                g = by_tick.get(coarse(int(r.tick))); er = g[g['steamid'] == E] if g is not None else None
                if er is not None and len(er):
                    try:
                        if me in [str(x) for x in er.iloc[0]['approximate_spotted_by']]: t_engage = int(r.tick); break
                    except TypeError:
                        pass
        out.append(dict(mate=str(d.user_name), mate_sid=T, enemy=str(d.attacker_name), enemy_sid=E, t_start=t_start, t_death=t_death, dur=dur,
                        busy=busy, blind=blind, dmg_before=dmg_before, t_engage=t_engage, saw_from=saw_from, min_dist=min_dist,
                        my_pos=my_pos, my_place=my_place, e_pos=e_pos, mate_pos=(d.user_X, d.user_Y), mate_place=str(d.user_last_place_name),
                        enemy_hp=int(d.attacker_health) if pd.notna(d.attacker_health) else None))
    return out



def by_tick_of(D):
    """Per-demo cache of the snapshot grouped by tick (shared by every detector and every player)."""
    if '_by_tick' not in D:
        D['_by_tick'] = {t: g for t, g in D['snap'].groupby('tick')}
    return D['_by_tick']


def ticktab_of(D):
    """Per-demo cache of compact numpy tables per tick: sid, name, team, X, Y, alive, spotted, place."""
    if '_ticktab' not in D:
        import numpy as np
        snap = D['snap'].sort_values('tick')
        ticks = snap['tick'].values
        cols = dict(sid=snap['steamid'].astype(str).values, name=snap['name'].astype(str).values, team=snap['team_num'].values.astype(int),
                    X=snap['X'].values.astype(float), Y=snap['Y'].values.astype(float), alive=snap['is_alive'].values.astype(bool),
                    spotted=snap['spotted'].values.astype(bool), place=snap['last_place_name'].astype(str).values)
        uniq, starts = np.unique(ticks, return_index=True)
        ends = list(starts[1:]) + [len(ticks)]
        D['_ticktab'] = {int(t): {k: v[a:b] for k, v in cols.items()} for t, a, b in zip(uniq, starts, ends)}
    return D['_ticktab']



def teammate_engagements(D, rn, team, me, gap_s=3.0):
    """Windows of damage exchanged between a teammate T and an enemy E in round rn: list of dicts(T, E, t0, t1, T_died, E_died)."""
    hurt = D['hurt']; deaths = D['deaths']
    h = hurt[(hurt['total_rounds_played'] == rn)]
    rd = deaths[deaths['total_rounds_played'] == rn]
    dead_at = {str(r.user_steamid): int(r.tick) for r in rd.itertuples()}
    pairs = {}
    for r in h.itertuples():
        a, v = str(r.attacker_steamid), str(r.user_steamid)
        # identify (teammate, enemy) regardless of direction
        pass
    # team membership from the snapshot at the freeze tick
    g = by_tick_of(D).get(D['fz'][rn])
    if g is None: return []
    my_team = set(str(x) for x in g[g['team_num'] == team]['steamid']) - {me}
    foes = set(str(x) for x in g[g['team_num'] != team]['steamid'])
    for r in h.itertuples():
        a, v = str(r.attacker_steamid), str(r.user_steamid)
        if a in my_team and v in foes: key = (a, v)
        elif v in my_team and a in foes: key = (v, a)
        else: continue
        pairs.setdefault(key, []).append(int(r.tick))
    out = []
    for (T, E), ticks in pairs.items():
        ticks.sort(); start = ticks[0]; last = ticks[0]
        for tk in ticks[1:] + [None]:
            if tk is None or tk - last > gap_s * TICK:
                t1 = last
                if T in dead_at and start <= dead_at[T] <= t1 + gap_s * TICK: t1 = max(t1, dead_at[T])
                if E in dead_at and start <= dead_at[E] <= t1 + gap_s * TICK: t1 = max(t1, dead_at[E])
                out.append(dict(T=T, E=E, t0=start, t1=t1, T_died=(T in dead_at and start <= dead_at[T] <= t1), E_died=(E in dead_at and start <= dead_at[E] <= t1)))
                if tk is not None: start = tk
            if tk is not None: last = tk
    return out

# ----------------------------------------------------------------------------- mistake detection
def nade_list(inv):
    try:
        return [x for x in inv if any(k in str(x) for k in ('Grenade', 'Molotov', 'Incendiary', 'Flashbang', 'Smoke', 'Decoy'))]
    except TypeError:
        return []

def detect(D):
    me = D['me']; fz = D['fz']; deaths = D['deaths']; snap = D['snap']
    by_tick = by_tick_of(D)
    mine = snap[snap['steamid'] == me].set_index('tick')
    out = []
    rt = lambda tick, rn: round((tick - fz[rn]) / TICK, 1) if rn in fz else None

    for d in deaths[deaths['user_steamid'] == me].itertuples():
        rn = int(d.total_rounds_played); t = int(d.tick); tsec = rt(t, rn)
        if tsec is None or tsec < 0: continue
        s = by_tick.get(t - 1)
        if s is None: continue
        team = int(d.user_team_num); side = 'CT' if team == 3 else 'T'
        if team not in (2, 3): continue
        me_row = s[s['steamid'] == me]
        me_row = me_row.iloc[0] if len(me_row) else None
        mates = s[(s['team_num'] == team) & (s['steamid'] != me) & (s['is_alive'] == True)]
        pos = (d.user_X, d.user_Y); kpos = (d.attacker_X, d.attacker_Y) if pd.notna(d.attacker_X) else None
        md = sorted([(math.dist(pos, (m.X, m.Y)) * M, m.name, (m.X, m.Y), m.last_place_name) for m in mates.itertuples()])
        near = md[0] if md else None
        K = str(d.attacker_steamid)
        def seen_by(sid_row, who):
            try: return who in [str(x) for x in sid_row['approximate_spotted_by']]
            except TypeError: return False
        # shared fight: a teammate died within SHARED_FIGHT_S before me AND was in the same engagement: same killer, damage exchanged
        # with my killer, or an enemy who had both of us in view at the same moment. Distance is only a sanity bound.
        shared = None
        for md_ in deaths[(deaths['total_rounds_played'] == rn) & (deaths['user_team_num'] == team) & (deaths['user_steamid'] != me) & (deaths['tick'] < t) & (deaths['tick'] >= t - SHARED_FIGHT_S * TICK)].itertuples():
            T_sid = str(md_.user_steamid); tT = int(md_.tick)
            dist_now = math.dist(pos, (md_.user_X, md_.user_Y)) * M
            g_then = by_tick.get(tT - 1); mr_then = g_then[g_then['steamid'] == me] if g_then is not None else None
            dist_then = math.dist((mr_then.iloc[0].X, mr_then.iloc[0].Y), (md_.user_X, md_.user_Y)) * M if mr_then is not None and len(mr_then) else dist_now
            dd = min(dist_now, dist_then)
            if dd > 2 * SHARED_FIGHT_M: continue
            same_killer = str(md_.attacker_steamid) == K
            hh = D['hurt'][(D['hurt']['total_rounds_played'] == rn) & (D['hurt']['tick'] >= tT - 6 * TICK) & (D['hurt']['tick'] <= t)]
            exchanged = bool(((hh['attacker_steamid'] == K) & (hh['user_steamid'] == T_sid)).any() or ((hh['attacker_steamid'] == T_sid) & (hh['user_steamid'] == K)).any())
            both_seen = False
            for ct in range(max(tT - 4 * TICK, int(min(by_tick))), tT + 1, 8):
                g = by_tick.get(ct)
                if g is None: continue
                mr_ = g[g['steamid'] == me]; tr_ = g[g['steamid'] == T_sid]
                if not len(mr_) or not len(tr_): continue
                try:
                    a_, b_ = set(str(x) for x in mr_.iloc[0]['approximate_spotted_by']), set(str(x) for x in tr_.iloc[0]['approximate_spotted_by'])
                except TypeError:
                    continue
                if a_ & b_: both_seen = True; break
            why = 'same killer' if same_killer else ('you and they traded damage with the same enemy' if exchanged else ('an enemy had both of you in view' if both_seen else None))
            if why and (shared is None or dd < shared[1]):
                shared = (str(md_.user_name), dd, (t - tT) / TICK, str(md_.user_last_place_name), why)
        # could a living teammate have traded? any teammate with my killer in view in the 2 s before my death
        mate_los = None
        mate_sids = set(str(x) for x in mates['steamid'])
        for ct in range(max(t - 2 * TICK, int(min(by_tick))), t, 8):
            g = by_tick.get(ct)
            if g is None: continue
            kr = g[g['steamid'] == K]
            if not len(kr): continue
            try:
                seen = [str(x) for x in kr.iloc[0]['approximate_spotted_by']]
            except TypeError:
                continue
            for x in seen:
                if x in mate_sids:
                    mate_los = str(g[g['steamid'] == x].iloc[0]['name']); break
            if mate_los: break
        later = deaths[(deaths['tick'] > t) & (deaths['tick'] <= t + 5 * TICK) & (deaths['user_steamid'] == d.attacker_steamid) & (deaths['total_rounds_played'] == rn)]
        traded = bool(len(later)) and bool((later['attacker_team_num'] == team).any())
        h = D['hurt'][(D['hurt']['total_rounds_played'] == rn) & (D['hurt']['attacker_steamid'] == me) & (D['hurt']['tick'] <= t)]
        dmg_round = int(h['dmg_health'].clip(upper=100).sum()); dmg_k = int(h[h['user_steamid'] == d.attacker_steamid]['dmg_health'].clip(upper=100).sum())
        shots = int(((D['gunfire']['total_rounds_played'] == rn) & (D['gunfire']['user_steamid'] == me) & (D['gunfire']['tick'] <= t)).sum())
        g4 = D['gunfire'][(D['gunfire']['total_rounds_played'] == rn) & (D['gunfire']['user_steamid'] == me) & (D['gunfire']['tick'] <= t) & (D['gunfire']['tick'] >= t - 4 * TICK)]
        shots4 = int(len(g4)); dmg_k4 = int(h[(h['user_steamid'] == d.attacker_steamid) & (h['tick'] >= t - 4 * TICK)]['dmg_health'].clip(upper=100).sum())
        hits4 = int(len(h[h['tick'] >= t - 4 * TICK]))
        dmg_any4 = int(h[h['tick'] >= t - 4 * TICK]['dmg_health'].clip(upper=100).sum())          # to anyone, not only the killer
        kills4 = int(((deaths['attacker_steamid'] == me) & (deaths['total_rounds_played'] == rn) & (deaths['tick'] >= t - 4 * TICK) & (deaths['tick'] <= t)).sum())
        # range of the shots: distance to the enemy each shot was aimed at (within 12 degrees), median; killer distance if none were aimed
        aimed = []
        for s_ in g4.itertuples():
            if not (getattr(s_, 'user_yaw', None) == getattr(s_, 'user_yaw', None)): continue
            ct_ = int(s_.tick) - ((int(s_.tick) - int(min(by_tick))) % 8); gg_ = by_tick.get(ct_)
            if gg_ is None: continue
            best = None
            for f_ in gg_[(gg_['team_num'] != team) & (gg_['is_alive'] == True)].itertuples():
                off_ = abs(((math.degrees(math.atan2(f_.Y - s_.user_Y, f_.X - s_.user_X)) - float(s_.user_yaw) + 180) % 360) - 180)
                if off_ < 12 and (best is None or off_ < best[0]): best = (off_, math.dist((s_.user_X, s_.user_Y), (f_.X, f_.Y)) * M)
            if best: aimed.append(best[1])
        aim_range = float(np.median(aimed)) if aimed else (float(d.distance) if pd.notna(d.distance) else 0)
        tk = sorted(int(x) for x in g4['tick']); runs = []
        for x in tk:
            if runs and x - runs[-1][-1] <= CONT_GAP: runs[-1].append(x)
            else: runs.append([x])
        run_lens = [len(r) for r in runs]; longest = max(run_lens) if run_lens else 0
        pattern = 'no shots' if not run_lens else ('a continuous spray of ' + str(longest) if longest >= SPRAY_RUN else ('bursts of ' + ', '.join(map(str, run_lens)) if longest >= 2 else str(len(run_lens)) + ' single taps'))
        c10 = t - 640; c10 = c10 - ((c10 - int(min(by_tick))) % 8)
        s10 = by_tick.get(c10); moved10 = None; mate10 = None
        if s10 is not None and (s10['steamid'] == me).any():
            m10 = s10[s10['steamid'] == me].iloc[0]; moved10 = math.dist(pos, (m10.X, m10.Y)) * M
            mm = s10[(s10['team_num'] == team) & (s10['steamid'] != me) & (s10['is_alive'] == True)]
            md10 = [math.dist((m10.X, m10.Y), (x.X, x.Y)) * M for x in mm.itertuples()]; mate10 = min(md10) if md10 else None
        rd = deaths[deaths['total_rounds_played'] == rn]
        order = int((rd['tick'] < t).sum()) + 1
        held = nade_list(me_row['inventory']) if me_row is not None else []
        # contact: first tick in the last 15 s with an enemy within 25 m of me (coarse ticks)
        contact = None; foes_peak = 0
        hurt_me_ticks = set(int(x) for x in D['hurt'][(D['hurt']['total_rounds_played'] == rn) & (D['hurt']['user_steamid'] == me)]['tick'])
        safe_run = 0; best_safe = 0; best_safe_end = None
        for ct in range(t - 15 * TICK, t, 8):
            g = by_tick.get(ct)
            if g is None: continue
            mr = g[g['steamid'] == me]
            if not len(mr): continue
            mp = (mr.iloc[0].X, mr.iloc[0].Y)
            foes_near = [f for f in g[(g['team_num'] != team) & (g['is_alive'] == True)].itertuples() if math.dist(mp, (f.X, f.Y)) * M < 25]
            n = len(foes_near)
            if n and contact is None: contact = ct
            foes_peak = max(foes_peak, n)
            if contact is not None:
                # a safe throw moment: nobody near is visible to my team, I am not visible to theirs, and I am not being hit
                me_seen = bool(mr.iloc[0]['spotted']); near_seen = any(bool(f.spotted) for f in foes_near)
                being_hit = any(h in hurt_me_ticks for h in range(ct - 8, ct + 1))
                if not me_seen and not near_seen and not being_hit:
                    safe_run += 1
                    if safe_run > best_safe: best_safe = safe_run; best_safe_end = ct
                else:
                    safe_run = 0
        after = (t - contact) / TICK if contact else 0.0
        safe_s = best_safe * 8 / TICK
        kd_m = float(d.distance) if pd.notna(d.distance) else 0
        usable = [n for n in held if after >= 2 and safe_s >= SAFE_WINDOW and ((('Flash' in n or 'High Explosive' in n) and kd_m <= 30) or (('Smoke' in n or 'Molotov' in n or 'Incendiary' in n) and after >= 4))]
        # my throws this round with signals at the throw
        throw_info = []
        thrown = D['nades'][(D['nades']['total_rounds_played'] == rn) & (D['nades']['tick'] <= t)]
        for r in thrown.itertuples():
            g = by_tick.get(int(r.tick)); nr = None; sp = None
            if g is not None:
                foes = g[(g['team_num'] != team) & (g['is_alive'] == True)]
                nr = sum(1 for f in foes.itertuples() if math.dist((r.user_X, r.user_Y), (f.X, f.Y)) * M < 30); sp = int(foes['spotted'].astype(bool).sum())
            throw_info.append(dict(t=rt(int(r.tick), rn), nade=r.weapon.replace('weapon_', ''), place=r.user_last_place_name, near=nr, spotted=sp,
                                   blind=(nr == 0 and sp == 0), pre=(contact is None or r.tick < contact)))
        equip = int(me_row['current_equip_value']) if me_row is not None else 0
        dist = float(d.distance) if pd.notna(d.distance) else 0
        # path: my positions in the last 12 s
        pt = mine[(mine.index >= t - 12 * TICK) & (mine.index <= t - 1)]
        path = [(r.X, r.Y) for r in pt.itertuples()]
        def path_of(sid):
            if sid is None: return []
            q = snap[(snap['steamid'] == str(sid)) & (snap['tick'] >= t - 12 * TICK) & (snap['tick'] <= t - 1) & (snap['is_alive'] == True)].sort_values('tick')
            return [(r.X, r.Y) for r in q.itertuples()]
        killer_path = path_of(d.attacker_steamid) if pd.notna(d.attacker_steamid) else []
        mate_sid = None
        if md:
            mrow = mates[mates['name'] == md[0][1]]
            mate_sid = mrow.iloc[0]['steamid'] if len(mrow) else None
        mate_path = path_of(mate_sid)
        thrown = D['nades'][(D['nades']['total_rounds_played'] == rn) & (D['nades']['tick'] <= t)]
        base = dict(round=rn + 1, side=side, time=tsec, z=float(d.user_Z) if pd.notna(d.user_Z) else None, order=order, dmg_round=dmg_round, equip=equip, after=after, foes_peak=foes_peak, moved10=moved10, n_usable=len(usable), place=d.user_last_place_name, pos=pos, killer=d.attacker_name, kpos=kpos, kplace=d.attacker_last_place_name,
                    weapon=d.weapon, my_weapon=d.user_active_weapon_name, dist=round(dist, 1), near=near, path=path, killer_path=killer_path, mate_path=mate_path, mates_alive=len(mates),
                    nades_thrown=[(r.weapon.replace('weapon_', ''), (r.user_X, r.user_Y)) for r in thrown.itertuples()], won=D['winner'].get(rn) == side)
        facts = f"Round {rn+1}, {side}, {tsec}s. Died at {d.user_last_place_name} to {d.attacker_name} ({d.weapon}) from {d.attacker_last_place_name}, {dist:.0f} m."
        if near: facts += f" Nearest teammate {near[1]} was {near[0]:.0f} m away at {near[3]}."
        if shared: facts += f" {shared[0]} had died {shared[2]:.1f} s earlier, {shared[1]:.0f} m from you at {shared[3]} ({shared[4]}): a shared fight, so this is not counted as an isolated death."
        if mate_los and not shared: facts += f" {mate_los} had your killer in view when you died, so a trade was possible from where they were."
        facts += f" In the 4 s before you died you fired {shots4} shots as {pattern}, {hits4} of them hit anyone, for {dmg_any4} damage in total and {dmg_k4} to your killer ({shots} shots, {dmg_k} damage over the whole round)."

        if usable and tsec > 10:
            win_end = rt(best_safe_end, rn) if best_safe_end else None
            out.append(dict(base, kind='util_unused', facts=facts + f" Contact began {after:.0f} s before you died with up to {foes_peak} attackers within 25 m. In that time you had a {safe_s:.1f} s window ending at {win_end} s where no nearby enemy was visible to your team, you were not visible to theirs, and you were not being hit. Usable and unthrown: {', '.join(usable)}." + (f" Not counted (no time or out of range): {', '.join(n for n in held if n not in usable)}." if len(held) > len(usable) else "")))
        elif held and tsec > 10 and contact is not None and after >= 2 and safe_s < SAFE_WINDOW:
            base['util_note'] = f"Held {', '.join(held)} at death, not counted: from contact at {rt(contact, rn)} s the enemy could engage you the whole time (longest safe window {safe_s:.1f} s), so throwing would have been the mistake."
        early = [x for x in throw_info if x['blind'] and x['pre'] and x['nade'] in ('smokegrenade', 'molotov', 'incgrenade')]
        if early and after >= 4 and not any(('Smoke' in n or 'Molotov' in n or 'Incendiary' in n) for n in held):
            e = early[0]
            out.append(dict(base, kind='util_too_early', facts=facts + f" At {e['t']} s you threw a {e['nade']} from {e['place']} with no enemy within 30 m and none spotted by your team. Contact came at {rt(contact, rn)} s and lasted {after:.0f} s; you had no smoke or molotov left for it." + (f" Throws that did have a signal: " + '; '.join(f"{x['nade']} at {x['t']} s with {x['near']} enemies within 30 m" for x in throw_info if not x['blind']) + '.' if any(not x['blind'] for x in throw_info) else "")))
        base['shared_fight'] = shared; base['mate_los'] = mate_los
        if len(mates) >= 2 and near and near[0] > 15 and not traded and not shared and not mate_los:
            sep = (moved10 is not None and moved10 > 12) or (mate10 is not None and mate10 < 15)
            gap = f" {len(mates)} teammates alive, nearest {near[0]:.0f} m away, nobody traded you."
            if sep:
                ten = f" Ten seconds earlier you were {moved10:.0f} m from this spot" + (f" and the nearest teammate was {mate10:.0f} m away." if mate10 is not None else ".")
                out.append(dict(base, kind='separated_from_team', facts=facts + gap + ten))
            else:
                out.append(dict(base, kind='held_alone', facts=facts + gap + " You had been in this area for at least 10 s with no teammate within 15 m."))
        if shots4 >= 6 and dmg_any4 <= 20 and kills4 == 0 and aim_range >= 20:
            tgt = f"the enemies you were aiming at were about {aim_range:.0f} m away" if aimed else f"your killer was {dist:.0f} m away"
            out.append(dict(base, kind='spray_at_range' if longest >= SPRAY_RUN else 'missed_at_range', facts=facts + f" Those shots did {dmg_any4} damage to anyone and got no kill; {tgt}. Longest continuous run: {longest} shots (spray threshold {SPRAY_RUN}).", aim_range=aim_range))
        mk = deaths[(deaths['attacker_steamid'] == me) & (deaths['total_rounds_played'] == rn) & (deaths['tick'] < t) & (deaths['tick'] >= t - 5 * TICK)]
        if len(mk):
            k = mk.iloc[-1]
            if pd.notna(k['attacker_X']) and math.dist(pos, (k['attacker_X'], k['attacker_Y'])) * M < 8:
                out.append(dict(base, kind='kill_then_die', facts=facts + f" You killed {k['user_name']} {round((t - k['tick']) / TICK, 1)} s earlier from within 8 m of where you died.", extra_pos=(k['user_X'], k['user_Y'])))
        if side == 'T' and tsec < 20 and near and near[0] > 10 and dmg_round == 0 and not shared and not mate_los:
            out.append(dict(base, kind='early_solo_contact', facts=facts))
        if side == 'CT' and order == 1 and tsec < 30:
            out.append(dict(base, kind='lost_opener_ct', facts=facts + " This was the first death of the round."))
        if d.user_flash_duration and d.user_flash_duration > 0:
            b = D['blind'][(D['blind']['total_rounds_played'] == rn) & (D['blind']['user_steamid'] == me) & (D['blind']['tick'] <= t) & (D['blind']['tick'] >= t - 6 * TICK)]
            who = 'unknown'
            if len(b):
                bb = b.iloc[-1]; who = f"{bb['attacker_name']} ({'teammate' if int(bb['attacker_team_num']) == team else 'enemy'})" if 'attacker_team_num' in b.columns and pd.notna(bb.get('attacker_team_num')) else str(bb['attacker_name'])
            out.append(dict(base, kind='died_blind', facts=facts + f" You had {d.user_flash_duration:.1f} s of flash left. Flashed by {who}."))
        if equip < 1500 and near and near[0] > 25 and not shared and not mate_los:
            out.append(dict(base, kind='eco_wander', facts=facts + f" Equipment value ${equip}."))

    # per-round: full buy, zero damage, zero nades thrown, died
    for rn, ft in fz.items():
        s = by_tick.get(ft)
        if s is None: continue
        r = s[s['steamid'] == me]
        if not len(r): continue
        r = r.iloc[0]; team = int(r['team_num']); side = 'CT' if team == 3 else 'T'
        if team not in (2, 3): continue
        h = D['hurt'][(D['hurt']['total_rounds_played'] == rn) & (D['hurt']['attacker_steamid'] == me)]
        thrown = D['nades'][D['nades']['total_rounds_played'] == rn]
        died = deaths[(deaths['total_rounds_played'] == rn) & (deaths['user_steamid'] == me)]
        if int(r['current_equip_value']) >= 3700 and int(h['dmg_health'].sum()) == 0 and not len(thrown) and len(died):
            dd = died.iloc[0]
            out.append(dict(round=rn + 1, side=side, time=rt(int(dd['tick']), rn), z=float(dd['user_Z']), place=dd['user_last_place_name'], pos=(dd['user_X'], dd['user_Y']), killer=dd['attacker_name'],
                            kpos=(dd['attacker_X'], dd['attacker_Y']), kplace=dd['attacker_last_place_name'], weapon=dd['weapon'], my_weapon=dd['user_active_weapon_name'], dist=0, near=None,
                            path=[(x.X, x.Y) for x in mine[(mine.index >= ft) & (mine.index <= int(dd['tick']))].itertuples()][::4], mates_alive=None, nades_thrown=[], won=D['winner'].get(rn) == side,
                            kind='zero_impact_full_buy', facts=f"Round {rn+1}, {side}. Equipment ${int(r['current_equip_value'])}, {len(nade_list(r['inventory']))} grenades bought, none thrown, 0 damage, died at {dd['user_last_place_name']} at {rt(int(dd['tick']), rn)} s."))

    # sat out: a teammate's fight I was free to join and never did (any outcome)
    first_tick = int(min(by_tick)); coarse_ticks = sorted(by_tick)
    def coarse0(tk):
        c = tk - ((tk - first_tick) % 8)
        return c if c in by_tick else max([x for x in coarse_ticks if x <= tk], default=first_tick)
    names = {str(r.steamid): str(r.name) for r in snap[['steamid', 'name']].drop_duplicates('steamid').itertuples()}
    for rn, ft in fz.items():
        g0 = by_tick.get(ft)
        if g0 is None or not (g0['steamid'] == me).any(): continue
        team = int(g0[g0['steamid'] == me].iloc[0]['team_num']); side = 'CT' if team == 3 else 'T'
        if team not in (2, 3): continue
        hurt_rn = D['hurt'][D['hurt']['total_rounds_played'] == rn]; fire_rn = D['gunfire'][(D['gunfire']['total_rounds_played'] == rn) & (D['gunfire']['user_steamid'] == me)]
        for e in teammate_engagements(D, rn, team, me):
            dur = (e['t1'] - e['t0']) / TICK
            if dur < 1.5: continue
            t0, t1, T, E = e['t0'], e['t1'], e['T'], e['E']
            # my own involvement: damage with anyone, or any enemy seeing me, or blind, or dead
            mine_h = hurt_rn[(hurt_rn['tick'] >= t0 - TICK) & (hurt_rn['tick'] <= t1 + TICK) & ((hurt_rn['attacker_steamid'] == me) | (hurt_rn['user_steamid'] == me))]
            if len(mine_h): continue
            engaged = hurt_rn[(hurt_rn['tick'] >= t0) & (hurt_rn['tick'] <= t1 + 4 * TICK) & (hurt_rn['attacker_steamid'] == me) & (hurt_rn['user_steamid'] == E)]
            if len(engaged): continue
            ok = True; min_dist = None; d_first = None; d_last = None; my_place = None; my_pos = None; e_pos = None; t_pos = None
            opportunity = None; other_threat = False; covering = False; near_others = False; others_alive = False
            def spot(row):
                try: return set(str(x) for x in row['approximate_spotted_by'])
                except TypeError: return set()
            for ct in range(coarse0(t0), t1 + 1, 16):
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
                who_sees_me = spot(mr); who_sees_E = spot(er)
                if who_sees_me - {E}: other_threat = True; break          # another enemy had me in view: a threat of my own
                # other enemies covering the fight: alive, not E, within 25 m of E, or with the teammate in view
                others = g[(g['team_num'] != team) & (g['is_alive'] == True) & (g['steamid'] != E)]
                who_sees_T = spot(tr.iloc[0]) if len(tr) else set()
                for o in others.itertuples():
                    do_e = math.dist((o.X, o.Y), (er.X, er.Y)) * M; do_me = math.dist((o.X, o.Y), (mr.X, mr.Y)) * M
                    if do_e <= 25 or str(o.steamid) in who_sees_T: covering = True
                    if do_e <= 40 or do_me <= 40: near_others = True
                    others_alive = True
                # evidence that a sightline to E was available to me
                if me in who_sees_E: opportunity = opportunity or 'you had the enemy in view yourself'
                elif T in who_sees_E and dt <= 12: opportunity = opportunity or f'{names.get(T, T)}, {dt:.0f} m from you, had the enemy in view'
                elif E in who_sees_me: opportunity = opportunity or 'the enemy had you in view'
                my_place = mr['last_place_name']; my_pos = (mr.X, mr.Y); e_pos = (er.X, er.Y); t_pos = (tr.iloc[0].X, tr.iloc[0].Y) if len(tr) else None
            if ok and not other_threat and my_pos is not None and not opportunity:
                # awareness without a live sightline: I had the enemy in view within the previous 10 s, or I could hear the fight
                for ct in range(coarse0(max(t0 - 10 * TICK, first_tick)), t0, 16):
                    g = by_tick.get(ct)
                    if g is None: continue
                    er = g[g['steamid'] == E]
                    if len(er) and me in spot(er.iloc[0]): opportunity = f'you had the enemy in view {(t0 - ct) / TICK:.0f} s before the fight started'; break
                if not opportunity:
                    shots = D['gunfire'][(D['gunfire']['total_rounds_played'] == rn) & (D['gunfire']['tick'] >= t0) & (D['gunfire']['tick'] <= t1) & (D['gunfire']['user_steamid'].isin([E, T]))]
                    for r in shots.itertuples():
                        g = by_tick.get(coarse0(int(r.tick)))
                        if g is None: continue
                        mr = g[g['steamid'] == me]; sr = g[g['steamid'] == str(r.user_steamid)]
                        if len(mr) and len(sr):
                            ds = math.dist((mr.iloc[0].X, mr.iloc[0].Y), (sr.iloc[0].X, sr.iloc[0].Y)) * M
                            if ds <= 40: opportunity = f'you could hear the fight: {names.get(str(r.user_steamid), "a player")} was shooting {ds:.0f} m from you'; break
            if not ok or other_threat or min_dist is None or my_pos is None or not opportunity: continue
            if min_dist > 45: continue
            if opportunity.startswith('you could hear') and dur < 3.0: continue    # sound alone needs time to hear, react and move
            # reachability: could I have got there while the fight was still on? path ~1.3x straight line, rifle run speed 5.5 m/s, 0.4 s reaction
            reach_s = (min_dist * 1.3) / 5.5 + 0.4
            SAT_OUT_DEBUG.append(dict(me=names.get(me, me), rn=rn + 1, T=names.get(T, T), E=names.get(E, E), dur=round(dur, 1), min_dist=round(min_dist, 1), reach=round(reach_s, 1), covering=covering, near_others=near_others, opp=opportunity))
            if reach_s > dur: continue
            # risk: another enemy covering the fight makes joining a bad trade; with sound-only evidence, any other enemy nearby rules it out
            if covering: continue
            if opportunity.startswith('you could hear') and near_others: continue
            # was I moving to help? closed 8 m or more toward the enemy over the fight
            if d_first is not None and d_last is not None and d_first - d_last >= 8: continue
            # did I fire at anything (a fight of my own that did no damage)?
            if len(fire_rn[(fire_rn['tick'] >= t0) & (fire_rn['tick'] <= t1)]): continue
            e_hp = None
            gE = by_tick.get(coarse0(t1)); erE = gE[gE['steamid'] == E] if gE is not None else None
            if erE is not None and len(erE) and 'health' in erE.columns: e_hp = int(erE.iloc[0]['health'])
            facts = (f"Round {rn+1}, {side}, {rt(t0, rn)} s to {rt(t1, rn)} s. {names.get(T, T)} fought {names.get(E, E)} for {dur:.1f} s"
                     + (f" and died" if e['T_died'] else (" and killed them" if e['E_died'] else " and both survived")) + f". You were at {my_place}, alive, not fighting anyone, not flashed, and no other enemy had you in view. Sightline evidence: {opportunity}. Reaching the fight would have taken about {reach_s:.1f} s of its {dur:.1f} s, and no other enemy was covering it. You did not fire, did no damage to {names.get(E, E)}, and did not move toward the fight.")
            out.append(dict(round=rn + 1, side=side, time=rt(t1, rn), z=None, place=my_place, pos=my_pos, killer=names.get(E, E), kpos=e_pos, kplace=None, weapon=None, my_weapon=None, dist=round(min_dist, 1),
                            near=(math.dist(my_pos, t_pos) * M, names.get(T, T), t_pos, '') if t_pos else None, path=[(r.X, r.Y) for r in mine[(mine.index >= t1 - 12 * TICK) & (mine.index <= t1)].itertuples()],
                            killer_path=[], mate_path=[], mates_alive=None, nades_thrown=[], won=D['winner'].get(rn) == side, kind='sat_out', facts=facts,
                            mate_died=e['T_died'], enemy_hp_after=e_hp, min_dist=min_dist, dur=dur, opportunity=opportunity, extra_pos=t_pos, extra_label=f"{names.get(T, T)} fighting"))

    # late support: a teammate's fight I could have joined but only engaged after they died
    first_tick = int(min(by_tick)); coarse_ticks = sorted(by_tick)
    def coarse(tk):
        c = tk - ((tk - first_tick) % 8)
        return c if c in by_tick else max([x for x in coarse_ticks if x <= tk], default=first_tick)
    for rn, ft in fz.items():
        g0 = by_tick.get(ft)
        if g0 is None or not (g0['steamid'] == me).any(): continue
        team = int(g0[g0['steamid'] == me].iloc[0]['team_num']); side = 'CT' if team == 3 else 'T'
        if team not in (2, 3): continue
        for f in teammate_fights(D, me, by_tick, coarse, rn, team):
            usable = f['dur'] - REACTION_S - PEEK_S
            if usable < 0.4 or f['busy'] or f['blind'] or f['min_dist'] is None or f['min_dist'] > SUPPORT_RANGE_M: continue
            if f['dmg_before'] > 0 or not f['t_engage']: continue
            saw = f['saw_from'] is not None
            if not saw and f['min_dist'] > PEEK_RANGE_M: continue
            t = f['t_death']
            pt = mine[(mine.index >= t - 12 * TICK) & (mine.index <= t)]
            facts = (f"Round {rn+1}, {side}, {rt(t, rn)} s. {f['mate']} fought {f['enemy']} for {f['dur']:.1f} s ({rt(f['t_start'], rn)} s to {rt(t, rn)} s) and died at {f['mate_place']}. "
                     f"You were {f['min_dist']:.0f} m from {f['enemy']} at {f['my_place']}, not in a fight and not flashed. "
                     + (f"{f['enemy']} had you in view from {rt(f['saw_from'], rn)} s. " if saw else f"You had no line of sight but were within {PEEK_RANGE_M} m and could have peeked. ")
                     + f"You did no damage during the fight and first engaged {f['enemy']} {(f['t_engage'] - t) / TICK:.1f} s after {f['mate']} died"
                     + (f"; {f['enemy']} had {f['enemy_hp']} hp left." if f['enemy_hp'] is not None else '.'))
            out.append(dict(round=rn + 1, side=side, time=rt(t, rn), z=None, place=f['my_place'], pos=f['my_pos'], killer=f['enemy'], kpos=f['e_pos'], kplace=None,
                            weapon=None, my_weapon=None, dist=round(f['min_dist'], 1), near=(math.dist(f['my_pos'], f['mate_pos']) * M, f['mate'], f['mate_pos'], f['mate_place']),
                            path=[(r.X, r.Y) for r in pt.itertuples()], killer_path=[], mate_path=[], mates_alive=None, nades_thrown=[], won=D['winner'].get(rn) == side,
                            kind='late_support', facts=facts, saw=saw, spare_s=usable, enemy_hp=f['enemy_hp'], extra_pos=f['mate_pos'], extra_label=f"{f['mate']} died"))

    import positioning, flags_extra
    out.extend(positioning.negatives(D, me))
    out.extend(flags_extra.negatives(D, me))
    out = [o for o in out if o['kind'] not in flags_extra.RETIRED]
    KEEP_NEAR = {'separated_from_team', 'held_alone', 'early_solo_contact', 'eco_wander', 'late_support', 'sat_out'}
    for m_ in out:
        if m_['kind'] not in KEEP_NEAR: m_['near'] = None

    # utility on a timer: same nade type + place + side, within 1.5 s spread, in >= 4 rounds
    groups = C.defaultdict(list)
    for r in D['nades'].itertuples():
        rn = int(r.total_rounds_played)
        if rn not in fz: continue
        s = by_tick.get(fz[rn]); side = None
        if s is not None:
            m = s[s['steamid'] == me]
            if len(m): side = 'CT' if int(m.iloc[0]['team_num']) == 3 else 'T'
        groups[(side, r.weapon.replace('weapon_', ''), r.user_last_place_name)].append((rn + 1, rt(int(r.tick), rn), (r.user_X, r.user_Y)))
    for (side, w, place), items in groups.items():
        times = [x[1] for x in items if x[1] is not None and x[1] > 0]
        if len(items) >= 4 and len(times) >= 4 and (max(times) - min(times)) <= 3.0:
            out.append(dict(round=items[0][0], side=side, time=round(float(np.mean(times)), 1), place=place, pos=items[0][2], killer=None, kpos=None, kplace=None, weapon=None, my_weapon=None, dist=0, near=None,
                            path=[], mates_alive=None, nades_thrown=[(w, x[2]) for x in items], won=None, kind='util_on_timer', repeats=len(items),
                            facts=f"{side} side: {w} thrown from {place} in {len(items)} rounds ({', '.join('R'+str(x[0]) for x in items)}) at {min(times)} to {max(times)} s every time."))

    # utility that hurt your own team
    bl = D['blind']; hurt = D['hurt']; nm = {str(r.steamid): str(r.name) for r in snap[['steamid', 'name']].drop_duplicates('steamid').itertuples()}
    first_tick = int(min(by_tick))
    def crs(tk_):
        c = tk_ - ((tk_ - first_tick) % 8)
        return c if c in by_tick else None
    def team_at(rn, sid):
        g0 = by_tick.get(fz[rn]); r0 = g0[g0['steamid'] == str(sid)] if g0 is not None else None
        return int(r0.iloc[0]['team_num']) if r0 is not None and len(r0) and r0.iloc[0]['team_num'] == r0.iloc[0]['team_num'] else None
    myb = bl[(bl['attacker_steamid'] == me) & (bl['user_steamid'] != me)] if len(bl) else bl
    for tick_, grp in myb.groupby('tick'):                      # one detonation = one flash
        rn = int(grp.iloc[0]['total_rounds_played']); t = int(tick_)
        if rn not in fz: continue
        team = team_at(rn, me)
        if team not in (2, 3): continue
        side = 'CT' if team == 3 else 'T'
        mates = grp[(grp['user_team_num'] == team) & (grp['blind_duration'] >= 1.0)]
        if not len(mates): continue
        foes = grp[(grp['user_team_num'] != team) & (grp['blind_duration'] >= 1.0)]
        g = by_tick.get(crs(t)); mr = g[g['steamid'] == me] if g is not None else None
        my_pos = (float(mr.iloc[0].X), float(mr.iloc[0].Y)) if mr is not None and len(mr) else None
        my_place = str(mr.iloc[0]['last_place_name']) if mr is not None and len(mr) else None
        thr = D['nades'][(D['nades']['weapon'].str.contains('flashbang', na=False)) & (D['nades']['tick'] <= t) & (D['nades']['tick'] >= t - 6 * TICK)]
        thrown = [('flashbang', (float(thr.iloc[-1]['user_X']), float(thr.iloc[-1]['user_Y'])))] if len(thr) else []
        if my_pos is None and thrown: my_pos = thrown[0][1]
        if my_pos is None: continue
        parts = []; died = []; extra = None; max_dur = 0.0
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
        out.append(dict(round=rn + 1, side=side, time=rt(t, rn), z=None, place=my_place, pos=my_pos, killer=None, kpos=None, kplace=None, weapon=None, my_weapon=None, dist=0, near=None,
                        path=[], mates_alive=None, nades_thrown=thrown, won=D['winner'].get(rn) == side, kind='team_flash', facts=facts, mate_died_blind=bool(died),
                        n_mates=len(mates), max_dur=max_dur, n_foes=len(foes), blind_left=(max(0, died[0]['left']) if died else 0),
                        extra_pos=extra[0] if extra else None, extra_label=extra[1] if extra else None))
    # HE or molotov damage to teammates, one flag per grenade type per round
    hm = hurt[(hurt['attacker_steamid'] == me) & (hurt['user_steamid'] != me) & (hurt['weapon'].isin(['hegrenade', 'inferno']))] if len(hurt) else hurt
    for (rn, wpn), grp in hm.groupby(['total_rounds_played', 'weapon']):
        rn = int(rn)
        if rn not in fz: continue
        team = team_at(rn, me)
        if team not in (2, 3): continue
        side = 'CT' if team == 3 else 'T'
        grp = grp[[team_at(rn, s) == team for s in grp['user_steamid']]]
        if not len(grp): continue
        dmg = int(grp['dmg_health'].clip(upper=100).sum())
        if dmg < 5: continue
        t = int(grp['tick'].min()); g = by_tick.get(crs(t)); mr = g[g['steamid'] == me] if g is not None else None
        my_pos = (float(mr.iloc[0].X), float(mr.iloc[0].Y)) if mr is not None and len(mr) else None
        if my_pos is None: continue
        victims = grp.groupby('user_name')['dmg_health'].sum().sort_values(ascending=False)
        kd = deaths[(deaths['total_rounds_played'] == rn) & (deaths['attacker_steamid'] == me) & (deaths['weapon'].isin(['hegrenade', 'inferno'])) & (deaths['user_steamid'].isin(grp['user_steamid']))]
        label = 'HE' if wpn == 'hegrenade' else 'molotov'
        first = grp.sort_values('tick').iloc[0]
        vpos = (float(first['user_X']), float(first['user_Y'])) if first['user_X'] == first['user_X'] else None
        facts = (f"Round {rn+1}, {side}, {rt(t, rn)} s. Your {label} did {dmg} damage to " + (', '.join(f"{n} ({int(v)})" for n, v in victims.items()) if len(victims) > 1 else str(victims.index[0])) + '.'
                 + (f" {', '.join(kd['user_name'])} died from it." if len(kd) else ''))
        out.append(dict(round=rn + 1, side=side, time=rt(t, rn), z=None, place=str(mr.iloc[0]['last_place_name']), pos=my_pos, killer=None, kpos=None, kplace=None, weapon=None, my_weapon=None, dist=0, near=None,
                        path=[], mates_alive=None, nades_thrown=[], won=D['winner'].get(rn) == side, kind='team_util_damage', facts=facts, dmg=dmg, mate_died=bool(len(kd)),
                        extra_pos=vpos, extra_label=f"{first['user_name']} hit"))
    return out

# ----------------------------------------------------------------------------- severity
BASE_SEVERITY = {
    'zero_impact_full_buy': 50, 'lost_opener_ct': 50, 'separated_from_team': 45, 'early_solo_contact': 45,
    'kill_then_die': 36, 'util_too_early': 36, 'util_unused': 34, 'spray_at_range': 30, 'died_blind': 28, 'util_on_timer': 30,
    'missed_at_range': 26, 'held_alone': 28, 'eco_wander': 20, 'late_support': 40, 'sat_out': 32, 'team_flash': 22, 'team_flash_death': 48, 'team_util_damage': 20,
    **__import__('positioning').BASE_NEG,
    **__import__('flags_extra').BASE_NEG,
}

for _k in __import__('flags_extra').RETIRED:
    RULES.pop(_k, None); BASE_SEVERITY.pop(_k, None)


def severity(m):
    """0-100. Base weight for the mistake type, then context modifiers. Returns (score, breakdown list)."""
    k = m['kind']; score = BASE_SEVERITY.get(k, 40); br = [f"base {score} for this mistake type"]
    def add(v, why):
        nonlocal score
        if v:
            score += v; br.append(f"{v:+d} {why}")
    rm = int(round(min(10, max(3, 0.25 * BASE_SEVERITY.get(k, 40)))))
    if m.get('won') is False: add(rm, 'round lost')
    elif m.get('won') is True: add(-rm, 'round won anyway')
    ma = m.get('mates_alive')
    if ma is not None and k != 'util_on_timer':
        add({4: 10, 3: 7, 2: 3}.get(ma, 0), f'{ma} teammates still alive')
    if m.get('order') == 1: add(8, 'first death of the round')
    if m.get('dmg_round') == 0 and k not in ('util_on_timer', 'zero_impact_full_buy'): add(8, 'no damage dealt that round')
    eq = m.get('equip')
    if eq is not None and k not in ('eco_wander', 'util_on_timer'):
        if eq >= 3700: add(6, 'full buy lost')
        elif eq < 1500: add(-8, 'eco round')
    if k == 'util_unused':
        add(min(8, 4 * (m.get('n_usable', 1) - 1)), 'more than one usable grenade held')
        add(4 if (m.get('after') or 0) >= 8 else 0, '8 s or more of contact to use it')
    if k == 'separated_from_team' and m.get('moved10'): add(min(8, int(m['moved10'] // 4)), f"moved {m['moved10']:.0f} m away in the last 10 s")
    if k == 'util_on_timer': add(min(16, 4 * (m.get('repeats', 4) - 4)), f"repeated in {m.get('repeats')} rounds")
    if k in ('spray_at_range', 'missed_at_range', 'held_alone') and (m.get('foes_peak') or 0) >= 3: add(-5, 'outnumbered 3+ at the time')
    if k == 'crossfire': add(min(8, 4 * (m.get('n_seen', 2) - 2)), f"{m.get('n_seen')} enemies had you in view")
    if k == 'swung_into_hold': add(5 if (m.get('k_aim') or 99) <= 8 else 0, 'they were already dead-on you')
    if k == 'seen_first': add(min(8, int((m.get('lead') or 0) * 2)), f"seen {m.get('lead', 0):.1f} s before you saw them")
    if k in ('team_flash', 'team_flash_death'):
        add(4 * max(0, (m.get('n_mates') or 1) - 1), f"{m.get('n_mates')} teammates blinded")
        add(min(8, int((m.get('max_dur') or 0) * 2)), f"blinded for up to {m.get('max_dur', 0):.1f} s")
        add(-4 if (m.get('n_foes') or 0) else 0, f"it also blinded {m.get('n_foes')} {'enemy' if m.get('n_foes') == 1 else 'enemies'}")
        if m.get('mate_died_blind'):
            add(26, 'a teammate died while still blind from it')
            add(6 if (m.get('blind_left') or 0) >= 1.0 else 0, f"they still had {m.get('blind_left', 0):.1f} s of blind left when they died")
    if k == 'team_util_damage':
        add(min(15, int((m.get('dmg') or 0) // 5)), f"{m.get('dmg')} damage to teammates")
        add(20 if m.get('mate_died') else 0, 'a teammate died from it')
    if k == 'sat_out':
        add(8 if m.get('mate_died') else 0, 'your teammate died in that fight')
        add(5 if (m.get('enemy_hp_after') or 0) >= 60 else 0, 'the enemy walked away barely hurt')
        add(4 if 'yourself' in (m.get('opportunity') or '') else 0, 'you had the enemy in view yourself')
        add(min(6, int((m.get('dur') or 0))), f"the fight lasted {m.get('dur', 0):.1f} s")
    if k == 'late_support':
        add(6 if m.get('saw') else 0, 'you had the enemy in view during the fight')
        add(min(8, int((m.get('spare_s') or 0) * 4)), f"{m.get('spare_s', 0):.1f} s of usable time before the death")
        add(5 if (m.get('enemy_hp') or 0) >= 80 else 0, 'the enemy was barely damaged when your teammate died')
    score = max(0, min(100, score))
    return score, br

def sev_rgb(score):
    a = (60, 64, 78); b = (225, 55, 55); f = max(0.0, min(1.0, score / 100.0))
    return tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3))

def sev_css(score):
    r, g, b = sev_rgb(score); return f"rgb({r},{g},{b})"

# ----------------------------------------------------------------------------- drawing
def make_map(D, size=900):
    """Returns (bases, proj, threshold_z). bases = {'upper': img, 'lower': img or None}.
    Uses the map's radar image + the game's overview offsets when tools/maps/<map>.png exists; otherwise a silhouette built from the demo."""
    here = os.path.dirname(os.path.abspath(__file__)); mdir = os.path.join(here, 'maps')
    offs = {}
    if os.path.exists(os.path.join(mdir, 'offsets.json')):
        offs = json.load(open(os.path.join(mdir, 'offsets.json')))
    snap = D['snap']
    pts = snap[snap['is_alive'] == True][['X', 'Y', 'last_place_name']].dropna()
    name = D['map']
    if name in offs and os.path.exists(os.path.join(mdir, name + '.png')):
        o = offs[name]; k = size / 1024.0
        def proj(x, y):
            if x != x or y != y: return (-9999, -9999)      # missing position: draw far off the canvas rather than fail
            return (int((x - o['pos_x']) / o['scale'] * k), int((o['pos_y'] - y) / o['scale'] * k))
        def load(fn):
            im = Image.open(fn).convert('RGB').resize((size, size), Image.LANCZOS)
            return Image.eval(im, lambda v: int(v * 0.72))
        bases = {'upper': load(os.path.join(mdir, name + '.png')),
                 'lower': load(os.path.join(mdir, name + '_lower.png')) if os.path.exists(os.path.join(mdir, name + '_lower.png')) else None}
        zthr = o.get('threshold_z') if bases['lower'] is not None else None
        font = _font(11)
        for key, im in bases.items():
            if im is None: continue
            d2 = ImageDraw.Draw(im)
            for place, g in pts.groupby('last_place_name'):
                if len(g) < 200 or not place: continue
                px, py = proj(g['X'].median(), g['Y'].median())
                d2.text((px + 1, py + 1), str(place), fill=(0, 0, 0), font=font, anchor='mm')
                d2.text((px, py), str(place), fill=(225, 228, 235), font=font, anchor='mm')
        return bases, proj, zthr
    # fallback: silhouette from the demo's own positions
    xmin, xmax = pts['X'].quantile(0.002), pts['X'].quantile(0.998); ymin, ymax = pts['Y'].quantile(0.002), pts['Y'].quantile(0.998)
    pad = 0.04 * max(xmax - xmin, ymax - ymin)
    xmin -= pad; xmax += pad; ymin -= pad; ymax += pad
    span = max(xmax - xmin, ymax - ymin)
    def proj(x, y):
        if x != x or y != y: return (-9999, -9999)
        return (int((x - xmin) / span * size), int((ymax - y) / span * size))
    img = Image.new('RGB', (size, size), (18, 20, 24))
    layer = Image.new('RGBA', (size, size), (0, 0, 0, 0)); dr = ImageDraw.Draw(layer)
    sub = pts.iloc[::3]
    for x, y in zip(sub['X'].values, sub['Y'].values):
        px, py = proj(x, y); dr.ellipse((px - 2, py - 2, px + 2, py + 2), fill=(120, 130, 150, 28))
    img.paste(layer, (0, 0), layer)
    font = _font(13)
    d2 = ImageDraw.Draw(img)
    for place, g in pts.groupby('last_place_name'):
        if len(g) < 200 or not place: continue
        px, py = proj(g['X'].median(), g['Y'].median())
        d2.text((px, py), str(place), fill=(170, 175, 185), font=font, anchor='mm')
    return {'upper': img, 'lower': None}, proj, None

def _font(sz):
    for f in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, sz)
    return ImageFont.load_default()

def draw_card(base, proj, m):
    img = base.copy(); d = ImageDraw.Draw(img); font = _font(15); small = _font(12)
    # killer and nearest-teammate paths, last 12 s, fading toward the death tick
    for key, col in (('killer_path', (255, 170, 60)), ('mate_path', (80, 140, 255))):
        pp = m.get(key) or []
        if len(pp) > 1:
            pts = [proj(*p) for p in pp]
            for i in range(1, len(pts)):
                f = 0.25 + 0.75 * i / len(pts)
                d.line([pts[i - 1], pts[i]], fill=tuple(int(c * f) for c in col), width=3)
            sx, sy = pts[0]; d.ellipse((sx - 3, sy - 3, sx + 3, sy + 3), outline=col, width=1)
    # path
    if len(m['path']) > 1:
        pts = [proj(*p) for p in m['path']]
        for i in range(1, len(pts)):
            a = int(60 + 195 * i / len(pts))
            d.line([pts[i - 1], pts[i]], fill=(a, 60, 60), width=3)
    for w, p in m['nades_thrown']:
        px, py = proj(*p); col = {'flashbang': (250, 240, 120), 'smokegrenade': (200, 200, 200), 'hegrenade': (240, 140, 60), 'molotov': (255, 90, 30), 'incgrenade': (255, 90, 30)}.get(w, (200, 200, 200))
        d.ellipse((px - 5, py - 5, px + 5, py + 5), outline=col, width=2)
    if m.get('near'):
        px, py = proj(*m['near'][2]); mx, my = proj(*m['pos'])
        d.line([(px, py), (mx, my)], fill=(80, 140, 255), width=1)
        d.ellipse((px - 7, py - 7, px + 7, py + 7), fill=(80, 140, 255))
        d.text((px + 10, py - 8), f"{m['near'][1]} {m['near'][0]:.0f}m", fill=(150, 190, 255), font=small)
    if m.get('kpos') and m['kpos'][0] is not None and not (isinstance(m['kpos'][0], float) and math.isnan(m['kpos'][0])):
        kx, ky = proj(*m['kpos']); mx, my = proj(*m['pos'])
        d.line([(kx, ky), (mx, my)], fill=(255, 170, 60), width=1)
        d.polygon([(kx, ky - 9), (kx - 8, ky + 6), (kx + 8, ky + 6)], fill=(255, 170, 60))
        d.text((kx + 10, ky - 8), f"{m['killer']}", fill=(255, 200, 120), font=small)
    if m.get('extra_pos'):
        ex, ey = proj(*m['extra_pos']); d.ellipse((ex - 6, ey - 6, ex + 6, ey + 6), outline=(120, 255, 120), width=2); d.text((ex + 9, ey - 8), m.get('extra_label', 'your kill'), fill=(140, 255, 140), font=small)
    mx, my = proj(*m['pos'])
    d.line([(mx - 9, my - 9), (mx + 9, my + 9)], fill=(255, 60, 60), width=4); d.line([(mx - 9, my + 9), (mx + 9, my - 9)], fill=(255, 60, 60), width=4)
    d.text((mx + 12, my + 4), "you", fill=(255, 120, 120), font=small)
    title = f"R{m['round']} {m['side']} {m['time']}s  |  {RULES[m['kind']][0]}"
    sc = m.get('severity', 0); col = sev_rgb(sc)
    d.rectangle((0, 0, img.width, 28), fill=tuple(int(c * 0.55) for c in col)); d.rectangle((0, 0, 8, 28), fill=col)
    label = f"impact {m['impact']:+d}" if 'impact' in m else f"severity {sc}"
    d.text((16, 6), f"{title}   {label}", fill=(255, 255, 255), font=font)
    d.text((10, img.height - 22), "red X you   orange killer   blue nearest teammate   trails = last 12 s, small ring = start   rings your grenades", fill=(140, 140, 150), font=small)
    return img

def b64(img):
    buf = BytesIO(); img.convert('RGB').save(buf, format='PNG', optimize=True); return base64.b64encode(buf.getvalue()).decode()

# ----------------------------------------------------------------------------- report
def report(D, mistakes, out_path, demo_name):
    bases, proj, zthr = make_map(D)
    order = ['separated_from_team', 'held_alone', 'util_unused', 'util_too_early', 'team_flash_death', 'team_flash', 'team_util_damage', 'spray_at_range', 'missed_at_range', 'kill_then_die', 'early_solo_contact', 'lost_opener_ct', 'died_blind', 'eco_wander', 'util_on_timer', 'zero_impact_full_buy']
    for m in mistakes:
        m['severity'], m['sev_breakdown'] = severity(m)
    counts = C.Counter(m['kind'] for m in mistakes)
    totsev = {k: sum(m['severity'] for m in mistakes if m['kind'] == k) for k in counts}
    avgsev = {k: round(totsev[k] / counts[k]) for k in counts}
    order = sorted(counts, key=lambda k: -totsev[k])   # categories by cumulative severity, highest first
    name = D['snap'][D['snap']['steamid'] == D['me']]['name'].iloc[0] if (D['snap']['steamid'] == D['me']).any() else D['me']
    h = [f"<!doctype html><html><head><meta charset='utf-8'><title>Mistake report {D['map']}</title><style>"
         "body{font-family:Segoe UI,Arial,sans-serif;background:#111318;color:#e6e6e6;margin:0;padding:24px;max-width:1500px}"
         "h1{font-size:22px;margin:0 0 4px}h2{font-size:18px;margin:36px 0 8px;border-bottom:1px solid #333;padding-bottom:6px}"
         ".sum{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}.chip{background:#1d2130;border:1px solid #333;border-radius:8px;padding:8px 12px}"
         ".chip b{font-size:20px;display:block}.why{background:#1a1d26;border-left:4px solid #e0a040;padding:10px 14px;margin:6px 0 14px;font-size:14px}"
         ".card{display:grid;grid-template-columns:560px 1fr;gap:18px;background:#171a22;border:1px solid #2a2e3a;border-radius:10px;padding:14px;margin:12px 0}"
         ".card img{width:560px;height:560px;border-radius:6px}.facts{font-size:14px;line-height:1.5}.facts .k{color:#e0a040;font-weight:600}.facts .f{color:#8fd18f;font-weight:600}"
         ".lost{color:#ff7a7a}.won{color:#8fd18f}small{color:#999}"
         ".sev{display:inline-block;color:#fff;font-weight:700;padding:4px 10px;border-radius:6px;margin-bottom:6px}.sevbr{font-size:12px;color:#aaa;margin-bottom:10px}</style></head><body>",
         f"<h1>Mistake report: {name} on {D['map']}</h1><small>{demo_name}. {len(mistakes)} flags over {len(D['fz'])} rounds. Rules are heuristics; each card shows the data so you can judge it.</small>",
         "<div class='sum'>"]
    for k in order:
        if counts[k]: h.append(f"<div class='chip' style='border-left:6px solid {sev_css(avgsev[k])}'><b>{counts[k]}</b>{RULES[k][0]}<br><small>avg severity {avgsev[k]}</small></div>")
    h.append("</div>")
    grouped = {}
    for m in sorted(mistakes, key=lambda m: -m['severity']):
        key = (m['round'], m['time']); g = grouped.setdefault(key, dict(sev=m['severity'], m=m, kinds=[]))
        g['kinds'].append(RULES[m['kind']][0])
    top = sorted(grouped.values(), key=lambda g: -g['sev'])[:6]
    h.append("<h2>Most severe deaths</h2><ol>" + ''.join(f"<li><span style='color:{sev_css(g['sev'])};font-weight:700'>{g['sev']}</span> &nbsp; R{g['m']['round']} {g['m']['side']} {g['m']['time']}s at {g['m']['place']}: {'; '.join(g['kinds'])}</li>" for g in top) + "</ol>")
    for k in order:
        ms = sorted([m for m in mistakes if m['kind'] == k], key=lambda m: (-m['severity'], m['round'], m['time'] or 0))
        if not ms: continue
        title, why, fix = RULES[k]
        h.append(f"<h2>{title} ({len(ms)})</h2><div class='why'><b>Why it matters:</b> {why}<br><b>Do instead:</b> {fix}</div>")
        for m in ms:
            lower = bases['lower'] is not None and zthr is not None and m.get('z') is not None and m['z'] < zthr
            img = draw_card(bases['lower'] if lower else bases['upper'], proj, m)
            res = '' if m['won'] is None else (f"<span class='won'>Round won</span>" if m['won'] else f"<span class='lost'>Round lost</span>")
            sc = m['severity']; css = sev_css(sc)
            h.append(f"<div class='card' style='border-left:8px solid {css}'><img src='data:image/png;base64,{b64(img)}'><div class='facts'><div class='sev' style='background:{css}'>Severity {sc} / 100</div><div class='sevbr'>{' &middot; '.join(m['sev_breakdown'])}</div><div class='k'>What happened</div>{m['facts']}<br>{res}"
                     f"<div class='k' style='margin-top:12px'>Why it is a mistake</div>{why}<div class='f' style='margin-top:12px'>What to do instead</div>{fix}</div></div>")
    h.append("</body></html>")
    open(out_path, 'w', encoding='utf-8').write('\n'.join(h))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('demo'); ap.add_argument('--player', default='76561198063294402'); ap.add_argument('--out', default=None)
    a = ap.parse_args()
    out = a.out or os.path.splitext(os.path.basename(a.demo))[0] + '_mistakes.html'
    D = parse(a.demo, a.player)
    mistakes = detect(D)
    report(D, mistakes, out, os.path.basename(a.demo))
    print(f"{D['map']}: {len(mistakes)} flags -> {out}")
    for k, n in C.Counter(m['kind'] for m in mistakes).most_common(): print(f"  {RULES[k][0]}: {n}")

if __name__ == '__main__':
    main()
