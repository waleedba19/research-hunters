#!/usr/bin/env python3
"""
run_no_download.py — Run the research hunt WITHOUT downloading PDFs.

Produces:
  1. Excel workbook with 40 sheets (ULTIMATE_RESEARCH_SYNTHESIS_V10.xlsx)
     built from the REAL search results.
  2. Full report in DOCX.
  3. Full report in PDF (via LibreOffice; DOCX still produced if unavailable).

The pipeline still searches all platforms, checks quartiles, deduplicates, and
generates the markdown / DOCX / master XLSX / PDF reports — only the PDF file
download step is skipped (skip_download=True).

Usage:
  python3 run_no_download.py "<topic>" [field] [--platforms p1,p2,...]
                                [--year-from N] [--year-to N]
                                [--max-papers N] [--mode normal|deep]
                                [--out DIR]

Examples:
  python3 run_no_download.py "Machine Learning in Education" education
  python3 run_no_download.py "AI in healthcare" medicine --platforms crossref,openalex --max-papers 50
"""
import argparse
import os
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))


def _progress(stage, message, progress):
    print(f"  [{progress:5.1%}] {stage}: {message[:90]}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run hunt with no PDF downloads.")
    ap.add_argument("title", help="Research topic / title")
    ap.add_argument("field", nargs="?", default="general", help="Academic field")
    ap.add_argument("--platforms", default="crossref,openalex,semantic_scholar",
                    help="Comma-separated platform names (default: 3 fast API platforms)")
    ap.add_argument("--year-from", type=int, default=None)
    ap.add_argument("--year-to", type=int, default=None)
    ap.add_argument("--max-papers", type=int, default=50,
                    help="Cap on papers (default 50)")
    ap.add_argument("--mode", choices=["normal", "deep"], default="normal")
    ap.add_argument("--rqs", default="", help="Comma-separated research questions")
    ap.add_argument("--out", default=None, help="Output folder override")
    args = ap.parse_args()

    print("=" * 64)
    print("  RESEARCH HUNT — NO-DOWNLOAD MODE")
    print("=" * 64)
    print(f"  Topic:    {args.title}")
    print(f"  Field:    {args.field}")
    print(f"  Platforms:{args.platforms}")
    print(f"  Years:    {args.year_from}-{args.year_to}")
    print(f"  Max:      {args.max_papers} papers")
    print(f"  Mode:     {args.mode}")
    print(f"  PDFs:     SKIPPED (skip_download=True)")
    print("=" * 64)

    start = time.time()

    from hunt_pipeline import run_hunt

    params = {
        "title": args.title,
        "field": args.field,
        "study_types": [],
        "year_from": args.year_from,
        "year_to": args.year_to,
        "research_questions": [q.strip() for q in args.rqs.split(",") if q.strip()],
        "platforms": [p.strip() for p in args.platforms.split(",") if p.strip()],
        "search_mode": args.mode,
        "use_scihub": False,
        "single_folder": True,
        "study_keywords": [],
        "lang_label": "English",
        "search_languages": ["en"],
        "skip_download": True,
        "max_papers": args.max_papers,
    }

    result = run_hunt(params, progress_callback=_progress)

    print()
    print("-" * 64)
    print("  HUNT RESULT")
    print("-" * 64)
    print(f"  success:      {result.get('success')}")
    print(f"  output_folder:{result.get('output_folder')}")
    print(f"  total_papers: {result.get('total_papers')}")
    print(f"  downloaded:   {result.get('downloaded')} (skipped)")
    if result.get("error"):
        print(f"  error:        {result['error']}")
    print("-" * 64)

    if not result.get("success"):
        print("\n❌ Hunt failed — no reports generated.")
        return 1

    out_folder = Path(result["output_folder"])
    results_path = out_folder / "results.json"
    report_data = result.get("results") or {}

    # ── Generate the 40-sheet Excel from real results ───────────────────────
    print("\n📊 Generating 40-sheet Excel from real results...")
    excel_out = out_folder / "ULTIMATE_RESEARCH_SYNTHESIS_V10.xlsx"
    import subprocess
    r = subprocess.run(
        [sys.executable, str(REPO / "generate_ultimate_excel_v10.py"),
         str(results_path), str(excel_out)],
        capture_output=True, text=True, cwd=str(REPO),
    )
    if r.returncode != 0:
        print("❌ Excel generation failed:")
        print(r.stderr[-1500:])
    else:
        print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "OK")
        print(f"   → {excel_out} ({excel_out.stat().st_size:,} bytes)")

    # ── Report the DOCX + PDF produced by the pipeline ──────────────────────
    print("\n📄 Reports produced by the pipeline:")
    docx_path = result.get("docx_path")
    pdf_path = result.get("pdf_path")
    xlsx_master = result.get("xlsx_path")
    md_path = result.get("md_path")
    for label, p in [("DOCX", docx_path), ("PDF", pdf_path),
                     ("Master XLSX", xlsx_master), ("Markdown", md_path)]:
        if p and Path(p).exists():
            print(f"   ✅ {label:12}: {p} ({Path(p).stat().st_size:,} bytes)")
        else:
            print(f"   ⚠️  {label:12}: not available"
                  + ("" if label != "PDF" else " (no LibreOffice — DOCX still available)"))

    elapsed = time.time() - start
    print()
    print("=" * 64)
    print(f"  DONE in {elapsed:.1f}s — all outputs in: {out_folder}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
