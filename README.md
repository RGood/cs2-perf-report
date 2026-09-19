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

Nothing to do if you start it with `CS2 Report.bat` or `make_report.bat`: both run `ensure_deps.py` first, which checks
`requirements.txt` against what is installed (no network, a fraction of a second) and runs pip only when a package is
missing or older than the listed minimum. To do it by hand, or when running the `.py` files directly:

    pip install -r requirements.txt

Python 3.12 on Windows is what this was built on. tkinter ships with Python.

## Your player

Enter your Steam profile URL in the app (vanity URL, /profiles/ URL, bare vanity name or Steam64 all work) and press
Save. It is resolved through Steam's public profile page (no API key) and stored in `settings.json`, together with
your FACEIT id if the account has one. Every report then opens on your tab by default. Command line:

    python cs2report.py profile https://steamcommunity.com/id/yourname/

## Premier and FACEIT match lists

The app lists matches from two sources, both local or Steam-official only. **Premier**: the demos the game saves when you download a match from the
in-game history (Watch > Your matches > Download); they land in the game's `replays` folder as `match730_*.dem` and are
listed with date, map, your win or loss, the scoreline and size (date, score and result come from the game's `.dem.info`
sidecar next to each demo; the map from the demo header). **FACEIT**: your recent matches from the FACEIT API, marked with whether the demo has
been downloaded to `Downloads`. Select one or more rows and press Analyse selected (or double-click). Selecting a FACEIT
match whose demo is not downloaded opens its match room in your browser (FACEIT only serves demos to a logged-in session);
the app then analyses it automatically once the download finishes. The app watches `Downloads` and the game's replays
folder through Windows directory-change notifications (`folder_watch.py`, no polling, no extra package): a demo that
appears or finishes downloading updates only its own row in place (selection and scroll position are kept) and does not
start a report by itself. Matches you fetched from the app are analysed on arrival only if "Analyse fetched matches when
they arrive" is ticked (off by default). To fetch a Premier demo you do not have yet, paste its share code (CS2: Watch > Your matches > share icon) into
"Fetch by share code": the app launches CS2 with `csgo_download_match <code>` (or copies that command to the clipboard if
CS2 is already running), the demo lands in the replays folder, and the watcher lists and analyses it. Command line:
`python cs2report.py premier`, `python cs2report.py list`, `python cs2report.py download <share code>`.

## Inputs

FACEIT demos must be downloaded by you from the match room (login required). They arrive in `Downloads` as
`<match id>-1-1.dem.zst`; `latest` and `list` look for them there. Any demo path works too.

## Files

| File | Role |
|---|---|
| `app.py` | Desktop app: drop zone, queue, progress, opens the report |
| `cs2report.py` | CLI runner: find demo, decompress, fetch radar, build |
| `performance_report.py` | The page: team headers, player tabs, and per player a summary paragraph, average impact per round, round strip, chips, ranked lists, cards (SVG over a shared radar) |
| `flags/` | Every flag, one Python file each, all with the same API (`KIND`, `SIDE`, `TITLE`, `WHY`, `DO`, `BASE`, `detect(c)`, optional `adjust(m, add)`). `flags/README.md` explains it; `flags/_template.py` is the starting point for a new flag; `_context.py` is what the flags share |
| `constants.py` | Every constant more than one file uses (`TICK`, `M`, `CONT_GAP`, `SPRAY_RUN`, `SAFE_WINDOW` ...). Imports nothing, so anything can import it without a dependency loop |
| `report_types.py` | Type aliases used across the project (`Demo`, `Card`, `XY`, `Add`, `Scored` ...). Imports nothing from the project. Every function is annotated and `mypy --ignore-missing-imports` passes; see `flags/README.md` |
| `demolib.py` | Helpers over the parsed demo shared by the flags and the report modules (per-demo caches, grenade flights, teammate-fight analysis, the per-bullet inaccuracy table) |
| `ensure_deps.py` | Run by both `.bat` launchers: installs what `requirements.txt` lists when a package is missing or too old |
| `folder_watch.py` | Event-driven watching of the demo folders for the app |
| `mistake_report.py` | The demo parser, radar drawing, and thin wrappers `detect` / `severity` over the mistake flags |
| `impact_report.py` | Thin wrappers `detect` / `impact` over the play flags |
| `app.py` startup | Self-check: recreates folders, rebuilds the byte-code cache, verifies imports and packages, shows a dialog if anything is wrong |
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
- Untraded deaths are split into "isolated before dying" (movement created the gap) and "died anchoring". Neither fires when
  the death was the second death of a shared fight (a teammate died within 8 s before you and was in the same engagement:
  same killer, damage exchanged with your killer, or an enemy who had both of you in view) or when a living teammate had
  your killer in view at the moment you died (a trade was possible). Engagement and line of sight decide this, not distance. The same two exemptions apply to "early solo T contact" and "alone on eco".
- Didn't join the fight: a teammate's fight (1.5 s or more of exchanged damage, 3 s if you could only hear it) that you knew about (you or the enemy had the other in view, the teammate beside you had them in view, or shots within 40 m), could have reached while it was still going (path distance at run speed plus reaction time), that no other enemy was covering, and that you were free to join (alive, not fighting, not flashed, not watched by another enemy) but never did. Awareness evidence, never distance alone. Rare by design.
- Late support: a teammate's fight you could have joined (0.4 s reaction + 0.6 s to swing allowed, line of sight or within 20 m) where you engaged only after they died.
- Fights on their terms: crossfire (two enemies had you in view from different angles), swung into a held angle (you moving, they set and aimed at first sight), seen first (they saw you 1.5 s+ before you saw them), their range (SMG vs rifle past 20 m, rifle vs AWP past 35 m). Speed comes from position deltas, not the demo's velocity field.

See `flag-catalog.md` for the full list of candidate flags and how each is detected.

Every flag is one file in `flags/`, with its thresholds as named constants at the top, its rule text, its base weight, its
detector and its own score modifiers. To add a flag, copy `flags/_template.py` to `flags/<kind>.py`; nothing else needs editing
(see `flags/README.md`). The shared scoring steps (round result, death context and its +10 cap) are in `flags/_score.py`.

## Player

Set through the app or `cs2report.py profile <url>`; stored in `settings.json`. `--player <steam64>` overrides it for one run.
