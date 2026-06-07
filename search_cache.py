"""
search_cache.py
---------------
Persistent cache for the research-hunter search workflow.

A single `SearchCache(study_dir)` instance lives for the whole run. It tracks:
  * queries the user has already used        (so we don't repeat them)
  * papers that have been "found"             (deduplication)
  * papers that have been "downloaded"        (resume + red-list)
  * high-level run statistics                 (papers new / downloaded / skipped)

State is persisted to `<study_dir>/search_cache.json` and auto-loaded on
instantiation. All public methods are safe to call before `save()`.
"""

from __future__ import annotations

import json
import time
import hashlib
from pathlib import Path
from typing import Any


def _paper_id(p: dict) -> str:
    """Stable identifier for a paper: prefer DOI, else first 80 chars of title."""
    doi = (p.get("doi") or "").strip().lower()
    if doi:
        return "doi:" + doi
    title = (p.get("title") or "").strip().lower()[:80]
    return "t:" + hashlib.md5(title.encode("utf-8", "ignore")).hexdigest()[:12]


class SearchCache:
    """Persistent JSON-backed cache for one study."""

    FILENAME = "search_cache.json"

    def __init__(self, study_dir):
        self.path = Path(study_dir) / self.FILENAME
        self.study_dir = Path(study_dir)
        self._state: dict = {
            "created":            time.strftime("%Y-%m-%dT%H:%M:%S"),
            "last_saved":         "",
            "queries_used":       [],
            "papers_found":       {},   # id -> {title, journal, year, doi, ...}
            "papers_downloaded":  {},   # id -> filename
            "runs":               [],   # list of {ts, new, downloaded, skipped}
            "queries_exhausted":  False,
        }
        self._load()

    # I/O
    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._state.update(data)
        except Exception:
            try:
                self.path.rename(self.path.with_suffix(".corrupt.json"))
            except Exception:
                pass

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._state["last_saved"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self._state, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
            tmp.replace(self.path)
        except Exception:
            pass

    # Queries
    def queries_used(self):
        """Return the list of search queries that have already been used."""
        return list(self._state.get("queries_used", []))

    def add_queries(self, queries):
        """Add new queries to the 'used' list (de-duplicated, order preserved)."""
        existing = set(q.strip().lower() for q in self._state.get("queries_used", []))
        for q in queries or []:
            if not q:
                continue
            ql = q.strip().lower()
            if ql not in existing:
                self._state.setdefault("queries_used", []).append(q.strip())
                existing.add(ql)

    def mark_queries_exhausted(self):
        """Signal that the query-generator has nothing new to produce."""
        self._state["queries_exhausted"] = True

    def queries_exhausted(self):
        return bool(self._state.get("queries_exhausted", False))

    # Papers
    def mark_found(self, paper):
        """Record that we have 'seen' this paper in some search result."""
        pid = _paper_id(paper)
        self._state.setdefault("papers_found", {})[pid] = {
            "title":      (paper.get("title") or "")[:200],
            "journal":    paper.get("journal", ""),
            "year":       str(paper.get("year", ""))[:4],
            "doi":        paper.get("doi") or "",
            "source":     paper.get("source", ""),
            "first_seen": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    def mark_downloaded(self, paper, filename):
        """Record that the PDF for this paper has been successfully downloaded."""
        pid = _paper_id(paper)
        self._state.setdefault("papers_downloaded", {})[pid] = {
            "filename":      filename,
            "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        # also mark as found, just in case
        self.mark_found(paper)

    def is_downloaded(self, paper):
        return _paper_id(paper) in self._state.get("papers_downloaded", {})

    def is_known(self, paper):
        return _paper_id(paper) in self._state.get("papers_found", {})

    # Bulk operations
    def deduplicate(self, papers):
        """
        Deduplicate a batch of papers against each other AND the cache.
        First occurrence wins; later copies are dropped.
        """
        seen_ids = set()
        seen_titles = set()
        out = []
        for p in papers or []:
            pid = _paper_id(p)
            title = (p.get("title") or "").strip().lower()[:80]
            if pid in seen_ids:
                continue
            if title and title in seen_titles:
                continue
            seen_ids.add(pid)
            if title:
                seen_titles.add(title)
            out.append(p)
        return out

    def filter_new(self, papers):
        """
        Split a batch into (new_papers, skipped_count).
        'New' = not previously recorded as found AND not already downloaded.
        """
        found = set(self._state.get("papers_found", {}).keys())
        downloaded = set(self._state.get("papers_downloaded", {}).keys())
        known = found | downloaded

        new_papers = []
        skipped = 0
        for p in papers or []:
            pid = _paper_id(p)
            if pid in known:
                skipped += 1
                continue
            new_papers.append(p)
        return new_papers, skipped

    # Stats / run recording
    def stats(self):
        return {
            "total_found":      len(self._state.get("papers_found", {})),
            "total_downloaded": len(self._state.get("papers_downloaded", {})),
            "queries_used":     len(self._state.get("queries_used", [])),
        }

    def record_run(self, new, downloaded, skipped=0):
        self._state.setdefault("runs", []).append({
            "ts":         time.strftime("%Y-%m-%dT%H:%M:%S"),
            "new":        int(new),
            "downloaded": int(downloaded),
            "skipped":    int(skipped),
        })
        # Trim history to last 200 runs to keep file small
        if len(self._state["runs"]) > 200:
            self._state["runs"] = self._state["runs"][-200:]

    def reset(self):
        """Wipe the cache (use only when you really want a fresh start)."""
        self._state = {
            "created":            time.strftime("%Y-%m-%dT%H:%M:%S"),
            "last_saved":         "",
            "queries_used":       [],
            "papers_found":       {},
            "papers_downloaded":  {},
            "runs":               [],
            "queries_exhausted":  False,
        }
        self.save()

    def __repr__(self):
        s = self.stats()
        return ("<SearchCache " + repr(self.path.name)
                + " found=" + str(s["total_found"])
                + " downloaded=" + str(s["total_downloaded"])
                + " queries=" + str(s["queries_used"]) + ">")
