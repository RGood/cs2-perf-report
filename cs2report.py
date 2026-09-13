"""One-step CS2 performance report (things to improve + things to keep doing).

Usage
  python cs2report.py latest                    newest FACEIT match, any map
  python cs2report.py latest --map de_nuke      newest FACEIT match on that map
  python cs2report.py <match-id or path>        a FACEIT match id (1-xxxx...), a .dem, or a .dem.zst
  python cs2report.py list [--n 15]             show recent FACEIT matches with map, score, and whether the demo is on disk

Options
  --player <steam64>   default 76561198063294402 (RGood)
  --out <file.html>    default reports/<map>_<date>_performance.html
  --keep-dem           keep the decompressed .dem next to the report (default: delete after parsing)

What it does
  1. Resolves the demo: FACEIT match id -> Downloads/<id>-1-1.dem.zst; a path is used as is.
  2. Decompresses .zst if needed.
  3. Makes sure the map's radar exists in tools/maps (fetches from the CS Demo Manager repo when missing;
     falls back to the demo's own position silhouette if it cannot).
  4. Runs performance_report.py (mistakes + impact in one page) and prints the counts and the output path.
"""
import sys, os, json, glob, argparse, subprocess, datetime, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, 'reports')
os.makedirs(ROOT, exist_ok=True)
MAPS = os.path.join(HERE, 'maps')
DOWNLOADS = os.path.expanduser('~/Downloads')
PLAYER = '76561198063294402'
FACEIT_PLAYER_ID = '182727c3-3ec1-40a2-a25b-f62f7cc76d89'
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36',
      'Accept': 'application/json', 'Origin': 'https://www.faceit.com', 'Referer': 'https://www.faceit.com/'}
RADAR_SRC = 'https://raw.githubusercontent.com/akiver/cs-demo-manager/main/static/images/maps/cs2/radars/{m}.png'


def faceit_recent(n=20):
    url = f'https://api.faceit.com/stats/v1/stats/time/users/{FACEIT_PLAYER_ID}/games/cs2?page=0&size={n}'
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


def ensure_radar(mapname):
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


def decompress(src, dst):
    import zstandard
    with open(src, 'rb') as f, open(dst, 'wb') as o:
        zstandard.ZstdDecompressor().copy_stream(f, o)


def map_of_demo(path):
    from demoparser2 import DemoParser
    return DemoParser(path).parse_header().get('map_name', 'unknown')


def run(target, player, out, keep):
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
        tmp = os.path.join(HERE, os.path.basename(src)[:-4])
        print(f'decompressing {os.path.basename(src)} ...'); decompress(src, tmp); dem = tmp
    mapname = map_of_demo(dem)
    ensure_radar(mapname)
    if not out:
        stamp = datetime.datetime.fromtimestamp(os.path.getmtime(src)).strftime('%Y-%m-%d')
        out = os.path.join(ROOT, f'{mapname[3:] if mapname.startswith("de_") else mapname}_{stamp}_performance.html')
    r = subprocess.run([sys.executable, os.path.join(HERE, 'performance_report.py'), dem, '--player', player, '--out', out], capture_output=True, text=True)
    print('\n'.join(l for l in r.stdout.splitlines() if 'Warning' not in l) or r.stderr[-800:])
    if tmp and not keep:
        os.remove(tmp)
    elif tmp:
        print(f'kept {tmp}')
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('target', help='latest | list | <faceit match id> | <path to .dem or .dem.zst>')
    ap.add_argument('--map', default=None, help='with latest: restrict to this map, e.g. de_nuke')
    ap.add_argument('--n', type=int, default=15)
    ap.add_argument('--player', default=PLAYER)
    ap.add_argument('--out', default=None)
    ap.add_argument('--keep-dem', action='store_true')
    a = ap.parse_args()
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
        out = run(r['demo'], a.player, a.out, a.keep_dem)
    else:
        out = run(a.target, a.player, a.out, a.keep_dem)
    print(f'report: {out}')


if __name__ == '__main__':
    main()
