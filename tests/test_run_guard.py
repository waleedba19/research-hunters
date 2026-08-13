"""test_run_guard.py — Tests for runtime safety guards (long-run stability).

Covers: disk_guard (low-disk abort + emergency progress), cleanup_old_logs,
DBMaintenance (periodic VACUUM), CircuitBreaker (trip + half-open reset),
and error_handler TransientHTTPError retry behavior.

Run:  python3 tests/test_run_guard.py
No network, no ollama.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import run_guard  # noqa: E402
from error_handler import retry, TransientHTTPError  # noqa: E402
from paper_db import PaperDB  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name}  {detail}")


def test_disk_guard_ok():
    print("\n[1] disk_guard passes with free space")
    d = tempfile.mkdtemp()
    ok = run_guard.disk_guard(d)
    check("disk_guard True when free", ok is True)


def test_disk_guard_low():
    print("\n[2] disk_guard aborts on low disk + emits emergency progress")
    d = tempfile.mkdtemp()
    with mock.patch.object(run_guard, "disk_free_bytes", return_value=100 * 1024):
        ok = run_guard.disk_guard(d)
    check("disk_guard False when low", ok is False)
    prog = Path(d) / "_chain_progress.json"
    check("emergency progress written", prog.exists())
    if prog.exists():
        data = json.loads(prog.read_text())
        check("disk_low flag set", data.get("disk_low") is True)


def test_disk_guard_never_raises():
    print("\n[3] disk_guard never raises on bad input")
    ok = run_guard.disk_guard("/nonexistent/path/xyz")
    check("returns bool (True on err)", isinstance(ok, bool))


def test_cleanup_old_logs():
    print("\n[4] cleanup_old_logs removes oldest over cap")
    d = tempfile.mkdtemp()
    # create 5 files of ~50KB, cap at 100KB → keep newest ~2
    for i in range(5):
        f = Path(d) / f"mod_{i}.log"
        f.write_text("x" * 50000)
        time.sleep(0.01)
    run_guard.cleanup_old_logs(d, keep_mb=0)  # ~0 MB cap → keep near nothing
    remaining = list(Path(d).glob("*.log"))
    # at least some removed
    check("old logs removed", len(remaining) < 5, str(len(remaining)))


def test_db_maintenance_vacuum():
    print("\n[5] DBMaintenance triggers VACUUM after threshold")
    d = tempfile.mkdtemp()
    db = PaperDB(d)
    for i in range(20):
        db.upsert_paper({"title": f"P{i}", "doi": f"10.v/{i}"})
    vacuums = [0]
    orig = db.vacuum
    def counted():
        vacuums[0] += 1
        orig()
    db.vacuum = counted
    m = run_guard.DBMaintenance(db, vacuum_every=10)
    m.maybe_maintain(new_papers=12)  # > 10 → should vacuum
    check("vacuum triggered once", vacuums[0] == 1, str(vacuums[0]))
    m.maybe_maintain(new_papers=5)  # < 10 since reset → no vacuum
    check("vacuum not re-triggered", vacuums[0] == 1, str(vacuums[0]))
    m.maybe_maintain(new_papers=5)  # now 10 → vacuum
    check("vacuum triggered again", vacuums[0] == 2, str(vacuums[0]))
    db.close()


def test_circuit_breaker_trip():
    print("\n[6] CircuitBreaker trips after threshold failures")
    cb = run_guard.CircuitBreaker(threshold=3, window_s=60)
    check("allowed initially", cb.allow("pubmed") is True)
    cb.record_failure("pubmed")
    cb.record_failure("pubmed")
    check("allowed at 2 fails", cb.allow("pubmed") is True)
    cb.record_failure("pubmed")
    check("tripped at 3 fails", cb.allow("pubmed") is False)
    check("other key unaffected", cb.allow("core") is True)


def test_circuit_breaker_half_open():
    print("\n[7] CircuitBreaker half-open reset after window")
    cb = run_guard.CircuitBreaker(threshold=2, window_s=0.1)
    cb.record_failure("x")
    cb.record_failure("x")
    check("tripped", cb.allow("x") is False)
    time.sleep(0.15)
    check("allowed after window (half-open)", cb.allow("x") is True)


def test_circuit_breaker_reset():
    print("\n[8] CircuitBreaker explicit reset")
    cb = run_guard.CircuitBreaker(threshold=2)
    cb.record_failure("a"); cb.record_failure("a")
    cb.reset("a")
    check("reset allows again", cb.allow("a") is True)


def test_retry_transient_http():
    print("\n[9] retry() retries TransientHTTPError (429/5xx)")
    calls = [0]

    @retry(max_attempts=3, base_delay=0.01)
    def flaky():
        calls[0] += 1
        if calls[0] < 3:
            raise TransientHTTPError(503, "temp")
        return "ok"

    r = flaky()
    check("retry succeeded after 2 retries", r == "ok" and calls[0] == 3,
          f"calls={calls[0]} r={r}")


def test_retry_gives_up():
    print("\n[10] retry() raises after max_attempts")
    calls = [0]

    @retry(max_attempts=2, base_delay=0.01)
    def always_fail():
        calls[0] += 1
        raise TransientHTTPError(429)

    raised = False
    try:
        always_fail()
    except TransientHTTPError:
        raised = True
    check("raised TransientHTTPError", raised)
    check("called max_attempts times", calls[0] == 2, str(calls[0]))


def test_retry_no_retry_on_value_error():
    print("\n[11] retry() does not retry non-transient errors")
    calls = [0]

    @retry(max_attempts=3, base_delay=0.01)
    def bad():
        calls[0] += 1
        raise ValueError("not transient")

    raised = False
    try:
        bad()
    except ValueError:
        raised = True
    check("ValueError raised immediately", raised)
    check("called once (no retry)", calls[0] == 1, str(calls[0]))


def main():
    for k, v in list(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
    print(f"\n{'='*60}\nrun_guard tests: {PASS} passed, {FAIL} failed\n{'='*60}")
    if FAIL:
        sys.exit(1)
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
