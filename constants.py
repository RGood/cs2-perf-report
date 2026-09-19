"""Constants shared across the project. This file imports nothing, so anything may import it without creating a dependency loop.
A threshold only one flag uses stays at the top of that flag's file; it belongs here once a second file needs it."""

# ---- units
TICK = 64               # demo ticks per second
M = 0.0254              # world units -> metres

# ---- shot patterns (the 4 s engagement window)
CONT_GAP = 10           # ticks (~0.16 s): shots closer together than this are one continuous run (AK/M4 cycle ~6-7 ticks)
SPRAY_RUN = 7           # a continuous run this long or longer is a spray; shorter runs are bursts

# ---- utility
SAFE_WINDOW = 1.5       # seconds after contact during which no enemy could engage you, needed before a held grenade counts as usable
NADE_RADIUS = {'smokegrenade': 144, 'molotov': 150}   # world units: smoke cloud, molotov fire patch

# ---- shared fights and supporting a teammate
SHARED_FIGHT_S = 8      # a teammate who died this many seconds before you ...
SHARED_FIGHT_M = 15     # ... within this distance means you died second in a shared fight, not alone
REACTION_S = 0.4        # reasonable reaction time before support could begin
PEEK_S = 0.6            # time to swing and get the crosshair on the enemy
SUPPORT_RANGE_M = 30    # beyond this you could not realistically have joined
PEEK_RANGE_M = 20       # within this you could have peeked even without line of sight

# ---- per-bullet accuracy (demolib.bullet_cones)
STANDING_SPEED = 15     # u/s: slower than this is standing still
RECOIL_BUCKETS = (1, 4, 9)      # recoil index 0 | 1-3 | 4-8 | 9+: how far into a spray the bullet was
