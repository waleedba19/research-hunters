"""
hunt_pipeline.py — Non-interactive wrapper around v2-4's SUPER LOADED pipeline
for Telegram bot integration.

Exposes:
    run_hunt(params, progress_callback=None) -> dict

The `progress_callback` function is called at each stage:
    progress_callback(stage: str, message: str, progress: float)

Stage values:
    "starting"          — initializing
    "generating_queries"  — AI query generation
    "searching"         — searching platforms
    "deduplicating"     — deduplication + relevance filter
    "checking_quartiles" — quartile/batch check
    "downloading"       — downloading PDFs
    "generating_report" — building reports
    "done"              — complete
"""

import os
import sys
import json
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable

# Load v2-4 via the existing shim (handles dashes in module name)
import research_hunter_v2_4 as v2_4

from search_cache import SearchCache
from scopus_checker import quartile_badge

# Re-import what v2-4 doesn't re-export
Q_FOLDER_MAP = getattr(v2_4, "Q_FOLDER_MAP", {})
ALL_EXTRA_FOLDERS = getattr(v2_4, "ALL_EXTRA_FOLDERS", [])
HAS_DRISSIONPAGE = getattr(v2_4, "HAS_DRISSIONPAGE", False)

# Map human-readable names to v2-4's internal platform keys (auto-generated)
PLATFORM_ALIASES = {
    "semantic scholar": "Semantic Scholar",
    "semantic_scholar": "Semantic Scholar",
    "openalex": "OpenAlex",
    "core": "CORE",
    "core api": "CORE API",
    "core_api": "CORE API",
    "crossref": "CrossRef",
    "eric": "ERIC",
    "doaj": "DOAJ",
    "hal archives": "HAL Archives",
    "hal_archives": "HAL Archives",
    "base": "BASE",
    "pubmed": "PubMed",
    "arxiv": "arXiv",
    "zenodo": "Zenodo",
    "zenodo extended": "Zenodo Extended",
    "zenodo_extended": "Zenodo Extended",
    "scielo": "SciELO",
    "europe pmc": "Europe PMC",
    "europe_pmc": "Europe PMC",
    "plos one": "PLoS ONE",
    "plos_one": "PLoS ONE",
    "oxford up": "Oxford UP",
    "oxford_up": "Oxford UP",
    "springer open": "Springer Open",
    "springer_open": "Springer Open",
    "wiley open": "Wiley Open",
    "wiley_open": "Wiley Open",
    "taylor & francis": "Taylor & Francis",
    "taylor_and_francis": "Taylor & Francis",
    "sciencedirect": "ScienceDirect",
    "ssrn": "SSRN",
    "biorxiv": "bioRxiv",
    "medrxiv": "medRxiv",
    "psyarxiv": "PsyArXiv",
    "socarxiv": "SocArXiv",
    "osf preprints": "OSF Preprints",
    "osf_preprints": "OSF Preprints",
    "mdpi": "MDPI",
    "openaire": "OpenAIRE",
    "worldwidescience": "WorldWideScience",
    "cern document": "CERN Document",
    "cern_document": "CERN Document",
    "science.gov": "Science.gov",
    "sciencegov": "Science.gov",
    "nasa ntrs": "NASA NTRS",
    "nasa_ntrs": "NASA NTRS",
    "digital commons": "Digital Commons",
    "digital_commons": "Digital Commons",
    "jstor open": "JSTOR Open",
    "jstor_open": "JSTOR Open",
    "ebsco dissertations": "EBSCO Dissertations",
    "ebsco_dissertations": "EBSCO Dissertations",
    "ssoar": "SSOAR",
    "academia.edu": "Academia.edu",
    "academiaedu": "Academia.edu",
    "paperpanda": "PaperPanda",
    "redalyc": "Redalyc",
    "bioline int'l": "BioLine Int'l",
    "bioline_intl": "BioLine Int'l",
    "philpapers": "PhilPapers",
    "directory of oa books": "Directory of OA Books",
    "directory_of_oa_books": "Directory of OA Books",
    "cogprints": "CogPrints",
    "ajol": "AJOL",
    "scielo brazil": "SciELO Brazil",
    "scielo_brazil": "SciELO Brazil",
    "dialnet": "Dialnet",
    "anna's archive": "Anna's Archive",
    "annas_archive": "Anna's Archive",
    "sci-hub multi": "Sci-Hub Multi",
    "sci-hub_multi": "Sci-Hub Multi",
    "genemedi": "Genemedi",
    "shadow libraries": "Shadow Libraries",
    "shadow_libraries": "Shadow Libraries",
    "scinet": "SciNet",
    "scibay": "SciBay",
    "grokipedia": "Grokipedia",
    "internet archive": "Internet Archive",
    "internet_archive": "Internet Archive",
    "google scholar": "Google Scholar",
    "google_scholar": "Google Scholar",
    "researchgate": "ResearchGate",
    "z-library": "Z-Library",
    "libgen": "LibGen",
    "duckduckgo": "DuckDuckGo",
    "perplexica": "Perplexica",
    "oatd": "OATD",
    "ethos": "EThOS",
    "ohiolink etd": "OhioLINK ETD",
    "ohiolink_etd": "OhioLINK ETD",
    "nature": "Nature",
    "academicianhelp": "AcademicianHelp",
    "elife sciences": "eLife Sciences",
    "elife_sciences": "eLife Sciences",
    "scienceopen": "ScienceOpen",
    "oa.mg": "OA.mg",
    "oamg": "OA.mg",
    "ss": "Semantic Scholar",
    "googlescholar": "Google Scholar",
    "scopus": "Semantic Scholar",
    # v6.1 expansion aliases
    "connected papers": "Connected Papers",
    "connectedpapers": "Connected Papers",
    "lens": "Lens.org",
    "lens.org": "Lens.org",
    "datacite": "DataCite",
    "figshare": "Figshare",
    "dryad": "Dryad",
    "chemrxiv": "ChemRxiv",
    "research square": "Research Square",
    "researchsquare": "Research Square",
    "opendoar": "OpenDOAR",
    "nber": "NBER",
    "repec": "RePEc",
    "google dataset": "Google Dataset Search",
    "google_dataset": "Google Dataset Search",
}


def _resolve_platforms(platforms: list) -> list:
    """Resolve human-readable platform names to v2-4 keys."""
    PLATFORM_FNS = getattr(v2_4, "PLATFORM_FNS", {})
    resolved = []
    for p in platforms:
        key = PLATFORM_ALIASES.get(p.lower().strip(), p)
        if key in PLATFORM_FNS or key == "all":
            resolved.append(key)
    if not resolved or "all" in resolved:
        return list(PLATFORM_FNS.keys())
    return resolved


def _safe_name(name: str, mx: int = 80) -> str:
    """Safe folder name from a topic string. Local impl so it works even if v2-4 is missing."""
    import re
    s = re.sub(r'[^\w\s\-\.]', '_', (name or "untitled"))
    s = re.sub(r'\s+', '_', s).strip('_')
    if not s:
        s = "untitled"
    if len(s) > mx:
        s = s[:mx].rstrip('_')
    return s


def _progress_log(progress_cb, stage: str, msg: str, progress: float):
    """Log via callback if provided."""
    if progress_cb:
        try:
            progress_cb(stage, msg, progress)
        except Exception:
            pass


def run_hunt(
    params: dict,
    progress_callback: Optional[Callable[[str, str, float], None]] = None,
) -> dict:
    """
    Run the full v2-4 research pipeline non-interactively.

    Parameters (in `params` dict):
        title (str) — research topic / title
        field (str) — academic field (default "general")
        study_types (list) — study types to focus on
        year_from (int|None) — start year
        year_to (int|None) — end year
        research_questions (list) — research questions for query generation
        platforms (list) — platform names
        search_mode (str) — "normal" or "deep"
        use_scihub (bool) — enable Sci-Hub downloads
        single_folder (bool) — save all PDFs to one folder
        study_keywords (list) — extra keywords
        lang_label (str) — language label
        search_languages (list) — language codes
        country_context (list|None) — geographic context override

    Returns:
        dict with keys:
            success (bool)       — True if pipeline completed without errors
            output_folder (str)  — path to the output folder (always set, even on failure)
            total_papers (int)   — total papers found
            downloaded (int)     — PDFs downloaded this run
            red_list_count (int) — papers that failed all download layers
            results (dict)       — full report_data dict (for further processing)
            error (str|None)     — error message if success=False
    """
    _progress_log(progress_callback, "starting", "Initializing hunt pipeline...", 0.0)

    # ── Defaults ────────────────────────────────────────────────────────────
    import traceback
    log = _get_logger("hunt_pipeline.run_hunt")

    try:
        return _run_hunt_impl(params, progress_callback, log)
    except KeyboardInterrupt:
        raise
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        log.error(f"run_hunt failed: {err}\n{traceback.format_exc()}")
        _progress_log(
            progress_callback, "failed",
            f"Pipeline error: {err[:200]}",
            1.0,
        )
        out_folder = Path("pdf_files") / _safe_name(params.get("title", "Research Topic"), 80)
        return {
            "success": False,
            "output_folder": str(out_folder),
            "total_papers": 0,
            "downloaded": 0,
            "red_list_count": 0,
            "results": {},
            "error": err,
        }


def _get_logger(name: str):
    """Get a logger that doesn't crash if logger.py is missing."""
    try:
        from logger import get_logger
        return get_logger(name)
    except Exception:
        import logging
        return logging.getLogger(name)


def _run_hunt_impl(
    params: dict,
    progress_callback: Optional[Callable[[str, str, float], None]],
    log,
) -> dict:
    """Internal implementation of run_hunt. Always called via the wrapper."""
    title = params.get("title", "Research Topic")
    field = params.get("field", "general")
    study_types = params.get("study_types", [])
    year_from = params.get("year_from")
    year_to = params.get("year_to")
    rqs = params.get("research_questions", [])
    platforms_raw = params.get("platforms", ["all"])
    mode = params.get("search_mode", "normal")
    use_scihub = params.get("use_scihub", False)
    study_keywords = params.get("study_keywords", [])
    lang_label = params.get("lang_label", "English")
    search_languages = params.get("search_languages", ["en"])
    single_folder = params.get("single_folder", False)
    country_context = params.get("country_context") or v2_4.detect_country_context(title, rqs)

    # Resolve platforms
    platforms = _resolve_platforms(platforms_raw)
    if not platforms:
        platforms = list(getattr(v2_4, "PLATFORM_FNS", {}).keys())

    _progress_log(
        progress_callback, "starting",
        f"Topic: {title[:60]} | Field: {field} | Platforms: {len(platforms)} | Mode: {mode}",
        0.02,
    )

    # ── Output folder & cache ──────────────────────────────────────────────
    folder_name = _safe_name(title, 80)
    out_folder = Path("pdf_files") / folder_name
    out_folder.mkdir(parents=True, exist_ok=True)

    # Create subfolders (same as v2-4 main())
    if not single_folder:
        all_fn = list(set(Q_FOLDER_MAP.values())) + ALL_EXTRA_FOLDERS
        for fn in all_fn:
            try:
                (out_folder / fn).mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

    # Scan existing PDFs for duplicate avoidance
    existing_titles = v2_4.scan_existing_pdfs(out_folder)

    cache = SearchCache(out_folder)
    stats = cache.stats()
    if stats.get("total_found", 0) > 0:
        _progress_log(
            progress_callback, "starting",
            f"Resuming previous — {stats['total_found']} papers cached "
            f"({stats.get('total_downloaded', 0)} downloaded, {stats.get('queries_used', 0)} queries used)",
            0.03,
        )

    # Start optional proxy
    v2_4.start_g4f_proxy()

    # Red List manager
    red_list = v2_4.RedListManager(out_folder)

    # ── Generate queries ────────────────────────────────────────────────────
    _progress_log(progress_callback, "generating_queries", "Generating AI search queries...", 0.05)

    used_q = list(cache.queries_used() or [])
    queries = v2_4.generate_queries(
        title, field, study_types, rqs, year_from, used_q, country_context
    )

    # Inject study keywords as extra queries
    extra_kw_queries = [
        kw for kw in study_keywords
        if len(kw.split()) >= 2 and kw.lower() not in {q.lower() for q in list(queries) + used_q}
    ]
    queries = list(queries) + extra_kw_queries[:8]
    queries = queries[:25]

    cache.add_queries(queries)
    cache.save()

    _progress_log(
        progress_callback, "generating_queries",
        f"Generated {len(queries)} queries", 0.10,
    )

    # ── Search all platforms ────────────────────────────────────────────────
    _progress_log(
        progress_callback, "searching",
        f"Searching {len(platforms)} platforms in {mode} mode...", 0.15,
    )

    raw = v2_4.search_all(
        queries, platforms,
        year_from=year_from, year_to=year_to,
        field=field, country_context=country_context,
        topic_slug=folder_name,
    )

    _progress_log(
        progress_callback, "searching",
        f"Raw results: {len(raw)} papers found", 0.30,
    )

    # ── Deduplicate ──────────────────────────────────────────────────────────
    _progress_log(progress_callback, "deduplicating", "Deduplicating results...", 0.35)

    deduped = cache.deduplicate(raw)
    _progress_log(
        progress_callback, "deduplicating",
        f"After dedup: {len(deduped)} papers", 0.40,
    )

    # ── Relevance filter ────────────────────────────────────────────────────
    relevant, removed = v2_4.filter_by_relevance(deduped, title, field, threshold=0.15)
    if removed:
        _progress_log(
            progress_callback, "deduplicating",
            f"Relevance filter removed {removed} unrelated papers", 0.45,
        )

    # Filter already-known
    new_papers, skipped = cache.filter_new(relevant)
    if skipped:
        _progress_log(
            progress_callback, "deduplicating",
            f"Skipped {skipped} already-found papers", 0.50,
        )

    # Filter existing PDFs
    if existing_titles:
        truly_new = []
        dup_count = 0
        for p in new_papers:
            if v2_4.is_duplicate_paper(p, existing_titles):
                dup_count += 1
            else:
                truly_new.append(p)
        if dup_count > 0:
            _progress_log(
                progress_callback, "deduplicating",
                f"Skipped {dup_count} papers already downloaded as PDFs", 0.52,
            )
        new_papers = truly_new

    if not new_papers:
        _progress_log(
            progress_callback, "done",
            "No new papers found. Try Deep mode, more RQs, or broader topic.",
            1.0,
        )
        return {
            "success": True,
            "output_folder": str(out_folder),
            "total_papers": 0,
            "downloaded": 0,
            "red_list_count": 0,
            "results": {},
            "error": None,
        }

    for p in new_papers:
        cache.mark_found(p)

    # Optional cap on number of papers to process (used by smoke tests)
    max_papers = params.get("max_papers")
    if max_papers and isinstance(max_papers, int) and max_papers > 0:
        if len(new_papers) > max_papers:
            _progress_log(
                progress_callback, "deduplicating",
                f"Capping to {max_papers} papers (smoke-test mode)", 0.54,
            )
            new_papers = new_papers[:max_papers]

    # ═══════ INTERLEAVED QUARTILE + DOWNLOAD PIPELINE ═══════
    _progress_log(progress_callback, "checking_quartiles", "Checking quartiles & downloading...", 0.55)

    BATCH_SIZE = 50
    dl_count = 0
    type_cnt = {"PhD": 0, "MA": 0, "Book": 0, "BookChapter": 0, "Conference": 0}
    geo_cnt = {"Libya": 0, "Neighbor": 0, "MENA": 0}
    folder_dl = {}
    q_cnt = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0, "Not Found": 0}
    total_batches = (len(new_papers) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(total_batches):
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(new_papers))
        batch = new_papers[start:end]
        batch_num = batch_idx + 1

        # Step A: Check quartiles
        seen = {}
        for p in batch:
            journal = (p.get("journal") or p.get("venue") or "") or ""
            if not journal.strip():
                p["scopus_quartile"] = {"quartile": "Not Found"}
                continue
            jkey = journal.lower().strip()
            if jkey in seen:
                p["scopus_quartile"] = seen[jkey]
            else:
                try:
                    r = check_quartile_wrapper(journal)
                except Exception:
                    r = {"quartile": "Not Found", "verified": False}
                qval = r.get("quartile", "") if isinstance(r, dict) else str(r)
                if not qval or qval in ("Not Found", "Not Ranked", ""):
                    upgraded = v2_4.enhanced_quartile_check(p)
                    if upgraded and upgraded not in ("Not Found", ""):
                        if isinstance(r, dict):
                            r["quartile"] = upgraded
                        else:
                            r = {"quartile": upgraded}
                seen[jkey] = r
                p["scopus_quartile"] = r

        # Step B: Count quartiles
        for p in batch:
            q = (p.get("scopus_quartile") or {})
            q = q.get("quartile", "Not Found") if isinstance(q, dict) else str(q)
            q_cnt[q if q in q_cnt else "Not Found"] += 1

        _progress_log(
            progress_callback, "checking_quartiles",
            f"Batch {batch_num}/{total_batches}: Q1={q_cnt['Q1']} Q2={q_cnt['Q2']} "
            f"Q3={q_cnt['Q3']} Q4={q_cnt['Q4']} N/A={q_cnt['Not Found']}",
            0.55 + (batch_idx / total_batches) * 0.25,
        )

        # Step C: Download batch
        for i, paper in enumerate(batch, 1):
            global_idx = start + i
            success, folder_used = v2_4.smart_file_paper(
                paper, out_folder, use_scihub, red_list, cache, single_folder
            )
            paper["downloaded"] = success
            if success:
                dl_count += 1
                folder_dl[folder_used] = folder_dl.get(folder_used, 0) + 1
            dt = v2_4.detect_doc_type(paper)
            if dt in type_cnt:
                type_cnt[dt] += 1
            gt = v2_4.detect_geo_tier(paper)
            if gt in geo_cnt:
                geo_cnt[gt] += 1
            if i % 10 == 0:
                _progress_log(
                    progress_callback, "downloading",
                    f"[{global_idx}/{len(new_papers)}] {dl_count} downloaded so far...",
                    0.55 + (batch_idx / total_batches) * 0.25 + (i / len(batch)) * (0.25 / total_batches),
                )
            time.sleep(0.15)

    cache.save()

    # ── Generate reports ─────────────────────────────────────────────────────
    _progress_log(progress_callback, "generating_report", "Generating reports...", 0.85)

    # Load & merge previous results
    existing = []
    results_path = out_folder / "results.json"
    if results_path.exists():
        try:
            prev = json.loads(results_path.read_text(encoding="utf-8"))
            existing = prev.get("papers") or []
        except Exception:
            pass

    all_papers = cache.deduplicate(new_papers + existing)

    # Overall stats
    all_q = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0, "Not Found": 0}
    for p in all_papers:
        q = (p.get("scopus_quartile") or {})
        q = q.get("quartile", "Not Found") if isinstance(q, dict) else str(q)
        all_q[q if q in all_q else "Not Found"] += 1

    report_data = {
        "title":               title,
        "field":               field,
        "study_types":         study_types,
        "year_range":          params.get("year_range", f"{year_from}-{year_to}" if year_from else ""),
        "search_mode":         mode,
        "platforms_searched":  platforms,
        "ai_queries":          queries,
        "study_keywords":      study_keywords,
        "search_language":     lang_label,
        "country_context":     " → ".join(country_context) if country_context else "International",
        "papers":              all_papers,
        "executive_summary":   "",
        "generated_at":        datetime.now().isoformat(),
        "run_stats": {
            "new_this_run":        len(new_papers),
            "downloaded_this_run": dl_count,
            "total_in_cache":      len(all_papers),
            "q_distribution":      all_q,
            "type_distribution":   type_cnt,
            "geo_distribution":    geo_cnt,
            "red_list_count":      len(red_list.entries),
            "folder_downloads":    folder_dl,
        },
    }
    report_data["executive_summary"] = v2_4.generate_executive_summary(report_data)

    # ── Generate future research directions (v6.5) ────────────────────────────
    # Uses ollama to suggest 3-5 gap-filling studies based on the literature.
    # Always returns at least the deterministic fallback.
    future_studies = []
    try:
        _progress_log(progress_callback, "generating_report",
                      "Generating future research directions...", 0.83)
        from future_studies import generate_future_studies
        future_studies = generate_future_studies(
            title=title, field=field,
            papers=all_papers, country_context=country_context,
            max_suggestions=5,
        )
        report_data["future_studies"] = future_studies
        log.info(f"Generated {len(future_studies)} future study suggestions")
    except Exception as e:
        log.warning(f"Future studies generation failed: {e}")
        report_data["future_studies"] = []

    # Save results.json
    results_path.write_text(
        json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    cache.record_run(len(new_papers), dl_count, skipped)
    cache.save()

    # Markdown + DOCX + XLSX reports
    md_path = v2_4.generate_markdown_report(report_data, out_folder)
    # Append the future_studies markdown section to the .md report
    try:
        if future_studies and md_path:
            from future_studies import to_markdown
            fs_md = to_markdown(future_studies, title=title)
            if fs_md:
                with open(md_path, "a", encoding="utf-8") as f:
                    f.write(fs_md)
                log.info(f"Appended {len(future_studies)} future studies to {md_path}")
    except Exception as e:
        log.warning(f"Failed to append future studies to .md: {e}")
    docx_path = v2_4.generate_docx_report(report_data, out_folder)
    xlsx_path = v2_4._write_master_xlsx(all_papers, out_folder)

    # ── Generate PDF (heavy report) ──────────────────────────────────────────
    # Tries LibreOffice (soffice, libreoffice), then docx2pdf.
    # Gracefully skips if neither is available — the DOCX is still produced.
    pdf_path = None
    if docx_path and Path(docx_path).exists():
        try:
            from report_pdf import docx_to_pdf
            _progress_log(progress_callback, "generating_report",
                          "Converting DOCX to PDF (heavy report)...", 0.92)
            pdf_path = docx_to_pdf(docx_path, timeout=600)
            if pdf_path:
                _progress_log(progress_callback, "generating_report",
                              f"PDF ready: {pdf_path.name} "
                              f"({pdf_path.stat().st_size:,} bytes)", 0.95)
            else:
                _progress_log(progress_callback, "generating_report",
                              "PDF skipped (no LibreOffice/Word installed — "
                              "DOCX still available)", 0.95)
        except Exception as e:
            log.warning(f"PDF generation failed: {e}")
            pdf_path = None

    total_dl = sum(1 for p in all_papers if p.get("downloaded"))

    _progress_log(
        progress_callback, "done",
        f"Hunt complete! {len(all_papers)} total papers, {total_dl} PDFs downloaded. "
        f"Q1:{all_q['Q1']} Q2:{all_q['Q2']} Q3:{all_q['Q3']} Q4:{all_q['Q4']}",
        1.0,
    )

    return {
        "success": True,
        "output_folder": str(out_folder),
        "total_papers": len(all_papers),
        "downloaded": dl_count,
        "red_list_count": len(red_list.entries),
        "future_studies_count": len(future_studies),
        "results": report_data,
        "docx_path": str(docx_path) if docx_path and Path(docx_path).exists() else None,
        "pdf_path": str(pdf_path) if pdf_path and Path(pdf_path).exists() else None,
        "xlsx_path": str(xlsx_path) if xlsx_path and Path(xlsx_path).exists() else None,
        "md_path": str(md_path) if md_path and Path(md_path).exists() else None,
        "results_path": str(results_path) if results_path.exists() else None,
        "error": None,
    }


def check_quartile_wrapper(journal_name: str) -> dict:
    """Check quartile for a journal. Uses v2-4's built-in logic.

    The original v2-4 calls `check_quartile(journal)` at line 5989 which
    is not defined in the file nor imported. This wrapper provides fallback
    logic using scopus_checker if available, then enhanced_quartile_check.
    """
    try:
        from scopus_checker import check_quartile
        return check_quartile(journal_name)
    except (ImportError, AttributeError):
        pass
    try:
        import scopus_checker
        if hasattr(scopus_checker, "check_quartile"):
            return scopus_checker.check_quartile(journal_name)
    except (ImportError, AttributeError):
        pass
    # Ultimate fallback: return Not Found
    return {"quartile": "Not Found", "verified": False}


def zip_results(out_folder: str) -> str:
    """Zip the output folder for download/upload. Returns path to zip file."""
    import shutil
    folder = Path(out_folder)
    zip_name = str(folder.parent / f"{folder.name}.zip")
    shutil.make_archive(str(folder), "zip", str(folder.parent), folder.name)
    return zip_name


if __name__ == "__main__":
    # Quick test: run a minimal hunt
    test_params = {
        "title": "Machine Learning in Education",
        "field": "education",
        "study_types": [],
        "year_from": 2020,
        "year_to": 2025,
        "research_questions": ["How is ML used in education?"],
        "platforms": ["crossref", "openalex"],
        "search_mode": "normal",
        "use_scihub": False,
        "single_folder": True,
        "study_keywords": [],
        "lang_label": "English",
        "search_languages": ["en"],
    }

    def cb(stage, msg, progress):
        print(f"[{progress:.0%}] {stage}: {msg[:80]}")

    result = run_hunt(test_params, progress_callback=cb)
    print(f"\nDone: {result['total_papers']} papers, {result['downloaded']} PDFs")
    print(f"Folder: {result['output_folder']}")
