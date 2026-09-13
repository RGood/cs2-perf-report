# CS2 Performance Report

Deterministic, offline-capable performance reports for Counter-Strike 2 demos. No AI at runtime: demo parsing,
rule-based detection, arithmetic scoring, radar drawing and an HTML template.

## Run

Desktop app (drag demos onto the window; each becomes a report that opens in your browser):

    CS2 Report.bat            (or: pythonw app.py)

Command line:

    make_report latest             newest FACEIT match, any map
    make_report latest de_nuke     newest FACEIT match on that map
    make_report list               recent FACEIT matches and whether each demo is downloaded
    make_report <match id>         a FACEIT match id (1-...) whose demo is in Downloads
    make_report <path>             a .dem, .dem.zst, .zip, .gz or .bz2

Reports land in `reports/` as `<map>_<date>_performance.html`, self-contained (open anywhere, share as a file).
One page covers every player in the match: the top shows both teams with rounds won (green = winner, red = loser)
and a tab per player with their average impact per round; click a tab to switch. `--player` picks the default tab.

## Install

    pip install -r requirements.txt

Python 3.12 on Windows is what this was built on. tkinter ships with Python.

## Inputs

FACEIT demos must be downloaded by you from the match room (login required). They arrive in `Downloads` as
`<match id>-1-1.dem.zst`; `latest` and `list` look for them there. Any demo path works too.

## Files

| File | Role |
|---|---|
| `app.py` | Desktop app: drop zone, queue, progress, opens the report |
| `cs2report.py` | CLI runner: find demo, decompress, fetch radar, build |
| `performance_report.py` | The page: team headers, player tabs, and per player a summary paragraph, average impact per round, round strip, chips, ranked lists, cards (SVG over a shared radar) |
| `mistake_report.py` | Things-to-improve rules, severity, shared demo parser and radar drawing |
| `impact_report.py` | Things-to-keep-doing rules and impact scoring |
| `maps/` | Radar PNGs (from the CS Demo Manager repo) and `offsets.json` (game overview offsets, 44 maps) |

## How scoring works

One metric, impact. Good plays score 0 to +100, mistakes 0 to -100, each from a base weight per type plus context
modifiers (round won or lost, teammates alive, first death, damage, buy). The arithmetic is printed on every card.
The headline is average impact per round.

Analysis rules worth knowing:

- Duel metrics use the 4 s before a death, not the whole round.
- Spray vs burst comes from the gaps between shots (a run of 7+ at cycle rate is a spray).
- A grenade held at death counts only if there was time after contact, a target, and a safe throw window of at
  least 1.5 s in which no nearby enemy was visible to your team, you were not visible to theirs, and you were not
  being hit.
- A grenade thrown too early counts only if it was thrown with no enemy within 30 m and none spotted, and was
  then missing during 4 s+ of contact later that round.
- Untraded deaths are split into "isolated before dying" (movement created the gap) and "died anchoring".

See `flag-catalog.md` for the full list of candidate flags and how each is detected.

Thresholds are named constants at the top of `mistake_report.py` (`CONT_GAP`, `SPRAY_RUN`, `SAFE_WINDOW`) and in
`severity()` / `impact()`. To add a rule: a `RULES` entry, a block in `detect()`, and a base weight.

## Player

Defaults to Steam64 76561198063294402 (RGood). Pass `--player <steam64>` to the CLI, or change `PLAYER` in
`app.py` and `cs2report.py`.
