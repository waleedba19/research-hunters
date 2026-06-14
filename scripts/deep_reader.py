#!/usr/bin/env python3
"""
scripts/deep_reader.py — Deep PDF Reading & Knowledge Extraction v1.0
=====================================================================
Reads academic papers page-by-page, extracts structure, writing patterns,
methodologies, and key findings. Stores knowledge in deep_knowledge.db.
Deletes PDFs after processing. Sends Telegram notifications.

Usage:
  python scripts/deep_reader.py --model qwen2.5vl:3b --max-papers 3
  python scripts/deep_reader.py --model qwen2.5vl:3b --max-papers 3 --notify
  python scripts/deep_reader.py --stats
  python scripts/deep_reader.py --report
"""

import hashlib, json, os, re, sqlite3, sys, time, urllib.request, urllib.parse
import tempfile, shutil, ssl
from pathlib import Path
from datetime import datetime
from collections import defaultdict

SCRIPTS_DIR = Path(__file__).parent
PROOF_DB = SCRIPTS_DIR / "proof_memory.db"
DEEP_DB = SCRIPTS_DIR / "deep_knowledge.db"
OLLAMA_URL = "http://127.0.0.1:11434"
MODEL_NAME = None
PDF_DIR = Path(tempfile.gettempdir()) / "deep_reader_pdfs"
TELEGRAM_CHAT_ID = "6792230101"
MAX_TELEGRAM_LEN = 4000

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


class DeepReader:
    def __init__(self, max_papers: int = 3):
        self.max_papers = max_papers
        self.conn = sqlite3.connect(str(DEEP_DB))
        self.conn.row_factory = sqlite3.Row
        self._init_db()
        self.stats = defaultdict(int)
        self.reading_results = []
        self.total_reading_time = 0

    def _init_db(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS processed_pdfs (
                source_url_hash TEXT PRIMARY KEY,
                source_url TEXT,
                title TEXT,
                category TEXT,
                download_success INTEGER DEFAULT 0,
                total_pages INTEGER DEFAULT 0,
                total_sections INTEGER DEFAULT 0,
                patterns_extracted INTEGER DEFAULT 0,
                knowledge_facts INTEGER DEFAULT 0,
                processed_at TEXT,
                pdf_size_bytes INTEGER DEFAULT 0,
                error_message TEXT
            );
            CREATE TABLE IF NOT EXISTS paper_structures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url_hash TEXT,
                section_name TEXT,
                page_start INTEGER,
                page_end INTEGER,
                section_summary TEXT,
                key_points TEXT,
                word_count INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS writing_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url_hash TEXT,
                category TEXT,
                pattern_text TEXT,
                context_note TEXT,
                frequency INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS extracted_knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url_hash TEXT,
                knowledge_type TEXT,
                content TEXT,
                confidence TEXT,
                page_reference INTEGER
            );
            CREATE TABLE IF NOT EXISTS citation_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url_hash TEXT,
                citation_style TEXT,
                placement TEXT,
                example_text TEXT
            );
            CREATE TABLE IF NOT EXISTS formatting_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url_hash TEXT,
                font_name TEXT,
                font_size_body INTEGER,
                font_size_headings INTEGER,
                line_spacing REAL,
                margins_json TEXT,
                column_count INTEGER DEFAULT 1,
                heading_style TEXT
            );
            CREATE TABLE IF NOT EXISTS deep_reading_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date TEXT,
                papers_attempted INTEGER,
                papers_succeeded INTEGER,
                papers_failed INTEGER,
                total_pages_read INTEGER,
                patterns_learned INTEGER,
                knowledge_facts INTEGER,
                duration_seconds REAL
            );
        """)
        self.conn.commit()

    def _ollama_ready(self) -> bool:
        try:
            r = urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5)
            data = json.loads(r.read())
            models = [m["name"] for m in data.get("models", [])]
            return MODEL_NAME in models
        except Exception:
            return False

    def _ollama_call(self, prompt: str, max_tokens: int = 512) -> str:
        try:
            req = urllib.request.Request(
                f"{OLLAMA_URL}/api/generate",
                data=json.dumps({
                    "model": MODEL_NAME, "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": max_tokens}
                }).encode(),
                headers={"Content-Type": "application/json"}
            )
            resp = json.loads(urllib.request.urlopen(req, timeout=120).read())
            return resp.get("response", "").strip()
        except Exception as e:
            return f"ERROR: {e}"

    def get_candidates(self) -> list:
        proof_conn = sqlite3.connect(str(PROOF_DB))
        proof_conn.row_factory = sqlite3.Row
        try:
            processed = set()
            try:
                rows = self.conn.execute("SELECT source_url_hash FROM processed_pdfs").fetchall()
                for r in rows:
                    processed.add(r[0])
            except Exception:
                pass

            placeholders = ",".join("?" for _ in processed) if processed else "''"
            rows = proof_conn.execute(
                f"SELECT dr.result_hash, dr.title, dr.url, dr.relevance_score, dt.category "
                f"FROM daily_learn_results dr "
                f"LEFT JOIN daily_learn_topics dt ON dr.topic_hash = dt.topic_hash "
                f"WHERE dr.relevance_score IN ('high', 'medium') "
                f"AND dr.result_hash NOT IN ({placeholders}) "
                f"ORDER BY CASE dr.relevance_score WHEN 'high' THEN 0 ELSE 1 END, dr.first_seen DESC "
                f"LIMIT ?",
                list(processed) + [self.max_papers]
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            print(f"  Error querying proof_memory.db: {e}")
            return []
        finally:
            proof_conn.close()

    def download_pdf(self, url: str, title: str) -> Path | None:
        PDF_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", title)[:60]
        pdf_path = PDF_DIR / f"{safe_name}.pdf"

        strategies = [
            ("Direct PDF", lambda: self._try_direct_pdf(url)),
            ("HTTrack PDF from page", lambda: self._try_extract_from_html(url)),
            ("arXiv PDF", lambda: self._try_arxiv_pdf(url)),
        ]

        for strategy_name, strategy_fn in strategies:
            try:
                print(f"    Trying {strategy_name}...")
                data = strategy_fn()
                if data and len(data) > 50000:
                    pdf_path.write_bytes(data)
                    if pdf_path.stat().st_size > 10000:
                        print(f"    Downloaded: {pdf_path.stat().st_size} bytes")
                        return pdf_path
            except Exception:
                continue

        return None

    def _try_direct_pdf(self, url: str) -> bytes | None:
        if ".pdf" in url.lower():
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Mozilla/5.0 (X11; Linux x86_64)"
            })
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                return resp.read()
        return None

    def _try_extract_from_html(self, url: str) -> bytes | None:
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"
        })
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        pdf_links = re.findall(r'href="([^"]*\.pdf[^"]*)"', html, re.IGNORECASE)
        for plink in pdf_links:
            if plink.startswith("//"):
                plink = "https:" + plink
            elif plink.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(url)
                plink = f"{parsed.scheme}://{parsed.netloc}{plink}"
            elif not plink.startswith("http"):
                plink = url.rstrip("/") + "/" + plink.lstrip("/")

            pdf_req = urllib.request.Request(plink, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"
            })
            with urllib.request.urlopen(pdf_req, timeout=30, context=ctx) as pdf_resp:
                data = pdf_resp.read()
                if len(data) > 10000:
                    return data
        return None

    def _try_arxiv_pdf(self, url: str) -> bytes | None:
        m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d+\.\d+)", url)
        if m:
            pdf_url = f"https://arxiv.org/pdf/{m.group(1)}.pdf"
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request(pdf_url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"
            })
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                return resp.read()
        return None

    def extract_pages(self, pdf_path: Path) -> list:
        try:
            import pdfplumber
        except ImportError:
            print("  pdfplumber not installed, trying PyMuPDF...")
            return self._extract_pages_fitz(pdf_path)

        pages = []
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    pages.append({"page_num": i + 1, "text": text.strip(), "word_count": len(text.split())})
        except Exception as e:
            print(f"  pdfplumber failed: {e}, trying PyMuPDF...")
            return self._extract_pages_fitz(pdf_path)
        return pages

    def _extract_pages_fitz(self, pdf_path: Path) -> list:
        try:
            import fitz
        except ImportError:
            print("  PyMuPDF not available either")
            return []

        pages = []
        try:
            doc = fitz.open(str(pdf_path))
            for i in range(len(doc)):
                text = doc[i].get_text()
                pages.append({"page_num": i + 1, "text": text.strip(), "word_count": len(text.split())})
            doc.close()
        except Exception as e:
            print(f"  PyMuPDF failed: {e}")
        return pages

    def is_book(self, pages: list) -> bool:
        return len(pages) > 50

    def analyze_page(self, page_num: int, text: str, total_pages: int, is_book_mode: bool = False) -> dict:
        truncated = text[:1500]
        mode_hint = "(BOOK CHAPTER)" if is_book_mode else "(ACADEMIC PAPER PAGE)"

        prompt = (
            f"You are analyzing {mode_hint} {page_num}/{total_pages}\n\n"
            f"---CONTENT START---\n{truncated}\n---CONTENT END---\n\n"
            f"Extract as JSON (valid, no trailing commas):\n"
            f"{{\n"
            f'  "section": "which section? Abstract/Intro/Methods/Results/Discussion/Conclusion/Other or Chapter N: Title for books",\n'
            f'  "key_points": ["point 1", "point 2"],\n'
            f'  "writing_techniques": {{\n'
            f'    "sentence_openings": ["example phrase"],\n'
            f'    "transitions": ["transition used"],\n'
            f'    "argument_style": "how arguments presented"\n'
            f"  }},\n"
            f'  "citations": ["Smith et al. 2020" or "[1]" or null],\n'
            f'  "methodology_note": "any method mentioned or null",\n'
            f'  "key_finding": "main finding on this page or null"\n'
            f"}}"
        )

        raw = self._ollama_call(prompt, max_tokens=512)
        try:
            first_brace = raw.find("{")
            last_brace = raw.rfind("}")
            if first_brace >= 0 and last_brace > first_brace:
                parsed = json.loads(raw[first_brace:last_brace + 1])
            else:
                parsed = {}
        except json.JSONDecodeError:
            parsed = {}

        return {
            "page_num": page_num,
            "section": parsed.get("section", "unknown"),
            "key_points": parsed.get("key_points", [])[:3],
            "writing_techniques": parsed.get("writing_techniques", {}),
            "citations": parsed.get("citations", []),
            "methodology_note": parsed.get("methodology_note"),
            "key_finding": parsed.get("key_finding"),
            "raw_ollama": raw[:200],
        }

    def analyze_chapter(self, chapter_num: int, chapter_title: str, text: str, total_chapters: int) -> dict:
        truncated = text[:2000]
        prompt = (
            f"You are analyzing BOOK CHAPTER {chapter_num}/{total_chapters}: {chapter_title}\n\n"
            f"---CHAPTER CONTENT---\n{truncated}\n---END---\n\n"
            f"Extract as JSON:\n"
            f"{{\n"
            f'  "purpose": "what this chapter aims to do",\n'
            f'  "main_arguments": ["arg1", "arg2"],\n'
            f'  "writing_style": "how the chapter is written",\n'
            f'  "key_takeaways": ["takeaway 1"],\n'
            f'  "citation_pattern": "how sources are cited in this chapter"\n'
            f"}}"
        )

        raw = self._ollama_call(prompt, max_tokens=512)
        try:
            first_brace = raw.find("{")
            last_brace = raw.rfind("}")
            if first_brace >= 0 and last_brace > first_brace:
                parsed = json.loads(raw[first_brace:last_brace + 1])
            else:
                parsed = {}
        except json.JSONDecodeError:
            parsed = {}

        return {
            "chapter_num": chapter_num,
            "chapter_title": chapter_title,
            "purpose": parsed.get("purpose", ""),
            "main_arguments": parsed.get("main_arguments", [])[:3],
            "writing_style": parsed.get("writing_style", ""),
            "key_takeaways": parsed.get("key_takeaways", [])[:3],
            "citation_pattern": parsed.get("citation_pattern", ""),
        }

    def detect_sections(self, page_analyses: list) -> list:
        sections = []
        current_section = None
        current_pages = []

        for pa in page_analyses:
            sec = pa["section"] if pa["section"] != "unknown" else "Body"
            if current_section is None:
                current_section = sec
                current_pages = [pa["page_num"]]
            elif sec != current_section:
                sections.append({
                    "section_name": current_section,
                    "page_start": current_pages[0],
                    "page_end": current_pages[-1],
                    "page_count": len(current_pages),
                })
                current_section = sec
                current_pages = [pa["page_num"]]
            else:
                current_pages.append(pa["page_num"])

        if current_section and current_pages:
            sections.append({
                "section_name": current_section,
                "page_start": current_pages[0],
                "page_end": current_pages[-1],
                "page_count": len(current_pages),
            })

        return sections

    def extract_global_writing_patterns(self, page_analyses: list) -> dict:
        all_openings = []
        all_transitions = []
        citation_styles_seen = set()
        argument_style = None

        for pa in page_analyses:
            wt = pa.get("writing_techniques", {}) or {}
            if isinstance(wt, dict):
                for o in wt.get("sentence_openings", []):
                    if isinstance(o, str) and len(o) > 5:
                        all_openings.append(o)
                for t in wt.get("transitions", []):
                    if isinstance(t, str) and len(t) > 3:
                        all_transitions.append(t)
                if wt.get("argument_style") and len(str(wt.get("argument_style", ""))) > 5:
                    argument_style = wt["argument_style"]

            citations = pa.get("citations", [])
            if citations and isinstance(citations, list):
                for c in citations:
                    if isinstance(c, str):
                        if re.search(r"\[\d+\]", c):
                            citation_styles_seen.add("vancouver/ieee")
                        elif re.search(r"\(\w+,\s*\d{4}", c):
                            citation_styles_seen.add("apa")
                        elif re.search(r"\w+\s*\(\d{4}\)", c):
                            citation_styles_seen.add("harvard")

        return {
            "sentence_openings": list(set(all_openings))[:10],
            "transitions": list(set(all_transitions))[:10],
            "argument_style": argument_style,
            "citation_styles": list(citation_styles_seen) or ["unknown"],
        }

    def read_paper(self, url_hash: str, title: str, url: str, category: str) -> dict | None:
        print(f"\n  📖 Reading: {title[:80]}")
        t0 = time.time()

        pdf_path = self.download_pdf(url, title)
        if pdf_path is None:
            print(f"  ⚠ Could not download PDF, skipping")
            self.conn.execute(
                "INSERT OR REPLACE INTO processed_pdfs "
                "(source_url_hash, source_url, title, category, download_success, error_message, processed_at) "
                "VALUES (?, ?, ?, ?, 0, 'download_failed', ?)",
                (url_hash, url, title, category, datetime.now().isoformat())
            )
            self.conn.commit()
            return None

        pages = self.extract_pages(pdf_path)
        if not pages:
            print(f"  ⚠ Could not extract text from PDF")
            pdf_path.unlink(missing_ok=True)
            return None

        total_pages = len(pages)
        print(f"  Pages: {total_pages}")
        book_mode = self.is_book(pages)
        if book_mode:
            print(f"  📚 Detected as BOOK ({total_pages} pages) — reading by chapters")

        page_analyses = []

        if book_mode:
            keywords_for_chapters = [
                "introduction", "background", "literature", "review",
                "methodology", "method", "approach", "results", "findings",
                "discussion", "conclusion", "summary", "chapter",
                "appendix", "references", "bibliography", "index"
            ]
            pages_per_chapter = max(1, total_pages // 15)
            chapter_num = 0
            for i in range(0, total_pages, pages_per_chapter):
                chunk_pages = pages[i:i + pages_per_chapter]
                chapter_num += 1
                combined_text = "\n".join(p["text"] for p in chunk_pages if p["text"])
                if not combined_text.strip():
                    continue
                first_page_text = chunk_pages[0]["text"][:100].lower()
                chapter_title = "Chapter"
                for kw in keywords_for_chapters:
                    if kw in first_page_text:
                        chapter_title = kw.title()
                        break
                analysis = self.analyze_chapter(
                    chapter_num, chapter_title, combined_text,
                    min(15, total_pages // pages_per_chapter + 1)
                )
                page_analyses.append({
                    "page_num": chunk_pages[0]["page_num"],
                    "section": f"Chapter {chapter_num}: {chapter_title}",
                    "key_points": analysis.get("key_takeaways", []),
                    "writing_techniques": {
                        "sentence_openings": [],
                        "transitions": [],
                        "argument_style": analysis.get("writing_style", ""),
                    },
                    "citations": [analysis.get("citation_pattern", "")] if analysis.get("citation_pattern") else [],
                    "key_finding": str(analysis.get("purpose", "")),
                    "chapter_analysis": analysis,
                })
                print(f"    Analyzed chapter {chapter_num}: {chapter_title} ({len(chunk_pages)} pages)")
        else:
            pages_per_batch = max(1, total_pages // 3)
            for i in range(0, total_pages, pages_per_batch):
                batch = pages[i:i + pages_per_batch]
                for p in batch:
                    if not p["text"].strip():
                        continue
                    analysis = self.analyze_page(p["page_num"], p["text"], total_pages, book_mode=False)
                    page_analyses.append(analysis)
                    if (p["page_num"] - 1) % max(1, total_pages // 5) == 0 or p["page_num"] == total_pages:
                        print(f"    Page {p['page_num']}/{total_pages}: {analysis.get('section', '?')}")

        sections = self.detect_sections(page_analyses)
        patterns = self.extract_global_writing_patterns(page_analyses)
        sections_filtered = [s for s in sections if s["section_name"].lower() not in ("references", "bibliography", "appendix", "body")]
        if not sections_filtered:
            sections_filtered = sections

        knowledge_count = 0
        for pa in page_analyses:
            for kp in pa.get("key_points", []):
                if isinstance(kp, str) and len(kp) > 10:
                    self.conn.execute(
                        "INSERT INTO extracted_knowledge (source_url_hash, knowledge_type, content, confidence, page_reference) "
                        "VALUES (?, 'key_finding', ?, 'high', ?)",
                        (url_hash, kp[:500], pa["page_num"])
                    )
                    knowledge_count += 1
            finding = pa.get("key_finding")
            if finding and isinstance(finding, str) and len(finding) > 10 and "null" not in finding.lower():
                self.conn.execute(
                    "INSERT INTO extracted_knowledge (source_url_hash, knowledge_type, content, confidence, page_reference) "
                    "VALUES (?, 'page_finding', ?, 'medium', ?)",
                    (url_hash, finding[:500], pa["page_num"])
                )
                knowledge_count += 1

        pattern_count = 0
        for opening in patterns.get("sentence_openings", []):
            self.conn.execute(
                "INSERT INTO writing_patterns (source_url_hash, category, pattern_text, context_note) "
                "VALUES (?, 'sentence_opening', ?, 'observed from deep reading')",
                (url_hash, opening[:300])
            )
            pattern_count += 1
        for transition in patterns.get("transitions", []):
            self.conn.execute(
                "INSERT INTO writing_patterns (source_url_hash, category, pattern_text, context_note) "
                "VALUES (?, 'transition', ?, 'observed from deep reading')",
                (url_hash, transition[:300])
            )
            pattern_count += 1
        if patterns.get("argument_style"):
            self.conn.execute(
                "INSERT INTO writing_patterns (source_url_hash, category, pattern_text, context_note) "
                "VALUES (?, 'argument_style', ?, 'observed from deep reading')",
                (url_hash, str(patterns["argument_style"])[:300])
            )
            pattern_count += 1

        for style_name in patterns.get("citation_styles", []):
            self.conn.execute(
                "INSERT INTO citation_patterns (source_url_hash, citation_style, placement, example_text) "
                "VALUES (?, ?, 'various', 'observed from deep reading')",
                (url_hash, style_name)
            )

        for sec in sections_filtered:
            self.conn.execute(
                "INSERT INTO paper_structures (source_url_hash, section_name, page_start, page_end, word_count) "
                "VALUES (?, ?, ?, ?, 0)",
                (url_hash, sec["section_name"][:100], sec["page_start"], sec["page_end"])
            )

        self.conn.execute(
            "INSERT OR REPLACE INTO processed_pdfs "
            "(source_url_hash, source_url, title, category, download_success, total_pages, total_sections, patterns_extracted, knowledge_facts, processed_at, pdf_size_bytes) "
            "VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)",
            (url_hash, url, title[:200], category[:100],
             total_pages, len(sections_filtered), pattern_count, knowledge_count,
             datetime.now().isoformat(), pdf_path.stat().st_size if pdf_path.exists() else 0)
        )
        self.conn.commit()

        pdf_path.unlink(missing_ok=True)
        elapsed = time.time() - t0
        self.total_reading_time += elapsed

        result = {
            "title": title[:80],
            "url": url,
            "category": category,
            "pages": total_pages,
            "sections": [s["section_name"] for s in sections_filtered],
            "patterns_found": pattern_count,
            "knowledge_facts": knowledge_count,
            "citation_styles": patterns.get("citation_styles", []),
            "duration_seconds": round(elapsed, 1),
            "is_book": book_mode,
        }
        self.reading_results.append(result)
        print(f"  ✅ Read: {result['duration_seconds']}s, {knowledge_count} facts, {pattern_count} patterns")
        return result

    def get_summary(self) -> dict:
        try:
            cur = self.conn.execute("SELECT COUNT(*) as c FROM processed_pdfs WHERE download_success=1")
            total_read = cur.fetchone()["c"]
            cur = self.conn.execute("SELECT COUNT(*) as c FROM writing_patterns")
            total_patterns = cur.fetchone()["c"]
            cur = self.conn.execute("SELECT COUNT(*) as c FROM extracted_knowledge")
            total_knowledge = cur.fetchone()["c"]
            cur = self.conn.execute("SELECT COUNT(*) as c FROM processed_pdfs WHERE download_success=0")
            total_failed = cur.fetchone()["c"]
        except Exception:
            total_read = total_patterns = total_knowledge = total_failed = 0

        return {
            "papers_read_today": len(self.reading_results),
            "total_papers_read_ever": total_read,
            "total_patterns": total_patterns,
            "total_knowledge_facts": total_knowledge,
            "total_download_failures": total_failed,
            "reading_time_seconds": round(self.total_reading_time, 1),
            "results": self.reading_results,
        }

    def format_notification(self, summary: dict) -> str:
        lines = []
        lines.append("🧠 DAILY DEEP READING REPORT")
        lines.append(f"📅 {datetime.now().strftime('%Y-%m-%d')}")
        lines.append("")

        read_today = summary.get("papers_read_today", 0)
        if read_today == 0:
            lines.append("📭 No papers were read today (none pending or all processed).")
            lines.append("")
            lines.append("📊 Brain Status:")
            lines.append(f"  Total deeply read: {summary.get('total_papers_read_ever', 0)}")
            lines.append(f"  Writing patterns: {summary.get('total_patterns', 0)}")
            lines.append(f"  Knowledge facts: {summary.get('total_knowledge_facts', 0)}")
            return "\n".join(lines)

        lines.append(f"📖 Papers Read Today: {read_today}")
        lines.append("")

        for i, result in enumerate(self.reading_results, 1):
            lines.append(f"─── {i}. {result.get('title', 'Untitled')} ───")
            lines.append(f"  Category: {result.get('category', 'General')}")
            lines.append(f"  Pages: {result.get('pages', '?')}")
            sections = result.get("sections", [])
            if sections:
                lines.append(f"  Structure: {' → '.join(sections[:6])}")
            lines.append(f"  Patterns extracted: {result.get('patterns_found', 0)}")
            lines.append(f"  Knowledge facts: {result.get('knowledge_facts', 0)}")
            url = result.get("url", "")
            if url:
                lines.append(f"  Link: {url}")
            if result.get("is_book"):
                lines.append("  (Read as book — chapter-level analysis)")
            lines.append("")

        lines.append("─── Brain Status ───")
        lines.append(f"  Total deeply read papers: {summary.get('total_papers_read_ever', 0)}")
        lines.append(f"  Writing patterns learned: {summary.get('total_patterns', 0)}")
        lines.append(f"  Knowledge facts extracted: {summary.get('total_knowledge_facts', 0)}")
        lines.append(f"  Download failures: {summary.get('total_download_failures', 0)}")
        lines.append("")
        lines.append("Tomorrow: 3 more papers will be read and learned.")

        return "\n".join(lines)

    def send_telegram(self, message: str):
        token = TELEGRAM_BOT_TOKEN
        if not token:
            print("  TELEGRAM_BOT_TOKEN not set, skipping notification")
            return

        def _send_chunk(text):
            data = urllib.parse.urlencode({
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": "false",
            }).encode()
            try:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                urllib.request.urlopen(url, data=data, timeout=15)
                print("  Telegram notification sent")
            except Exception as e:
                print(f"  Telegram send failed: {e}")

        if len(message) > MAX_TELEGRAM_LEN:
            max_lines = message[:MAX_TELEGRAM_LEN].count("\n")
            parts = message.split("\n")
            chunks = []
            current = ""
            for line in parts:
                if len(current) + len(line) + 1 > MAX_TELEGRAM_LEN:
                    chunks.append(current)
                    current = line
                else:
                    current += "\n" + line if current else line
            if current:
                chunks.append(current)
            for chunk in chunks:
                _send_chunk(chunk)
        else:
            _send_chunk(message)

    def run(self) -> dict:
        if not self._ollama_ready():
            return {"error": f"Ollama model '{MODEL_NAME}' not available"}

        t0 = time.time()
        candidates = self.get_candidates()
        if not candidates:
            print("  No unprocessed high-relevance papers found in brain")
            return {"note": "no_candidates", "duration": 0}

        print(f"  Found {len(candidates)} unprocessed papers to read")
        attempted = 0
        succeeded = 0
        failed = 0
        total_pages = 0

        for c in candidates:
            attempted += 1
            result = self.read_paper(
                c["result_hash"], c["title"], c["url"], c.get("category", "General")
            )
            if result:
                succeeded += 1
                total_pages += result.get("pages", 0)
            else:
                failed += 1

        duration = time.time() - t0
        self.conn.execute(
            "INSERT INTO deep_reading_runs "
            "(run_date, papers_attempted, papers_succeeded, papers_failed, total_pages_read, patterns_learned, knowledge_facts, duration_seconds) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), attempted, succeeded, failed,
             total_pages, self.stats.get("patterns", 0), self.stats.get("knowledge", 0), duration)
        )
        self.conn.commit()
        return self.get_summary()

    def close(self):
        self.conn.close()


def generate_report(reader: DeepReader) -> str:
    sep = "=" * 72
    sub = "-" * 72
    now = datetime.now()
    summary = reader.get_summary()

    lines = []
    lines.append(sep)
    lines.append("  DEEP READING BRAIN REPORT")
    lines.append(f"  {now.strftime('%Y-%m-%d %H:%M:%S')} ({now.strftime('%A')})")
    lines.append(sep)
    lines.append("")

    if summary.get("papers_read_today", 0) == 0:
        lines.append("  No papers were read today (all processed or none pending).")
    else:
        lines.append(sub)
        lines.append("  TODAY'S READING")
        lines.append(sub)
        lines.append(f"  Papers read: {summary['papers_read_today']}")
        lines.append(f"  Duration: {summary.get('reading_time_seconds', 0):.0f}s")
        lines.append("")

        for i, r in enumerate(reader.reading_results, 1):
            lines.append(f"  [{i}] {r.get('title', 'Untitled')}")
            lines.append(f"      Category: {r.get('category', 'General')}")
            lines.append(f"      Pages: {r.get('pages', '?')}")
            lines.append(f"      Structure: {' → '.join(r.get('sections', [])[:6])}")
            lines.append(f"      Patterns: {r.get('patterns_found', 0)}")
            lines.append(f"      Facts: {r.get('knowledge_facts', 0)}")
            lines.append(f"      Time: {r.get('duration_seconds', 0):.0f}s")
            lines.append(f"      URL: {r.get('url', '')}")
            lines.append("")

    lines.append(sub)
    lines.append("  BRAIN KNOWLEDGE (Lifetime)")
    lines.append(sub)
    lines.append(f"  Total deeply read papers: {summary.get('total_papers_read_ever', 0)}")
    lines.append(f"  Writing patterns stored:  {summary.get('total_patterns', 0)}")
    lines.append(f"  Knowledge facts stored:   {summary.get('total_knowledge_facts', 0)}")
    lines.append(f"  Download failures:        {summary.get('total_download_failures', 0)}")
    lines.append("")
    lines.append(sub)
    lines.append("  READY. The brain grows smarter every day.")
    lines.append(sub)

    return "\n".join(lines)


def cli():
    global MODEL_NAME
    import argparse
    parser = argparse.ArgumentParser(description="Deep PDF Reader & Knowledge Extractor")
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "qwen2.5vl:3b"),
                        help="Ollama model name")
    parser.add_argument("--max-papers", type=int, default=3,
                        help="Maximum number of papers to read (default: 3)")
    parser.add_argument("--notify", action="store_true",
                        help="Send Telegram notification after reading")
    parser.add_argument("--stats", action="store_true",
                        help="Show deep reading stats and exit")
    parser.add_argument("--report", action="store_true",
                        help="Generate deep reading report")
    parser.add_argument("--report-path", default="deep_report.md",
                        help="Path for deep reading report")
    args = parser.parse_args()

    MODEL_NAME = args.model

    if args.stats:
        conn = sqlite3.connect(str(DEEP_DB))
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute("SELECT COUNT(*) as c FROM processed_pdfs WHERE download_success=1")
            total = cur.fetchone()["c"]
            cur = conn.execute("SELECT COUNT(*) as c FROM writing_patterns")
            patterns = cur.fetchone()["c"]
            cur = conn.execute("SELECT COUNT(*) as c FROM extracted_knowledge")
            knowledge = cur.fetchone()["c"]
            cur = conn.execute("SELECT COUNT(*) as c FROM deep_reading_runs")
            runs = cur.fetchone()["c"]
            cur = conn.execute("SELECT run_date, papers_succeeded, papers_failed FROM deep_reading_runs ORDER BY id DESC LIMIT 5")
            recent = [dict(r) for r in cur.fetchall()]
            conn.close()
            print(json.dumps({
                "total_deeply_read": total,
                "total_patterns": patterns,
                "total_knowledge_facts": knowledge,
                "total_runs": runs,
                "recent_runs": recent,
            }, indent=2))
        except sqlite3.OperationalError:
            conn.close()
            print(json.dumps({"note": "No deep reading data yet"}, indent=2))
        return

    reader = DeepReader(max_papers=args.max_papers)
    summary = reader.run()

    if args.report:
        report_text = generate_report(reader)
        Path(args.report_path).write_text(report_text, encoding="utf-8")
        print(f"\nDeep reading report written to: {args.report_path}")

    report_text = generate_report(reader)
    print("\n" + report_text)

    if args.notify:
        msg = reader.format_notification(summary)
        reader.send_telegram(msg)

    reader.close()

    if summary.get("papers_read_today", 0) > 0:
        print(f"\n  Read {summary['papers_read_today']} papers deeply today.")
    print(f"  Duration: {summary.get('reading_time_seconds', 0):.0f}s")


if __name__ == "__main__":
    cli()
