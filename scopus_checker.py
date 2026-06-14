"""scopus_checker.py — STUB for v2-4 import.

The real scopus_checker.py is a private module of the user's
"v6 SUPER LOADED GOD MODE" research hunter. It hits the Scopus API
to add quartile (Q1/Q2/Q3/Q4) and citation counts to papers.

This stub returns empty data so v2-4's main search loop still runs
via its other 70+ search platforms. Once the user provides the real
scopus_checker.py, this stub can be replaced.

Usage by v2-4:
    from scopus_checker import bulk_check, quartile_badge
"""
import logging

log = logging.getLogger("scopus_checker_stub")

__all__ = ["bulk_check", "quartile_badge", "HAS_SCOPUS_API"]


def bulk_check(papers, api_key=None, max_workers=4, timeout=15):
    """Return papers unchanged with no Scopus enrichment.

    Real impl: queries Elsevier Scopus API for each paper's DOI/title,
    returns the same list with `_quartile` and `_cited_by` fields added.
    """
    if not papers:
        return papers
    log.warning(
        "scopus_checker.bulk_check: STUB mode — no Scopus API key configured. "
        "%d papers will not be quartile-enriched. Add the real scopus_checker.py "
        "to the repo to enable Scopus quartile scoring.", len(papers)
    )
    for p in papers:
        if isinstance(p, dict):
            p.setdefault("_quartile", "n/a")
            p.setdefault("_cited_by", 0)
            p.setdefault("_scopus_source", "stub")
    return papers


def quartile_badge(q):
    """Format a quartile letter (Q1/Q2/Q3/Q4) as a colored badge string."""
    if not q or q == "n/a":
        return "[grey50]Q?[/grey50]"
    q = str(q).upper()
    palette = {
        "Q1": "bright_green",
        "Q2": "green",
        "Q3": "yellow",
        "Q4": "red",
    }
    style = palette.get(q, "white")
    return f"[{style}]{q}[/{style}]"


HAS_SCOPUS_API = False
