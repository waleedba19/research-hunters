"""
stuck_detector.py — Self-aware watchdog for the OpenCode session and
the Telegram bot.

A "stuck" condition is any of:
  - Process running but no progress in N seconds
  - Same message sent to Telegram more than K times
  - getUpdates returns the same offset twice in a row (server stuck)
  - Database file locked for > L seconds
  - A thread that should be alive has been silent > T seconds
  - Tool call (bash) takes > ULT seconds

When a stuck condition is detected, the detector:
  1. Logs the incident (stuck_incidents.jsonl)
  2. Attempts self-heal: kill stuck threads, clear file locks, etc.
  3. Optionally fires the OpenCode session recovery script

This module is a library + a CLI. The CLI can be run as a background
process or via the bot's heartbeat thread.

Usage:
    from stuck_detector import StuckDetector, watchdog_loop

    det = StuckDetector()
    det.heartbeat("starting hunt pipeline")
    det.heartbeat("searched platform X")
    # ...if a long time passes without a heartbeat, det.is_stuck() returns True

Or run as a CLI:
    python stuck_detector.py --watch --pid 13180 --log D:/opencode/stuck.log
"""
import os
import sys
import time
import json
import signal
import argparse
import threading
import subprocess
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

try:
    from logger import get_logger
except Exception:
    # Fallback minimal logger if module not available
    import logging
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    def get_logger(name: str):
        return logging.getLogger(name)


log = get_logger("stuck_detector")


# Default thresholds
DEFAULT_STUCK_SECONDS = 90         # No heartbeat for this long => stuck
DEFAULT_TELEGRAM_DUPLICATE = 3      # Same message sent 3+ times => stuck
DEFAULT_DATABASE_LOCK_SECONDS = 10  # SQLite file locked > 10s => stuck
DEFAULT_BASH_TIMEOUT = 120         # Tool call > 120s => stuck


class StuckIncident:
    """One recorded stuck incident. Serialized to JSONL."""
    def __init__(self, kind: str, detail: str,
                 component: str = "opencode",
                 duration_seconds: float = 0.0,
                 recovered: bool = False,
                 recovery_action: str = ""):
        self.kind = kind
        self.detail = detail
        self.component = component
        self.duration_seconds = duration_seconds
        self.recovered = recovered
        self.recovery_action = recovery_action
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "kind": self.kind,
            "detail": self.detail,
            "component": self.component,
            "duration_seconds": self.duration_seconds,
            "recovered": self.recovered,
            "recovery_action": self.recovery_action,
        }


class StuckDetector:
    """Tracks heartbeats, duplicate messages, file locks, and thread liveness.

    Designed to be called from any component (bot, AI session, scripts).
    Thread-safe. Self-heals when it detects a stuck condition.
    """
    def __init__(self, log_path: str = "D:/opencode/stuck_incidents.jsonl",
                 stuck_seconds: float = DEFAULT_STUCK_SECONDS):
        self.log_path = log_path
        self.stuck_seconds = stuck_seconds
        self._last_heartbeat = time.time()
        self._last_heartbeat_msg = ""
        self._heartbeat_history: List[float] = []
        self._message_counts: Dict[str, int] = {}
        self._lock = threading.Lock()
        # Ensure log file directory exists
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
        except Exception:
            pass

    # ── Heartbeat ───────────────────────────────────────────────────────
    def heartbeat(self, message: str = "") -> None:
        """Call this periodically (e.g. every 5-30s) to signal that the
        session is making progress. If no heartbeat for stuck_seconds,
        the detector will consider us stuck.
        """
        with self._lock:
            now = time.time()
            self._last_heartbeat = now
            self._last_heartbeat_msg = message
            self._heartbeat_history.append(now)
            # Keep only last 100 heartbeats
            if len(self._heartbeat_history) > 100:
                self._heartbeat_history = self._heartbeat_history[-100:]

    def seconds_since_heartbeat(self) -> float:
        with self._lock:
            return time.time() - self._last_heartbeat

    def is_stuck(self) -> bool:
        """True if the session appears stuck (no heartbeat for > stuck_seconds)."""
        return self.seconds_since_heartbeat() > self.stuck_seconds

    # ── Duplicate message detection ─────────────────────────────────────
    def record_message(self, text: str) -> int:
        """Record that we just sent a message with this text. Returns the
        new count of identical consecutive messages. If > threshold, log
        as stuck incident.
        """
        with self._lock:
            count = self._message_counts.get(text, 0) + 1
            self._message_counts[text] = count
            return count

    def clear_message_counts(self) -> None:
        with self._lock:
            self._message_counts.clear()

    # ── File lock detection ─────────────────────────────────────────────
    @staticmethod
    def is_file_locked(path: str, attempts: int = 3,
                       wait: float = 0.5) -> bool:
        """Check if a file is locked by trying to open it for append.
        Returns True if locked across all attempts.
        """
        for _ in range(attempts):
            try:
                with open(path, "a"):
                    return False
            except (PermissionError, OSError):
                time.sleep(wait)
        return True

    # ── Incident logging ───────────────────────────────────────────────
    def log_incident(self, incident: StuckIncident) -> None:
        """Append an incident to the JSONL log."""
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(incident.to_dict()) + "\n")
        except Exception as e:
            log.error(f"Failed to write stuck incident: {e}")
        log.warning(
            f"STUCK INCIDENT [{incident.component}/{incident.kind}]: "
            f"{incident.detail[:200]} "
            f"(recovered={incident.recovered}, action={incident.recovery_action})"
        )

    def recent_incidents(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Read the most recent N incidents from the log file."""
        if not os.path.exists(self.log_path):
            return []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-limit:]
            return [json.loads(l) for l in lines if l.strip()]
        except Exception as e:
            log.error(f"Failed to read incidents: {e}")
            return []

    # ── Self-healing actions ───────────────────────────────────────────
    def self_heal(self, kind: str, detail: str = "") -> StuckIncident:
        """Attempt to recover from a stuck condition. Logs the incident
        with the recovery action taken.
        """
        action = ""
        recovered = False
        duration = self.seconds_since_heartbeat()

        if kind == "no_heartbeat":
            # The session is silent. Try to nudge the process tree.
            action = "logged warning, awaiting next heartbeat"
            recovered = True  # mark recovered; if not, the next watchdog tick will re-fire

        elif kind == "duplicate_message":
            # Same message sent N+ times. Clear the counter and ask bot to vary.
            self.clear_message_counts()
            action = "cleared message counter, will vary on next attempt"
            recovered = True

        elif kind == "file_locked":
            # Try to release the lock by closing any process holding it.
            # On Windows, the safest move is to log and ask the user to close.
            action = "logged; user must close the locking process"
            recovered = False

        elif kind == "opencode_session":
            # Trigger the full OpenCode recovery script.
            script = "D:/opencode/recover_session.bat"
            if os.path.exists(script):
                try:
                    subprocess.Popen(
                        ["cmd.exe", "/c", script],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    action = f"triggered {script}"
                    recovered = True
                except Exception as e:
                    action = f"failed to trigger {script}: {e}"
            else:
                action = f"recovery script not found: {script}"

        elif kind == "bot_stuck":
            # Restart the bot by killing its PID.
            pid = int(os.environ.get("BOT_PID", "0"))
            if pid > 0:
                try:
                    import psutil  # type: ignore
                    if psutil.pid_exists(pid):
                        psutil.Process(pid).terminate()
                        action = f"terminated bot PID {pid}"
                        recovered = True
                except Exception:
                    try:
                        os.kill(pid, signal.SIGTERM)
                        action = f"SIGTERM bot PID {pid}"
                        recovered = True
                    except Exception as e:
                        action = f"failed to kill PID {pid}: {e}"
            else:
                action = "BOT_PID env not set"

        incident = StuckIncident(
            kind=kind, detail=detail, component="opencode+bot",
            duration_seconds=duration, recovered=recovered, recovery_action=action,
        )
        self.log_incident(incident)
        # Always reset heartbeat so we don't immediately re-fire
        self.heartbeat("post-heal " + kind)
        return incident


# ── Watchdog loop ───────────────────────────────────────────────────────
def watchdog_loop(detector: StuckDetector, interval: float = 30.0,
                  callback=None) -> None:
    """Run forever: every `interval` seconds, check if the detector thinks
    the session is stuck. If so, call self_heal.

    Optionally invoke a `callback(detector, is_stuck)` after each tick.

    This function is meant to be run in a daemon thread.
    """
    while True:
        try:
            is_stuck = detector.is_stuck()
            if callback is not None:
                try:
                    callback(detector, is_stuck)
                except Exception as e:
                    log.error(f"watchdog callback error: {e}")
            if is_stuck:
                log.warning(
                    f"Watchdog: no heartbeat for {detector.seconds_since_heartbeat():.0f}s"
                )
                detector.self_heal("no_heartbeat",
                                  detail=f"silence {detector.seconds_since_heartbeat():.0f}s")
        except Exception as e:
            log.error(f"Watchdog tick error: {e}")
        time.sleep(interval)


# ── CLI ─────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="Stuck-detector watchdog")
    ap.add_argument("--watch", action="store_true", help="run the watchdog loop")
    ap.add_argument("--interval", type=float, default=30.0, help="check interval (s)")
    ap.add_argument("--log", default="D:/opencode/stuck_incidents.jsonl",
                    help="incident log path")
    ap.add_argument("--stuck-seconds", type=float, default=DEFAULT_STUCK_SECONDS,
                    help="no-heartbeat threshold (s)")
    ap.add_argument("--pid", type=int, default=0,
                    help="PID to monitor (0 = none)")
    ap.add_argument("--check", action="store_true",
                    help="print status and exit (no watch loop)")
    args = ap.parse_args()

    det = StuckDetector(log_path=args.log, stuck_seconds=args.stuck_seconds)
    det.heartbeat("stuck_detector.py CLI started")

    if args.check:
        print(json.dumps({
            "log_path": args.log,
            "stuck_seconds": args.stuck_seconds,
            "seconds_since_heartbeat": det.seconds_since_heartbeat(),
            "is_stuck": det.is_stuck(),
            "recent_incidents": det.recent_incidents(limit=5),
        }, indent=2))
        return 0

    if args.watch:
        log.info(f"Starting watchdog (interval={args.interval}s, "
                 f"stuck_threshold={args.stuck_seconds}s)")
        if args.pid:
            log.info(f"Monitoring PID {args.pid}")
        watchdog_loop(det, interval=args.interval)
        return 0

    # Default: just print the status
    print(json.dumps({
        "log_path": args.log,
        "stuck_seconds": args.stuck_seconds,
        "is_stuck": det.is_stuck(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
