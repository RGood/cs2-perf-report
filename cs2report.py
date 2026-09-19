"""One-step CS2 performance report (things to improve + things to keep doing).

Usage
  python cs2report.py latest                    newest FACEIT match, any map
  python cs2report.py latest --map de_nuke      newest FACEIT match on that map
  python cs2report.py <match-id or path>        a FACEIT match id (1-xxxx...), a .dem, or a .dem.zst
  python cs2report.py list [--n 15]             show recent FACEIT matches with map, score, and whether the demo is on disk
  python cs2report.py premier                   list Premier demos saved by the game (download them in-game first)
  python cs2report.py download <share code>     make CS2 download that Premier demo (csgo_download_match) into the replays folder
  python cs2report.py profile <steam url>       set the player (Steam profile URL, vanity name or Steam64); saved to settings.json

Options
  --player <steam64>   override the player saved in settings.json for one run
  --out <file.html>    default reports/<map>_<date>_performance.html
  --keep-dem           keep the decompressed .dem next to the report (default: delete after parsing)

What it does
  1. Resolves the demo: FACEIT match id -> Downloads/<id>-1-1.dem.zst; a path is used as is.
  2. Decompresses .zst if needed.
  3. Makes sure the map's radar exists in tools/maps (fetches from the CS Demo Manager repo when missing;
     falls back to the demo's own position silhouette if it cannot).
  4. Runs performance_report.py (mistakes + impact in one page) and prints the counts and the output path.
"""
from __future__ import annotations
from typing import Any, Callable
OnProgress = Callable[[float, float, float, str], None]      # (percent, seconds elapsed, seconds left, message)
OnLine = Callable[[str], None]
import sys, os, json, glob, argparse, subprocess, datetime, urllib.request
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')      # type: ignore[union-attr]
    except Exception: pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, 'reports')
os.makedirs(ROOT, exist_ok=True)
MAPS = os.path.join(HERE, 'maps')
DOWNLOADS = os.path.expanduser('~/Downloads')
SETTINGS = os.path.join(HERE, 'settings.json')
DEFAULTS = dict(steam64='', name='', profile_url='', faceit_id=None)   # no player until one is entered


def load_settings() -> dict[str, Any]:
    try:
        s = json.load(open(SETTINGS, encoding='utf-8'))
        return {**DEFAULTS, **s}
    except Exception:
        return dict(DEFAULTS)


def save_settings(s: dict[str, Any]) -> None:
    json.dump(s, open(SETTINGS, 'w', encoding='utf-8'), indent=1)


def clear_settings() -> None:
    if os.path.exists(SETTINGS):
        os.remove(SETTINGS)


def resolve_steam(text: str) -> tuple[str, str | None]:
    """Accepts a steamcommunity profile URL (vanity or /profiles/), a bare vanity name, or a 17-digit Steam64.
    Returns (steam64, persona name). Uses the public profile XML; no API key."""
    import re, xml.etree.ElementTree as ET
    text = (text or '').strip()
    m = re.search(r'(7656\d{13})', text)
    if m and '/id/' not in text:
        url = f'https://steamcommunity.com/profiles/{m.group(1)}/?xml=1'
    else:
        m2 = re.search(r'/id/([^/?#]+)', text)
        vanity = m2.group(1) if m2 else text.rstrip('/').split('/')[-1]
        url = f'https://steamcommunity.com/id/{vanity}/?xml=1'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=20) as resp:
        root = ET.fromstring(resp.read())
    sid = root.findtext('steamID64'); name = root.findtext('steamID')
    if not sid:
        raise ValueError('profile not found or private: ' + (root.findtext('error') or url))
    return sid, name


def faceit_id_for(steam64: str) -> str | None:
    """FACEIT player id for a Steam64, or None if the account is not on FACEIT."""
    req = urllib.request.Request(f'https://api.faceit.com/users/v1/users?game=cs2&game_id={steam64}', headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            d = json.load(resp)
        pl = d.get('payload') or []
        return pl[0]['id'] if pl else None
    except Exception:
        return None


SHARE_DICT = "ABCDEFGHJKLMNOPQRSTUVWXYZabcdefhijkmnopqrstuvwxyz23456789"


def decode_sharecode(code: str) -> tuple[int, int, int]:
    """CSGO-xxxxx-xxxxx-xxxxx-xxxxx-xxxxx -> (match_id, outcome_id, token). Same encoding the game uses."""
    import re
    s = re.sub(r'^CSGO-', '', code.strip()).replace('-', '')
    if len(s) != 25 or any(c not in SHARE_DICT for c in s):
        raise ValueError(f'not a share code: {code}')
    big = 0
    for c in reversed(s):
        big = big * len(SHARE_DICT) + SHARE_DICT.index(c)
    raw = big.to_bytes(18, 'little')
    match_id = int.from_bytes(raw[0:8], 'little'); outcome_id = int.from_bytes(raw[8:16], 'little'); token = int.from_bytes(raw[16:18], 'little')
    return match_id, outcome_id, token


def _pb_fields(b: bytes) -> list[tuple[int, Any]]:
    """Minimal protobuf walker: list of (field, value) where value is an int (varint) or bytes (length-delimited / fixed)."""
    i = 0; out: list[tuple[int, Any]] = []
    def varint(i: int) -> tuple[int, int]:
        v = 0; s = 0
        while True:
            x = b[i]; i += 1; v |= (x & 0x7f) << s; s += 7
            if not x & 0x80: return v, i
    while i < len(b):
        key, i = varint(i); f, wt = key >> 3, key & 7
        if wt == 0: v, i = varint(i); out.append((f, v))
        elif wt == 2: l, i = varint(i); out.append((f, b[i:i + l])); i += l
        elif wt == 1: out.append((f, b[i:i + 8])); i += 8
        elif wt == 5: out.append((f, b[i:i + 4])); i += 4
        else: break
    return out


def premier_info(dem_path: str, steam64: str | None = None) -> dict[str, Any]:
    """Read the game's <demo>.dem.info sidecar (CDataGCCStrike15_v2_MatchInfo): match time, final team scores, who won,
    and whether the given player won. Returns {} if the sidecar is missing."""
    p = dem_path + '.info'
    if not os.path.exists(p): return {}
    try:
        top = _pb_fields(open(p, 'rb').read())
        mt = next((v for k, v in top if k == 2), None)
        rounds = [v for k, v in top if k == 5]
        if not rounds: return dict(time=datetime.datetime.fromtimestamp(mt)) if mt else {}
        last = _pb_fields(rounds[-1])
        scores = [v for k, v in last if k == 12]
        result = next((v for k, v in last if k == 11), None)      # 1 = first team won, 2 = second, 0 = draw
        res = next((v for k, v in last if k == 2), b'')
        accounts = [v for k, v in _pb_fields(res) if k == 1]
        won = None
        if steam64 and len(accounts) >= 10 and result in (1, 2):
            a32 = int(steam64) - 76561197960265728
            if a32 in accounts:
                team = 0 if accounts.index(a32) < 5 else 1
                won = (result - 1) == team
        return dict(time=datetime.datetime.fromtimestamp(mt) if mt else None, scores=scores if len(scores) == 2 else None, result=result, won=won,
                    score_text=f'{scores[0]}-{scores[1]}' if len(scores) == 2 else '')
    except Exception:
        return {}


def expected_premier_path(match_id: int, outcome_id: int, token: int) -> str | None:
    d = cs2_replays_dir()
    return os.path.join(d, f'match730_{match_id:021d}_{outcome_id:010d}_{token}.dem') if d else None


def cs2_download_command(code: str) -> tuple[str, str]:
    """Console command that makes the game download a match demo by share code, and a steam:// URL that launches CS2 with it."""
    cmd = f'csgo_download_match {code.strip()}'
    return cmd, 'steam://run/730//+' + cmd.replace(' ', '%20')


def launch_cs2_download(code: str) -> str:
    """Ask Steam to launch CS2 with the download command. If CS2 is already running, Steam does not pass the command; use the console then."""
    cmd, url = cs2_download_command(code)
    os.startfile(url)
    return cmd


def cs2_replays_dir() -> str | None:
    """The game's replays folder, found through Steam's library list. Premier demos downloaded in-game land here."""
    cands = []
    for base in (r'C:\Program Files (x86)\Steam', r'C:\Program Files\Steam'):
        vdf = os.path.join(base, 'steamapps', 'libraryfolders.vdf')
        if os.path.exists(vdf):
            import re
            libs = re.findall(r'"path"\s+"([^"]+)"', open(vdf, encoding='utf-8', errors='ignore').read())
            cands += [l.replace('\\\\', '\\') for l in libs]
        cands.append(base)
    for lib in cands:
        d = os.path.join(lib, 'steamapps', 'common', 'Counter-Strike Global Offensive', 'game', 'csgo', 'replays')
        if os.path.isdir(d):
            return d
    return None


def premier_demos() -> list[dict[str, Any]]:
    """Premier / matchmaking demos saved by the game (match730_*.dem), newest first, with map from the demo header."""
    d = cs2_replays_dir()
    if not d:
        return []
    out = []
    for f in sorted(glob.glob(os.path.join(d, 'match730_*.dem')), key=os.path.getmtime, reverse=True):
        mapname = '?'
        try:
            from demoparser2 import DemoParser
            mapname = DemoParser(f).parse_header().get('map_name', '?')
        except Exception:
            pass
        info = premier_info(f, load_settings().get('steam64'))
        out.append(dict(path=f, date=info.get('time') or datetime.datetime.fromtimestamp(os.path.getmtime(f)), map=mapname, mb=os.path.getsize(f) / 1e6,
                        score=info.get('score_text', ''), won=info.get('won')))
    return out



UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36',
      'Accept': 'application/json', 'Origin': 'https://www.faceit.com', 'Referer': 'https://www.faceit.com/'}
RADAR_SRC = 'https://raw.githubusercontent.com/akiver/cs-demo-manager/main/static/images/maps/cs2/radars/{m}.png'


def faceit_recent(n: int = 20) -> list[dict[str, Any]]:
    s = load_settings(); fid = s.get('faceit_id')
    if not s.get('steam64'):
        raise RuntimeError('no player set: enter your Steam profile first (app field, or: cs2report.py profile <url>)')
    if not fid:
        raise RuntimeError('this Steam account has no FACEIT profile; use Premier demos or a demo file')
    url = f'https://api.faceit.com/stats/v1/stats/time/users/{fid}/games/cs2?page=0&size={n}'
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.load(r)
    out = []
    for r in rows:
        mid = r['matchId']
        out.append(dict(match_id=mid, map=r['i1'], date=datetime.datetime.fromtimestamp(r['date'] / 1000), won=r['i10'] == '1',
                        score=r['i18'], kills=r['i6'], deaths=r['i8'], adr=r['c10'], elo=r.get('elo'), elo_delta=r.get('elo_delta'),
                        demo=os.path.join(DOWNLOADS, f'{mid}-1-1.dem.zst')))
    return out


def ensure_radar(mapname: str) -> None:
    offs = json.load(open(os.path.join(MAPS, 'offsets.json'))) if os.path.exists(os.path.join(MAPS, 'offsets.json')) else {}
    if mapname not in offs:
        print(f'  no radar offsets for {mapname}; the report will use the demo silhouette instead')
        return
    for suffix in ('', '_lower'):
        dst = os.path.join(MAPS, f'{mapname}{suffix}.png')
        if os.path.exists(dst):
            continue
        try:
            req = urllib.request.Request(RADAR_SRC.format(m=mapname + suffix), headers={'User-Agent': 'curl'})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            if len(data) > 5000:
                open(dst, 'wb').write(data); print(f'  fetched radar {os.path.basename(dst)}')
        except Exception as e:
            if suffix == '':
                print(f'  could not fetch radar for {mapname} ({e}); using the demo silhouette')


def decompress(src: str, dst: str) -> None:
    import zstandard
    with open(src, 'rb') as f, open(dst, 'wb') as o:
        zstandard.ZstdDecompressor().copy_stream(f, o)


def map_of_demo(path: str) -> str:
    from demoparser2 import DemoParser
    return DemoParser(path).parse_header().get('map_name', 'unknown')


CRASH_CODES = {139, -11, 3221225477, -1073741819, 3221226505, -1073741571}   # segfault / access violation / fail-fast


class ReportCrashed(Exception):
    def __init__(self, code: int) -> None: super().__init__(str(code)); self.code = code


def run_with_progress(cmd: list[str], on_progress: OnProgress | None = None, on_line: OnLine | None = None, attempts: int = 3) -> list[str]:
    """Run the report script; if the process dies in a native crash (demoparser2 has a thread race on some demos) run it again."""
    for i in range(attempts):
        try:
            return _run_with_progress(cmd, on_progress, on_line)
        except ReportCrashed as e:
            if i + 1 >= attempts: raise RuntimeError(f"the demo parser crashed {attempts} times in a row (exit code {e.code}); try once more, and if it keeps failing the demo may be damaged")
            msg = f"the demo parser crashed (exit code {e.code}); running the report again ({i + 2} of {attempts})"
            print(msg, file=sys.stderr, flush=True)
            if on_line: on_line(msg)
    raise RuntimeError('the report was not run: attempts must be at least 1')


def _run_with_progress(cmd: list[str], on_progress: OnProgress | None = None, on_line: OnLine | None = None) -> list[str]:
    """Run the report script, forwarding PROGRESS lines to a callback (or drawing a text bar) and other lines to on_line/print."""
    # pythonw has no valid C-level stdout/stderr; a C library writing a warning to them fail-fasts the process (0xc0000409).
    # The report and its worker processes therefore always run under python.exe, hidden by CREATE_NO_WINDOW.
    exe = cmd[0]
    if exe.lower().endswith('pythonw.exe'):
        cand = exe[:-len('pythonw.exe')] + 'python.exe'
        if os.path.exists(cand): cmd = [cand] + list(cmd[1:])
    p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1,
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    tail = []
    import threading, time as _t
    state: dict[str, Any] = {}; stop = threading.Event()
    def ticker() -> None:
        # redraw the text bar every 0.3 s, advancing at the rate implied by the last estimate
        while not stop.is_set():
            _t.sleep(0.3)
            if not state or on_progress: continue
            import math
            since = _t.time() - state['at']
            target = state['pct'] + (1 - math.exp(-since / state['dur'])) * state['step']
            pct = state['shown'] = max(state.get('shown', 0), min(target, 99))
            bar = '#' * int(pct // 4) + '-' * (25 - int(pct // 4))
            sys.stdout.write(f"\r[{bar}] {pct:3.0f}%  {state['el'] + since:3.0f}s elapsed, ~{max(state['eta'] - since, 0):3.0f}s left  {state['msg']:<45}"); sys.stdout.flush()
    threading.Thread(target=ticker, daemon=True).start()
    assert p.stdout is not None      # stdout=PIPE above
    for line in p.stdout:
        line = line.rstrip()
        if not line or 'Warning' in line: continue
        if line.startswith('PROGRESS '):
            _, pct, el, eta, msg = line.split(' ', 4)
            pct, el, eta = int(pct), int(el), int(eta)
            prev_pct, prev_at = state.get('pct'), state.get('at')
            step = (pct - prev_pct) if prev_pct is not None and pct > prev_pct else 6.0
            dur = (_t.time() - prev_at) if prev_at is not None and prev_pct is not None and pct > prev_pct else max(eta * step / max(100 - pct, 1), 0.5)
            state.update(pct=pct, el=el, eta=eta, msg=msg, at=_t.time(), step=step, dur=max(dur, 0.5), shown=max(state.get('shown', 0), pct))
            pct = int(state['shown'])
            if on_progress: on_progress(pct, el, eta, msg)
            else:
                bar = '#' * (pct // 4) + '-' * (25 - pct // 4)
                sys.stdout.write(f"\r[{bar}] {pct:3d}%  {el:3d}s elapsed, ~{eta:3d}s left  {msg:<45}"); sys.stdout.flush()
                if pct >= 100: stop.set(); sys.stdout.write('\n')
        else:
            tail.append(line)
            if on_line: on_line(line)
            elif not on_progress: print(line)
    p.wait(); stop.set()
    if p.returncode in CRASH_CODES or (p.returncode or 0) < 0: raise ReportCrashed(p.returncode)
    if p.returncode != 0:
        raise RuntimeError('\n'.join(tail[-12:]) or 'report script failed')
    return tail


def run(target: str, player: str | None, out: str | None, keep: bool) -> str:
    # resolve to a .dem.zst or .dem path
    label = None
    if os.path.exists(target):
        src = target
    elif target.startswith('1-'):
        src = os.path.join(DOWNLOADS, f'{target}-1-1.dem.zst')
        if not os.path.exists(src):
            sys.exit(f'demo for {target} is not in {DOWNLOADS}. Download it from https://www.faceit.com/en/cs2/room/{target} first.')
    else:
        sys.exit(f'not found: {target}')
    dem = src
    tmp = None
    if src.endswith('.zst'):
        tmp = os.path.join(HERE, f'tmp_{os.getpid()}_' + os.path.basename(src)[:-4])
        print(f'decompressing {os.path.basename(src)} ...'); decompress(src, tmp); dem = tmp
    mapname = map_of_demo(dem)
    ensure_radar(mapname)
    if not out:
        stamp = datetime.datetime.fromtimestamp(os.path.getmtime(src)).strftime('%Y-%m-%d')
        out = os.path.join(ROOT, f'{mapname[3:] if mapname.startswith("de_") else mapname}_{stamp}_performance.html')
    run_with_progress([sys.executable, os.path.join(HERE, 'performance_report.py'), dem, '--player', player or '', '--out', out])
    if tmp and not keep:
        if os.path.exists(tmp): os.remove(tmp)
    elif tmp:
        print(f'kept {tmp}')
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('target', help='latest | list | premier | download <share code> | profile <steam url> | <faceit match id> | <path to .dem or .dem.zst>')
    ap.add_argument('rest', nargs='*')
    ap.add_argument('--map', default=None, help='with latest: restrict to this map, e.g. de_nuke')
    ap.add_argument('--n', type=int, default=15)
    ap.add_argument('--player', default=None)
    ap.add_argument('--out', default=None)
    ap.add_argument('--keep-dem', action='store_true')
    a = ap.parse_args()
    if a.target == 'profile':
        sid, name = resolve_steam(' '.join(a.rest)); s = load_settings(); s.update(steam64=sid, name=name, profile_url=' '.join(a.rest), faceit_id=faceit_id_for(sid)); save_settings(s)
        print(f"player set to {name} ({sid}); FACEIT: {s['faceit_id'] or 'not found'}"); return
    if a.target == 'download':
        code = a.rest[0]; mid, oid, tok = decode_sharecode(code); cmd = launch_cs2_download(code)
        print('Launched CS2 with: ' + cmd)
        print('The demo will appear as ' + os.path.basename(expected_premier_path(mid, oid, tok) or 'match730_...dem') + ' in the replays folder. If CS2 was already running, paste the command into its console instead.')
        return
    if a.target == 'premier':
        rows = premier_demos()
        if not rows: print('no Premier demos found. Download a match from the in-game match history first (Watch > Your matches > Download); it lands in the game\'s replays folder.')
        for x in rows[:a.n]: print(f"{x['date']:%Y-%m-%d %H:%M}  {x['map']:<12} {('W ' if x['won'] else 'L ' if x['won'] is False else '  ') + x['score']:<8} {x['mb']:.0f} MB  {x['path']}")
        return
    if a.target in ('latest', 'list'):
        rows = faceit_recent(max(a.n, 30))
        if a.target == 'list':
            for r in rows[:a.n]:
                print(f"{r['date']:%Y-%m-%d %H:%M}  {r['map']:<12} {'W' if r['won'] else 'L'} {r['score']:<8} K/D {r['kills']}/{r['deaths']}  ADR {r['adr']:<6} elo {r['elo']} {r['elo_delta'] or ''}  {'demo on disk' if os.path.exists(r['demo']) else 'demo NOT downloaded'}  {r['match_id']}")
            return
        cands = [r for r in rows if not a.map or r['map'] == a.map]
        if not cands:
            sys.exit(f'no recent match on {a.map}')
        r = cands[0]
        print(f"latest {r['map']} match: {r['date']:%Y-%m-%d %H:%M}, {'won' if r['won'] else 'lost'} {r['score']}, {r['match_id']}")
        if not os.path.exists(r['demo']):
            sys.exit(f"demo not on disk. Download it from https://www.faceit.com/en/cs2/room/{r['match_id']} (it lands in Downloads as {os.path.basename(r['demo'])}), then rerun.")
        out = run(r['demo'], a.player or load_settings()['steam64'], a.out, a.keep_dem)
    else:
        out = run(a.target, a.player or load_settings()['steam64'], a.out, a.keep_dem)
    print(f'report: {out}')


if __name__ == '__main__':
    main()
