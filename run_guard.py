"""run_guard.py — Runtime safety guards for long (6-10 day) continuous runs.

Provides three independent, defensive mechanisms that keep the pipeline
running when the environment degrades:

  1. disk_guard()  — abort a chunk gracefully if the runner is nearly full
     (GitHub runners have ~14 GB; ENOSPC mid-run is the #1 killer of long
     chains). Triggers emergency chain progress so the next chunk can try
     after the artifact upload frees space.
  2. DBMaintenance — periodic SQLite VACUUM + WAL checkpoint for a PaperDB,
     so the DB + WAL don't grow unbounded across 100k papers / many chunks.
  3. CircuitBreaker — per-platform fail-fast: if a platform errors N times
     in a window, skip it for the rest of this chunk so one flaky platform
     doesn't burn the whole 3-hour budget.

All guards are best-effort and degrade gracefully (never raise into the
pipeline). Used by research_hunter_v2-4.py.
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from threading import Lock
from typing import Dict, Optional

from logger import get_logger

log = get_logger(__name__)

# Abort if free disk drops below this absolute floor (bytes).
_DISK_FLOOR = int(os.environ.get("CI_DISK_FLOOR_GB", "2")) * (1024 ** 3)
_VACUUM_INTERVAL = int(os.environ.get("CI_VACUUM_EVERY", "15000"))  # papers


def disk_free_bytes(path: str = ".") -> int:
    """Free bytes on the filesystem holding `path`."""
    return shutil.disk_usage(path).free


def disk_guard(out_folder: Optional[str] = None) -> bool:
    """Return True if it's safe to continue, False if disk is critically low.

    When False, logs a loud warning and writes an emergency chain-progress
    note so the auto-chain step can re-dispatch (the artifact upload between
    chunks usually frees space). Never raises.
    """
    try:
        free = disk_free_bytes(str(out_folder or "."))
        if free < _DISK_FLOOR:
            log.warning("DISK LOW: %.2f GB free (< %.2f GB floor) — aborting chunk",
                        free / (1024 ** 3), _DISK_FLOOR / (1024 ** 3))
            if out_folder:
                try:
                    import json
                    from datetime import datetime
                    p = Path(out_folder)
                    p.mkdir(parents=True, exist_ok=True)
                    progress = {
                        "total_found": 0, "total_downloaded": 0, "new_this_run": 0,
                        "queries_exhausted": False, "limit_reached": False,
                        "disk_low": True,
                        "error": f"disk_low: {free/(1024**3):.2f}GB free",
                        "updated_at": datetime.now().isoformat(),
                    }
                    tmp = p / "_chain_progress.json.tmp"
                    tmp.write_text(json.dumps(progress, indent=2), encoding="utf-8")
                    os.replace(tmp, p / "_chain_progress.json")
                except Exception:
                    pass
            return False
        return True
    except Exception as e:
        log.warning("disk_guard check failed (continuing): %s", e)
        return True


def cleanup_old_logs(log_dir: str, keep_mb: int = 200):
    """Best-effort: delete oldest log files if the log dir exceeds keep_mb.
    Prevents log accumulation across a 10-day run from filling the disk.
    """
    try:
        d = Path(log_dir)
        if not d.is_dir():
            return
        files = sorted(d.glob("*.log*"), key=lambda f: f.stat().st_mtime)
        total = sum(f.stat().st_size for f in files)
        cap = keep_mb * 1024 * 1024
        removed = 0
        for f in files:
            if total <= cap:
                break
            sz = f.stat().st_size
            f.unlink(missing_ok=True)
            total -= sz
            removed += 1
        if removed:
            log.info("cleaned %d old log files (now %.1f MB)", removed,
                     total / (1024 ** 2))
    except Exception as e:
        log.warning("log cleanup failed: %s", e)


class DBMaintenance:
    """Periodic VACUUM + WAL checkpoint for a PaperDB to bound growth."""

    def __init__(self, db, vacuum_every: int = _VACUUM_INTERVAL):
        self.db = db
        self._interval = max(1, vacuum_every)
        self._since_vacuum = 0
        self._lock = Lock()

    def maybe_maintain(self, new_papers: int = 0):
        """Call after each batch. VACUUMs when enough new papers accumulate."""
        try:
            self._since_vacuum += max(0, new_papers)
            if self._since_vacuum >= self._interval:
                with self._lock:
                    self.db.vacuum()
                    self._since_vacuum = 0
                log.info("DB VACUUM done (every %d papers)", self._interval)
        except Exception as e:
            log.warning("DB maintenance failed: %s", e)


class CircuitBreaker:
    """Per-key fail-fast: after `threshold` failures in `window_s` seconds,
    the key is "tripped" and `allow(key)` returns False for the rest of the
    window. Used per-platform so one bad source can't consume the chunk."""

    def __init__(self, threshold: int = 5, window_s: float = 600.0):
        self.threshold = max(1, threshold)
        self.window = float(window_s)
        self._failures: Dict[str, list] = {}
        self._tripped: Dict[str, float] = {}
        self._lock = Lock()

    def record_failure(self, key: str):
        now = time.time()
        with self._lock:
            self._failures.setdefault(key, []).append(now)
            # drop old entries outside the window
            self._failures[key] = [t for t in self._failures[key]
                                  if now - t < self.window]
            if len(self._failures[key]) >= self.threshold:
                self._tripped[key] = now
                log.warning("CircuitBreaker TRIPPED for %r "
                            "(%d failures in %.0fs)", key,
                            len(self._failures[key]), self.window)

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            t = self._tripped.get(key)
            if t is not None and now - t < self.window:
                return False
            if t is not None and now - t >= self.window:
                # half-open: reset and let it try again
                self._tripped.pop(key, None)
                self._failures.pop(key, None)
            return True

    def reset(self, key: str = None):
        with self._lock:
            if key is None:
                self._tripped.clear()
                self._failures.clear()
            else:
                self._tripped.pop(key, None)
                self._failures.pop(key, None)
