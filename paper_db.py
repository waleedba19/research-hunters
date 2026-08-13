"""paper_db.py — SQLite-backed paper store, the single source of truth.

Replaces the JSON-based SearchCache for large (10k–100k paper) runs that
span many chunks / days. SQLite (WAL mode) gives us:

  - incremental, crash-safe persistence (every batch is a transaction, so a
    mid-chunk crash never loses found papers),
  - indexed O(log n) dedup instead of an in-memory set that grows with the
    whole corpus,
  - no giant load→merge→write of results.json at the end (we generate that
    file from the DB only when a report is needed), and
  - concurrent read access (report generation) while a chunk is still writing.

Drop-in compatible with search_cache.SearchCache for the surface used by the
pipeline: mark_found, mark_downloaded, filter_new, deduplicate, add_queries,
queries_used, record_run, stats, save. Extra methods: upsert_paper,
bulk_upsert, get_all_papers, count, export_results_json, vacuum.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List, Optional, Set, Tuple

from logger import get_logger

log = get_logger(__name__)

# Columns mirrored into results.json by export_results_json. Keep in sync
# with the schema below and with what the report generators expect.
_PAPER_COLS = (
    "id", "key", "title", "authors", "year", "journal", "publisher", "doi",
    "url", "source", "quartile", "abstract", "introduction", "methodology",
    "results", "discussion", "fulltext_source", "has_fulltext", "pdf_path",
    "downloaded", "keywords", "scopus_quartile", "gs_citations", "oa",
    "funding", "geo", "doctype", "methodology_field", "relevance", "folder",
    "doctype_real", "geo_tier", "raw_json", "updated_at",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    key             TEXT UNIQUE NOT NULL,
    title           TEXT,
    authors         TEXT,
    year            INTEGER,
    journal         TEXT,
    publisher       TEXT,
    doi             TEXT,
    url             TEXT,
    source          TEXT,
    quartile        TEXT,
    abstract        TEXT,
    introduction    TEXT,
    methodology     TEXT,
    results         TEXT,
    discussion      TEXT,
    fulltext_source TEXT,
    has_fulltext    INTEGER DEFAULT 0,
    pdf_path        TEXT,
    downloaded      INTEGER DEFAULT 0,
    keywords        TEXT,
    scopus_quartile TEXT,
    gs_citations    INTEGER DEFAULT 0,
    oa              INTEGER DEFAULT 0,
    funding         TEXT,
    geo             TEXT,
    doctype         TEXT,
    methodology_field TEXT,
    relevance       TEXT,
    folder          TEXT,
    doctype_real    TEXT,
    geo_tier        TEXT,
    raw_json        TEXT,
    updated_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_papers_doi  ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year);
CREATE INDEX IF NOT EXISTS idx_papers_source ON papers(source);

CREATE TABLE IF NOT EXISTS queries (
    query    TEXT NOT NULL,
    platform TEXT,
    run_at   TEXT,
    PRIMARY KEY (query, platform)
);

CREATE TABLE IF NOT EXISTS runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk            INTEGER,
    new_papers       INTEGER,
    downloaded       INTEGER,
    total            INTEGER,
    queries_exhausted INTEGER DEFAULT 0,
    limit_reached    INTEGER DEFAULT 0,
    download_mode    TEXT,
    created_at       TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _paper_key(paper: dict) -> Optional[str]:
    """Deterministic dedup key: doi > url > normalized-title."""
    if not isinstance(paper, dict):
        return None
    doi = (paper.get("doi") or paper.get("DOI") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    url = (paper.get("url") or paper.get("link") or
           paper.get("source_url") or "").strip()
    if url:
        return f"url:{url}"
    title = (paper.get("title") or "").strip().lower()
    if title:
        return f"title:{title}"
    return None


def _coerce_authors(paper: dict) -> str:
    a = paper.get("authors")
    if isinstance(a, list):
        return ", ".join(str(x) for x in a)
    return str(a or "")


def _coerce_quartile(paper: dict) -> Tuple[str, str]:
    """Return (quartile_str, scopus_quartile_json)."""
    q = paper.get("scopus_quartile")
    if isinstance(q, dict):
        return (q.get("quartile", "") or "", json.dumps(q, ensure_ascii=False))
    return (str(q or ""), "")


class PaperDB:
    """SQLite paper store. Thread-safe per-connection (one connection per
    thread); the main thread's connection is reused across calls."""

    def __init__(self, out_folder: Optional[str] = None,
                 db_name: str = "papers.db"):
        self.out_folder = Path(out_folder) if out_folder else Path(".")
        self.out_folder.mkdir(parents=True, exist_ok=True)
        self._db_path = self.out_folder / db_name
        self._lock = threading.Lock()
        self._counts = {"found": 0, "downloaded": 0, "runs": 0}
        self._loaded_counts = False
        self._conn = self._open()
        self._bootstrap()
        log.info("PaperDB ready at %s", self._db_path)

    # ── connection / schema ────────────────────────────────────────────
    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=30.0,
                                isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # WAL = readers never block the writer; durable across crashes.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA cache_size=-64000")  # ~64MB cache
        return conn

    def _bootstrap(self):
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._load_counts()

    def _load_counts(self):
        if self._loaded_counts:
            return
        try:
            c = self._conn.execute(
                "SELECT COUNT(*) AS n, "
                "COALESCE(SUM(downloaded),0) AS d FROM papers").fetchone()
            r = self._conn.execute("SELECT COUNT(*) AS r FROM runs").fetchone()
            self._counts = {"found": c["n"], "downloaded": c["d"],
                            "runs": r["r"]}
        except Exception as e:
            log.warning("PaperDB count load failed: %s", e)
        self._loaded_counts = True

    # ── SearchCache-compatible surface ──────────────────────────────────
    def save(self) -> bool:  # no-op (transactions already durable)
        return True

    def mark_found(self, paper: dict):
        self.upsert_paper(paper)

    def mark_downloaded(self, paper: dict, filename: str = ""):
        with self._lock:
            k = _paper_key(paper)
            if not k:
                return
            self._conn.execute(
                "BEGIN IMMEDIATE")
            try:
                self._conn.execute(
                    "UPDATE papers SET downloaded=1, "
                    "pdf_path=COALESCE(?, pdf_path) WHERE key=?",
                    (filename or paper.get("file_path"), k))
                # Only count if it wasn't already downloaded.
                row = self._conn.execute(
                    "SELECT downloaded FROM papers WHERE key=?", (k,)).fetchone()
                if row and row["downloaded"]:
                    self._counts["downloaded"] = self._counts.get("downloaded", 0) + 1
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def queries_used(self) -> Set[str]:
        with self._lock:
            rows = self._conn.execute("SELECT DISTINCT query FROM queries").fetchall()
        return {r["query"] for r in rows}

    def add_queries(self, queries):
        if not queries:
            return
        rows = []
        ts = _now()
        for q in queries:
            if isinstance(q, str) and q.strip():
                # platform='' (not NULL) so the (query, platform) PRIMARY KEY
                # dedups identical queries — SQLite treats NULL != NULL.
                rows.append((q.strip(), "", ts))
        if not rows:
            return
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO queries(query, platform, run_at) "
                    "VALUES (?,?,?)", rows)
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def record_run(self, n_found: int = 0, n_downloaded: int = 0,
                   n_skipped: int = 0, **extra):
        with self._lock:
            self._conn.execute(
                "INSERT INTO runs(chunk, new_papers, downloaded, total, "
                "queries_exhausted, limit_reached, download_mode, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (extra.get("chunk"), n_found, n_downloaded,
                 self._counts["found"], int(extra.get("queries_exhausted", False)),
                 int(extra.get("limit_reached", False)),
                 extra.get("download_mode", "off"), _now()))
            self._counts["runs"] += 1

    def stats(self) -> dict:
        self._load_counts()
        with self._lock:
            rq = self._conn.execute("SELECT COUNT(*) AS n FROM queries").fetchone()["n"]
        return {
            "mode": "sqlite",
            "cache_file": str(self._db_path),
            "seen_unique": self._counts["found"],
            "queries_logged": rq,
            "total_found": self._counts["found"],
            "total_downloaded": self._counts["downloaded"],
            "queries_used": rq,
            "runs_total": self._counts["runs"],
        }

    def deduplicate(self, papers: List[dict]) -> List[dict]:
        """In-list dedup only (does not consult the DB). Matches SearchCache."""
        if not papers:
            return []
        seen: Set[str] = set()
        out = []
        for p in papers:
            k = _paper_key(p)
            if k is None:
                out.append(p)
                continue
            if k in seen:
                continue
            seen.add(k)
            out.append(p)
        return out

    def filter_new(self, papers: List[dict]) -> Tuple[List[dict], int]:
        """Return (new_papers, skipped) — inserts new ones into the DB so
        subsequent calls treat them as seen."""
        if not papers:
            return [], 0
        new, skipped = [], 0
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                for p in papers:
                    k = _paper_key(p)
                    if not k:
                        new.append(p)
                        continue
                    exists = self._conn.execute(
                        "SELECT 1 FROM papers WHERE key=?", (k,)).fetchone()
                    if exists:
                        skipped += 1
                        continue
                    self._insert_row(p, k)
                    new.append(p)
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        if new:
            self._counts["found"] += len(new)
        return new, skipped

    # ── extended API ────────────────────────────────────────────────────
    def upsert_paper(self, paper: dict) -> bool:
        """Insert if new, update if existing. Returns True if newly inserted."""
        k = _paper_key(paper)
        if not k:
            return False
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT id FROM papers WHERE key=?", (k,)).fetchone()
                if row:
                    self._update_row(row["id"], paper, k)
                    self._conn.execute("COMMIT")
                    return False
                self._insert_row(paper, k)
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        self._counts["found"] += 1
        return True

    def bulk_upsert(self, papers: Iterable[dict]) -> Tuple[int, int]:
        new_n, dup_n = 0, 0
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                for p in papers:
                    k = _paper_key(p)
                    if not k:
                        continue
                    row = self._conn.execute(
                        "SELECT id FROM papers WHERE key=?", (k,)).fetchone()
                    if row:
                        self._update_row(row["id"], p, k)
                        dup_n += 1
                    else:
                        self._insert_row(p, k)
                        new_n += 1
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        self._counts["found"] += new_n
        return new_n, dup_n

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]

    def get_all_papers(self, limit: Optional[int] = None) -> List[dict]:
        """Return all papers as dicts (mirror of results.json 'papers')."""
        sql = "SELECT * FROM papers ORDER BY id"
        if limit:
            sql += f" LIMIT {int(limit)}"
        with self._lock:
            rows = self._conn.execute(sql).fetchall()
        return [self._row_to_paper(r) for r in rows]

    def iter_papers(self):
        """Generator streaming papers one at a time (low memory for 100k)."""
        with self._lock:
            cur = self._conn.execute("SELECT * FROM papers ORDER BY id")
            while True:
                rows = cur.fetchmany(500)
                if not rows:
                    break
                for r in rows:
                    yield self._row_to_paper(r)

    def export_results_json(self, path, meta: Optional[dict] = None) -> Path:
        """Build results.json FROM the db (backwards compat for report gens).

        Streams via iter_papers so 100k papers don't blow memory.
        """
        out = Path(path)
        papers = []
        for p in self.iter_papers():
            papers.append(p)
        data = dict(meta or {})
        data["papers"] = papers
        data.setdefault("generated_at", _now())
        tmp = out.with_suffix(out.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, out)  # atomic
        log.info("exported %d papers -> %s", len(papers), out)
        return out

    def vacuum(self):
        with self._lock:
            self._conn.execute("VACUUM")

    def close(self):
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass

    # ── internals ───────────────────────────────────────────────────────
    def _insert_row(self, paper: dict, key: str):
        q, sqj = _coerce_quartile(paper)
        self._conn.execute(
            "INSERT INTO papers (key, title, authors, year, journal, publisher, "
            "doi, url, source, quartile, abstract, introduction, methodology, "
            "results, discussion, fulltext_source, has_fulltext, pdf_path, "
            "downloaded, keywords, scopus_quartile, gs_citations, oa, funding, "
            "geo, doctype, methodology_field, relevance, folder, doctype_real, "
            "geo_tier, raw_json, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (key, paper.get("title", ""), _coerce_authors(paper),
             int(paper.get("year") or 0), paper.get("journal", ""),
             paper.get("publisher", ""), paper.get("doi", ""),
             paper.get("url", ""), paper.get("source", ""), q,
             paper.get("abstract", ""), paper.get("introduction", ""),
             paper.get("methodology", ""), paper.get("results", ""),
             paper.get("discussion", ""), paper.get("fulltext_source", ""),
             int(bool(paper.get("has_fulltext"))), paper.get("pdf_path", ""),
             int(bool(paper.get("downloaded"))), paper.get("keywords", ""),
             sqj, int(paper.get("gs_citations") or 0),
             int(bool(paper.get("oa") or paper.get("pdf_url"))),
             paper.get("funding", ""), paper.get("geo", ""),
             paper.get("doctype", ""), paper.get("methodology_field", ""),
             paper.get("relevance", ""), paper.get("folder", ""),
             paper.get("doctype_real", ""), paper.get("geo_tier", ""),
             json.dumps(paper, ensure_ascii=False), _now()))

    def _update_row(self, row_id: int, paper: dict, key: str):
        """Update mutable fields on an existing paper (merge enriched text)."""
        q, sqj = _coerce_quartile(paper)
        self._conn.execute(
            "UPDATE papers SET title=?, authors=?, year=?, journal=?, "
            "publisher=?, doi=?, url=?, source=?, quartile=?, abstract=?, "
            "introduction=COALESCE(NULLIF(?, ''), introduction), "
            "methodology=COALESCE(NULLIF(?, ''), methodology), "
            "results=COALESCE(NULLIF(?, ''), results), "
            "discussion=COALESCE(NULLIF(?, ''), discussion), "
            "fulltext_source=COALESCE(NULLIF(?, ''), fulltext_source), "
            "has_fulltext=MAX(has_fulltext, ?), "
            "downloaded=MAX(downloaded, ?), pdf_path=COALESCE(?, pdf_path), "
            "keywords=COALESCE(NULLIF(?, ''), keywords), "
            "scopus_quartile=COALESCE(NULLIF(?, ''), scopus_quartile), "
            "gs_citations=MAX(gs_citations, ?), oa=MAX(oa, ?), "
            "funding=COALESCE(NULLIF(?, ''), funding), "
            "raw_json=?, updated_at=? WHERE id=?",
            (paper.get("title", ""), _coerce_authors(paper),
             int(paper.get("year") or 0), paper.get("journal", ""),
             paper.get("publisher", ""), paper.get("doi", ""),
             paper.get("url", ""), paper.get("source", ""), q,
             paper.get("abstract", ""), paper.get("introduction", ""),
             paper.get("methodology", ""), paper.get("results", ""),
             paper.get("discussion", ""), paper.get("fulltext_source", ""),
             int(bool(paper.get("has_fulltext"))),
             int(bool(paper.get("downloaded"))), paper.get("pdf_path", ""),
             paper.get("keywords", ""), sqj,
             int(paper.get("gs_citations") or 0),
             int(bool(paper.get("oa") or paper.get("pdf_url"))),
             paper.get("funding", ""),
             json.dumps(paper, ensure_ascii=False), _now(), row_id))

    @staticmethod
    def _row_to_paper(row: sqlite3.Row) -> dict:
        """Reconstruct a paper dict from a DB row (report-facing fields)."""
        raw = row["raw_json"]
        base = {}
        if raw:
            try:
                base = json.loads(raw)
            except Exception:
                base = {}
        # Overlay structured columns (authoritative over the cached raw).
        sqj = row["scopus_quartile"]
        qdict = json.loads(sqj) if sqj else {}
        if not qdict and row["quartile"]:
            qdict = {"quartile": row["quartile"]}
        authors = row["authors"]
        if authors and not isinstance(authors, list):
            authors = [a.strip() for a in authors.split(",") if a.strip()]
        base.update({
            "id": row["id"],
            "title": row["title"] or base.get("title", ""),
            "authors": authors or base.get("authors", []),
            "year": row["year"] or base.get("year", 0),
            "journal": row["journal"] or base.get("journal", ""),
            "publisher": row["publisher"] or base.get("publisher", ""),
            "doi": row["doi"] or base.get("doi", ""),
            "url": row["url"] or base.get("url", ""),
            "source": row["source"] or base.get("source", ""),
            "scopus_quartile": qdict,
            "quartile": row["quartile"] or qdict.get("quartile", ""),
            "abstract": row["abstract"] or base.get("abstract", ""),
            "introduction": row["introduction"] or base.get("introduction", ""),
            "methodology": row["methodology"] or base.get("methodology", ""),
            "results": row["results"] or base.get("results", ""),
            "discussion": row["discussion"] or base.get("discussion", ""),
            "fulltext_source": row["fulltext_source"] or "",
            "has_fulltext": bool(row["has_fulltext"]),
            "pdf_path": row["pdf_path"] or base.get("pdf_path", ""),
            "downloaded": bool(row["downloaded"]),
            "keywords": row["keywords"] or base.get("keywords", ""),
            "gs_citations": row["gs_citations"] or base.get("gs_citations", 0),
            "oa": bool(row["oa"]),
            "funding": row["funding"] or base.get("funding", ""),
            "geo": row["geo"] or base.get("geo", ""),
            "doctype": row["doctype"] or base.get("doctype", ""),
            "folder": row["folder"] or base.get("folder", ""),
            "relevance": row["relevance"] or base.get("relevance", ""),
        })
        return base
