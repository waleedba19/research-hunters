"""
verify_refs/orchestrator.py — Main pipeline:
  for each reference: search 81 platforms → ollama score → classify
  → download PDFs for verified refs → save outputs.
"""
import os
import re
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from logger import get_logger
from verify_refs.input_parser import parse_input
from verify_refs.reports import build_excel_report, build_docx_report

log = get_logger("verify_refs.orchestrator")

# Lazy imports for modules that may not always be available
_precision_search = None
_download_chain = None


def _get_precision_search():
    """Lazy import precision_engine.precision_search."""
    global _precision_search
    if _precision_search is None:
        try:
            from precision_engine import precision_search
            _precision_search = precision_search
        except ImportError as e:
            log.warning(f"precision_engine not importable: {e}")
    return _precision_search


def _get_download_chain():
    """Lazy import research_hunter_v2_4.download_with_full_chain."""
    global _download_chain
    if _download_chain is None:
        try:
            import research_hunter_v2_4 as v24
            _download_chain = v24.download_with_full_chain
        except ImportError as e:
            log.warning(f"research_hunter_v2_4 not importable: {e}")
    return _download_chain


def classify_ref(ref_text: str, threshold_verified: float = 0.85,
                 threshold_likely: float = 0.60) -> Dict[str, Any]:
    """Search + ollama-score a single reference. Returns a classification dict.

    Returns:
        {
          "ref": str,                   # original reference text
          "status": "VERIFIED"|"LIKELY"|"UNVERIFIED"|"FAKE",
          "score": float,               # best ollama match score (0 if none)
          "reason": str,                # ollama reasoning (truncated)
          "matched_title": str,         # title of the best candidate (or "")
          "matched_doi": str,           # DOI of best candidate (or "")
          "matched_authors": str,
          "matched_year": str,
          "matched_url": str,           # any PDF URL for download
          "source_platform": str,       # which platform had the best match
          "source_count": int,          # how many platforms had this paper
          "candidates_count": int,      # how many candidates before scoring
          "error": str,                 # error message if any
        }
    """
    precision_search = _get_precision_search()
    out: Dict[str, Any] = {
        "ref": ref_text,
        "status": "FAKE",
        "score": 0.0,
        "reason": "",
        "matched_title": "",
        "matched_doi": "",
        "matched_authors": "",
        "matched_year": "",
        "matched_url": "",
        "source_platform": "",
        "source_count": 0,
        "candidates_count": 0,
        "error": "",
    }

    if not precision_search:
        out["error"] = "precision_engine not available"
        return out

    try:
        # precision_search uses threshold internally; pass low threshold to get
        # all candidates back, then we classify based on score.
        candidates = precision_search(
            ref_text, threshold=threshold_likely, max_candidates=5)
    except Exception as e:
        out["error"] = f"precision_search failed: {e}"
        return out

    out["candidates_count"] = len(candidates) if candidates else 0
    if not candidates:
        # No candidates at all - check if we should call it FAKE
        # (precision_search returns [] when nothing found OR when scores < threshold)
        # To distinguish: try search_all_platforms directly
        try:
            from platform_registry import search_all_platforms
            # Extract a title-ish query from the reference (first 80 chars)
            title_guess = re.sub(r"\s+", " ", ref_text)[:80]
            results = search_all_platforms(title_guess, max_per_platform=3)
            if not results or all(len(v) == 0 for v in results.values()):
                out["status"] = "FAKE"
            else:
                out["status"] = "UNVERIFIED"
                out["candidates_count"] = sum(len(v) for v in results.values())
        except Exception as e:
            out["error"] = f"platform search failed: {e}"
            out["status"] = "UNVERIFIED"
        return out

    # Pick the best candidate
    best = max(candidates, key=lambda p: p.get("match_score", 0.0))
    out["score"] = float(best.get("match_score", 0.0))
    out["reason"] = str(best.get("match_reason", ""))[:300]
    out["matched_title"] = str(best.get("title", ""))[:300]
    out["matched_doi"] = str(best.get("doi", ""))
    out["matched_authors"] = str(best.get("authors", ""))[:200]
    out["matched_year"] = str(best.get("year", ""))
    out["matched_url"] = str(best.get("pdf_url") or best.get("url") or "")
    out["source_platform"] = str(best.get("_source_platform", ""))
    out["source_count"] = int(best.get("source_count", 0))

    # Classify
    if out["score"] >= threshold_verified:
        out["status"] = "VERIFIED"
    elif out["score"] >= threshold_likely:
        out["status"] = "LIKELY"
    else:
        out["status"] = "UNVERIFIED"
    return out


def _safe_filename(s: str, mx: int = 80) -> str:
    """Make a filesystem-safe version of a string."""
    s = re.sub(r'[\\/*?:"<>|\n\r\t]+', "_", s).strip()
    s = re.sub(r"\s+", " ", s)
    return s[:mx].rstrip() or "reference"


def _ref_id(ref_text: str) -> str:
    """Short stable id for a reference (used in filenames)."""
    h = hashlib.sha1(ref_text.encode("utf-8", errors="replace")).hexdigest()[:8]
    return f"ref_{h}"


def download_verified_papers(classified: List[Dict[str, Any]],
                              output_dir: Path,
                              max_workers: int = 4) -> List[Dict[str, Any]]:
    """For each VERIFIED reference, try the 14-layer download chain.
    Saves PDFs to <output_dir>/01_PDFs/<safe_title>.pdf
    Returns a list of download result dicts to merge into the report.
    """
    download_chain = _get_download_chain()
    if not download_chain:
        log.warning("download chain not available; skipping downloads")
        return []

    pdfs_dir = output_dir / "01_PDFs"
    pdfs_dir.mkdir(parents=True, exist_ok=True)

    verified = [c for c in classified if c.get("status") == "VERIFIED"]
    log.info(f"Attempting to download {len(verified)} verified refs")

    results: List[Dict[str, Any]] = []

    def _download_one(idx: int, classification: Dict[str, Any]) -> Dict[str, Any]:
        rec = dict(classification)
        rec["download_attempted"] = True
        rec["download_success"] = False
        rec["download_path"] = ""
        rec["download_layer"] = ""

        # Build a paper dict for download_with_full_chain
        paper = {
            "title": rec.get("matched_title", ""),
            "doi": rec.get("matched_doi", ""),
            "pdf_url": rec.get("matched_url", ""),
            "year": rec.get("matched_year", ""),
            "authors": rec.get("matched_authors", ""),
        }
        if not paper["doi"] and not paper["pdf_url"] and not paper["title"]:
            rec["error"] = (rec.get("error", "") + " | no doi/url/title to download").strip(" |")
            return rec

        safe_title = _safe_filename(paper["title"] or rec.get("ref", "")[:60])
        dest = pdfs_dir / f"{idx:03d}_{safe_title}.pdf"
        try:
            ok, tried = download_chain(paper, dest)
            rec["download_success"] = bool(ok)
            rec["download_path"] = str(dest.relative_to(output_dir)) if ok else ""
            rec["download_tried_layers"] = tried
        except Exception as e:
            rec["error"] = (rec.get("error", "") + f" | download error: {e}").strip(" |")
        return rec

    if not verified:
        return results

    # Parallel downloads
    indexed = list(enumerate(verified, start=1))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_download_one, i, c): i for i, c in indexed}
        for fut in as_completed(futs):
            try:
                result = fut.result(timeout=60)
            except Exception as e:
                log.error(f"Download future failed: {e}")
                continue
            results.append(result)

    # Sort back to original order
    results.sort(key=lambda r: int(re.match(r"(\d+)_", Path(r.get("download_path", "0_")).name).group(1)) if r.get("download_path") else 0)

    # Merge back into classified list (replace originals)
    verified_map = {id(c): c for c in verified}
    for r in results:
        # Find original by matched_title
        for orig in verified:
            if orig.get("matched_title") == r.get("matched_title") and "download_success" not in orig:
                orig["download_attempted"] = r.get("download_attempted", False)
                orig["download_success"] = r.get("download_success", False)
                orig["download_path"] = r.get("download_path", "")
                orig["download_tried_layers"] = r.get("download_tried_layers", [])
                orig["error"] = r.get("error", orig.get("error", ""))
                break
    return results


def run_verification(
    input_path: str,
    output_folder_name: str,
    base_output_dir: Optional[str] = None,
    download_pdfs: bool = True,
    threshold_verified: float = 0.85,
    threshold_likely: float = 0.60,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """End-to-end reference verification pipeline.

    Args:
        input_path: folder path, file path, or 'PASTED:<text>' for pasted lists.
        output_folder_name: name for the output folder (also used for Drive title).
        base_output_dir: where to create the output folder.
                        Defaults to <project>/pdf_files/<output_folder_name>.
        download_pdfs: if True, attempt PDF downloads for verified refs.
        threshold_verified: ollama score >= this counts as VERIFIED.
        threshold_likely: ollama score >= this counts as LIKELY.
        progress_callback: optional callable receiving {"stage", "current", "total", "ref"}.

    Returns:
        {
          "success": bool,
          "output_dir": str,
          "total_refs": int,
          "verified": int, "likely": int, "unverified": int, "fake": int,
          "pdfs_downloaded": int,
          "excel_path": str,
          "docx_path": str,
          "results": [...],  # list of per-ref classification dicts
          "source_description": str,
          "error": str,
        }
    """
    out: Dict[str, Any] = {
        "success": False,
        "output_dir": "",
        "total_refs": 0,
        "verified": 0, "likely": 0, "unverified": 0, "fake": 0,
        "pdfs_downloaded": 0,
        "excel_path": "",
        "docx_path": "",
        "results": [],
        "source_description": "",
        "error": "",
    }

    def _progress(stage: str, current: int = 0, total: int = 0, ref: str = "") -> None:
        if progress_callback:
            try:
                progress_callback({
                    "stage": stage, "current": current, "total": total,
                    "ref": ref[:80],
                })
            except Exception:
                pass

    try:
        # 1. Parse input
        _progress("parsing", 0, 1)
        refs, source_desc = parse_input(input_path)
        out["source_description"] = source_desc
        out["total_refs"] = len(refs)
        if not refs:
            out["error"] = "No references found in input"
            return out
        log.info(f"Parsed {len(refs)} references from {source_desc}")

        # 2. Set up output dir
        if base_output_dir is None:
            base_output_dir = os.path.join(os.path.dirname(__file__), "..", "pdf_files")
        base_output_dir = os.path.abspath(base_output_dir)
        output_dir = os.path.join(base_output_dir, _safe_filename(output_folder_name, mx=60))
        os.makedirs(output_dir, exist_ok=True)
        # Standard subfolders (mirroring hunt_pipeline layout)
        for sub in ("00_Input_References", "01_PDFs", "02_Verification_Results",
                    "03_Drive_Upload"):
            os.makedirs(os.path.join(output_dir, sub), exist_ok=True)
        out["output_dir"] = output_dir

        # 3. Classify each ref
        classified: List[Dict[str, Any]] = []
        for i, ref in enumerate(refs, start=1):
            _progress("verifying", i, len(refs), ref)
            log.info(f"[{i}/{len(refs)}] classifying: {ref[:60]!r}")
            try:
                c = classify_ref(ref, threshold_verified=threshold_verified,
                                 threshold_likely=threshold_likely)
            except Exception as e:
                log.error(f"classify_ref failed for {ref[:60]!r}: {e}")
                c = {
                    "ref": ref, "status": "FAKE", "score": 0.0, "reason": "",
                    "matched_title": "", "matched_doi": "", "matched_authors": "",
                    "matched_year": "", "matched_url": "", "source_platform": "",
                    "source_count": 0, "candidates_count": 0,
                    "error": str(e),
                }
            classified.append(c)
            # Log progress to stdout (useful in CLI)
            print(f"  [{i:03d}/{len(refs):03d}] {c['status']:11s} score={c['score']:.2f}  {ref[:70]!r}",
                  flush=True)

        # 4. Tally
        for c in classified:
            st = c.get("status", "FAKE")
            if st == "VERIFIED":
                out["verified"] += 1
            elif st == "LIKELY":
                out["likely"] += 1
            elif st == "UNVERIFIED":
                out["unverified"] += 1
            else:
                out["fake"] += 1

        # 5. Download PDFs for verified refs
        if download_pdfs and out["verified"] > 0:
            _progress("downloading", 0, out["verified"])
            download_verified_papers(classified, Path(output_dir))
            out["pdfs_downloaded"] = sum(
                1 for c in classified if c.get("download_success"))

        # 6. Save classified JSON
        import json
        results_json = os.path.join(output_dir, "02_Verification_Results",
                                    "classification_results.json")
        with open(results_json, "w", encoding="utf-8") as f:
            json.dump(classified, f, ensure_ascii=False, indent=2)

        # 7. Save parsed input refs (for traceability)
        refs_file = os.path.join(output_dir, "00_Input_References",
                                 f"input_refs_{int(time.time())}.txt")
        with open(refs_file, "w", encoding="utf-8") as f:
            f.write(f"# Source: {source_desc}\n# Total: {len(refs)} references\n\n")
            for i, r in enumerate(refs, 1):
                f.write(f"[{i}] {r}\n\n")

        # 8. Build reports
        _progress("reporting", 0, 1)
        excel_path = os.path.join(output_dir, "02_Verification_Results",
                                  "master_database_verifyrefs.xlsx")
        docx_path = os.path.join(output_dir, "02_Verification_Results",
                                 "literature_verification_report.docx")
        try:
            build_excel_report(classified, excel_path, source_desc=source_desc)
        except Exception as e:
            log.error(f"Excel report build failed: {e}")
        try:
            build_docx_report(classified, docx_path, source_desc=source_desc)
        except Exception as e:
            log.error(f"DOCX report build failed: {e}")
        out["excel_path"] = excel_path
        out["docx_path"] = docx_path
        out["results"] = classified
        out["success"] = True
        _progress("done", len(refs), len(refs))
        log.info(
            f"Verification complete: VERIFIED={out['verified']} LIKELY={out['likely']} "
            f"UNVERIFIED={out['unverified']} FAKE={out['fake']} "
            f"PDFs={out['pdfs_downloaded']}")
        return out

    except Exception as e:
        out["error"] = str(e)
        log.error(f"run_verification failed: {e}")
        import traceback
        log.error(traceback.format_exc())
        return out
