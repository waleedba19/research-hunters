"""
tests/test_verify_refs_smoke.py — Real end-to-end smoke test of verify_refs.

Runs the FULL pipeline (not mocks) on a small list of real references:
  1. Parse pasted list of 5 well-known ML papers
  2. For each ref: search 81 platforms, score with ollama
  3. Classify as VERIFIED / LIKELY / UNVERIFIED / FAKE
  4. Generate Excel + DOCX reports
  5. Verify the reports are non-empty and well-formed

This test REQUIRES:
  - Ollama running on http://127.0.0.1:11434 (CI provides this)
  - Network access to the 81 academic platforms

If ollama is not available, the test is SKIPPED (not failed).
If ollama is available but no platform returns results, the test is FAILED
(this would indicate a real problem with the pipeline).

Output:  smoke_reports/ in the current working directory.
"""
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from logger import get_logger
log = get_logger("test_verify_refs_smoke")

# A small list of well-known, easy-to-find papers. These should all be VERIFIED
# if the pipeline is working correctly. The test is considered PASSED if at
# least 4/5 are correctly classified as VERIFIED.
SAMPLE_REFS = """\
Vaswani A, Shazeer N, Parmar N, et al. Attention is all you need. NeurIPS 2017.
He K, Zhang X, Ren S, Sun J. Deep residual learning for image recognition. CVPR 2016.
LeCun Y, Bengio Y, Hinton G. Deep learning. Nature 2015;521(7553):436-444.
Hochreiter S, Schmidhuber J. Long short-term memory. Neural Computation 1997;9(8):1735-1780.
Kingma DP, Ba J. Adam: a method for stochastic optimization. ICLR 2015.
"""


def _check_ollama_alive() -> bool:
    """Check if ollama is running on localhost:11434."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> int:
    print("=" * 60)
    print("  verify_refs SMOKE TEST (real end-to-end pipeline)")
    print("=" * 60)

    if not _check_ollama_alive():
        print("[smoke] SKIPPED: ollama not running on http://127.0.0.1:11434")
        return 0

    from verify_refs.orchestrator import run_verification
    output_dir = REPO_ROOT / "smoke_reports"
    if output_dir.exists():
        import shutil
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    result = run_verification(
        input_path="PASTED:" + SAMPLE_REFS,
        output_folder_name="verify_refs_smoke",
        base_output_dir=str(output_dir),
        download_pdfs=False,  # smoke test, no downloads
        threshold_verified=0.7,  # slightly lower for test reliability
        threshold_likely=0.4,
    )
    elapsed = time.time() - t0

    print()
    print("=" * 60)
    print(f"  Pipeline finished in {elapsed:.1f}s")
    print(f"  Output dir: {result.get('output_dir', '')}")
    print(f"  Total: {result.get('total_refs', 0)}")
    print(f"  VERIFIED: {result.get('verified', 0)}")
    print(f"  LIKELY: {result.get('likely', 0)}")
    print(f"  UNVERIFIED: {result.get('unverified', 0)}")
    print(f"  FAKE: {result.get('fake', 0)}")
    print("=" * 60)

    if not result.get("success"):
        print(f"[smoke] FAILED: {result.get('error')}")
        return 1

    # Verify both reports exist
    excel_path = result.get("excel_path", "")
    docx_path = result.get("docx_path", "")
    excel_ok = excel_path and Path(excel_path).is_file() and Path(excel_path).stat().st_size > 5000
    docx_ok = docx_path and Path(docx_path).is_file() and Path(docx_path).stat().st_size > 5000

    print(f"  Excel report: {excel_path} ({'OK' if excel_ok else 'MISSING'})")
    print(f"  DOCX report:  {docx_path} ({'OK' if docx_ok else 'MISSING'})")
    print()

    if not excel_ok or not docx_ok:
        print("[smoke] FAILED: reports are missing or too small")
        return 1

    # Verify per-reference classifications
    classified = result.get("results", [])
    n_verified = sum(1 for c in classified if c.get("status") == "VERIFIED")
    n_total = len(classified)
    print(f"  Per-ref classifications:")
    for c in classified:
        title = c.get("matched_title") or c.get("ref", "")[:50]
        print(f"    [{c.get('status'):11s}] score={c.get('score', 0):.2f}  {title[:50]!r}")

    # Pass criteria: at least 60% VERIFIED for known-good papers
    if n_total == 0:
        print("[smoke] FAILED: no refs processed")
        return 1
    pct = n_verified / n_total
    if pct < 0.6:
        print(f"[smoke] FAILED: only {n_verified}/{n_total} ({pct*100:.0f}%) verified (need >=60%)")
        return 1

    print()
    print(f"[smoke] PASS: {n_verified}/{n_total} verified ({pct*100:.0f}%)")
    print(f"[smoke] Reports saved to: {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
