"""The demo parser, the radar background, and the mistake side of the flags (thin wrappers over the flags package).

parse(path, me) reads a CS2 demo once into a dict of tables that every flag and the page builder share; make_map() builds the radar
background (from maps/ when the map is known, else a silhouette from the demo). detect() and severity() run and score the mistake flags.
Requires: pip install -r requirements.txt
"""
from __future__ import annotations
from typing import Any
from report_types import Card, Demo, ProgressFn, Proj, Rules, Scored, XY
import sys, os, json, base64
from io import BytesIO
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from demoparser2 import DemoParser
from constants import TICK
from demolib import nade_flight, for_player      # for_player and nade_flight are re-exported for the page builder

PROGRESS: ProgressFn = lambda pct, msg: None   # set by the caller to receive (percent, message)

# ----------------------------------------------------------------------------- parsing
def parse(path: str, me: str, attempts: int = 3) -> Demo:
    """demoparser2 occasionally fails at random on some demos (a race in its threads: a spurious EntityNotFound, or a crash of
    the whole process). A Python-level failure is retried here; a crash is retried by the process runner in cs2report."""
    last: Exception | None = None
    for i in range(attempts):
        try: return _parse(path, me)
        except Exception as e:
            last = e
            if 'demoparser' not in (type(e).__module__ or '').lower() and 'DemoParser' not in type(e).__qualname__ and 'DemoParser' not in str(e): raise
            print(f"demo parser failed ({e}); retrying ({i + 2} of {attempts})", file=sys.stderr, flush=True)
    raise last if last is not None else RuntimeError('the demo could not be parsed')


def _parse(path: str, me: str) -> Demo:
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
               'entityid', 'winner', 'reason', 'site', 'silenced', 'inaccuracy', 'spread', 'recoil_index', 'player_inair']
    def ev(name: str, **kw: Any) -> pd.DataFrame:
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
    # a dead player's spectator camera keeps "seeing": their id turns up in other players' approximate_spotted_by lists and their own
    # spotted flag goes stale. Drop dead players from every spotted-by list and clear spotted on dead rows.
    alive_sets = {int(t_): set(g_.loc[g_['is_alive'] == True, 'steamid'].astype(str)) for t_, g_ in snap.groupby('tick')}
    ticks_ = snap['tick'].to_numpy(); lists_ = snap['approximate_spotted_by'].tolist(); cleaned = []
    for t_, v_ in zip(ticks_, lists_):
        try: cleaned.append([x for x in v_ if str(x) in alive_sets.get(int(t_), ())])
        except TypeError: cleaned.append(v_)
    snap['approximate_spotted_by'] = cleaned
    snap.loc[snap['is_alive'] == False, 'spotted'] = False
    # a dead player spectating a teammate still receives player_blind events (the camera they watch gets flashed): drop those
    if len(blind):
        c0 = int(coarse[0]) if len(coarse) else 0
        alive_at = {(int(t_), str(s_)): bool(a_) for t_, s_, a_ in zip(snap['tick'], snap['steamid'].astype(str), snap['is_alive'])}
        keep = []
        for t_, s_ in zip(blind['tick'], blind['user_steamid'].astype(str)):
            ct_ = int(t_) - ((int(t_) - c0) % 8)
            keep.append(alive_at.get((ct_, s_), alive_at.get((int(t_), s_), True)))
        blind = blind[keep].copy()
    for df_ in (deaths, hurt, blind):
        for c_ in [c for c in df_.columns if c.endswith('team_num')]: df_[c_] = df_[c_].fillna(0)
    PROGRESS(30, 'positions read')
    snap['steamid'] = snap['steamid'].astype(str)
    round_end = {int(r.total_rounds_played) - 1: int(r.tick) for r in rend.itertuples()}
    round_reason = {int(r.total_rounds_played) - 1: str(r.reason) for r in rend.itertuples()}   # t_killed, ct_killed, bomb_exploded, bomb_defused, target_saved (time ran out) ...
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
    bullets = ev("fire_bullets")     # one row per bullet as the game fired it: inaccuracy, spread, recoil_index, player_inair
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
    return dict(bullets=bullets, reloads=reloads, defuse_begin=defuse_begin, defused=defused, plant_begin=plant_begin, bomb_drop=bomb_drop, bomb_pick=bomb_pick, pickups=pickups, exploded=exploded, xt=xt,
                map=mapname, fz=fz, winner=winner, round_end=round_end, round_reason=round_reason, deaths=deaths, hurt=hurt, gunfire=gunfire, nades=nades, all_nades=all_nades, blind=blind, plant=plant, snap=snap, me=me, proj=proj, deton=deton, fx=fx)


# ----------------------------------------------------------------------------- mistakes: every flag lives in its own file under flags/
import flags

RULES: Rules = flags.rules('mistake')               # {kind: (title, why, what to do)}


def detect(D: Demo) -> list[Card]:
    """Every mistake flag for the player D['me']."""
    return flags.detect(D, 'mistake')


def severity(m: Card) -> Scored:
    """0-100. Base weight for the mistake type, then context modifiers. Returns (score, breakdown list)."""
    return flags.score(m)


def sev_rgb(score: float) -> tuple[int, ...]:
    a = (60, 64, 78); b = (225, 55, 55); f = max(0.0, min(1.0, score / 100.0))
    return tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3))

def sev_css(score: float) -> str:
    r, g, b = sev_rgb(score); return f"rgb({r},{g},{b})"

# ----------------------------------------------------------------------------- drawing
def make_map(D: Demo, size: int = 900) -> tuple[dict[str, Any], Proj, float | None]:
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
        def proj(x: float, y: float) -> XY:
            if x != x or y != y: return (-9999, -9999)      # missing position: draw far off the canvas rather than fail
            return (int((x - o['pos_x']) / o['scale'] * k), int((o['pos_y'] - y) / o['scale'] * k))
        def load(fn: str) -> Image.Image:
            im = Image.open(fn).convert('RGB').resize((size, size), Image.Resampling.LANCZOS)
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
    def proj(x: float, y: float) -> XY:  # type: ignore[no-redef]  # the radar-image branch above has returned
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

def _font(sz: int) -> Any:
    for f in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, sz)
    return ImageFont.load_default()


def b64(img: Image.Image) -> str:
    buf = BytesIO(); img.convert('RGB').save(buf, format='PNG', optimize=True); return base64.b64encode(buf.getvalue()).decode()
