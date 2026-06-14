"""search_cache.py — STUB for v2-4 import.

The real search_cache.py is a private module of the user's
"v6 SUPER LOADED GOD MODE" research hunter. It persists search
state to disk so the same paper is never downloaded twice across runs.

This stub provides an in-memory no-op cache with the SAME public
interface as the real one, so v2-4's main loop never crashes on
cache.mark_downloaded(), cache.deduplicate(), etc.

Methods implemented (all no-op safe):
    SearchCache(out_folder)              — constructor
    cache.mark_downloaded(paper, name)   — record a downloaded paper
    cache.mark_found(paper)              — record a found paper
    cache.stats()                        — returns summary dict
    cache.queries_used()                 — returns set of queries done
    cache.add_queries(queries)           — add queries to history
    cache.deduplicate(papers)            — drop exact-duplicate dicts
    cache.filter_new(papers)             — drop papers already in cache
    cache.record_run(n, dl, skp)         — log this run's stats
    cache.save()                         — flush to disk (no-op in stub)
"""
import logging
import os
from pathlib import Path

log = logging.getLogger("search_cache_stub")

__all__ = ["SearchCache"]


class SearchCache:
    """In-memory no-op cache. Drop-in replacement for the real one.

    The real SearchCache uses an SQLite DB at out_folder/.search_cache.sqlite
    plus a JSON manifest. This stub keeps everything in two sets in RAM.
    """

    def __init__(self, out_folder):
        self.out_folder = Path(out_folder) if out_folder else Path(".")
        self._seen_titles: set[str] = set()
        self._seen_dois:    set[str] = set()
        self._seen_urls:    set[str] = set()
        self._queries:      set[str] = set()
        self._found_count:  int = 0
        self._downloaded_count: int = 0
        self._run_count:    int = 0
        log.warning(
            "search_cache.SearchCache: STUB mode — cache is in-memory only. "
            "Restarting the bot will lose dedup history. Replace with the "
            "real search_cache.py for persistent caching."
        )

    def _key(self, paper):
        """Return a dedup key for a paper dict."""
        if not isinstance(paper, dict):
            return None
        doi = (paper.get("doi") or paper.get("DOI") or "").strip().lower()
        if doi:
            return f"doi:{doi}"
        url = (paper.get("url") or paper.get("link") or paper.get("source_url") or "").strip()
        if url:
            return f"url:{url}"
        title = (paper.get("title") or "").strip().lower()
        if title:
            return f"title:{title}"
        return None

    def mark_downloaded(self, paper, filename=""):
        k = self._key(paper)
        if k:
            self._seen_titles.add(k)
            self._downloaded_count += 1

    def mark_found(self, paper):
        k = self._key(paper)
        if k:
            self._seen_titles.add(k)
            self._found_count += 1

    def stats(self):
        return {
            "mode": "stub",
            "out_folder": str(self.out_folder),
            "seen_unique": len(self._seen_titles),
            "queries_logged": len(self._queries),
            "found_total": self._found_count,
            "downloaded_total": self._downloaded_count,
            "runs_total": self._run_count,
        }

    def queries_used(self):
        return set(self._queries)

    def add_queries(self, queries):
        if not queries:
            return
        for q in queries:
            if isinstance(q, str) and q.strip():
                self._queries.add(q.strip())

    def deduplicate(self, papers):
        if not papers:
            return []
        seen = set()
        out = []
        for p in papers:
            k = self._key(p)
            if k is None:
                out.append(p)
                continue
            if k in seen:
                continue
            seen.add(k)
            out.append(p)
        return out

    def filter_new(self, papers):
        if not papers:
            return [], 0
        new = []
        skipped = 0
        for p in papers:
            k = self._key(p)
            if k and k in self._seen_titles:
                skipped += 1
                continue
            if k:
                self._seen_titles.add(k)
            new.append(p)
        return new, skipped

    def record_run(self, n_found=0, n_downloaded=0, n_skipped=0):
        self._run_count += 1
        log.info(
            "cache.record_run #%d: found=%d downloaded=%d skipped=%d",
            self._run_count, n_found, n_downloaded, n_skipped,
        )

    def save(self):
        log.debug("cache.save (no-op in stub): %d entries", len(self._seen_titles))
        return True
