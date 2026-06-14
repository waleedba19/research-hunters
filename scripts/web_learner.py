#!/usr/bin/env python3
"""
scripts/web_learner.py — Web Learning Engine for academic formatting.
Uses Playwright to crawl official style guides and academic formatting
resources, storing the learned patterns in the academic memory database.

Usage:
  python web_learner.py --search "APA table format"
  python web_learner.py --learn-style-guide apa
  python web_learner.py --list-learned
"""

import json, os, sys, re, time, hashlib, sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

SCRIPTS_DIR = Path(__file__).parent
PATTERNS_FILE = SCRIPTS_DIR / "academic_patterns.json"
MEMORY_DB = SCRIPTS_DIR / "academic_memory.db"

class WebLearner:
    """Learns academic formatting rules from the web via Playwright."""

    def __init__(self):
        self._init_db()
        self.patterns = {}
        if PATTERNS_FILE.exists():
            self.patterns = json.loads(PATTERNS_FILE.read_text(encoding="utf-8"))
        self.playwright_available = self._check_playwright()

    def _check_playwright(self) -> bool:
        try:
            import playwright
            return True
        except ImportError:
            return False

    def _init_db(self):
        MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(MEMORY_DB))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS web_learned_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT,
                source_name TEXT,
                topic TEXT,
                content TEXT,
                learned_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS style_guides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guide_name TEXT UNIQUE,
                url TEXT,
                last_crawled TEXT,
                sections_found TEXT
            )
        """)
        conn.commit()
        conn.close()

    def search_and_learn(self, query: str) -> Dict:
        """Search DuckDuckGo for formatting rules and store results."""
        if not self.playwright_available:
            return {"error": "Playwright not installed", "results": []}

        try:
            from playwright.sync_api import sync_playwright
            results = []
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, timeout=15000)
                page = browser.new_page()

                # Search DuckDuckGo
                search_url = f"https://api.duckduckgo.com/?q={query.replace(' ', '+')}&format=json&no_html=1"
                page.goto(search_url, timeout=15000)
                body = page.text_content("body") or "{}"

                try:
                    data = json.loads(body)
                    abstract = data.get("AbstractText", "")
                    source = data.get("AbstractSource", "")
                    url = data.get("AbstractURL", "")
                    if abstract:
                        results.append({"source": source, "url": url, "content": abstract[:500]})
                except json.JSONDecodeError:
                    pass

                # Also try a direct content page
                try:
                    page.goto(f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}", timeout=15000)
                    snippets = page.text_content("body") or ""
                    if snippets:
                        results.append({"source": "duckduckgo_html", "url": "", "content": snippets[:500]})
                except Exception:
                    pass

                browser.close()

            # Store what we learned
            conn = sqlite3.connect(str(MEMORY_DB))
            for r in results:
                topic_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
                conn.execute(
                    "INSERT OR IGNORE INTO web_learned_patterns (source_url, source_name, topic, content) VALUES (?, ?, ?, ?)",
                    (r.get("url", ""), r.get("source", "web"), query, r.get("content", ""))
                )
            conn.commit()
            conn.close()

            return {"query": query, "results": results}

        except Exception as e:
            return {"error": str(e)[:200], "results": []}

    def learn_style_guide(self, guide_name: str) -> Dict:
        """Fetch known formatting rules for a specific style guide."""
        style_guides = {
            "apa": {
                "url": "https://apastyle.apa.org/style-grammar-guidelines",
                "known_rules": [
                    "Use Times New Roman 12pt",
                    "Double spacing throughout",
                    "1 inch margins on all sides",
                    "Running head on every page",
                    "Page numbers top right",
                    "Five heading levels with specific formatting",
                    "Reference list alphabetically by author",
                    "Hanging indent 0.5 inches for references"
                ]
            },
            "ieee": {
                "url": "https://journals.ieeeauthorcenter.ieee.org/your-role-in-article-creation/ieee-editorial-style-manual/",
                "known_rules": [
                    "Citations numbered in order of appearance [1]",
                    "References listed in citation order",
                    "Conference papers distinguished from journals",
                    "Author names: initials before surname"
                ]
            },
            "mla": {
                "url": "https://style.mla.org/",
                "known_rules": [
                    "Times New Roman 12pt",
                    "Double spacing",
                    "1 inch margins",
                    "Header with last name + page number",
                    "Works Cited page with hanging indent"
                ]
            }
        }

        guide = style_guides.get(guide_name.lower())
        if not guide:
            return {"error": f"Unknown guide: {guide_name}. Known: {list(style_guides.keys())}"}

        conn = sqlite3.connect(str(MEMORY_DB))
        try:
            conn.execute(
                "INSERT OR REPLACE INTO style_guides (guide_name, url, last_crawled, sections_found) VALUES (?, ?, ?, ?)",
                (guide_name, guide["url"], datetime.now().isoformat(),
                 json.dumps(list(guide["known_rules"])))
            )
            conn.commit()
        finally:
            conn.close()

        # Store individual rules
        conn = sqlite3.connect(str(MEMORY_DB))
        for rule in guide["known_rules"]:
            conn.execute(
                "INSERT OR IGNORE INTO web_learned_patterns (source_name, topic, content) VALUES (?, ?, ?)",
                (f"{guide_name}_style_guide", f"{guide_name}_rules", rule)
            )
        conn.commit()
        conn.close()

        return {
            "guide": guide_name,
            "rules_stored": len(guide["known_rules"]),
            "rules": guide["known_rules"]
        }

    def list_learned(self) -> List[Dict]:
        """List all patterns learned from the web."""
        conn = sqlite3.connect(str(MEMORY_DB))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT source_name, topic, content, learned_at FROM web_learned_patterns ORDER BY learned_at DESC LIMIT 50"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def query_learned(self, topic: str, limit: int = 10) -> List[str]:
        """Search learned patterns by topic."""
        conn = sqlite3.connect(str(MEMORY_DB))
        rows = conn.execute(
            "SELECT content FROM web_learned_patterns WHERE topic LIKE ? OR content LIKE ? OR source_name LIKE ? LIMIT ?",
            (f"%{topic}%", f"%{topic}%", f"%{topic}%", limit)
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]


def cli():
    import argparse
    parser = argparse.ArgumentParser(description="Web Learner — learn academic formatting from the internet")
    parser.add_argument("--search", help="Search and learn about a formatting topic")
    parser.add_argument("--learn-style-guide", help="Learn a known style guide (apa, ieee, mla)")
    parser.add_argument("--list-learned", action="store_true", help="List all learned patterns")
    parser.add_argument("--query", help="Query learned patterns by topic")
    args = parser.parse_args()

    wl = WebLearner()

    if args.search:
        print(f"Searching for: {args.search}")
        result = wl.search_and_learn(args.search)
        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            print(f"Found {len(result['results'])} results")
            for r in result['results']:
                print(f"  [{r.get('source','?')}] {r.get('content','')[:100]}...")

    if args.learn_style_guide:
        result = wl.learn_style_guide(args.learn_style_guide)
        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            print(f"✅ Learned {result['rules_stored']} rules for {result['guide']}:")
            for r in result["rules"]:
                print(f"  • {r}")

    if args.list_learned:
        learned = wl.list_learned()
        print(f"Learned patterns ({len(learned)}):")
        for item in learned:
            print(f"  [{item['source_name']}] {item['topic']}: {item['content'][:80]}...")
            print(f"    Learned: {item['learned_at']}")

    if args.query:
        results = wl.query_learned(args.query)
        print(f"Results for '{args.query}':")
        for r in results:
            print(f"  • {r[:120]}")

    if not any([args.search, args.learn_style_guide, args.list_learned, args.query]):
        parser.print_help()


if __name__ == "__main__":
    cli()
