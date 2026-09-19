"""Weapon names, classes and the few weapon numbers the flags use."""
from __future__ import annotations
from typing import Iterable
import math

RIFLES = ('ak47', 'm4a1', 'm4a4', 'famas', 'galil', 'aug', 'sg556', 'sg553')
SNIPERS = ('awp', 'ssg08', 'scar20', 'g3sg1')
SMGS = ('mp9', 'mp7', 'mac10', 'mp5', 'ump45', 'p90', 'bizon')
PISTOLS = ('glock', 'usp', 'p2000', 'p250', 'fiveseven', 'tec9', 'cz75', 'deagle', 'revolver', 'elite', 'hkp2000')
SHOTGUNS = ('nova', 'xm1014', 'mag7', 'sawedoff')
# kill a helmeted head in one shot at any range; the AUG only up to mid range, so it counts as helmet-relevant
ONE_SHOT_HELMET = ('ak47', 'sg556', 'sg553', 'awp', 'ssg08', 'scar20', 'g3sg1', 'deagle', 'revolver')

# body hits to kill an armoured enemy at close to mid range; a reload is premature when the clip still held about twice that
BTK = {'ak47': 4, 'sg556': 4, 'sg553': 4, 'aug': 4, 'm4a1': 5, 'm4a4': 5, 'm4a1s': 5, 'famas': 5, 'galil': 5, 'galilar': 5, 'awp': 1, 'ssg08': 2, 'scar20': 2, 'g3sg1': 2,
       'deagle': 3, 'revolver': 2, 'usps': 5, 'usp': 5, 'glock': 6, 'p2000': 5, 'hkp2000': 5, 'p250': 4, 'fiveseven': 5, 'tec9': 5, 'cz75auto': 5, 'elite': 5,
       'mp9': 6, 'mp7': 6, 'mac10': 6, 'mp5sd': 6, 'ump45': 5, 'p90': 6, 'bizon': 7, 'ppbizon': 7, 'nova': 2, 'xm1014': 3, 'mag7': 2, 'sawedoff': 2, 'negev': 5, 'm249': 5}
HIT_RATE = 0.5      # a typical share of shots that land in a duel; shots needed = hits needed / HIT_RATE


def norm(name: str | None) -> str:
    """Weapon name in one form whether it came from an event ('m4a1_silencer', 'deagle') or an inventory ('M4A1-S', 'Desert Eagle')."""
    n = (name or '').lower().replace('weapon_', '').replace('-', '').replace(' ', '').replace('_', '')
    return {'deserteagle': 'deagle', 'r8revolver': 'revolver', 'dualberettas': 'elite', 'm4a1silencer': 'm4a1s', 'uspsilencer': 'usps', 'cz75a': 'cz75auto'}.get(n, n)


def wclass(name: str | None) -> str:
    """'sniper', 'rifle', 'smg', 'shotgun', 'pistol' or 'other'."""
    n = norm(name)
    for cls, keys in (('sniper', SNIPERS), ('rifle', RIFLES), ('smg', SMGS), ('shotgun', SHOTGUNS), ('pistol', PISTOLS)):
        if any(k in n for k in keys): return cls
    return 'other'


# the positioning flags were written against a looser classifier (substring keys, no shotguns); kept so their results do not change
_P_PISTOLS = ('glock', 'usp', 'p2000', 'p250', 'five', 'tec', 'cz75', 'deagle', 'desert', 'revolver', 'r8', 'elite', 'dual')
_P_SMGS = ('mp9', 'mp7', 'mp5', 'mac', 'ump', 'p90', 'bizon')
_P_SNIPERS = ('awp', 'ssg', 'scar', 'g3sg1')
_P_RIFLES = ('ak', 'm4', 'galil', 'famas', 'aug', 'sg 5', 'sg55')


def wclass_loose(name: str | None) -> str:
    n = (name or '').lower().replace('weapon_', '').replace('-', '').replace(' ', '').replace('_', '')
    n = {'deserteagle': 'deagle', 'r8revolver': 'revolver', 'dualberettas': 'elite'}.get(n, n)
    for cls, keys in (('sniper', _P_SNIPERS), ('rifle', _P_RIFLES), ('smg', _P_SMGS), ('pistol', _P_PISTOLS)):
        if any(k in n for k in keys): return cls
    return 'other'


def wkey(name: str | None) -> str:
    """Event weapon name without the 'weapon_' prefix, for display."""
    return (name or '').lower().replace('weapon_', '')


def best_gun(inv: Iterable[str]) -> tuple[str, str] | None:
    """The strongest gun in an inventory list by class, as (name, class); None if only a knife or grenades."""
    rank = {'sniper': 5, 'rifle': 4, 'smg': 3, 'shotgun': 2, 'pistol': 1}
    best = None
    for w in inv:
        cls = wclass(w)
        if cls in rank and (best is None or rank[cls] > rank[best[1]]): best = (w, cls)
    return best


def enough_for_kill(weapon: str, ammo: float) -> tuple[bool, int, int]:
    """Would this much ammo plausibly have got a kill? Returns (enough, hits_needed, shots_needed)."""
    n = norm(weapon); btk = BTK.get(n)
    if btk is None:
        for k_, v_ in BTK.items():
            if k_ in n: btk = v_; break
    if btk is None: btk = {'rifle': 4, 'sniper': 2, 'smg': 6, 'shotgun': 2, 'pistol': 5}.get(wclass(weapon), 5)
    need = math.ceil(btk / HIT_RATE)
    return ammo >= need, btk, need
