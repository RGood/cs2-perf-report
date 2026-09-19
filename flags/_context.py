"""The context object handed to every flag's detect(c).

One Ctx exists per analysed player. It wraps the parsed demo dict D (see mistake_report.parse) and gives the flags:

    lookups      c.row(tick, sid), c.x(tick, sid), c.sees(row, sid), c.speed(tick, sid), c.first_seen(seer, seen, t_end)
    round data   c.rounds() -> [Round]: team, side, deaths, my kills, my damage, my shots, mates, foes ...
    death data   c.deaths_in_depth() and c.death_sightlines(): the analyses several death flags share, computed once
    card makers  c.card(...) for a plain card, Round.play(...) and DeathInDepth.card(...) for the richer ones

Anything two or more flags need belongs here, computed once and cached; anything only one flag needs belongs in that flag's file.
Everything reads exact demo data: events and sampled tick properties. Nothing here estimates.
"""
from __future__ import annotations
from typing import Any
from report_types import ByTick, Card, Demo, EventRow, FlashTurn, NearMate, Row, TickTable, XY
import math
from types import SimpleNamespace
import numpy as np, pandas as pd
from constants import TICK, M, CONT_GAP, SPRAY_RUN, SAFE_WINDOW, SHARED_FIGHT_S, SHARED_FIGHT_M
from demolib import by_tick_of, ticktab_of, nade_flight, nade_list, teammate_fights, teammate_engagements, speed_at


# ----------------------------------------------------------------------------- small geometry helpers
def ang(a: float, b: float) -> float:
    """Absolute difference between two angles in degrees, 0 to 180."""
    return abs((a - b + 180) % 360 - 180)


def bearing(frm: XY, to: XY) -> float:
    """Direction in degrees from one (x, y) to another, comparable with a player's yaw."""
    return math.degrees(math.atan2(to[1] - frm[1], to[0] - frm[0]))


def dist_m(a: XY, b: XY) -> float:
    """Distance between two (x, y) points in metres."""
    return math.dist(a, b) * M


def spotters(row: Row) -> set[str]:
    """The set of steamids that have this player's row in view (approximate_spotted_by); empty when the field is missing."""
    try: return set(str(x) for x in row['approximate_spotted_by'])
    except TypeError: return set()


# ----------------------------------------------------------------------------- the context
class Ctx:
    """Everything the flags share for one player: caches, lookups, per-round and per-death context."""
    D: Demo; me: str; by_tick: ByTick; tab: TickTable; ticks: list[int]; first_tick: int
    fz: dict[int, int]                  # round number (0-based) -> freeze-end tick
    rend: dict[int, int]                # round number -> round-end tick
    deaths: pd.DataFrame; hurt: pd.DataFrame; fire: pd.DataFrame; snap: pd.DataFrame; blind: pd.DataFrame; plant: pd.DataFrame
    nades: pd.DataFrame; deton: pd.DataFrame; fx: pd.DataFrame; mine: pd.DataFrame
    names: dict[str, str]               # steamid -> player name

    @classmethod
    def of(cls, D: Demo) -> Ctx:
        """The context for D['me'], built once per player and reused by every flag on both sides."""
        c = D.get('_ctx')
        if c is None or c.me != str(D['me']): c = D['_ctx'] = cls(D)
        return c

    def __init__(self, D: Demo) -> None:
        self.D = D; self.me = str(D['me']); self.by_tick = by_tick_of(D); self.tab = ticktab_of(D)
        if '_coarse_ticks' not in D: D['_coarse_ticks'] = sorted(self.by_tick)
        self.ticks = D['_coarse_ticks']; self.first_tick = int(self.ticks[0])
        self.fz = D['fz']; self.deaths = D['deaths']; self.hurt = D['hurt']; self.fire = D['gunfire']; self.snap = D['snap']
        self.blind = D['blind']; self.plant = D['plant']; self.nades = D['nades']; self.deton = D['deton']; self.fx = D['fx']
        self.rend = D.get('round_end', {}) or {}
        self.xt = D.get('xt'); self.xti = {}
        if self.xt is not None and len(self.xt):
            for r in self.xt.itertuples(): self.xti[(int(r.tick), str(r.steamid))] = r
        self._pos: dict[int, dict[str, int]] = {}; self._cache: dict[Any, Any] = {}
        self.mine = self.snap[self.snap['steamid'] == self.me].set_index('tick')
        self.names = {str(r.steamid): str(r.name) for r in self.snap[['steamid', 'name']].drop_duplicates('steamid').itertuples()}

    # ---- time
    def rt(self, tick: int, rn: int) -> float:
        """Round time in seconds (from freeze end) of a tick in round rn. The round must have a freeze end: every Round from rounds() does."""
        return round((tick - self.fz[rn]) / TICK, 1)

    def rt_or_none(self, tick: int, rn: int) -> float | None:
        """rt() for a round number straight from an event, which may have no freeze end (warm-up, knife round): None then."""
        return self.rt(tick, rn) if rn in self.fz else None

    def end_of(self, rn: int) -> int:
        return int(self.rend.get(rn, self.fz.get(rn + 1, int(self.snap['tick'].max()))))

    def coarse(self, tk: int) -> int:
        """The sampled tick at or before tk. Positions are sampled every 8 ticks, plus the exact ticks of deaths, throws and freeze ends."""
        c = tk - ((tk - self.first_tick) % 8)
        return c if c in self.by_tick else max([x for x in self.ticks if x <= tk], default=self.first_tick)

    def on_grid(self, tk: int) -> int | None:
        """tk snapped down to the 8-tick grid, or None when that tick was not sampled."""
        c = tk - ((tk - self.first_tick) % 8)
        return c if c in self.by_tick else None

    # ---- rows
    def row(self, tick: int, sid: str | None) -> Row | None:
        """One player's snapshot row at a tick (the exact tick when sampled, else the sample before it); None if absent."""
        tk = tick if tick in self.by_tick else self.coarse(tick)
        g = self.by_tick.get(tk)
        if g is None: return None
        idx = self._pos.get(tk)
        if idx is None: idx = self._pos[tk] = dict(zip(g['steamid'].astype(str), range(len(g))))
        i = idx.get(str(sid))
        return g.iloc[i] if i is not None else None

    def x(self, tick: int, sid: str) -> Any:
        """Extra tick props (ducking, is_airborne, ammo, is_scoped, has_defuser, has_helmet, balance ...) sampled at this exact tick, else None."""
        return self.xti.get((int(tick), str(sid)))

    def team(self, rn: int) -> int | None:
        """My team number (2 = T, 3 = CT) at the freeze end of round rn; None when not on a team."""
        r = self.row(self.fz[rn], self.me)
        if r is None or not (r['team_num'] == r['team_num']): return None
        t = int(r['team_num']); return t if t in (2, 3) else None

    def sees(self, r: Row, sid: str) -> bool:
        """Did player sid have the player of row r in view?"""
        try: return str(sid) in [str(x) for x in r['approximate_spotted_by']]
        except TypeError: return False

    def speed(self, c: int, sid: str) -> float:
        """Horizontal speed in units/s from the position change over the previous sample (the demo's velocity field is unusable)."""
        return speed_at(self.tab, c, sid)

    def me_and_foes(self, t: int, team: int) -> tuple[int | None, Any]:
        """From the compact table at tick t: my index and a mask of alive enemies. (None, None) when I am not in it."""
        r = self.tab.get(t)
        if r is None: return None, None
        idx = np.where(r['sid'] == self.me)[0]
        if not len(idx): return None, None
        return int(idx[0]), (r['team'] != team) & r['alive']

    def alive_counts(self, tick: int, team: int) -> tuple[int | None, int | None]:
        """(my team alive, enemies alive) at a tick."""
        t = self.tab.get(self.coarse(tick))
        if t is None: return None, None
        return int(((t['team'] == team) & t['alive']).sum()), int(((t['team'] != team) & (t['team'] > 1) & t['alive']).sum())

    def nearest_mate(self, tick: int, team: int) -> NearMate | None:
        """(metres, name, (x, y)) of my nearest living teammate at a tick; None when there is none."""
        t = self.tab.get(self.coarse(tick))
        if t is None: return None
        i = np.where(t['sid'] == self.me)[0]
        if not len(i): return None
        i = i[0]; mask = (t['team'] == team) & t['alive'] & (t['sid'] != self.me)
        if not mask.any(): return None
        d = np.hypot(t['X'][mask] - t['X'][i], t['Y'][mask] - t['Y'][i]) * M
        j = int(np.argmin(d)); return float(d[j]), str(t['name'][mask][j]), (float(t['X'][mask][j]), float(t['Y'][mask][j]))

    def first_seen(self, sid_seer: str, sid_seen: str, t_end: int, back_s: float = 6.0) -> int | None:
        """First sample in [t_end - back_s, t_end] at which sid_seer had sid_seen in view, after a sample where they had not. None if never."""
        key = ('first_seen', str(sid_seer), str(sid_seen), int(t_end), back_s)
        if key in self._cache: return self._cache[key]
        prev = False; found = None; out = None
        for ct in range(self.coarse(t_end - int(back_s * TICK)), t_end + 1, 8):
            r = self.row(ct, sid_seen)
            if r is None: continue
            now = self.sees(r, sid_seer)
            if now and not prev: found = ct
            if now and found is not None: out = found; break
            prev = now
        else:
            out = found
        self._cache[key] = out
        return out

    def my_path(self, t: int, upto: int = 0) -> list[XY]:
        """My positions over the 12 s before tick t (through t + upto)."""
        return [(r.X, r.Y) for r in self.mine[(self.mine.index >= t - 12 * TICK) & (self.mine.index <= t + upto)].itertuples()]

    def path_of(self, sid: str | None, t: int) -> list[XY]:
        """A living player's positions over the 12 s up to tick t."""
        q = self.snap[(self.snap['steamid'] == str(sid)) & (self.snap['tick'] >= t - 12 * TICK) & (self.snap['tick'] <= t) & (self.snap['is_alive'] == True)].sort_values('tick')
        return [(r.X, r.Y) for r in q.itertuples()]

    def loss_bonus(self, rn: int) -> int:
        """The loss bonus my team would be paid for losing round rn: 1400 plus 500 per consecutive loss before it, capped at 3400."""
        streak = 0
        for r_ in range(rn - 1, -1, -1):
            tm_ = self.team(r_) if r_ in self.fz else None
            if tm_ is not None and self.D['winner'].get(r_) is not None and self.D['winner'].get(r_) != ('CT' if tm_ == 3 else 'T'): streak += 1
            else: break
        return min(3400, 1400 + 500 * streak)

    # ---- cards
    def card(self, rn: int, side: str, t: int, place: str | None, pos: XY | None, **kw: Any) -> Card:
        """A plain card: round, side, result, round time, place and position, plus whatever the flag adds (facts=..., killer=..., extra_pos=...)."""
        d = dict(round=rn + 1, side=side, won=self.D['winner'].get(rn) == side, time=self.rt(t, rn), z=None, place=place, pos=pos, near=None, path=[], mate_path=[],
                 killer_path=[], victim_path=[], mates_alive=None, foes_alive=None, nades_thrown=[], order=None, dmg_round=None, equip=None, killer=None, kpos=None,
                 kplace=None, weapon=None, my_weapon=None, dist=0)
        d.update(kw); return d

    def position_card(self, rn: int, side: str, won: bool, t: int, place: str | None, pos: XY) -> Card:
        """The card the positioning flags use (no killer fields unless the flag adds them)."""
        return dict(round=rn + 1, side=side, won=won, time=self.rt(t, rn), z=None, place=place, pos=pos, near=None, path=[], mate_path=[], killer_path=[], victim_path=[],
                    mates_alive=None, foes_alive=None, nades_thrown=[], order=None, dmg_round=None, equip=None)

    # ---- shared analyses
    def rounds(self) -> list[Round]:
        """Every round I played on a team, in order, as Round objects (built once)."""
        if 'rounds' not in self._cache:
            out = []
            for rn in sorted(self.fz):
                team = self.team(rn)
                if team is not None: out.append(Round(self, rn, team))
            self._cache['rounds'] = out
        return self._cache['rounds']

    def deaths_in_depth(self) -> list[DeathInDepth]:
        """Each of my deaths with the full analysis the original death flags share (see DeathInDepth)."""
        if 'depth' not in self._cache:
            out = []
            for d in self.deaths[self.deaths['user_steamid'] == self.me].itertuples():
                a = _death_in_depth(self, d)
                if a is not None: out.append(a)
            self._cache['depth'] = out
        return self._cache['depth']

    def death_sightlines(self) -> list[SimpleNamespace]:
        """Each of my deaths to another player with who saw whom over the last 3 s (see _death_sightline)."""
        if 'sight' not in self._cache:
            out = []
            for d in self.deaths[self.deaths['user_steamid'] == self.me].itertuples():
                s = _death_sightline(self, d)
                if s is not None: out.append(s)
            self._cache['sight'] = out
        return self._cache['sight']

    def attention(self, killer: str, trader: str, t_death: int, t_trade: int, kname: str, tname: str, victim_word: str) -> tuple[dict[str, Any], str]:
        """Did the victim hold the killer's attention for the trade? The measure is the angle between the killer's view direction and the
        trader at the trader's first shot aimed within 15 degrees of the killer. A large angle means the trader had a free shot at a killer
        still looking elsewhere; a small one means the killer was already set on them. Returns (fields for the card, sentence for the facts)."""
        killer, trader = str(killer), str(trader); by_tick = self.by_tick
        def off(tick: int) -> float | None:
            g = by_tick.get(tick) if tick in by_tick else by_tick.get(self.coarse(tick))
            if g is None: return None
            kr = g[g['steamid'] == killer]; tr = g[g['steamid'] == trader]
            if not len(kr) or not len(tr) or not (kr.iloc[0]['yaw'] == kr.iloc[0]['yaw']): return None
            b = math.degrees(math.atan2(tr.iloc[0].Y - kr.iloc[0].Y, tr.iloc[0].X - kr.iloc[0].X))
            return ang(b, float(kr.iloc[0]['yaw']))
        t_spot = None
        gf = self.fire; shots = gf[(gf['user_steamid'] == trader) & (gf['tick'] >= t_death - 3 * TICK) & (gf['tick'] <= t_trade)].sort_values('tick')
        for s_ in shots.itertuples():
            if not (s_.user_yaw == s_.user_yaw): continue
            g = by_tick.get(self.coarse(int(s_.tick)))
            if g is None: continue
            kr = g[g['steamid'] == killer]
            if not len(kr): continue
            b = math.degrees(math.atan2(kr.iloc[0].Y - s_.user_Y, kr.iloc[0].X - s_.user_X))
            if ang(b, float(s_.user_yaw)) < 15: t_spot = int(s_.tick); break
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


# ----------------------------------------------------------------------------- one round
class Round:
    """One round from my side.

    rn, team (2 T / 3 CT), side ('T'/'CT'), ft (freeze-end tick), end (round-end tick), won
    g0            the snapshot of all players at freeze end
    mates, foes   steamid sets of my teammates (without me) and of the enemy team
    rd            deaths this round from freeze end on, by tick;  my_deaths / my_kills: the rows where I died / killed
    rh, rf        damage I dealt and shots I fired this round
    all_*         the same tables without the freeze-end filter, as the original play flags read them
    """
    c: Ctx; rn: int; team: int; side: str; ft: int; end: int; won: bool
    g0: pd.DataFrame | None; me0: Row             # me0: my row at freeze end (always present: the round exists because I was on a team then)
    mates: set[str]; foes: set[str]; not_my_team: set[str]
    rd: pd.DataFrame; my_deaths: pd.DataFrame; my_kills: pd.DataFrame; rh: pd.DataFrame; rf: pd.DataFrame
    all_deaths: pd.DataFrame; all_my_deaths: pd.DataFrame; all_my_kills: pd.DataFrame
    def __init__(self, c: Ctx, rn: int, team: int) -> None:
        self.c = c; self.rn = rn; self.team = team; self.side = 'CT' if team == 3 else 'T'; me = c.me
        self.ft = c.fz[rn]; self.end = c.end_of(rn); self.won = c.D['winner'].get(rn) == self.side
        deaths = c.deaths; hurt = c.hurt; fire = c.fire
        self.all_deaths = deaths[deaths['total_rounds_played'] == rn].sort_values('tick')
        self.rd = self.all_deaths[self.all_deaths['tick'] >= self.ft]
        self.my_deaths = self.rd[self.rd['user_steamid'] == me]; self.my_kills = self.rd[self.rd['attacker_steamid'] == me]
        self.all_my_kills = self.all_deaths[self.all_deaths['attacker_steamid'] == me]; self.all_my_deaths = self.all_deaths[self.all_deaths['user_steamid'] == me]
        self.rh = hurt[(hurt['total_rounds_played'] == rn) & (hurt['attacker_steamid'] == me)]
        self.rf = fire[(fire['total_rounds_played'] == rn) & (fire['user_steamid'] == me)]
        self.g0 = g0 = c.by_tick.get(self.ft); self.mates = set(); self.foes = set(); self.not_my_team = set()
        if g0 is not None:
            self.mates = set(str(s) for s in g0[(g0['team_num'] == team) & (g0['steamid'] != me)]['steamid'])
            self.foes = set(str(s) for s in g0[(g0['team_num'] != team) & (g0['team_num'] > 1)]['steamid'])
            self.not_my_team = set(g0[g0['team_num'] != team]['steamid'])      # the looser set the original play flags used
        self.me0 = c.row(self.ft, me)
        self._cache: dict[str, Any] = {}

    # ---- values several play flags read
    @property
    def died(self) -> bool: return len(self.all_my_deaths) > 0

    @property
    def death_tick(self) -> int | None: return int(self.all_my_deaths.iloc[0]['tick']) if self.died else None

    @property
    def dmg_to_enemies(self) -> int:
        """My damage this round on players not on my team (each hit capped at 100)."""
        if 'dmg' not in self._cache:
            h = self.rh[self.rh['user_steamid'].isin(self.not_my_team)]
            self._cache['h_en'] = h; self._cache['dmg'] = int(h['dmg_health'].clip(upper=100).sum())
        return self._cache['dmg']

    @property
    def hits_on_enemies(self) -> pd.DataFrame:
        self.dmg_to_enemies; return self._cache['h_en']

    @property
    def equip0(self) -> int:
        """My equipment value at freeze end."""
        return int(self.me0['current_equip_value'])

    @property
    def plant_tick(self) -> int | None:
        pl = self.c.plant
        return int(pl[pl['total_rounds_played'] == self.rn]['tick'].min()) if (pl['total_rounds_played'] == self.rn).any() else None

    @property
    def first_contact_tick(self) -> int | None:
        """First tick from freeze end (every 16) at which my team had an enemy spotted; None if never."""
        if 'contact' not in self._cache:
            out = None
            for ct in range(self.ft, self.end, 16):
                g = self.c.by_tick.get(ct)
                if g is None: continue
                if ((g['team_num'] != self.team) & (g['is_alive'] == True) & (g['spotted'] == True)).any(): out = ct; break
            self._cache['contact'] = out
        return self._cache['contact']

    def state(self, t: int) -> tuple[int | None, int | None, list[tuple[Any, ...]], XY | None]:
        """(teammates alive, enemies alive, teammates by distance [(m, name, (x, y), place, sid)], my position) at tick t."""
        c = self.c; g = c.by_tick.get(c.coarse(t))
        if g is None: return None, None, [], None
        mr = g[g['steamid'] == c.me]
        mates = g[(g['team_num'] == self.team) & (g['steamid'] != c.me) & (g['is_alive'] == True)]
        foes = g[(g['team_num'] != self.team) & (g['is_alive'] == True)]
        mp = (mr.iloc[0].X, mr.iloc[0].Y) if len(mr) else None
        md = sorted([(math.dist(mp, (x.X, x.Y)) * M, x.name, (x.X, x.Y), x.last_place_name, x.steamid) for x in mates.itertuples()]) if mp else []
        return len(mates), len(foes), md, mp

    def play(self, t: int, pos: XY | None, victim: str | None = None, vpos: XY | None = None, facts: str = '', **extra: Any) -> Card | None:
        """A rich play card at tick t: my path, the victim's path, the nearest teammate, players alive, my grenades so far.
        Returns None for pre-round artefacts (pauses, knife rounds)."""
        c = self.c; rn = self.rn
        tsec = c.rt_or_none(t, rn)
        if tsec is None or tsec < 0: return None
        ma, fo, md, mp = self.state(t)
        near = md[0] if md else None
        nd = c.nades
        return dict(round=rn + 1, side=self.side, won=self.won, equip=self.equip0, time=c.rt(t, rn), pos=pos, place=extra.pop('place', None), victim=victim, vpos=vpos,
                    z=extra.pop('z', None), path=c.path_of(c.me, t), victim_path=c.path_of(extra.pop('victim_sid', None), t) if victim else [],
                    mate_path=c.path_of(near[4], t) if near else [], near=near, mates_alive=ma, foes_alive=fo,
                    nades_thrown=[(r.weapon.replace('weapon_', ''), (r.user_X, r.user_Y)) for r in nd[(nd['total_rounds_played'] == rn) & (nd['tick'] <= t)].itertuples()],
                    facts=facts, **extra)

    def teammate_fights(self) -> list[dict[str, Any]]:
        """Each teammate death this round with the fight window, whether I could help, and when I engaged the killer (demolib.teammate_fights)."""
        if 'tf' not in self._cache:
            self._cache['tf'] = teammate_fights(self.c.D, self.c.me, self.c.by_tick, self.c.coarse, self.rn, self.team)
        return self._cache['tf']

    def teammate_engagements(self) -> list[dict[str, Any]]:
        """Windows of damage exchanged between a teammate and an enemy this round (demolib.teammate_engagements)."""
        if 'te' not in self._cache:
            self._cache['te'] = teammate_engagements(self.c.D, self.rn, self.team, self.c.me)
        return self._cache['te']

    def deaths_of_mine(self) -> list[Death]:
        """My deaths this round as Death objects: the light per-death prelude most death flags start from."""
        if 'deaths' not in self._cache:
            out = []
            for d in self.my_deaths.itertuples():
                x = Death(self, d)
                if x.ok: out.append(x)
            self._cache['deaths'] = out
        return self._cache['deaths']

    def kills_of_mine(self) -> list[Kill]:
        """My kills on enemies this round as Kill objects."""
        if 'kills' not in self._cache:
            out = []
            for k in self.my_kills.itertuples():
                x = Kill(self, k)
                if x.ok: out.append(x)
            self._cache['kills'] = out
        return self._cache['kills']

    def flash_turns(self) -> list[FlashTurn]:
        """For each of my flash pops this round: (det_tick, throw_tick, land, [(enemy row at pop, blind_s, dist_m, off_at_throw, off_at_pop), ...]) where
        the enemy was within 25 m of the pop, facing the landing point at the throw (within 60 deg) and facing away from it at the pop (over 100 deg)."""
        if 'turns' in self._cache: return self._cache['turns']
        c = self.c; me = c.me; D = c.D; out = []
        dt = D['deton']; pops = dt[(dt['steamid'] == me) & (dt['kind'] == 'flashbang') & (dt['tick'] >= self.ft) & (dt['tick'] < self.end)] if len(dt) else dt
        nd = D['nades']; throws = nd[(nd['total_rounds_played'] == self.rn) & (nd['weapon'].str.contains('flashbang', na=False))]
        bl = D['blind']
        for p_ in pops.itertuples():
            det = int(p_.tick); land = (float(p_.x), float(p_.y))
            thr_ = throws[(throws['tick'] <= det) & (throws['tick'] >= det - 4 * TICK)]
            if not len(thr_): continue
            thr = int(thr_.iloc[-1]['tick']); g_pop = c.by_tick.get(c.coarse(det)); g_thr = c.by_tick.get(c.coarse(thr))
            if g_pop is None or g_thr is None: continue
            turned = []
            for e in g_pop[(g_pop['team_num'] != self.team) & (g_pop['is_alive'] == True)].itertuples():
                if not (e.X == e.X and e.yaw == e.yaw): continue
                dm = dist_m((float(e.X), float(e.Y)), land)
                if dm > 25: continue
                e0 = g_thr[g_thr['steamid'] == e.steamid]
                if not len(e0) or not (e0.iloc[0]['yaw'] == e0.iloc[0]['yaw']): continue
                off_thr = ang(float(e0.iloc[0]['yaw']), bearing((float(e0.iloc[0].X), float(e0.iloc[0].Y)), land))
                off_pop = ang(float(e.yaw), bearing((float(e.X), float(e.Y)), land))
                if off_thr <= 60 and off_pop >= 100:
                    b_ = bl[(bl['attacker_steamid'] == me) & (bl['user_steamid'] == str(e.steamid)) & ((bl['tick'] - det).abs() <= 2)] if len(bl) else bl
                    blind_s = float(b_['blind_duration'].max()) if len(b_) else 0.0
                    turned.append((e, blind_s, dm, off_thr, off_pop))
            if turned: out.append((det, thr, land, turned))
        self._cache['turns'] = out
        return out


# ----------------------------------------------------------------------------- one death, one kill (the light preludes)
class Death:
    """One of my deaths. d is the player_death row; t its tick; pos / kpos my and the killer's position; killer the killer's steamid
    (by_enemy says whether they were on the other team); place; first_death; nm the nearest teammate (m, name, (x, y)) or None;
    traded; kw the killer fields every death card carries; facts the opening sentence.
    last is my extra tick props (ducking, is_airborne, ammo ...) at the last tick I was alive, t - 1. Never read them at t itself: at the
    death tick the player is already dead, is_airborne reads True for that one tick in about half of all deaths, and the ammo is gone."""
    R: Round; d: EventRow; t: int; ok: bool
    pos: XY; kpos: XY | None; killer: str; by_enemy: bool; place: str; first_death: bool      # killer is '' when the demo names none
    nm: NearMate | None; last: Any; traded: bool; kw: dict[str, Any]; dist: float; facts: str
    def __init__(self, R: Round, d: EventRow) -> None:
        c = R.c; self.R = R; self.d = d; self.t = t = int(d.tick); rd = R.rd
        pos = (float(d.user_X), float(d.user_Y)) if d.user_X == d.user_X else None; tsec = c.rt_or_none(t, R.rn)
        self.ok = not (pos is None or tsec is None or tsec < 0)
        if pos is None or not self.ok: return
        self.pos = pos
        self.killer = killer = str(d.attacker_steamid) if pd.notna(d.attacker_steamid) else ''
        self.by_enemy = killer in R.foes
        self.kpos = (float(d.attacker_X), float(d.attacker_Y)) if d.attacker_X == d.attacker_X else None
        self.place = str(d.user_last_place_name)
        self.first_death = bool(len(rd) and int(rd.iloc[0]['tick']) == t and str(rd.iloc[0]['user_steamid']) == c.me)
        self.nm = c.nearest_mate(t - 1, R.team)
        self.last = c.x(t - 1, c.me)
        self.traded = bool(len(rd[(rd['tick'] > t) & (rd['tick'] <= t + 5 * TICK) & (rd['user_steamid'] == killer) & (rd['attacker_team_num'] == R.team)])) if killer else False
        self.kw = dict(killer=str(d.attacker_name), kpos=self.kpos, weapon=str(d.weapon), my_weapon=str(d.user_active_weapon_name), dist=round(float(d.distance), 1) if pd.notna(d.distance) else 0)
        self.dist = self.kw['dist']
        from ._weapons import wkey
        self.facts = f"Round {R.rn+1}, {R.side}, {c.rt(t, R.rn)} s. Died at {self.place} to {d.attacker_name} ({wkey(d.weapon)}, {self.dist} m)."

    def card(self, more_facts: str = '', **kw: Any) -> Card:
        """A card for this death: the opening sentence plus the flag's own, and the killer fields."""
        R = self.R
        return R.c.card(R.rn, R.side, self.t, self.place, self.pos, facts=self.facts + more_facts, **{**self.kw, **kw})


class Kill:
    """One of my kills on an enemy. k is the player_death row; t its tick; victim the victim's steamid; pos / vpos my and their position;
    place; kw the victim fields every kill card carries; facts the opening sentence."""
    R: Round; k: EventRow; t: int; ok: bool; victim: str
    pos: XY; vpos: XY | None; place: str; kw: dict[str, Any]; facts: str
    def __init__(self, R: Round, k: EventRow) -> None:
        c = R.c; self.R = R; self.k = k; self.t = t = int(k.tick); self.victim = victim = str(k.user_steamid)
        tsec = c.rt_or_none(t, R.rn)
        self.ok = not (victim not in R.foes or not (k.attacker_X == k.attacker_X) or tsec is None or tsec < 0)
        if not self.ok: return
        self.pos = (float(k.attacker_X), float(k.attacker_Y)); self.vpos = (float(k.user_X), float(k.user_Y)) if k.user_X == k.user_X else None
        self.place = str(k.attacker_last_place_name)
        self.kw = dict(victim=str(k.user_name), vpos=self.vpos, victim_sid=victim, weapon=str(k.weapon), dist=round(float(k.distance), 1) if pd.notna(k.distance) else 0)
        from ._weapons import wkey
        self.facts = f"Round {R.rn+1}, {R.side}, {c.rt(t, R.rn)} s. Killed {k.user_name} ({wkey(k.weapon)}, {self.kw['dist']} m) from {self.place}."

    def card(self, more_facts: str = '', **kw: Any) -> Card:
        R = self.R
        return R.c.card(R.rn, R.side, self.t, self.place, self.pos, facts=self.facts + more_facts, **{**self.kw, **kw})


# ----------------------------------------------------------------------------- the in-depth death analysis
class DeathInDepth(SimpleNamespace):
    """One of my deaths with everything the original death flags share. The fields the flags read:

    d, rn, t, tsec, team, side, pos, kpos, K (killer steamid), dist (killer distance, m), equip, order (1 = first death of the round)
    mates (living teammates), near = (m, name, (x, y), place) of the nearest or None, moved10 / mate10 (my movement and the nearest teammate 10 s earlier)
    shared       a teammate died just before me in the same fight: (name, m, seconds earlier, place, why) or None
    mate_los     name of a living teammate who had my killer in view in my last 2 s, or None
    traded       my killer died to my team within 5 s
    dmg_round, dmg_k, shots      my damage and shots over the round up to the death
    shots4, hits4, dmg_any4, dmg_k4, kills4, aimed, aim_range, longest, pattern     the 4 s engagement window
    contact, after, foes_peak, safe_s, best_safe_end     contact (an enemy within 25 m) in the last 15 s and the longest safe throw window after it
    held, usable, throw_info     grenades held at death, those that were usable, and what each of my throws this round did
    base, facts  the card fields and the opening sentence; use card(...)
    """
    d: EventRow; rn: int; t: int; tsec: float; team: int; side: str; pos: XY; kpos: XY | None; K: str; dist: float; equip: int; order: int
    mates: pd.DataFrame; near: tuple[float, str, XY, str] | None; moved10: float | None; mate10: float | None
    shared: tuple[str, float, float, str, str] | None; mate_los: str | None; traded: bool
    dmg_round: int; dmg_k: int; shots: int; shots4: int; hits4: int; dmg_any4: int; dmg_k4: int; kills4: int
    aimed: list[float]; aim_range: float; longest: int; pattern: str
    contact: int | None; after: float; foes_peak: int; safe_s: float; best_safe_end: int | None
    held: list[str]; usable: list[str]; throw_info: list[dict[str, Any]]; base: Card; facts: str
    def card(self, more_facts: str = '', **kw: Any) -> Card:
        return dict(self.base, facts=self.facts + more_facts, **kw)


def _death_in_depth(c: Ctx, d: EventRow) -> DeathInDepth | None:
    D = c.D; me = c.me; by_tick = c.by_tick; deaths = c.deaths; snap = c.snap; mine = c.mine; fz = c.fz; rt = c.rt
    rn = int(d.total_rounds_played); t = int(d.tick); tsec = c.rt_or_none(t, rn)
    if tsec is None or tsec < 0: return None
    s = by_tick.get(t - 1)
    if s is None: return None
    team = int(d.user_team_num); side = 'CT' if team == 3 else 'T'
    if team not in (2, 3): return None
    me_row = s[s['steamid'] == me]
    me_row = me_row.iloc[0] if len(me_row) else None
    mates = s[(s['team_num'] == team) & (s['steamid'] != me) & (s['is_alive'] == True)]
    pos = (d.user_X, d.user_Y); kpos = (d.attacker_X, d.attacker_Y) if pd.notna(d.attacker_X) else None
    md = sorted([(math.dist(pos, (m.X, m.Y)) * M, m.name, (m.X, m.Y), m.last_place_name) for m in mates.itertuples()])
    near = md[0] if md else None
    K = str(d.attacker_steamid)
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
        for ct in range(max(tT - 4 * TICK, c.first_tick), tT + 1, 8):
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
    for ct in range(max(t - 2 * TICK, c.first_tick), t, 8):
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
        ct_ = int(s_.tick) - ((int(s_.tick) - c.first_tick) % 8); gg_ = by_tick.get(ct_)
        if gg_ is None: continue
        best = None
        for f_ in gg_[(gg_['team_num'] != team) & (gg_['is_alive'] == True)].itertuples():
            off_ = abs(((math.degrees(math.atan2(f_.Y - s_.user_Y, f_.X - s_.user_X)) - float(s_.user_yaw) + 180) % 360) - 180)
            if off_ < 12 and (best is None or off_ < best[0]): best = (off_, math.dist((s_.user_X, s_.user_Y), (f_.X, f_.Y)) * M)
        if best: aimed.append(best[1])
    aim_range = float(np.median(aimed)) if aimed else (float(d.distance) if pd.notna(d.distance) else 0)
    tk = sorted(int(v) for v in g4['tick']); runs: list[list[int]] = []
    for shot_tick in tk:
        if runs and shot_tick - runs[-1][-1] <= CONT_GAP: runs[-1].append(shot_tick)
        else: runs.append([shot_tick])
    run_lens = [len(r) for r in runs]; longest = max(run_lens) if run_lens else 0
    pattern = 'no shots' if not run_lens else ('a continuous spray of ' + str(longest) if longest >= SPRAY_RUN else ('bursts of ' + ', '.join(map(str, run_lens)) if longest >= 2 else str(len(run_lens)) + ' single taps'))
    c10 = t - 640; c10 = c10 - ((c10 - c.first_tick) % 8)
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
            being_hit = any(h_ in hurt_me_ticks for h_ in range(ct - 8, ct + 1))
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
        # what the grenade did after landing: did the team use the space it made, did it touch an enemy, or was it a diversion?
        used = False; touched = False; fake = False; fake_d = None; land_ok = False
        fl_ = nade_flight(D, me, int(r.tick), r.weapon) if 'smoke' in r.weapon or 'molotov' in r.weapon or 'inc' in r.weapon else None
        if fl_:
            kind_, _p_, land_, _thr_, det_ = fl_; land_ok = True
            fxr_ = D['fx'][(D['fx']['kind'] == kind_) & ((D['fx']['tick'] - det_).abs() <= 2)]
            end_ = int(fxr_.iloc[0]['end']) if len(fxr_) else det_ + (18 if kind_ == 'smokegrenade' else 7) * TICK
            mate_near15 = False
            for ct_ in range(det_ - ((det_ - c.first_tick) % 8), end_ + 1, 16):
                g_ = by_tick.get(ct_)
                if g_ is None: continue
                for p_ in g_[(g_['is_alive'] == True)].itertuples():
                    dd_ = math.dist((p_.X, p_.Y), land_) * M
                    if int(p_.team_num) == team:
                        if dd_ <= 8: used = True
                        if dd_ <= 15: mate_near15 = True
                    elif dd_ <= 12: touched = True
                if used and touched: break
            # a diversion: the team's first exchange of damage after the throw came well away from it, later, with nobody of ours near it
            hx_ = D['hurt'][(D['hurt']['total_rounds_played'] == rn) & (D['hurt']['tick'] > int(r.tick)) & (D['hurt']['user_X'].notna())]
            g0_ = by_tick.get(fz[rn]); my_ids_ = set(str(x) for x in g0_[g0_['team_num'] == team]['steamid']) if g0_ is not None else set()
            foe_ids_ = set(str(x) for x in g0_[(g0_['team_num'] != team) & (g0_['team_num'] > 1)]['steamid']) if g0_ is not None else set()
            for hh_ in hx_.itertuples():
                a_s = str(hh_.attacker_steamid); u_s = str(hh_.user_steamid)
                if (a_s in my_ids_ and u_s in foe_ids_) or (a_s in foe_ids_ and u_s in my_ids_):
                    fake_d = math.dist((hh_.user_X, hh_.user_Y), land_) * M
                    fake = fake_d >= 40 and (int(hh_.tick) - int(r.tick)) / TICK >= 5 and not mate_near15
                    break
        throw_info.append(dict(t=rt(int(r.tick), rn), nade=r.weapon.replace('weapon_', ''), place=r.user_last_place_name, near=nr, spotted=sp,
                               blind=(nr == 0 and sp == 0), pre=(contact is None or r.tick < contact), used=used, touched=touched, fake=fake, fake_d=fake_d, land_ok=land_ok))
    equip = int(me_row['current_equip_value']) if me_row is not None else 0
    dist = float(d.distance) if pd.notna(d.distance) else 0
    # paths: the last 12 s of me, the killer and the nearest teammate
    pt = mine[(mine.index >= t - 12 * TICK) & (mine.index <= t - 1)]
    path = [(r.X, r.Y) for r in pt.itertuples()]
    def path_of(sid: Any) -> list[XY]:
        if sid is None: return []
        q = snap[(snap['steamid'] == str(sid)) & (snap['tick'] >= t - 12 * TICK) & (snap['tick'] <= t - 1) & (snap['is_alive'] == True)].sort_values('tick')
        return [(r.X, r.Y) for r in q.itertuples()]
    killer_path = path_of(d.attacker_steamid) if pd.notna(d.attacker_steamid) else []
    mate_sid = None
    if md:
        mrow = mates[mates['name'] == md[0][1]]
        mate_sid = mrow.iloc[0]['steamid'] if len(mrow) else None
    mate_path = path_of(mate_sid)
    base = dict(round=rn + 1, side=side, time=tsec, z=float(d.user_Z) if pd.notna(d.user_Z) else None, order=order, dmg_round=dmg_round, equip=equip, after=after, foes_peak=foes_peak, moved10=moved10, n_usable=len(usable), place=d.user_last_place_name, pos=pos, killer=d.attacker_name, kpos=kpos, kplace=d.attacker_last_place_name,
                weapon=d.weapon, my_weapon=d.user_active_weapon_name, dist=round(dist, 1), near=near, path=path, killer_path=killer_path, mate_path=mate_path, mates_alive=len(mates),
                nades_thrown=[(r.weapon.replace('weapon_', ''), (r.user_X, r.user_Y)) for r in thrown.itertuples()], won=D['winner'].get(rn) == side,
                shared_fight=shared, mate_los=mate_los)
    # held grenades that did not count: say why on every card from this death
    if not (usable and tsec > 10) and held and tsec > 10 and contact is not None and after >= 2 and safe_s < SAFE_WINDOW:
        base['util_note'] = f"Held {', '.join(held)} at death, not counted: from contact at {rt(contact, rn)} s the enemy could engage you the whole time (longest safe window {safe_s:.1f} s), so throwing would have been the mistake."
    facts = f"Round {rn+1}, {side}, {tsec}s. Died at {d.user_last_place_name} to {d.attacker_name} ({d.weapon}) from {d.attacker_last_place_name}, {dist:.0f} m."
    if near: facts += f" Nearest teammate {near[1]} was {near[0]:.0f} m away at {near[3]}."
    if shared: facts += f" {shared[0]} had died {shared[2]:.1f} s earlier, {shared[1]:.0f} m from you at {shared[3]} ({shared[4]}): a shared fight, so this is not counted as an isolated death."
    if mate_los and not shared: facts += f" {mate_los} had your killer in view when you died, so a trade was possible from where they were."
    facts += f" In the 4 s before you died you fired {shots4} shots as {pattern}, {hits4} of them hit anyone, for {dmg_any4} damage in total and {dmg_k4} to your killer ({shots} shots, {dmg_k} damage over the whole round)."
    return DeathInDepth(d=d, rn=rn, t=t, tsec=tsec, team=team, side=side, pos=pos, kpos=kpos, K=K, dist=dist, equip=equip, order=order, mates=mates, near=near,
                        moved10=moved10, mate10=mate10, shared=shared, mate_los=mate_los, traded=traded, dmg_round=dmg_round, dmg_k=dmg_k, shots=shots, shots4=shots4,
                        hits4=hits4, dmg_any4=dmg_any4, dmg_k4=dmg_k4, kills4=kills4, aimed=aimed, aim_range=aim_range, longest=longest, pattern=pattern,
                        contact=contact, after=after, foes_peak=foes_peak, safe_s=safe_s, best_safe_end=best_safe_end, held=held, usable=usable,
                        throw_info=throw_info, base=base, facts=facts)


def _death_sightline(c: Ctx, d: EventRow) -> SimpleNamespace | None:
    """One of my deaths to another player, with who saw whom over the last 3 s. Fields: d, rn, t, team, side, won, K, mypos, kpos, base (card), shots
    (mine in the last 4 s), seen_by {enemy sid: first tick they had me in view}, k_saw_me_from, i_saw_k_from, first_mutual = (tick, my row, killer row) or None."""
    me = c.me; fz = c.fz; fire = c.fire; by_tick = c.by_tick
    rn = int(d.total_rounds_played); t = int(d.tick)
    if rn not in fz or t < fz[rn]: return None
    team = int(d.user_team_num); side = 'CT' if team == 3 else 'T'; won = c.D['winner'].get(rn) == side
    if team not in (2, 3): return None
    K = str(d.attacker_steamid)
    if K in ('nan', 'None', '') or K == me: return None
    mypos = (d.user_X, d.user_Y); kpos = (d.attacker_X, d.attacker_Y)
    base = c.position_card(rn, side, won, t, d.user_last_place_name, mypos)
    base.update(path=c.my_path(t), killer=str(d.attacker_name), kpos=kpos, dist=round(float(d.distance), 1) if pd.notna(d.distance) else 0)
    shots = int(((fire['total_rounds_played'] == rn) & (fire['user_steamid'] == me) & (fire['tick'] >= t - 4 * TICK) & (fire['tick'] <= t)).sum())
    seen_by: dict[str, int] = {}; first_mutual = None; k_saw_me_from = None; i_saw_k_from = None
    for ct in range(c.coarse(t - 3 * TICK), t + 1, 8):
        g = by_tick.get(ct)
        if g is None: continue
        mr = g[g['steamid'] == me]; mr = mr.iloc[0] if len(mr) else None
        kr = g[g['steamid'] == K]; kr = kr.iloc[0] if len(kr) else None
        if mr is None: continue
        try:
            for e in mr['approximate_spotted_by']:
                seen_by.setdefault(str(e), ct)
        except TypeError:
            pass
        if kr is not None:
            k_sees = c.sees(mr, K); i_see = c.sees(kr, me)
            if k_sees and k_saw_me_from is None: k_saw_me_from = ct
            if i_see and i_saw_k_from is None: i_saw_k_from = ct
            if k_sees and i_see and first_mutual is None: first_mutual = (ct, mr, kr)
    return SimpleNamespace(d=d, rn=rn, t=t, team=team, side=side, won=won, K=K, mypos=mypos, kpos=kpos, base=base, shots=shots, seen_by=seen_by,
                           k_saw_me_from=k_saw_me_from, i_saw_k_from=i_saw_k_from, first_mutual=first_mutual)
