"""
fanout_merge.py — Fan-out → Merge unified research workflow.

Splits a research topic into parallel sub-hunts (one per research question or
sub-topic), then merges all results into a single unified report with
deduplication and synthesis.

Usage:
    from fanout_merge import fanout_and_merge
    report_data = fanout_and_merge(params, progress_callback)

The merge phase combines multiple `report_data` dicts (as produced by
`research_hunter_v2-4.generate_docx_report`) into one:
  - Deduplicates papers by DOI → title-hash → URL.
  - Aggregates run_stats (q_distribution, type/geo distributions, counts).
  - Merges ai_queries, platforms_searched, study_keywords (union, ordered).
  - Preserves the deepest pdf_reader data when the same paper appears in
    multiple sub-hunts.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from logger import get_logger

log = get_logger(__name__)


# ── Deduplication keys ──────────────────────────────────────────────────────

def _norm_doi(doi: Any) -> str:
    """Normalize a DOI for dedup (lowercase, strip prefix, trim)."""
    if not doi or not isinstance(doi, str):
        return ""
    d = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:", "doi.org/"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d.strip()


def _title_hash(title: Any) -> str:
    """Produce a stable hash for a paper title (ignoring case/punctuation)."""
    if not title or not isinstance(title, str):
        return ""
    t = re.sub(r"[^\w\s]", " ", title.lower())
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) < 15:
        return ""
    return hashlib.md5(t.encode("utf-8")).hexdigest()[:16]


def _norm_url(url: Any) -> str:
    """Normalize a URL for dedup (strip trailing slash, lowercase host)."""
    if not url or not isinstance(url, str):
        return ""
    u = url.strip().lower()
    if u.endswith("/") and u.count("/") > 3:
        u = u.rstrip("/")
    return u


def _paper_key(paper: Dict[str, Any]) -> tuple:
    """Return a (kind, value) dedup key for a paper, preferring DOI then title then URL."""
    doi = _norm_doi(paper.get("doi"))
    if doi:
        return ("doi", doi)
    th = _title_hash(paper.get("title"))
    if th:
        return ("title", th)
    url = _norm_url(paper.get("url"))
    if url:
        return ("url", url)
    return ("none", "")


# ── Merge logic ─────────────────────────────────────────────────────────────

def _deep_merge_dicts(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge dict b into dict a. Returns a new merged dict.

    - Scalars: b wins only if a's value is empty/None.
    - Dicts: recurse.
    - Lists: union (preserving order, deduping hashable items).
    """
    result = dict(a)
    for key, bval in b.items():
        aval = result.get(key)
        if aval in (None, "", [], {}):
            result[key] = bval
        elif bval in (None, "", [], {}):
            continue
        elif isinstance(aval, dict) and isinstance(bval, dict):
            result[key] = _deep_merge_dicts(aval, bval)
        elif isinstance(aval, list) and isinstance(bval, list):
            seen = set()
            out = []
            for item in aval + bval:
                k = item if isinstance(item, (str, int, float)) else str(item)
                if k not in seen:
                    seen.add(k)
                    out.append(item)
            result[key] = out
    return result


def _merge_paper(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two copies of the same paper, keeping the richest data."""
    return _deep_merge_dicts(a, b)


def merge_reports(reports: List[Dict[str, Any]],
                  unified_title: str = "",
                  unified_field: str = "") -> Dict[str, Any]:
    """Merge multiple report_data dicts into one unified report_data.

    Args:
        reports: list of report_data dicts (from run_hunt / generate_docx_report).
        unified_title: override title for the merged report.
        unified_field: override field for the merged report.

    Returns:
        A single report_data dict with all papers deduplicated and stats aggregated.
    """
    if not reports:
        return {}
    if len(reports) == 1:
        r = dict(reports[0])
        if unified_title:
            r["title"] = unified_title
        if unified_field:
            r["field"] = unified_field
        return r

    log.info(f"Merging {len(reports)} sub-reports...")

    # ── Deduplicate papers ──
    seen: Dict[tuple, Dict[str, Any]] = {}
    total_before = 0
    for report in reports:
        for paper in report.get("papers", []):
            total_before += 1
            key = _paper_key(paper)
            if key[1] and key in seen:
                seen[key] = _merge_paper(seen[key], paper)
            else:
                seen[key] = paper
    all_papers = list(seen.values())
    dupes_removed = total_before - len(all_papers)
    log.info(f"  Papers: {total_before} → {len(all_papers)} ({dupes_removed} duplicates removed)")

    # ── Aggregate stats ──
    q_dist = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0, "Not Found": 0}
    type_cnt = {"PhD": 0, "MA": 0, "Book": 0, "BookChapter": 0, "Conference": 0}
    geo_cnt = {"Libya": 0, "Neighbor": 0, "MENA": 0}
    new_total = 0
    dl_total = 0
    for report in reports:
        rs = report.get("run_stats", {})
        rq = rs.get("q_distribution", {})
        for k, v in rq.items():
            if k in q_dist:
                q_dist[k] += v
        rt = rs.get("type_distribution", {})
        for k, v in rt.items():
            if k in type_cnt:
                type_cnt[k] += v
        rg = rs.get("geo_distribution", {})
        for k, v in rg.items():
            if k in geo_cnt:
                geo_cnt[k] += v
        new_total += rs.get("new_this_run", 0)
        dl_total += rs.get("downloaded_this_run", 0)

    # ── Merge query/platform/keyword lists (union, ordered) ──
    def _union_lists(key: str) -> list:
        seen_vals = set()
        out = []
        for report in reports:
            vals = report.get(key, [])
            if not isinstance(vals, list):
                vals = [vals]
            for v in vals:
                if v and v not in seen_vals:
                    seen_vals.add(v)
                    out.append(v)
        return out

    ai_queries = _union_lists("ai_queries")
    platforms = _union_lists("platforms_searched")
    keywords = _union_lists("study_keywords")
    queries_used = _union_lists("queries_used")

    first = reports[0]
    merged = {
        "title":              unified_title or first.get("title", "Unified Research Report"),
        "field":             unified_field or first.get("field", "general"),
        "study_types":       first.get("study_types", []),
        "year_range":        first.get("year_range", ""),
        "search_mode":       first.get("search_mode", "normal"),
        "platforms_searched": platforms,
        "ai_queries":         ai_queries,
        "queries_used":       queries_used,
        "study_keywords":     keywords,
        "search_language":    first.get("search_language", "English"),
        "country_context":    first.get("country_context", "International"),
        "papers":             all_papers,
        "executive_summary":  "",
        "generated_at":       first.get("generated_at", ""),
        "user_filters":       first.get("user_filters", {}),
        "run_stats": {
            "new_this_run":        new_total,
            "downloaded_this_run": dl_total,
            "total_in_cache":      len(all_papers),
            "q_distribution":      q_dist,
            "type_distribution":   type_cnt,
            "geo_distribution":    geo_cnt,
            "red_list_count":      sum(r.get("run_stats", {}).get("red_list_count", 0) for r in reports),
            "folder_downloads":    sum(r.get("run_stats", {}).get("folder_downloads", 0) for r in reports),
            "sub_reports_merged":  len(reports),
            "duplicates_removed":  dupes_removed,
        },
    }
    log.info(f"  Merged report: {len(all_papers)} papers, "
             f"{len(platforms)} platforms, {len(ai_queries)} queries")
    return merged


# ── Sub-topic splitting ─────────────────────────────────────────────────────

def split_into_subhunts(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Split a single hunt into multiple parallel sub-hunts.

    Each research question (or auto-generated sub-topic) becomes its own sub-hunt
    with a focused query set. Returns a list of params dicts, each ready for
    run_hunt().

    Args:
        params: the original hunt params dict (title, field, research_questions, etc.)

    Returns:
        List of sub-hunt params dicts. If no sub-topics can be derived, returns
        a single-element list with the original params.
    """
    title = params.get("title", "")
    field = params.get("field", "general")
    rqs = params.get("research_questions", [])
    study_keywords = params.get("study_keywords", [])

    subhunts: List[Dict[str, Any]] = []

    if rqs:
        # One sub-hunt per research question
        for i, rq in enumerate(rqs):
            rq_str = rq if isinstance(rq, str) else str(rq.get("question", rq))
            if not rq_str.strip():
                continue
            sub = dict(params)
            sub["title"] = f"{title} — RQ{i+1}: {rq_str[:80]}"
            sub["research_questions"] = [rq]
            sub["_subhunt_label"] = f"RQ{i+1}"
            subhunts.append(sub)

    if not subhunts and study_keywords:
        # Fall back to study keywords as sub-topics
        for i, kw in enumerate(study_keywords):
            kw_str = kw if isinstance(kw, str) else str(kw)
            if not kw_str.strip():
                continue
            sub = dict(params)
            sub["title"] = f"{title} — Aspect {i+1}: {kw_str[:80]}"
            sub["study_keywords"] = [kw]
            sub["_subhunt_label"] = f"Aspect{i+1}"
            subhunts.append(sub)

    if not subhunts:
        # No splittable sub-topics — single hunt
        return [dict(params)]

    # Propagate shared fields to every sub-hunt
    for sub in subhunts:
        sub.setdefault("field", field)
        sub.setdefault("platforms", params.get("platforms", ["all"]))
        sub.setdefault("search_mode", params.get("search_mode", "normal"))
        sub.setdefault("download_pdfs", params.get("download_pdfs", True))

    log.info(f"Split '{title[:50]}' into {len(subhunts)} sub-hunts: "
             f"{[s.get('_subhunt_label') for s in subhunts]}")
    return subhunts


# ── Full fan-out → merge pipeline ──────────────────────────────────────────

def fanout_and_merge(
    params: Dict[str, Any],
    progress_callback: Optional[Callable[[str, str, float], None]] = None,
    out_folder: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run the full fan-out → merge pipeline.

    1. Splits the hunt into sub-hunts (one per research question / aspect).
    2. Runs each sub-hunt sequentially via hunt_pipeline.run_hunt.
    3. Merges all sub-report_data dicts into one unified report.
    4. Generates the unified DOCX + Excel + PDF in out_folder.

    Args:
        params: hunt params (same shape as hunt_pipeline.run_hunt expects).
        progress_callback: optional callback(stage, msg, progress).
        out_folder: where to write the merged report (default: pdf_files/<title>).

    Returns:
        The merged report_data dict.
    """
    from hunt_pipeline import run_hunt
    import research_hunter_v2_4 as v2_4

    def _log(stage: str, msg: str, progress: float):
        log.info(f"[{stage}] {msg} ({progress:.0%})")
        if progress_callback:
            try:
                progress_callback(stage, msg, progress)
            except Exception:
                pass

    title = params.get("title", "Research")
    subhunts = split_into_subhunts(params)
    n = len(subhunts)

    _log("fanout_start", f"Fan-out: {n} sub-hunt(s) for '{title[:60]}'", 0.0)

    sub_reports: List[Dict[str, Any]] = []
    for i, sub in enumerate(subhunts):
        label = sub.pop("_subhunt_label", f"Sub{i+1}")
        base_progress = i / n
        chunk_progress = 1.0 / n

        def sub_cb(stage: str, msg: str, p: float, _bp=base_progress, _cp=chunk_progress):
            _log(stage, f"[{label}] {msg}", _bp + p * _cp)

        _log("subhunt_start", f"Starting {label} ({i+1}/{n})", base_progress)
        try:
            result = run_hunt(sub, progress_callback=sub_cb)
            report_data = result.get("results") if isinstance(result, dict) else None
            if report_data:
                report_data["_subhunt_label"] = label
                sub_reports.append(report_data)
            _log("subhunt_done", f"{label} complete", base_progress + chunk_progress * 0.9)
        except Exception as e:
            log.error(f"Sub-hunt {label} failed: {e}")
            _log("subhunt_error", f"{label} failed: {e}", base_progress + chunk_progress * 0.9)

    _log("merge_start", f"Merging {len(sub_reports)} sub-reports...", 0.95)

    unified_title = title  # use the original (non-split) title
    unified_field = params.get("field", "general")
    merged = merge_reports(sub_reports, unified_title=unified_title, unified_field=unified_field)

    if not merged or not merged.get("papers"):
        _log("merge_done", "No papers found across all sub-hunts", 1.0)
        return merged or {"papers": [], "title": unified_title, "field": unified_field}

    # Generate unified output files
    if out_folder is None:
        folder_name = v2_4._safe_name(title, 80) if hasattr(v2_4, "_safe_name") else "unified_report"
        out_folder = Path("pdf_files") / folder_name
    out_folder = Path(out_folder)
    out_folder.mkdir(parents=True, exist_ok=True)

    _log("generate_docx", "Generating unified DOCX report...", 0.97)
    try:
        docx_path = v2_4.generate_docx_report(merged, out_folder)
        _log("generate_docx", f"DOCX: {docx_path.name if docx_path else 'FAILED'}", 0.98)
    except Exception as e:
        log.error(f"DOCX generation failed: {e}")
        docx_path = None

    _log("generate_excel", "Generating unified Excel report...", 0.99)
    try:
        excel_path = None
        if hasattr(v2_4, "_write_master_xlsx"):
            excel_path = v2_4._write_master_xlsx(
                merged.get("papers", []),
                out_folder,
                queries_used=merged.get("queries_used", merged.get("ai_queries", [])),
            )
        _log("generate_excel", f"Excel: {excel_path.name if excel_path else 'N/A'}", 1.0)
    except Exception as e:
        log.error(f"Excel generation failed: {e}")
        excel_path = None

    # PDF via report_pdf
    if docx_path:
        try:
            from report_pdf import docx_to_pdf
            pdf_path = docx_to_pdf(docx_path, timeout=300)
            _log("generate_pdf", f"PDF: {pdf_path.name if pdf_path else 'FAILED'}", 1.0)
        except Exception as e:
            log.error(f"PDF generation failed: {e}")

    _log("fanout_complete",
         f"Unified report: {len(merged.get('papers', []))} papers from {len(sub_reports)} sub-hunts",
         1.0)
    return merged


if __name__ == "__main__":
    import json, sys
    # CLI: python fanout_merge.py --params params.json
    if len(sys.argv) < 2:
        print("Usage: python fanout_merge.py --params <params.json> [--out <dir>]")
        sys.exit(1)
    args = sys.argv[1:]
    params_file = None
    out_dir = None
    i = 0
    while i < len(args):
        if args[i] == "--params" and i + 1 < len(args):
            params_file = args[i + 1]
            i += 2
        elif args[i] == "--out" and i + 1 < len(args):
            out_dir = args[i + 1]
            i += 2
        else:
            i += 1
    if not params_file:
        print("Error: --params is required")
        sys.exit(1)
    with open(params_file) as f:
        params = json.load(f)
    result = fanout_and_merge(params, out_folder=Path(out_dir) if out_dir else None)
    print(f"Merged report: {len(result.get('papers', []))} papers")
