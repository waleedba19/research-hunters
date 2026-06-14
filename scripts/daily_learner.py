#!/usr/bin/env python3
"""
scripts/daily_learner.py — Autonomous Daily Academic Learning System v1.0
========================================================================
Searches for new academic papers across rotating topics, reads with Ollama,
stores everything in proof_memory.db. Never repeats explored topics.

Usage: python scripts/daily_learner.py [--new-only] [--topics N] [--model NAME]
       --new-only   Only search topics not yet in DB
       --topics N   Number of topics per run (default: 5)
       --model NAME Ollama model name (default: qwen2.5vl:3b)
"""

import hashlib, json, os, re, sqlite3, sys, time, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

SCRIPTS_DIR = Path(__file__).parent
PROOF_DB = SCRIPTS_DIR / "proof_memory.db"
OLLAMA_URL = "http://127.0.0.1:11434"
MODEL_NAME = None

TOPIC_POOL = [
    {"category": "Computer Science / AI", "queries": [
        "deep learning in healthcare diagnostic systems systematic review",
        "reinforcement learning applications robotics autonomous systems",
        "transformer architecture advances natural language processing",
        "explainable AI interpretable machine learning models survey",
        "federated learning privacy preserving distributed training",
    ]},
    {"category": "Medicine & Health Sciences", "queries": [
        "personalized medicine genomic biomarkers precision therapy",
        "AI assisted diagnosis medical imaging radiology pathology",
        "neurodegenerative disease early detection Alzheimer's biomarker",
        "cancer immunotherapy CAR-T cell novel treatments",
        "telemedicine digital health remote patient monitoring outcomes",
    ]},
    {"category": "Climate & Environmental Science", "queries": [
        "climate change adaptation strategies coastal communities",
        "renewable energy transition solar wind grid integration",
        "carbon capture utilization storage CCUS technologies review",
        "biodiversity conservation ecosystem restoration 21st century",
        "sustainable agriculture climate resilient food systems",
    ]},
    {"category": "Neuroscience & Psychology", "queries": [
        "brain computer interface neural decoding motor control",
        "neuroplasticity learning memory synaptic plasticity mechanisms",
        "cognitive behavioral therapy digital mental health interventions",
        "sleep neuroscience memory consolidation glymphatic system",
        "social neuroscience empathy theory mind brain networks",
    ]},
    {"category": "Education & EdTech", "queries": [
        "AI powered adaptive learning personalized education outcomes",
        "learning analytics student success prediction dropout prevention",
        "virtual augmented reality in stem education engagement",
        "gamification in higher education motivation learning outcomes",
        "online vs blended learning effectiveness post-pandemic meta-analysis",
    ]},
    {"category": "Engineering & Robotics", "queries": [
        "soft robotics bioinspired actuators medical applications",
        "autonomous drone swarms coordination disaster response",
        "additive manufacturing 3D printing advanced materials",
        "human robot collaboration industrial cobot safety",
        "nanotechnology drug delivery targeted therapy nanoparticles",
    ]},
    {"category": "Social Sciences", "queries": [
        "social media polarization echo chambers misinformation spread",
        "artificial intelligence labor market automation employment effects",
        "urban inequality smart cities inclusive development",
        "migration refugee integration host community dynamics",
        "digital democracy civic engagement online participation",
    ]},
    {"category": "Biology & Life Sciences", "queries": [
        "CRISPR gene editing therapeutic applications beyond oncology",
        "synthetic biology engineered organisms bioproduction",
        "microbiome gut brain axis human health disease",
        "single cell sequencing transcriptomics cellular heterogeneity",
        "protein structure prediction AlphaFold drug discovery impact",
    ]},
    {"category": "Business & Economics", "queries": [
        "blockchain decentralized finance DeFi smart contract risk",
        "sustainable finance ESG investing climate risk disclosure",
        "digital transformation industry 4.0 manufacturing value chains",
        "gig economy platform work labor rights algorithmic management",
        "behavioral economics nudge theory policy intervention effectiveness",
    ]},
    {"category": "Physics & Astronomy", "queries": [
        "quantum computing error correction near term applications",
        "gravitational wave astronomy multi messenger astrophysics",
        "dark matter direct detection WIMP alternative candidates",
        "exoplanet atmosphere characterization JWST biosignatures",
        "fusion energy magnetic confinement tokamak progress",
    ]},
    {"category": "Chemistry & Materials", "queries": [
        "perovskite solar cells efficiency stability commercial pathways",
        "battery technology solid state lithium sulfur next generation",
        "metal organic frameworks MOF gas storage separation",
        "polymer recycling biodegradable circular economy plastics",
        "catalysis green hydrogen production water splitting",
    ]},
    {"category": "Public Health & Epidemiology", "queries": [
        "pandemic preparedness early warning systems global health security",
        "vaccine hesitancy determinants communication strategies interventions",
        "antimicrobial resistance AMR new antibiotics alternative therapies",
        "health equity social determinants disparities marginalized populations",
        "non communicable diseases prevention lifestyle digital interventions",
    ]},
    {"category": "Data Science & Statistics", "queries": [
        "causal inference machine learning observational studies methods",
        "graph neural networks molecular property prediction drug discovery",
        "time series forecasting deep learning financial economic applications",
        "Bayesian deep learning uncertainty quantification reliable predictions",
        "differential privacy synthetic data generation privacy utility tradeoff",
    ]},
    {"category": "Law & Political Science", "queries": [
        "AI regulation governance framework ethical guidelines comparative",
        "international climate law Paris Agreement implementation effectiveness",
        "digital privacy data protection GDPR impact compliance",
        "electoral integrity voting technology cybersecurity democracy",
        "human rights artificial intelligence facial recognition bias",
    ]},
    {"category": "Linguistics & Communication", "queries": [
        "large language models natural language understanding reasoning",
        "multilingual NLP cross lingual transfer low resource languages",
        "discourse analysis political communication social media framing",
        "second language acquisition technology assisted learning mobile",
        "computational sociolinguistics dialect variation social meaning",
    ]},
    {"category": "History & Archaeology", "queries": [
        "digital humanities computational methods text analysis archives",
        "ancient DNA aDNA human migration population history",
        "archaeological remote sensing LiDAR satellite imagery settlement",
        "climate history paleoclimate reconstruction societal collapse",
        "industrial revolution technological innovation economic transformation",
    ]},
    {"category": "Philosophy & Ethics", "queries": [
        "AI ethics fairness accountability transparency algorithmic decision making",
        "machine consciousness phenomenal consciousness theories",
        "neuroethics brain enhancement cognitive liberty neurotechnology",
        "environmental ethics climate justice intergenerational obligations",
        "research integrity reproducibility open science reform",
    ]},
    {"category": "Psychology & Behavioral Science", "queries": [
        "decision making heuristics biases real world contexts",
        "positive psychology well-being interventions flourishing measurement",
        "developmental psychology adolescence digital media identity",
        "clinical psychology trauma PTSD resilience evidence based treatment",
        "cross cultural psychology values behavior cultural variation",
    ]},
]


class DailyLearner:
    def __init__(self, new_only: bool = True, topics_per_run: int = 5):
        self.new_only = new_only
        self.topics_per_run = topics_per_run
        self.conn = sqlite3.connect(str(PROOF_DB))
        self.conn.row_factory = sqlite3.Row
        self._init_db()
        self.stats = defaultdict(int)

    def _init_db(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS daily_learn_topics (
                topic_hash TEXT PRIMARY KEY,
                category TEXT,
                query_text TEXT,
                first_searched TEXT,
                last_searched TEXT,
                search_count INTEGER DEFAULT 1,
                total_results_found INTEGER DEFAULT 0,
                new_results_found INTEGER DEFAULT 0,
                fully_explored INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS daily_learn_results (
                result_hash TEXT PRIMARY KEY,
                topic_hash TEXT,
                title TEXT,
                url TEXT,
                snippet TEXT,
                ollama_assessment TEXT,
                relevance_score TEXT,
                first_seen TEXT,
                last_seen TEXT,
                visit_count INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS daily_learn_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date TEXT,
                topics_attempted INTEGER,
                topics_skipped INTEGER,
                results_found INTEGER,
                new_results INTEGER,
                remembered_results INTEGER,
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

    def _ollama_assess(self, title: str, snippet: str) -> tuple:
        try:
            prompt = (
                f"Title: {title}\nSnippet: {snippet}\n\n"
                "Rate this academic source for relevance (high/medium/low) "
                "in one word. Then explain why in one sentence."
            )
            req = urllib.request.Request(
                f"{OLLAMA_URL}/api/generate",
                data=json.dumps({
                    "model": MODEL_NAME, "prompt": prompt,
                    "stream": False, "options": {"num_predict": 80}
                }).encode(),
                headers={"Content-Type": "application/json"}
            )
            resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
            text = resp.get("response", "").strip()
            score = "unknown"
            for s in ["high", "medium", "low"]:
                if s in text.lower():
                    score = s
                    break
            return text[:300], score
        except Exception:
            return "assessment_failed", "unknown"

    def _search_ddg(self, query: str, max_results: int = 10) -> list:
        results = []
        try:
            post_data = urllib.parse.urlencode({"q": query}).encode()
            req = urllib.request.Request(
                "https://html.duckduckgo.com/html/", data=post_data,
                headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            for m in re.finditer(
                r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                html, re.DOTALL
            ):
                url = m.group(1)
                title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                if title and url:
                    results.append({"title": title[:200], "url": url[:500], "snippet": ""})
                    if len(results) >= max_results:
                        break

            snippets = re.findall(
                r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL
            )
            for i, s in enumerate(snippets):
                if i < len(results):
                    results[i]["snippet"] = re.sub(r"<[^>]+>", "", s).strip()[:300]

        except Exception:
            pass
        return results

    def _get_todays_topics(self) -> list:
        today = datetime.now(timezone.utc)
        day_of_year = today.timetuple().tm_yday

        flat_topics = []
        for cat in TOPIC_POOL:
            for q in cat["queries"]:
                flat_topics.append({"category": cat["category"], "query": q})

        if self.new_only:
            existing = set()
            try:
                rows = self.conn.execute(
                    "SELECT topic_hash FROM daily_learn_topics WHERE fully_explored = 1"
                ).fetchall()
                for r in rows:
                    h = hashlib.sha256(r[0].encode()).hexdigest()
                    existing.add(h)
            except Exception:
                pass

            unseen = [t for t in flat_topics
                      if hashlib.sha256(t["query"].encode()).hexdigest()[:16] not in existing]
        else:
            unseen = flat_topics

        if not unseen:
            unseen = flat_topics

        selected = []
        for i in range(self.topics_per_run):
            idx = (day_of_year + i * 7) % len(unseen)
            selected.append(unseen[idx])

        return selected

    def run(self) -> dict:
        if not self._ollama_ready():
            return {"error": f"Ollama model '{MODEL_NAME}' not available"}
        t0 = time.time()
        topics = self._get_todays_topics()
        total_new = 0
        total_rem = 0
        topics_attempted = 0
        topics_skipped = 0

        for topic in topics:
            qhash = hashlib.sha256(topic["query"].encode()).hexdigest()[:16]

            old_count = self.conn.execute(
                "SELECT COUNT(*) as c FROM daily_learn_results WHERE topic_hash = ?",
                (qhash,)
            ).fetchone()["c"]

            if old_count >= 5 and self.new_only:
                topics_skipped += 1
                continue

            topics_attempted += 1
            results = self._search_ddg(topic["query"], max_results=8)

            new_count = 0
            for r in results:
                rhash = hashlib.sha256(r["url"].encode()).hexdigest()[:16]
                existing = self.conn.execute(
                    "SELECT visit_count FROM daily_learn_results WHERE result_hash = ?",
                    (rhash,)
                ).fetchone()

                if existing:
                    self.conn.execute(
                        "UPDATE daily_learn_results SET last_seen = ?, visit_count = visit_count + 1 WHERE result_hash = ?",
                        (datetime.now().isoformat(), rhash)
                    )
                    total_rem += 1
                else:
                    assessment, score = self._ollama_assess(r["title"], r["snippet"])
                    self.conn.execute(
                        "INSERT OR REPLACE INTO daily_learn_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                        (rhash, qhash, r["title"], r["url"], r["snippet"],
                         assessment, score, datetime.now().isoformat(), datetime.now().isoformat())
                    )
                    new_count += 1
                    total_new += 1

            self.conn.execute("""
                INSERT OR REPLACE INTO daily_learn_topics
                (topic_hash, category, query_text, first_searched, last_searched,
                 search_count, total_results_found, new_results_found, fully_explored)
                VALUES (?, ?, ?, COALESCE((SELECT first_searched FROM daily_learn_topics WHERE topic_hash = ?), ?), ?,
                        COALESCE((SELECT search_count FROM daily_learn_topics WHERE topic_hash = ?), 0) + 1,
                        COALESCE((SELECT total_results_found FROM daily_learn_topics WHERE topic_hash = ?), 0) + ?,
                        COALESCE((SELECT new_results_found FROM daily_learn_topics WHERE topic_hash = ?), 0) + ?,
                        ?)
            """, (
                qhash, topic["category"], topic["query"],
                qhash, datetime.now().isoformat(), datetime.now().isoformat(),
                qhash, len(results),
                qhash, new_count,
                1 if len(results) == 0 else 0
            ))
            self.conn.commit()

        self.conn.execute(
            "INSERT INTO daily_learn_runs (run_date, topics_attempted, topics_skipped, results_found, new_results, remembered_results, duration_seconds) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), topics_attempted, topics_skipped,
             total_new + total_rem, total_new, total_rem, time.time() - t0)
        )
        self.conn.commit()
        self.conn.close()

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "topics_attempted": topics_attempted,
            "topics_skipped": topics_skipped,
            "new_results_stored": total_new,
            "remembered_updated": total_rem,
            "total_in_brain": self.stats.get("total_in_brain", 0),
            "duration_seconds": round(time.time() - t0, 1),
            "model": MODEL_NAME,
        }


def cli():
    global MODEL_NAME
    import argparse
    parser = argparse.ArgumentParser(description="Daily Academic Learner")
    parser.add_argument("--new-only", action="store_true", default=True,
                        help="Only search topics not yet in brain DB")
    parser.add_argument("--topics", type=int, default=5,
                        help="Number of topics per run (default: 5)")
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "qwen2.5vl:3b"),
                        help="Ollama model name")
    parser.add_argument("--stats", action="store_true",
                        help="Print brain stats and exit")
    args = parser.parse_args()
    MODEL_NAME = args.model

    if args.stats:
        conn = sqlite3.connect(str(PROOF_DB))
        cur = conn.execute("SELECT COUNT(*) as c FROM daily_learn_results")
        total = cur.fetchone()[0]
        cur = conn.execute("SELECT COUNT(*) as c FROM daily_learn_topics")
        topics = cur.fetchone()[0]
        cur = conn.execute("SELECT COUNT(*) as c FROM daily_learn_runs")
        runs = cur.fetchone()[0]
        cur = conn.execute("SELECT run_date, topics_attempted, new_results FROM daily_learn_runs ORDER BY id DESC LIMIT 5")
        recent = [dict(r) for r in cur.fetchall()]
        conn.close()
        print(json.dumps({
            "total_results_in_brain": total,
            "total_topics_searched": topics,
            "total_runs": runs,
            "recent_runs": recent,
        }, indent=2))
        return

    learner = DailyLearner(new_only=args.new_only, topics_per_run=args.topics)
    report = learner.run()
    print(json.dumps(report, indent=2))

    if report.get("new_results_stored", 0) > 0:
        print(f"\n  Learned {report['new_results_stored']} new academic sources today.")
    if report.get("remembered_updated", 0) > 0:
        print(f"  Updated {report['remembered_updated']} previously seen sources.")
    print(f"  Duration: {report.get('duration_seconds', 0):.0f}s")


if __name__ == "__main__":
    cli()
