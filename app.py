"""CS2 Performance Report desktop app.

Drag compressed or raw demos onto the window (.dem.zst, .dem.gz, .dem.bz2, .zip containing a .dem, or a plain .dem).
Each one is decompressed, a performance report is generated, and the report opens in your browser.
No AI involved: everything is the deterministic pipeline in this folder.

Run:  pythonw app.py   (or double-click "CS2 Report.bat" in this folder)
"""
import os, sys, threading, queue, traceback, webbrowser, datetime, zipfile, gzip, bz2, shutil, subprocess
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

PLAYER = '76561198063294402'
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


def build_report(src, log):
    """Decompress, generate, return the report path."""
    import cs2report
    workdir = HERE
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
        log('  parsing demo and building report (20 to 60 s) ...')
        r = subprocess.run([sys.executable, os.path.join(HERE, 'performance_report.py'), dem, '--player', PLAYER, '--out', out],
                           capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        lines = [l for l in r.stdout.splitlines() if 'Warning' not in l]
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip()[-1500:] or 'report script failed')
        for l in lines[:1]:
            log('  ' + l.split(' -> ')[0])
        return out
    finally:
        if temp and os.path.exists(dem):
            os.remove(dem)


def _different_demo(out, dem):
    """True if an existing report was built from a different demo file (by name in the page header)."""
    try:
        with open(out, encoding='utf-8') as f:
            head = f.read(4000)
        return os.path.basename(dem) not in head
    except Exception:
        return False


class App:
    def __init__(self):
        self.root = TkinterDnD.Tk() if HAVE_DND else tk.Tk()
        self.root.title('CS2 Performance Report')
        self.root.geometry('640x460')
        self.root.minsize(520, 380)
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

        row = tk.Frame(self.root, bg='#111318'); row.pack(fill='x', padx=16)
        ttk.Button(row, text='Browse...', command=self.browse).pack(side='left')
        ttk.Button(row, text='Latest FACEIT match', command=self.latest).pack(side='left', padx=8)
        ttk.Button(row, text='Open reports folder', command=lambda: os.startfile(ROOT)).pack(side='left')
        self.open_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row, text='Open in browser when done', variable=self.open_var, fg='#cfd3dc', bg='#111318', selectcolor='#1d2130',
                       activebackground='#111318', activeforeground='#cfd3dc').pack(side='right')

        self.prog = ttk.Progressbar(self.root, mode='indeterminate'); self.prog.pack(fill='x', padx=16, pady=(10, 4))
        self.log = tk.Text(self.root, height=10, bg='#0d0f13', fg='#cfd3dc', insertbackground='#cfd3dc', font=('Consolas', 9), relief='flat', wrap='word')
        self.log.pack(fill='both', expand=True, padx=16, pady=(0, 14))
        self.log.configure(state='disabled')
        self.write(f'Ready. Reports are written to {ROOT}')
        threading.Thread(target=self.worker, daemon=True).start()
        self.root.after(100, self.pump)

    # ---- UI helpers
    def write(self, msg):
        self.q.put(msg)

    def pump(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg == '__busy__': self.prog.start(12); self.busy = True
                elif msg == '__idle__': self.prog.stop(); self.busy = False
                else:
                    self.log.configure(state='normal'); self.log.insert('end', msg + '\n'); self.log.see('end'); self.log.configure(state='disabled')
        except queue.Empty:
            pass
        self.root.after(100, self.pump)

    def on_drop(self, event):
        paths = self.root.tk.splitlist(event.data)
        self.drop.configure(bg='#171a22')
        self.enqueue(paths)

    def browse(self):
        paths = filedialog.askopenfilenames(title='Choose demo files', filetypes=[('CS2 demos', '*.zst *.zip *.gz *.bz2 *.dem'), ('All files', '*.*')],
                                            initialdir=os.path.expanduser('~/Downloads'))
        self.enqueue(paths)

    def latest(self):
        def job():
            import cs2report
            rows = cs2report.faceit_recent(5)
            r = rows[0]
            self.write(f"Latest FACEIT match: {r['date']:%Y-%m-%d %H:%M} {r['map']} {'won' if r['won'] else 'lost'} {r['score']}")
            if not os.path.exists(r['demo']):
                self.write(f"  demo not in Downloads. Download it from https://www.faceit.com/en/cs2/room/{r['match_id']} then drop it here.")
                return
            self.enqueue([r['demo']])
        threading.Thread(target=job, daemon=True).start()

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
                out = build_report(src, self.write)
                self.write(f'  done: {out}')
                if self.open_var.get():
                    webbrowser.open('file:///' + out.replace('\\', '/'))
            except Exception as e:
                self.write('  FAILED: ' + str(e)); self.write(traceback.format_exc().strip().splitlines()[-1])
            finally:
                self.write('__idle__')


if __name__ == '__main__':
    App().root.mainloop()
