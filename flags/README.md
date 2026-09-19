# flags

One Python file per flag. The file name is the flag's id (`ran_into_contact.py` defines the `ran_into_contact` flag), and every file has the same shape, so adding or changing a flag never touches another file.

## The API every flag implements

```python
KIND  = 'ran_into_contact'     # the id; must equal the file name
SIDE  = 'mistake'              # 'mistake' counts as negative impact, 'play' as positive
TITLE = "Ran into contact"     # name on the report
WHY   = "..."                  # what is measured, every threshold named, and why it matters
DO    = "..."                  # what to do about it (mistake) or keep doing (play)
BASE  = 12                     # base score, 0 to 100

def detect(c: Ctx) -> Iterator[Card | None]:      # yield one card (a dict) per instance; a None is skipped
    ...

def adjust(m: Card, add: Add) -> None:            # optional: flag-specific score modifiers, add(points, "reason")
    ...
```

Optional attributes: `RETIRED = "why"` (kept for reference, not reported), `KEEP_NEAR = True` (keep the nearest-teammate marker), `SKIP_CONTEXT = {...}` (death-context modifiers that do not apply), `OUTNUMBERED_BONUS = True` (a play worth +5 when at most one teammate was alive).

`flags/__init__.py` loads every file that does not start with an underscore, checks it defines the required names, and exposes:

| Call | Returns |
|---|---|
| `flags.detect(D, 'mistake')` / `flags.detect(D, 'play')` | every card for the player `D['me']`, each stamped with its `kind` |
| `flags.score(card)` | `(score 0 to 100, breakdown lines)` |
| `flags.rules(side)`, `flags.bases(side)` | the titles/texts and base weights the report pages read |
| `flags.ALL` | `{kind: module}` including retired flags |

`mistake_report.detect/severity` and `impact_report.detect/impact` are thin wrappers over these, so the report code did not change.

## Adding a flag

1. Copy `_template.py` to `flags/<kind>.py` and fill it in. That is all: no list to register it in.
2. `detect(c)` receives the shared context (`_context.py`). Use what it already offers before scanning the demo yourself:
   - `c.rounds()` gives `Round` objects: `team`, `side`, `ft`/`end` ticks, `won`, `rd` (deaths), `my_kills`, `my_deaths`, `rh` (my damage), `rf` (my shots), `mates`, `foes`, `first_contact_tick`, `teammate_fights()`, `flash_turns()`.
   - `R.deaths_of_mine()` / `R.kills_of_mine()` give `Death` / `Kill` objects with the position, the other player, the nearest teammate, whether it was traded, and a `card(...)` maker.
   - `c.deaths_in_depth()` is the full death analysis (contact, safe throw windows, the 4 s engagement window, shared fights); `c.death_sightlines()` is who saw whom over the last 3 s.
   - Lookups: `c.row(tick, sid)`, `c.x(tick, sid)` (ducking, ammo, helmet, balance ...), `c.sees(row, sid)`, `c.first_seen(seer, seen, t_end)`, `c.speed(tick, sid)`, `c.nearest_mate(tick, team)`, `c.alive_counts(tick, team)`, `c.loss_bonus(rn)`, `c.attention(...)`.
3. Yield cards made with `c.card(...)`, `Death.card(...)`, `Kill.card(...)` or `Round.play(...)`. A card needs `round`, `side`, `time`, `pos`, `won` and `facts`; extra keys (`extra_pos`, `extra_label`, `opponents`, your own numbers for `adjust`) ride along. `facts` is the evidence sentence: put the numbers in it.
4. Put thresholds in named constants at the top of the file and name them in `WHY`.
5. A flag file never imports another flag file. Something two flags need goes into `_context.py` (demo context, computed once per player and cached), `_shared.py` (helper functions, such as the isolation test `held_alone` and `separated_from_team` both use) or, for a constant, `../constants.py`. A threshold only one flag uses stays at the top of that flag's file.

## Scoring

`_score.py`: base weight, then the round result (a quarter of the base, between 3 and 10), then for mistakes the death-context modifiers (teammates alive, first death, no damage dealt, equipment), capped at +10 together, then the flag's own `adjust`. Plays get the outnumbered bonus last. The arithmetic is shown on every card.

## Conventions

- Measure decisions and behaviours, not outcomes. Outcome flags are retired, not deleted: see the `RETIRED` line in their files.
- Exact demo data only. Where the demo cannot say something (whether another angle existed, footsteps), the flag says so in `WHY` instead of guessing.
- Evidence over distance: who had whom in view, who shot at whom, what the grenade did.
- Engagement metrics use the 4 s before the death or kill; a sighting counts as "seen" for 8 s.
- State at a death (stance, ammo, airborne) is read at the last tick alive, `Death.last`, never at the death tick: there the player is already dead, the ammo is blank and `is_airborne` reads true for about half of all deaths.
- Weapon accuracy comes from the game's own per-bullet record (`demolib.bullet_cones`, from the `fire_bullets` event), not from speed thresholds.

## Types

Every function is annotated. The aliases are in `../report_types.py` (`Demo`, `Card`, `XY`, `Add`, `Scored`, `Row`, `EventRow` ...), which imports nothing from the project; the shape of a flag file is the `FlagModule` protocol in `_types.py`; and `Ctx`, `Round`, `Death`, `Kill` and `DeathInDepth` declare their attributes at the top of each class, so an editor can complete `x.kpos` or `R.foes` and a checker can catch a misspelt one. The demo tables are pandas frames and the cards are plain dicts, so their contents are `Any`: the annotations say what a value is, they do not validate it.

`c.rt(tick, rn)` returns a float and needs a round with a freeze end, which every `Round` from `c.rounds()` has; use `c.rt_or_none()` for a round number taken straight from an event. `Death.pos` is always set and `Death.killer` is `''` when the demo names no killer, while `Death.kpos`, `Death.nm` and `Kill.vpos` can be `None` and must be checked.

To check the project (mypy is a development tool, not a requirement of the report):

    pip install mypy
    mypy --ignore-missing-imports constants.py report_types.py demolib.py mistake_report.py impact_report.py performance_report.py cs2report.py app.py folder_watch.py ensure_deps.py flags

It passes with no issues; keep it that way when adding a flag.

## Shared files

`_context.py` (the context, rounds, deaths, kills), `_types.py` (the `FlagModule` protocol), `_shared.py` (helpers two or more flags use), `_score.py` (scoring), `_weapons.py` (weapon classes, hits-to-kill), `_economy.py` (freeze-time buy data), `_template.py` (start here). Demo-level helpers shared with the report modules are in `../demolib.py`, and every shared constant (`TICK`, `M`, `CONT_GAP`, `SPRAY_RUN`, `SAFE_WINDOW` ...) is in `../constants.py`, which imports nothing.

Imports run one way, so no loop is possible: `constants` / `report_types` → `demolib` → `_weapons` / `_context` / `_economy` → `_shared` → the flag files → `flags/__init__.py` → `mistake_report` / `impact_report` → `performance_report`.
