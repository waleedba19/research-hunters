#!/usr/bin/env python3
"""Tests for scripts/collect_diagnostics.py — the daily_learn status engine.

Verifies the scanner correctly detects + dedupes errors/warnings/exceptions
in research-run logs and never crashes the job. Run via: python tests/test_diagnostics.py
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "collect_diagnostics.py"


def _run(logdir: str, out: str) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--log-dirs", logdir, "--repo-root", str(REPO), "--out", out],
        capture_output=True, text=True, timeout=120,
    )
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _make_log(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_detects_and_dedupes_errors():
    d = tempfile.mkdtemp()
    _make_log(Path(d) / "leg_RQ1/data/logs/run.log", [
        "2026-08-14 14:33:27 [INFO] Loaded 93 platforms",
        "2026-08-14 14:34:10 [WARNING] DOAB: connection timeout, retrying",
        "2026-08-14 14:35:00 [ERROR] AttributeError: 'list' object has no attribute 'get'",
        "2026-08-14 14:35:01 [ERROR] AttributeError: 'list' object has no attribute 'get'",
        "2026-08-14 14:36:00 [WARNING] Batch 2: 3 papers hung >120s abandoning",
    ])
    out = os.path.join(d, "report.md")
    rc, text = _run(d, out)
    assert rc == 0, f"scanner exited {rc}: {text}"
    report = Path(out).read_text(encoding="utf-8")
    # The duplicate AttributeError should be counted once (1 unique, count 2).
    assert "AttributeError" in report, "error not detected"
    assert "timeout" in report, "warning not detected"
    assert "abandon" in report.lower(), "hang warning not detected"
    assert "Offline System Health" in report, "offline health section missing"
    print("test_detects_and_dedupes_errors: PASS")


def test_never_crashes_on_empty():
    d = tempfile.mkdtemp()
    out = os.path.join(d, "report.md")
    rc, text = _run(d, out)
    assert rc == 0, f"scanner should not crash on empty dir: {text}"
    report = Path(out).read_text(encoding="utf-8")
    assert "No log files found" in report or "No errors" in report
    print("test_never_crashes_on_empty: PASS")


def test_never_crashes_on_garbage():
    d = tempfile.mkdtemp()
    # Unreadable / binary-ish junk should not crash the scanner.
    _make_log(Path(d) / "bad/data/logs/x.log", [
        "\x00\x01\x02 binary \x00 junk",
        "not a real log line at all",
    ])
    out = os.path.join(d, "report.md")
    rc, text = _run(d, out)
    assert rc == 0, f"scanner crashed on garbage: {text}"
    assert Path(out).exists()
    print("test_never_crashes_on_garbage: PASS")


def main():
    test_detects_and_dedupes_errors()
    test_never_crashes_on_empty()
    test_never_crashes_on_garbage()
    print("\n============================================================")
    print("  ALL DIAGNOSTICS TESTS PASSED")
    print("============================================================")


if __name__ == "__main__":
    main()
