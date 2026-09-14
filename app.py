"""CS2 Performance Report desktop app.

Drag compressed or raw demos onto the window (.dem.zst, .dem.gz, .dem.bz2, .zip containing a .dem, or a plain .dem).
Each one is decompressed, a performance report is generated, and the report opens in your browser.
No AI involved: everything is the deterministic pipeline in this folder.

Run:  pythonw app.py   (or double-click "CS2 Report.bat" in this folder)
"""
import os, sys, time, threading, queue, traceback, webbrowser, datetime, zipfile, gzip, bz2, shutil, subprocess
import tkinter as tk
from tkinter import ttk, filedialog

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, 'reports')
os.makedirs(ROOT, exist_ok=True)
sys.path.insert(0, HERE)
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAVE_DND = True
except Exception:
    HAVE_DND = False

ACCEPT = ('.zst', '.gz', '.bz2', '.zip', '.dem')


def decompress(src, workdir):
    """Return path to a .dem for the given input (decompressing into workdir if needed) and whether it is temporary."""
    low = src.lower()
    if low.endswith('.dem'):
        return src, False
    base = os.path.basename(src)
    if low.endswith('.zst'):
        import zstandard
        dst = os.path.join(workdir, base[:-4] if base.lower().endswith('.dem.zst') else base + '.dem')
        with open(src, 'rb') as f, open(dst, 'wb') as o:
            zstandard.ZstdDecompressor().copy_stream(f, o)
        return dst, True
    if low.endswith('.gz'):
        dst = os.path.join(workdir, base[:-3] if base.lower().endswith('.dem.gz') else base + '.dem')
        with gzip.open(src, 'rb') as f, open(dst, 'wb') as o:
            shutil.copyfileobj(f, o)
        return dst, True
    if low.endswith('.bz2'):
        dst = os.path.join(workdir, base[:-4] if base.lower().endswith('.dem.bz2') else base + '.dem')
        with bz2.open(src, 'rb') as f, open(dst, 'wb') as o:
            shutil.copyfileobj(f, o)
        return dst, True
    if low.endswith('.zip'):
        with zipfile.ZipFile(src) as z:
            names = [n for n in z.namelist() if n.lower().endswith('.dem')]
            if not names:
                raise ValueError('zip contains no .dem file')
            dst = os.path.join(workdir, os.path.basename(names[0]))
            with z.open(names[0]) as f, open(dst, 'wb') as o:
                shutil.copyfileobj(f, o)
            return dst, True
    raise ValueError(f'unsupported file type: {base}')


def build_report(src, log, on_progress=None):
    """Decompress, generate, return the report path."""
    import cs2report
    workdir = os.path.join(HERE, 'tmp'); os.makedirs(workdir, exist_ok=True)
    log(f'{os.path.basename(src)}: decompressing ...')
    dem, temp = decompress(src, workdir)
    try:
        mapname = cs2report.map_of_demo(dem)
        log(f'  map {mapname}; checking radar ...')
        cs2report.ensure_radar(mapname)
        stamp = datetime.datetime.fromtimestamp(os.path.getmtime(src)).strftime('%Y-%m-%d')
        short = mapname[3:] if mapname.startswith('de_') else mapname
        out = os.path.join(ROOT, f'{short}_{stamp}_performance.html')
        n = 2
        while os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(src) + 1 and _different_demo(out, dem):
            out = os.path.join(ROOT, f'{short}_{stamp}_{n}_performance.html'); n += 1
        log('  building report ...')
        lines = cs2report.run_with_progress([sys.executable, os.path.join(HERE, 'performance_report.py'), dem, '--player', cs2report.load_settings()['steam64'], '--out', out],
                                            on_progress=on_progress, on_line=lambda l: None)
        for l in lines:
            if ' -> ' in l: log('  ' + l.split(' -> ')[0])
            if l.startswith('built in'): log('  ' + l)
        return out
    finally:
        if temp and os.path.exists(dem):
            try: os.remove(dem)
            except OSError: pass


def _different_demo(out, dem):
    """True if an existing report was built from a different demo file (by name in the page header)."""
    try:
        with open(out, encoding='utf-8') as f:
            head = f.read(4000)
        return os.path.basename(dem) not in head
    except Exception:
        return False




def self_check():
    """Repair and verify the install on startup: folders, byte-code cache, module imports, packages, map data."""
    import importlib, compileall
    problems = []; notes = []
    for d in ('reports', 'maps', 'tmp'):
        os.makedirs(os.path.join(HERE, d), exist_ok=True)
    try:
        compileall.compile_dir(HERE, quiet=1, force=False)
        notes.append('byte-code cache rebuilt')
    except Exception as e:
        problems.append(f'could not compile modules: {e}')
    for pkg in ('demoparser2', 'zstandard', 'pandas', 'numpy', 'PIL'):
        try:
            importlib.import_module(pkg)
        except Exception as e:
            problems.append(f'missing package {pkg} ({e.__class__.__name__}). Run: pip install -r requirements.txt')
    for mod in ('cs2report', 'mistake_report', 'impact_report', 'positioning', 'performance_report'):
        try:
            importlib.import_module(mod)
        except Exception as e:
            problems.append(f'{mod}.py failed to import: {e.__class__.__name__}: {e}')
    if not os.path.exists(os.path.join(HERE, 'maps', 'offsets.json')):
        problems.append('maps/offsets.json is missing; radars will fall back to the demo silhouette')
    # clear leftovers from interrupted runs
    for f in os.listdir(os.path.join(HERE, 'tmp')):
        try: os.remove(os.path.join(HERE, 'tmp', f))
        except OSError: pass
    return problems, notes


class App:
    def __init__(self):
        self.root = TkinterDnD.Tk() if HAVE_DND else tk.Tk()
        self.root.title('CS2 Performance Report')
        self.root.geometry('900x640')
        self.root.minsize(640, 520)
        self.root.configure(bg='#111318')
        self.q = queue.Queue()
        self.jobs = queue.Queue()
        self.busy = False

        style = ttk.Style(self.root)
        try: style.theme_use('clam')
        except Exception: pass
        style.configure('TButton', padding=6)
        style.configure('TProgressbar', troughcolor='#1d2130', background='#40b060')

        top = tk.Frame(self.root, bg='#111318'); top.pack(fill='x', padx=16, pady=(14, 6))
        tk.Label(top, text='CS2 Performance Report', fg='#e6e6e6', bg='#111318', font=('Segoe UI', 15, 'bold')).pack(anchor='w')
        tk.Label(top, text='Drop match demos here: .dem.zst (FACEIT), .zip, .gz, .bz2 or .dem. Each becomes a report that opens in your browser.',
                 fg='#9aa0ad', bg='#111318', font=('Segoe UI', 9), wraplength=600, justify='left').pack(anchor='w', pady=(2, 0))

        self.drop = tk.Label(self.root, text='Drop demo files here' if HAVE_DND else 'Drag and drop needs the tkinterdnd2 package.\nUse the Browse button.',
                             fg='#cfd3dc', bg='#171a22', font=('Segoe UI', 13), relief='ridge', bd=2, height=5, cursor='hand2')
        self.drop.pack(fill='x', padx=16, pady=8)
        self.drop.bind('<Button-1>', lambda e: self.browse())
        if HAVE_DND:
            self.drop.drop_target_register(DND_FILES)
            self.drop.dnd_bind('<<Drop>>', self.on_drop)
            self.drop.dnd_bind('<<DragEnter>>', lambda e: self.drop.configure(bg='#1f2a3a'))
            self.drop.dnd_bind('<<DragLeave>>', lambda e: self.drop.configure(bg='#171a22'))

        # ---- player profile
        import cs2report
        self.settings = cs2report.load_settings()
        prow = tk.Frame(self.root, bg='#111318'); prow.pack(fill='x', padx=16, pady=(2, 6))
        tk.Label(prow, text='Your Steam profile', fg='#cfd3dc', bg='#111318', font=('Segoe UI', 9, 'bold')).pack(side='left')
        self.profile_var = tk.StringVar(value=self.settings.get('profile_url', ''))
        e = tk.Entry(prow, textvariable=self.profile_var, bg='#0d0f13', fg='#e6e6e6', insertbackground='#e6e6e6', relief='flat', width=44); e.pack(side='left', padx=8, ipady=3)
        e.bind('<Return>', lambda ev: self.save_profile())
        ttk.Button(prow, text='Save', command=self.save_profile).pack(side='left')
        ttk.Button(prow, text='Clear', command=self.clear_profile).pack(side='left', padx=(6, 0))
        self.who = tk.Label(prow, text='', fg='#8fd18f', bg='#111318', font=('Segoe UI', 9)); self.who.pack(side='left', padx=10)
        self.show_who()

        # ---- match list
        mrow = tk.Frame(self.root, bg='#111318'); mrow.pack(fill='x', padx=16)
        self.source = tk.StringVar(value='premier')
        for txt, val in (('Premier (local demos)', 'premier'), ('FACEIT', 'faceit')):
            tk.Radiobutton(mrow, text=txt, variable=self.source, value=val, command=self.refresh_matches, fg='#cfd3dc', bg='#111318', selectcolor='#1d2130', activebackground='#111318', activeforeground='#cfd3dc').pack(side='left')
        ttk.Button(mrow, text='Refresh', command=self.refresh_matches).pack(side='left', padx=8)
        ttk.Button(mrow, text='Analyse selected', command=self.analyse_selected).pack(side='left')
        ttk.Button(mrow, text='Browse...', command=self.browse).pack(side='left', padx=8)
        ttk.Button(mrow, text='Open reports folder', command=lambda: os.startfile(ROOT)).pack(side='left')
        tk.Label(mrow, text='Fetch by share code', fg='#9aa0ad', bg='#111318', font=('Segoe UI', 8)).pack(side='left', padx=(14, 2))
        self.code_var = tk.StringVar()
        ce = tk.Entry(mrow, textvariable=self.code_var, bg='#0d0f13', fg='#e6e6e6', insertbackground='#e6e6e6', relief='flat', width=32); ce.pack(side='left', ipady=2)
        ce.bind('<Return>', lambda ev: self.fetch_by_code())
        ttk.Button(mrow, text='Fetch', command=self.fetch_by_code).pack(side='left', padx=(4, 0))
        lbox = tk.Frame(self.root, bg='#111318'); lbox.pack(fill='x', padx=16, pady=(6, 0))
        self.matches = tk.Listbox(lbox, height=6, bg='#0d0f13', fg='#cfd3dc', selectbackground='#2a3550', selectmode='extended', font=('Consolas', 9), relief='flat', activestyle='none')
        self.matches.pack(side='left', fill='x', expand=True)
        sb = ttk.Scrollbar(lbox, command=self.matches.yview); sb.pack(side='right', fill='y'); self.matches.configure(yscrollcommand=sb.set)
        self.matches.bind('<Double-Button-1>', lambda ev: self.analyse_selected())
        self.match_rows = []
        row = tk.Frame(self.root, bg='#111318'); row.pack(fill='x', padx=16, pady=(6, 0))
        self.auto_var = tk.BooleanVar(value=False)
        tk.Checkbutton(row, text='Analyse fetched matches when they arrive', variable=self.auto_var, fg='#cfd3dc', bg='#111318', selectcolor='#1d2130',
                       activebackground='#111318', activeforeground='#cfd3dc').pack(side='left')
        self.open_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row, text='Open in browser when done', variable=self.open_var, fg='#cfd3dc', bg='#111318', selectcolor='#1d2130',
                       activebackground='#111318', activeforeground='#cfd3dc').pack(side='right')

        self.prog = ttk.Progressbar(self.root, mode='determinate', maximum=100); self.prog.pack(fill='x', padx=16, pady=(10, 2))
        self.status = tk.Label(self.root, text='', fg='#9aa0ad', bg='#111318', font=('Segoe UI', 9), anchor='w'); self.status.pack(fill='x', padx=16, pady=(0, 4))
        self.log = tk.Text(self.root, height=10, bg='#0d0f13', fg='#cfd3dc', insertbackground='#cfd3dc', font=('Consolas', 9), relief='flat', wrap='word')
        self.log.pack(fill='both', expand=True, padx=16, pady=(0, 14))
        self.log.configure(state='disabled')
        self.write(f'Ready. Reports are written to {ROOT}')
        threading.Thread(target=self.worker, daemon=True).start()
        threading.Thread(target=self.startup_check, daemon=True).start()
        self.pending = {}; self.settling = set()
        self.monitor_folders()
        self.root.after(300, self.refresh_matches)
        self.root.after(100, self.pump)

    def startup_check(self):
        problems, notes = self_check()
        if notes: self.write('Startup check: ' + ', '.join(notes) + '.')
        for p in problems: self.write('PROBLEM: ' + p)
        if problems:
            from tkinter import messagebox
            self.root.after(0, lambda: messagebox.showwarning('CS2 Performance Report', 'Startup found problems:\n\n' + '\n'.join(problems)))

    # ---- UI helpers
    def write(self, msg):
        self.q.put(msg)

    def pump(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg == '__busy__': self.prog['value'] = 0; self.prog_shown = 0; self.prog_state = None; self.status.configure(text='starting ...'); self.busy = True
                elif msg == '__idle__': self.prog['value'] = 100; self.busy = False
                elif isinstance(msg, tuple) and msg[0] == '__progress__':
                    _, pct, el, eta, text = msg
                    prev = getattr(self, 'prog_state', None)
                    step = (pct - prev['pct']) if prev and pct > prev['pct'] else 6.0            # size of the last checkpoint step
                    dur = (time.time() - prev['at']) if prev and pct > prev['pct'] else max(eta * step / max(100 - pct, 1), 0.5)  # how long that step took
                    shown = max(pct, getattr(self, 'prog_shown', 0))                               # never move backwards
                    self.prog_state = dict(pct=pct, el=el, eta=eta, text=text, at=time.time(), step=step, dur=max(dur, 0.5))
                    self.prog_shown = shown; self.prog['value'] = shown
                    self.status.configure(text=f"{shown:.0f}%  ·  {text}  ·  {el} s elapsed, about {eta} s left" if pct < 100 else f"done in {el} s")
                else:
                    self.log.configure(state='normal'); self.log.insert('end', msg + '\n'); self.log.see('end'); self.log.configure(state='disabled')
        except queue.Empty:
            pass
        # smooth the bar between progress messages: advance at the rate implied by the last estimate
        st = getattr(self, 'prog_state', None)
        if st and self.busy and st['pct'] < 100:
            import math
            since = time.time() - st['at']
            # approach the next checkpoint asymptotically (63% of the way after one typical step duration, never past it)
            target = st['pct'] + (1 - math.exp(-since / st['dur'])) * st['step']
            shown = max(getattr(self, 'prog_shown', 0), min(target, 99.0))
            self.prog_shown = shown; self.prog['value'] = shown
            left = max(st['eta'] - since, 0)
            self.status.configure(text=f"{shown:.0f}%  ·  {st['text']}  ·  {st['el'] + since:.0f} s elapsed, about {left:.0f} s left")
        self.root.after(100, self.pump)

    def on_drop(self, event):
        paths = self.root.tk.splitlist(event.data)
        self.drop.configure(bg='#171a22')
        self.enqueue(paths)

    def browse(self):
        paths = filedialog.askopenfilenames(title='Choose demo files', filetypes=[('CS2 demos', '*.zst *.zip *.gz *.bz2 *.dem'), ('All files', '*.*')],
                                            initialdir=os.path.expanduser('~/Downloads'))
        self.enqueue(paths)

    def show_who(self):
        s = self.settings
        if not s.get('steam64'):
            self.who.configure(text='No player set. Reports still build; they open on the first player.', fg='#9aa0ad'); return
        self.who.configure(text=f"{s.get('name') or '?'}  ({s.get('steam64')})  {'FACEIT linked' if s.get('faceit_id') else 'no FACEIT account'}", fg='#8fd18f')

    def clear_profile(self):
        import cs2report
        cs2report.clear_settings(); self.settings = cs2report.load_settings(); self.profile_var.set('')
        self.show_who(); self.write('Player cleared. Enter a Steam profile URL to set one.'); self.refresh_matches()

    def save_profile(self):
        text = self.profile_var.get().strip()
        if not text: return
        def job():
            import cs2report
            try:
                sid, name = cs2report.resolve_steam(text)
                fid = cs2report.faceit_id_for(sid)
                self.settings.update(steam64=sid, name=name, profile_url=text, faceit_id=fid)
                cs2report.save_settings(self.settings)
                self.write(f'Player set to {name} ({sid}). ' + ('FACEIT account found.' if fid else 'No FACEIT account for this Steam ID; the FACEIT list will be empty.'))
                self.root.after(0, self.show_who); self.root.after(0, self.refresh_matches)
            except Exception as e:
                self.write(f'Could not resolve that profile: {e}')
        threading.Thread(target=job, daemon=True).start()

    def refresh_matches(self):
        src = self.source.get()
        self.matches.delete(0, 'end'); self.match_rows = []
        self.matches.insert('end', 'loading ...')
        def job():
            import cs2report
            rows = []
            try:
                if src == 'premier':
                    for x in cs2report.premier_demos():
                        wl = 'W' if x['won'] else ('L' if x['won'] is False else ' ')
                        rows.append(dict(label=f"{x['date']:%Y-%m-%d %H:%M}  {x['map']:<12} {wl} {x['score']:<7} {x['mb']:4.0f} MB   ", status='Premier, demo on disk', path=x['path'], ok=True, key=os.path.normcase(os.path.abspath(x['path']))))
                    if not rows:
                        rows.append(dict(label="No Premier demos found. In CS2: Watch > Your matches > Download, then Refresh.", status='', path=None, ok=False, key=None))
                else:
                    for r in cs2report.faceit_recent(20):
                        on = os.path.exists(r['demo'])
                        rows.append(dict(label=f"{r['date']:%Y-%m-%d %H:%M}  {r['map']:<12} {'W' if r['won'] else 'L'} {r['score']:<8} K/D {r['kills']}/{r['deaths']}  ", status='demo on disk' if on else 'not downloaded: select to open the match room, then download the demo',
                                         path=r['demo'] if on else ('faceit:' + r['match_id'] + '|' + r['demo']), ok=on, key=os.path.normcase(os.path.abspath(r['demo']))))
            except Exception as e:
                msg = str(e)
                rows.append(dict(label=msg if any(k in msg for k in ('no player set', 'no FACEIT')) else f"Could not list matches: {msg}", status='', path=None, ok=False, key=None))
            def fill():
                self.matches.delete(0, 'end'); self.match_rows = rows
                for row in rows:
                    self.matches.insert('end', row['label'] + row['status'])
                    if not row['ok']: self.matches.itemconfig('end', fg='#8a8f9a')
            self.root.after(0, fill)
        threading.Thread(target=job, daemon=True).start()

    def analyse_selected(self):
        sel = [self.match_rows[i] for i in self.matches.curselection() if i < len(self.match_rows)]
        paths = [r['path'] for r in sel if r['ok'] and r['path']]
        pending = [r['path'] for r in sel if (not r['ok']) and r['path'] and str(r['path']).startswith('faceit:')]
        for p in pending:
            mid, expected = p[len('faceit:'):].split('|', 1)
            self.open_room_and_watch(mid, expected)
        if paths:
            self.enqueue(paths)
        elif not pending:
            self.write('Select one or more matches.')

    def monitor_folders(self):
        """Event-driven: the OS notifies us of changes in Downloads (FACEIT .dem.zst) and the game's replays folder
        (Premier .dem). No polling. A new or renamed demo is confirmed finished by waiting for its size to settle."""
        import cs2report, folder_watch
        self.pending = getattr(self, 'pending', {})   # expected path -> True for demos we should analyse on arrival
        folders = [(os.path.expanduser('~/Downloads'), lambda n: n.startswith('1-') and n.endswith('.dem.zst'), 'Downloads')]
        rep = cs2report.cs2_replays_dir()
        if rep: folders.append((rep, lambda n: n.startswith('match730_') and n.endswith('.dem'), 'the replays folder'))
        def make_cb(folder, match, label):
            def cb(action, name):
                if not match(name): return
                full = os.path.normcase(os.path.abspath(os.path.join(folder, name)))
                if action in ('added', 'renamed_to', 'modified'):
                    if full in self.settling: return
                    self.settling.add(full)
                    def confirm():
                        size = folder_watch.settled(full, quiet=1.5, timeout=1800)
                        self.settling.discard(full)
                        if size is None: return
                        self.root.after(0, lambda f=full: self.mark_downloaded(f, True))
                        was_pending = self.pending.pop(full, None)
                        if was_pending and self.auto_var.get():
                            self.write(f'Demo ready in {label}: {name} ({size / 1e6:.0f} MB). Analysing, as you fetched it from here.'); self.enqueue([full])
                        else:
                            self.write(f'Demo ready in {label}: {name} ({size / 1e6:.0f} MB). Marked as downloaded; select it and press Analyse when you want the report.')
                    threading.Thread(target=confirm, daemon=True).start()
                elif action == 'removed':
                    self.root.after(0, lambda f=full: self.mark_downloaded(f, False))
            return cb
        self.settling = set()
        self.watch_stops = [folder_watch.watch(folder, make_cb(folder, match, label)) for folder, match, label in folders]
        self.write('Watching Downloads' + (' and the replays folder' if rep else '') + ' for new demos.')

    def mark_downloaded(self, full, present=True):
        """Update just the row that refers to this demo (status text, colour, payload). Selection and scroll position are kept.
        A Premier demo that is not in the list yet is inserted at the top."""
        key = os.path.normcase(os.path.abspath(full))
        sel = set(self.matches.curselection()); top = self.matches.yview()[0]
        for i, row in enumerate(self.match_rows):
            if row.get('key') == key:
                if present:
                    row['ok'] = True; row['status'] = 'demo on disk' if str(row['path']).startswith('faceit:') or 'Premier' not in row['status'] else row['status']
                    if str(row['path']).startswith('faceit:'): row['path'] = full
                    if 'Premier' in row['status']: row['status'] = 'Premier, demo on disk'
                else:
                    row['ok'] = False; row['status'] = 'demo removed'
                self.matches.delete(i); self.matches.insert(i, row['label'] + row['status'])
                self.matches.itemconfig(i, fg='#cfd3dc' if row['ok'] else '#8a8f9a')
                for s in sel: self.matches.selection_set(s)
                self.matches.yview_moveto(top)
                return True
        if present and os.path.basename(full).startswith('match730_') and self.source.get() == 'premier':
            import cs2report
            info = cs2report.premier_info(full, self.settings.get('steam64')); mapname = ''
            try:
                from demoparser2 import DemoParser
                mapname = DemoParser(full).parse_header().get('map_name', '')
            except Exception:
                pass
            wl = 'W' if info.get('won') else ('L' if info.get('won') is False else ' ')
            date = info.get('time') or datetime.datetime.fromtimestamp(os.path.getmtime(full))
            row = dict(label=f"{date:%Y-%m-%d %H:%M}  {mapname:<12} {wl} {info.get('score_text', ''):<7} {os.path.getsize(full) / 1e6:4.0f} MB   ", status='Premier, demo on disk', path=full, ok=True, key=key)
            self.match_rows.insert(0, row); self.matches.insert(0, row['label'] + row['status'])
            for s in sel: self.matches.selection_set(s + 1)
            self.matches.yview_moveto(top)
            return True
        return False

    def fetch_by_code(self):
        code = self.code_var.get().strip()
        if code: self.download_premier(code)

    def download_premier(self, code):
        """Have the game download a Premier demo by share code; the folder watcher analyses it when it lands."""
        import cs2report
        try:
            mid, oid, tok = cs2report.decode_sharecode(code)
        except ValueError as e:
            self.write(str(e)); return
        expected = cs2report.expected_premier_path(mid, oid, tok)
        if expected:
            self.pending = getattr(self, 'pending', {}); self.pending[os.path.normcase(os.path.abspath(expected))] = True
        cmd, url = cs2report.cs2_download_command(code)
        try:
            self.root.clipboard_clear(); self.root.clipboard_append(cmd)
        except Exception:
            pass
        try:
            os.startfile(url)
            self.write('Asked Steam to start CS2 with "' + cmd + '". If CS2 is already running, Steam ignores the command: open the CS2 console and paste (the command is on your clipboard). The demo appears in the replays folder and the list updates' + (' and it is analysed automatically.' if self.auto_var.get() else '; then select it and press Analyse.'))
        except Exception as e:
            self.write('Could not launch through Steam (' + str(e) + '). Paste this into the CS2 console: ' + cmd)

    def open_room_and_watch(self, match_id, expected):
        """FACEIT only hands demos to a logged-in browser session: open the room, and mark the demo as pending so the
        folder watcher analyses it the moment the download finishes."""
        url = f'https://www.faceit.com/en/cs2/room/{match_id}'
        webbrowser.open(url)
        self.pending = getattr(self, 'pending', {}); self.pending[os.path.normcase(os.path.abspath(expected))] = True
        self.write(f'Opened the FACEIT match room in your browser. Download the demo there; the row updates when {os.path.basename(expected)} lands in Downloads' + (' and it will be analysed automatically.' if self.auto_var.get() else '. Then select it and press Analyse.'))

    def enqueue(self, paths):
        for p in paths:
            p = p.strip('{}')
            if not os.path.isfile(p):
                continue
            if not p.lower().endswith(ACCEPT):
                self.write(f'skipped {os.path.basename(p)}: not a demo'); continue
            self.jobs.put(p); self.write(f'queued {os.path.basename(p)}')

    # ---- background worker
    def worker(self):
        while True:
            src = self.jobs.get()
            self.write('__busy__')
            try:
                out = build_report(src, self.write, on_progress=lambda pct, el, eta, text: self.q.put(('__progress__', pct, el, eta, text)))
                self.write(f'  done: {out}')
                if self.open_var.get():
                    webbrowser.open('file:///' + out.replace('\\', '/'))
            except Exception as e:
                self.write('  FAILED: ' + str(e)); self.write(traceback.format_exc().strip().splitlines()[-1])
            finally:
                self.write('__idle__')


if __name__ == '__main__':
    try:
        App().root.mainloop()
    except Exception:
        import tkinter.messagebox as mb
        try:
            r = tk.Tk(); r.withdraw(); mb.showerror('CS2 Performance Report failed to start', traceback.format_exc()[-2500:])
        except Exception:
            pass
        raise
