"""Type aliases shared across the project. Imports nothing from the project, so anything may import it without a dependency loop.

The parsed demo and the flag cards are plain dicts (they are pickled to worker processes and merged freely), so their types are aliases
that say what a value is rather than schemas that enforce it. The keys are documented where they are made: mistake_report._parse for
Demo, flags/_context.py (Ctx.card, Round.play, DeathInDepth) for Card."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable, Literal

if TYPE_CHECKING:
    import pandas as pd

XY = tuple[float, float]                        # a map position in world units, or a pixel position on the radar
Proj = Callable[[float, float], XY]             # world (x, y) -> radar pixel (x, y)

Demo = dict[str, Any]                           # the parsed demo: event and tick tables by name, 'me', 'fz', 'winner' ... plus '_' caches
Card = dict[str, Any]                           # one flag instance: round, side, time, pos, won, facts, kind, and the flag's own fields
Side = Literal['mistake', 'play']
Rules = dict[str, tuple[str, str, str]]         # kind -> (title, why, what to do)
Add = Callable[[int, str], None]                # add(points, reason): how a flag's adjust() changes a score
Scored = tuple[int, list[str]]                  # (score 0 to 100, the arithmetic as lines)

Row = Any                                       # one player's snapshot row at a tick (a pandas Series): r['yaw'], r.X ...
EventRow = Any                                  # one event row from DataFrame.itertuples(): d.tick, d.user_steamid ...
ByTick = dict[int, 'pd.DataFrame']              # sampled tick -> every player's snapshot row at that tick
TickTable = dict[int, dict[str, Any]]           # sampled tick -> numpy columns (sid, name, team, X, Y, alive, spotted, place)
Coarse = Callable[[int], int]                   # a tick -> the sampled tick at or before it
NearMate = tuple[float, str, XY]                # (metres, name, position) of the nearest living teammate
FlashTurn = tuple[int, int, XY, list[tuple[Any, float, float, float, float]]]   # see Round.flash_turns

ProgressFn = Callable[[float, str], None]       # (percent, message)
