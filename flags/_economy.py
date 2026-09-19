"""What the buy flags share: my money, equipment and guns at freeze end, against my teammates' average."""
from __future__ import annotations
from ._context import Ctx, Round
from types import SimpleNamespace
from ._weapons import wclass


def freeze_economy(c: Ctx, R: Round) -> SimpleNamespace | None:
    """My economy at the freeze end of round R, or None when the demo has no economy sample for me there.

    my_eq      my equipment value            avg        my teammates' average equipment value (team_eq: the list)
    bal        money left in the bank        spent      money spent this round
    inv        my inventory (names)          prim       the rifles, SMGs and snipers in it
    xr         the raw tick sample (has_helmet, has_defuser ...)       spawn   where I stood, for the card
    """
    if 'eco' in R._cache: return R._cache['eco']
    me = c.me; ft = R.ft; g0 = R.g0; out = None
    xr = c.x(ft, me); r0 = c.row(ft, me)
    spawn = (float(r0.X), float(r0.Y)) if r0 is not None and r0.X == r0.X else None
    if xr is not None and g0 is not None and r0 is not None and spawn is not None:
        my_eq = int(r0['current_equip_value'])
        team_eq = [int(v) for v in g0[(g0['team_num'] == R.team) & (g0['steamid'] != me)]['current_equip_value'].dropna()]
        avg = (sum(team_eq) / len(team_eq)) if team_eq else 0
        try: inv = [str(w) for w in r0['inventory']]
        except TypeError: inv = []
        prim = [w for w in inv if wclass(w) in ('rifle', 'smg', 'sniper')]
        bal = int(xr.balance) if xr.balance == xr.balance else 0; spent = int(xr.cash_spent_this_round) if xr.cash_spent_this_round == xr.cash_spent_this_round else 0
        out = SimpleNamespace(xr=xr, spawn=spawn, my_eq=my_eq, team_eq=team_eq, avg=avg, inv=inv, prim=prim, bal=bal, spent=spent)
    R._cache['eco'] = out
    return out
