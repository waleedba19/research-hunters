#!/usr/bin/env python3
"""Collect diagnostics from a research run's logs and artifacts.

This is the "report to us what we might miss" engine for the daily_learn job.
It scans every leg's log files (data/logs/*.log) for ERROR/WARNING/Exception/
Traceback lines, summarizes them by category and frequency, and emits a
single Markdown report. It also runs the offline system-health entrypoint
(run.py) so the report captures module/platform/transport status even when
the research workflow is OFF.

Design:
  - Pure-Python, no network, no ollama, no Google creds required. Runs in CI
    and locally. Never raises — a failure in one log never aborts the scan.
  - Reads logs from one or more directories (leg log folders) via glob.
  - Deduplicates repeated lines (a stack-trace spamming the same warning is
    reported once with a count, not a thousand times).
  - Captures the first/last timestamp per log so we can see time spans.

Usage:
  python scripts/collect_diagnostics.py \\
      --log-dirs legs_current logs_dir1 legs_dir2 \\
      --repo-root . \\
      --out diagnostics_report.md
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import subprocess
import sys
import traceback
from collections import Counter, defaultdict
from pathlib import Path

# Lines that indicate a real problem worth surfacing.
_ERROR_RE = re.compile(
    r"\b(ERROR|CRITICAL|FATAL|Exception|Traceback|"
    r"AttributeError|TypeError|ValueError|KeyError|"
    r"ImportError|ModuleNotFoundError|RuntimeError|"
    r"TimeoutError|ConnectionError|ConnectionReset|"
    r"JSONDecodeError|OSError|MemoryError|PermissionError)\b",
    re.IGNORECASE,
)
_WARN_RE = re.compile(r"\b(WARNING|WARN|⚠|failed|skipped|abandon|hang|timeout)\b", re.IGNORECASE)

# Lines we never want to surface (noise / expected non-fatal recovery).
_IGNORE_RE = re.compile(
    r"(Non-fatal|non-fatal|continue-on-error|graceful|skipped gracefully|"
    r"cache save failed.*non-fatal|Notification skipped|PDF step errored — continuing)",
    re.IGNORECASE,
)


def _scan_file(path: Path) -> tuple[list[str], list[str], str, str]:
    """Return (error_lines, warn_lines, first_ts, last_ts) for one log file."""
    errors: list[str] = []
    warns: list[str] = []
    first_ts = ""
    last_ts = ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return errors, warns, first_ts, last_ts
    for line in text.splitlines():
        if not first_ts:
            # log lines look like: 2026-08-14 14:33:27 [INFO] ...
            m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
            if m:
                first_ts = m.group(1)
        m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
        if m:
            last_ts = m.group(1)
        if _IGNORE_RE.search(line):
            continue
        if _ERROR_RE.search(line):
            errors.append(line.strip()[:300])
        elif _WARN_RE.search(line):
            warns.append(line.strip()[:300])
    return errors, warns, first_ts, last_ts


def collect(log_dirs: list[str]) -> dict:
    """Scan all .log files under log_dirs. Returns a structured summary."""
    findings: dict = {
        "scanned_files": 0,
        "per_file": [],
        "error_counter": Counter(),
        "warn_counter": Counter(),
        "first_seen": "",
        "last_seen": "",
    }
    seen_paths: set[str] = set()
    for d in log_dirs:
        base = Path(d)
        if not base.exists():
            continue
        for log_path in sorted(base.rglob("*.log")):
            if str(log_path) in seen_paths:
                continue
            seen_paths.add(str(log_path))
            errs, warns, fts, lts = _scan_file(log_path)
            findings["scanned_files"] += 1
            findings["per_file"].append({
                "file": str(log_path),
                "errors": len(errs),
                "warnings": len(warns),
                "first": fts,
                "last": lts,
            })
            for e in errs:
                # Normalize variable bits (numbers, long paths) so repeats group.
                norm = re.sub(r"\d+", "N", e)
                norm = re.sub(r"/tmp/[^ ]+", "/tmp/...", norm)
                findings["error_counter"][norm[:200]] += 1
            for w in warns:
                norm = re.sub(r"\d+", "N", w)
                findings["warn_counter"][norm[:200]] += 1
            if fts and (not findings["first_seen"] or fts < findings["first_seen"]):
                findings["first_seen"] = fts
            if lts and (not findings["last_seen"] or lts > findings["last_seen"]):
                findings["last_seen"] = lts
    return findings


def _run_health(repo_root: str) -> str:
    """Run run.py (offline health) and capture its output. Never raises."""
    try:
        out = subprocess.run(
            [sys.executable, "run.py"],
            cwd=repo_root, capture_output=True, text=True, timeout=120,
        )
        return (out.stdout or "") + (out.stderr or "")
    except FileNotFoundError:
        return "(run.py not found — skipping offline health)"
    except Exception as e:
        return f"(offline health check failed: {e})"


def render_markdown(findings: dict, health_output: str, repo_root: str) -> str:
    """Render the diagnostics as a Markdown report."""
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []
    lines.append("# 🔍 Research Run — Diagnostics & Status Report")
    lines.append("")
    lines.append(f"**Generated:** {now}  ")
    lines.append(f"**Repo root:** `{repo_root}`  ")
    lines.append(f"**Logs scanned:** {findings['scanned_files']}  ")
    lines.append(f"**Time span:** {findings['first_seen'] or 'n/a'} → {findings['last_seen'] or 'n/a'}  ")
    lines.append("")
    lines.append("> This report surfaces errors, warnings, and exceptions captured in the")
    lines.append("> research run's logs that you might miss when the workflow is off. The")
    lines.append("> offline system-health section below works **without** the workflow running")
    lines.append("> — it reflects module/platform/transport status from the codebase state.")
    lines.append("")

    # ── Top errors ─────────────────────────────────────────────
    top_errors = findings["error_counter"].most_common(30)
    total_errors = sum(c for _, c in findings["error_counter"].items())
    lines.append(f"## 🛑 Errors & Exceptions ({total_errors} total, {len(top_errors)} unique)")
    lines.append("")
    if not top_errors:
        lines.append("✅ No errors or exceptions detected in any leg's logs.")
    else:
        lines.append("| Count | Message (normalized) |")
        lines.append("|------:|----------------------|")
        for msg, cnt in top_errors:
            safe = msg.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {cnt} | {safe} |")
    lines.append("")

    # ── Top warnings ───────────────────────────────────────────
    top_warns = findings["warn_counter"].most_common(30)
    total_warns = sum(c for _, c in findings["warn_counter"].items())
    lines.append(f"## ⚠️ Warnings ({total_warns} total, {len(top_warns)} unique)")
    lines.append("")
    if not top_warns:
        lines.append("✅ No warnings detected.")
    else:
        lines.append("| Count | Message (normalized) |")
        lines.append("|------:|----------------------|")
        for msg, cnt in top_warns:
            safe = msg.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {cnt} | {safe} |")
    lines.append("")

    # ── Per-file breakdown ─────────────────────────────────────
    lines.append("## 📄 Per-log-file breakdown")
    lines.append("")
    if not findings["per_file"]:
        lines.append("_No log files found. Either no leg ran, or logs weren't uploaded._")
    else:
        lines.append("| File | Errors | Warnings | First | Last |")
        lines.append("|------|-------:|---------:|-------|------|")
        for pf in findings["per_file"]:
            f = pf["file"].replace("|", "\\|")
            # shorten to leg-relative path if possible
            if "legs_" in f:
                f = f.split("legs_", 1)[-1]
                f = "legs_" + f
            lines.append(f"| {f} | {pf['errors']} | {pf['warnings']} | {pf['first']} | {pf['last']} |")
    lines.append("")

    # ── Offline system health (works when workflow is OFF) ─────
    lines.append("## 🏥 Offline System Health (`run.py`)")
    lines.append("")
    lines.append("_This runs the offline health entrypoint — module health, platform count,")
    lines.append("transport status. Works regardless of whether the workflow is running._")
    lines.append("")
    lines.append("```")
    lines.append(health_output.strip() or "(no output)")
    lines.append("```")
    lines.append("")

    # ── Recommendations ───────────────────────────────────────
    lines.append("## 🔧 Recommended actions")
    lines.append("")
    if not top_errors and not top_warns:
        lines.append("- No issues detected — the run looks healthy.")
    else:
        if top_errors:
            lines.append("- Investigate the top errors above — these are the most likely bugs.")
        if any("timeout" in m.lower() or "hang" in m.lower() for m, _ in top_warns):
            lines.append("- Timeout/hang warnings detected — check the download chain "
                          "(ghost/scraping layers) for hung workers.")
        if any("ConnectionError" in m or "ConnectionReset" in m for m, _ in top_errors):
            lines.append("- Connection errors — a platform API may be down or rate-limiting. "
                          "Re-run later or exclude the platform.")
        if any("ImportError" in m or "ModuleNotFoundError" in m for m, _ in top_errors):
            lines.append("- Missing dependency — check `pip install -r requirements.txt` ran.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect research-run diagnostics into a Markdown report.")
    ap.add_argument("--log-dirs", nargs="*", default=["data/logs"],
                    help="Directories to scan for *.log files (recursively).")
    ap.add_argument("--repo-root", default=".", help="Repo root (for run.py).")
    ap.add_argument("--out", default="diagnostics_report.md", help="Output Markdown path.")
    args = ap.parse_args()

    try:
        findings = collect(args.log_dirs)
        health = _run_health(args.repo_root)
        report = render_markdown(findings, health, args.repo_root)
        Path(args.out).write_text(report, encoding="utf-8")
        print(report)
        print(f"\n✅ Diagnostics report written to {args.out}")
    except Exception:
        # The diagnostics tool must NEVER fail the workflow — emit the error
        # into the report instead so we can still see something useful.
        tb = traceback.format_exc()
        Path(args.out).write_text(f"# Diagnostics tool crashed\n\n```\n{tb}\n```\n",
                                  encoding="utf-8")
        print(tb)
        print(f"⚠️ Diagnostics tool crashed — partial report written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
