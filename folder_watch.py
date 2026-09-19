"""Event-driven folder watching on Windows via ReadDirectoryChangesW (ctypes, no dependencies).

    stop = watch(r"C:\\Users\\me\\Downloads", callback)   # callback(action, filename) on the watcher thread
    stop()                                               # to end it

Actions: 'added', 'removed', 'modified', 'renamed_from', 'renamed_to'. Falls back to a 3 s poller when the OS call
is unavailable (non-Windows), so callers get the same callback either way.
"""
from __future__ import annotations
from typing import Callable
WatchCallback = Callable[[str, str], None]      # (action, file name); action is 'added', 'removed', 'modified', 'renamed_from' or 'renamed_to'
import os, sys, threading, time

ACTIONS = {1: 'added', 2: 'removed', 3: 'modified', 4: 'renamed_from', 5: 'renamed_to'}


def _watch_windows(path: str, callback: WatchCallback, stop_event: threading.Event) -> None:
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.windll.kernel32
    FILE_LIST_DIRECTORY = 0x0001
    FILE_SHARE = 0x1 | 0x2 | 0x4
    OPEN_EXISTING = 3
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    NOTIFY = 0x1 | 0x2 | 0x8 | 0x10   # file name, dir name, size, last write
    h = k32.CreateFileW(path, FILE_LIST_DIRECTORY, FILE_SHARE, None, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, None)
    if h == wintypes.HANDLE(-1).value:
        raise OSError(f'cannot open {path} for watching')
    buf = ctypes.create_string_buffer(64 * 1024)
    n = wintypes.DWORD()
    try:
        while not stop_event.is_set():
            ok = k32.ReadDirectoryChangesW(h, buf, len(buf), False, NOTIFY, ctypes.byref(n), None, None)
            if not ok:
                time.sleep(1); continue
            off = 0
            while True:
                next_off, action, name_len = ctypes.cast(ctypes.addressof(buf) + off, ctypes.POINTER(wintypes.DWORD * 3)).contents
                name = ctypes.wstring_at(ctypes.addressof(buf) + off + 12, name_len // 2)
                try:
                    callback(ACTIONS.get(action, str(action)), name)
                except Exception:
                    pass
                if not next_off: break
                off += next_off
    finally:
        k32.CloseHandle(h)


def _watch_poll(path: str, callback: WatchCallback, stop_event: threading.Event, interval: float = 3) -> None:
    def snap() -> dict[str, int]:
        try:
            return {f: os.path.getsize(os.path.join(path, f)) for f in os.listdir(path)}
        except OSError:
            return {}
    prev = snap()
    while not stop_event.is_set():
        time.sleep(interval)
        cur = snap()
        for f in cur:
            if f not in prev: callback('added', f)
            elif cur[f] != prev[f]: callback('modified', f)
        for f in prev:
            if f not in cur: callback('removed', f)
        prev = cur


def watch(path: str, callback: WatchCallback) -> Callable[[], None] | None:
    """Start watching `path`; returns a stop() function. Uses OS notifications on Windows, polling elsewhere."""
    stop_event = threading.Event()
    def run() -> None:
        if sys.platform == 'win32':
            try:
                _watch_windows(path, callback, stop_event); return
            except Exception:
                pass
        _watch_poll(path, callback, stop_event)
    threading.Thread(target=run, daemon=True, name=f'watch:{os.path.basename(path)}').start()
    return stop_event.set


def settled(path: str, quiet: float = 1.5, timeout: float = 600) -> int | None:
    """Block until the file's size has been unchanged for `quiet` seconds (a finished write), or timeout. Returns final size or None."""
    t0 = time.time(); last = -1; since = time.time()
    while time.time() - t0 < timeout:
        try:
            size = os.path.getsize(path)
        except OSError:
            size = -1
        if size == last and size > 0 and time.time() - since >= quiet:
            return size
        if size != last:
            last = size; since = time.time()
        time.sleep(0.25)
    return None
