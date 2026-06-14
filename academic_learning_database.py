"""
academic_learning_database.py
==============================
Comprehensive learning database for Research Hunter v2-4

Tracks and learns from:
- Every search performed
- Every paper downloaded and analyzed
- Every writing pattern observed
- Every study structure generated
- Workflow form patterns and their effects

Uses Ollama to learn academic writing styles and generate research papers

ENHANCED for 10,000+ papers:
- Hierarchical chunking (chunk -> paper -> topic -> field summaries)
- WAL mode + performance pragmas for SQLite at scale
- Content-hash deduplication
- FTS5 full-text search
- Batch processing with progress queue
- Cursor-based pagination
- Multi-level summary aggregation
"""

import sqlite3
import json
import hashlib
import time
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any, Generator
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import threading

# Ollama client
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


CHUNK_SIZE = 1000       # tokens per chunk
CHUNK_OVERLAP = 100     # overlap between chunks
BATCH_SIZE = 50         # papers per batch for processing
MAX_RETRY = 3           # retry attempts for failed chunks


@dataclass
class StudyType:
    """Represents a type of academic study"""
    id: str
    name: str
    description: str
    required_sections: List[str]
    typical_length: str
    methodology_patterns: List[str]
    citation_style: str
    examples: List[str]
    language_specific: Dict[str, str]


@dataclass
class FieldPattern:
    """Academic field-specific patterns"""
    field_id: str
    field_name: str
    common_methods: List[str]
    key_concepts: List[str]
    important_journals: List[str]
    typical_structure_variations: List[str]
    terminology: Dict[str, str]
    writing_style_notes: str


@dataclass
class WorkflowConfig:
    """Stores workflow form configuration and its effects"""
    research_topic: str
    academic_field: str
    publication_type: str
    study_level: str
    methodology: str
    language: str
    year_range: str
    quartile_filter: str
    search_mode: str
    output_format: str

    def to_dict(self) -> Dict:
        return asdict(self)


class OllamaInterface:
    """Interface to Ollama for learning and generation"""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.model = "qwen2.5vl:3b"
        self._available = None

    @property
    def available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            if HAS_REQUESTS:
                r = requests.get(f"{self.base_url}/api/tags", timeout=5)
                self._available = r.status_code == 200
            else:
                self._available = False
        except Exception:
            self._available = False
        return self._available

    def generate(self, prompt: str, system: str = "", temperature: float = 0.3) -> str:
        if not self.available or not HAS_REQUESTS:
            return ""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": 4096
            }
        }

        if system:
            payload["system"] = system

        try:
            r = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=180)
            if r.status_code == 200:
                return r.json().get("response", "")
        except Exception as e:
            print(f"Ollama error: {e}")
        return ""

    def chat(self, messages: List[Dict], temperature: float = 0.3) -> str:
        if not self.available or not HAS_REQUESTS:
            return ""

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": 4096
            }
        }

        try:
            r = requests.post(f"{self.base_url}/v1/chat/completions", json=payload, timeout=180)
            if r.status_code == 200:
                return r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            print(f"Ollama chat error: {e}")
        return ""


class AcademicLearningDatabase:
    """
    SQLite-based learning database — enhanced for 10,000+ papers.

    New features for scale:
    - paper_chunks table: chunked content with per-chunk summaries
    - processing_queue: resumable batch processing with progress tracking
    - topic_summaries: hierarchical summaries (chunk -> paper -> topic -> field)
    - FTS5 virtual table: full-text search across all papers
    - Content-hash deduplication on add_paper
    - Cursor-based pagination on all list queries
    - WAL mode + cache tuning for high read concurrency
    """

    def __init__(self, db_path: str = "academic_learning.db"):
        self.db_path = db_path
        self.ollama = OllamaInterface()
        self.lock = threading.Lock()
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=268435456")
        return conn

    def _init_database(self):
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    results_count INTEGER,
                    papers_downloaded INTEGER,
                    field TEXT,
                    language TEXT,
                    config_hash TEXT,
                    session_id TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS papers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    authors TEXT,
                    abstract TEXT,
                    keywords TEXT,
                    journal TEXT,
                    year INTEGER,
                    doi TEXT,
                    url TEXT,
                    file_path TEXT,
                    file_type TEXT,
                    text_content TEXT,
                    language TEXT,
                    field TEXT,
                    paper_type TEXT,
                    quartile TEXT,
                    downloaded_at TEXT,
                    analyzed BOOLEAN DEFAULT 0,
                    content_hash TEXT UNIQUE,
                    quality_score REAL,
                    relevance_score REAL,
                    search_id INTEGER,
                    word_count INTEGER DEFAULT 0,
                    FOREIGN KEY (search_id) REFERENCES searches(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS paper_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_text TEXT NOT NULL,
                    token_count INTEGER,
                    summary TEXT,
                    embedding TEXT,
                    created_at TEXT,
                    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS field_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    field_id TEXT UNIQUE NOT NULL,
                    field_name TEXT NOT NULL,
                    common_methods TEXT,
                    key_concepts TEXT,
                    important_journals TEXT,
                    structure_variations TEXT,
                    terminology TEXT,
                    style_notes TEXT,
                    updated_at TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS study_types (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    required_sections TEXT,
                    typical_length TEXT,
                    methodology_patterns TEXT,
                    citation_style TEXT,
                    examples TEXT,
                    language_specific TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workflow_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_hash TEXT UNIQUE NOT NULL,
                    config_json TEXT NOT NULL,
                    times_used INTEGER DEFAULT 1,
                    last_used TEXT,
                    success_rate REAL,
                    generated_papers INTEGER
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS writing_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT NOT NULL,
                    pattern_text TEXT NOT NULL,
                    context TEXT,
                    field TEXT,
                    study_type TEXT,
                    language TEXT,
                    quality_score REAL,
                    usage_count INTEGER DEFAULT 1,
                    learned_from TEXT,
                    created_at TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS generated_papers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    workflow_config_id INTEGER,
                    papers_used TEXT,
                    field TEXT,
                    study_type TEXT,
                    language TEXT,
                    generated_at TEXT,
                    quality_score REAL,
                    user_feedback TEXT,
                    FOREIGN KEY (workflow_config_id) REFERENCES workflow_configs(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learned_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_category TEXT NOT NULL,
                    pattern_key TEXT NOT NULL,
                    pattern_value TEXT,
                    confidence REAL,
                    source TEXT,
                    language TEXT,
                    field TEXT,
                    learned_at TEXT,
                    usage_count INTEGER DEFAULT 1
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER,
                    knowledge_type TEXT,
                    knowledge_text TEXT,
                    source_paper_id INTEGER,
                    extracted_at TEXT,
                    confidence REAL,
                    FOREIGN KEY (source_paper_id) REFERENCES papers(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processing_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0,
                    error TEXT,
                    created_at TEXT,
                    processed_at TEXT,
                    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS topic_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    field TEXT,
                    summary_level INTEGER DEFAULT 1,
                    summary_text TEXT,
                    source_papers INTEGER DEFAULT 0,
                    scope_json TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

            try:
                cursor.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
                        title, abstract, text_content, keywords,
                        content='papers', content_rowid='id',
                        tokenize='unicode61'
                    )
                """)
            except Exception:
                pass

            for idx_sql in [
                "CREATE INDEX IF NOT EXISTS idx_papers_title ON papers(title)",
                "CREATE INDEX IF NOT EXISTS idx_papers_field ON papers(field)",
                "CREATE INDEX IF NOT EXISTS idx_papers_language ON papers(language)",
                "CREATE INDEX IF NOT EXISTS idx_searches_query ON searches(query)",
                "CREATE INDEX IF NOT EXISTS idx_learned_category ON learned_patterns(pattern_category)",
                "CREATE INDEX IF NOT EXISTS idx_chunks_paper ON paper_chunks(paper_id, chunk_index)",
                "CREATE INDEX IF NOT EXISTS idx_queue_status ON processing_queue(status, stage)",
                "CREATE INDEX IF NOT EXISTS idx_queue_paper ON processing_queue(paper_id)",
                "CREATE INDEX IF NOT EXISTS idx_topic_field ON topic_summaries(field, topic)",
                "CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year)",
            ]:
                try:
                    cursor.execute(idx_sql)
                except Exception:
                    pass

            for col_sql in [
                "ALTER TABLE papers ADD COLUMN content_hash TEXT UNIQUE",
                "ALTER TABLE papers ADD COLUMN word_count INTEGER DEFAULT 0",
                "CREATE INDEX IF NOT EXISTS idx_papers_content_hash ON papers(content_hash)",
            ]:
                try:
                    cursor.execute(col_sql)
                except Exception:
                    pass

            conn.commit()
            conn.close()

    # ═══════════════════════════════════════════════════════════════════════════
    # CHUNKING — Core infrastructure
    # ═══════════════════════════════════════════════════════════════════════════

    def chunk_text(self, text: str, chunk_size: int = CHUNK_SIZE,
                   overlap: int = CHUNK_OVERLAP) -> List[Tuple[int, str, int]]:
        words = text.split()
        chunks = []
        i = 0
        while i < len(words):
            end = min(i + chunk_size, len(words))
            chunk_words = words[i:end]
            chunks.append((len(chunks), " ".join(chunk_words), len(chunk_words)))
            if end >= len(words):
                break
            i += chunk_size - overlap
        return chunks

    def _compute_content_hash(self, paper_data: Dict) -> str:
        raw = (paper_data.get("title", "") + paper_data.get("abstract", "")).strip().lower()
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def is_duplicate(self, paper_data: Dict) -> Optional[int]:
        h = self._compute_content_hash(paper_data)
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM papers WHERE content_hash = ?", (h,))
        row = cursor.fetchone()
        conn.close()
        return row["id"] if row else None

    # ═══════════════════════════════════════════════════════════════════════════
    # SEARCH TRACKING
    # ═══════════════════════════════════════════════════════════════════════════

    def record_search(self, query: str, config: WorkflowConfig, results_count: int = 0,
                      papers_downloaded: int = 0, session_id: str = "") -> int:
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            config_hash = hashlib.md5(
                json.dumps(asdict(config), sort_keys=True).encode()
            ).hexdigest()

            cursor.execute("""
                INSERT INTO searches (query, timestamp, results_count, papers_downloaded,
                                     field, language, config_hash, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (query, datetime.now().isoformat(), results_count, papers_downloaded,
                  config.academic_field, config.language, config_hash, session_id))

            search_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return search_id

    def get_recent_searches(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM searches ORDER BY timestamp DESC LIMIT ? OFFSET ?
        """, (limit, offset))
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def count_searches(self) -> int:
        conn = self._get_connection()
        row = conn.execute("SELECT COUNT(*) as c FROM searches").fetchone()
        conn.close()
        return row["c"]

    # ═══════════════════════════════════════════════════════════════════════════
    # PAPER MANAGEMENT — Dedup, chunk, paginate
    # ═══════════════════════════════════════════════════════════════════════════

    def add_paper(self, paper_data: Dict, search_id: int = None) -> int:
        existing = self.is_duplicate(paper_data)
        if existing:
            return existing

        content_hash = self._compute_content_hash(paper_data)
        text = paper_data.get("text_content", "")
        word_count = len(text.split())

        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO papers (title, authors, abstract, keywords, journal, year,
                                   doi, url, file_path, file_type, text_content, language,
                                   field, paper_type, quartile, downloaded_at, search_id,
                                   content_hash, word_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                paper_data.get("title", ""),
                json.dumps(paper_data.get("authors", [])),
                paper_data.get("abstract", ""),
                json.dumps(paper_data.get("keywords", [])),
                paper_data.get("journal", ""),
                paper_data.get("year"),
                paper_data.get("doi", ""),
                paper_data.get("url", ""),
                paper_data.get("file_path", ""),
                paper_data.get("file_type", ""),
                text,
                paper_data.get("language", "en"),
                paper_data.get("field", ""),
                paper_data.get("paper_type", ""),
                paper_data.get("quartile", ""),
                datetime.now().isoformat(),
                search_id,
                content_hash,
                word_count
            ))

            paper_id = cursor.lastrowid
            conn.commit()
            conn.close()

        self._queue_processing(paper_id)
        return paper_id

    def add_papers_bulk(self, papers_data: List[Dict], search_id: int = None) -> int:
        added = 0
        for pd in papers_data:
            try:
                self.add_paper(pd, search_id)
                added += 1
            except Exception as e:
                print(f"  [SKIP] {pd.get('title', '?')[:60]} — {e}")
        return added

    def _queue_processing(self, paper_id: int):
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            for stage in ("chunk", "summarize", "analyze", "learn"):
                cursor.execute("""
                    INSERT OR IGNORE INTO processing_queue
                    (paper_id, stage, status, created_at)
                    VALUES (?, ?, 'pending', ?)
                """, (paper_id, stage, now))
            conn.commit()
            conn.close()

    def get_papers_paginated(self, page: int = 1, per_page: int = 50,
                             field: str = None, language: str = None,
                             sort_by: str = "year", sort_dir: str = "DESC") -> Dict:
        conn = self._get_connection()
        cursor = conn.cursor()

        where = []
        params = []
        if field:
            where.append("field = ?")
            params.append(field)
        if language:
            where.append("language = ?")
            params.append(language)

        where_clause = ("WHERE " + " AND ".join(where)) if where else ""
        order = f"ORDER BY {sort_by} {sort_dir}"

        cursor.execute(f"SELECT COUNT(*) as c FROM papers {where_clause}", params)
        total = cursor.fetchone()["c"]

        offset = (page - 1) * per_page
        cursor.execute(f"""
            SELECT * FROM papers {where_clause} {order} LIMIT ? OFFSET ?
        """, params + [per_page, offset])

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        for r in results:
            try:
                if r.get("authors"):
                    r["authors"] = json.loads(r["authors"])
            except Exception:
                pass
            try:
                if r.get("keywords"):
                    r["keywords"] = json.loads(r["keywords"])
            except Exception:
                pass

        return {
            "papers": results,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": max(1, math.ceil(total / per_page)),
        }

    def get_papers_by_field(self, field: str, limit: int = 100) -> List[Dict]:
        result = self.get_papers_paginated(page=1, per_page=limit, field=field)
        return result["papers"]

    def get_paper_by_id(self, paper_id: int) -> Optional[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM papers WHERE id = ?", (paper_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            data = dict(row)
            try:
                if data.get("authors"):
                    data["authors"] = json.loads(data["authors"])
            except Exception:
                pass
            try:
                if data.get("keywords"):
                    data["keywords"] = json.loads(data["keywords"])
            except Exception:
                pass
            return data
        return None

    # ═══════════════════════════════════════════════════════════════════════════
    # FULL-TEXT SEARCH via FTS5
    # ═══════════════════════════════════════════════════════════════════════════

    def _sync_fts(self):
        try:
            conn = self._get_connection()
            conn.execute("INSERT INTO papers_fts(papers_fts) VALUES('rebuild')")
            conn.commit()
            conn.close()
        except Exception:
            pass

    def search_papers(self, query: str, page: int = 1, per_page: int = 50,
                      field: str = None, language: str = None) -> Dict:
        conn = self._get_connection()
        cursor = conn.cursor()

        safe_query = query.replace('"', '""')
        fts_where = "papers_fts MATCH ?"
        fts_params = [safe_query]

        if field:
            fts_where += " AND p.field = ?"
            fts_params.append(field)
        if language:
            fts_where += " AND p.language = ?"
            fts_params.append(language)

        try:
            cursor.execute(f"""
                SELECT COUNT(*) as c FROM papers_fts f
                JOIN papers p ON p.id = f.rowid
                WHERE {fts_where}
            """, fts_params)
            total = cursor.fetchone()["c"]
        except Exception:
            conn.close()
            return {"papers": [], "page": page, "per_page": per_page, "total": 0, "total_pages": 0}

        offset = (page - 1) * per_page
        cursor.execute(f"""
            SELECT p.*, rank FROM papers_fts f
            JOIN papers p ON p.id = f.rowid
            WHERE {fts_where}
            ORDER BY rank
            LIMIT ? OFFSET ?
        """, fts_params + [per_page, offset])

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()

        for r in results:
            try:
                if r.get("authors"):
                    r["authors"] = json.loads(r["authors"])
            except Exception:
                pass
            try:
                if r.get("keywords"):
                    r["keywords"] = json.loads(r["keywords"])
            except Exception:
                pass

        return {
            "papers": results,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": max(1, math.ceil(total / per_page)),
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # PAPER ANALYSIS — chunk-based (no 5K limit)
    # ═══════════════════════════════════════════════════════════════════════════

    def analyze_paper_content(self, paper_id: int, text_content: str = None):
        if not self.ollama.available:
            return

        if text_content is None:
            paper = self.get_paper_by_id(paper_id)
            if not paper:
                return
            text_content = paper.get("text_content", "")

        if not text_content or len(text_content.strip()) < 100:
            with self.lock:
                conn = self._get_connection()
                conn.execute("UPDATE papers SET analyzed = 1 WHERE id = ?", (paper_id,))
                conn.commit()
                conn.close()
            return

        chunks = self.chunk_text(text_content)
        chunk_summaries = []
        total_chunks = len(chunks)

        print(f"  Analyzing paper {paper_id}: {total_chunks} chunks")

        for idx, chunk_text, token_count in chunks:
            existing = self._get_chunk_summary(paper_id, idx)
            if existing:
                chunk_summaries.append((idx, existing))
                continue

            prompt = f"""Summarize this section of an academic paper concisely.
Extract: key claims, methodology mentioned, findings, and terminology.

Section:
{chunk_text[:3000]}

Return a brief structured summary (3-5 bullet points)."""

            summary = self.ollama.generate(prompt, temperature=0.2)
            if summary:
                self._store_chunk(paper_id, idx, chunk_text, token_count, summary)
                chunk_summaries.append((idx, summary))

        if not chunk_summaries:
            return

        full_analysis = self._synthesize_analysis(paper_id, chunk_summaries, text_content)

        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE papers SET analyzed = 1 WHERE id = ?", (paper_id,))
            cursor.execute("""
                INSERT INTO document_knowledge (document_id, knowledge_type, knowledge_text, extracted_at)
                VALUES (?, ?, ?, ?)
            """, (paper_id, "chunked_analysis", full_analysis, datetime.now().isoformat()))
            conn.commit()
            conn.close()

        self._update_queue_status(paper_id, "analyze", "done")

    def _get_chunk_summary(self, paper_id: int, chunk_index: int) -> Optional[str]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT summary FROM paper_chunks WHERE paper_id = ? AND chunk_index = ?",
            (paper_id, chunk_index)
        )
        row = cursor.fetchone()
        conn.close()
        return row["summary"] if row and row["summary"] else None

    def _store_chunk(self, paper_id: int, chunk_index: int,
                     chunk_text: str, token_count: int, summary: str):
        with self.lock:
            conn = self._get_connection()
            conn.execute("""
                INSERT OR REPLACE INTO paper_chunks
                (paper_id, chunk_index, chunk_text, token_count, summary, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (paper_id, chunk_index, chunk_text, token_count,
                  summary, datetime.now().isoformat()))
            conn.commit()
            conn.close()

    def _synthesize_analysis(self, paper_id: int, chunk_summaries: List[Tuple[int, str]],
                             full_text: str) -> str:
        summaries_text = "\n".join(f"Section {i+1}: {s}" for i, (_, s) in enumerate(chunk_summaries))

        prompt = f"""Synthesize these section summaries of an academic paper into a complete analysis:

{summaries_text}

Extract and return:
1. KEY RESEARCH QUESTIONS
2. MAIN FINDINGS
3. METHODOLOGY USED
4. THEORETICAL FRAMEWORK
5. LIMITATIONS
6. FUTURE RESEARCH DIRECTIONS

Be specific and detailed. Use the full paper context when possible."""

        system = "You are an expert academic analyst. Synthesize section-level summaries into a coherent whole-paper analysis."
        return self.ollama.generate(prompt, system=system, temperature=0.2)

    def _update_queue_status(self, paper_id: int, stage: str, status: str, error: str = ""):
        with self.lock:
            conn = self._get_connection()
            now = datetime.now().isoformat()
            if error:
                conn.execute("""
                    UPDATE processing_queue SET status=?, error=?, processed_at=?
                    WHERE paper_id=? AND stage=?
                """, (status, error[:500], now, paper_id, stage))
            else:
                conn.execute("""
                    UPDATE processing_queue SET status=?, processed_at=?
                    WHERE paper_id=? AND stage=?
                """, (status, now, paper_id, stage))
            conn.commit()
            conn.close()

    # ═══════════════════════════════════════════════════════════════════════════
    # BATCH PROCESSING — Scalable pipeline for 10,000+ papers
    # ═══════════════════════════════════════════════════════════════════════════

    def get_processing_status(self) -> Dict:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT stage, status, COUNT(*) as count
            FROM processing_queue
            GROUP BY stage, status
            ORDER BY stage, status
        """)
        rows = cursor.fetchall()
        conn.close()

        status = defaultdict(lambda: defaultdict(int))
        for row in rows:
            status[row["stage"]][row["status"]] = row["count"]
        return {k: dict(v) for k, v in status.items()}

    def process_pending_batch(self, stage: str = "chunk", batch_size: int = BATCH_SIZE) -> Dict:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT q.paper_id, p.text_content
            FROM processing_queue q
            JOIN papers p ON p.id = q.paper_id
            WHERE q.stage = ? AND q.status = 'pending'
            ORDER BY q.id
            LIMIT ?
        """, (stage, batch_size))
        batch = cursor.fetchall()
        conn.close()

        if not batch:
            return {"stage": stage, "processed": 0, "total": 0, "done": True}

        processed = 0
        errors = 0
        for row in batch:
            try:
                if stage == "chunk":
                    self._stage_chunk(row["paper_id"], row["text_content"])
                elif stage == "summarize":
                    self._stage_summarize(row["paper_id"])
                elif stage == "analyze":
                    self.analyze_paper_content(row["paper_id"], row["text_content"])
                elif stage == "learn":
                    self._stage_learn(row["paper_id"])
                processed += 1
            except Exception as e:
                errors += 1
                self._update_queue_status(row["paper_id"], stage, "error", str(e))

        remaining = self._count_pending(stage)
        return {
            "stage": stage,
            "processed": processed,
            "errors": errors,
            "remaining": remaining,
            "done": remaining == 0,
        }

    def _stage_chunk(self, paper_id: int, text_content: str = None):
        if not text_content:
            paper = self.get_paper_by_id(paper_id)
            if not paper:
                return
            text_content = paper.get("text_content", "")

        if not text_content:
            self._update_queue_status(paper_id, "chunk", "done")
            return

        chunks = self.chunk_text(text_content)
        for idx, chunk_text, token_count in chunks:
            existing = self._get_chunk_summary(paper_id, idx)
            if not existing:
                prompt = f"""Summarize this section concisely.
Key claims, methodology, findings, terminology.

Section:
{chunk_text[:3000]}

Return 3-5 bullet points."""

                summary = self.ollama.generate(prompt, temperature=0.2)
                if summary:
                    self._store_chunk(paper_id, idx, chunk_text, token_count, summary)

        self._update_queue_status(paper_id, "chunk", "done")

    def _stage_summarize(self, paper_id: int):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT chunk_index, summary FROM paper_chunks
            WHERE paper_id = ? AND summary IS NOT NULL
            ORDER BY chunk_index
        """, (paper_id,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            self._update_queue_status(paper_id, "summarize", "done")
            return

        summaries = [(r["chunk_index"], r["summary"]) for r in rows]
        analysis = self._synthesize_analysis(paper_id, summaries, "")

        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE papers SET analyzed = 1 WHERE id = ?", (paper_id,))
            cursor.execute("""
                INSERT OR REPLACE INTO document_knowledge
                (document_id, knowledge_type, knowledge_text, extracted_at)
                VALUES (?, 'chunked_analysis', ?, ?)
            """, (paper_id, analysis, datetime.now().isoformat()))
            conn.commit()
            conn.close()

        self._update_queue_status(paper_id, "summarize", "done")

    def _stage_learn(self, paper_id: int):
        paper = self.get_paper_by_id(paper_id)
        if not paper:
            return

        text = paper.get("text_content", "") or paper.get("abstract", "")
        if len(text) < 500:
            self._update_queue_status(paper_id, "learn", "done")
            return

        field = paper.get("field", "general") or "general"
        lang = paper.get("language", "en") or "en"
        sample = text[:3000]

        prompt = f"""Analyze this academic text and identify writing patterns:
1. Common phrases used
2. Sentence structure patterns
3. Terminology and field-specific language
4. Citation style indicators

Text:
{sample}

Return a structured analysis of writing patterns."""

        patterns = self.ollama.generate(prompt, temperature=0.2)

        if patterns:
            with self.lock:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO learned_patterns
                    (pattern_category, pattern_key, pattern_value, source, language, field, learned_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, ("writing_patterns", f"{field}_{lang}", patterns,
                      f"paper_{paper_id}", lang, field, datetime.now().isoformat()))
                conn.commit()
                conn.close()

        self._update_queue_status(paper_id, "learn", "done")

    def _count_pending(self, stage: str) -> int:
        conn = self._get_connection()
        row = conn.execute(
            "SELECT COUNT(*) as c FROM processing_queue WHERE stage=? AND status='pending'",
            (stage,)
        ).fetchone()
        conn.close()
        return row["c"]

    def process_all_pending(self, stages: List[str] = None,
                            batch_size: int = BATCH_SIZE,
                            callback=None) -> Dict:
        if stages is None:
            stages = ["chunk", "summarize", "analyze", "learn"]

        results = {}
        for stage in stages:
            stage_results = []
            while True:
                result = self.process_pending_batch(stage, batch_size)
                stage_results.append(result)
                if callback:
                    callback(stage, result)
                if result["done"]:
                    break
            results[stage] = stage_results[-1] if stage_results else {"done": True}
        return results

    def reset_failed_queue_items(self):
        with self.lock:
            conn = self._get_connection()
            conn.execute("""
                UPDATE processing_queue
                SET status='pending', error=NULL, processed_at=NULL
                WHERE status='error' AND retry_count < ?
            """, (MAX_RETRY,))
            conn.execute("""
                UPDATE processing_queue
                SET retry_count = retry_count + 1
                WHERE status='error' AND retry_count < ?
            """, (MAX_RETRY,))
            conn.commit()
            conn.close()

    # ═══════════════════════════════════════════════════════════════════════════
    # TOPIC SUMMARY AGGREGATION — Hierarchical: chunk -> paper -> topic -> field
    # ═══════════════════════════════════════════════════════════════════════════

    def aggregate_topic_summary(self, topic: str, field: str = None,
                                summary_level: int = 2) -> Optional[str]:
        existing = self._get_topic_summary(topic, field, summary_level)
        if existing:
            return existing

        papers = self.search_papers(topic, page=1, per_page=100, field=field)
        all_papers = papers["papers"]

        if not all_papers:
            return None

        doc_knowledge = []
        for p in all_papers:
            kn = self._get_paper_knowledge(p["id"])
            if kn:
                doc_knowledge.append(kn)

        if not doc_knowledge:
            return None

        combined = "\n\n---\n\n".join(doc_knowledge[:20])
        scope = {"paper_count": len(all_papers), "knowledge_sources": len(doc_knowledge)}

        prompt = f"""Synthesize the following paper analyses on the topic "{topic}" into a comprehensive academic overview.

{combined}

Return a structured synthesis covering:
1. Current state of research
2. Key findings across studies
3. Methodological approaches used
4. Gaps and controversies
5. Future research directions"""

        system = "You are an expert at synthesizing academic literature. Create a coherent overview from multiple paper analyses."
        summary = self.ollama.generate(prompt, system=system, temperature=0.2)

        if summary:
            self._store_topic_summary(topic, field, summary_level, summary, scope)

        return summary

    def update_all_topic_summaries(self, field: str = None) -> Dict:
        conn = self._get_connection()
        cursor = conn.cursor()

        if field:
            cursor.execute("""
                SELECT DISTINCT field FROM papers
                WHERE field IS NOT NULL AND field != ''
            """)
            fields = [row["field"] for row in cursor.fetchall()]
        else:
            fields = [field]

        conn.close()

        results = {}
        for f in fields:
            try:
                summary = self.aggregate_topic_summary("literature_review", field=f, summary_level=3)
                results[f] = bool(summary)
            except Exception as e:
                results[f] = str(e)

        return results

    def _get_topic_summary(self, topic: str, field: str = None,
                           summary_level: int = 2) -> Optional[str]:
        conn = self._get_connection()
        cursor = conn.cursor()
        if field:
            cursor.execute("""
                SELECT summary_text FROM topic_summaries
                WHERE topic=? AND field=? AND summary_level=?
                ORDER BY updated_at DESC LIMIT 1
            """, (topic, field, summary_level))
        else:
            cursor.execute("""
                SELECT summary_text FROM topic_summaries
                WHERE topic=? AND summary_level=?
                ORDER BY updated_at DESC LIMIT 1
            """, (topic, summary_level))
        row = cursor.fetchone()
        conn.close()
        return row["summary_text"] if row else None

    def _store_topic_summary(self, topic: str, field: str,
                             summary_level: int, summary_text: str,
                             scope: Dict):
        with self.lock:
            conn = self._get_connection()
            now = datetime.now().isoformat()
            conn.execute("""
                INSERT INTO topic_summaries
                (topic, field, summary_level, summary_text, source_papers, scope_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (topic, field or "", summary_level, summary_text,
                  scope.get("paper_count", 0), json.dumps(scope),
                  now, now))
            conn.commit()
            conn.close()

    def _get_paper_knowledge(self, paper_id: int) -> Optional[str]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT knowledge_text FROM document_knowledge
            WHERE source_paper_id = ? ORDER BY extracted_at DESC LIMIT 1
        """, (paper_id,))
        row = cursor.fetchone()
        conn.close()
        return row["knowledge_text"] if row else None

    def get_chunks_for_paper(self, paper_id: int) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM paper_chunks WHERE paper_id = ? ORDER BY chunk_index
        """, (paper_id,))
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    # ═══════════════════════════════════════════════════════════════════════════
    # FIELD PATTERNS
    # ═══════════════════════════════════════════════════════════════════════════

    def learn_field_pattern(self, field_data: Dict):
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO field_patterns
                (field_id, field_name, common_methods, key_concepts, important_journals,
                 structure_variations, terminology, style_notes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                field_data.get("field_id", ""),
                field_data.get("field_name", ""),
                json.dumps(field_data.get("common_methods", [])),
                json.dumps(field_data.get("key_concepts", [])),
                json.dumps(field_data.get("important_journals", [])),
                json.dumps(field_data.get("structure_variations", [])),
                json.dumps(field_data.get("terminology", {})),
                field_data.get("style_notes", ""),
                datetime.now().isoformat()
            ))

            conn.commit()
            conn.close()

    def get_field_pattern(self, field_id: str) -> Optional[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM field_patterns WHERE field_id = ?", (field_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            data = dict(row)
            data["common_methods"] = json.loads(data["common_methods"] or "[]")
            data["key_concepts"] = json.loads(data["key_concepts"] or "[]")
            data["important_journals"] = json.loads(data["important_journals"] or "[]")
            data["structure_variations"] = json.loads(data["structure_variations"] or "[]")
            data["terminology"] = json.loads(data["terminology"] or "{}")
            return data
        return None

    # ═══════════════════════════════════════════════════════════════════════════
    # STUDY TYPES
    # ═══════════════════════════════════════════════════════════════════════════

    def init_study_types(self):
        study_types = [
            StudyType(
                id="research_article",
                name="Research Article",
                description="Original empirical research",
                required_sections=["abstract", "introduction", "methodology", "results", "discussion", "references"],
                typical_length="5000-8000 words",
                methodology_patterns=["quantitative", "qualitative", "mixed_methods", "experimental", "correlational"],
                citation_style="APA",
                examples=["empirical study", "original research"],
                language_specific={"ar": "مقال بحثي", "fr": "Article de recherche"}
            ),
            StudyType(
                id="systematic_review",
                name="Systematic Review",
                description="Comprehensive review of literature using systematic methods",
                required_sections=["abstract", "introduction", "methods", "results", "discussion", "conclusion", "references"],
                typical_length="8000-15000 words",
                methodology_patterns=["prisma", "search_strategy", "inclusion_criteria", "quality_assessment"],
                citation_style="APA",
                examples=["systematic review", "meta-analysis"],
                language_specific={"ar": "مراجعة منهجية", "fr": "Revue systématique"}
            ),
            StudyType(
                id="thesis_phd",
                name="PhD Dissertation",
                description="Doctoral dissertation",
                required_sections=["abstract", "acknowledgments", "introduction", "literature_review",
                                  "methodology", "results", "discussion", "conclusion", "references", "appendices"],
                typical_length="80000-100000 words",
                methodology_patterns=["qualitative", "quantitative", "mixed", "historical", "case_study"],
                citation_style="APA",
                examples=["phd thesis", "doctoral dissertation"],
                language_specific={"ar": "أطروحة دكتوراه", "fr": "Thèse de doctorat"}
            ),
            StudyType(
                id="thesis_master",
                name="Master's Thesis",
                description="Master's degree thesis",
                required_sections=["abstract", "introduction", "literature_review", "methodology",
                                  "results", "discussion", "conclusion", "references"],
                typical_length="15000-30000 words",
                methodology_patterns=["quantitative", "qualitative", "mixed_methods"],
                citation_style="APA",
                examples=["master thesis", "ma thesis", "msc thesis"],
                language_specific={"ar": "رسالة ماجستير", "fr": "Mémoire de master"}
            ),
            StudyType(
                id="conference_paper",
                name="Conference Paper",
                description="Paper presented at academic conference",
                required_sections=["abstract", "introduction", "methodology", "results", "conclusion", "references"],
                typical_length="4000-6000 words",
                methodology_patterns=["quantitative", "qualitative", "case_study"],
                citation_style="IEEE",
                examples=["conference paper", "conference proceedings"],
                language_specific={"ar": "ورقة مؤتمر", "fr": "Article de conférence"}
            ),
            StudyType(
                id="book_chapter",
                name="Book Chapter",
                description="Chapter in an academic book",
                required_sections=["introduction", "content_sections", "conclusion", "references"],
                typical_length="5000-10000 words",
                methodology_patterns=["theoretical", "conceptual", "analytical"],
                citation_style="APA",
                examples=["book chapter", "edited volume"],
                language_specific={"ar": "فصل كتاب", "fr": "Chapitre de livre"}
            ),
            StudyType(
                id="literature_review",
                name="Literature Review",
                description="Comprehensive review of existing literature",
                required_sections=["abstract", "introduction", "search_methodology", "results", "discussion", "conclusion", "references"],
                typical_length="6000-12000 words",
                methodology_patterns=["thematic", "chronological", "conceptual"],
                citation_style="APA",
                examples=["review article", "narrative review"],
                language_specific={"ar": "مراجعة أدبيات", "fr": "Revue de littérature"}
            )
        ]

        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            for st in study_types:
                cursor.execute("""
                    INSERT OR REPLACE INTO study_types
                    (id, name, description, required_sections, typical_length,
                     methodology_patterns, citation_style, examples, language_specific)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    st.id, st.name, st.description, json.dumps(st.required_sections),
                    st.typical_length, json.dumps(st.methodology_patterns), st.citation_style,
                    json.dumps(st.examples), json.dumps(st.language_specific)
                ))

            conn.commit()
            conn.close()

    def get_study_type(self, study_type_id: str) -> Optional[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM study_types WHERE id = ?", (study_type_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            data = dict(row)
            data["required_sections"] = json.loads(data["required_sections"] or "[]")
            data["methodology_patterns"] = json.loads(data["methodology_patterns"] or "[]")
            data["examples"] = json.loads(data["examples"] or "[]")
            data["language_specific"] = json.loads(data["language_specific"] or "{}")
            return data
        return None

    # ═══════════════════════════════════════════════════════════════════════════
    # PAPER GENERATION — Enhanced with chunked context
    # ═══════════════════════════════════════════════════════════════════════════

    def generate_research_paper(self, config: WorkflowConfig,
                                reference_papers: List[Dict] = None) -> str:
        if not self.ollama.available:
            return "Error: Ollama not available"

        study_type = self.get_study_type(config.publication_type)
        if not study_type:
            study_type = self.get_study_type("research_article")

        field_pattern = self.get_field_pattern(config.academic_field)

        system_prompt = f"""You are an expert academic writer specializing in {config.academic_field}.
You write high-quality academic papers following {study_type.get('citation_style', 'APA')} format.

Study Type: {study_type['name']}
Required Sections: {', '.join(study_type['required_sections'])}
Typical Length: {study_type['typical_length']}

Language: {config.language}
Methodology: {config.methodology}

Focus on:
- Clear, academic writing style
- Proper structure and flow
- Evidence-based arguments
- Appropriate citations format
"""

        prompt = f"""Write a complete academic {study_type['name']} on the topic:

TOPIC: {config.research_topic}

"""

        if hasattr(config, "research_questions"):
            for i, rq in enumerate(config.research_questions, 1):
                if rq:
                    prompt += f"Research Question {i}: {rq}\n"

        if reference_papers:
            prompt += "\nREFERENCE PAPERS:\n"
            for i, paper in enumerate(reference_papers[:10], 1):
                prompt += f"\n{i}. {paper.get('title', 'Unknown')}"
                if paper.get("abstract"):
                    prompt += f"\n   Abstract: {paper['abstract'][:500]}..."

            topic_summary = self._get_topic_summary(
                config.research_topic, config.academic_field, summary_level=2
            )
            if topic_summary:
                prompt += f"\n\nLEARNED TOPIC CONTEXT:\n{topic_summary[:2000]}\n"

        if field_pattern:
            prompt += f"\n\nFIELD-SPECIFIC GUIDANCE:\n"
            prompt += f"Common Methods: {', '.join(field_pattern.get('common_methods', [])[:5])}\n"
            prompt += f"Key Concepts: {', '.join(field_pattern.get('key_concepts', [])[:5])}\n"
            if field_pattern.get("style_notes"):
                prompt += f"Writing Style: {field_pattern['style_notes']}\n"

        written_patterns = self.get_learned_patterns(
            category="writing_patterns",
            field=config.academic_field
        )
        if written_patterns:
            prompt += "\n\nLEARNED WRITING PATTERNS:\n"
            for wp in written_patterns[:3]:
                prompt += f"\n{wp.get('pattern_value', '')[:1000]}\n"

        prompt += """
\nWrite the complete paper with ALL required sections.
Include proper headings, content, and formatting.
Return ONLY the paper content, no additional commentary.
"""

        result = self.ollama.generate(prompt, system=system_prompt, temperature=0.3)

        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO generated_papers (title, content, field, study_type, language, generated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                config.research_topic,
                result,
                config.academic_field,
                config.publication_type,
                config.language,
                datetime.now().isoformat()
            ))
            conn.commit()
            conn.close()

        return result

    # ═══════════════════════════════════════════════════════════════════════════
    # LEARNING FROM CONTENT — Unlimited via batching
    # ═══════════════════════════════════════════════════════════════════════════

    def learn_from_papers(self, papers: List[Dict], field: str, language: str = "en",
                          batch_mode: bool = True, max_samples: int = None):
        if not self.ollama.available or not papers:
            return

        target = papers if max_samples is None else papers[:max_samples]

        if batch_mode:
            for p in target:
                self.add_paper(p)
                paper_id = self.is_duplicate(p)
                if paper_id and not self._get_paper_knowledge(paper_id):
                    self.analyze_paper_content(paper_id)
        else:
            samples = []
            for paper in target:
                text = paper.get("text_content", "") or paper.get("abstract", "")
                if len(text) > 500:
                    samples.append(text[:3000])

            if not samples:
                return

            combined = "\n\n---\n\n".join(samples)

            prompt = f"""Analyze these academic paper samples and identify:
1. Common phrases and transitions
2. Typical sentence structures
3. Field-specific terminology usage
4. Citation patterns
5. Writing style characteristics

Papers:
{combined}

Return a structured analysis of the patterns found."""

            patterns = self.ollama.generate(prompt, temperature=0.2)

            with self.lock:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO learned_patterns (pattern_category, pattern_key, pattern_value,
                                                 source, language, field, learned_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    "writing_patterns",
                    f"{field}_{language}",
                    patterns,
                    f"batch_{len(target)}_papers",
                    language,
                    field,
                    datetime.now().isoformat()
                ))
                conn.commit()
                conn.close()

    def get_learned_patterns(self, category: str = None, field: str = None) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM learned_patterns WHERE 1=1"
        params = []

        if category:
            query += " AND pattern_category = ?"
            params.append(category)

        if field:
            query += " AND field = ?"
            params.append(field)

        query += " ORDER BY usage_count DESC"

        cursor.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    # ═══════════════════════════════════════════════════════════════════════════
    # STATISTICS — Fast aggregation without full scans
    # ═══════════════════════════════════════════════════════════════════════════

    def get_statistics(self) -> Dict:
        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {}

        tables = ["searches", "papers", "field_patterns", "study_types",
                  "generated_papers", "learned_patterns", "document_knowledge",
                  "paper_chunks", "processing_queue", "topic_summaries"]

        for table in tables:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
            stats[table] = cursor.fetchone()["count"]

        cursor.execute("""
            SELECT field, COUNT(*) as count FROM papers
            WHERE field IS NOT NULL AND field != ''
            GROUP BY field ORDER BY count DESC LIMIT 10
        """)
        stats["papers_by_field"] = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT language, COUNT(*) as count FROM papers
            WHERE language IS NOT NULL
            GROUP BY language
        """)
        stats["papers_by_language"] = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT quartile, COUNT(*) as count FROM papers
            WHERE quartile IS NOT NULL AND quartile != ''
            GROUP BY quartile ORDER BY quartile
        """)
        stats["papers_by_quartile"] = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT stage, status, COUNT(*) as count
            FROM processing_queue GROUP BY stage, status
        """)
        stats["queue_status"] = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT summary_level, COUNT(*) as count
            FROM topic_summaries GROUP BY summary_level
        """)
        stats["topic_summaries_by_level"] = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT SUM(word_count) as total_words,
                   AVG(word_count) as avg_words,
                   MAX(word_count) as max_words
            FROM papers
        """)
        row = cursor.fetchone()
        if row:
            stats["word_count_total"] = row["total_words"] or 0
            stats["word_count_avg"] = round(row["avg_words"] or 0, 1)
            stats["word_count_max"] = row["max_words"] or 0

        cursor.execute("""
            SELECT COUNT(*) as analyzed,
                   ROUND(AVG(quality_score), 2) as avg_quality,
                   ROUND(AVG(relevance_score), 2) as avg_relevance
            FROM papers WHERE analyzed = 1
        """)
        row = cursor.fetchone()
        if row:
            stats["papers_analyzed"] = row["analyzed"] or 0
            stats["avg_quality"] = row["avg_quality"] or 0
            stats["avg_relevance"] = row["avg_relevance"] or 0

        conn.close()
        return stats

    def get_db_size(self) -> Dict:
        path = Path(self.db_path)
        wal_path = path.with_suffix(".db-wal")
        shm_path = path.with_suffix(".db-shm")

        sizes = {"main": path.stat().st_size if path.exists() else 0}
        if wal_path.exists():
            sizes["wal"] = wal_path.stat().st_size
        if shm_path.exists():
            sizes["shm"] = shm_path.stat().st_size
        sizes["total_mb"] = round(sum(sizes.values()) / (1024 * 1024), 2)
        return sizes


def initialize_learning_database():
    """Initialize the learning database"""
    db = AcademicLearningDatabase()
    db.init_study_types()
    return db


def format_size_report(db: AcademicLearningDatabase):
    print("=" * 60)
    print("📊 ENHANCED ACADEMIC LEARNING DATABASE — REPORT")
    print("=" * 60)
    stats = db.get_statistics()
    sizes = db.get_db_size()

    print(f"\n🗄️  Database: {db.db_path} ({sizes['total_mb']} MB)")
    print(f"\n📚 Papers:     {stats['papers']}")
    print(f"   📝 Total words: {stats.get('word_count_total', 'N/A')}")
    print(f"   📏 Avg words:   {stats.get('word_count_avg', 'N/A')}")
    print(f"   ✅ Analyzed:    {stats.get('papers_analyzed', 'N/A')}")
    print(f"   🧩 Chunks:      {stats['paper_chunks']}")
    print(f"\n🔍 Searches:  {stats['searches']}")
    print(f"📋 Patterns:  {stats['learned_patterns']}")
    print(f"📄 Generated: {stats['generated_papers']}")
    print(f"🧠 Knowledge: {stats['document_knowledge']}")
    print(f"📊 Summaries: {stats['topic_summaries']}")
    print(f"\n⏳ Queue:")
    for qs in stats.get("queue_status", []):
        print(f"   {qs['stage']}/{qs['status']}: {qs['count']}")

    print(f"\n📈 Avg quality:    {stats.get('avg_quality', 'N/A')}")
    print(f"   Avg relevance:  {stats.get('avg_relevance', 'N/A')}")

    if stats.get("topic_summaries_by_level"):
        print(f"\n📚 Topic Summaries by Level:")
        for ts in stats["topic_summaries_by_level"]:
            lvl_name = {1: "per-paper", 2: "per-topic", 3: "per-field"}.get(
                ts.get("summary_level", 0), "unknown"
            )
            print(f"   Level {ts['summary_level']} ({lvl_name}): {ts['count']}")

    print("\n✓ Enhanced learning database ready!")


if __name__ == "__main__":
    db = initialize_learning_database()
    format_size_report(db)
