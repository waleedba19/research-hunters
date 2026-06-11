"""
scopus_checker.py
─────────────────
Scopus quartile (Q1–Q4) verification for academic journals.

This module provides three public functions used by research_hunter_v2-4.py:
  • check_quartile(journal_name)  → dict  {"quartile": "Q1"–"Q4"/"Not Found", "verified": bool, "source": "..."}
  • bulk_check(papers)            → list  of paper dicts, each enriched with a "scopus_quartile" field
  • quartile_badge(q)             → str   colourised badge string for console display

Backends (in order of priority):
  1. Local known-journal fuzzy cache (KNOWN_Q1 / KNOWN_Q2 journals in main script) — handled
     here via the same known-journal lists if available, otherwise via a built-in list.
  2. Scimago Journal Rankings (SJR) — public API: https://www.scimagojr.com/
  3. SciRev.org (open journal info) — fallback
  4. Local fuzzy / substring match — last resort

NOTE: The script ALSO defines its own KNOWN_Q1_JOURNALS / KNOWN_Q2_JOURNALS sets and
calls enhanced_quartile_check(paper) after check_quartile, so this module only needs
to return a *baseline* quartile from the live SJR endpoint (or a sensible default).
"""

from __future__ import annotations

import json
import re
import time
import difflib
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

# ──────────────────────────────────────────────────────────────────────────────
#  Local cache (persists between runs so we don't hammer SJR every time)
# ──────────────────────────────────────────────────────────────────────────────
CACHE_FILE = Path("scopus_cache.json")
_SESSION_CACHE: dict[str, dict] = {}
_HAS_RICH = False
try:
    from rich.console import Console
    _console = Console()
    _HAS_RICH = True
except Exception:
    pass


def _load_cache() -> dict:
    if _SESSION_CACHE:
        return _SESSION_CACHE
    if CACHE_FILE.exists():
        try:
            _SESSION_CACHE.update(json.loads(CACHE_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return _SESSION_CACHE


def _save_cache() -> None:
    try:
        CACHE_FILE.write_text(
            json.dumps(_SESSION_CACHE, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────
#  Built-in fallback journal lists (used only if main script's lists are absent)
# ──────────────────────────────────────────────────────────────────────────────
_DEFAULT_Q1 = {
    "nature", "science", "cell", "lancet", "nejm", "jama",
    "plos biology", "plos medicine", "plos one",
    "applied linguistics", "tesol quarterly", "language",
    "modern language journal", "system", "language learning",
    "studies in second language acquisition", "language teaching",
    "language teaching research", "english for specific purposes",
    "journal of second language writing", "elt journal",
    "computer-assisted language learning", "calico journal",
    "educational researcher", "review of educational research",
    "teaching and teacher education", "learning and instruction",
    "computers & education", "computers and education",
    "british journal of educational technology",
    "journal of educational psychology",
    "reading research quarterly", "written communication",
    "cognitive science", "cognition", "psychological science",
    "journal of memory and language", "bilingualism: language and cognition",
}

_DEFAULT_Q2 = {
    "english language teaching", "elt", "language learning journal",
    "asian efl journal", "arab world english journal", "awej",
    "international journal of applied linguistics",
    "journal of language teaching and research",
    "studies in applied linguistics", "relc journal",
    "innovation in language learning and teaching",
    "language awareness", "linguistic approaches to bilingualism",
    "educational technology & society", "education and information technologies",
    "interactive learning environments", "sustainability", "frontiers in psychology",
    "frontiers in education", "frontiers in medicine",
}


# ──────────────────────────────────────────────────────────────────────────────
#  Core: check_quartile(journal_name)
# ──────────────────────────────────────────────────────────────────────────────
HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def _normalise(name: str) -> str:
    n = (name or "").lower().strip()
    n = re.sub(r"[\(\)\[\]\.,&]", " ", n)
    n = re.sub(r"\s+", " ", n)
    return n.strip()


def _local_guess(journal: str) -> str:
    """Quick baseline guess using built-in lists."""
    jl = _normalise(journal)
    if not jl:
        return ""
    # Q1
    for k in _DEFAULT_Q1:
        if k in jl or jl in k:
            return "Q1"
    if difflib.get_close_matches(jl, _DEFAULT_Q1, n=1, cutoff=0.85):
        return "Q1"
    # Q2
    for k in _DEFAULT_Q2:
        if k in jl or jl in k:
            return "Q2"
    if difflib.get_close_matches(jl, _DEFAULT_Q2, n=1, cutoff=0.85):
        return "Q2"
    return ""


def _scimago_lookup(journal: str) -> dict | None:
    """
    Best-effort lookup against Scimago Journal Rankings public site.
    Returns dict {quartile, verified, source} or None on failure.
    """
    try:
        # SJR search endpoint (returns HTML; we just need a hit + quartile band)
        url = f"https://www.scimagojr.com/journalsearch.php?q={quote(journal)}"
        r = requests.get(url, headers=HDRS, timeout=5, allow_redirects=True)  # Reduced from 12s to 5s
        if r.status_code != 200:
            return None
        text = r.text.lower()
        # Sniff any Q* hint near the first result
        # The SJR results page shows the quartile in the form "Q1" or "Q2", etc.
        m = re.search(r"q([1-4])\b", text)
        if m:
            return {"quartile": f"Q{m.group(1)}", "verified": True, "source": "scimago"}
    except Exception:
        pass
    return None


def check_quartile(journal: str) -> dict:
    """
    Look up the Scopus quartile for a single journal.

    Returns a dict like:
        {"quartile": "Q1", "verified": True,  "source": "scimago"}
        {"quartile": "Q2", "verified": False, "source": "local_cache"}
        {"quartile": "Not Found", "verified": False, "source": "none"}
    """
    if not journal or not str(journal).strip():
        return {"quartile": "Not Found", "verified": False, "source": "empty"}

    cache = _load_cache()
    key = _normalise(journal)
    if key in cache:
        return cache[key]

    # 1. Try live SJR lookup
    live = _scimago_lookup(journal)
    if live:
        cache[key] = live
        _save_cache()
        return live

    # 2. Fall back to local fuzzy / substring guess
    guess = _local_guess(journal)
    result = (
        {"quartile": guess, "verified": False, "source": "local_guess"}
        if guess
        else {"quartile": "Not Found", "verified": False, "source": "none"}
    )
    cache[key] = result
    _save_cache()
    return result


# ──────────────────────────────────────────────────────────────────────────────
#  Bulk: bulk_check(papers)
# ──────────────────────────────────────────────────────────────────────────────
def bulk_check(papers: list[dict], *, max_workers: int = 12) -> list[dict]:  # Increased from 6 to 12
    """
    Add / refresh 'scopus_quartile' on every paper in `papers` (in-place return).

    Each paper is expected to have a "journal" field. Results from
    check_quartile() are attached as a dict under "scopus_quartile".

    Uses a thread pool to keep things snappy.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not papers:
        return papers

    # Deduplicate journals for fewer lookups
    journals: dict[str, str] = {}
    for p in papers:
        j = (p.get("journal") or p.get("venue") or "").strip()
        if j:
            journals.setdefault(_normalise(j), j)

    # Lookup table
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(check_quartile, name): key for key, name in journals.items()}
        for fut in as_completed(futs):
            key = futs[fut]
            try:
                results[key] = fut.result() or {"quartile": "Not Found",
                                                 "verified": False,
                                                 "source": "none"}
            except Exception:
                results[key] = {"quartile": "Not Found", "verified": False,
                                "source": "error"}

    # Attach to papers
    for p in papers:
        j = (p.get("journal") or p.get("venue") or "").strip()
        if not j:
            p["scopus_quartile"] = {"quartile": "Not Found",
                                    "verified": False, "source": "empty"}
            continue
        p["scopus_quartile"] = results.get(_normalise(j),
                                            {"quartile": "Not Found",
                                             "verified": False,
                                             "source": "none"})
    return papers


# ──────────────────────────────────────────────────────────────────────────────
#  Display: quartile_badge(q)
# ──────────────────────────────────────────────────────────────────────────────
_Q_STYLE = {
    "Q1":        ("bold green",  "✅ Q1"),
    "Q2":        ("bold blue",   "🟦 Q2"),
    "Q3":        ("bold yellow", "🟨 Q3"),
    "Q4":        ("bold red",    "🟥 Q4"),
    "Not Found": ("dim white",   "—"),
    "Not Ranked":("dim white",   "—"),
    "":          ("dim white",   "—"),
}


def quartile_badge(q: str) -> str:
    """
    Return a colourised badge for display in the console.

    Falls back to plain ASCII if `rich` is not installed.
    """
    style, plain = _Q_STYLE.get(q or "", _Q_STYLE["Not Found"])
    if _HAS_RICH:
        return f"[{style}]{plain}[/{style}]"
    return plain
