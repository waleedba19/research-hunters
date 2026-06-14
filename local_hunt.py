"""
local_hunt.py — Way A: simple local-only search pipeline.

No GHA. No Drive. No RQ packages. No PDF download. No quartile check.
Just: topic → 70+ platforms → relevance filter → top N papers → Telegram.

Uses v2-4's proven search core (generate_queries, search_all, filter_by_relevance).
Stops BEFORE the broken PDF download / quartile phase.

This is the local fallback the user can rely on.
"""
import sys
import os
import re
import json
import time
import hashlib
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any

# Force UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")

# Import the proven v2-4 search core
import research_hunter_v2_4 as v2_4


# Default platform set — the 6 fastest & most reliable API-only platforms.
# 6 × 8 queries = 48 calls → ~1-2 min. Tested working in GHA at 3×14=42.
DEFAULT_PLATFORMS = [
    "openalex", "semantic_scholar", "crossref", "arxiv", "pubmed", "core_api",
]

# Slow / flaky / scraper platforms — explicitly excluded for speed
SLOW_PLATFORMS = {
    "libgen", "zlibrary", "google_scholar", "duckduckgo_pdfs",
    "scihub_multi", "shadow_libraries", "academia_edu",
    "scinet", "scibay", "annas_archive_enhanced", "genemedi",
    "perplexica", "oa_mg", "grokipedia", "internet_archive",
    "philpapers", "sciencedirect", "nature_linguistics",
    "elife_sciences", "scienceopen", "doab", "cogprints",
    "europepmc", "dialnet", "digital_commons", "ebsco_dissertations",
    "etd_ohiolink", "ethos", "ssoar", "bioline", "redalyc",
    "scielo", "biorxiv", "medrxiv", "psyarxiv", "socarxiv",
    "plos", "mdpi", "cern", "cern_server", "nasa_ntrs",
    "worldwidescience", "openaire", "science_gov", "jstor_open",
    "paperpanda", "scieelo_bra", "ajol", "bialitic", "oup",
}


def _log(msg: str) -> None:
    print(f"[local_hunt] {msg}", flush=True)


def _normalize_topic(topic: str) -> str:
    """Strip extra whitespace and clip to reasonable length."""
    t = re.sub(r"\s+", " ", str(topic or "")).strip()
    return t[:200] if t else "Research Topic"


def _auto_field_and_study_type(title: str) -> tuple[str, list[str]]:
    """Skip v2-4's auto_detect_field — known to mis-classify some topics.
    Just return 'general' so the search works across all fields.
    """
    return "general", []


def _build_simple_queries(title: str, max_q: int = 8) -> list:
    """Build queries locally without AI — works without ollama/kimi/g4f.
    Returns the title as primary + a few targeted variations.
    """
    q = [_normalize_topic(title)]
    words = [w for w in re.findall(r"[a-zA-Z]{3,}", title)
             if w.lower() not in {"the", "and", "for", "with", "from", "study",
                                  "research", "using", "based", "investigation",
                                  "into", "integrating", "current", "perspectives"}]
    if words:
        # Add: full title in quotes, 3-word variations, key terms
        q.append(f'"{title}"')
        if len(words) >= 3:
            q.append(" ".join(words[:3]))
            q.append(" ".join(words[:4]))
            q.append(" ".join(words[-3:]))
        q.append(" ".join(words[:2]))
        if len(words) >= 4:
            q.append(" ".join(words[1:5]))
    # Dedupe, preserve order, cap
    seen, out = set(), []
    for x in q:
        x = x.strip()
        if x and x.lower() not in seen:
            seen.add(x.lower())
            out.append(x)
    return out[:max_q]


def _dedup_by_doi_or_title(papers: list) -> list:
    """Fast dedup: same DOI, or same normalized title."""
    seen_doi: set = set()
    seen_title: set = set()
    out: list = []
    for p in papers:
        if not isinstance(p, dict):
            continue
        doi = (p.get("doi") or "").strip().lower()
        if doi and doi in seen_doi:
            continue
        if doi:
            seen_doi.add(doi)

        title = (p.get("title") or "").strip().lower()
        title_key = re.sub(r"\s+", " ", title)[:120]
        if title_key and title_key in seen_title:
            continue
        if title_key:
            seen_title.add(title_key)

        out.append(p)
    return out


def _compact_paper(p: dict) -> dict:
    """Trim paper to the fields Telegram will actually use. Smart URL extraction."""
    # Try every common URL field — different platforms use different names
    url = (p.get("url") or p.get("pdf_url") or p.get("link")
           or p.get("doi_url") or p.get("paper_url") or "")
    doi = (p.get("doi") or "").strip()
    if not url and doi:
        url = f"https://doi.org/{doi}"
    if not url and (p.get("title") or "").strip():
        # Last resort: build a Semantic Scholar search URL
        from urllib.parse import quote_plus
        url = f"https://www.semanticscholar.org/search?q={quote_plus(p['title'])}"

    return {
        "title":       (p.get("title") or "").strip(),
        "authors":     p.get("authors") or p.get("author") or [],
        "year":        p.get("year") or "",
        "journal":     p.get("journal") or p.get("venue") or "",
        "abstract":    (p.get("abstract") or "").strip(),
        "doi":         doi,
        "url":         url,
        "source":      p.get("source") or "",
        "relevance":   round(float(p.get("_relevance", 0.5) or 0.0), 3),
    }


def run_local_hunt(
    topic: str,
    max_papers: int = 15,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    platforms: Optional[List[str]] = None,
    progress_callback: Optional[Callable[[str, str, float], None]] = None,
) -> Dict[str, Any]:
    """
    Run a local search for the given topic across 70+ academic platforms.

    Returns a dict with:
      - success (bool)
      - topic, queries, papers (list of compact dicts)
      - stats: {raw, deduped, relevant, returned}
      - error (str|None) on failure
    """
    def _prog(stage: str, msg: str, pct: float) -> None:
        if progress_callback:
            try:
                progress_callback(stage, msg, pct)
            except Exception:
                pass

    title = _normalize_topic(topic)
    max_papers = max(5, min(int(max_papers or 15), 100))
    platforms = platforms or DEFAULT_PLATFORMS

    result: Dict[str, Any] = {
        "success": False,
        "topic": title,
        "queries": [],
        "papers": [],
        "stats": {"raw": 0, "deduped": 0, "relevant": 0, "returned": 0},
        "error": None,
    }

    try:
        # ── Step 1: Auto-detect context ──────────────────────────────────────
        _prog("starting", f"Topic: {title[:60]}", 0.02)
        field, study_types = _auto_field_and_study_type(title)
        try:
            country_context = v2_4.detect_country_context(title, []) or []
        except Exception:
            country_context = []
        _log(f"field={field} study_types={study_types} country={country_context}")

        # ── Step 2: Generate queries (locally, no AI required) ──────────────
        _prog("generating_queries", "Generating search queries...", 0.05)
        try:
            ai_queries = v2_4.generate_queries(
                title, field, study_types, [], year_from, [], country_context
            ) or []
        except Exception as e:
            _log(f"v2-4 generate_queries unavailable: {e}")
            ai_queries = []
        # Always include local queries as a fallback (works without AI service)
        local_queries = _build_simple_queries(title, max_q=8)
        # Combine: AI queries first (more diverse), then local fallback
        result["queries"] = (ai_queries[:6] + local_queries)[:10]
        _prog("generating_queries", f"Generated {len(result['queries'])} queries", 0.10)
        for i, q in enumerate(result["queries"], 1):
            _log(f"  Q{i:2d}. {q}")

        # ── Step 3: Resolve platforms to actual functions ────────────────────
        all_plats = list(getattr(v2_4, "PLATFORM_FNS", {}).keys())
        if not all_plats:
            return {**result, "error": "v2-4 PLATFORM_FNS is empty — cannot search"}
        if "all" in platforms or "ALL" in platforms:
            selected = all_plats
        else:
            selected = [p for p in platforms if p in all_plats] or all_plats
        # Filter out slow / scraper platforms
        selected = [p for p in selected if p not in SLOW_PLATFORMS]
        # Cap to 6 platforms for speed (6×10=60 calls, ~1-2 min)
        if len(selected) > 6:
            _log(f"Limiting to 6 of {len(selected)} fast platforms")
            selected = selected[:6]
        _log(f"Final platforms ({len(selected)}): {selected}")
        _prog("searching",
              f"Searching {len(selected)} fast API platforms...", 0.15)

        # ── Step 4: Search all platforms ─────────────────────────────────────
        try:
            raw = v2_4.search_all(
                result["queries"], selected,
                year_from=year_from, year_to=year_to,
                field=field, country_context=country_context,
            ) or []
        except Exception as e:
            _log(f"search_all failed: {e}")
            return {**result, "error": f"search_all crashed: {e}"}
        result["stats"]["raw"] = len(raw)
        _prog("searching", f"Raw results: {len(raw)} papers found", 0.30)
        _log(f"raw papers: {len(raw)}")

        if not raw:
            return {**result, "error": "No papers found — try a different topic"}

        # ── Step 5: Deduplicate ──────────────────────────────────────────────
        _prog("deduplicating", "Deduplicating results...", 0.35)
        deduped = _dedup_by_doi_or_title(raw)
        result["stats"]["deduped"] = len(deduped)
        _prog("deduplicating", f"After dedup: {len(deduped)} papers", 0.40)

        # ── Step 6: Filter by relevance ──────────────────────────────────────
        _prog("deduplicating", "Filtering by relevance...", 0.45)
        try:
            relevant, removed = v2_4.filter_by_relevance(
                deduped, title, field, threshold=0.12
            )
        except Exception as e:
            _log(f"filter_by_relevance failed: {e}, keeping all deduped")
            relevant, removed = deduped, 0
        result["stats"]["relevant"] = len(relevant)
        if removed:
            _prog("deduplicating",
                  f"Relevance filter removed {removed} unrelated papers", 0.50)

        if not relevant:
            return {**result, "error": "No relevant papers after filtering"}

        # ── Step 7: Cap to max_papers ────────────────────────────────────────
        kept = relevant[:max_papers]
        result["stats"]["returned"] = len(kept)
        result["papers"] = [_compact_paper(p) for p in kept]
        _prog("complete",
              f"Found {len(relevant)} relevant, returning top {len(kept)}",
              0.55)
        _log(f"returning {len(kept)} papers")

        result["success"] = True
        return result

    except Exception as e:
        _log(f"run_local_hunt crashed: {e!r}")
        result["error"] = f"{type(e).__name__}: {e}"
        return result


def format_for_telegram(result: Dict[str, Any], topic: str = "") -> str:
    """Format the local hunt result as a Telegram message (Markdown).
    Splits into multiple messages if too long (Telegram limit = 4096 chars).
    """
    if not result.get("success"):
        err = result.get("error", "Unknown error")
        return f"⚠️ *Hunt failed*\n\n`{err[:500]}`\n\nTry a different topic."

    topic = topic or result.get("topic", "Research")
    papers = result.get("papers", [])
    stats = result.get("stats", {})
    queries = result.get("queries", [])

    header = (
        f"📚 *{topic[:80]}*\n\n"
        f"📊 *Stats:* raw={stats.get('raw', 0)} → "
        f"dedup={stats.get('deduped', 0)} → "
        f"relevant={stats.get('relevant', 0)} → "
        f"returned={stats.get('returned', 0)}\n\n"
        f"🔍 *Queries used ({len(queries)}):*\n"
    )
    q_lines = "\n".join(f"  {i+1}. {q[:80]}" for i, q in enumerate(queries[:8]))
    if len(queries) > 8:
        q_lines += f"\n  ... +{len(queries) - 8} more"

    chunks: list = [header + q_lines + "\n\n📄 *Top Papers:*\n"]

    for i, p in enumerate(papers, 1):
        title = (p.get("title") or "Untitled").replace("*", "").replace("`", "'")[:160]
        authors = p.get("authors") or []
        if isinstance(authors, str):
            authors = [authors]
        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += f" et al."
        year = p.get("year") or "n.d."
        journal = p.get("journal") or p.get("source") or ""
        doi = p.get("doi") or ""
        url = p.get("url") or (f"https://doi.org/{doi}" if doi else "")
        relevance = p.get("relevance", 0)

        block = (
            f"\n*{i}. {title}*\n"
            f"   👥 {author_str or 'Unknown'} ({year})\n"
        )
        if journal:
            block += f"   📖 _{journal[:80]}_\n"
        if url:
            block += f"   🔗 {url[:100]}\n"
        block += f"   ⭐ relevance={relevance}\n"

        # If appending this block would overflow, start a new chunk
        if len(chunks[-1]) + len(block) > 3500:
            chunks.append("")
        chunks[-1] += block

    if not chunks[-1].strip():
        chunks.pop()

    return chunks  # list of strings — caller sends each as separate message


# ── Quick CLI test ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("topic", help="Research topic")
    p.add_argument("--max", type=int, default=10)
    p.add_argument("--year-from", type=int, default=None)
    p.add_argument("--year-to", type=int, default=None)
    args = p.parse_args()

    print(f"Searching for: {args.topic}")
    r = run_local_hunt(args.topic, max_papers=args.max,
                        year_from=args.year_from, year_to=args.year_to)
    print(f"\nResult: success={r['success']}")
    print(f"Stats: {r['stats']}")
    print(f"Queries: {len(r['queries'])}")
    print(f"Papers: {len(r['papers'])}")
    if r['papers']:
        print(f"\nFirst paper: {r['papers'][0]['title'][:80]}")
        print(f"  URL: {r['papers'][0]['url']}")
    if r['error']:
        print(f"\nError: {r['error']}")
