"""
test_hunt_smoke.py — End-to-end smoke test for hunt_pipeline.run_hunt

Validates the full pipeline executes without crashing, produces a
valid output folder with REAL files (xlsx, md, results.json, PDFs, optionally
PDF heavy report), and returns a well-formed result dict.

Designed to run in CI (no Telegram, no Drive, no GUI):
  - Uses minimal params: 3 platforms (CrossRef, OpenAlex, Semantic Scholar),
    year 2024-2025, single_folder mode
  - max_papers=10 (enough to exercise the search + score + download chain)
  - Asserts: import OK, function returns, output folder exists, all 3
    core report files present (xlsx, md, json), at least 1 paper found
  - Reports the number of papers and PDFs actually produced
  - In CI, copies the output folder to smoke_reports/hunt_smoke/ for upload
"""
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

if sys.platform == "win32":
    # Force UTF-8 on Windows so v2-4's rich.console.print (ℹ etc) doesn't crash on cp1252
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")


def main() -> int:
    print("[smoke] Starting hunt_pipeline smoke test")
    start = time.time()

    repo_root = Path(__file__).resolve().parent.parent
    os.chdir(repo_root)
    sys.path.insert(0, str(repo_root))
    print(f"[smoke] cwd: {repo_root}")

    tmp_root = Path(tempfile.mkdtemp(prefix="hunt_smoke_"))
    print(f"[smoke] tmp dir: {tmp_root}")

    # If running in CI, also save a copy to smoke_reports/ for the artifact upload.
    # The tmp dir is removed at the end; this copy persists.
    is_ci = os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS")
    saved_dir = None
    if is_ci:
        saved_dir = repo_root / "smoke_reports" / "hunt_smoke"
        saved_dir.mkdir(parents=True, exist_ok=True)

    test_params = {
        "title": "Machine Learning in Education",
        "field": "education",
        "study_types": [],
        "year_from": 2024,
        "year_to": 2025,
        "research_questions": ["How is ML used in education?"],
        "platforms": ["crossref", "openalex", "semantic_scholar"],
        "search_mode": "normal",
        "use_scihub": False,
        "single_folder": True,
        "study_keywords": [],
        "lang_label": "English",
        "search_languages": ["en"],
        "_out_root": str(tmp_root),
        # Smoke test: cap to 10 papers + 3 platforms so it completes in ~5-10 min
        # but still exercises the search + score + download chain with realistic load.
        # v6.4 default is 1000 (unleashed deep search).
        "max_papers": 10,
    }

    progress_events = []

    def cb(stage, message, progress):
        progress_events.append((stage, progress, message[:80]))
        print(f"[smoke] [{progress:.0%}] {stage}: {message[:80]}")

    try:
        from hunt_pipeline import run_hunt
        print("[smoke] Imported hunt_pipeline OK")
    except Exception as e:
        print(f"[smoke] FAIL: import hunt_pipeline raised: {e}")
        shutil.rmtree(tmp_root, ignore_errors=True)
        return 1

    os.chdir(tmp_root)

    try:
        result = run_hunt(test_params, progress_callback=cb)
    except Exception as e:
        print(f"[smoke] FAIL: run_hunt raised: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        shutil.rmtree(tmp_root, ignore_errors=True)
        return 1

    print(f"[smoke] run_hunt returned in {time.time()-start:.1f}s")

    # Validate result dict structure
    if not isinstance(result, dict):
        print(f"[smoke] FAIL: result is not a dict: {type(result)}")
        shutil.rmtree(tmp_root, ignore_errors=True)
        return 1

    required_keys = ["output_folder", "total_papers", "downloaded"]
    for k in required_keys:
        if k not in result:
            print(f"[smoke] FAIL: result missing key '{k}'. Got: {list(result.keys())}")
            shutil.rmtree(tmp_root, ignore_errors=True)
            return 1
    print(f"[smoke] Result has all required keys: {required_keys}")

    # Check success flag (added in critical-fix commit)
    success = result.get("success", None)
    print(f"[smoke] Result success flag: {success}")
    if success is False:
        err = result.get("error", "(no error message)")
        print(f"[smoke] FAIL: run_hunt reported failure: {err}")
        shutil.rmtree(tmp_root, ignore_errors=True)
        return 1

    # Validate output folder
    out_folder = Path(result["output_folder"])
    if not out_folder.exists():
        print(f"[smoke] FAIL: output_folder does not exist: {out_folder}")
        shutil.rmtree(tmp_root, ignore_errors=True)
        return 1
    print(f"[smoke] Output folder exists: {out_folder}")

    # Validate results.json
    results_json = out_folder / "results.json"
    if not results_json.exists():
        print(f"[smoke] FAIL: results.json not created at {results_json}")
        shutil.rmtree(tmp_root, ignore_errors=True)
        return 1
    print(f"[smoke] results.json exists")

    try:
        with open(results_json, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[smoke] FAIL: results.json is invalid JSON: {e}")
        shutil.rmtree(tmp_root, ignore_errors=True)
        return 1

    if "papers" not in data:
        print(f"[smoke] FAIL: results.json missing 'papers' key. Got: {list(data.keys())}")
        shutil.rmtree(tmp_root, ignore_errors=True)
        return 1
    print(f"[smoke] results.json valid, {len(data['papers'])} papers")

    # Validate the CORE report files exist with non-zero size.
    # (These are exactly the files _send_hunt_v2_result delivers to the user)
    core_report_files = {
        "results.json": out_folder / "results.json",
        "research_report.md": out_folder / "research_report.md",
        "master_database.xlsx": out_folder / "master_database.xlsx",
    }
    for label, path in core_report_files.items():
        if not path.exists():
            print(f"[smoke] FAIL: required report file missing: {label} at {path}")
            shutil.rmtree(tmp_root, ignore_errors=True)
            return 1
        size = path.stat().st_size
        if size == 0:
            print(f"[smoke] FAIL: required report file is empty: {label}")
            shutil.rmtree(tmp_root, ignore_errors=True)
            return 1
        print(f"[smoke] {label} OK ({size:,} bytes)")

    # DOCX is optional (requires Node.js which is not in the CI image).
    # We log whether it was generated but don't fail if missing.
    docx_path = out_folder / "research_report.docx"
    if docx_path.exists():
        print(f"[smoke] research_report.docx OK ({docx_path.stat().st_size:,} bytes)")
        # PDF is the "heavy report" the user expects. Try to convert DOCX to PDF.
        try:
            from report_pdf import docx_to_pdf
            pdf_path = docx_to_pdf(docx_path, timeout=300)
            if pdf_path and pdf_path.exists() and pdf_path.stat().st_size > 1000:
                print(f"[smoke] research_report.pdf OK ({pdf_path.stat().st_size:,} bytes)")
            else:
                print(f"[smoke] research_report.pdf SKIPPED (LibreOffice/Word not available)")
        except Exception as e:
            print(f"[smoke] PDF conversion error: {e}")
    else:
        print(f"[smoke] research_report.docx SKIPPED (Node.js not available — "
              f"see AGENTS.md 'No Node.js in image')")

    # Validate at least 1 paper was found (search worked)
    if len(data["papers"]) == 0:
        print(f"[smoke] FAIL: 0 papers found — search chain broken")
        shutil.rmtree(tmp_root, ignore_errors=True)
        return 1
    print(f"[smoke] Search chain returned {len(data['papers'])} papers")

    # Validate PDFs directory and count real downloaded PDFs
    pdfs_dir = out_folder / "pdfs"
    pdf_count = 0
    pdf_size_total = 0
    if pdfs_dir.exists():
        pdfs = list(pdfs_dir.glob("*.pdf"))
        pdf_count = len(pdfs)
        pdf_size_total = sum(p.stat().st_size for p in pdfs)
    print(f"[smoke] PDFs on disk: {pdf_count} ({pdf_size_total:,} bytes total)")
    # This is informational only — smoke test passes even if 0 PDFs (network may be slow)
    # but we LOG it loudly so CI artifacts show real progress.

    # Validate progress events were emitted
    stages_seen = {s for s, _, _ in progress_events}
    expected_stages = {"starting", "generating_queries", "searching", "deduplicating"}
    missing = expected_stages - stages_seen
    if missing:
        print(f"[smoke] FAIL: progress callback missing stages: {missing}. Saw: {stages_seen}")
        shutil.rmtree(tmp_root, ignore_errors=True)
        return 1
    print(f"[smoke] Progress callback emitted all expected stages: {expected_stages}")

    # Validate progress reaches 1.0
    if not any(abs(p - 1.0) < 0.01 for _, p, _ in progress_events):
        print(f"[smoke] FAIL: progress never reached 1.0. Last few: {progress_events[-3:]}")
        shutil.rmtree(tmp_root, ignore_errors=True)
        return 1
    print(f"[smoke] Progress reached 1.0 (completion)")

    # Validate that "done" stage was emitted
    if not any(s == "done" for s, _, _ in progress_events):
        print(f"[smoke] FAIL: 'done' stage never emitted. Stages: {stages_seen}")
        shutil.rmtree(tmp_root, ignore_errors=True)
        return 1
    print(f"[smoke] 'done' stage emitted")

    elapsed = time.time() - start
    print(f"\n[smoke] PASS in {elapsed:.1f}s")
    print(f"[smoke] total_papers={result['total_papers']} downloaded={result['downloaded']}")
    print(f"[smoke] red_list={result.get('red_list_count', 0)}")
    print(f"[smoke] pdfs_on_disk={pdf_count} ({pdf_size_total:,} bytes)")
    print(f"[smoke] output_folder={out_folder}")

    # Save a copy of the output folder to smoke_reports/ for CI artifact upload
    if saved_dir and out_folder.exists():
        try:
            dest = saved_dir / out_folder.name
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(out_folder, dest)
            print(f"[smoke] Saved copy to {dest} (CI artifact)")
        except Exception as e:
            print(f"[smoke] WARN: could not save copy: {e}")

    shutil.rmtree(tmp_root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
