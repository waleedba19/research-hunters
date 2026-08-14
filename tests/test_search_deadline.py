#!/usr/bin/env python3
"""Regression tests for the two chain-breaking bugs that froze matrix research.

Bug A — post-hunt interpreter-shutdown hang:
    search_all() runs up to ~1614 platform jobs in a ThreadPoolExecutor. On the
    CI search-deadline path it calls shutdown(wait=False, cancel_futures=True),
    but the still-RUNNING worker threads are NON-DAEMON, so Python's atexit
    handler joins each one at interpreter shutdown. That join blocked ~26 min
    after "Hunt Complete!" until the 3h GitHub job cap killed the process —
    turning a successful hunt into a "cancelled" run and breaking the chain.

    Fix: main() does a hard os._exit(0) after the banner (all state is already
    on disk). This test proves search_all returns within the deadline even when
    every platform job hangs forever.

Bug B — chain re-dispatch 422:
    The continuation signal "continue:LABEL|||TITLE" was carried in the
    fanout_mode CHOICE input; GitHub's workflow_dispatch API rejects choice
    values that aren't declared options (HTTP 422), so the next chunk never ran.
    The fix changes fanout_mode to type: string. That's validated by the YAML
    parse in CI; here we only cover the Python-side behavior.

Run: python tests/test_search_deadline.py
"""
import os
import sys
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_v24():
    """Load research_hunter_v2-4 (dash filename) via the shim, return the module."""
    import importlib
    return importlib.import_module("research_hunter_v2_4")


def test_search_all_escapes_deadline_with_hung_jobs():
    """search_all must return within ~deadline seconds even if every job hangs.

    A hung platform job simulates a browser/scraping layer that never returns
    (the real-world cause of the 277/1614 jobs still running at the deadline).
    Old code: the `with ThreadPoolExecutor` __exit__ re-blocked on shutdown(wait=True).
    Fixed code: manual executor + shutdown(wait=False, cancel_futures=True).

    Run in a subprocess so the non-daemon hung worker thread (which survives
    shutdown(wait=False) and would block a normal interpreter exit — the very
    bug the end-of-main os._exit(0) fixes) can't hang the test runner itself.
    """
    import subprocess
    code = (
        "import time, threading, sys\n"
        "sys.path.insert(0, %r)\n"
        "import importlib; v24 = importlib.import_module('research_hunter_v2_4')\n"
        "def _hung(query, **kw): threading.Event().wait(3600)\n"
        "orig = v24.PLATFORM_FNS.copy(); v24.PLATFORM_FNS.clear()\n"
        "v24.PLATFORM_FNS['__hung_test_platform__'] = _hung; v24.BROWSER_PLATS = []\n"
        "start = time.monotonic()\n"
        "results = v24.search_all(queries=['test query one two three'], "
        "platforms=['__hung_test_platform__'], year_from=2020, field='general', search_timeout=2)\n"
        "elapsed = time.monotonic() - start\n"
        "v24.PLATFORM_FNS.clear(); v24.PLATFORM_FNS.update(orig)\n"
        "print('ELAPSED' + format(elapsed, '.1f') + ' RESULTS' + repr(results))\n"
        # Hard exit so the hung non-daemon worker thread doesn't block this
        # helper's own interpreter shutdown (mirrors main()'s os._exit(0)).
        "import os; os._exit(0)\n"
    ) % os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run(
        [sys.executable, "-u", "-c", code],
        capture_output=True, text=True, timeout=30,
    )
    out = (proc.stdout or "").strip()
    assert "ELAPSED" in out, f"helper produced no timing output:\n{proc.stderr}"
    line = [l for l in out.splitlines() if l.startswith("ELAPSED")][0]
    elapsed = float(line.split("ELAPSED")[1].split("RESULTS")[0])
    results = line.split("RESULTS", 1)[1]
    assert elapsed < 15, (
        f"search_all hung for {elapsed:.1f}s with hung jobs — the deadline-escape "
        f"fix is broken (this is the 26-min post-hunt freeze bug)."
    )
    assert results == "[]", "hung jobs should produce no papers"
    print(f"[test] search_all escaped 1 hung job in {elapsed:.1f}s (deadline 2s) ✓")


def test_main_has_hard_exit():
    """main() must end with a hard os._exit(0) so non-daemon worker threads
    can't block interpreter shutdown after the hunt completes."""
    import inspect
    v24 = _load_v24()
    src = inspect.getsource(v24.main)
    assert "os._exit(0)" in src, (
        "main() must call os._exit(0) at the end — otherwise non-daemon "
        "ThreadPoolExecutor worker threads (hung search jobs) are joined at "
        "interpreter shutdown, freezing the process ~26 min until the 3h GHA "
        "job cap kills it (the 'cancelled' instead of 'success' bug)."
    )
    # The hard exit must come AFTER reports are written. Sanity-check it's near
    # the end of main(), after the Hunt Complete banner.
    assert "Hunt Complete" in src, "banner marker not found in main()"
    banner_idx = src.rfind("Hunt Complete")
    exit_idx = src.rfind("os._exit(0)")
    assert exit_idx > banner_idx, (
        "os._exit(0) must come AFTER the Hunt Complete banner (reports/results "
        "are persisted before the banner; exiting before would lose them)."
    )
    print("[test] main() hard-exits after the banner (no atexit thread-join hang) ✓")


def test_download_batch_executor_is_nonblocking():
    """The per-batch download executor must NOT use a `with` block (its __exit__
    calls shutdown(wait=True) and re-blocks on hung ghost/scraping workers)."""
    import inspect
    v24 = _load_v24()
    src = inspect.getsource(v24.main)
    # Find the download-batch loop region.
    assert "ex = ThreadPoolExecutor(max_workers=10)" in src, (
        "download batch should use a manually-managed executor "
        "(ex = ThreadPoolExecutor(...)) not a `with` block."
    )
    assert "ex.shutdown(wait=False, cancel_futures=True)" in src, (
        "download batch executor must shutdown(wait=False) in finally."
    )
    print("[test] download-batch executor is non-blocking (no with-block re-hang) ✓")


def main():
    test_search_all_escapes_deadline_with_hung_jobs()
    test_main_has_hard_exit()
    test_download_batch_executor_is_nonblocking()
    print("=" * 60)
    print("  ALL TESTS PASSED (3/3)")
    print("=" * 60)


if __name__ == "__main__":
    main()
