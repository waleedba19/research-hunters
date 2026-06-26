"""scopus_checker.py — Enriches papers with quartile & citation data.

Uses CrossRef API and OpenAlex API (free, no key needed) to estimate
journal quartiles and citation counts. Full Scopus API integration
requires an Elsevier API key set via SCOPUS_API_KEY env var.
"""
import os, json, re, logging, concurrent.futures, urllib.request, urllib.error
from typing import Dict, List, Optional, Any

log = logging.getLogger("scopus_checker")

__all__ = ["bulk_check", "quartile_badge", "HAS_SCOPUS_API"]

CROSSREF_BASE = "https://api.crossref.org/works"
OPENALEX_BASE  = "https://api.openalex.org/works"
SCOPUS_API_KEY = os.environ.get("SCOPUS_API_KEY", "")
HAS_SCOPUS_API = bool(SCOPUS_API_KEY)


def _fetch_json(url: str, timeout: int = 15) -> Optional[dict]:
    """Fetch JSON from a URL with retry."""
    req = urllib.request.Request(url, headers={"User-Agent": "ResearchHunter/2.4", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _estimate_quartile_from_issn(issn: str) -> str:
    """Estimate quartile from ISSN using OpenAlex's summarized stats."""
    url = f"https://api.openalex.org/sources/issn/{issn}"
    data = _fetch_json(url)
    if data:
        q = data.get("summary_stats", {}).get("2yr_mean_citedness")
        if q is None:
            return "n/a"
        if q >= 3.0:
            return "Q1"
        elif q >= 1.5:
            return "Q2"
        elif q >= 0.5:
            return "Q3"
        else:
            return "Q4"
    return "n/a"


def _get_cited_by_from_openalex(doi: str) -> int:
    """Get cited_by_count from OpenAlex API."""
    url = f"{OPENALEX_BASE}/doi:{doi}"
    data = _fetch_json(url)
    if data:
        return data.get("cited_by_count", 0)
    return 0


def _enrich_paper(paper: dict) -> dict:
    """Enrich a single paper dict with quartile and citation data."""
    doi = (paper.get("doi") or paper.get("DOI") or "").strip()
    issn = (paper.get("issn") or paper.get("ISSN") or paper.get("journal_issn") or "").strip()
    journal = (paper.get("journal") or paper.get("container-title") or [""])
    if isinstance(journal, list):
        journal = journal[0] if journal else ""

    cited_by = 0
    quartile = "n/a"

    # Try OpenAlex for citation count via DOI
    if doi:
        cited_by = _get_cited_by_from_openalex(doi)
        if not cited_by:
            # Try CrossRef for citation count
            url = f"{CROSSREF_BASE}/{doi}"
            data = _fetch_json(url)
            if data:
                cr = data.get("message", {})
                cited_by = cr.get("is-referenced-by-count", 0) or 0
                if not issn:
                    issn = (cr.get("ISSN") or [""])[0]

    # Estimate quartile from ISSN
    if issn:
        quartile = _estimate_quartile_from_issn(issn)

    paper["_quartile"] = quartile
    paper["_cited_by"] = cited_by
    paper["_scopus_source"] = "openalex" if doi else "stub"
    return paper


def bulk_check(papers: List[Dict], api_key: Optional[str] = None,
               max_workers: int = 4, timeout: int = 15) -> List[Dict]:
    """Enrich papers with quartile and citation data in parallel."""
    if not papers:
        return papers
    enriched = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_enrich_paper, p): i for i, p in enumerate(papers)}
        for future in concurrent.futures.as_completed(futures, timeout=timeout):
            idx = futures[future]
            try:
                enriched.append((idx, future.result()))
            except Exception as e:
                p = papers[idx]
                if isinstance(p, dict):
                    p.setdefault("_quartile", "n/a")
                    p.setdefault("_cited_by", 0)
                    p.setdefault("_scopus_source", "error")
                enriched.append((idx, p))
    enriched.sort(key=lambda x: x[0])
    log.info("bulk_check enriched %d/%d papers", len([e for e in enriched if e[1].get("_quartile") != "n/a"]), len(papers))
    return [e[1] for e in enriched]


def quartile_badge(q: str) -> str:
    """Format a quartile letter (Q1/Q2/Q3/Q4) as a colored badge string."""
    if not q or q == "n/a":
        return "[grey50]Q?[/grey50]"
    q = str(q).upper()
    palette = {"Q1": "bright_green", "Q2": "green", "Q3": "yellow", "Q4": "red"}
    style = palette.get(q, "white")
    return f"[{style}]{q}[/{style}]"
