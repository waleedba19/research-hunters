"""search_cache.py — Persistent search cache using JSON on disk.

Persists dedup state to a JSON file so the same paper is never
downloaded twice across runs.
"""
import os, json, logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

log = logging.getLogger("search_cache")

__all__ = ["SearchCache"]


class SearchCache:
    """Persistent JSON-based cache. Drop-in replacement for the original stub.

    Stores seen papers and queries in a JSON file at out_folder/.search_cache.json.
    """

    CACHE_FILE = ".search_cache.json"

    def __init__(self, out_folder: Optional[str] = None):
        self.out_folder = Path(out_folder) if out_folder else Path(".")
        self.out_folder.mkdir(parents=True, exist_ok=True)
        self._cache_path = self.out_folder / self.CACHE_FILE

        self._seen_keys: Set[str] = set()
        self._queries: Set[str] = set()
        self._found_count: int = 0
        self._downloaded_count: int = 0
        self._run_count: int = 0

        self._load()

    def _load(self):
        if self._cache_path.exists():
            try:
                data = json.loads(self._cache_path.read_text(encoding="utf-8"))
                self._seen_keys = set(data.get("seen_keys", []))
                self._queries = set(data.get("queries", []))
                self._found_count = data.get("found_count", 0)
                self._downloaded_count = data.get("downloaded_count", 0)
                self._run_count = data.get("run_count", 0)
                log.info("cache loaded from %s (%d keys)", self._cache_path, len(self._seen_keys))
            except Exception as e:
                log.warning("cache load failed: %s", e)

    def save(self):
        try:
            data = {
                "seen_keys": list(self._seen_keys),
                "queries": list(self._queries),
                "found_count": self._found_count,
                "downloaded_count": self._downloaded_count,
                "run_count": self._run_count,
            }
            self._cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            log.debug("cache saved to %s (%d keys)", self._cache_path, len(self._seen_keys))
            return True
        except Exception as e:
            log.warning("cache save failed: %s", e)
            return False

    def _key(self, paper: dict) -> Optional[str]:
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

    def mark_downloaded(self, paper: dict, filename: str = ""):
        k = self._key(paper)
        if k:
            self._seen_keys.add(k)
            self._downloaded_count += 1
            self.save()

    def mark_found(self, paper: dict):
        k = self._key(paper)
        if k:
            self._seen_keys.add(k)
            self._found_count += 1
            self.save()

    def stats(self) -> dict:
        return {
            "mode": "persistent",
            "cache_file": str(self._cache_path),
            "seen_unique": len(self._seen_keys),
            "queries_logged": len(self._queries),
            "total_found": self._found_count,
            "total_downloaded": self._downloaded_count,
            "queries_used": len(self._queries),
            "runs_total": self._run_count,
        }

    def queries_used(self) -> Set[str]:
        return set(self._queries)

    def add_queries(self, queries):
        if not queries:
            return
        changed = False
        for q in queries:
            if isinstance(q, str) and q.strip():
                if q.strip() not in self._queries:
                    self._queries.add(q.strip())
                    changed = True
        if changed:
            self.save()

    def deduplicate(self, papers: List[dict]) -> List[dict]:
        if not papers:
            return []
        seen: Set[str] = set()
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

    def filter_new(self, papers: List[dict]):
        if not papers:
            return [], 0
        new = []
        skipped = 0
        for p in papers:
            k = self._key(p)
            if k and k in self._seen_keys:
                skipped += 1
                continue
            if k:
                self._seen_keys.add(k)
            new.append(p)
        if new:
            self.save()
        return new, skipped

    def record_run(self, n_found: int = 0, n_downloaded: int = 0, n_skipped: int = 0):
        self._run_count += 1
        self.save()
        log.info("cache.record_run #%d: found=%d downloaded=%d skipped=%d",
                 self._run_count, n_found, n_downloaded, n_skipped)
