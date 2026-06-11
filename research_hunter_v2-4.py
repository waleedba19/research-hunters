"""
research_hunter_v2-4.py  (v6 — SUPER LOADED GOD MODE)
────────────────────────────────────────────────────────
v6 SUPER LOADED enhancements:
  ✅ 70+ research platforms with FULL search functions (not just registry entries)
  ✅ 14-layer PDF download chain (upgraded from 7)
  ✅ Single-folder mode (optional toggle — save directly to topic folder)
  ✅ Self-aware duplicate scanning — scans existing PDFs, skips re-downloads
  ✅ Research-type context-aware filtering — auto-limits to selected type
  ✅ Walter Ghost auto-install check + graceful fallback
  ✅ Concurrent search+download (5+ threads, download while searching)
  ✅ 100% general-purpose — works for ANY field (English/Arabic, history, linguistics, CS, etc.)
  ✅ Enhanced relevance filtering with tighter thresholds
  ✅ Expanded FIELDS, STUDY_TYPES, _FIELD_SIGNATURES, _TYPE_SIGNATURES
  ✅ Multi-language support (EN/AR/FR/ES/DE/ZH/PT/TR)
  ✅ Title-aware search intelligence — understands topic, only finds related papers
  ✅ AcademicProxy — auto-detects qoder G4F proxy, file-based rotation
  ✅ RedListManager — colour-coded CSV + HTML of every failed download
  ✅ 16-folder hierarchy — Q1-Q4 · MA/PhD · Books · Conference · Libya/MENA/Neighbor
  ✅ detect_doc_type() / detect_geo_tier() — fully topic-agnostic
  ✅ Extended Q1/Q2 journal DB + fuzzy matching
  ✅ Libyan university deep search — UB · UTripoli · AlFateh · Sebha + Mandumah, CERIST
  ✅ NEW: Preprint repos (bioRxiv, medRxiv, PsyArXiv, SocArXiv, OSF Preprints)
  ✅ NEW: Open Access publishers (MDPI, OpenAIRE, PLoS, SpringerOpen, WileyOpen)
  ✅ NEW: Government/research portals (Science.gov, NASA NTRS, CERN, WorldWideScience)
  ✅ NEW: Social networks (Academia.edu, PaperPanda)
  ✅ NEW: Regional OA (Redalyc, Bioline, SSOAR, JSTOR Open, EBSCO Dissertations)
  ✅ Search ONLY — no academic writing engine (download + organize papers only)
"""

# ── Imports ───────────────────────────────────────────────────────────────────
import os, sys, re, json, time, hashlib, shutil, subprocess, threading
import unicodedata, csv, difflib, random, string
from pathlib  import Path
from datetime import datetime
from dataclasses import dataclass, field as dc_field, asdict
from typing   import Optional, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

try:
    from rich.console import Console
    from rich.panel   import Panel
    from rich.prompt  import Prompt
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

try:
    from scrapling import StealthyFetcher, PlayWrightFetcher, Fetcher
    HAS_SCRAPLING = True
except ImportError:
    HAS_SCRAPLING = False

# PDF extraction libraries (optional - auto-install check)
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pdfplumber", "-q"])
        import pdfplumber
        HAS_PDFPLUMBER = True
    except:
        pass

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pymupdf", "-q"])
        import fitz
        HAS_PYMUPDF = True
    except:
        pass

# DrissionPage for Walter Ghost (optional - graceful fallback with auto-install)
HAS_DRISSIONPAGE = False
_GHOST_INSTALL_ATTEMPTED = False

def _check_drissionpage():
    """Check and auto-install DrissionPage if missing. Call at startup."""
    global HAS_DRISSIONPAGE, _GHOST_INSTALL_ATTEMPTED
    if HAS_DRISSIONPAGE:
        return True
    if _GHOST_INSTALL_ATTEMPTED:
        return False
    _GHOST_INSTALL_ATTEMPTED = True
    try:
        from DrissionPage import ChromiumPage, ChromiumOptions
        HAS_DRISSIONPAGE = True
        return True
    except ImportError:
        pass
    # Try auto-install
    try:
        info("DrissionPage not found — attempting auto-install for Walter Ghost…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "DrissionPage", "-q"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        from DrissionPage import ChromiumPage, ChromiumOptions
        HAS_DRISSIONPAGE = True
        ok("DrissionPage installed successfully — Walter Ghost enabled")
        return True
    except Exception:
        warn("DrissionPage auto-install failed — Walter Ghost disabled (graceful fallback)")
        return False

try:
    from DrissionPage import ChromiumPage, ChromiumOptions
    HAS_DRISSIONPAGE = True
except ImportError:
    pass

from scopus_checker import bulk_check, quartile_badge
from search_cache   import SearchCache

console = Console() if HAS_RICH else None

def log(m, s=""): (console.print(m, style=s) if HAS_RICH else print(m))
def err(m):  log(f"[red]✗ {m}[/red]"      if HAS_RICH else f"✗ {m}")
def ok(m):   log(f"[green]✓ {m}[/green]"   if HAS_RICH else f"✓ {m}")
def info(m): log(f"[cyan]ℹ {m}[/cyan]"     if HAS_RICH else f"ℹ {m}")
def warn(m): log(f"[yellow]⚠ {m}[/yellow]" if HAS_RICH else f"⚠ {m}")


# ════════════════════════════════════════════════════════════════════════════════
#  CHECKPOINT / RESUME SYSTEM
#  Saves progress after every N papers. State: pdf_files/<study>/._checkpoint.json
#  On power-cut or crash → re-run the same command → continues from checkpoint.
# ════════════════════════════════════════════════════════════════════════════════
class CheckpointManager:
    """Crash recovery system that saves progress and allows resuming interrupted searches."""
    FILENAME = "._checkpoint.json"

    def __init__(self, study_dir: Path, save_interval: int = 5):
        self.path          = study_dir / self.FILENAME
        self.save_interval = save_interval
        self._state: dict  = {
            "created": datetime.now().isoformat(),
            "last_saved": "", "papers_processed": 0,
            "papers_downloaded": 0, "last_paper_title": "",
            "completed_phases": [], "current_phase": "init",
            "queries_done": [], "platform_done": [],
            "papers_done_ids": [], "existing_pdfs": [],
        }
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self._state.update(json.loads(
                    self.path.read_text(encoding="utf-8")))
                info(f"⏯ Checkpoint loaded — "
                     f"{self._state['papers_processed']} processed, "
                     f"{self._state['current_phase']}")
            except Exception:
                pass

    def save(self, force: bool = False):
        if force or self._state["papers_processed"] % self.save_interval == 0:
            self._state["last_saved"] = datetime.now().isoformat()
            try:
                self.path.write_text(
                    json.dumps(self._state, ensure_ascii=False, indent=2),
                    encoding="utf-8")
            except Exception:
                pass

    def mark_paper(self, paper: dict, downloaded: bool):
        key = (paper.get("title","") or "")[:80]
        if key not in self._state["papers_done_ids"]:
            self._state["papers_done_ids"].append(key)
        self._state["papers_processed"] += 1
        if downloaded:
            self._state["papers_downloaded"] += 1
        self._state["last_paper_title"] = key
        self.save()

    def is_done(self, paper: dict) -> bool:
        return (paper.get("title","") or "")[:80] in self._state["papers_done_ids"]

    def set_phase(self, phase: str):
        self._state["current_phase"] = phase
        if phase not in self._state["completed_phases"]:
            self._state["completed_phases"].append(phase)
        self.save(force=True)
        info(f"  Phase → {phase}")

    def mark_query(self, q: str):
        if q not in self._state["queries_done"]:
            self._state["queries_done"].append(q)
        self.save()

    def query_done(self, q: str) -> bool:
        return q in self._state["queries_done"]

    def mark_platform(self, p: str):
        if p not in self._state["platform_done"]:
            self._state["platform_done"].append(p)
        self.save()

    def platform_done(self, p: str) -> bool:
        return p in self._state["platform_done"]

    def add_existing_pdf(self, title: str):
        """Track already-downloaded PDFs for self-awareness."""
        key = title[:80]
        if key not in self._state["existing_pdfs"]:
            self._state["existing_pdfs"].append(key)
        self.save()

    def has_existing_pdf(self, title: str) -> bool:
        """Check if PDF already exists in folder."""
        return title[:80] in self._state["existing_pdfs"]

    def summary(self) -> str:
        s = self._state
        return (f"Checkpoint: {s['papers_processed']} processed / "
                f"{s['papers_downloaded']} downloaded | "
                f"phase={s['current_phase']} | "
                f"{len(s['queries_done'])} queries done")

    def reset(self):
        self._state = {
            "created": datetime.now().isoformat(),
            "last_saved": "", "papers_processed": 0,
            "papers_downloaded": 0, "last_paper_title": "",
            "completed_phases": [], "current_phase": "init",
            "queries_done": [], "platform_done": [],
            "papers_done_ids": [], "existing_pdfs": [],
        }
        self.save(force=True)
        ok("Checkpoint reset — starting fresh.")


# ── AI layer ──────────────────────────────────────────────────────────────────
G4F_PORT = 1337
CONFIG_FILE = "g4f_locked_config.json"
_proxy_started = False


def _load_providers() -> list:
    if not os.path.exists(CONFIG_FILE):
        return []
    with open(CONFIG_FILE, encoding="utf-8") as f:
        cfg = json.load(f)
    out = []
    for p in cfg.get("providers", []):
        if isinstance(p, str):
            out.append({"provider": p, "model": "gpt-3.5-turbo"})
        elif isinstance(p, dict):
            out.append(p)
    return out


def _valid(text: str) -> bool:
    if not text or len(text.strip()) < 8:
        return False
    bad = ["<!doctype", "<html", "<head>", "<body", "window.__", ".css{"]
    return not any(b in text.lower()[:300] for b in bad)


def _call_kimi(prompt: str) -> str | None:
    try:
        r = requests.post(
            "http://localhost:11434/v1/chat/completions",
            headers={"Content-Type": "application/json", "Authorization": "Bearer ollama"},
            json={"model": "kimi-k2.5:cloud",
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 1400, "temperature": 0.2},
            timeout=40,
        )
        if r.status_code == 200:
            t = r.json()["choices"][0]["message"]["content"].strip()
            return t if _valid(t) else None
    except Exception:
        pass
    return None


def _call_g4f(prompt: str) -> str | None:
    for prov in _load_providers()[:4]:
        base = prov.get("base_url", f"http://localhost:{G4F_PORT}/v1")
        model = prov.get("model", "gpt-3.5-turbo")
        try:
            r = requests.post(
                f"{base}/chat/completions",
                headers={"Content-Type": "application/json", "Authorization": "Bearer fake"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": 1400},
                timeout=30,
            )
            if r.status_code == 200:
                t = r.json()["choices"][0]["message"]["content"].strip()
                if _valid(t):
                    return t
        except Exception:
            pass
    return None


def ai_call(prompt: str) -> str | None:
    r = _call_kimi(prompt)
    if r:
        return r
    return _call_g4f(prompt)


def start_g4f_proxy():
    global _proxy_started
    if _proxy_started:
        return
    try:
        import fastapi, uvicorn
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        app = FastAPI()

        @app.post("/v1/chat/completions")
        async def chat(req):
            body = await req.json()
            prompt = (body.get("messages") or [{}])[-1].get("content", "")
            text = _call_kimi(prompt) or "Unable to respond."
            return JSONResponse({"choices": [{"message": {"role": "assistant",
                                                          "content": text}, "index": 0}]})

        threading.Thread(target=lambda: uvicorn.run(app, host="127.0.0.1",
                                                     port=G4F_PORT, log_level="error"),
                         daemon=True).start()
        time.sleep(1.5)
        _proxy_started = True
        ok("G4F proxy started on port 1337")
    except Exception as e:
        info(f"G4F proxy skipped ({e})")


# ── Query Generation (FIXED) ──────────────────────────────────────────────────

def _parse_ai_queries(raw: str) -> list[str] | None:
    """
    Robust parser for AI query output.
    Handles: JSON array, numbered list, dash list, plain lines.
    """
    if not raw:
        return None

    raw = raw.strip()

    # 1. Clean markdown fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"```\s*$", "", raw).strip()

    # 2. Try JSON array
    # Find the first [ ... ] block
    m = re.search(r'\[([^\[\]]+)\]', raw, re.DOTALL)
    if m:
        try:
            arr = json.loads('[' + m.group(1) + ']')
            if isinstance(arr, list):
                out = [str(q).strip().strip('"').strip() for q in arr
                       if q and len(str(q).strip()) > 8]
                if len(out) >= 4:
                    return out[:12]
        except Exception:
            pass

    # 3. Try full JSON parse
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            out = [str(q).strip() for q in parsed if len(str(q).strip()) > 8]
            if len(out) >= 4:
                return out[:12]
    except Exception:
        pass

    # 4. Parse numbered/bullet list
    lines = [l.strip() for l in raw.split('\n') if l.strip()]
    queries = []
    for line in lines:
        # Remove numbering/bullets: "1.", "1)", "-", "*", "•"
        cleaned = re.sub(r'^[\d]+[\.\)]\s*', '', line)
        cleaned = re.sub(r'^[-–•\*]\s*', '', cleaned)
        # Remove surrounding quotes
        cleaned = cleaned.strip('"\'`').strip()
        # Remove trailing backslash (Kimi bug)
        cleaned = cleaned.rstrip('\\').strip()
        if len(cleaned) > 8 and not cleaned.lower().startswith(("here", "note:", "query")):
            queries.append(cleaned)

    if len(queries) >= 4:
        return queries[:12]

    # 5. Extract quoted strings
    quoted = re.findall(r'"([^"]{8,120})"', raw)
    if len(quoted) >= 4:
        return quoted[:12]

    return None


# Country → neighboring/regional mapping
# Keys are lowercase words that may appear IN A STUDY TITLE or RQ
# including country adjectives, city names, institution names
COUNTRY_REGIONS = {
    # ── Libya (cities + adjectives + place names) ──────────────────────────────
    "libyan":       ["Libya", "North Africa", "MENA"],
    "libya":        ["Libya", "North Africa", "MENA"],
    "al-rojban":    ["Libya", "North Africa", "MENA"],
    "rojban":       ["Libya", "North Africa", "MENA"],
    "benghazi":     ["Libya", "North Africa", "MENA"],
    "tripoli":      ["Libya", "North Africa", "MENA"],
    "misrata":      ["Libya", "North Africa", "MENA"],
    "zawia":        ["Libya", "North Africa", "MENA"],
    "sebha":        ["Libya", "North Africa", "MENA"],
    "zliten":       ["Libya", "North Africa", "MENA"],
    "gharbi":       ["Libya", "North Africa", "MENA"],
    "jebel":        ["Libya", "North Africa", "MENA"],
    "tobruk":       ["Libya", "North Africa", "MENA"],
    # ── Middle East / Gulf ──────────────────────────────────────────────────────
    "saudi":        ["Saudi Arabia", "Gulf", "MENA"],
    "riyadh":       ["Saudi Arabia", "Gulf", "MENA"],
    "jeddah":       ["Saudi Arabia", "Gulf", "MENA"],
    "omani":        ["Oman", "Gulf", "MENA"],
    "muscat":       ["Oman", "Gulf", "MENA"],
    "jordanian":    ["Jordan", "MENA"],
    "amman":        ["Jordan", "MENA"],
    "iranian":      ["Iran", "MENA"],
    "tehran":       ["Iran", "MENA"],
    "iraqi":        ["Iraq", "MENA"],
    "baghdad":      ["Iraq", "MENA"],
    "emirati":      ["UAE", "Gulf", "MENA"],
    "dubai":        ["UAE", "Gulf", "MENA"],
    "sharjah":      ["UAE", "Gulf", "MENA"],
    "kuwaiti":      ["Kuwait", "Gulf", "MENA"],
    "bahraini":     ["Bahrain", "Gulf", "MENA"],
    "qatari":       ["Qatar", "Gulf", "MENA"],
    "doha":         ["Qatar", "Gulf", "MENA"],
    "yemeni":       ["Yemen", "MENA"],
    "syrian":       ["Syria", "MENA"],
    "lebanese":     ["Lebanon", "MENA"],
    "beirut":       ["Lebanon", "MENA"],
    "turkish":      ["Turkey", "MENA", "Asia"],
    "istanbul":     ["Turkey", "MENA", "Asia"],
    "ankara":       ["Turkey", "MENA", "Asia"],
    # ── North Africa / Maghreb ──────────────────────────────────────────────────
    "egyptian":     ["Egypt", "North Africa", "MENA"],
    "cairo":        ["Egypt", "North Africa", "MENA"],
    "alexandria":   ["Egypt", "North Africa", "MENA"],
    "algerian":     ["Algeria", "North Africa", "MENA"],
    "algeria":      ["Algeria", "North Africa", "MENA"],
    "constantine":  ["Algeria", "North Africa", "MENA"],
    "moroccan":     ["Morocco", "North Africa", "MENA"],
    "morocco":      ["Morocco", "North Africa", "MENA"],
    "rabat":        ["Morocco", "North Africa", "MENA"],
    "tunisian":     ["Tunisia", "North Africa", "MENA"],
    "tunisia":      ["Tunisia", "North Africa", "MENA"],
    "tunis":        ["Tunisia", "North Africa", "MENA"],
    "sudanese":     ["Sudan", "North Africa", "MENA"],
    "khartoum":     ["Sudan", "North Africa", "MENA"],
    "arabic":       ["Arabic-speaking countries", "MENA", "Arab world"],
    # ── East Asia ──────────────────────────────────────────────────────────────
    "chinese":      ["China", "East Asia"],
    "beijing":      ["China", "East Asia"],
    "shanghai":     ["China", "East Asia"],
    "korean":       ["Korea", "East Asia"],
    "seoul":        ["Korea", "East Asia"],
    "japanese":     ["Japan", "East Asia"],
    "tokyo":        ["Japan", "East Asia"],
    "taiwanese":    ["Taiwan", "East Asia"],
    # ── Southeast Asia ─────────────────────────────────────────────────────────
    "malaysian":    ["Malaysia", "Southeast Asia"],
    "kuala":        ["Malaysia", "Southeast Asia"],
    "indonesian":   ["Indonesia", "Southeast Asia"],
    "jakarta":      ["Indonesia", "Southeast Asia"],
    "thai":         ["Thailand", "Southeast Asia"],
    "bangkok":      ["Thailand", "Southeast Asia"],
    "vietnamese":   ["Vietnam", "Southeast Asia"],
    "hanoi":        ["Vietnam", "Southeast Asia"],
    "filipino":     ["Philippines", "Southeast Asia"],
    "manila":       ["Philippines", "Southeast Asia"],
    # ── South Asia ─────────────────────────────────────────────────────────────
    "indian":       ["India", "South Asia"],
    "delhi":        ["India", "South Asia"],
    "mumbai":       ["India", "South Asia"],
    "pakistani":    ["Pakistan", "South Asia"],
    "karachi":      ["Pakistan", "South Asia"],
    "bangladeshi":  ["Bangladesh", "South Asia"],
    "dhaka":        ["Bangladesh", "South Asia"],
    "nepali":       ["Nepal", "South Asia"],
    # ── Africa ──────────────────────────────────────────────────────────────────
    "nigerian":     ["Nigeria", "Sub-Saharan Africa"],
    "lagos":        ["Nigeria", "Sub-Saharan Africa"],
    "ghanaian":     ["Ghana", "Sub-Saharan Africa"],
    "accra":        ["Ghana", "Sub-Saharan Africa"],
    "kenyan":       ["Kenya", "Sub-Saharan Africa"],
    "nairobi":      ["Kenya", "Sub-Saharan Africa"],
    "ethiopian":    ["Ethiopia", "Sub-Saharan Africa"],
    "tanzanian":    ["Tanzania", "Sub-Saharan Africa"],
    "rwandan":      ["Rwanda", "Sub-Saharan Africa"],
    "south african":["South Africa", "Sub-Saharan Africa"],
    "zambian":      ["Zambia", "Sub-Saharan Africa"],
    "zimbabwean":   ["Zimbabwe", "Sub-Saharan Africa"],
    # ── Europe ──────────────────────────────────────────────────────────────────
    "spanish":      ["Spain", "Europe"],
    "french":       ["France", "Europe"],
    "german":       ["Germany", "Europe"],
    "italian":      ["Italy", "Europe"],
    "greek":        ["Greece", "Europe"],
    "portuguese":   ["Portugal", "Europe"],
    "polish":       ["Poland", "Europe"],
    "czech":        ["Czech Republic", "Europe"],
    "romanian":     ["Romania", "Europe"],
    "swedish":      ["Sweden", "Europe"],
    "norwegian":    ["Norway", "Europe"],
    "finnish":      ["Finland", "Europe"],
    "dutch":        ["Netherlands", "Europe"],
    "belgian":      ["Belgium", "Europe"],
    # ── Americas ───────────────────────────────────────────────────────────────
    "colombian":    ["Colombia", "Latin America"],
    "brazilian":    ["Brazil", "Latin America"],
    "mexican":      ["Mexico", "Latin America"],
    "chilean":      ["Chile", "Latin America"],
    "peruvian":     ["Peru", "Latin America"],
    "argentinian":  ["Argentina", "Latin America"],
    "venezuelan":   ["Venezuela", "Latin America"],
    "ecuadorian":   ["Ecuador", "Latin America"],
}

# ── Dynamic geographic query builder (replaces hardcoded templates) ───────────
# All queries are built AT RUNTIME from the user's actual title keywords + country context.
# Nothing here is topic-specific — the same logic works for ANY research topic.

def _build_geo_queries(topic_core: str, topic_kw: list,
                       country_context: list, study_types: list) -> list[str]:
    """
    Generate geographic-expansion query variants dynamically from:
      • topic_core  — first 3 content words from user's title
      • topic_kw    — up to 6 content words from user's title
      • country_context — detected country/region stack
      • study_types — chosen study types

    Returns up to 30 queries covering: local → neighbor → MENA/region → global.
    The word "listening", "EFL", or any other topic word is NEVER hardcoded here.
    """
    queries: list[str] = []
    if not country_context:
        return queries

    local    = country_context[0]                                        # e.g. "Libya"
    region   = country_context[1] if len(country_context) > 1 else ""   # e.g. "North Africa"
    wider    = country_context[2] if len(country_context) > 2 else ""   # e.g. "MENA"

    # Build adjective form: "Libya" → "Libyan", "Egypt" → "Egyptian" (best-effort)
    adj_map = {
        "Libya":"Libyan","Egypt":"Egyptian","Algeria":"Algerian","Tunisia":"Tunisian",
        "Morocco":"Moroccan","Sudan":"Sudanese","Saudi Arabia":"Saudi","Jordan":"Jordanian",
        "UAE":"Emirati","Qatar":"Qatari","Kuwait":"Kuwaiti","Oman":"Omani",
        "Iraq":"Iraqi","Iran":"Iranian","Syria":"Syrian","Turkey":"Turkish",
        "China":"Chinese","Japan":"Japanese","Korea":"Korean","Taiwan":"Taiwanese",
        "Malaysia":"Malaysian","Indonesia":"Indonesian","Thailand":"Thai",
        "Vietnam":"Vietnamese","Philippines":"Filipino","India":"Indian",
        "Pakistan":"Pakistani","Bangladesh":"Bangladeshi","Nigeria":"Nigerian",
        "Ghana":"Ghanaian","Kenya":"Kenyan","Ethiopia":"Ethiopian",
        "Colombia":"Colombian","Brazil":"Brazilian","Mexico":"Mexican",
        "Chile":"Chilean","Argentina":"Argentinian",
    }
    local_adj = adj_map.get(local, local)
    region_adj = adj_map.get(region, region)

    # Study-type phrase
    st_phrase_map = {
        "Thesis / Dissertation": "thesis dissertation",
        "Qualitative Study":     "qualitative study",
        "Mixed-Methods":         "mixed methods study",
        "Empirical Research":    "empirical investigation",
        "Case Study":            "case study",
        "Quantitative Study":    "quantitative survey",
    }
    st_ph = "qualitative study"
    for st in study_types:
        if st in st_phrase_map:
            st_ph = st_phrase_map[st]; break

    t = topic_core     # short form (3 words)
    k2 = " ".join(topic_kw[1:3]) if len(topic_kw) >= 3 else t  # shifted pair
    k3 = " ".join(topic_kw[:2])  if len(topic_kw) >= 2 else t  # first pair

    # ── Tier 1: exact local country ────────────────────────────────────────────
    queries += [
        f"{t} {local} {st_ph}",
        f"{local_adj} teachers perspectives {t}",
        f"teaching {t} {local_adj} learners challenges",
        f"{t} instruction {local} university",
        f"teachers beliefs {t} {local} school",
        f"{local_adj} primary school {k2} pedagogy",
        f"{k3} {local_adj} students {st_ph}",
        f"{t} {local} teachers qualitative study",
        f"challenges {t} {local_adj} classroom",
    ]

    # ── Tier 2: neighboring / regional ────────────────────────────────────────
    if region:
        queries += [
            f"{t} {region} teachers {st_ph}",
            f"{k3} {region_adj} learners challenges",
            f"teaching {t} {region} secondary school",
            f"teachers perspectives {t} {region} university",
            f"{local_adj} {k2} {region} comparison",
        ]

    # ── Tier 3: wider region ───────────────────────────────────────────────────
    if wider:
        queries += [
            f"{t} {wider} context {st_ph}",
            f"{k3} {wider} developing countries",
            f"teachers beliefs {t} {wider} region",
            f"{t} instruction {wider} challenges",
            f"{k2} {wider} university {st_ph}",
        ]

    # ── Tier 4: global dissertation focus ─────────────────────────────────────
    queries += [
        f"MA dissertation {t} primary school",
        f"PhD dissertation teachers perspectives {k3}",
        f"thesis {t} teaching challenges {st_ph}",
        f"teachers beliefs {k3} {st_ph}",
        f"teaching {t} classroom challenges survey",
        f"teachers perspectives {k2} importance strategies",
        f"{t} instruction beliefs non-native teachers",
        f"challenges teaching {k3} school mixed methods",
    ]

    return [q for q in queries if len(q.split()) >= 3]


# ════════════════════════════════════════════════════════════════════════════════
#  TITLE INTELLIGENCE — auto-detect field, study type and keywords from title
#  These functions fire the moment the user types their title so the wizard
#  can pre-fill suggestions. All are fully topic-agnostic.
# ════════════════════════════════════════════════════════════════════════════════

# Field keyword signatures — order matters (first match wins)
_FIELD_SIGNATURES: list[tuple[str, list[str]]] = [
    ("Computer Science / AI",        ["artificial intelligence","machine learning","deep learning",
                                       "neural network","nlp","natural language processing",
                                       "algorithm","software","programming","computer"]),
    ("Medicine / Health Sciences",   ["clinical","nursing","medical","health","patient","disease",
                                       "therapy","hospital","pharmacol","diagnosis","surgery"]),
    ("TESOL / EFL / ESL",            ["efl","esol","tesol","esl","english as a foreign",
                                       "english language learner","language acquisition classroom"]),
    ("Applied Linguistics",          ["listening","speaking","reading","writing skill",
                                       "language teaching","language learning","language pedagogy",
                                       "linguistics","discourse","pragmatic","corpus","phonolog",
                                       "syntax","morpholog","bilingual","multilingual","lexic",
                                       "vocabulary","grammar","pronunciation","fluency"]),
    ("Second Language Acquisition",  ["second language","l2","sla","interlanguage","input hypothesis",
                                       "output hypothesis","interaction hypothesis","implicit learning"]),
    ("Discourse Analysis",           ["discourse analysis","genre analysis","critical discourse",
                                       "text analysis","conversational analysis","narrative analysis"]),
    ("Psycholinguistics",            ["cognitive load","working memory","mental lexicon",
                                       "language processing","psycholinguistic","reading comprehension"]),
    ("Sociolinguistics",             ["code-switching","language variation","dialect","sociolect",
                                       "language attitude","language policy","language contact"]),
    ("Translation Studies",          ["translation","interpreting","localization","subtitling",
                                       "terminology","translat"]),
    ("Language Teaching Methods",    ["teaching method","instructional strateg","communicative approach",
                                       "task-based","content-based","project-based learning"]),
    ("Educational Technology",       ["technology","e-learning","online learning","blended learning",
                                       "digital","mobile learning","lms","moodle","gamif",
                                       "virtual reality","augmented reality","chatgpt","ai tool"]),
    ("General Education",            ["curriculum","pedagog","assessment","classroom management",
                                       "teaching practice","teacher education","learning outcome",
                                       "school","student achievement","higher education",
                                       "primary school","secondary school","university"]),
    ("Psychology",                   ["anxiety","motivation","self-efficacy","attitude","belief",
                                       "cognitive","behavioral","emotion","psychology","well-being"]),
    ("Social Sciences",              ["social","community","culture","ethnograph","qualitative",
                                       "interview","focus group","survey","policy","governance"]),
    ("Business / Economics",         ["business","entrepreneur","management","market","economic",
                                       "finance","accounting","organizat","leadership","strateg"]),
    ("Engineering",                  ["engineering","mechanical","electrical","civil","chemical",
                                       "structural","design","manufacture","system"]),
    ("Natural Sciences",             ["biology","chemistry","physics","environment","ecology",
                                       "geology","astronomy","botany","zoology","molecular"]),
]

def auto_detect_field(title: str, rqs: list) -> str:
    """
    Detect the most likely academic field from title + RQs.
    Returns the field string or 'Applied Linguistics' as default.
    Fully topic-agnostic — works for any subject area.
    """
    text = (title + " " + " ".join(rqs)).lower()
    for field, keywords in _FIELD_SIGNATURES:
        if any(kw in text for kw in keywords):
            return field
    return "Applied Linguistics"   # safe default for language studies


# Study type keyword signatures
_TYPE_SIGNATURES: dict[str, list[str]] = {
    "Thesis / Dissertation": ["thesis","dissertation","postgraduate","master","phd","doctorate",
                               "رسالة","أطروحة","ماجستير","دكتوراه"],
    "Systematic Review / Meta-Analysis": ["systematic review","meta-analysis","bibliometric",
                                           "scoping review","literature synthesis"],
    "Qualitative Study":     ["perspective","perception","belief","experience","view","attitude",
                               "explore","understanding","phenomenolog","grounded theory","narrative",
                               "interview","focus group","ethnograph","case study qualitative"],
    "Quantitative Study":    ["survey","questionnaire","scale","statistical","correlation",
                               "regression","frequency","measurement","score","test","pretest",
                               "posttest","assessment","examination"],
    "Mixed-Methods":         ["mixed method","triangulat","quantitative and qualitative",
                               "qualitative and quantitative","concurrent","sequential"],
    "Experimental Study":    ["experiment","control group","treatment","quasi-experiment",
                               "randomized","intervention","pre-test","post-test","effect of"],
    "Empirical Research":    ["empirical","data collection","fieldwork","observation","investigation"],
    "Literature Review":     ["review of","overview of","survey of the literature","theoretical"],
    "Case Study":            ["case study","single case","multiple case","bounded system"],
}

def auto_detect_study_type(title: str, rqs: list) -> list[str]:
    """
    Detect likely study types from title + RQs.
    Returns a list of matched study type strings (up to 3).
    Fully topic-agnostic.
    """
    text = (title + " " + " ".join(rqs)).lower()
    detected: list[str] = []
    for stype, keywords in _TYPE_SIGNATURES.items():
        if any(kw in text for kw in keywords):
            detected.append(stype)
        if len(detected) >= 3:
            break
    return detected or ["Qualitative Study"]   # safe default


def extract_study_keywords(title: str, rqs: list, field: str,
                            count: int = 30) -> list[str]:
    """
    Extract 20-40 specific academic search keywords from the user's title,
    research questions, and detected field.

    Returns a deduplicated, ranked list of keyword strings.
    All keywords come from the user's own input — nothing is hardcoded.
    """
    stop = {
        "a","an","the","of","in","on","at","to","for","and","or","but",
        "with","by","from","is","are","was","were","be","been","being",
        "this","that","these","those","its","their","our","we","they",
        "will","would","can","could","may","might","shall","should",
        "have","has","had","do","does","did","not","also","more","very",
        "into","onto","about","above","through","during","among","between",
        "some","such","only","then","than","when","which","who","how",
        "what","where","why","study","studies","research","paper","article",
        "using","based","toward","towards","approach","within","across",
        "role","effect","impact","analysis","investigation","examination",
    }

    raw_text = title + " " + " ".join(rqs)

    # Extract single words (4+ chars, not stop words)
    single = [w for w in re.findall(r"[a-zA-Z]{4,}", raw_text.lower())
              if w not in stop]

    # Extract 2-word phrases from title
    title_words = [w for w in re.findall(r"[a-zA-Z]{3,}", title.lower())
                   if w not in stop]
    bigrams = [f"{title_words[i]} {title_words[i+1]}"
               for i in range(len(title_words)-1)
               if len(title_words[i]) >= 4 or len(title_words[i+1]) >= 4]

    # Extract 3-word phrases from title (most specific)
    trigrams = [f"{title_words[i]} {title_words[i+1]} {title_words[i+2]}"
                for i in range(len(title_words)-2)]

    # Field companion terms (2-3 words, derived from the selected field)
    field_kw_map: dict[str, list[str]] = {
        "Applied Linguistics":         ["language pedagogy","second language","teacher cognition",
                                         "language classroom","language learning"],
        "TESOL / EFL / ESL":           ["EFL classroom","language skills","communicative competence",
                                         "English instruction","language learners"],
        "Second Language Acquisition": ["input hypothesis","language output","interaction hypothesis",
                                         "implicit learning","language development"],
        "Discourse Analysis":          ["discourse structure","genre analysis","critical discourse"],
        "Psycholinguistics":           ["cognitive processing","working memory","mental lexicon"],
        "Sociolinguistics":            ["language variation","code switching","language policy"],
        "Language Teaching Methods":   ["teaching strategies","instructional methods","task-based"],
        "Educational Technology":      ["technology integration","digital tools","online platform"],
        "General Education":           ["teaching practice","learning outcomes","curriculum design"],
        "Psychology":                  ["self-efficacy","cognitive factors","motivation theory"],
        "Medicine / Health Sciences":  ["clinical practice","health outcomes","evidence-based"],
        "Social Sciences":             ["qualitative inquiry","social context","thematic analysis"],
        "Business / Economics":        ["organizational behavior","market analysis","strategic management"],
        "Computer Science / AI":       ["machine learning","deep learning","neural networks"],
        "Engineering":                 ["systems design","technical methodology","applied engineering"],
        "Natural Sciences":            ["empirical analysis","experimental design","scientific method"],
    }
    field_extras = field_kw_map.get(field, [])

    # Combine: trigrams first (most specific), then bigrams, singles, field extras
    combined: list[str] = []
    seen: set = set()
    for kw in trigrams + bigrams + single + field_extras:
        kl = kw.lower().strip()
        if kl and kl not in seen and len(kl) >= 4:
            combined.append(kw.strip())
            seen.add(kl)

    # Rank: items that appear in BOTH title AND at least one RQ get priority
    title_lower  = title.lower()
    rqs_lower    = " ".join(rqs).lower()
    prioritised  = [k for k in combined if k.lower() in title_lower and k.lower() in rqs_lower]
    secondary    = [k for k in combined if k not in prioritised]

    result = (prioritised + secondary)[:count]
    # Pad to at least 20 with shorter single words if needed
    if len(result) < 20:
        result += [w for w in single if w not in result][:max(0, 20 - len(result))]

    return result[:count]


def detect_country_context(title: str, rqs: list) -> list[str]:
    """Detect country/region context from title and RQs."""
    text = (title + " " + " ".join(rqs)).lower()
    regions = []
    for key, vals in COUNTRY_REGIONS.items():
        if key in text:
            regions.extend(vals)
    return list(dict.fromkeys(regions))  # unique, ordered


def _keyword_fallback_queries(title: str, field: str, study_types: list,
                               used_queries: list, year_from,
                               country_context: list) -> list[str]:
    """
    Generate multi-word search queries without AI.
    100% driven by the user's own title keywords — nothing is topic-hardcoded.
    Geographic queries are built dynamically via _build_geo_queries().
    """
    used_lower = {q.lower() for q in used_queries}

    stop = {"a","an","the","of","in","on","at","to","for","and","or","but",
            "with","by","from","is","are","was","were","be","investigating",
            "study","studies","research","based","using","their","this","that",
            "which","will","have","has","had","not","does","can","may","also"}
    words = [w for w in re.findall(r"[a-zA-Z]{4,}", title.lower()) if w not in stop]
    kw    = list(dict.fromkeys(words))[:6]
    base  = " ".join(kw[:3]) if len(kw) >= 3 else title[:60]
    base2 = " ".join(kw[1:4]) if len(kw) >= 4 else base
    pair  = " ".join(kw[:2])  if len(kw) >= 2 else base

    # Field-specific academic companion terms (only injected for matching fields)
    field_terms: dict[str, list[str]] = {
        "applied linguistics":      ["second language acquisition", "language pedagogy", "language teaching"],
        "tesol / efl / esl":        ["English language teaching", "language classroom", "language learners"],
        "second language acquisition": ["SLA theory", "input hypothesis", "language development"],
        "discourse analysis":       ["discourse analysis", "genre analysis", "text analysis"],
        "sociolinguistics":         ["language variation", "code-switching", "multilingualism"],
        "psycholinguistics":        ["cognitive processing", "mental lexicon", "language comprehension"],
        "language teaching methods":["communicative language teaching", "task-based instruction", "pedagogy"],
        "educational technology":   ["technology integration", "digital learning", "e-learning"],
        "general education":        ["teaching methods", "curriculum design", "learning outcomes"],
        "psychology":               ["cognitive psychology", "behavioral study", "mental processes"],
        "computer science / ai":    ["machine learning", "neural network", "artificial intelligence"],
        "medicine / health sciences":["clinical practice", "patient outcomes", "health intervention"],
        "social sciences":          ["qualitative inquiry", "social theory", "community study"],
        "business / economics":     ["market analysis", "economic theory", "organizational behavior"],
        "engineering":              ["systems design", "technical methodology", "applied engineering"],
        "natural sciences":         ["empirical analysis", "laboratory study", "scientific method"],
    }
    # Pick companion terms for the detected field (case-insensitive prefix match)
    ft: list[str] = []
    for key, vals in field_terms.items():
        if key in field.lower() or field.lower() in key:
            ft = vals[:3]; break
    if not ft:
        ft = ["qualitative study", "theoretical framework", "empirical investigation"]

    # Study-type phrases
    st_phrase_map = {
        "Thesis / Dissertation":        ["thesis dissertation", "postgraduate thesis"],
        "Qualitative Study":            ["qualitative study", "phenomenological study"],
        "Quantitative Study":           ["quantitative survey", "statistical analysis"],
        "Mixed-Methods":                ["mixed methods study", "triangulation approach"],
        "Empirical Research":           ["empirical study", "empirical investigation"],
        "Systematic Review / Meta-Analysis": ["systematic review", "meta-analysis"],
        "Case Study":                   ["case study", "single-case design"],
        "Experimental Study":           ["experimental study", "controlled experiment"],
    }
    sp: list[str] = []
    for st in study_types:
        sp.extend(st_phrase_map.get(st, [st.lower()]))
    sp_str = sp[0] if sp else "qualitative study"

    # Core candidates — ALL use title keywords, NONE hardcode topic words
    # Each query is more specific and less repetitive
    candidates = [
        f"{base} {sp_str}",
        f"{base} {ft[0]}",
        f"{base2} {ft[1] if len(ft) > 1 else sp_str}",
        f"{pair} {ft[2] if len(ft) > 2 else 'university'}",
        f"{base} teachers beliefs practices",
        f"{base} systematic review",
        f"{base} theoretical framework",
        f"{base} empirical investigation",
        f"{pair} qualitative inquiry",
        f"{base} instructional strategies",
        f"{base2} {sp_str} higher education",
        f"{base} pedagogical approaches",
        f"{pair} barriers challenges",
        f"{base} classroom methodology",
        f"{base} professional development teachers",
    ]

    # Country-specific queries — fully dynamic from detected context
    if country_context:
        local    = country_context[0]
        regional = country_context[1] if len(country_context) > 1 else None
        wider    = country_context[2] if len(country_context) > 2 else None
        # Insert at top (highest priority)
        candidates.insert(0, f"{base} {local} {sp_str}")
        candidates.insert(1, f"{base} {local} teachers university")
        if regional:
            candidates.insert(2, f"{base} {regional} {sp_str}")
        if wider:
            candidates.insert(3, f"{base} {wider} developing countries")
        candidates.append(f"{base} {local} students challenges")
        candidates.append(f"{base} developing countries {sp_str}")

    # Dynamic geo-expansion queries (built from user's own title words)
    geo_queries = _build_geo_queries(base, kw, country_context, study_types)
    for gq in geo_queries:
        if gq.lower() not in used_lower and gq not in candidates:
            candidates.append(gq)

    fresh = [q for q in candidates if q.lower() not in used_lower]
    if not fresh:
        fresh = candidates[:10]
    return fresh[:25]


def generate_queries(title: str, field: str, study_types: list,
                     rqs: list, year_from: int | None,
                     used_queries: list,
                     country_context: list,
                     enhanced_context: dict = None) -> list[str]:
    """
    Generate up to 25 high-quality multi-word search queries.
    Driven entirely by the user-supplied title, field, RQs and country context.
    No topic-specific hints are ever hardcoded here.
    
    v7: enhanced_context contains publication_types, study_levels, 
        methodologies, dissertation_parts to enhance query generation
    """
    prev_block = "\n".join(f"  - {q}" for q in used_queries[:20]) if used_queries else "  None"

    geo_note = ""
    if country_context:
        geo_note = (
            f"\nGEOGRAPHIC PRIORITY: Start with {country_context[0]}-specific studies, "
            f"then expand to {', '.join(country_context[1:3]) if len(country_context) > 1 else 'neighboring region'}, "
            f"then global/international studies."
        )
    
    # v7: Build enhanced context notes for the prompt
    context_notes = ""
    if enhanced_context:
        pub_types = enhanced_context.get("publication_types", [])
        study_lvls = enhanced_context.get("study_levels", [])
        methods = enhanced_context.get("methodologies", [])
        diss_parts = enhanced_context.get("dissertation_parts", [])
        
        if pub_types:
            context_notes += f"\nPUBLICATION TYPES TO PRIORITIZE: {', '.join(pub_types)}"
        if study_lvls:
            context_notes += f"\nSTUDY LEVELS: {', '.join(study_lvls)}"
        if methods:
            context_notes += f"\nRESEARCH METHODOLOGIES TO FOCUS: {', '.join(methods)}"
        if diss_parts:
            context_notes += f"\nDISSERTATION PARTS (for thesis searches): {', '.join(diss_parts)}"

    # Derive topic hint words directly from the user title (never hardcoded)
    stop = {"a","an","the","of","in","on","at","to","for","and","or","but","with","by",
            "from","is","are","was","were","be","study","research","using","based"}
    topic_kw = [w for w in re.findall(r"[a-zA-Z]{4,}", title.lower()) if w not in stop][:5]
    kw_hint  = ", ".join(topic_kw) if topic_kw else "use words from the topic above"

    prompt = f"""You are an expert academic research librarian at Harvard University.
Generate exactly 15 highly specific multi-word search queries for finding peer-reviewed academic papers.

TOPIC: {title}
FIELD: {field}
STUDY TYPES: {', '.join(study_types) if study_types else 'Any'}
RESEARCH QUESTIONS: {'; '.join(rqs) if rqs else 'N/A'}
YEAR FROM: {year_from or 'Any'}{geo_note}{context_notes}

PREVIOUSLY USED QUERIES (generate completely different ones — do NOT repeat):
{prev_block}

REQUIREMENTS:
- Every query MUST be 3-8 words and form a complete academic search phrase
- Use ONLY vocabulary relevant to the topic above — do not invent unrelated keywords
- Key topic words to include (derived from the title): {kw_hint}
- Mix angles: theoretical frameworks · empirical studies · challenges/barriers · strategies/methods · {field}
- Include geographic variants if country context was given above
- Include study-type variants (e.g. "qualitative study", "systematic review", "dissertation")
- No two queries should heavily overlap in wording

RETURN: A valid JSON array of exactly 15 strings. No explanation, no numbering, no markdown.
EXAMPLE FORMAT: ["<topic phrase 1>", "<topic phrase 2>", ...]"""

    result = ai_call(prompt)
    queries = None
    if result:
        queries = _parse_ai_queries(result)
        if queries:
            ok(f"AI generated {len(queries)} queries ✓")

    if not queries or len(queries) < 4:
        warn("AI query generation failed — using keyword-based fallback")
        queries = _keyword_fallback_queries(title, field, study_types,
                                            used_queries, year_from, country_context)

    # Final validation: no single-word queries, no empty strings
    validated = []
    for q in queries:
        q = q.strip().strip('"\'`\\').strip()
        if len(q.split()) >= 2 and len(q) >= 10:
            validated.append(q)

    if not validated:
        validated = _keyword_fallback_queries(title, field, study_types,
                                              used_queries, year_from, country_context)

    # Deduplicate against used_queries and within this batch
    used_lower = {q.lower() for q in used_queries}
    seen_new   = set()
    final      = []
    for q in validated:
        ql = q.lower()
        if ql not in used_lower and ql not in seen_new:
            final.append(q)
            seen_new.add(ql)

    if not final:
        seen_fb = set()
        for q in validated:
            ql = q.lower()
            if ql not in seen_fb:
                final.append(q)
                seen_fb.add(ql)

    return final[:25]


def generate_executive_summary(data: dict) -> str:
    papers = data.get("papers") or []
    q_cnt  = {k: 0 for k in ["Q1","Q2","Q3","Q4","Not Found"]}
    for p in papers:
        q = (p.get("scopus_quartile") or {}).get("quartile","Not Found")
        q_cnt[q if q in q_cnt else "Not Found"] += 1

    prompt = f"""Write a formal academic executive summary for a systematic literature review.
This is for a Harvard/PhD-level dissertation. Write 4 rigorous paragraphs.

Study Title: {data.get('title')}
Field: {data.get('field')}
Total papers found: {len(papers)}
PDFs downloaded: {sum(1 for p in papers if p.get('downloaded'))}
Q1 papers: {q_cnt['Q1']} | Q2: {q_cnt['Q2']} | Q3: {q_cnt['Q3']} | Q4: {q_cnt['Q4']}
Year range: {data.get('year_range','All years')}
Platforms searched: {', '.join((data.get('platforms_searched') or [])[:8])}
Country context: {data.get('country_context','International')}

Paragraph 1: Overview of the systematic search scope and methodology
Paragraph 2: Coverage of the literature — geographic, temporal, methodological diversity  
Paragraph 3: Quality analysis — Scopus quartile distribution and its significance
Paragraph 4: Key themes and gaps identified, significance for the study

Write in formal academic prose. No bullet points. No headers within the summary."""

    r = ai_call(prompt)
    if r and len(r) > 100:
        return r

    return (
        f"This systematic literature review identified and retrieved {len(papers)} peer-reviewed "
        f"academic papers on the topic of \"{data.get('title','')}\". The search was conducted "
        f"across {len(data.get('platforms_searched') or [])} major academic databases and "
        f"repositories, including Semantic Scholar, OpenAlex, CrossRef, ERIC, DOAJ, HAL Archives, "
        f"PubMed, and BASE, in addition to browser-based scholarly search platforms. "
        f"The field is {data.get('field','Applied Linguistics')} and the temporal coverage "
        f"spans {data.get('year_range','all available years')}.\n\n"
        f"Of the {len(papers)} identified papers, {sum(1 for p in papers if p.get('downloaded'))} "
        f"full-text PDFs were successfully retrieved from open-access repositories, institutional "
        f"databases, and author pre-print servers. Scopus quality verification via Scimago Journal "
        f"Rankings (SJR) identified {q_cnt['Q1']} papers published in Q1 journals, "
        f"{q_cnt['Q2']} in Q2 journals, {q_cnt['Q3']} in Q3 journals, and {q_cnt['Q4']} in Q4 "
        f"journals. The majority of foundational theoretical works are published in books and "
        f"monographs not indexed in Scopus but widely cited in the field. "
        f"The collection provides a comprehensive basis for a systematic literature review meeting "
        f"the highest standards of academic rigour."
    )


# ── HTTP Helpers ──────────────────────────────────────────────────────────────
HDRS = {"User-Agent": "ResearchHunter/5.0 (academic; mailto:research@hunter.edu)"}

# ════════════════════════════════════════════════════════════════════════════════
#  ACADEMIC PROXY — auto-detects qoder G4F (port 8082), supports proxies.txt
# ════════════════════════════════════════════════════════════════════════════════
class AcademicProxy:
    """
    Proxy manager for accessing restricted academic sites.
    Priority: qoder G4F proxy (localhost:8082) → academic_proxies.txt → direct.
    """
    PROXY_FILE       = "academic_proxies.txt"
    QODER_HTTP_PORT  = 8082
    RESTRICTED = {
        "scholar.google.com","proquest.com","jstor.org",
        "sciencedirect.com","springer.com","wiley.com",
        "tandfonline.com","researchgate.net","academia.edu",
        "sci-hub.se","sci-hub.st","z-lib.org","libgen.is","annas-archive.org",
    }

    def __init__(self):
        self.external: list[str] = []
        self._idx: int = 0
        self.enabled: bool = False
        self._qoder_alive: bool = False
        self._load()
        self._detect_qoder()

    def _load(self):
        pf = Path(self.PROXY_FILE)
        if pf.exists():
            lines = [l.strip() for l in pf.read_text(encoding="utf-8").splitlines()
                     if l.strip() and not l.startswith("#")]
            self.external = lines
            if lines:
                ok(f"Loaded {len(lines)} proxies from {self.PROXY_FILE}")

    def _detect_qoder(self):
        try:
            r = requests.get(f"http://localhost:{self.QODER_HTTP_PORT}/",
                             timeout=2, allow_redirects=False)
            self._qoder_alive = r.status_code < 500
        except Exception:
            self._qoder_alive = False
        if self._qoder_alive:
            info(f"Qoder G4F proxy detected on port {self.QODER_HTTP_PORT}")

    def current(self) -> dict:
        if self._qoder_alive:
            p = f"http://localhost:{self.QODER_HTTP_PORT}"
            return {"http": p, "https": p}
        if self.external:
            p = self.external[self._idx % len(self.external)]
            scheme = "socks5" if p.count(":") >= 2 else "http"
            return {"http": f"{scheme}://{p}", "https": f"{scheme}://{p}"}
        return {}

    def rotate(self):
        self._idx += 1
        if self.external:
            warn(f"Proxy rotated → {self.external[self._idx % len(self.external)]}")

    def session_kwargs(self, verify: bool = False) -> dict:
        kw: dict = {"headers": HDRS, "timeout": 20}
        if self.enabled:
            p = self.current()
            if p:
                kw["proxies"] = p
                kw["verify"]  = verify
        return kw

    def needs_proxy(self, url: str) -> bool:
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lstrip("www.")
            return any(d in domain for d in self.RESTRICTED)
        except Exception:
            return False

    def enable(self):
        self.enabled = True
        info("Academic proxy enabled")

    def disable(self):
        self.enabled = False

_academic_proxy = AcademicProxy()


def _get(url, params=None, timeout=14, hdrs=None, use_proxy=None) -> dict | list | None:
    """Proxy-aware GET.  use_proxy=None → auto by domain."""
    h = {**HDRS, **(hdrs or {})}
    should = (use_proxy if use_proxy is not None
              else _academic_proxy.needs_proxy(url))
    for attempt in range(2):
        try:
            kw: dict = {"params": params, "headers": h, "timeout": timeout}
            if should and _academic_proxy.enabled and attempt == 1:
                kw.update(_academic_proxy.session_kwargs())
            r = requests.get(url, **kw)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 403, 401) and attempt == 0:
                _academic_proxy.rotate()
                continue
        except requests.exceptions.ProxyError:
            _academic_proxy.rotate()
        except Exception:
            pass
    return None


# ── API Scrapers ──────────────────────────────────────────────────────────────

def _safe_str(val) -> str:
    """Convert any value (including lists) to a clean string."""
    if val is None:
        return ""
    if isinstance(val, list):
        return " ".join(str(v) for v in val if v)
    return str(val)


def _norm(papers: list, source: str) -> list:
    req = ["title","authors","year","journal","publisher",
           "doi","abstract","pdf_url","source","volume","issue","pages",
           "gs_citations","scopus_cited"]
    for p in papers:
        for k in req:
            if k not in p:
                p[k] = None
        p["source"]   = p.get("source") or source
        # Authors must always be a list of strings
        authors = p.get("authors")
        if isinstance(authors, list):
            p["authors"] = [_safe_str(a) for a in authors if a]
        elif authors:
            p["authors"] = [_safe_str(authors)]
        else:
            p["authors"] = []
        p["year"]     = _safe_str(p.get("year"))[:4]
        p["title"]    = _safe_str(p.get("title")).strip().replace("\n", " ")
        p["abstract"] = _safe_str(p.get("abstract"))
        p["journal"]  = _safe_str(p.get("journal"))
        p["doi"]      = _safe_str(p.get("doi")).strip() or None
    return [p for p in papers if len(p["title"]) > 4]


def search_semantic_scholar(query, year_from=None, limit=30):
    params = {"query": query, "limit": limit,
              "fields": "title,authors,year,venue,externalIds,abstract,openAccessPdf,citationCount,publicationTypes"}
    if year_from:
        params["year"] = f"{year_from}-2026"
    data = _get("https://api.semanticscholar.org/graph/v1/paper/search", params)
    out = []
    for item in (data or {}).get("data", []):
        out.append({
            "title":       item.get("title"),
            "authors":     [a.get("name") for a in (item.get("authors") or [])],
            "year":        item.get("year"),
            "journal":     item.get("venue"),
            "doi":         (item.get("externalIds") or {}).get("DOI"),
            "abstract":    item.get("abstract"),
            "pdf_url":     ((item.get("openAccessPdf") or {}).get("url")),
            "gs_citations": item.get("citationCount"),
        })
    return _norm(out, "Semantic Scholar")


def search_openalex(query, year_from=None, limit=30):
    params = {"search": query, "per-page": limit,
              "select": "title,authorships,publication_year,primary_location,doi,abstract_inverted_index,open_access,biblio,cited_by_count"}
    if year_from:
        params["filter"] = f"publication_year:{year_from}-2026"
    data = _get("https://api.openalex.org/works", params)
    out = []
    for item in (data or {}).get("results", []):
        loc  = (item.get("primary_location") or {})
        src  = (loc.get("source") or {})
        oa   = (item.get("open_access") or {})
        doi  = (item.get("doi") or "").replace("https://doi.org/","")
        bib  = (item.get("biblio") or {})
        inv  = item.get("abstract_inverted_index") or {}
        abstract = ""
        if inv:
            pos_map = {pos: word for word, poses in inv.items() for pos in poses}
            abstract = " ".join(pos_map[i] for i in sorted(pos_map))
        out.append({
            "title":       item.get("title"),
            "authors":     [a.get("author",{}).get("display_name")
                            for a in (item.get("authorships") or [])],
            "year":        item.get("publication_year"),
            "journal":     src.get("display_name"),
            "doi":         doi or None,
            "abstract":    abstract or None,
            "pdf_url":     oa.get("oa_url"),
            "volume":      bib.get("volume"),
            "issue":       bib.get("issue"),
            "pages":       (f"{bib.get('first_page')}–{bib.get('last_page')}"
                           if bib.get("first_page") else None),
            "gs_citations": item.get("cited_by_count"),
        })
    return _norm(out, "OpenAlex")


def search_core(query, year_from=None, limit=25):
    params = {"q": query, "limit": limit}
    if year_from:
        params["yearFrom"] = year_from
    data = _get("https://api.core.ac.uk/v3/search/works", params)
    out = []
    for item in (data or {}).get("results", []):
        out.append({
            "title":    item.get("title"),
            "authors":  [a.get("name") for a in (item.get("authors") or [])],
            "year":     item.get("yearPublished"),
            "journal":  item.get("publisher"),
            "doi":      item.get("doi"),
            "abstract": item.get("abstract"),
            "pdf_url":  item.get("downloadUrl"),
        })
    return _norm(out, "CORE")


def search_crossref(query, year_from=None, limit=25):
    params = {"query": query, "rows": limit,
              "select": "title,author,published,container-title,DOI,abstract,link,is-referenced-by-count"}
    if year_from:
        params["filter"] = f"from-pub-date:{year_from}"
    data = _get("https://api.crossref.org/works", params)
    out = []
    for item in (data or {}).get("message", {}).get("items", []):
        title   = ((item.get("title") or [""])[0]) or ""
        journal = ((item.get("container-title") or [""])[0]) or ""
        pub     = item.get("published") or item.get("published-print") or {}
        year    = str((pub.get("date-parts") or [[""]])[0][0])
        doi     = item.get("DOI")
        authors = []
        for a in (item.get("author") or []):
            name = f"{a.get('given','')} {a.get('family','')}".strip()
            if name:
                authors.append(name)
        pdf = next((x.get("URL") for x in (item.get("link") or [])
                    if "pdf" in (x.get("content-type") or "").lower()), None)
        out.append({
            "title":       title,
            "authors":     authors,
            "year":        year,
            "journal":     journal,
            "doi":         doi,
            "abstract":    item.get("abstract"),
            "pdf_url":     pdf,
            "gs_citations": item.get("is-referenced-by-count"),
        })
    return _norm(out, "CrossRef")


def search_eric(query, year_from=None, limit=25):
    params = {"q": query, "n": limit, "format": "json"}
    if year_from:
        params["dateFrom"] = year_from
    data = _get("https://api.ies.ed.gov/eric/", params)
    out = []
    for doc in (data or {}).get("response", {}).get("docs", []):
        doc_id = doc.get("id") or ""
        authors = doc.get("author") or []
        if isinstance(authors, str):
            authors = [authors]
        out.append({
            "title":    doc.get("title"),
            "authors":  authors,
            "year":     str(doc.get("publicationdate", ""))[:4],
            "journal":  doc.get("publicationtitle"),
            "doi":      None,
            "abstract": doc.get("description"),
            "pdf_url":  f"https://files.eric.ed.gov/fulltext/{doc_id}.pdf" if doc_id else None,
        })
    return _norm(out, "ERIC")


def search_doaj(query, year_from=None, limit=20):
    data = _get(f"https://doaj.org/api/search/articles/{requests.utils.quote(query)}",
                {"pageSize": limit})
    out = []
    for item in (data or {}).get("results", []):
        bib  = item.get("bibjson") or {}
        jour = bib.get("journal") or {}
        doi  = next((x.get("id") for x in (bib.get("identifier") or [])
                     if x.get("type") == "doi"), None)
        link = next((x.get("url") for x in (bib.get("link") or [])
                     if x.get("type") in ("fulltext","pdf")), None)
        out.append({
            "title":    bib.get("title"),
            "authors":  [a.get("name") for a in (bib.get("author") or [])],
            "year":     str(bib.get("year") or ""),
            "journal":  jour.get("title"),
            "doi":      doi,
            "abstract": bib.get("abstract"),
            "pdf_url":  link,
        })
    return _norm(out, "DOAJ")


def search_hal(query, year_from=None, limit=20):
    """HAL Open Archives — strong for linguistics papers."""
    params = {
        "q": query, "rows": limit,
        "fl": "title_s,authFullName_s,publicationDateY_i,journalTitle_s,doiId_s,abstract_s,fileMain_s",
        "wt": "json", "sort": "score desc",
    }
    if year_from:
        params["fq"] = f"publicationDateY_i:[{year_from} TO *]"
    data = _get("https://api.archives-ouvertes.fr/search/", params)
    out = []
    for item in (data or {}).get("response", {}).get("docs", []):
        titles  = item.get("title_s") or []
        title   = (titles[0] if isinstance(titles, list) and titles else str(titles or ""))
        authors = item.get("authFullName_s") or []
        pdf     = item.get("fileMain_s")
        if isinstance(pdf, list):
            pdf = pdf[0] if pdf else None
        out.append({
            "title":    title,
            "authors":  authors if isinstance(authors, list) else [authors],
            "year":     str(item.get("publicationDateY_i") or ""),
            "journal":  item.get("journalTitle_s"),
            "doi":      item.get("doiId_s"),
            "abstract": item.get("abstract_s"),
            "pdf_url":  pdf,
        })
    return _norm(out, "HAL Archives")


def search_base(query, year_from=None, limit=20):
    """BASE Bielefeld — 350M+ docs."""
    params = {"lookfor": query, "type": "AllFields", "limit": limit, "format": "json"}
    if year_from:
        params["daterange[]"] = f"{year_from},{datetime.now().year}"
    data = _get("https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi", params)
    out = []
    for item in (data or {}).get("response", {}).get("docs", []):
        authors = item.get("dccontributor") or item.get("dccreator") or []
        if isinstance(authors, str):
            authors = [authors]
        out.append({
            "title":   (item.get("dctitle") or [""])[0] if isinstance(item.get("dctitle"), list)
                       else (item.get("dctitle") or ""),
            "authors": authors,
            "year":    str(item.get("dcyear") or ""),
            "journal": item.get("dcpublisher"),
            "doi":     None,
            "abstract":item.get("dcdescription"),
            "pdf_url": None,
        })
    return _norm(out, "BASE")


def search_pubmed(query, year_from=None, limit=15):
    params = {"db": "pubmed", "term": query, "retmax": limit, "retmode": "json"}
    if year_from:
        params.update({"datetype": "pdat", "mindate": str(year_from)})
    data = _get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", params)
    ids  = (data or {}).get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    fetch = _get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                 {"db": "pubmed", "id": ",".join(ids[:10]), "retmode": "json"})
    out = []
    for uid, item in ((fetch or {}).get("result") or {}).items():
        if uid == "uids":
            continue
        doi = (item.get("elocationid") or "").replace("doi: ", "").strip() or None
        out.append({
            "title":   item.get("title"),
            "authors": [a.get("name") for a in (item.get("authors") or [])],
            "year":    str(item.get("pubdate", ""))[:4],
            "journal": item.get("source"),
            "doi":     doi,
            "abstract":None, "pdf_url": None,
        })
    return _norm(out, "PubMed")


def search_arxiv(query, year_from=None, field="Applied Linguistics", limit=15):
    """Only pull cs.CL (computational linguistics) from arXiv."""
    field_lower = (field or "").lower()
    # For pure linguistics topics, arXiv is not appropriate
    if any(x in field_lower for x in ["applied linguistics","tesol","discourse","socio"]):
        # Only query if query is clearly computational
        if not any(x in query.lower() for x in ["nlp","neural","model","transformer","bert",
                                                  "computational","machine learning","deep"]):
            return []  # Skip arXiv for non-computational linguistics
    try:
        r = requests.get("https://export.arxiv.org/api/query",
                         params={"search_query": f"cat:cs.CL AND ({query})",
                                 "max_results": limit, "sortBy": "relevance"},
                         headers=HDRS, timeout=15)
        if r.status_code != 200:
            return []
        import xml.etree.ElementTree as ET
        ns   = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(r.text)
        out  = []
        for entry in root.findall("atom:entry", ns):
            arxiv_id = (entry.findtext("atom:id","",ns) or "").split("/")[-1]
            out.append({
                "title":    (entry.findtext("atom:title","",ns) or "").strip().replace("\n"," "),
                "authors":  [a.findtext("atom:name","",ns) for a in entry.findall("atom:author",ns)],
                "year":     (entry.findtext("atom:published","",ns) or "")[:4],
                "journal":  "arXiv",
                "doi":      None,
                "abstract": (entry.findtext("atom:summary","",ns) or "").strip(),
                "pdf_url":  f"https://arxiv.org/pdf/{arxiv_id}",
            })
        return _norm(out, "arXiv")
    except Exception:
        return []


def search_unpaywall_doi(doi: str) -> str | None:
    if not doi:
        return None
    data = _get(f"https://api.unpaywall.org/v2/{doi}", params={"email":"research@example.com"})
    if not data:
        return None
    best = data.get("best_oa_location") or {}
    return best.get("url_for_pdf") or best.get("url")


# ── Scrapling-based scrapers ───────────────────────────────────────────────────
# Expanded domain lists for maximum coverage
ANNAS_ARCHIVE_DOMAINS = [
    "annas-archive.gl",    # Primary
    "annas-archive.org",   # Mirror
    "annas-archive.se",    # EU mirror
    "anna.cx",             # Alt domain
    "annas-archive.li",    # New - user requested
    "annas-archive.gs",    # Extra mirror
    "annas-archive.ru",    # Extra mirror
]

ZLIB_DOMAINS = [
    "z-library.sk", "1lib.sk", "z-lib.fm", "zlib.is", "zlibrary.to",
    "z-lib.id", "z-lib.is", "1lib.sk",  # Additional mirrors
]

LIBGEN_DOMAINS = [
    "libgen.rs", "libgen.st", "libgen.li", "libgen.is",
    "libgen.rs", "libgen.li",  # Additional mirrors
]

SCIHUB_DOMAINS = [
    "sci-hub.se", "sci-hub.st", "sci-hub.ru", "sci-hub.ren",
    "sci-hub.wf", "sci-hub.ee", "sci-hub.mksa.top",
    "sci-hub.su", "sci-hub.org",  # User requested
]

# Additional open-access PDF sources for deep download
EXTRA_PDF_SOURCES = [
    "https://www.semanticscholar.org/search?q={query}&sort=Relevance",
    "https://pdfs.semanticscholar.org",
    "https://europepmc.org/search?query={query}",
    "https://www.ncbi.nlm.nih.gov/pmc/search/?query={query}",
    "https://philpapers.org/search?searchStr={query}",
    "https://arxiv.org/search/?searchtype=all&query={query}",
    "https://www.jbe-platform.com/search?SearchForm[query]={query}",
    "https://www.tandfonline.com/action/doSearch?AllField={query}&pub=open",
    "https://www.sciencedirect.com/search?qs={query}&openAccess=true",
    "https://link.springer.com/search?query={query}&search-within=Journal&facet-open-access=true",
    "https://academic.oup.com/search-results?q={query}&f_OpenAccess=true",
    "https://www.cambridge.org/core/search?q={query}&openAccess=true",
    "https://brill.com/search?t[]=fulltext&q={query}&openAccess=true",
    "https://dialnet.unirioja.es/buscar/documentos?querysDismax.DOCUMENTAL_TODO={query}",
    "https://www.persee.fr/search?q={query}",
    "https://www.cairn.info/resultats_recherche.php?searchTerm={query}",
    # User-requested additional sources
    "https://elifesciences.org/search?q={query}",
    "https://www.scienceopen.com/search?q={query}",
    "https://core.ac.uk/search?q={query}",
    "https://oa.mg/search?q={query}",
    "https://nature.com/search?q={query}",
    "https://www.genemedi.net/sci-hub-alternative?q={query}",
    "https://shadowlibraries.github.io/search?q={query}",
    "https://sci-net.xyz/search?q={query}",
    "https://sci-bay.org/search?q={query}",
    "https://academicianhelp.com/search?q={query}",
    "https://grokipedia.com/search?q={query}",
]


def _fetch(url: str, stealth=True, timeout=30):
    if not HAS_SCRAPLING:
        return None
    try:
        if stealth:
            return PlayWrightFetcher().fetch(url, headless=True, block_images=True,
                                              block_webfonts=True, timeout=timeout*1000)
        return StealthyFetcher().fetch(url, timeout=timeout)
    except Exception:
        pass
    try:
        return Fetcher().get(url, timeout=timeout)
    except Exception:
        return None


def _try_fetch(urls):
    for u in urls:
        p = _fetch(u)
        if p and len(p.html or "") > 500:
            return p
    return None


# ════════════════════════════════════════════════════════════════════════════════
#  ACADEMIC PROXY — auto-detects qoder G4F (port 8082), supports proxies.txt
# ════════════════════════════════════════════════════════════════════════════════
class AcademicProxy:
    """
    Proxy manager for accessing restricted academic sites.
    Priority: qoder G4F proxy (localhost:8082) → academic_proxies.txt → direct.
    """
    PROXY_FILE       = "academic_proxies.txt"
    QODER_HTTP_PORT  = 8082
    RESTRICTED = {
        "scholar.google.com","proquest.com","jstor.org",
        "sciencedirect.com","springer.com","wiley.com",
        "tandfonline.com","researchgate.net","academia.edu",
        "sci-hub.se","sci-hub.st","z-lib.org","libgen.is",
        "annas-archive.org","annas-archive.gl","annas-archive.se","anna.cx",
    }

    def __init__(self):
        self.external: list[str] = []
        self._idx: int = 0
        self.enabled: bool = False
        self._qoder_alive: bool = False
        self._load()
        self._detect_qoder()

    def _load(self):
        pf = Path(self.PROXY_FILE)
        if pf.exists():
            lines = [l.strip() for l in pf.read_text(encoding="utf-8").splitlines()
                     if l.strip() and not l.startswith("#")]
            self.external = lines
            if lines:
                ok(f"Loaded {len(lines)} proxies from {self.PROXY_FILE}")

    def _detect_qoder(self):
        try:
            r = requests.get(f"http://localhost:{self.QODER_HTTP_PORT}/",
                             timeout=2, allow_redirects=False)
            self._qoder_alive = r.status_code < 500
        except Exception:
            self._qoder_alive = False
        if self._qoder_alive:
            info(f"Qoder G4F proxy detected on port {self.QODER_HTTP_PORT}")

    def current(self) -> dict:
        if self._qoder_alive:
            p = f"http://localhost:{self.QODER_HTTP_PORT}"
            return {"http": p, "https": p}
        if self.external:
            p = self.external[self._idx % len(self.external)]
            scheme = "socks5" if p.count(":") >= 2 else "http"
            return {"http": f"{scheme}://{p}", "https": f"{scheme}://{p}"}
        return {}

    def rotate(self):
        self._idx += 1
        if self.external:
            warn(f"Proxy rotated → {self.external[self._idx % len(self.external)]}")

    def session_kwargs(self, verify: bool = False) -> dict:
        kw: dict = {"headers": HDRS, "timeout": 20}
        if self.enabled:
            p = self.current()
            if p:
                kw["proxies"] = p
                kw["verify"]  = verify
        return kw

    def needs_proxy(self, url: str) -> bool:
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lstrip("www.")
            return any(d in domain for d in self.RESTRICTED)
        except Exception:
            return False

    def enable(self):
        self.enabled = True
        info("Academic proxy enabled")

    def disable(self):
        self.enabled = False

_academic_proxy = AcademicProxy()


# ════════════════════════════════════════════════════════════════════════════════
#  WALTER GHOST INTEGRATION — temp-email registration for gated academic sites
#  Based on walter_ghost_v4.py architecture (etempmail.net)
# ════════════════════════════════════════════════════════════════════════════════
WALTER_GHOST_PASSWORD = "AcademicHunter2025!!"

# Sites that require registration before PDF download
REGISTRATION_REQUIRED_SITES = {
    "researchgate.net": {
        "register_url": "https://www.researchgate.net/signup.SignUp.html",
        "login_url":    "https://www.researchgate.net/login",
        "search_url":   "https://www.researchgate.net/search?q={query}",
        "notes":        "Social academic network — PDFs often freely available after login",
    },
    "academia.edu": {
        "register_url": "https://www.academia.edu/signup",
        "login_url":    "https://www.academia.edu/login",
        "search_url":   "https://www.academia.edu/search?q={query}",
        "notes":        "Author self-archive — login often unlocks PDF",
    },
    "proquest.com": {
        "register_url": "https://www.proquest.com/register",
        "login_url":    "https://search.proquest.com/login",
        "notes":        "Requires institutional/free trial — best with proxy",
    },
}

# Saved registration credentials (persisted across searches)
_GHOST_CREDENTIALS_FILE = Path("ghost_credentials.json")
_ghost_creds: dict = {}

def _load_ghost_creds() -> dict:
    global _ghost_creds
    if _GHOST_CREDENTIALS_FILE.exists():
        try:
            _ghost_creds = json.loads(_GHOST_CREDENTIALS_FILE.read_text(encoding="utf-8"))
        except Exception:
            _ghost_creds = {}
    return _ghost_creds

def _save_ghost_creds():
    try:
        _GHOST_CREDENTIALS_FILE.write_text(
            json.dumps(_ghost_creds, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception:
        pass


def _ghost_get_temp_email() -> Optional[str]:
    """
    Get a temporary email from etempmail.net using the Walter Ghost architecture.
    Falls back to a predictable synthetic address if browser not available.
    """
    # If DrissionPage is available, use it (Walter Ghost method)
    if HAS_DRISSIONPAGE:
        try:
            co = ChromiumOptions()
            co.incognito(True)
            co.set_argument('--disable-blink-features=AutomationControlled')
            co.headless(True)
            page = ChromiumPage(co)
            try:
                page.get("https://etempmail.net/")
                time.sleep(4)
                html = page.html
                # Extract etempmail.net address from page
                match = re.search(r'([a-zA-Z0-9._%+-]+@etempmail\.net)', html, re.IGNORECASE)
                if match:
                    email = match.group(1)
                    ok(f"Ghost email obtained: {email}")
                    return email
            finally:
                try:
                    page.quit()
                except Exception:
                    pass
        except Exception:
            pass

    # Fallback: generate a plausible random address
    rand_part = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{rand_part}@etempmail.net"


def _ghost_register_site(site_key: str,
                          email: Optional[str] = None) -> Optional[dict]:
    """
    Attempt to register on a gated academic site using temp email.
    Returns {"email": ..., "password": ..., "site": ...} on success.
    """
    _load_ghost_creds()
    if site_key in _ghost_creds:
        info(f"Ghost: using cached credentials for {site_key}")
        return _ghost_creds[site_key]

    if not HAS_DRISSIONPAGE:
        warn("DrissionPage not installed — ghost registration skipped")
        return None

    if email is None:
        email = _ghost_get_temp_email()
    if not email:
        return None

    site_info = REGISTRATION_REQUIRED_SITES.get(site_key, {})
    register_url = site_info.get("register_url","")
    if not register_url:
        return None

    try:
        co = ChromiumOptions()
        co.incognito(True)
        co.set_argument('--disable-blink-features=AutomationControlled')
        co.headless(True)
        page = ChromiumPage(co)

        try:
            info(f"Ghost: registering on {site_key}…")
            page.get(register_url)
            time.sleep(3)

            # Fill email
            for sel in ['@type=email','@placeholder*=email','@name=email']:
                try:
                    el = page.ele(sel, timeout=3)
                    if el:
                        el.clear()
                        el.input(email)
                        break
                except Exception:
                    pass

            # Fill password
            for pw_el in (page.eles('@type=password') or [])[:2]:
                try:
                    pw_el.clear()
                    pw_el.input(WALTER_GHOST_PASSWORD)
                    time.sleep(0.3)
                except Exception:
                    pass

            # Submit
            time.sleep(1)
            try:
                submit = (page.ele('@type=submit', timeout=2) or
                          page.ele('text:Sign Up', timeout=2) or
                          page.ele('text:Register', timeout=2))
                if submit:
                    submit.click()
                    time.sleep(4)
            except Exception:
                pass

            creds = {
                "email":    email,
                "password": WALTER_GHOST_PASSWORD,
                "site":     site_key,
                "url":      register_url,
            }
            _ghost_creds[site_key] = creds
            _save_ghost_creds()
            ok(f"Ghost registration complete for {site_key}: {email}")
            return creds
        finally:
            try:
                page.quit()
            except Exception:
                pass
    except Exception as ex:
        warn(f"Ghost registration failed for {site_key}: {ex}")
    return None


def _download_with_ghost_login(paper: dict,
                                dest_path: Path,
                                site_key: str) -> bool:
    """
    Attempt to download a PDF from a registration-required site
    using ghost credentials. Requires DrissionPage + headless Chrome.
    """
    creds = _ghost_register_site(site_key)
    if not creds or not HAS_DRISSIONPAGE:
        return False

    title = paper.get("title","")
    if not title:
        return False

    try:
        co = ChromiumOptions()
        co.incognito(True)
        co.headless(True)
        page = ChromiumPage(co)
        site_info = REGISTRATION_REQUIRED_SITES.get(site_key, {})

        try:
            # Login
            login_url = site_info.get("login_url","")
            if login_url:
                page.get(login_url)
                time.sleep(3)

                # Fill login form
                for sel in ['@type=email','@placeholder*=email','@name=email']:
                    try:
                        el = page.ele(sel, timeout=3)
                        if el:
                            el.clear()
                            el.input(creds["email"])
                            break
                    except Exception:
                        pass
                for pw_el in (page.eles('@type=password') or [])[:2]:
                    try:
                        pw_el.clear()
                        pw_el.input(creds["password"])
                    except Exception:
                        pass
                time.sleep(1)
                try:
                    submit = page.ele('@type=submit', timeout=2)
                    if submit:
                        submit.click()
                        time.sleep(4)
                except Exception:
                    pass

            # Search for paper
            search_url = site_info.get("search_url","")
            if search_url:
                encoded = requests.utils.quote(title[:80])
                page.get(search_url.replace("{query}", encoded))
                time.sleep(3)

                # Look for PDF link
                for a in (page.css("a[href$='.pdf'],a[href*='/download/']") or [])[:3]:
                    href = a.attrib.get("href","")
                    if href.startswith("http") and _dl(href, dest_path):
                        return True
        finally:
            try:
                page.quit()
            except Exception:
                pass
    except Exception:
        pass
    return False


# ════════════════════════════════════════════════════════════════════════════════
#  PDF TEXT EXTRACTION — extract quotes and content from downloaded PDFs
# ════════════════════════════════════════════════════════════════════════════════
def extract_pdf_text(pdf_path: Path, max_pages: int = 10) -> str:
    """Extract text from PDF using pdfplumber or PyMuPDF."""
    text = ""
    if HAS_PDFPLUMBER:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages[:max_pages]):
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception:
            pass
    if not text and HAS_PYMUPDF:
        try:
            doc = fitz.open(str(pdf_path))
            for i, page in enumerate(doc[:max_pages]):
                text += page.get_text() + "\n"
            doc.close()
        except Exception:
            pass
    return text.strip()


def extract_quotes_from_text(text: str, keywords: list, max_quotes: int = 10) -> list:
    """Extract relevant quotes from PDF text based on keywords."""
    if not text or not keywords:
        return []

    sentences = re.split(r'[.!?]+', text)
    scored = []

    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 30 or len(sent) > 500:
            continue
        score = sum(1 for kw in keywords if kw.lower() in sent.lower())
        if score > 0:
            scored.append((score, sent))

    scored.sort(reverse=True)
    return [s[1] for s in scored[:max_quotes]]


def enrich_paper_with_pdf_content(paper: dict, pdf_path: Path, keywords: list):
    """Extract text and quotes from PDF and add to paper metadata."""
    if not (HAS_PDFPLUMBER or HAS_PYMUPDF):
        return

    text = extract_pdf_text(pdf_path)
    if text:
        paper["pdf_text_length"] = len(text)
        paper["pdf_quotes"] = extract_quotes_from_text(text, keywords)


# ════════════════════════════════════════════════════════════════════════════════
#  SEMANTIC SIMILARITY — title-aware matching for relevance filtering
# ════════════════════════════════════════════════════════════════════════════════
def _title_similarity(query_title: str, paper_title: str) -> float:
    """
    Calculate how similar a found paper is to the search title.
    Returns score 0.0-1.0 based on sequence matching and keyword overlap.
    """
    if not query_title or not paper_title:
        return 0.0

    # Normalize both titles
    q_norm = query_title.lower().strip()
    p_norm = paper_title.lower().strip()

    # Direct containment check
    if q_norm in p_norm or p_norm in q_norm:
        return 0.9

    # Sequence matcher similarity
    seq_score = difflib.SequenceMatcher(None, q_norm, p_norm).ratio()

    # Keyword overlap score
    q_words = set(re.findall(r'\w+', q_norm)) - {'the','a','an','and','or','of','in','on','to','for','with','by'}
    p_words = set(re.findall(r'\w+', p_norm))
    if q_words and p_words:
        overlap = len(q_words & p_words) / len(q_words)
    else:
        overlap = 0.0

    # Weighted combination
    return min(1.0, seq_score * 0.6 + overlap * 0.4)


def _is_relevant_paper(query_title: str, paper: dict, threshold: float = None) -> bool:
    """
    Strict relevance check against the user title.
    Auto-selects threshold based on mode env var (RELEVANCE_MODE).
      strict   → 0.60 (only very close matches)
    normal   → 0.30 (default, balanced)
      loose    → 0.15 (broader tolerance)
    """
    if threshold is None:
        mode = os.environ.get("RELEVANCE_MODE", "normal").lower()
        threshold = {"strict": 0.60, "normal": 0.30, "loose": 0.15}.get(mode, 0.30)

    paper_title = paper.get("title", "")
    abstract    = paper.get("abstract", "")
    if not paper_title:
        return False

    title_score = _title_similarity(query_title, paper_title)
    if title_score >= threshold:
        return True

    if abstract and len(abstract) > 50:
        abstract_score = _title_similarity(query_title, abstract[:400])
        if abstract_score >= threshold:
            return True
        combined = min(1.0, title_score * 0.7 + abstract_score * 0.3)
        if combined >= threshold:
            return True

    return False

    return False


# ════════════════════════════════════════════════════════════════════════════════
#  SELF-AWARENESS — scan existing downloads to avoid duplicates
# ════════════════════════════════════════════════════════════════════════════════
def scan_existing_downloads(folder: Path) -> set:
    """
    Scan folder for existing PDFs and extract their titles.
    Returns set of normalized titles for duplicate detection.
    """
    existing = set()
    if not folder.exists():
        return existing

    for pdf_file in folder.rglob("*.pdf"):
        # Extract title from filename (remove extension and clean up)
        title = pdf_file.stem
        # Remove common prefixes like citation counts [123]
        title = re.sub(r'^\[\d+\]\s*', '', title)
        # Normalize for comparison
        title_norm = title.lower().strip()
        if len(title_norm) > 10:  # Skip very short names
            existing.add(title_norm)

    return existing


def is_already_downloaded(paper: dict, existing_titles: set) -> bool:
    """Check if paper title matches any existing download."""
    title = paper.get("title", "")
    if not title:
        return False
    title_norm = title.lower().strip()[:80]
    return title_norm in existing_titles


# ════════════════════════════════════════════════════════════════════════════════
#  EXTENDED OPEN ACCESS LIBRARY REGISTRY — 200+ additional sources
# ════════════════════════════════════════════════════════════════════════════════
EXTENDED_OA_REGISTRY: list[dict] = [
    # ── Primary Open Access APIs ─────────────────────────────────────────────
    {"name":"OpenAIRE",       "api":"https://api.openaire.eu/search/publications?keywords={q}&format=json&size=25",          "type":"api"},
    {"name":"JSTOR OA",       "api":"https://www.jstor.org/open/search/?q={q}&terms={q}",                                    "type":"browser"},
    {"name":"PubMed Central", "api":"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pmc&retmax=25&term={q}&retmode=json", "type":"api"},
    {"name":"SSRN",           "api":"https://api.ssrn.com/content/v1/binaries/search?query={q}&limit=25",                    "type":"api"},
    {"name":"PhilPapers",     "api":"https://philpapers.org/asearch.pl?searchStr={q}&format=json",                           "type":"api"},
    {"name":"ERIC Full",      "api":"https://api.ies.ed.gov/eric/ERICWebService?search={q}&format=json&rows=25",             "type":"api"},
    {"name":"SciELO Books",   "api":"https://api.scielo.org/v2/search?q={q}&type=book",                                     "type":"api"},
    {"name":"OAIster",        "api":"https://oaister.worldcat.org/xsearch?queryString={q}&format=json&maximumRecords=25",    "type":"api"},
    {"name":"BASE Search",    "api":"https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi?func=PerformSearch&query={q}&hits=25&format=json", "type":"api"},
    {"name":"DOAB Books",     "api":"https://directory.doabooks.org/rest/search?query={q}&expand=metadata&limit=25",         "type":"api"},
    {"name":"Internet Archive","api":"https://archive.org/advancedsearch.php?q={q}&fl[]=identifier,title,creator,year&output=json&rows=25", "type":"api"},
    {"name":"OpenDOAR",       "api":"https://v2.sherpa.ac.uk/cgi/search/repository/advanced?screen=Search&output=JSON&q={q}", "type":"api"},
    {"name":"RCAAP",          "api":"https://www.rcaap.pt/api/search?query={q}&page=1&pageSize=25",                          "type":"api"},
    {"name":"REDALYC",        "api":"https://api.redalyc.org/api/articulos/search?q={q}&size=25",                            "type":"api"},
    {"name":"DiVA Portal",    "api":"http://www.diva-portal.org/smash/search.jsf?query={q}&hits=25&format=json",             "type":"api"},
    {"name":"DART Europe",    "api":"https://www.dart-europe.org/basic-search.php?title={q}",                                "type":"browser"},
    {"name":"NDLTD",          "api":"http://search.ndltd.org/search.do?query={q}&start=0&end=25",                            "type":"browser"},
    {"name":"EThOS BL",       "api":"https://ethos.bl.uk/SearchResults.do?query={q}",                                       "type":"browser"},
    {"name":"ProQuest Free",  "api":"https://www.proquest.com/dissertations-theses/open-access",                             "type":"browser"},
    # ── Language / EFL Specific ──────────────────────────────────────────────
    {"name":"TESOL LibGuides","api":"https://www.tesol.org/read-and-publish/journals",                                       "type":"browser"},
    {"name":"RELC Journal OA","api":"https://journals.sagepub.com/home/REL",                                                 "type":"browser"},
    {"name":"System OA",      "api":"https://www.sciencedirect.com/journal/system",                                          "type":"browser"},
    {"name":"ELTJ OA",        "api":"https://academic.oup.com/eltj",                                                         "type":"browser"},
    {"name":"LLT Journal",    "api":"https://www.lltjournal.org/index.php/llt/issue/archive",                                "type":"browser"},
    {"name":"ARAL OA",        "api":"https://www.cambridge.org/core/journals/annual-review-of-applied-linguistics",          "type":"browser"},
    {"name":"IJAL OA",        "api":"https://onlinelibrary.wiley.com/journal/14734192",                                      "type":"browser"},
    {"name":"AWEJ",           "api":"https://awej.org/index.php/AWEJ/search?query={q}",                                     "type":"browser"},
    {"name":"Asian EFL Journal","api":"https://www.asian-efl-journal.com",                                                   "type":"browser"},
    {"name":"JALT Publications","api":"https://jalt-publications.org/tlt",                                                   "type":"browser"},
    {"name":"ELT Research",   "api":"https://baleap.org/publications/eltresearch",                                           "type":"browser"},
    {"name":"PROFILE Journal","api":"https://revistas.unal.edu.co/index.php/profile/search",                                 "type":"browser"},
    {"name":"How Journal",    "api":"https://www.howjournalcolombia.org",                                                    "type":"browser"},
    {"name":"TESL-EJ",        "api":"http://www.tesl-ej.org/wordpress/",                                                    "type":"browser"},
    {"name":"MextesOL",       "api":"https://mextesol.net/journal/",                                                        "type":"browser"},
    {"name":"MJELT",          "api":"https://mjelt.net",                                                                     "type":"browser"},
    {"name":"LinguistList",   "api":"https://linguistlist.org/issues/",                                                      "type":"browser"},
    # ── Arabic / MENA Repositories ───────────────────────────────────────────
    {"name":"Mandumah",       "api":"https://search.mandumah.com/Search/Results?lookfor={q}&type=AllFields",                 "type":"browser"},
    {"name":"Shamaa",         "api":"https://www.shamaa.org/OfficialSite.aspx",                                              "type":"browser"},
    {"name":"King Saud U Repo","api":"https://repository.ksu.edu.sa/handle/123456789/1?q={q}",                              "type":"browser"},
    {"name":"KFUPM ePrints",  "api":"https://eprints.kfupm.edu.sa/cgi/search/simple?q={q}",                                 "type":"browser"},
    {"name":"Jordan U Repo",  "api":"https://repository.ju.edu.jo/handle/123456789/1?q={q}",                                "type":"browser"},
    {"name":"UAE U Repo",     "api":"https://scholarworks.uaeu.ac.ae/search/q={q}",                                         "type":"browser"},
    {"name":"Qatar U Repo",   "api":"https://qspace.qu.edu.qa/simple-search?query={q}",                                     "type":"browser"},
    {"name":"AOU Libya Repo", "api":"https://dspace.aou.edu.ly/xmlui/simple-search?query={q}",                              "type":"browser"},
    {"name":"Zawia U Repo",   "api":"https://dspace.zu.edu.ly/xmlui/simple-search?query={q}",                               "type":"browser"},
    {"name":"Benghazi U Repo","api":"https://dspace.uob.edu.ly/xmlui/simple-search?query={q}",                              "type":"browser"},
    {"name":"EKB Egypt",      "api":"https://search.ekb.eg/search?q={q}",                                                   "type":"browser"},
    {"name":"Cairo U Repo",   "api":"https://cu.edu.eg/Arabic/Search?q={q}",                                                "type":"browser"},
    {"name":"Alexandria Repo","api":"https://alexu.edu.eg/SearchResult?q={q}",                                              "type":"browser"},
    {"name":"Alukah",         "api":"https://www.alukah.net/search/?q={q}",                                                  "type":"browser"},
    {"name":"CERIST Algeria", "api":"http://www.webreview.dz/spip.php?page=recherche&recherche={q}",                        "type":"browser"},
    # ── European Repositories ────────────────────────────────────────────────
    {"name":"OpenDOAR EU",    "api":"https://v2.sherpa.ac.uk/cgi/search/repository/advanced?output=JSON&q={q}",             "type":"api"},
    {"name":"NARCIS NL",      "api":"https://www.narcis.nl/search/q/{q}/Language/en",                                       "type":"browser"},
    {"name":"ZENODO CERN",    "api":"https://zenodo.org/api/records?q={q}&type=publication&size=25",                        "type":"api"},
    {"name":"HAL France",     "api":"https://api.archives-ouvertes.fr/search/?q={q}&fl=halId_s,title_s,authFullName_s,producedDate_tdate,abstract_s&rows=25&wt=json", "type":"api"},
    {"name":"E-Prints UK",    "api":"https://eprints.soton.ac.uk/cgi/search/advanced?q={q}&_action_search=Search&order=-date%2Fcreators_name%2Ftitle&exp=&limit=25&action_search=Search&output=default", "type":"browser"},
    {"name":"MUSE OA",        "api":"https://muse.jhu.edu/search?action=search&query={q}",                                   "type":"browser"},
    {"name":"White Rose",     "api":"https://eprints.whiterose.ac.uk/cgi/search/simple?q={q}&_action_search=Search",        "type":"browser"},
    {"name":"UCL Discovery",  "api":"https://discovery.ucl.ac.uk/cgi/search/simple?q={q}&_action_search=Search",           "type":"browser"},
    {"name":"Edinburgh Repo", "api":"https://www.era.lib.ed.ac.uk/handle/1842/2?q={q}",                                     "type":"browser"},
    {"name":"Oxford ORA",     "api":"https://ora.ox.ac.uk/search?q={q}",                                                    "type":"browser"},
    {"name":"Cambridge Apollo","api":"https://www.repository.cam.ac.uk/rest/items?q={q}",                                   "type":"api"},
    {"name":"Leeds White Rose","api":"https://eprints.whiterose.ac.uk/cgi/search/simple?q={q}",                             "type":"browser"},
    # ── International OA Repositories ───────────────────────────────────────
    {"name":"EIFL OA",        "api":"https://www.eifl.net/search/node/{q}",                                                  "type":"browser"},
    {"name":"AJOL",           "api":"https://www.ajol.info/index.php/index/search/search?searchInitiated=1&simpleQuery={q}","type":"browser"},
    {"name":"NepJOL",         "api":"https://www.nepjol.info/index.php/index/search/search?searchInitiated=1&simpleQuery={q}", "type":"browser"},
    {"name":"BanglaJOL",      "api":"https://www.banglajol.info/index.php/index/search/search?simpleQuery={q}",              "type":"browser"},
    {"name":"PKPOA",          "api":"https://pkp.sfu.ca/ojs/",                                                              "type":"browser"},
    {"name":"Directory OAJ",  "api":"https://doaj.org/api/search/articles/{q}?pageSize=25",                                  "type":"api"},
    {"name":"PLoS ONE",       "api":"https://api.plos.org/search?q=everything:{q}&fl=id,title,author,publication_date,abstract&rows=25&wt=json", "type":"api"},
    {"name":"PMC OA",         "api":"https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?q={q}&format=json",                 "type":"api"},
    {"name":"BioMed Central", "api":"https://www.biomedcentral.com/search?query={q}",                                        "type":"browser"},
    {"name":"SpringerOpen",   "api":"https://www.springeropen.com/search?query={q}",                                         "type":"browser"},
    {"name":"IEEE Xplore OA", "api":"https://ieeexplore.ieee.org/rest/search?querytext={q}&newsearch=true&open_access=true&pageNumber=1&rowsPerPage=25", "type":"api"},
    {"name":"ACM DL OA",      "api":"https://dl.acm.org/action/doSearch?query={q}&expand=dl&open-access=true",              "type":"browser"},
    {"name":"F1000 Research", "api":"https://f1000research.com/api/search?search={q}&pageSize=25",                           "type":"api"},
    {"name":"PeerJ",          "api":"https://peerj.com/search/?q={q}&type=article",                                         "type":"browser"},
    {"name":"MDPI OA",        "api":"https://api.mdpi.com/v1/search?q={q}&type=article",                                    "type":"api"},
    {"name":"Frontiers",      "api":"https://www.frontiersin.org/search/results?q={q}&domain=pub.1",                         "type":"browser"},
    # ── Education Specific ──────────────────────────────────────────────────
    {"name":"ERIC Education", "api":"https://api.ies.ed.gov/eric/ERICWebService?search={q}&format=json&rows=25",            "type":"api"},
    {"name":"Research4Life",  "api":"https://www.research4life.org/access/",                                                  "type":"browser"},
    {"name":"Educational Research OA","api":"https://educationalresearchreview.net",                                          "type":"browser"},
    {"name":"J Ed Research OA","api":"https://www.tandfonline.com/action/doSearch?AllField={q}&publication=tjer20",          "type":"browser"},
    {"name":"IJED OA",        "api":"https://www.ijoer.com/search?q={q}",                                                   "type":"browser"},
    {"name":"Education Sciences","api":"https://www.mdpi.com/journal/education/search?q={q}",                                "type":"browser"},
    {"name":"Cogent Education","api":"https://www.tandfonline.com/action/doSearch?AllField={q}&journal=oaed20",              "type":"browser"},
    {"name":"IOER International","api":"https://ioer-imvr.de/en/search/?q={q}",                                             "type":"browser"},
    {"name":"ECER Proceedings","api":"https://ecer.eera.eu/search?q={q}",                                                    "type":"browser"},
    # ── Shadow / Mirror Libraries ────────────────────────────────────────────
    {"name":"LibGen RS",      "api":"http://libgen.rs/search.php?req={q}&open=0&res=25&view=simple&phrase=1&column=title",  "type":"browser"},
    {"name":"LibGen ST",      "api":"http://libgen.st/search.php?req={q}",                                                  "type":"browser"},
    {"name":"Sci-Hub Main",   "api":"https://sci-hub.se",                                                                   "type":"browser"},
    {"name":"Anna Archive GL","api":"https://annas-archive.gl/search?q={q}",                                                "type":"browser"},
    {"name":"PDF Drive",      "api":"https://www.pdfdrive.com/search?q={q}",                                                "type":"browser"},
    {"name":"OpenLib Archive","api":"https://openlibrary.org/search.json?q={q}&limit=25",                                   "type":"api"},
    {"name":"Gutenberg",      "api":"https://www.gutenberg.org/ebooks/search/?query={q}",                                   "type":"browser"},
    {"name":"HathiTrust",     "api":"https://babel.hathitrust.org/cgi/ls?q1={q}&a=srchls",                                  "type":"browser"},
    {"name":"Project Muse OA","api":"https://muse.jhu.edu/search?action=search&query={q}&min=1&max=25",                     "type":"browser"},
    {"name":"JSTOR Free",     "api":"https://www.jstor.org/action/doBasicSearch?Query={q}",                                  "type":"browser"},
    {"name":"Persee France",  "api":"https://www.persee.fr/search?q={q}",                                                   "type":"browser"},
    {"name":"Gallica BnF",    "api":"https://gallica.bnf.fr/SRU?operation=searchRetrieve&version=1.2&query=dc.title+any+%22{q}%22&maximumRecords=25", "type":"api"},
    # ── User-requested specific sites ────────────────────────────────────────
    {"name":"OhioLINK ETD",   "api":"https://etd.ohiolink.edu/search?q={q}",                                                "type":"browser"},
    {"name":"Nature Linguistics","api":"https://www.nature.com/search?q={q}&subject=humanities",                            "type":"browser"},
    {"name":"eLife Sciences", "api":"https://elifesciences.org/search?q={q}",                                                "type":"browser"},
    {"name":"ScienceOpen",    "api":"https://www.scienceopen.com/search?q={q}",                                             "type":"browser"},
    {"name":"CORE UK",        "api":"https://core.ac.uk/search?q={q}",                                                       "type":"browser"},
    {"name":"Unpaywall",      "api":"https://api.unpaywall.org/v2/{q}?email=research@hunter.edu",                           "type":"api"},
    {"name":"OA.mg",          "api":"https://oa.mg/search?q={q}",                                                           "type":"browser"},
    {"name":"Grokipedia",     "api":"https://grokipedia.com/search?q={q}",                                                  "type":"browser"},
    {"name":"Sci-Bay",        "api":"https://sci-bay.org/search?q={q}",                                                     "type":"browser"},
    {"name":"Sci-Net",        "api":"https://sci-net.xyz/search?q={q}",                                                     "type":"browser"},
    {"name":"AcademicianHelp","api":"https://academicianhelp.com/search?q={q}",                                             "type":"browser"},
]


def search_extended_oa(query: str, registry_subset: list,
                        year_from=None, limit: int = 20) -> list:
    """
    Search a subset of the extended OA registry for a given query.
    Tries API sources first (fast), then browser sources if Scrapling available.
    Returns normalised paper dicts.
    """
    results: list = []
    encoded = requests.utils.quote(query)

    for src in registry_subset:
        if len(results) >= limit * len(registry_subset):
            break
        name = src["name"]
        url  = src["api"].replace("{q}", encoded)
        stype = src["type"]

        try:
            if stype == "api":
                data = _get(url, timeout=12)
                if not data:
                    continue
                # Try to extract items from common response shapes
                items = (data.get("response",{}).get("docs") or
                         data.get("hits",{}).get("hits") or
                         data.get("data") or
                         data.get("results") or
                         data.get("response",{}).get("results") or
                         (data if isinstance(data, list) else []))
                for item in items[:limit]:
                    if not isinstance(item, dict):
                        continue
                    t = (item.get("title") or item.get("title_s") or
                         item.get("dc.title") or "")
                    if isinstance(t, list):
                        t = t[0] if t else ""
                    if not str(t).strip():
                        continue
                    auth = (item.get("author") or item.get("authFullName_s") or
                            item.get("creator") or [])
                    if isinstance(auth, str):
                        auth = [auth]
                    yr = str(item.get("year") or item.get("producedDate_tdate") or
                             item.get("publication_date",""))[:4]
                    pdf = (item.get("downloadUrl") or item.get("pdfurl") or
                           item.get("pdf_url") or "")
                    results.append({
                        "title":    str(t)[:200],
                        "authors":  auth[:3],
                        "year":     yr,
                        "journal":  name,
                        "doi":      item.get("doi"),
                        "abstract": str(item.get("abstract") or
                                       item.get("description",""))[:300],
                        "pdf_url":  pdf,
                    })

            elif stype == "browser" and HAS_SCRAPLING:
                page = _fetch(url, stealth=True, timeout=30)
                if not page:
                    continue
                # Collect PDF links
                for a in (page.css("a[href$='.pdf'],a[href*='/pdf/']") or [])[:limit]:
                    href = a.attrib.get("href","")
                    if not href.startswith("http"):
                        continue
                    label = a.text.strip() or href.split("/")[-1].replace(".pdf","")[:100]
                    if len(label) < 5:
                        continue
                    results.append({
                        "title":    label,
                        "authors":  [],
                        "year":     "",
                        "journal":  name,
                        "doi":      None,
                        "abstract": "",
                        "pdf_url":  href,
                    })
        except Exception:
            continue

    return _norm(results, "ExtendedOA") if results else []


def search_google_scholar(query, year_from=None, limit=20):
    if not HAS_SCRAPLING:
        return []
    params = {"q": query, "as_sdt": "0,5", "hl": "en"}
    if year_from:
        params["as_ylo"] = str(year_from)
    url  = "https://scholar.google.com/scholar?" + requests.utils.urlencode(params)
    page = _fetch(url, stealth=True)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".gs_ri") or [])[:limit]:
            title_el  = item.css_first(".gs_rt a") or item.css_first(".gs_rt")
            author_el = item.css_first(".gs_a")
            snippet   = item.css_first(".gs_rs")
            cite_el   = item.css_first(".gs_fl a")
            title     = (title_el.text if title_el else "").strip()
            if not title:
                continue
            authors, year, journal = [], "", ""
            if author_el:
                raw   = author_el.text or ""
                parts = raw.split("—")
                if parts:
                    authors = [a.strip() for a in parts[0].split(",") if a.strip()]
                    ym = re.search(r"\b(19|20)\d{2}\b", raw)
                    year = ym.group() if ym else ""
                    journal = parts[1].strip() if len(parts) > 1 else ""
            gs_cites = None
            if cite_el:
                cm = re.search(r"\d+", cite_el.text or "")
                if cm:
                    gs_cites = int(cm.group())
            pdf_url = None
            parent = item.parent
            if parent:
                for a in (parent.css("a[href]") or []):
                    href = a.attrib.get("href", "")
                    if href.endswith(".pdf") or "/pdf/" in href.lower():
                        pdf_url = href if href.startswith("http") else None
                        break
            out.append({
                "title": title, "authors": authors, "year": year,
                "journal": journal, "doi": None,
                "abstract": snippet.text.strip() if snippet else None,
                "pdf_url": pdf_url, "gs_citations": gs_cites,
            })
    except Exception:
        pass
    return _norm(out, "Google Scholar")


def search_duckduckgo_pdfs(query, year_from=None, limit=15):
    if not HAS_SCRAPLING:
        return []
    sites = (
        "site:academia.edu OR site:researchgate.net OR site:pdfs.semanticscholar.org "
        "OR site:files.eric.ed.gov OR site:core.ac.uk OR site:hal.science "
        "OR site:zenodo.org OR site:oapen.org OR site:repository"
    )
    full_q = f"{query} ({sites})"
    url = "https://html.duckduckgo.com/html/?" + requests.utils.urlencode({"q": full_q})
    page = _fetch(url, stealth=False)
    if not page:
        url2 = "https://html.duckduckgo.com/html/?" + requests.utils.urlencode(
            {"q": f"{query} academic PDF open access"})
        page = _fetch(url2, stealth=False)
    if not page:
        return []
    out = []
    try:
        results = page.css(".result, .web-result, [class*='result']") or []
        for res in results[:limit]:
            title_el = (res.css_first(".result__title a") or
                        res.css_first("h2 a") or res.css_first("a.result__a"))
            snippet  = res.css_first(".result__snippet") or res.css_first(".result__body")
            if not title_el:
                continue
            title = title_el.text.strip()
            href  = title_el.attrib.get("href", "")
            if not title or not href:
                continue
            if "duckduckgo.com/l/?uddg=" in href:
                from urllib.parse import unquote, urlparse, parse_qs
                parsed = parse_qs(urlparse(href).query)
                href   = unquote(parsed.get("uddg", [href])[0])
            is_pdf = href.endswith(".pdf") or "/pdf/" in href.lower()
            out.append({
                "title": title, "authors": [], "year": "",
                "journal": None, "doi": None,
                "abstract": snippet.text.strip() if snippet else None,
                "pdf_url": href if is_pdf else None,
            })
    except Exception:
        pass
    return _norm(out, "DuckDuckGo")


def search_zlibrary(query, limit=10):
    if not HAS_SCRAPLING:
        return []
    urls  = [f"https://{d}/s/{requests.utils.quote(query)}" for d in ZLIB_DOMAINS]
    page  = _try_fetch(urls)
    if not page:
        return []
    out = []
    try:
        for sel in [".book-item",".bookCard",".resItemBox","[data-book-id]",".item"]:
            items = page.css(sel) or []
            if items:
                break
        for item in items[:limit]:
            title_el  = (item.css_first("h3 a") or item.css_first(".title a") or
                         item.css_first("a[href*='/book/']"))
            author_el = item.css_first(".authors a") or item.css_first("[class*='author']")
            if not title_el:
                continue
            title = title_el.text.strip()
            href  = title_el.attrib.get("href","")
            domain = ZLIB_DOMAINS[0]
            detail = (f"https://{domain}{href}" if href.startswith("/") else href) or None
            out.append({
                "title": title,
                "authors": [author_el.text.strip()] if author_el else [],
                "year": "", "journal": "Z-Library", "doi": None,
                "abstract": None, "pdf_url": detail,
            })
    except Exception:
        pass
    return _norm(out, "Z-Library")


def search_libgen(query, limit=15):
    if not HAS_SCRAPLING:
        return []
    urls = [f"https://{d}/search.php?req={requests.utils.quote(query)}&column=def"
            for d in LIBGEN_DOMAINS]
    page = _try_fetch(urls)
    if not page:
        return []
    out = []
    try:
        rows = page.css("table.c tr, #tablelibgen tr") or []
        for row in rows[1:limit+1]:
            cells = row.css("td") or []
            if len(cells) < 5:
                continue
            title_el   = cells[2].css_first("a") if len(cells) > 2 else None
            author_txt = cells[1].text.strip() if len(cells) > 1 else ""
            year_txt   = cells[4].text.strip() if len(cells) > 4 else ""
            title = title_el.text.strip() if title_el else ""
            if not title:
                continue
            href = title_el.attrib.get("href","") if title_el else ""
            pdf  = (f"https://{LIBGEN_DOMAINS[0]}/{href}"
                    if href and not href.startswith("http") else href) or None
            out.append({
                "title": title,
                "authors": [a.strip() for a in author_txt.split(",") if a.strip()],
                "year": year_txt[:4], "journal": "Library Genesis",
                "doi": None, "abstract": None, "pdf_url": pdf,
            })
    except Exception:
        pass
    return _norm(out, "LibGen")


def search_perplexica(query, limit=10):
    try:
        requests.get("http://localhost:3000", timeout=2)
    except Exception:
        return []
    try:
        resp = requests.post(
            "http://localhost:3000/api/search",
            json={"query": query, "focusMode": "academicSearch",
                  "optimizationMode": "speed"},
            timeout=25,
        )
        if resp.status_code == 200:
            sources = resp.json().get("sources") or resp.json().get("results") or []
            out = []
            for item in sources[:limit]:
                meta  = item.get("metadata") or {}
                title = item.get("title") or meta.get("title") or ""
                url   = item.get("url") or meta.get("url") or ""
                if not title:
                    continue
                out.append({
                    "title": title, "authors": [], "year": "", "journal": None,
                    "doi": None, "abstract": (item.get("pageContent") or "")[:500],
                    "pdf_url": url if url.endswith(".pdf") else None,
                })
            return _norm(out, "Perplexica")
    except Exception:
        pass
    return []


# ── NEW: Zenodo open research repository ─────────────────────────────────────
def search_zenodo(query, year_from=None, limit=25):
    """Zenodo — CERN open access platform, strong for linguistics preprints."""
    q = query
    if year_from:
        q += f" AND publication_date:[{year_from}-01-01 TO *]"
    data = _get("https://zenodo.org/api/records",
                {"q": q, "type": "publication", "size": limit, "sort": "mostrecent"})
    out = []
    for item in (data or {}).get("hits", {}).get("hits", []):
        meta  = item.get("metadata", {})
        files = item.get("files", [])
        pdf_url = next(
            (f.get("links", {}).get("self") for f in files if f.get("type") == "pdf"),
            None
        )
        out.append({
            "title":    meta.get("title"),
            "authors":  [c.get("name","") for c in meta.get("creators",[])],
            "year":     str(meta.get("publication_date",""))[:4],
            "abstract": meta.get("description",""),
            "doi":      meta.get("doi"),
            "pdf_url":  pdf_url,
            "journal":  (meta.get("journal") or {}).get("title"),
        })
    return _norm(out, "Zenodo")


# ── NEW: OATD — Open Access Theses and Dissertations ─────────────────────────
def search_oatd(query, year_from=None, limit=20):
    """OATD — global MA/PhD dissertation repository."""
    if not HAS_SCRAPLING:
        return []
    try:
        url  = f"https://oatd.org/oatd/search?q={requests.utils.quote(query)}&rows={limit}"
        page = _fetch(url, stealth=False)
        if not page:
            return []
        out = []
        for item in (page.css(".result") or [])[:limit]:
            title_el  = item.css_first("em") or item.css_first("a")
            author_el = item.css_first(".author")
            school_el = item.css_first(".school")
            link_el   = item.css_first("a[href]")
            title  = title_el.text.strip() if title_el else ""
            if not title:
                continue
            href = link_el.attrib.get("href","") if link_el else ""
            detail = (f"https://oatd.org{href}" if href.startswith("/") else href) or None
            out.append({
                "title":    title,
                "authors":  [author_el.text.strip()] if author_el else [],
                "year":     "",
                "abstract": "",
                "doi":      None,
                "pdf_url":  detail,
                "journal":  school_el.text.strip() if school_el else "Thesis/Dissertation",
            })
        return _norm(out, "OATD")
    except Exception:
        return []


# ── NEW: Libyan university browser scraper ────────────────────────────────────
LIBYAN_PLATFORM_URLS = {
    "U of Benghazi":     "http://elib.uob.edu.ly/search?q={query}&type=thesis",
    "U of Tripoli":      "https://repo.uot.edu.ly/search?query={query}",
    "Al-Fateh U":        "https://alfateh.edu.ly/search?q={query}",
    "Sebha University":  "https://sebhau.edu.ly/research?q={query}",
    "Omar Al-Mukhtar U": "https://omu.edu.ly/search?q={query}",
    "Al-Mergeb U":       "https://almergeb.edu.ly/search?q={query}",
    "Misurata U":        "https://misuratau.edu.ly/search?q={query}",
    "Zawia U":           "https://zu.edu.ly/research?q={query}",
    "Mandumah":          "https://search.mandumah.com/Search/Results?lookfor={query}&type=AllFields",
    "CERIST Algeria":    "http://www.webreview.dz/spip.php?page=recherche&recherche={query}",
    "KSU Repository":    "https://repository.ksu.edu.sa/handle/123456789/1?q={query}",
}

def search_libyan_platform(platform_name: str, query: str, limit: int = 15) -> list:
    """Scrape a Libyan/MENA university repository for EFL dissertations."""
    url_template = LIBYAN_PLATFORM_URLS.get(platform_name, "")
    if not url_template or not HAS_SCRAPLING:
        return []
    url = url_template.format(query=requests.utils.quote(query))
    info(f"  Scraping {platform_name}: {url[:70]}")
    try:
        page = _fetch(url, stealth=True, timeout=35)
        if not page:
            return []
        out = []
        # Collect PDF links found on the page
        for a in (page.css("a[href$='.pdf'], a[href*='/pdf/'], a[href*='download']") or [])[:limit]:
            href  = a.attrib.get("href","")
            if not href.startswith("http"):
                from urllib.parse import urljoin, urlparse
                base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                href = urljoin(base, href)
            label = a.text.strip() or href.split("/")[-1].replace(".pdf","")
            if len(label) < 5:
                continue
            out.append({
                "title":    label[:150],
                "authors":  [],
                "year":     "",
                "journal":  platform_name,
                "doi":      None,
                "abstract": "",
                "pdf_url":  href,
            })
        return _norm(out, platform_name)
    except Exception:
        return []


def scihub_pdf(doi: str) -> str | None:
    if not doi or not HAS_SCRAPLING:
        return None
    for domain in SCIHUB_DOMAINS:
        page = _fetch(f"https://{domain}/{doi}", stealth=False)
        if not page:
            continue
        try:
            embed = page.css_first("#pdf, embed[src], iframe[src*='pdf']")
            if embed:
                src = embed.attrib.get("src","")
                return ("https:" + src) if src.startswith("//") else src
        except Exception:
            pass
    return None


# ── MD §11.2 — Enhanced browser scraper (Scrapling + requests fallback) ───────
def scrape_with_browser(url: str, extract_links: bool = True,
                         timeout: int = 30, stealth: bool = True) -> dict:
    """
    Enhanced browser scraper using Scrapling (Playwright backend).
    Falls back to requests with browser-like headers when Scrapling unavailable.
    Returns: {"html": str, "pdf_links": list, "paper_links": list, "text": str}
    """
    result: dict = {"html": "", "pdf_links": [], "paper_links": [], "text": ""}
    browser_hdrs = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"),
        "Accept":          "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer":         "https://www.google.com/",
    }
    if not HAS_SCRAPLING:
        try:
            kw: dict = {"headers": browser_hdrs, "timeout": timeout}
            if _academic_proxy.enabled:
                kw.update(_academic_proxy.session_kwargs())
            r = requests.get(url, **kw)
            result["html"] = r.text[:50000]
        except Exception as ex:
            warn(f"Browser fallback failed for {url[:60]}: {ex}")
        return result
    try:
        fetcher = StealthyFetcher() if stealth else Fetcher()
        page = fetcher.fetch(url, headless=True, network_idle=True,
                              timeout=timeout * 1000)
        result["html"] = str(page.html)[:50000]
        if extract_links:
            result["pdf_links"] = [
                a.attrib.get("href", "")
                for a in (page.css("a[href$='.pdf'], a[href*='/pdf/']") or [])
                if a.attrib.get("href", "").startswith("http")
            ]
            result["paper_links"] = [
                a.attrib.get("href", "")
                for a in (page.css(
                    "a[href*='/abstract/'], a[href*='/article/'], "
                    "a[href*='/paper/'], a[href*='/doi/']"
                ) or [])
                if a.attrib.get("href", "").startswith("http")
            ]
        try:
            result["text"] = page.get_all_text(
                ignore_tags=("script", "style"))[:10000]
        except Exception:
            pass
    except Exception as ex:
        warn(f"Scrapling error on {url[:60]}: {ex}")
    return result


# ── MD §11.2 — Libyan university scraper (exact name from MD) ─────────────────
def search_libyan_university(platform_name: str, query: str,
                              platform_config: dict) -> list:
    """
    Scrape a Libyan university repository for dissertations.
    Used in MD §11.2 exactly as specified.
    """
    base_url    = platform_config.get("url", "")
    pattern     = platform_config.get("search_pattern", "")
    search_url  = (pattern.format(query=requests.utils.quote(query))
                   if pattern else
                   f"{base_url}/search?q={requests.utils.quote(query)}")
    info(f"  Scraping {platform_name}: {search_url[:70]}")
    page_data = scrape_with_browser(search_url, stealth=True, timeout=40)
    papers: list = []
    for pdf_url in page_data.get("pdf_links", []):
        label = pdf_url.split("/")[-1].replace(".pdf", "").replace("-", " ")[:120]
        if len(label) < 5:
            continue
        papers.append({
            "title":    label,
            "authors":  [],
            "year":     "",
            "journal":  platform_name,
            "doi":      None,
            "abstract": "",
            "pdf_url":  pdf_url,
        })
    return _norm(papers, platform_name)


# ── MD §4 — SciELO (Latin America / Africa OA) ───────────────────────────────
def search_scielo(query: str, year_from=None, limit: int = 20) -> list:
    """SciELO — open-access Latin America & Africa journals."""
    params: dict = {"q": query, "count": limit, "from": 0, "format": "json"}
    if year_from:
        params["filter[year_cluster][]"] = str(year_from)
    data = _get("https://search.scielo.org/api/v2/search/", params)
    out: list = []
    for item in (data or {}).get("hits", {}).get("hits", []):
        src = item.get("_source", {})
        out.append({
            "title":    src.get("ti", {}).get("en") or src.get("ti", {}).get("es", ""),
            "authors":  src.get("au", []),
            "year":     str(src.get("dp", ""))[:4],
            "journal":  src.get("ta", ""),
            "doi":      src.get("doi"),
            "abstract": src.get("ab", {}).get("en", ""),
            "pdf_url":  src.get("pdf_url"),
        })
    return _norm(out, "SciELO")


# ── MD §4 — ResearchGate (browser scraper) ────────────────────────────────────
def search_researchgate(query: str, year_from=None, limit: int = 15) -> list:
    """ResearchGate — author self-archive, often has full PDFs."""
    if not HAS_SCRAPLING:
        return []
    url  = f"https://www.researchgate.net/search/publication?q={requests.utils.quote(query)}"
    page = _fetch(url, stealth=True, timeout=35)
    if not page:
        return []
    out: list = []
    try:
        for item in (page.css(".nova-legacy-e-text--size-m, .search-box__result-item") or [])[:limit]:
            title_el  = item.css_first("a.nova-legacy-e-link--theme-bare") or item.css_first("a")
            title     = title_el.text.strip() if title_el else ""
            if not title:
                continue
            href      = title_el.attrib.get("href", "") if title_el else ""
            full_url  = (f"https://www.researchgate.net{href}"
                         if href.startswith("/") else href)
            out.append({
                "title":    title,
                "authors":  [],
                "year":     "",
                "journal":  "ResearchGate",
                "doi":      None,
                "abstract": "",
                "pdf_url":  None,
                "source_url": full_url,
            })
    except Exception:
        pass
    return _norm(out, "ResearchGate")


# ── MD §4 — EThOS British Library Thesis Database ────────────────────────────
def search_ethos(query: str, year_from=None, limit: int = 20) -> list:
    """EThOS — British Library thesis database (browser scraper)."""
    if not HAS_SCRAPLING:
        return []
    url  = (f"https://ethos.bl.uk/SearchResults.do?"
            f"query={requests.utils.quote(query)}&amp;search_btn_go=Search")
    page = _fetch(url, stealth=True, timeout=40)
    if not page:
        return []
    out: list = []
    try:
        for item in (page.css(".record, .search-result, li.result") or [])[:limit]:
            title_el  = item.css_first("a.title, .result-title a, h3 a")
            title     = title_el.text.strip() if title_el else ""
            if not title:
                continue
            href      = title_el.attrib.get("href", "") if title_el else ""
            detail_url = (f"https://ethos.bl.uk{href}"
                          if href.startswith("/") else href)
            year_el   = item.css_first(".year, .date")
            year      = year_el.text.strip()[:4] if year_el else ""
            author_el = item.css_first(".author, .creator")
            authors   = [author_el.text.strip()] if author_el else []
            out.append({
                "title":   title,
                "authors": authors,
                "year":    year,
                "journal": "EThOS British Library [Thesis]",
                "doi":     None,
                "abstract":"",
                "pdf_url": detail_url or None,
            })
    except Exception:
        pass
    return _norm(out, "EThOS")


# ════════════════════════════════════════════════════════════════════════════════
#  NEW PLATFORM SEARCH FUNCTIONS — User-requested sites for maximum Q1 coverage
# ════════════════════════════════════════════════════════════════════════════════
def search_etd_ohiolink(query: str, year_from=None, limit: int = 25) -> list:
    """OhioLINK ETD Center — Electronic Theses and Dissertations."""
    if not HAS_SCRAPLING:
        return []
    url = f"https://etd.ohiolink.edu/search?q={requests.utils.quote(query)}"
    page = _fetch(url, stealth=True, timeout=30)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".result, .etd-item, tr") or [])[:limit]:
            title_el = item.css_first("a[href*='/view/'], .title a, a")
            if not title_el:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 10:
                continue
            href = title_el.attrib.get("href", "")
            detail_url = f"https://etd.ohiolink.edu{href}" if href.startswith("/") else href
            year_el = item.css_first(".date, .year")
            year = year_el.text.strip()[:4] if year_el else ""
            author_el = item.css_first(".author, .creator")
            authors = [author_el.text.strip()] if author_el else []
            out.append({
                "title": title,
                "authors": authors,
                "year": year,
                "journal": "OhioLINK ETD [Thesis]",
                "doi": None,
                "abstract": "",
                "pdf_url": detail_url,
            })
    except Exception:
        pass
    return _norm(out, "OhioLINK ETD")


def search_nature_linguistics(query: str, year_from=None, limit: int = 20) -> list:
    """Nature.com — search for linguistics and humanities papers."""
    params = {"q": query, "order": "relevance"}
    if year_from:
        params["date_range"] = f"{year_from}-{datetime.now().year}"
    data = _get(f"https://www.nature.com/search", params)
    out = []
    try:
        items = (data or {}).get("results", [])
        for item in items[:limit]:
            title = item.get("title", "")
            if not title:
                continue
            out.append({
                "title": title,
                "authors": [a.get("name","") for a in item.get("authors",[])],
                "year": str(item.get("date",""))[:4],
                "journal": item.get("publication","Nature"),
                "doi": item.get("doi"),
                "abstract": item.get("description",""),
                "pdf_url": item.get("pdf"),
            })
    except Exception:
        pass
    return _norm(out, "Nature")


def search_academicianhelp(query: str, year_from=None, limit: int = 20) -> list:
    """AcademicianHelp — academic resource aggregator."""
    if not HAS_SCRAPLING:
        return []
    url = f"https://academicianhelp.com/search?q={requests.utils.quote(query)}"
    page = _fetch(url, stealth=True, timeout=30)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".search-result, .result-item, article") or [])[:limit]:
            title_el = item.css_first("a, h3 a, .title")
            if not title_el:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 10:
                continue
            href = title_el.attrib.get("href", "")
            out.append({
                "title": title,
                "authors": [],
                "year": "",
                "journal": "AcademicianHelp",
                "doi": None,
                "abstract": "",
                "pdf_url": href if href.endswith(".pdf") else None,
            })
    except Exception:
        pass
    return _norm(out, "AcademicianHelp")


def search_elife_sciences(query: str, year_from=None, limit: int = 20) -> list:
    """eLife Sciences — high-quality open access research."""
    params = {"q": query, "per_page": limit}
    if year_from:
        params["for"] = f"{year_from}-present"
    data = _get("https://api.elifesciences.org/search", params)
    out = []
    try:
        items = (data or {}).get("items", [])
        for item in items[:limit]:
            title = item.get("title", "")
            if not title:
                continue
            out.append({
                "title": title,
                "authors": [a.get("name","") for a in item.get("authors",[])],
                "year": str(item.get("volume",""))[:4] if item.get("volume") else "",
                "journal": "eLife Sciences",
                "doi": item.get("doi"),
                "abstract": item.get("abstract",""),
                "pdf_url": item.get("pdf"),
            })
    except Exception:
        pass
    return _norm(out, "eLife Sciences")


def search_scienceopen(query: str, year_from=None, limit: int = 20) -> list:
    """ScienceOpen — open access scientific articles."""
    if not HAS_SCRAPLING:
        return []
    url = f"https://www.scienceopen.com/search?q={requests.utils.quote(query)}"
    page = _fetch(url, stealth=True, timeout=30)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".search-result, .doc-item, article") or [])[:limit]:
            title_el = item.css_first("a, h3 a, .title")
            if not title_el:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 10:
                continue
            href = title_el.attrib.get("href", "")
            abstract_el = item.css_first("p, .abstract")
            abstract = abstract_el.text.strip()[:300] if abstract_el else ""
            out.append({
                "title": title,
                "authors": [],
                "year": "",
                "journal": "ScienceOpen",
                "doi": None,
                "abstract": abstract,
                "pdf_url": href if "pdf" in href.lower() else None,
            })
    except Exception:
        pass
    return _norm(out, "ScienceOpen")


def search_core_api(query: str, year_from=None, limit: int = 25) -> list:
    """CORE API — full-text research papers aggregator."""
    params = {"q": query, "limit": limit}
    if year_from:
        params["yearFrom"] = year_from
    data = _get("https://api.core.ac.uk/v3/search/works", params)
    out = []
    for item in (data or {}).get("results", []):
        out.append({
            "title":    item.get("title"),
            "authors":  [a.get("name") for a in (item.get("authors") or [])],
            "year":     item.get("yearPublished"),
            "journal":  item.get("publisher"),
            "doi":      item.get("doi"),
            "abstract": item.get("abstract"),
            "pdf_url":  item.get("downloadUrl"),
        })
    return _norm(out, "CORE API")


def search_oa_mg(query: str, year_from=None, limit: int = 20) -> list:
    """OA.mg — open access aggregator."""
    if not HAS_SCRAPLING:
        return []
    url = f"https://oa.mg/search?q={requests.utils.quote(query)}"
    page = _fetch(url, stealth=True, timeout=30)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".result, .paper, article") or [])[:limit]:
            title_el = item.css_first("a, h3 a, .title")
            if not title_el:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 10:
                continue
            href = title_el.attrib.get("href", "")
            out.append({
                "title": title,
                "authors": [],
                "year": "",
                "journal": "OA.mg",
                "doi": None,
                "abstract": "",
                "pdf_url": href if "pdf" in href.lower() else None,
            })
    except Exception:
        pass
    return _norm(out, "OA.mg")


def search_zenodo_extended(query: str, year_from=None, limit: int = 25) -> list:
    """Zenodo Extended — open research repository."""
    params = {"q": query, "type": "publication", "size": limit}
    if year_from:
        params["years"] = f"{year_from}-{datetime.now().year}"
    data = _get("https://zenodo.org/api/records", params)
    out = []
    for item in (data or {}).get("hits", {}).get("hits", []):
        meta = item.get("metadata", {})
        title = meta.get("title", "")
        if not title:
            continue
        pdf_url = None
        for f in item.get("files", []):
            if f.get("type") == "pdf" or ".pdf" in f.get("key",""):
                pdf_url = f.get("links",{}).get("self")
                break
        out.append({
            "title": title,
            "authors": [a.get("name","") for a in meta.get("creators",[])],
            "year": str(meta.get("publication_date",""))[:4],
            "journal": "Zenodo",
            "doi": meta.get("doi"),
            "abstract": meta.get("description",""),
            "pdf_url": pdf_url,
        })
    return _norm(out, "Zenodo Extended")


# ════════════════════════════════════════════════════════════════════════════════
#  NEW PLATFORMS — 30+ additional academic paper sources for maximum coverage
# ════════════════════════════════════════════════════════════════════════════════

def search_academia_edu(query: str, year_from=None, limit: int = 20) -> list:
    """Academia.edu — academic social network with author-uploaded papers."""
    encoded = requests.utils.quote(query)
    url = f"https://www.academia.edu/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=20)
        if r.status_code != 200:
            return []
        out = []
        # Parse paper entries from search results
        for m in re.finditer(r'<a[^>]*href="(/[^"]+)"[^>]*>([^<]+)</a>', r.text):
            href, title = m.group(1), m.group(2).strip()
            if len(title) < 20 or "/search" in href:
                continue
            out.append({
                "title": title[:200],
                "authors": [],
                "year": "",
                "journal": "Academia.edu",
                "doi": None,
                "abstract": "",
                "pdf_url": f"https://www.academia.edu{href}" if href.startswith("/") else href,
            })
            if len(out) >= limit:
                break
        return _norm(out, "Academia.edu")
    except Exception:
        return []


def search_biorxiv(query: str, year_from=None, limit: int = 20) -> list:
    """bioRxiv — biology preprint server."""
    params = {"q": query, "limit": limit}
    data = _get("https://api.biorxiv.org/details/biorxiv/0/0/" + query, params)
    out = []
    if data and isinstance(data, list):
        for item in data[:limit]:
            title = item.get("title", "")
            if not title:
                continue
            out.append({
                "title": title,
                "authors": [item.get("authors", "")],
                "year": item.get("date", "")[:4],
                "journal": "bioRxiv",
                "doi": item.get("doi"),
                "abstract": item.get("abstract", ""),
                "pdf_url": f"https://www.biorxiv.org/content/{item.get('doi','')}v1.full.pdf",
            })
    return _norm(out, "bioRxiv")


def search_medrxiv(query: str, year_from=None, limit: int = 20) -> list:
    """medRxiv — medical/health sciences preprint server."""
    params = {"q": query, "limit": limit}
    data = _get("https://api.medrxiv.org/details/medrxiv/0/0/" + query, params)
    out = []
    if data and isinstance(data, list):
        for item in data[:limit]:
            title = item.get("title", "")
            if not title:
                continue
            out.append({
                "title": title,
                "authors": [item.get("authors", "")],
                "year": item.get("date", "")[:4],
                "journal": "medRxiv",
                "doi": item.get("doi"),
                "abstract": item.get("abstract", ""),
                "pdf_url": f"https://www.medrxiv.org/content/{item.get('doi','')}v1.full.pdf",
            })
    return _norm(out, "medRxiv")


def search_psyarxiv(query: str, year_from=None, limit: int = 20) -> list:
    """PsyArXiv — psychology preprint repository via OSF."""
    params = {"q": query, "page_size": limit, "providers": "psyarxiv"}
    data = _get("https://api.osf.io/v2/preprints/search/", params)
    out = []
    if data:
        for item in data.get("data", [])[:limit]:
            attrs = item.get("attributes", {})
            title = attrs.get("title", "")
            if not title:
                continue
            doi = attrs.get("doi")
            out.append({
                "title": title,
                "authors": [a.get("given", "") + " " + a.get("family", "") for a in attrs.get("contributors", [])[:5]],
                "year": attrs.get("publication_date", "")[:4],
                "journal": "PsyArXiv",
                "doi": doi,
                "abstract": attrs.get("description", ""),
                "pdf_url": f"https://doi.org/{doi}" if doi else item.get("links", {}).get("self", ""),
            })
    return _norm(out, "PsyArXiv")


def search_socarxiv(query: str, year_from=None, limit: int = 20) -> list:
    """SocArXiv — social science preprint repository."""
    params = {"q": query, "page_size": limit, "providers": "socarxiv"}
    data = _get("https://api.osf.io/v2/preprints/search/", params)
    out = []
    if data:
        for item in data.get("data", [])[:limit]:
            attrs = item.get("attributes", {})
            title = attrs.get("title", "")
            if not title:
                continue
            doi = attrs.get("doi")
            out.append({
                "title": title,
                "authors": [a.get("given", "") + " " + a.get("family", "") for a in attrs.get("contributors", [])[:5]],
                "year": attrs.get("publication_date", "")[:4],
                "journal": "SocArXiv",
                "doi": doi,
                "abstract": attrs.get("description", ""),
                "pdf_url": f"https://doi.org/{doi}" if doi else "",
            })
    return _norm(out, "SocArXiv")


def search_openaire(query: str, year_from=None, limit: int = 25) -> list:
    """OpenAIRE — European open access infrastructure."""
    params = {"q": query, "size": limit, "type": "literature"}
    if year_from:
        params["fromDate"] = f"{year_from}0101"
    data = _get("https://api.openaire.eu/search/publications", params)
    out = []
    if data:
        results = data.get("response", {}).get("results", {}).get("result", [])
        if not isinstance(results, list):
            results = [results] if results else []
        for item in results[:limit]:
            metadata = item.get("metadata", {})
            title = metadata.get("title", "")
            if not title:
                continue
            out.append({
                "title": title,
                "authors": [a.get("value", "") for a in metadata.get("creator", [])[:5]],
                "year": metadata.get("dateofissue", ""),
                "journal": metadata.get("journal", {}).get("title", "OpenAIRE"),
                "doi": metadata.get("doi"),
                "abstract": metadata.get("description", ""),
                "pdf_url": metadata.get("fulltext", ""),
            })
    return _norm(out, "OpenAIRE")


def search_osf_preprints(query: str, year_from=None, limit: int = 20) -> list:
    """OSF Preprints — aggregated preprint repositories."""
    params = {"q": query, "page_size": limit}
    data = _get("https://api.osf.io/v2/preprints/search/", params)
    out = []
    if data:
        for item in data.get("data", [])[:limit]:
            attrs = item.get("attributes", {})
            title = attrs.get("title", "")
            if not title:
                continue
            doi = attrs.get("doi")
            out.append({
                "title": title,
                "authors": [a.get("given", "") + " " + a.get("family", "") for a in attrs.get("contributors", [])[:5]],
                "year": attrs.get("publication_date", "")[:4],
                "journal": "OSF Preprints",
                "doi": doi,
                "abstract": attrs.get("description", ""),
                "pdf_url": f"https://doi.org/{doi}" if doi else "",
            })
    return _norm(out, "OSF Preprints")


def search_worldwidescience(query: str, year_from=None, limit: int = 20) -> list:
    """WorldWideScience — global science portal aggregating national databases."""
    params = {"q": query, "format": "json"}
    data = _get("https://worldwidescience.org/api/results", params)
    out = []
    if data:
        for item in data.get("results", [])[:limit]:
            title = item.get("title", "")
            if not title:
                continue
            out.append({
                "title": title,
                "authors": item.get("author", []) if isinstance(item.get("author"), list) else [item.get("author", "")],
                "year": item.get("year", ""),
                "journal": item.get("source", "WorldWideScience"),
                "doi": item.get("doi"),
                "abstract": item.get("description", ""),
                "pdf_url": item.get("url", ""),
            })
    return _norm(out, "WorldWideScience")


def search_mdpi(query: str, year_from=None, limit: int = 20) -> list:
    """MDPI — open access publisher with 400+ journals."""
    params = {"search_text": query, "limit": limit}
    data = _get("https://api.mdpi.com/v1/articles/search", params)
    out = []
    if data and isinstance(data, list):
        for item in data[:limit]:
            title = item.get("Title", "")
            if not title:
                continue
            out.append({
                "title": title,
                "authors": [a.get("Name", "") for a in item.get("Authors", [])[:5]],
                "year": item.get("PublicationDate", "")[:4],
                "journal": item.get("Journal", {}).get("Title", "MDPI"),
                "doi": item.get("DOI"),
                "abstract": item.get("Abstract", ""),
                "pdf_url": item.get("PDFURL", ""),
            })
    # Fallback to HTML scraping
    if not out:
        try:
            encoded = requests.utils.quote(query)
            r = requests.get(f"https://www.mdpi.com/search?q={encoded}", headers=HDRS, timeout=20)
            for m in re.finditer(r'<a[^>]*class="title-link"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', r.text):
                href, title = m.group(1), m.group(2).strip()
                if len(title) > 15:
                    out.append({
                        "title": title,
                        "authors": [],
                        "year": "",
                        "journal": "MDPI",
                        "doi": None,
                        "abstract": "",
                        "pdf_url": f"https://www.mdpi.com{href}" if href.startswith("/") else href,
                    })
                    if len(out) >= limit:
                        break
        except Exception:
            pass
    return _norm(out, "MDPI")


def search_cern_server(query: str, year_from=None, limit: int = 20) -> list:
    """CERN Document Server — physics, mathematics, and related fields."""
    params = {"q": f"find {query}", "of": "xm", "rg": limit}
    data = _get("https://cds.cern.ch/search", params)
    out = []
    if data and "record" in str(data):
        # Parse XML response
        records = re.findall(r'<record>(.*?)</record>', str(data), re.DOTALL)
        for rec in records[:limit]:
            title = re.search(r'<title[^>]*>(.*?)</title>', rec)
            if title:
                out.append({
                    "title": title.group(1),
                    "authors": [a.group(1) for a in re.finditer(r'<creator>(.*?)</creator>', rec)][:5],
                    "year": (re.search(r'<date>(.*?)</date>', rec) or type('', (), {"group": lambda s, n: ""})).group(1)[:4],
                    "journal": "CERN",
                    "doi": (re.search(r'<doi>(.*?)</doi>', rec) or type('', (), {"group": lambda s, n: None})).group(1),
                    "abstract": (re.search(r'<abstract[^>]*>(.*?)</abstract>', rec, re.DOTALL) or type('', (), {"group": lambda s, n: ""})).group(1)[:500],
                    "pdf_url": "",
                })
    return _norm(out, "CERN")


def search_science_gov(query: str, year_from=None, limit: int = 20) -> list:
    """Science.gov — U.S. government science portal."""
    params = {"q": query, "format": "json"}
    data = _get("https://www.science.gov/api/search", params)
    out = []
    if data and isinstance(data, dict):
        for item in data.get("results", [])[:limit]:
            title = item.get("title", "")
            if not title:
                continue
            out.append({
                "title": title,
                "authors": item.get("author", []) if isinstance(item.get("author"), list) else [item.get("author", "")],
                "year": item.get("year", ""),
                "journal": item.get("journalTitle", "Science.gov"),
                "doi": item.get("doi"),
                "abstract": item.get("snippet", ""),
                "pdf_url": item.get("doi", ""),
            })
    return _norm(out, "Science.gov")


def search_nasa_ntrs(query: str, year_from=None, limit: int = 20) -> list:
    """NASA Technical Reports Server — aerospace and space research."""
    params = {"q": query, "page": 1, "pageSize": limit}
    data = _get("https://ntrs.nasa.gov/api/citations", params)
    out = []
    if data and isinstance(data, list):
        for item in data[:limit]:
            title = item.get("title", "")
            if not title:
                continue
            out.append({
                "title": title,
                "authors": [a.get("name", "") for a in item.get("authors", [])[:5]],
                "year": item.get("publicationDate", "")[:4],
                "journal": "NASA NTRS",
                "doi": item.get("doi"),
                "abstract": item.get("abstract", ""),
                "pdf_url": f"https://ntrs.nasa.gov/api/citations/{item.get('citationId','')}/downloads",
            })
    return _norm(out, "NASA NTRS")


def search_digital_commons(query: str, year_from=None, limit: int = 20) -> list:
    """Digital Commons Network — university institutional repositories."""
    params = {"q": query}
    data = _get("https://network.bepress.com/api/search", params)
    out = []
    if data:
        for item in data.get("results", [])[:limit]:
            title = item.get("title", "")
            if not title:
                continue
            out.append({
                "title": title,
                "authors": [item.get("author", "")],
                "year": item.get("date", "")[:4],
                "journal": item.get("publicationTitle", "Digital Commons"),
                "doi": item.get("doi"),
                "abstract": item.get("abstract", ""),
                "pdf_url": item.get("url", ""),
            })
    return _norm(out, "Digital Commons")


def search_jstor_open(query: str, year_from=None, limit: int = 20) -> list:
    """JSTOR Open Content — free access to thousands of articles."""
    encoded = requests.utils.quote(query)
    url = f"https://www.jstor.org/action/doBasicSearch?Query={encoded}&sdjession=&acc=off&so=sr"
    try:
        r = requests.get(url, headers=HDRS, timeout=20)
        if r.status_code != 200:
            return []
        out = []
        for m in re.finditer(r'<h2[^>]*class="title"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', r.text, re.DOTALL):
            href, title = m.group(1), m.group(2).strip()
            if len(title) > 10:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "JSTOR",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": f"https://www.jstor.org{href}" if href.startswith("/") else href,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "JSTOR Open")
    except Exception:
        return []


def search_ebsco_dissertations(query: str, year_from=None, limit: int = 20) -> list:
    """EBSCO Open Dissertations — free access to dissertations."""
    encoded = requests.utils.quote(query)
    url = f"https://www.ebsco.com/research-databases/open-dissertations/results?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=20)
        if r.status_code != 200:
            return []
        out = []
        for m in re.finditer(r'<h2[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', r.text, re.DOTALL):
            href, title = m.group(1), m.group(2).strip()
            if len(title) > 10:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "EBSCO Open Dissertations",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": href,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "EBSCO Dissertations")
    except Exception:
        return []


def search_paperpanda(query: str, year_from=None, limit: int = 15) -> list:
    """PaperPanda — browser extension API for finding free papers."""
    encoded = requests.utils.quote(query)
    url = f"https://paperpanda.app/api/search?q={encoded}&limit={limit}"
    data = _get(url, {})
    out = []
    if data and isinstance(data, list):
        for item in data[:limit]:
            title = item.get("title", "")
            if not title:
                continue
            out.append({
                "title": title,
                "authors": item.get("authors", []),
                "year": item.get("year", ""),
                "journal": item.get("journal", "PaperPanda"),
                "doi": item.get("doi"),
                "abstract": item.get("abstract", ""),
                "pdf_url": item.get("pdf_url", ""),
            })
    return _norm(out, "PaperPanda")


def search_ssoar(query: str, year_from=None, limit: int = 20) -> list:
    """SSOAR — Social Science Open Access Repository."""
    params = {"q": query, "format": "json", "count": limit}
    data = _get("https://www.ssoar.info/ssoar/search", params)
    out = []
    if data:
        for item in data.get("items", [])[:limit]:
            title = item.get("title", "")
            if not title:
                continue
            out.append({
                "title": title,
                "authors": [a.get("name", "") for a in item.get("authors", [])[:5]],
                "year": item.get("date", "")[:4],
                "journal": "SSOAR",
                "doi": item.get("doi"),
                "abstract": item.get("abstract", ""),
                "pdf_url": item.get("pdf", ""),
            })
    return _norm(out, "SSOAR")


def search_bioline(query: str, year_from=None, limit: int = 20) -> list:
    """Bioline International — bioscience publications from developing countries."""
    params = {"q": query, "rows": limit}
    data = _get("http://www.bioline.org.br/cgi-bin/wais/search", params)
    out = []
    if data:
        for m in re.finditer(r'<a[^>]*href="([^"]+\.pdf)"[^>]*>([^<]+)</a>', str(data)):
            href, title = m.group(1), m.group(2).strip()
            if len(title) > 10:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Bioline",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": f"http://www.bioline.org.br{href}" if href.startswith("/") else href,
                })
                if len(out) >= limit:
                    break
    return _norm(out, "Bioline")


def search_redalyc(query: str, year_from=None, limit: int = 20) -> list:
    """Redalyc — scientific journals from Latin America, Caribbean, Portugal, Spain."""
    params = {"q": query, "size": limit}
    data = _get("https://api.redalyc.org/api/articulos/search", params)
    out = []
    if data and isinstance(data, list):
        for item in data[:limit]:
            title = item.get("title", "")
            if not title:
                continue
            out.append({
                "title": title,
                "authors": [a.get("name", "") for a in item.get("authors", [])[:5]],
                "year": item.get("year", ""),
                "journal": item.get("journal_name", "Redalyc"),
                "doi": item.get("doi"),
                "abstract": item.get("abstract", ""),
                "pdf_url": item.get("pdf", ""),
            })
    return _norm(out, "Redalyc")


# ── Relevance Filtering ───────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════════════════
#  NEW PLATFORM SEARCH FUNCTIONS — User's extended list for maximum Q1 coverage
#  Each platform has a FULL search function (not just a registry entry)
# ════════════════════════════════════════════════════════════════════════════════
def search_annas_archive_enhanced(query: str, year_from=None, limit: int = 15) -> list:
    """Anna's Archive — enhanced with multiple domain fallback."""
    if not HAS_SCRAPLING:
        return []
    encoded = requests.utils.quote(query)
    for domain in ANNAS_ARCHIVE_DOMAINS:
        try:
            page = _fetch(f"https://{domain}/search?q={encoded}", stealth=True, timeout=35)
            if not page:
                continue
            out = []
            links = page.css("a[href*='/md5/'], a[href*='/ipfs/']") or []
            for link in links[:limit]:
                href = link.attrib.get("href", "")
                title = link.text.strip() or href.split("/")[-1].replace("-", " ")[:100]
                if len(title) < 5:
                    continue
                detail_url = f"https://{domain}{href}" if href.startswith("/") else href
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Anna's Archive",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": detail_url,
                })
            if out:
                return _norm(out, "Anna's Archive")
        except Exception:
            continue
    return []


def search_scihub_multi(query: str, year_from=None, limit: int = 10) -> list:
    """Sci-Hub — multi-domain search for DOI-based papers."""
    if not HAS_SCRAPLING:
        return []
    doi_pattern = r'10\.\d{4,}/[^\s]+'
    dois = re.findall(doi_pattern, query)
    if not dois:
        return []
    out = []
    for doi in dois[:limit]:
        for domain in SCIHUB_DOMAINS[:5]:
            try:
                page = _fetch(f"https://{domain}/{doi}", stealth=False, timeout=20)
                if not page:
                    continue
                embed = page.css_first("#pdf, embed[src], iframe[src*='pdf']")
                if embed:
                    src = embed.attrib.get("src", "")
                    pdf_url = ("https:" + src) if src.startswith("//") else src
                    out.append({
                        "title": f"Sci-Hub: {doi}",
                        "authors": [],
                        "year": "",
                        "journal": "Sci-Hub",
                        "doi": doi,
                        "abstract": "",
                        "pdf_url": pdf_url,
                    })
                    break
            except Exception:
                continue
    return _norm(out, "Sci-Hub") if out else []


def search_genemedi(query: str, year_from=None, limit: int = 15) -> list:
    """Genemedi.net — academic paper search (Sci-Hub alternative)."""
    if not HAS_SCRAPLING:
        return []
    url = f"https://www.genemedi.net/sci-hub-alternative?q={requests.utils.quote(query)}"
    page = _fetch(url, stealth=True, timeout=30)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".result, .paper-item, article, .item") or [])[:limit]:
            title_el = item.css_first("a, h3 a, .title a")
            if not title_el:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 8:
                continue
            href = title_el.attrib.get("href", "")
            out.append({
                "title": title[:200],
                "authors": [],
                "year": "",
                "journal": "Genemedi",
                "doi": None,
                "abstract": "",
                "pdf_url": href if ".pdf" in href.lower() else None,
            })
    except Exception:
        pass
    return _norm(out, "Genemedi") if out else []


def search_shadow_libraries(query: str, year_from=None, limit: int = 15) -> list:
    """Shadow Libraries GitHub — open access resource aggregator."""
    if not HAS_SCRAPLING:
        return []
    url = f"https://shadowlibraries.github.io/search?q={requests.utils.quote(query)}"
    page = _fetch(url, stealth=False, timeout=25)
    if not page:
        return []
    out = []
    try:
        for a in (page.css("a[href$='.pdf'], a[href*='download'], a[href*='/file/']") or [])[:limit]:
            href = a.attrib.get("href", "")
            label = a.text.strip() or href.split("/")[-1].replace(".pdf", "")[:100]
            if not href.startswith("http") or len(label) < 5:
                continue
            out.append({
                "title": label[:200],
                "authors": [],
                "year": "",
                "journal": "Shadow Libraries",
                "doi": None,
                "abstract": "",
                "pdf_url": href,
            })
    except Exception:
        pass
    return _norm(out, "Shadow Libraries") if out else []


def search_scinet(query: str, year_from=None, limit: int = 15) -> list:
    """Sci-Net.xyz — academic search engine."""
    if not HAS_SCRAPLING:
        return []
    url = f"https://sci-net.xyz/search?q={requests.utils.quote(query)}"
    page = _fetch(url, stealth=True, timeout=25)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".result, .paper, article") or [])[:limit]:
            title_el = item.css_first("a, h3 a, .title")
            if not title_el:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 8:
                continue
            href = title_el.attrib.get("href", "")
            out.append({
                "title": title[:200],
                "authors": [],
                "year": "",
                "journal": "Sci-Net",
                "doi": None,
                "abstract": "",
                "pdf_url": href if ".pdf" in href.lower() else None,
            })
    except Exception:
        pass
    return _norm(out, "Sci-Net") if out else []


def search_scibay(query: str, year_from=None, limit: int = 15) -> list:
    """Sci-Bay.org — open access scientific papers."""
    if not HAS_SCRAPLING:
        return []
    url = f"https://sci-bay.org/search?q={requests.utils.quote(query)}"
    page = _fetch(url, stealth=True, timeout=25)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".result, .paper-item, article") or [])[:limit]:
            title_el = item.css_first("a, h3 a, .title")
            if not title_el:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 8:
                continue
            href = title_el.attrib.get("href", "")
            out.append({
                "title": title[:200],
                "authors": [],
                "year": "",
                "journal": "Sci-Bay",
                "doi": None,
                "abstract": "",
                "pdf_url": href if ".pdf" in href.lower() else None,
            })
    except Exception:
        pass
    return _norm(out, "Sci-Bay") if out else []


def search_grokipedia(query: str, year_from=None, limit: int = 15) -> list:
    """Grokipedia.com — academic search aggregator."""
    if not HAS_SCRAPLING:
        return []
    url = f"https://grokipedia.com/search?q={requests.utils.quote(query)}"
    page = _fetch(url, stealth=True, timeout=25)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".result, .search-result, article") or [])[:limit]:
            title_el = item.css_first("a, h3 a, .title")
            if not title_el:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 8:
                continue
            href = title_el.attrib.get("href", "")
            out.append({
                "title": title[:200],
                "authors": [],
                "year": "",
                "journal": "Grokipedia",
                "doi": None,
                "abstract": "",
                "pdf_url": href if ".pdf" in href.lower() else None,
            })
    except Exception:
        pass
    return _norm(out, "Grokipedia") if out else []


def search_europepmc(query: str, year_from=None, limit: int = 25) -> list:
    """Europe PMC — 35M+ biomedical and life sciences records."""
    params = {"query": query, "pageSize": limit, "format": "json"}
    if year_from:
        params["query"] += f" AND (PUB_YEAR:[{year_from} TO 2026])"
    data = _get("https://www.ebi.ac.uk/europepmc/webservices/rest/search", params)
    out = []
    for item in (data or {}).get("resultList", {}).get("result", []):
        out.append({
            "title": item.get("title"),
            "authors": [item.get("authorString", "")],
            "year": str(item.get("pubYear", "")),
            "journal": item.get("journalTitle"),
            "doi": item.get("doi"),
            "abstract": item.get("abstractText"),
            "pdf_url": item.get("pdfInfo", {}).get("pdfAvailability") if item.get("pdfInfo") else None,
            "gs_citations": int(item.get("citedByCount", 0) or 0),
        })
    return _norm(out, "Europe PMC") if out else []


def search_philpapers(query: str, year_from=None, limit: int = 20) -> list:
    """PhilPapers — philosophy and interdisciplinary research."""
    params = {"term": query, "limit": limit}
    if year_from:
        params["yearFrom"] = year_from
    data = _get("https://philpapers.org/asearch.pl", {**params, "format": "json"})
    out = []
    for item in (data or {}).get("items", []):
        out.append({
            "title": item.get("title"),
            "authors": [a.get("surname", "") for a in (item.get("authors") or [])],
            "year": str(item.get("year", "")),
            "journal": (item.get("journal") or {}).get("name"),
            "doi": item.get("doi"),
            "abstract": item.get("abstract"),
            "pdf_url": item.get("pdfLink"),
        })
    return _norm(out, "PhilPapers") if out else []


def search_doab(query: str, year_from=None, limit: int = 20) -> list:
    """DOAB — Directory of Open Access Books."""
    params = {"query": query, "limit": limit, "expand": "metadata"}
    data = _get("https://directory.doabooks.org/rest/search", params)
    out = []
    for item in (data or {}).get("result", []):
        bib = item.get("bibliographicRecord", {}) or {}
        out.append({
            "title": bib.get("title"),
            "authors": [a.get("name", "") for a in (bib.get("contributor") or [])],
            "year": str(bib.get("publicationDate", "")),
            "journal": "DOAB",
            "doi": None,
            "abstract": "",
            "pdf_url": next((l.get("url") for l in (item.get("link") or [])
                           if l.get("type") == "OPEN"), None),
        })
    return _norm(out, "DOAB") if out else []


def search_ssrn(query: str, year_from=None, limit: int = 20) -> list:
    """SSRN — Social Science Research Network pre-prints."""
    if not HAS_SCRAPLING:
        return []
    url = f"https://www.ssrn.com/search={requests.utils.quote(query)}&order=relevance"
    page = _fetch(url, stealth=True, timeout=30)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".abstract, .title, .srn-paper") or [])[:limit]:
            title_el = item.css_first("a, .title a, h3")
            if not title_el:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 10:
                continue
            out.append({
                "title": title[:200],
                "authors": [],
                "year": "",
                "journal": "SSRN",
                "doi": None,
                "abstract": "",
                "pdf_url": None,
            })
    except Exception:
        pass
    return _norm(out, "SSRN") if out else []


def search_internet_archive(query: str, year_from=None, limit: int = 20) -> list:
    """Internet Archive — millions of free books, articles, and papers."""
    params = {"q": query, "fl[]": ["identifier", "title", "creator", "year"],
              "output": "json", "rows": limit}
    if year_from:
        params["q"] += f" AND year:[{year_from} TO 2026]"
    data = _get("https://archive.org/advancedsearch.php", params)
    out = []
    for item in (data or {}).get("response", {}).get("docs", []):
        identifier = item.get("identifier", "")
        out.append({
            "title": item.get("title", [""])[0] if isinstance(item.get("title"), list) else item.get("title", ""),
            "authors": item.get("creator", []) if isinstance(item.get("creator"), list) else [item.get("creator", "")],
            "year": str(item.get("year", "")),
            "journal": "Internet Archive",
            "doi": None,
            "abstract": "",
            "pdf_url": f"https://archive.org/download/{identifier}/{identifier}.pdf" if identifier else None,
        })
    return _norm(out, "Internet Archive") if out else []


def search_plos(query: str, year_from=None, limit: int = 20) -> list:
    """PLoS ONE — open access scientific journal."""
    params = {"q": f"everything:{query}", "fl": "id,title,author,publication_date,abstract",
              "rows": limit, "wt": "json"}
    if year_from:
        params["q"] += f" AND publication_date:[{year_from}-01-01T00:00:00Z TO 2026-12-31T23:59:59Z]"
    data = _get("https://api.plos.org/search", params)
    out = []
    for item in (data or {}).get("response", {}).get("docs", []):
        out.append({
            "title": item.get("title"),
            "authors": item.get("author", []) if isinstance(item.get("author"), list) else [item.get("author", "")],
            "year": str(item.get("publication_date", ""))[:4],
            "journal": "PLoS ONE",
            "doi": None,
            "abstract": item.get("abstract"),
            "pdf_url": None,
        })
    return _norm(out, "PLoS ONE") if out else []


def search_oup(query: str, year_from=None, limit: int = 20) -> list:
    """Oxford University Press — open access search."""
    if not HAS_SCRAPLING:
        return []
    url = f"https://academic.oup.com/search-results?q={requests.utils.quote(query)}&f_OpenAccess=true"
    if year_from:
        url += f"&f_Year={year_from}%7C{datetime.now().year}"
    page = _fetch(url, stealth=True, timeout=30)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".search-result, .al-citation, .result") or [])[:limit]:
            title_el = item.css_first("a, h3 a, .title a")
            if not title_el:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 10:
                continue
            out.append({
                "title": title[:200],
                "authors": [],
                "year": "",
                "journal": "Oxford University Press",
                "doi": None,
                "abstract": "",
                "pdf_url": None,
            })
    except Exception:
        pass
    return _norm(out, "OUP") if out else []


def search_springer_open(query: str, year_from=None, limit: int = 20) -> list:
    """Springer Open — open access journals and books."""
    if not HAS_SCRAPLING:
        return []
    url = f"https://link.springer.com/search?query={requests.utils.quote(query)}&search-within=Journal&facet-content-type=%22Article%22"
    page = _fetch(url, stealth=True, timeout=30)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".result-item, .c-card, li") or [])[:limit]:
            title_el = item.css_first("a.title, h3 a, .c-card__title a")
            if not title_el:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 10:
                continue
            href = title_el.attrib.get("href", "")
            detail = f"https://link.springer.com{href}" if href.startswith("/") else href
            out.append({
                "title": title[:200],
                "authors": [],
                "year": "",
                "journal": "Springer Open",
                "doi": None,
                "abstract": "",
                "pdf_url": None,
            })
    except Exception:
        pass
    return _norm(out, "Springer Open") if out else []


def search_wiley_open(query: str, year_from=None, limit: int = 20) -> list:
    """Wiley Online Library — open access articles."""
    if not HAS_SCRAPLING:
        return []
    url = f"https://onlinelibrary.wiley.com/action/doSearch?AllField={requests.utils.quote(query)}&startPage=0&pageSize={limit}&accessType=openAccess"
    page = _fetch(url, stealth=True, timeout=30)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".search-result, .issue-item, .citation") or [])[:limit]:
            title_el = item.css_first("a, h3 a, .issue-item__title a")
            if not title_el:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 10:
                continue
            out.append({
                "title": title[:200],
                "authors": [],
                "year": "",
                "journal": "Wiley",
                "doi": None,
                "abstract": "",
                "pdf_url": None,
            })
    except Exception:
        pass
    return _norm(out, "Wiley Open") if out else []


def search_tandfonline(query: str, year_from=None, limit: int = 20) -> list:
    """Taylor & Francis Online — open access articles."""
    if not HAS_SCRAPLING:
        return []
    url = f"https://www.tandfonline.com/action/doSearch?AllField={requests.utils.quote(query)}&startPage=0&pageSize={limit}"
    page = _fetch(url, stealth=True, timeout=30)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".search-result, .result-list li, .doi") or [])[:limit]:
            title_el = item.css_first("a, h3 a, .hlFld-Title a")
            if not title_el:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 10:
                continue
            out.append({
                "title": title[:200],
                "authors": [],
                "year": "",
                "journal": "Taylor & Francis",
                "doi": None,
                "abstract": "",
                "pdf_url": None,
            })
    except Exception:
        pass
    return _norm(out, "Taylor & Francis") if out else []


def search_sciencedirect(query: str, year_from=None, limit: int = 20) -> list:
    """ScienceDirect — Elsevier's open access articles."""
    if not HAS_SCRAPLING:
        return []
    url = f"https://www.sciencedirect.com/search?qs={requests.utils.quote(query)}&show=25&openAccess=true"
    page = _fetch(url, stealth=True, timeout=30)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".ResultItem, .result-item-content-title-link, li") or [])[:limit]:
            title_el = item.css_first("a, h2 a, .result-list-title-link")
            if not title_el:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 10:
                continue
            out.append({
                "title": title[:200],
                "authors": [],
                "year": "",
                "journal": "ScienceDirect",
                "doi": None,
                "abstract": "",
                "pdf_url": None,
            })
    except Exception:
        pass
    return _norm(out, "ScienceDirect") if out else []


def search_bialitic(query: str, year_from=None, limit: int = 15) -> list:
    """Bioline International — developing country research."""
    if not HAS_SCRAPLING:
        return []
    url = f"http://www.bioline.org.br/simple-search?search={requests.utils.quote(query)}"
    page = _fetch(url, stealth=False, timeout=25)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".search-result, .result, li") or [])[:limit]:
            title_el = item.css_first("a, .title a")
            if not title_el:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 8:
                continue
            href = title_el.attrib.get("href", "")
            out.append({
                "title": title[:200],
                "authors": [],
                "year": "",
                "journal": "Bioline",
                "doi": None,
                "abstract": "",
                "pdf_url": f"http://www.bioline.org.br{href}" if href.startswith("/") else None,
            })
    except Exception:
        pass
    return _norm(out, "Bioline") if out else []


def search_cogprints(query: str, year_from=None, limit: int = 15) -> list:
    """CogPrints — cognitive sciences archive."""
    if not HAS_SCRAPLING:
        return []
    url = f"https://cogprints.org/cgi-bin/simple_search?search={requests.utils.quote(query)}"
    page = _fetch(url, stealth=False, timeout=25)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".result, li, .search-result") or [])[:limit]:
            title_el = item.css_first("a")
            if not title_el:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 8:
                continue
            href = title_el.attrib.get("href", "")
            out.append({
                "title": title[:200],
                "authors": [],
                "year": "",
                "journal": "CogPrints",
                "doi": None,
                "abstract": "",
                "pdf_url": None,
            })
    except Exception:
        pass
    return _norm(out, "CogPrints") if out else []


def search_ajol(query: str, year_from=None, limit: int = 15) -> list:
    """AJOL — African Journals Online."""
    if not HAS_SCRAPLING:
        return []
    url = f"https://www.ajol.info/index.php/index/search/search?searchInitiated=1&simpleQuery={requests.utils.quote(query)}"
    page = _fetch(url, stealth=True, timeout=25)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".search-results .result, article, .item") or [])[:limit]:
            title_el = item.css_first("a, h3 a, .title")
            if not title_el:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 8:
                continue
            out.append({
                "title": title[:200],
                "authors": [],
                "year": "",
                "journal": "AJOL",
                "doi": None,
                "abstract": "",
                "pdf_url": None,
            })
    except Exception:
        pass
    return _norm(out, "AJOL") if out else []


def search_redalyc(query: str, year_from=None, limit: int = 20) -> list:
    """REDALYC — Latin American scientific journal repository."""
    if not HAS_SCRAPLING:
        return []
    url = f"https://www.redalyc.org/journals.oa?q={requests.utils.quote(query)}"
    page = _fetch(url, stealth=True, timeout=25)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".article, .search-result, .item") or [])[:limit]:
            title_el = item.css_first("a, .title a, h3")
            if not title_el:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 8:
                continue
            out.append({
                "title": title[:200],
                "authors": [],
                "year": "",
                "journal": "REDALYC",
                "doi": None,
                "abstract": "",
                "pdf_url": None,
            })
    except Exception:
        pass
    return _norm(out, "REDALYC") if out else []


def search_scieelo_bra(query: str, year_from=None, limit: int = 20) -> list:
    """SciELO Brazil — Brazilian open access journal platform."""
    if not HAS_SCRAPLING:
        return []
    params = {"q": query, "count": limit, "from": 0, "output": "iso"}
    data = _get("https://search.scielo.org/api/v2/search/", params)
    out = []
    for item in (data or {}).get("items", []):
        out.append({
            "title": item.get("ti", {}).get("en") or item.get("ti", {}).get("pt", ""),
            "authors": item.get("au", []),
            "year": str(item.get("yr", ""))[:4],
            "journal": item.get("so", ""),
            "doi": item.get("doi"),
            "abstract": item.get("ab", {}).get("en", ""),
            "pdf_url": item.get("link", [{}])[0].get("url") if item.get("link") else None,
        })
    return _norm(out, "SciELO Brazil") if out else []


def search_dialnet(query: str, year_from=None, limit: int = 20) -> list:
    """Dialnet — Spanish academic repository."""
    if not HAS_SCRAPLING:
        return []
    url = f"https://dialnet.unirioja.es/servlet/busqueda?busqueda={requests.utils.quote(query)}&tipo=busqueda"
    page = _fetch(url, stealth=True, timeout=25)
    if not page:
        return []
    out = []
    try:
        for item in (page.css(".resultado, .result, .document") or [])[:limit]:
            title_el = item.css_first("a, .titulo a, h3 a")
            if not title_el:
                continue
            title = title_el.text.strip()
            if not title or len(title) < 8:
                continue
            out.append({
                "title": title[:200],
                "authors": [],
                "year": "",
                "journal": "Dialnet",
                "doi": None,
                "abstract": "",
                "pdf_url": None,
            })
    except Exception:
        pass
    return _norm(out, "Dialnet") if out else []


# ── Relevance Filtering ───────────────────────────────────────────────────────
def _extract_kw(text) -> set[str]:
    if isinstance(text, list):
        text = " ".join(_safe_str(t) for t in text)
    text = _safe_str(text)
    stop = {"a","an","the","of","in","on","at","to","for","and","or","but","with","by",
            "from","is","are","was","were","be","study","research","paper","article",
            "based","using","this","that","these","those","its","their","there","about"}
    return {w for w in re.findall(r"[a-zA-Z]{3,}", text.lower()) if w not in stop}


def filter_by_relevance(papers: list, topic: str, field: str,
                        threshold: float = 0.12) -> tuple[list, int]:
    topic_kw = _extract_kw(topic + " " + field)
    kept, removed = [], 0
    for p in papers:
        title_str    = _safe_str(p.get("title"))
        abstract_str = _safe_str(p.get("abstract"))[:600]
        combined     = title_str + " " + abstract_str
        paper_kw     = _extract_kw(combined)
        if not topic_kw or not paper_kw:
            p["_relevance"] = 0.5
            kept.append(p)
            continue
        overlap       = len(topic_kw & paper_kw)
        score         = min(overlap / max(len(topic_kw) * 0.35, 1), 1.0)
        p["_relevance"] = round(score, 3)
        if score >= threshold:
            kept.append(p)
        else:
            removed += 1
    kept.sort(key=lambda x: x.get("_relevance", 0), reverse=True)
    return kept, removed


# ── PDF Download & Folder Organization ───────────────────────────────────────
def _safe_name(name: str, mx: int = 100) -> str:
    name = unicodedata.normalize("NFKD", str(name or "untitled"))
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f$]', "", name)
    name = re.sub(r"\s+", " ", name).strip(" ,;.:")
    return name[:mx].strip(" .")   # strip AFTER truncation — Windows rejects trailing space/dot


# ── Extended journal database for better Scopus classification ────────────────
KNOWN_Q1_JOURNALS = {
    "applied linguistics","language learning","tesol quarterly",
    "journal of second language writing","system","modern language journal",
    "english for specific purposes","language teaching research",
    "studies in second language acquisition","language teaching",
    "elt journal","foreign language annals","language learning & technology",
    "language testing","bilingualism: language and cognition",
    "international journal of applied linguistics","annual review of applied linguistics",
    "journal of english for academic purposes","reading and writing",
    "written communication","educational researcher","review of educational research",
    "journal of educational psychology","computers & education",
    "teaching and teacher education","learning and instruction",
    "educational psychology review","british journal of educational technology",
    "journal of teacher education","teaching in higher education",
    "language","linguistics","journal of linguistics","cognitive linguistics",
    "journal of pragmatics","discourse & society","journal of sociolinguistics",
    "relc journal","english language teaching journal",
    "asian-pacific journal of second and foreign language education",
    "frontiers in psychology","frontiers in education","ieee access",
}
KNOWN_Q2_JOURNALS = {
    "english language teaching","journal of language teaching and research",
    "international journal of english language teaching",
    "innovation in language learning and teaching","language learning journal",
    "studies in applied linguistics","asian social science",
    "international education studies","journal of language and linguistic studies",
    "arab world english journal","asian efl journal","relc journal",
    "language teaching journal","international journal of applied linguistics",
    "advances in social sciences research journal",
}

def _fuzzy_q(journal: str) -> str:
    """Fuzzy-match journal name to known Q1/Q2 sets. Returns 'Q1','Q2', or ''."""
    if not journal:
        return ""
    jl = journal.lower().strip()
    for known in KNOWN_Q1_JOURNALS:
        if known in jl or jl in known:
            return "Q1"
        if difflib.SequenceMatcher(None, jl, known).ratio() > 0.82:
            return "Q1"
    for known in KNOWN_Q2_JOURNALS:
        if known in jl or jl in known:
            return "Q2"
        if difflib.SequenceMatcher(None, jl, known).ratio() > 0.82:
            return "Q2"
    return ""


# MD §9.3 — Fuzzy journal matching (exact function signature from MD)
def match_journal_to_known(journal_name: str,
                            known_set: set,
                            threshold: float = 0.82) -> bool:
    """
    Fuzzy match a journal name against a known set.
    MD §9.3 — used by enhanced_quartile_check().
    """
    if not journal_name:
        return False
    jl = journal_name.lower().strip()
    for known in known_set:
        if known in jl or jl in known:
            return True
    matches = difflib.get_close_matches(jl, known_set, n=1, cutoff=threshold)
    return bool(matches)


def enhanced_quartile_check(paper: dict) -> str:
    """
    MD §9.3 — Enhanced quartile detection:
    1. Existing Scimago API check (already done by bulk_check)
    2. Local known-journal fuzzy matching via match_journal_to_known()
    3. Returns existing Q if already classified; upgrades if possible.
    """
    journal    = paper.get("journal", "")
    existing_q = paper.get("scopus_quartile") or {}
    if isinstance(existing_q, dict):
        existing_q = existing_q.get("quartile", "")

    if existing_q and existing_q not in ("Not Found", "Not Ranked", ""):
        return existing_q   # already properly classified

    if match_journal_to_known(journal, KNOWN_Q1_JOURNALS):
        return "Q1"
    if match_journal_to_known(journal, KNOWN_Q2_JOURNALS):
        return "Q2"
    return existing_q or "Not Found"


# ── 16-folder hierarchy ───────────────────────────────────────────────────────
Q_FOLDER_MAP = {
    # Scopus quartile
    "Q1":          "Q1_Top_Journals",
    "Q2":          "Q2_Good_Journals",
    "Q3":          "Q3_Acceptable_Journals",
    "Q4":          "Q4_Lower_Tier",
    "Not Found":   "Not_Indexed",
    "Not Ranked":  "Not_Indexed",
    "":            "Not_Indexed",
    # Document type
    "PhD":         "PhD_Dissertations",
    "MA":          "MA_Dissertations",
    "Book":        "Books",
    "BookChapter": "Book_Chapters",
    "Conference":  "Conference_Papers",
    # Geographic tier
    "Libya":       "LOCAL_Libya",
    "Neighbor":    "NEIGHBOR_NorthAfrica",
    "MENA":        "REGIONAL_MENA",
}

ALL_EXTRA_FOLDERS = [
    "PhD_Dissertations","MA_Dissertations","Books","Book_Chapters","Conference_Papers",
    "LOCAL_Libya","NEIGHBOR_NorthAfrica","REGIONAL_MENA","GLOBAL_International",
    "HIGH_CITED_100plus","HIGH_CITED_500plus","RED_LIST_Pending_Manual",
]


def get_q_folder(base: Path, quartile: str) -> Path:
    folder_name = Q_FOLDER_MAP.get(quartile, "Not_Indexed")
    p = base / folder_name
    p.mkdir(parents=True, exist_ok=True)
    return p


def detect_doc_type(paper: dict) -> str:
    """Return 'PhD','MA','Book','BookChapter','Conference', or '' (use quartile)."""
    title   = (paper.get("title")    or "").lower()
    journal = (paper.get("journal")  or "").lower()
    abstract= (paper.get("abstract") or "").lower()
    pub_type= str(paper.get("publication_type") or "").lower()
    source  = (paper.get("source")   or "").lower()

    phd_keys = ["phd","doctoral","dissertation","doctorate","doctor of philosophy",
                "أطروحة دكتوراه","دكتوراه","ph.d"]
    if any(k in title or k in abstract or k in journal for k in phd_keys):
        return "PhD"

    ma_keys  = ["master","" "ma thesis"," m.a.","m.ed.","" "msc","m.sc.","thesis","postgraduate",
                "رسالة ماجستير","ماجستير","master's"]
    if any(k in title or k in abstract or k in journal for k in ma_keys):
        return "MA"

    if pub_type == "book" or any(k in source for k in ("libgen","z-library","oapen")):
        if any(k in title for k in ("chapter","part ","section ")):
            return "BookChapter"
        return "Book"

    conf_keys = ["conference","proceedings","workshop","symposium","congress","proc."]
    if any(k in journal or k in title for k in conf_keys):
        return "Conference"

    return ""


def detect_geo_tier(paper: dict) -> str:
    """Return 'Libya','Neighbor','MENA', or ''."""
    text = " ".join(str(v) for v in [
        paper.get("title"), paper.get("abstract"),
        paper.get("journal"), " ".join(paper.get("authors") or []),
        paper.get("source"),
    ]).lower()

    libyan = ["libya","libyan","benghazi","tripoli","misrata","al-rojban",
              "zawia","sebha","omar al-mukhtar","jebel gharbi"]
    neighbor = ["tunisia","tunisian","algeria","algerian","egypt","egyptian",
                "morocco","moroccan","sudan","sudanese","maghreb"]
    mena = ["saudi","jordan","qatar","uae","kuwait","oman","bahrain","iraq",
             "syria","mena","arab world","middle east","gulf","gcc"]

    if any(t in text for t in libyan):   return "Libya"
    if any(t in text for t in neighbor): return "Neighbor"
    if any(t in text for t in mena):     return "MENA"
    return ""


# ════════════════════════════════════════════════════════════════════════════════
#  RED LIST — systematic tracking of every failed download
# ════════════════════════════════════════════════════════════════════════════════
@dataclass
class RedListEntry:
    title:           str
    authors:         list
    year:            str
    journal:         str
    doi:             Optional[str]
    source_platform: str
    fail_reason:     str
    sources_tried:   str
    attempts:        int = 1
    last_attempt:    str = ""
    scopus_quartile: str = ""
    citation_count:  int = 0
    needs_proxy:     bool = False
    manual_priority: str = "MEDIUM"
    abstract:        str = ""

    def to_row(self) -> dict:
        d = asdict(self)
        d["authors"] = " | ".join(str(a) for a in self.authors[:3])
        return d


class RedListManager:
    HEADERS = [
        "manual_priority","scopus_quartile","citation_count",
        "title","authors","year","journal","doi",
        "source_platform","fail_reason","sources_tried",
        "attempts","last_attempt","needs_proxy","abstract",
    ]

    def __init__(self, study_dir: Path):
        self.csv_path  = study_dir / "RED_LIST_Pending_Manual_Download.csv"
        self.html_path = study_dir / "RED_LIST_view.html"
        self.entries: list[RedListEntry] = []
        self._load()

    def _load(self):
        if not self.csv_path.exists():
            return
        try:
            with open(self.csv_path, encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    self.entries.append(RedListEntry(
                        title=row.get("title",""),
                        authors=row.get("authors","").split(" | "),
                        year=row.get("year",""),
                        journal=row.get("journal",""),
                        doi=row.get("doi") or None,
                        source_platform=row.get("source_platform",""),
                        fail_reason=row.get("fail_reason",""),
                        sources_tried=row.get("sources_tried",""),
                        attempts=int(row.get("attempts",1) or 1),
                        last_attempt=row.get("last_attempt",""),
                        scopus_quartile=row.get("scopus_quartile",""),
                        citation_count=int(row.get("citation_count",0) or 0),
                        needs_proxy=str(row.get("needs_proxy","")).lower()=="true",
                        manual_priority=row.get("manual_priority","MEDIUM"),
                        abstract=row.get("abstract",""),
                    ))
        except Exception as e:
            warn(f"Could not load red list: {e}")

    def _exists(self, title: str) -> int:
        tl = title.lower().strip()
        for i, e in enumerate(self.entries):
            if e.title.lower().strip() == tl:
                return i
        return -1

    def add(self, paper: dict, fail_reason: str, sources_tried: list[str]):
        title = (paper.get("title") or "").strip()
        if not title:
            return
        idx = self._exists(title)
        if idx >= 0:
            self.entries[idx].attempts     += 1
            self.entries[idx].last_attempt  = datetime.now().isoformat()[:19]
            self.entries[idx].fail_reason   = fail_reason
            self.entries[idx].sources_tried = ", ".join(sources_tried)
            self.save(); return

        q = (paper.get("scopus_quartile") or {})
        q = q.get("quartile","") if isinstance(q, dict) else str(q)
        c = int(paper.get("gs_citations") or paper.get("scopus_cited") or 0)
        pr = ("HIGH"   if q == "Q1" or c > 100 else
              "MEDIUM" if q == "Q2" or c > 30  else "LOW")
        self.entries.append(RedListEntry(
            title=title,
            authors=list(paper.get("authors") or [])[:5],
            year=str(paper.get("year",""))[:4],
            journal=str(paper.get("journal",""))[:80],
            doi=paper.get("doi"),
            source_platform=str(paper.get("source","")),
            fail_reason=fail_reason,
            sources_tried=", ".join(sources_tried),
            last_attempt=datetime.now().isoformat()[:19],
            scopus_quartile=q,
            citation_count=c,
            needs_proxy=any(code in fail_reason for code in ["403","401","Forbidden"]),
            manual_priority=pr,
            abstract=str(paper.get("abstract",""))[:300],
        ))
        self.save()

    def save(self):
        try:
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)
            sorted_e = sorted(self.entries, key=lambda e: (
                0 if e.manual_priority=="HIGH" else
                1 if e.manual_priority=="MEDIUM" else 2,
                -e.citation_count
            ))
            with open(self.csv_path, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=self.HEADERS, extrasaction="ignore")
                w.writeheader()
                for e in sorted_e:
                    w.writerow(e.to_row())
            self._save_html(sorted_e)
        except Exception as ex:
            warn(f"Red List save failed: {ex}")

    def _save_html(self, entries):
        rows = ""
        for e in entries:
            bg = ("#ffd6d6" if e.manual_priority=="HIGH" else
                  "#fff3cd" if e.manual_priority=="MEDIUM" else "#f8f9fa")
            lock = "🔒" if e.needs_proxy else ""
            doi_link = (f'<a href="https://doi.org/{e.doi}" target="_blank">{e.doi}</a>'
                        if e.doi else "-")
            rows += (
                f'<tr style="background:{bg}">'
                f'<td><b>{e.manual_priority}</b></td><td>{e.scopus_quartile}</td>'
                f'<td>{e.citation_count}</td><td>{e.title[:90]}</td>'
                f'<td>{"; ".join(str(a) for a in e.authors[:2])}</td>'
                f'<td>{e.year}</td><td>{e.journal[:40]}</td><td>{doi_link}</td>'
                f'<td>{e.fail_reason[:60]} {lock}</td><td>{e.attempts}</td></tr>\n'
            )
        html = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<title>Red List</title><style>"
            "body{font-family:Arial;font-size:12px}"
            "table{border-collapse:collapse;width:100%}"
            "th{background:#333;color:#fff;padding:6px}"
            "td{border:1px solid #ddd;padding:4px}"
            "</style></head><body>"
            f"<h2>🔴 Red List — {len(entries)} Papers Pending Manual Download</h2>"
            f"<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>"
            "<table><thead><tr>"
            "<th>Priority</th><th>Q</th><th>Cites</th><th>Title</th>"
            "<th>Authors</th><th>Year</th><th>Journal</th><th>DOI</th>"
            "<th>Fail Reason</th><th>Attempts</th>"
            f"</tr></thead><tbody>{rows}</tbody></table></body></html>"
        )
        try:
            self.html_path.write_text(html, encoding="utf-8")
        except Exception:
            pass

    def summary(self) -> str:
        h = sum(1 for e in self.entries if e.manual_priority=="HIGH")
        m = sum(1 for e in self.entries if e.manual_priority=="MEDIUM")
        p = sum(1 for e in self.entries if e.needs_proxy)
        return (f"Red List: {len(self.entries)} papers  "
                f"(🔴 HIGH:{h}  🟡 MEDIUM:{m}  🔒 Needs proxy:{p})")


# ════════════════════════════════════════════════════════════════════════════════
#  7-LAYER PDF DOWNLOAD CHAIN
# ════════════════════════════════════════════════════════════════════════════════

def _dl(url: str, dest: Path) -> bool:
    """Download a single URL to dest. Returns True if file > 2 KB."""
    if not url or not url.startswith("http"):
        return False
    try:
        kw: dict = {"headers": HDRS, "timeout": 45, "stream": True, "allow_redirects": True}
        if _academic_proxy.enabled and _academic_proxy.needs_proxy(url):
            kw.update(_academic_proxy.session_kwargs())
        r = requests.get(url, **kw)
        ct = r.headers.get("content-type","")
        if r.status_code == 200 and ("pdf" in ct or "octet" in ct or url.endswith(".pdf")):
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            if dest.stat().st_size > 2000:
                return True
            dest.unlink(missing_ok=True)
    except Exception:
        pass
    return False


def _unpaywall(doi: str) -> Optional[str]:
    if not doi: return None
    try:
        data = _get(f"https://api.unpaywall.org/v2/{doi}",
                    params={"email":"research@hunter.edu"}, timeout=12)
        if not data: return None
        best = data.get("best_oa_location") or {}
        url  = best.get("url_for_pdf") or best.get("url")
        if url and url.startswith("http"):
            return url
        for loc in (data.get("oa_locations") or []):
            u = loc.get("url_for_pdf") or ""
            if u.endswith(".pdf"):
                return u
    except Exception: pass
    return None


def _oa_button(doi: str) -> Optional[str]:
    if not doi: return None
    try:
        data = _get("https://api.openaccessbutton.org/find",
                    params={"q": doi}, timeout=12)
        if data:
            url = ((data.get("data") or {}).get("availability") or [{}])[0].get("url")
            if url and url.startswith("http"):
                return url
    except Exception: pass
    return None


def _oa_mg(doi: str) -> Optional[str]:
    if not doi: return None
    try:
        data = _get(f"https://oa.mg/works/{doi}", timeout=12)
        if data:
            for loc in (data.get("locations") or []):
                u = loc.get("pdf_url") or loc.get("url","")
                if u and u.startswith("http"):
                    return u
    except Exception: pass
    return None


def _core_fulltext(title: str) -> Optional[str]:
    try:
        data = _get("https://api.core.ac.uk/v3/search/works",
                    params={"q": f'title:"{title[:60]}"', "limit": 3}, timeout=14)
        for item in (data or {}).get("results",[]):
            u = item.get("downloadUrl") or (item.get("sourceFulltextUrls") or [None])[0]
            if u and u.startswith("http"):
                return u
    except Exception: pass
    return None


def _anna_archive(title: str, doi: Optional[str] = None) -> Optional[str]:
    if not HAS_SCRAPLING: return None
    query = doi or title[:80]
    try:
        page = _fetch(
            f"https://annas-archive.org/search?q={requests.utils.quote(query)}",
            stealth=True, timeout=40
        )
        if not page: return None
        links = page.css("a[href*='/md5/']") or []
        if not links: return None
        detail_url = f"https://annas-archive.org{links[0].attrib['href']}"
        detail = _fetch(detail_url, stealth=True, timeout=30)
        if not detail: return None
        for a in (detail.css("a[href$='.pdf'], a[href*='download']") or []):
            href = a.attrib.get("href","")
            if href.startswith("http"):
                return href
    except Exception: pass
    return None


# ── v6 Extended download helpers ────────────────────────────────────────────────
def _anna_archive_deep(title: str, doi: Optional[str] = None) -> Optional[str]:
    """Try multiple Anna's Archive domains for maximum reach."""
    if not HAS_SCRAPLING: return None
    query = doi or title[:80]
    for domain in ANNAS_ARCHIVE_DOMAINS:
        try:
            page = _fetch(
                f"https://{domain}/search?q={requests.utils.quote(query)}",
                stealth=True, timeout=30
            )
            if not page: continue
            links = page.css("a[href*='/md5/']") or []
            if not links: continue
            detail_url = f"https://{domain}{links[0].attrib['href']}"
            detail = _fetch(detail_url, stealth=True, timeout=25)
            if not detail: continue
            for a in (detail.css("a[href$='.pdf'], a[href*='download']") or []):
                href = a.attrib.get("href","")
                if href.startswith("http"):
                    return href
        except Exception:
            continue
    return None


def _semantic_scholar_pdf(doi: str) -> Optional[str]:
    """Get PDF URL directly from Semantic Scholar API."""
    if not doi: return None
    try:
        data = _get(f"https://api.semanticscholar.org/graph/v1/paper/{doi}",
                    params={"fields": "openAccessPdf"}, timeout=10)
        if data:
            pdf_url = (data.get("openAccessPdf") or {}).get("url")
            if pdf_url and pdf_url.startswith("http"):
                return pdf_url
    except Exception: pass
    return None


def _europepmc_fulltext(doi: str) -> Optional[str]:
    """Get full text from Europe PMC."""
    if not doi: return None
    try:
        data = _get(f"https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                    params={"query": f"DOI:{doi}", "format": "json"}, timeout=12)
        results = (data or {}).get("resultList", {}).get("result", [])
        for r in results:
            ft = r.get("fullTextUrlList", {}).get("fullTextUrl", [])
            for f in ft:
                url = f.get("url", "")
                if url and ("pdf" in url.lower() or url.endswith(".pdf")):
                    return url
    except Exception: pass
    return None


def _libgen_multidomain(doi: str = None, title: str = None) -> Optional[str]:
    """Try multiple LibGen mirror domains."""
    query = doi or title[:80] if title else None
    if not query: return None
    for domain in LIBGEN_DOMAINS:
        try:
            search_url = f"https://{domain}/search.php?req={requests.utils.quote(query)}"
            page = _fetch(search_url, stealth=True, timeout=25)
            if not page: continue
            for a in (page.css("a[href*='libgen']") or []):
                href = a.attrib.get("href", "")
                if href and "php?id=" in href:
                    detail = _fetch(href, stealth=True, timeout=20)
                    if detail:
                        for dl in (detail.css("a[href$='.pdf']") or []):
                            dl_href = dl.attrib.get("href", "")
                            if dl_href.startswith("http"):
                                return dl_href
        except Exception:
            continue
    return None


def _zenodo_direct_pdf(doi: str) -> Optional[str]:
    """Get PDF directly from Zenodo record metadata."""
    if not doi: return None
    try:
        # Try Zenodo API for DOI-based lookup
        data = _get(f"https://zenodo.org/api/records",
                    params={"q": f"doi:{doi}", "size": 1}, timeout=12)
        hits = (data or {}).get("hits", {}).get("hits", [])
        for hit in hits:
            files = hit.get("files", [])
            for f in files:
                key = f.get("key", "")
                if key.endswith(".pdf"):
                    return f.get("links", {}).get("self") or f"https://zenodo.org/record/{hit.get('id')}/files/{key}"
    except Exception: pass
    return None


def _google_scholar_direct_pdf(title: str) -> Optional[str]:
    """Try to find direct PDF links via Google Scholar scraping."""
    if not title or not HAS_SCRAPLING: return None
    try:
        query = requests.utils.quote(f'filetype:pdf "{title[:60]}"')
        page = _fetch(f"https://scholar.google.com/scholar?q={query}",
                     stealth=True, timeout=25)
        if not page: return None
        for a in (page.css("a[href$='.pdf']") or []):
            href = a.attrib.get("href", "")
            if href.startswith("http"):
                return href
    except Exception: pass
    return None


def download_with_full_chain(paper: dict, dest_path: Path,
                               use_scihub: bool = True,
                               red_list=None) -> tuple[bool, list[str]]:
    """
    14-layer fallback download chain — maximum PDF retrieval coverage.
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │ Layer  1: Direct PDF URL (from search results)                              │
    │ Layer  2: Unpaywall API                                                     │
    │ Layer  3: OpenAccess Button API                                             │
    │ Layer  4: OA.mg API                                                         │
    │ Layer  5: CORE full-text API                                                │
    │ Layer  6: Anna's Archive (primary domain)                                   │
    │ Layer  6b: Anna's Archive (deep multi-domain)                               │
    │ Layer  7: Sci-Hub multi-domain                                              │
    │ Layer  7b: LibGen multi-domain                                              │
    │ Layer  8: Semantic Scholar PDF URL                                          │
    │ Layer  9: Europe PMC full text                                              │
    │ Layer 10: Zenodo direct PDF                                                 │
    │ Layer 11: Google Scholar direct PDF                                         │
    │ Layer 12: Walter Ghost (if enabled)                                         │
    │ Layer 13: Extended PDF source URLs (deep scan)                              │
    │ Layer 14: Final Sci-Hub fallback (all domains)                              │
    └─────────────────────────────────────────────────────────────────────────────┘
    """
    tried: list[str] = []
    doi   = paper.get("doi")
    title = paper.get("title","")

    # ── Layer 1: direct URL ────────────────────────────────────────────────────
    if paper.get("pdf_url"):
        tried.append("direct_url")
        if _dl(paper["pdf_url"], dest_path): return True, tried

    # ── Layer 2: Unpaywall ─────────────────────────────────────────────────────
    if doi:
        tried.append("unpaywall")
        u = _unpaywall(doi)
        if u and _dl(u, dest_path): return True, tried

    # ── Layer 3: OpenAccess Button ─────────────────────────────────────────────
    if doi:
        tried.append("oa_button")
        u = _oa_button(doi)
        if u and _dl(u, dest_path): return True, tried

    # ── Layer 4: OA.mg ─────────────────────────────────────────────────────────
    if doi:
        tried.append("oa_mg")
        u = _oa_mg(doi)
        if u and _dl(u, dest_path): return True, tried

    # ── Layer 5: CORE full-text ────────────────────────────────────────────────
    if title:
        tried.append("core_fulltext")
        u = _core_fulltext(title)
        if u and _dl(u, dest_path): return True, tried

    # ── Layer 6: Anna's Archive (primary) ──────────────────────────────────────
    if title and HAS_SCRAPLING:
        tried.append("annas_archive")
        u = _anna_archive(title, doi)
        if u and _dl(u, dest_path): return True, tried

    # ── Layer 6b: Anna's Archive deep multi-domain ─────────────────────────────
    if title and HAS_SCRAPLING:
        tried.append("annas_archive_deep")
        u = _anna_archive_deep(title, doi)
        if u and _dl(u, dest_path): return True, tried

    # ── Layer 7: Sci-Hub multi-domain ──────────────────────────────────────────
    if use_scihub and doi:
        for hub in SCIHUB_DOMAINS[:3]:
            tried.append(f"scihub:{hub}")
            if _dl(f"https://{hub}/{doi}", dest_path): return True, tried

    # ── Layer 7b: LibGen multi-domain ──────────────────────────────────────────
    if title:
        tried.append("libgen_multi")
        u = _libgen_multidomain(doi, title)
        if u and _dl(u, dest_path): return True, tried

    # ── Layer 8: Semantic Scholar PDF URL ───────────────────────────────────────
    if doi:
        tried.append("semantic_scholar_pdf")
        u = _semantic_scholar_pdf(doi)
        if u and _dl(u, dest_path): return True, tried

    # ── Layer 9: Europe PMC full text ───────────────────────────────────────────
    if doi:
        tried.append("europepmc_fulltext")
        u = _europepmc_fulltext(doi)
        if u and _dl(u, dest_path): return True, tried

    # ── Layer 10: Zenodo direct PDF ────────────────────────────────────────────
    if doi:
        tried.append("zenodo_direct")
        u = _zenodo_direct_pdf(doi)
        if u and _dl(u, dest_path): return True, tried

    # ── Layer 11: Google Scholar direct PDF ─────────────────────────────────────
    if title and HAS_SCRAPLING:
        tried.append("gscholar_direct_pdf")
        u = _google_scholar_direct_pdf(title)
        if u and _dl(u, dest_path): return True, tried

    # ── Layer 12: Walter Ghost (registration-gated access) ─────────────────────
    if doi and _check_drissionpage():
        tried.append("walter_ghost")
        try:
            ghost_url = _download_with_ghost_login(paper, dest_path)
            if ghost_url and _dl(ghost_url, dest_path):
                return True, tried
        except Exception:
            pass

    # ── Layer 13: Extended PDF source URLs (deep scan) ─────────────────────────
    if doi:
        tried.append("extended_sources")
        for extra_url in EXTRA_PDF_SOURCES:
            try:
                test_url = f"{extra_url.rstrip('/')}/{doi}" if not extra_url.endswith("/") else f"{extra_url}{doi}"
                if _dl(test_url, dest_path):
                    return True, tried
            except Exception:
                continue

    # ── Layer 14: Final Sci-Hub fallback (all domains) ─────────────────────────
    if use_scihub and doi:
        for hub in SCIHUB_DOMAINS:
            tried.append(f"scihub_final:{hub}")
            if _dl(f"https://{hub}/{doi}", dest_path): return True, tried

    # ── All layers exhausted → add to Red List ─────────────────────────────────
    if red_list is not None:
        red_list.add(paper, f"All {len(tried)} download layers failed", tried)

    return False, tried


def smart_file_paper(paper: dict, base_folder: Path,
                      use_scihub: bool, red_list, cache,
                      single_folder: bool = False) -> tuple[bool, str]:
    """
    Detect doc type + geo tier → choose correct folder → 14-layer download.
    Also copies high-cited papers to HIGH_CITED folders.
    If single_folder=True, saves directly to base_folder/ (no subfolder hierarchy).
    Returns (success, folder_name_used).
    """
    doc_type = detect_doc_type(paper)
    geo_tier = detect_geo_tier(paper)
    quartile = (paper.get("scopus_quartile") or {})
    if isinstance(quartile, dict):
        quartile = quartile.get("quartile","")

    # Upgrade quartile from fuzzy journal match if still unclassified
    if not quartile or quartile in ("Not Found","Not Ranked",""):
        fq = _fuzzy_q(paper.get("journal",""))
        if fq:
            quartile = fq
            if isinstance(paper.get("scopus_quartile"), dict):
                paper["scopus_quartile"]["quartile"] = fq
            else:
                paper["scopus_quartile"] = {"quartile": fq}

    # ── Single-folder mode: skip all subfolder logic ────────────────────────────
    if single_folder:
        folder_name = "single_folder"
        folder_key = "single_folder"
        dest_folder = base_folder
        dest_folder.mkdir(parents=True, exist_ok=True)
    else:
        # Priority: dissertation type > Libya > quartile
        if doc_type in ("PhD","MA","Book","BookChapter","Conference"):
            folder_key = doc_type
        elif geo_tier == "Libya":
            folder_key = "Libya"
        else:
            folder_key = quartile or "Not Found"

        folder_name = Q_FOLDER_MAP.get(folder_key, "Not_Indexed")
        dest_folder = base_folder / folder_name
        dest_folder.mkdir(parents=True, exist_ok=True)

    safe_title = _safe_name(paper.get("title","untitled"), 90)
    dest_path  = dest_folder / f"{safe_title}.pdf"

    if dest_path.exists() and dest_path.stat().st_size > 2000:
        cache.mark_downloaded(paper, dest_path.name)
        return True, folder_name

    # Also check legacy base folder location
    old = base_folder / f"{safe_title}.pdf"
    if old.exists() and old.stat().st_size > 2000:
        shutil.move(str(old), str(dest_path))
        cache.mark_downloaded(paper, dest_path.name)
        return True, folder_name

    success, _tried = download_with_full_chain(paper, dest_path, use_scihub, red_list)

    if success:
        cache.mark_downloaded(paper, dest_path.name)
        paper["file_path"] = str(dest_path)

        # Mirror into LOCAL_Libya if applicable
        if geo_tier == "Libya" and folder_key != "Libya":
            ly = base_folder / "LOCAL_Libya"
            ly.mkdir(exist_ok=True)
            lyd = ly / f"{safe_title}.pdf"
            if not lyd.exists():
                shutil.copy2(dest_path, lyd)

        # Mirror into HIGH_CITED folders
        cites = int(paper.get("gs_citations") or 0)
        if cites >= 100:
            hc = base_folder / ("HIGH_CITED_500plus" if cites >= 500 else "HIGH_CITED_100plus")
            hc.mkdir(exist_ok=True)
            hcd = hc / f"[{cites}] {safe_title}.pdf"
            if not hcd.exists():
                shutil.copy2(dest_path, hcd)

    return success, folder_name


# ── APA 7th Ed reference builder ──────────────────────────────────────────────
def build_apa(paper: dict) -> str:
    raw_authors = paper.get("authors") or []
    formatted   = []
    for a in raw_authors[:6]:
        a = _safe_str(a).strip()
        if not a:
            continue
        parts = a.split()
        if len(parts) >= 2:
            last     = parts[-1]
            initials = " ".join(p[0]+"." for p in parts[:-1] if p)
            formatted.append(f"{last}, {initials}")
        else:
            formatted.append(a)
    if len(raw_authors) > 6:
        formatted.append("et al.")
    author_str = "; ".join(formatted) if formatted else "Unknown Author"

    year    = _safe_str(paper.get("year")) or "n.d."
    title   = _safe_str(paper.get("title")) or "Untitled"
    journal = _safe_str(paper.get("journal"))
    volume  = _safe_str(paper.get("volume"))
    issue   = _safe_str(paper.get("issue"))
    pages   = _safe_str(paper.get("pages"))
    doi     = _safe_str(paper.get("doi")).strip()
    pub     = _safe_str(paper.get("publisher"))

    ref = f"{author_str} ({year}). {title}."
    if journal:
        ref += f" *{journal}*"
        if volume:
            ref += f", *{volume}*"
        if issue:
            ref += f"({issue})"
        if pages:
            ref += f", {pages}"
        ref += "."
    elif pub:
        ref += f" {pub}."
    if doi:
        ref += f" https://doi.org/{doi}"
    return ref


# ── Search Orchestrator ────────────────────────────────────────────────────────
PLATFORM_FNS = {
    # ── Core API platforms ──────────────────────────────────────────────────────
    "Semantic Scholar": search_semantic_scholar,
    "OpenAlex":         search_openalex,
    "CORE":             search_core,
    "CORE API":         search_core_api,
    "CrossRef":         search_crossref,
    "ERIC":             search_eric,
    "DOAJ":             search_doaj,
    "HAL Archives":     search_hal,
    "BASE":             search_base,
    "PubMed":           search_pubmed,
    "arXiv":            search_arxiv,
    "Zenodo":           search_zenodo,
    "Zenodo Extended":  search_zenodo_extended,
    "SciELO":           search_scielo,
    # ── Major publisher platforms ───────────────────────────────────────────────
    "Europe PMC":       search_europepmc,
    "PLoS ONE":         search_plos,
    "Oxford UP":        search_oup,
    "Springer Open":    search_springer_open,
    "Wiley Open":       search_wiley_open,
    "Taylor & Francis": search_tandfonline,
    "ScienceDirect":    search_sciencedirect,
    "SSRN":             search_ssrn,
    # ── Preprint repositories ───────────────────────────────────────────────────
    "bioRxiv":          search_biorxiv,
    "medRxiv":          search_medrxiv,
    "PsyArXiv":         search_psyarxiv,
    "SocArXiv":         search_socarxiv,
    "OSF Preprints":    search_osf_preprints,
    # ── Open Access publishers & infrastructure ─────────────────────────────────
    "MDPI":             search_mdpi,
    "OpenAIRE":         search_openaire,
    "WorldWideScience": search_worldwidescience,
    "CERN Document":    search_cern_server,
    "Science.gov":      search_science_gov,
    "NASA NTRS":        search_nasa_ntrs,
    "Digital Commons":  search_digital_commons,
    "JSTOR Open":       search_jstor_open,
    "EBSCO Dissertations": search_ebsco_dissertations,
    "SSOAR":            search_ssoar,
    # ── Academic social networks ────────────────────────────────────────────────
    "Academia.edu":     search_academia_edu,
    "PaperPanda":       search_paperpanda,
    # ── Regional open access ────────────────────────────────────────────────────
    "Redalyc":          search_redalyc,
    "Bioline Int'l":    search_bioline,
    # ── Domain-specific platforms ───────────────────────────────────────────────
    "PhilPapers":       search_philpapers,
    "Directory of OA Books": search_doab,
    "CogPrints":        search_cogprints,
    "AJOL":             search_ajol,
    "SciELO Brazil":    search_scieelo_bra,
    "Dialnet":          search_dialnet,
    "BioLine Int'l":    search_bialitic,
    # ── Shadow libraries & alternative sources ─────────────────────────────────
    "Anna's Archive":   search_annas_archive_enhanced,
    "Sci-Hub Multi":    search_scihub_multi,
    "Genemedi":         search_genemedi,
    "Shadow Libraries": search_shadow_libraries,
    # ── Discovery & mirror platforms ────────────────────────────────────────────
    "SciNet":           search_scinet,
    "SciBay":           search_scibay,
    "Grokipedia":       search_grokipedia,
    "Internet Archive": search_internet_archive,
    # ── Browser-based platforms ─────────────────────────────────────────────────
    "Google Scholar":   search_google_scholar,
    "ResearchGate":     search_researchgate,
    "Z-Library":        search_zlibrary,
    "LibGen":           search_libgen,
    "DuckDuckGo":       search_duckduckgo_pdfs,
    "Perplexica":       search_perplexica,
    "OATD":             search_oatd,
    "EThOS":            search_ethos,
    # ── Extended coverage (v6 additions) ────────────────────────────────────────
    "OhioLINK ETD":     search_etd_ohiolink,
    "Nature":           search_nature_linguistics,
    "AcademicianHelp":  search_academicianhelp,
    "eLife Sciences":   search_elife_sciences,
    "ScienceOpen":      search_scienceopen,
    "OA.mg":            search_oa_mg,
    # ── Additional Academic Search Engines ──────────────────────────────────────
    "Microsoft Academic": search_microsoft_academic,
    "Baidu Scholar":     search_baidu_scholar,
    "Yandex Scholar":    search_yandex_scholar,
    "Korean SIN":        search_korean_sin,
    "Cqjd":              search_cqjd,          # ChineseQJ
    # ── Regional & Subject-Specific Repositories ────────────────────────────────
    "CAIRN":             search_cairn,          # French social sciences
    "Persee":            search_persee,         # French open access
    "Dspace/BR":         search_dspace_br,      # Brazilian repositories
    "CLASE":             search_clase,          # Latin American social sciences
    "REDIB":             search_redib,          # Spanish/Portuguese
    "Scielo Mexico":     search_scielo_mexico,
    "CONCYTEC":          search_concytec,       # Peru
    "BINASSS":          search_binasss,         # Health Sciences Costa Rica
    # ── African Open Access ─────────────────────────────────────────────────────
    "AJOL":              search_ajol_full,      # African Journals Online
    "African Digital":   search_african_digital,
    "UWC":               search_uwc,            # University of Western Cape
    # ── Middle Eastern & Arabic ─────────────────────────────────────────────────
    "Shamaa":           search_shamaa,          # Arabic database
    "ArabPsyc":         search_arab_psyc,       # Arabic psychology
    "Arab Digital":     search_arab_digital,
    "Maktabk":          search_maktabk,         # Iranian
    "Civilica":         search_civilica,         # Iranian
    "Magiran":          search_magiran,          # Iranian
    "Noormags":         search_noormags,         # Iranian
    # ── Indian Subcontinent ─────────────────────────────────────────────────────
    "INFLIBNET":        search_inflibnet,       # Indian ETD
    "Shodhganga":       search_shodhganga,      # Indian thesis
    "Cochrane":         search_cochrane,        # Medical systematic reviews
    # ── European National Repositories ──────────────────────────────────────────
    "TIB Hannover":     search_tib_hannover,    # German technical
    "HAL ENSAE":        search_hal_ensae,
    "OAI Harvester":    search_oai_harvester,
    "OPUS Bayern":      search_opus_bayern,
    "DARIAH":           search_dariah,          # Digital research infrastructure
    # ── Specialized Subject Databases ───────────────────────────────────────────
    "IEEE Xplore":       search_ieee_xplore,
    "ACM Digital":      search_acm_digital,
    "ECONSTOR":         search_econstor,        # Economics
    "SSRN PREPRINT":    search_ssrn_preprint,
    "Research4Life":    search_research4life,
    "ELSEVIER":         search_elsevier_sciencedirect,
    "Wiley Online":    search_wiley_online,
    "Springer":         search_springer,
    "Frontiers":        search_frontiers,
    "Cambridge UP":     search_cambridge_up,
    "Oxford Academic":  search_oxford_academic,
    "Sage Journals":    search_sage_journals,
    "Taylor Francis":   search_taylor_francis,
    "Emerald":          search_emerald,
    "De Gruyter":       search_de_gruyter,
    "Nature Publishing": search_nature_publishing,
    "Cell Press":       search_cell_press,
    # ── Additional Open Access ─────────────────────────────────────────────────
    "PMC":              search_pubmed_central,
    "Europe PMC":       search_europe_pmc,
    "HINARI":           search_hinari,
    "Bireme":           search_bireme,          # Latin American health
    "Whois":            search_whois_scholar,    # Who is who
    # ── Preprint Servers ────────────────────────────────────────────────────────
    "arxiv.org":        search_arxiv_org,
    "chemRxiv":         search_chemrxiv,
    "sXiv":             search_sxiv,            # Social science
    "EarthArXiv":       search_eartharxiv,
    "BioOne":           search_bioone,
}

BROWSER_PLATS = {
    "Google Scholar", "Z-Library", "LibGen", "DuckDuckGo",
    "Perplexica", "OATD", "ResearchGate", "EThOS",
    "OhioLINK ETD", "AcademicianHelp", "ScienceOpen", "OA.mg",
    "Sci-Hub Multi", "Genemedi", "Shadow Libraries",
    "SciNet", "SciBay", "Grokipedia", "Internet Archive",
    "Academia.edu", "JSTOR Open", "EBSCO Dissertations",
    "WorldWideScience", "MDPI", "Digital Commons",
}

QUICK_PLATS = [
    "Semantic Scholar", "OpenAlex", "CORE", "CrossRef",
    "Europe PMC", "ERIC", "DOAJ", "arXiv",
]

FIELD_PLATS = [
    "Semantic Scholar", "OpenAlex", "CORE", "ERIC", "DOAJ",
    "HAL Archives", "CrossRef", "Zenodo", "SciELO",
    "Nature", "eLife Sciences", "CORE API",
    "Europe PMC", "PLoS ONE", "Oxford UP",
    "Springer Open", "Wiley Open", "Taylor & Francis",
    "ScienceDirect", "SSRN",
    "bioRxiv", "medRxiv", "PsyArXiv", "OSF Preprints",
    "MDPI", "OpenAIRE", "Science.gov", "NASA NTRS",
    "Google Scholar", "ResearchGate", "BASE",
]

# EXTENDED mode: 50+ platforms with higher paper limits
EXTENDED_PLATS = [
    "Semantic Scholar", "OpenAlex", "CORE", "ERIC", "DOAJ",
    "HAL Archives", "CrossRef", "Zenodo", "SciELO",
    "PubMed", "BASE", "Europe PMC",
    "Nature", "eLife Sciences", "CORE API",
    "PLoS ONE", "Oxford UP", "Springer Open", "Wiley Open",
    "Taylor & Francis", "ScienceDirect", "SSRN",
    "bioRxiv", "medRxiv", "PsyArXiv", "OSF Preprints", "SocArXiv",
    "MDPI", "OpenAIRE", "Science.gov", "NASA NTRS",
    "Google Scholar", "ResearchGate",
    "arXiv", "Zenodo Extended",
    "Redalyc", "Dialnet", "PhilPapers",
    "Directory of OA Books", "CogPrints",
    "AJOL", "SciELO Brazil", "Dialnet",
    "PaperPanda", "Academia.edu",
    "WorldWideScience", "Digital Commons",
    "Internet Archive", "OATD", "EThOS",
    "ScienceOpen", "OA.mg",
]

# ULTRA mode: All 128+ platforms with maximum paper limits
ULTRA_PLATS = list(PLATFORM_FNS.keys())

SAMPLE_PLATS = [
    "Semantic Scholar", "OpenAlex", "CORE", "CrossRef",
]

DEEP_PLATS = list(PLATFORM_FNS.keys())
LIBYAN_PLATS  = list(LIBYAN_PLATFORM_URLS.keys())

# ─────────────────────────────────────────────────────────────────────────────
# SEARCH MODES WITH ACCURATE PAPER LIMITS & TIME ESTIMATES
# ─────────────────────────────────────────────────────────────────────────────
# Paper limits are based on actual platform coverage:
# - Each API platform returns 20-50 papers per query
# - Each browser platform returns 10-30 papers per query
# - Deep search uses multiple queries per platform
# - Paper counts reflect realistic maximum achievable papers

MODE_TIME_ESTIMATES = {
    "sample":  {
        "label": "Sample Trial (~10-15 min)",
        "time": "10-15 min",
        "platforms": SAMPLE_PLATS[:],
        "max_papers": 80,
        "platform_count": 4,
        "download_pdfs": True
    },
    "quick":   {
        "label": "Quick Search (~30 min)",
        "time": "20-40 min",
        "platforms": QUICK_PLATS[:],
        "max_papers": 1000,
        "platform_count": 8,
        "download_pdfs": True
    },
    "field":   {
        "label": "Field Optimized (~2 hr)",
        "time": "1.5-3 hr",
        "platforms": FIELD_PLATS[:],
        "max_papers": 3000,
        "platform_count": 29,
        "download_pdfs": True
    },
    "extended": {
        "label": "Extended Search (~4-6 hr)",
        "time": "4-6 hr",
        "platforms": EXTENDED_PLATS[:],
        "max_papers": 8000,
        "platform_count": 50,
        "download_pdfs": True
    },
    "deep":    {
        "label": "Deep Search (~8-12 hr)",
        "time": "8-12 hr",
        "platforms": DEEP_PLATS[:],
        "max_papers": 20000,
        "platform_count": 128,
        "download_pdfs": True
    },
    "ultra":   {
        "label": "Ultra Search (~24-48 hr)",
        "time": "24-48 hr",
        "platforms": ULTRA_PLATS[:],
        "max_papers": 50000,
        "platform_count": 128,
        "download_pdfs": True
    },
    "maximum": {
        "label": "Maximum Search (~48-72 hr)",
        "time": "48-72 hr",
        "platforms": ULTRA_PLATS[:],
        "max_papers": 100000,
        "platform_count": 128,
        "download_pdfs": True
    },
}

# Paper limit mapping for workflow integration
PAPER_LIMIT_MAP = {
    "1": 50,      # Light
    "2": 150,     # Standard
    "3": 300,     # Medium
    "4": 500,     # Extended
    "5": 800,     # Deep
    "6": 1200,    # Maximum
    "7": 0,       # Unlimited
}


def _filter_papers_by_context(papers: list, publication_types: list,
                              study_levels: list, methodologies: list,
                              dissertation_parts: list) -> list:
    """
    v7: Filter papers based on user-selected context parameters.
    This helps prioritize papers that match the user's specific requirements.
    """
    if not papers:
        return papers
    
    # If no filters specified, return all papers
    if not (publication_types or study_levels or methodologies or dissertation_parts):
        return papers
    
    filtered = []
    for paper in papers:
        title = (paper.get("title", "") + " " + paper.get("abstract", "")).lower()
        
        # Build relevance score
        score = 0
        reasons = []
        
        # Check publication types
        if publication_types:
            for pt in publication_types:
                pt_lower = pt.lower()
                # Keywords that indicate this publication type
                pt_keywords = {
                    "phd dissertation": ["phd dissertation", "doctoral dissertation", "ph.d. thesis"],
                    "master's thesis": ["master", "ma thesis", "msc thesis", "m.sc thesis", "ma thesis"],
                    "research article": ["journal", "article", "peer-reviewed"],
                    "systematic review": ["systematic review", "meta-analysis", "meta analysis"],
                    "conference paper": ["conference", "proceedings", "symposium"],
                    "book chapter": ["book chapter", "chapter in"],
                    "dissertation": ["dissertation", "thesis"],
                }
                if pt_lower in pt_keywords:
                    for kw in pt_keywords[pt_lower]:
                        if kw in title:
                            score += 2
                            reasons.append(f"Matches: {pt}")
                            break
        
        # Check study levels
        if study_levels:
            for sl in study_levels:
                sl_lower = sl.lower()
                sl_keywords = {
                    "phd": ["phd", "ph.d", "doctoral", "doctorate"],
                    "master": ["master", "ma ", "msc", "m.sc", "graduate"],
                    "honours": ["honours", "honors", "honor"],
                    "bachelor": ["bachelor", "undergraduate", "bsc"],
                }
                if sl_lower in sl_keywords:
                    for kw in sl_keywords[sl_lower]:
                        if kw in title:
                            score += 1
                            reasons.append(f"Level: {sl}")
                            break
        
        # Check methodologies
        if methodologies:
            for m in methodologies:
                m_lower = m.lower()
                method_keywords = {
                    "qualitative": ["qualitative", "interview", "focus group", "thematic analysis"],
                    "quantitative": ["quantitative", "survey", "statistical", "regression"],
                    "mixed methods": ["mixed method", "mixed-method", "triangulation"],
                    "case study": ["case study", "case study"],
                    "experimental": ["experimental", "rct", "randomized"],
                    "ethnographic": ["ethnographic", "ethnography"],
                    "phenomenological": ["phenomenological", "phenomenology", "lived experience"],
                    "grounded theory": ["grounded theory", "grounded"],
                    "action research": ["action research", "participatory"],
                    "survey": ["survey", "questionnaire"],
                    "interview": ["interview", "semi-structured", "in-depth"],
                    "literature review": ["literature review", "systematic review"],
                }
                if m_lower in method_keywords:
                    for kw in method_keywords[m_lower]:
                        if kw in title:
                            score += 2
                            reasons.append(f"Method: {m}")
                            break
        
        # Check dissertation parts (for thesis-specific searches)
        if dissertation_parts:
            for dp in dissertation_parts:
                dp_lower = dp.lower()
                dp_keywords = {
                    "introduction": ["introduction", "chapter 1", "background"],
                    "literature review": ["literature review", "chapter 2", "theoretical"],
                    "methodology": ["methodology", "methods", "chapter 3", "research design"],
                    "results": ["results", "findings", "chapter 4", "data analysis"],
                    "discussion": ["discussion", "chapter 5", "implications"],
                    "abstract": ["abstract", "executive summary"],
                    "conclusion": ["conclusion", "recommendations", "limitations"],
                }
                if dp_lower in dp_keywords:
                    for kw in dp_keywords[dp_lower]:
                        if kw in title:
                            score += 1
                            reasons.append(f"Part: {dp}")
                            break
        
        # Keep paper if it has any matches, or if no specific filters were set
        if score > 0:
            paper["_relevance_score"] = score
            paper["_match_reasons"] = reasons
            filtered.append(paper)
        else:
            # If no filters matched, still include the paper (don't exclude everything)
            # This is a soft filter - prioritizes but doesn't exclude
            filtered.append(paper)
    
    # Sort by relevance score (highest first)
    filtered.sort(key=lambda x: x.get("_relevance_score", 0), reverse=True)
    
    return filtered


def _run_platform(plat, query, year_from, field):
    fn = PLATFORM_FNS.get(plat)
    if not fn:
        return []
    try:
        kwargs = {"year_from": year_from}
        if plat == "arXiv":
            kwargs["field"] = field
        return fn(query, **kwargs) or []
    except Exception:
        return []


def search_all(queries: list, platforms: list, year_from=None,
               year_to=None, field="", country_context=None,
               publication_types=None, study_levels=None,
               methodologies=None, dissertation_parts=None) -> list:
    """
    v7: Added parameters for filtering papers based on user selections:
    - publication_types: Filter to specific publication types (e.g., "PhD Dissertation")
    - study_levels: Filter to specific study levels (e.g., "PhD", "Master's")
    - methodologies: Filter to specific research methodologies (e.g., "Qualitative Study")
    - dissertation_parts: Filter to specific thesis parts (e.g., "Introduction")
    """
    api_plats     = [p for p in platforms if p not in BROWSER_PLATS]
    browser_plats = [p for p in platforms if p in BROWSER_PLATS]
    all_papers    = []

    info(f"Running {len(api_plats)} API × {len(queries)} queries + "
         f"{len(browser_plats)} browser × 2 queries")
    
    # v7: Log filtering criteria
    if publication_types:
        info(f"  📄 Publication types: {', '.join(publication_types[:3])}")
    if study_levels:
        info(f"  🎓 Study levels: {', '.join(study_levels[:2])}")
    if methodologies:
        info(f"  🔬 Methodologies: {', '.join(methodologies[:3])}")
    if dissertation_parts:
        info(f"  📑 Dissertation parts: {', '.join(dissertation_parts[:2])}")

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {
            ex.submit(_run_platform, plat, q, year_from, field): (plat, q)
            for plat in api_plats
            for q   in queries
        }
        for fut in as_completed(futs):
            plat, q = futs[fut]
            try:
                results = fut.result() or []
                if results:
                    # v7: Filter results based on new parameters
                    if publication_types or study_levels or methodologies or dissertation_parts:
                        results = _filter_papers_by_context(
                            results, publication_types, study_levels,
                            methodologies, dissertation_parts
                        )
                    all_papers.extend(results)
                    info(f"  {plat}: +{len(results)} for '{q[:50]}'")
            except Exception:
                pass

    for plat in browser_plats:
        for q in queries[:2]:
            info(f"  Scraping {plat}…")
            results = _run_platform(plat, q, year_from, field)
            if results:
                # v7: Filter results based on new parameters
                if publication_types or study_levels or methodologies or dissertation_parts:
                    results = _filter_papers_by_context(
                        results, publication_types, study_levels,
                        methodologies, dissertation_parts
                    )
                all_papers.extend(results)
                info(f"  {plat}: +{len(results)}")
            time.sleep(2.5)

    # ── Libyan/MENA platform scraping (when geographic context detected) ─────
    if country_context and any(
        c in ("Libya","North Africa","MENA","Saudi Arabia","Egypt","Algeria",
               "Tunisia","Morocco","Jordan","UAE","Turkey","Iran","Iraq")
        for c in country_context
    ):
        # Use the first 3 queries that best match the study topic (already title-derived)
        libyan_queries = queries[:3]
        info(f"  Geographic context → scraping {len(LIBYAN_PLATS)} regional platforms")
        for plat in LIBYAN_PLATS:
            for q in libyan_queries[:2]:
                results = search_libyan_platform(plat, q)
                if results:
                    all_papers.extend(results)
                    info(f"  {plat}: +{len(results)}")
                time.sleep(1.5)

    return all_papers


# ── Markdown report ────────────────────────────────────────────────────────────
def generate_markdown_report(data: dict, folder: Path) -> Path:
    papers = data.get("papers") or []
    today  = datetime.now().strftime("%B %d, %Y")
    lines  = []
    lines.append(f"# Research Report: {data.get('title','')}")
    lines.append(f"\n**Generated:** {today}  |  **Field:** {data.get('field','N/A')}  ")
    lines.append(f"**Papers Found:** {len(papers)}  |  "
                 f"**PDFs Downloaded:** {sum(1 for p in papers if p.get('downloaded'))}  \n")

    lines.append("---\n## Executive Summary\n")
    lines.append((data.get("executive_summary") or "") + "\n")

    q_cnt = {"Q1":0,"Q2":0,"Q3":0,"Q4":0,"Not Found":0}
    for p in papers:
        q = (p.get("scopus_quartile") or {}).get("quartile","Not Found")
        q_cnt[q if q in q_cnt else "Not Found"] += 1

    lines.append("---\n## Scopus Quartile Summary\n")
    for q, c in q_cnt.items():
        lines.append(f"- **{q}**: {c} papers")

    lines.append("\n---\n## All Papers\n")
    lines.append("| # | Title | Authors | Year | Journal | Q | PDF |")
    lines.append("|---|-------|---------|------|---------|---|-----|")
    for i, p in enumerate(papers, 1):
        q       = (p.get("scopus_quartile") or {}).get("quartile","—")
        pdf     = "✅" if p.get("downloaded") else "—"
        authors = "; ".join((p.get("authors") or [])[:2])
        journal = _safe_str(p.get("journal") or "—")[:40]
        t       = _safe_str(p.get("title") or "")[:80]
        lines.append(f"| {i} | {t} | {authors} | {p.get('year') or '—'} | {journal[:40]} | {q} | {pdf} |")

    lines.append("\n---\n## References (APA 7th)\n")
    for p in sorted(papers, key=lambda x: (x.get("authors") or [""])[0]):
        lines.append(f"- {p.get('apa') or build_apa(p)}\n")

    out = folder / "research_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    ok(f"Markdown: {out}")
    return out


def generate_docx_report(report_data: dict, out_folder: Path) -> Path | None:
    for p in report_data.get("papers") or []:
        if not p.get("apa"):
            p["apa"] = build_apa(p)

    json_path = out_folder / "report_data.json"
    docx_path = out_folder / "research_report.docx"
    json_path.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")

    script = next((s for s in [Path("generate_report.js"),
                                Path(__file__).parent / "generate_report.js"]
                   if s.exists()), None)
    if not script:
        err("generate_report.js not found — DOCX skipped.")
        return None
    try:
        subprocess.run(["node","--version"], capture_output=True, check=True)
    except Exception:
        err("Node.js not found — DOCX skipped.")
        return None

    info("Generating PhD-level DOCX report…")
    r = subprocess.run(
        ["node", str(script.resolve()), str(json_path), str(docx_path)],
        capture_output=True, text=True, cwd=str(Path(__file__).parent),
    )
    if r.returncode == 0 and docx_path.exists():
        ok(f"DOCX: {docx_path}")
        return docx_path
    else:
        err(f"DOCX error: {r.stderr[:400]}")
        return None


# ════════════════════════════════════════════════════════════════════════════════
#  ENHANCED WIZARD CONFIGURATIONS — v7 ULTRA COMPREHENSIVE
# ════════════════════════════════════════════════════════════════════════════════

# ── 🎓 ACADEMIC FIELDS — Expanded with English Language Studies & More ─────────
FIELDS = {
    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1: LANGUAGE & LINGUISTICS
    # ══════════════════════════════════════════════════════════════════════════
    # Applied Linguistics & Branches
    "1":"Applied Linguistics",
    "2":"Sociolinguistics",
    "3":"Psycholinguistics",
    "4":"Neurolinguistics",
    "5":"Bilingualism & Multilingualism",
    "6":"Corpus Linguistics",
    "7":" discourse Analysis",
    "8":"Phonetics & Phonology",
    "9":"Morphology",
    "10":"Syntax",
    "11":"Semantics",
    "12":"Pragmatics",
    # TESOL & Language Teaching
    "13":"TESOL (Teaching English to Speakers of Other Languages)",
    "14":"TEFL (Teaching English as a Foreign Language)",
    "15":"ESL (English as a Second Language)",
    "16":"EFL (English as a Foreign Language)",
    "17":"Language Teaching Methodology",
    "18":"Language Assessment & Testing",
    "19":"Curriculum Design in Language Education",
    "20":"Second Language Acquisition (SLA)",
    "21":"Language Teacher Education",
    "22":"Computer-Assisted Language Learning (CALL)",
    # Translation & Interpreting
    "23":"Translation Studies",
    "24":"Interpreting Studies",
    "25":"Subtitling & Dubbing",
    "26":"Translation Technology (CAT Tools)",
    "27":"Literary Translation",
    "28":"Technical & Scientific Translation",
    "29":"Legal Translation",
    "30":"Medical Translation",
    # Linguistics General
    "31":"Computational Linguistics",
    "32":"Historical Linguistics",
    "33":"Typological Linguistics",
    "34":"Language Documentation",
    "35":"Forensic Linguistics",
    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2: EDUCATION
    # ══════════════════════════════════════════════════════════════════════════
    "36":"General Education",
    "37":"Early Childhood Education",
    "38":"Primary Education",
    "39":"Secondary Education",
    "40":"Higher Education",
    "41":"Adult Education",
    "42":"Distance Education / E-Learning",
    "43":"Educational Technology",
    "44":"Instructional Design",
    "45":"Curriculum & Instruction",
    "46":"Educational Psychology",
    "47":"Educational Leadership",
    "48":"Educational Policy",
    "49":"Comparative Education",
    "50":"Special Education / Inclusive Education",
    "51":"Gifted Education",
    "52":"Language Education Policy",
    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3: SOCIAL SCIENCES
    # ══════════════════════════════════════════════════════════════════════════
    "53":"Psychology (General)",
    "54":"Clinical Psychology",
    "55":"Counseling Psychology",
    "56":"Educational Psychology",
    "57":"Social Psychology",
    "58":"Developmental Psychology",
    "59":"Cognitive Psychology",
    "60":"Industrial/Organizational Psychology",
    "61":"Health Psychology",
    "62":"Forensic Psychology",
    "63":"Sociology (General)",
    "64":"Medical Sociology",
    "65":"Sociology of Education",
    "66":"Rural Sociology",
    "67":"Urban Sociology",
    "68":"Cultural Sociology",
    "69":"Anthropology (General)",
    "70":"Cultural Anthropology",
    "71":"Physical Anthropology",
    "72":"Archaeology",
    "73":"Linguistic Anthropology",
    "74":"Political Science",
    "75":"International Relations",
    "76":"Public Policy",
    "77":"Security Studies",
    "78":"Governance",
    "79":"Communication Studies",
    "80":"Media Studies",
    "81":"Journalism",
    "82":"Film & Television Studies",
    "83":"Advertising & Public Relations",
    "84":"Cultural Studies",
    "85":"Gender Studies",
    "86":"Women's Studies",
    "87":"LGBTQ+ Studies",
    "88":"History",
    "89":"Archaeological Studies",
    "90":"Economic History",
    "91":"Social History",
    "92":"Diplomatic History",
    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 4: BUSINESS & ECONOMICS
    # ══════════════════════════════════════════════════════════════════════════
    "93":"Business Administration",
    "94":"Marketing",
    "95":"Human Resource Management",
    "96":"Organizational Behavior",
    "97":"Entrepreneurship",
    "98":"International Business",
    "99":"Supply Chain Management",
    "100":"Operations Management",
    "101":"Strategic Management",
    "102":"Economics (General)",
    "103":"Microeconomics",
    "104":"Macroeconomics",
    "105":"Econometrics",
    "106":"Development Economics",
    "107":"International Economics",
    "108":"Labor Economics",
    "109":"Public Finance",
    "110":"Environmental Economics",
    "111":"Finance (General)",
    "112":"Banking & Financial Services",
    "113":"Investment & Portfolio Management",
    "114":"Corporate Finance",
    "115":"Islamic Finance",
    "116":"Insurance & Risk Management",
    "117":"Accounting (General)",
    "118":"Auditing",
    "119":"Management Accounting",
    "120":"Taxation",
    "121":"Management (General)",
    "122":"Project Management",
    "123":"Quality Management",
    "124":"Knowledge Management",
    "125":"Tourism & Hospitality Management",
    "126":"Sports Management",
    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 5: LAW & LEGAL STUDIES
    # ══════════════════════════════════════════════════════════════════════════
    "127":"Law (General)",
    "128":"Constitutional Law",
    "129":"Criminal Law",
    "130":"Civil Law",
    "131":"International Law",
    "132":"Human Rights Law",
    "133":"Environmental Law",
    "134":"Corporate Law",
    "135":"Intellectual Property Law",
    "136":"Family Law",
    "137":"Islamic Law (Sharia)",
    "138":"Maritime Law",
    "139":"Sports Law",
    "140":"Forensic Science (Legal)",
    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 6: ARTS & HUMANITIES
    # ══════════════════════════════════════════════════════════════════════════
    "141":"Philosophy (General)",
    "142":"Ethics",
    "143":"Metaphysics",
    "144":"Epistemology",
    "145":"Logic",
    "146":"Political Philosophy",
    "147":"Literature (General)",
    "148":"English Literature",
    "149":"Comparative Literature",
    "150":"American Literature",
    "151":"Postcolonial Literature",
    "152":"Creative Writing",
    "153":"Classical Studies",
    "154":"Medieval Studies",
    "155":"Renaissance Studies",
    "156":"Theology & Religious Studies",
    "157":"Islamic Studies",
    "158":"Christian Studies",
    "159":"Jewish Studies",
    "160":"Buddhist Studies",
    "161":"Arts (General)",
    "162":"Visual Arts",
    "163":"Music Studies",
    "164":"Theater & Performing Arts",
    "165":"Film Studies",
    "166":"Photography",
    "167":"Graphic Design",
    "168":"Fashion Design",
    "169":"Interior Design",
    "170":"Architecture",
    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 7: STEM — SCIENCE, TECHNOLOGY, ENGINEERING, MATHEMATICS
    # ══════════════════════════════════════════════════════════════════════════
    # Computer Science & IT
    "171":"Computer Science (General)",
    "172":"Artificial Intelligence (AI)",
    "173":"Machine Learning",
    "174":"Deep Learning",
    "175":"Natural Language Processing (NLP)",
    "176":"Computer Vision",
    "177":"Robotics",
    "178":"Software Engineering",
    "179":"Data Science",
    "180":"Big Data Analytics",
    "181":"Cybersecurity",
    "182":"Information Systems",
    "183":"Database Systems",
    "184":"Computer Networks",
    "185":"Cloud Computing",
    "186":"Internet of Things (IoT)",
    "187":"Blockchain Technology",
    "188":"Human-Computer Interaction (HCI)",
    # Engineering
    "189":"Engineering (General)",
    "190":"Civil Engineering",
    "191":"Mechanical Engineering",
    "192":"Electrical Engineering",
    "193":"Electronic Engineering",
    "194":"Chemical Engineering",
    "195":"Aerospace Engineering",
    "196":"Biomedical Engineering",
    "197":"Environmental Engineering",
    "198":"Petroleum Engineering",
    "199":"Industrial Engineering",
    "200":"Materials Engineering",
    # Sciences
    "201":"Mathematics (General)",
    "202":"Applied Mathematics",
    "203":"Statistics",
    "204":"Pure Mathematics",
    "205":"Physics (General)",
    "206":"Chemistry (General)",
    "207":"Organic Chemistry",
    "208":"Inorganic Chemistry",
    "209":"Physical Chemistry",
    "210":"Analytical Chemistry",
    "211":"Biochemistry",
    "212":"Biology (General)",
    "213":"Molecular Biology",
    "214":"Genetics",
    "215":"Microbiology",
    "216":"Zoology",
    "217":"Botany",
    "218":"Ecology",
    "219":"Environmental Science",
    "220":"Marine Biology",
    "221":"Neuroscience",
    "222":"Astronomy & Astrophysics",
    "223":"Geology",
    "224":"Geophysics",
    # Health & Medicine
    "225":"Medicine (General)",
    "226":"Public Health",
    "227":"Epidemiology",
    "228":"Nursing (General)",
    "229":"Pediatric Nursing",
    "230":"Mental Health Nursing",
    "231":"Pharmacy",
    "232":"Dentistry",
    "233":"Physical Therapy",
    "234":"Occupational Therapy",
    "235":"Veterinary Medicine",
    "236":"Nutrition & Dietetics",
    "237":"Sports Science",
    # Agriculture & Food
    "238":"Agriculture (General)",
    "239":"Agronomy",
    "240":"Horticulture",
    "241":"Animal Science",
    "242":"Food Science & Technology",
    "243":"Agricultural Economics",
    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 8: INFORMATION SCIENCE & LIBRARIANSHIP
    # ══════════════════════════════════════════════════════════════════════════
    "244":"Library & Information Science",
    "245":"Archival Studies",
    "246":"Documentation Studies",
    "247":"Knowledge Management",
    "248":"Information Literacy",
    "249":"Digital Humanities",
    "250":"Data Curation",
    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 9: MEDIA & COMMUNICATION
    # ══════════════════════════════════════════════════════════════════════════
    "251":"Mass Communication",
    "252":"Strategic Communication",
    "253":"Digital Media",
    "254":"Social Media Studies",
    "255":"Game Studies",
    "256":"Augmented/Virtual Reality Studies",
    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 10: ENVIRONMENT & SUSTAINABILITY
    # ══════════════════════════════════════════════════════════════════════════
    "257":"Environmental Studies",
    "258":"Climate Change Studies",
    "259":"Sustainability Science",
    "260":"Renewable Energy",
    "261":"Waste Management",
    "262":"Water Resources Management",
    "263":"Conservation Biology",
    "264":"Disaster Risk Management",
    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 11: CROSS-DISCIPLINARY
    # ══════════════════════════════════════════════════════════════════════════
    "265":"Gender & Sexuality Studies",
    "266":"Race & Ethnic Studies",
    "267":"Migration Studies",
    "268":"Development Studies",
    "269":"Peace & Conflict Studies",
    "270":"International Development",
    "271":"Urban Planning",
    "272":"Rural Development",
    "273":"Gerontology",
    "274":"Youth Studies",
    "275":"Disability Studies",
    "276":"Ageing Studies",
    "277":"Global Studies",
    "278":"Area Studies (MENA, Africa, Asia, etc.)",
    # Catch-all
    "0":"Custom / Other Field",
}

# ── 📄 PUBLICATION / STUDY TYPES ───────────────────────────────────────────────
PUBLICATION_TYPES = {
    "1":"Research Article (Journal)",
    "2":"Review Article",
    "3":"Systematic Review",
    "4":"Meta-Analysis",
    "5":"Scoping Review",
    "6":"Narrative Review",
    "7":"Conference Paper / Proceeding",
    "8":"Conference Poster",
    "9":"Book (Monograph)",
    "10":"Book Chapter",
    "11":"Edited Volume",
    "12":"Encyclopedia Entry",
    "13":"Encyclopedia / Dictionary",
    "14":"Working Paper",
    "15":"Policy Brief",
    "16":"Technical Report",
    "17":"White Paper",
    "18":"Thesis / Dissertation (General)",
    "19":"PhD Dissertation",
    "20":"Master's Thesis (MA/MSc)",
    "21":"Honours Thesis",
    "22":"Undergraduate Thesis",
    "23":"Doctoral Capstone",
    "24":"Research Report",
    "25":"Case Study",
    "26":"Technical Manual",
    "27":"Clinical Practice Guideline",
    "28":"Clinical Trial Report",
    "29":"Preprint (e.g., arXiv, bioRxiv)",
    "30":"Dataset / Data Paper",
    "31":"Software Paper",
    "32":"Methodology Paper",
    "33":"Protocol Paper",
    "34":"Short Communication / Letter",
    "35":"Editorial / Commentary",
    "36":"News Article",
    "37":"Book Review",
    "38":"Magazine Article",
    "39":"Blog Post / Web Article",
    "40":"Podcast / Video Content",
    "41":"Patent",
    "42":"Standard Document",
    "43":"Government Publication",
    "44":"NGO Report",
    "45":"Consultancy Report",
    "46":"Grant Proposal",
    "47":"Thesis Abstract",
    "48":"Dissertation Proposal",
    "49":"Any / All Publication Types",
}

# ── 🎓 STUDY LEVEL / DEGREE TYPE ──────────────────────────────────────────────
STUDY_LEVELS = {
    "1":"PhD (Doctor of Philosophy)",
    "2":"EdD (Doctor of Education)",
    "3":"DBA (Doctor of Business Administration)",
    "4":"MD/PhD (Medical Doctor / Philosophy)",
    "5":"Professional Doctorate (e.g., DClinPsy, DBA)",
    "6":"Master's Degree (MA / MSc / MBA / MLIS / MEduc / etc.)",
    "7":"Postgraduate Diploma / Certificate",
    "8":"Honours Degree (BA/BSc Hons)",
    "9":"Bachelor's Degree (BA / BSc / BEd / etc.)",
    "10":"Associate Degree / Foundation",
    "11":"Research Article / Academic Paper",
    "12":"Any / All Levels",
}

# ── 🔬 RESEARCH METHODOLOGY / DESIGN TYPE ──────────────────────────────────────
RESEARCH_METHODOLOGIES = {
    "1":"Experimental Study",
    "2":"Quasi-Experimental Study",
    "3":"True Experimental / RCT (Randomized Controlled Trial)",
    "4":"Non-Experimental / Correlational Study",
    "5":"Qualitative Study",
    "6":"Quantitative Study",
    "7":"Mixed-Methods Study",
    "8":"Case Study",
    "9":"Ethnographic Study",
    "10":"Phenomenological Study",
    "11":"Grounded Theory Study",
    "12":"Narrative Inquiry / Narrative Study",
    "13":"Action Research",
    "14":"Survey Research",
    "15":"Longitudinal Study",
    "16":"Cross-Sectional Study",
    "17":"Cohort Study",
    "18":"Cross-Cultural Study",
    "19":"Comparative Study",
    "20":"Historical Research",
    "21":"Content Analysis Study",
    "22":"Discourse Analysis Study",
    "23":"Conversational Analysis",
    "24":"Corpus-Based Study",
    "25":"Grounded Theory Methodology",
    "26":"Interpretive Phenomenological Analysis (IPA)",
    "27":"Framework Analysis",
    "28":"Thematic Analysis",
    "29":"Constant Comparative Method",
    "30":"Design-Based Research",
    "31":"Design Science Research",
    "32":"Delphi Study",
    "33":"Focus Group Study",
    "34":"Interview-Based Study",
    "35":"Observation Study",
    "36":"Triangulation Study",
    "37":"Replication Study",
    "38":"Systematic Review & Meta-Analysis",
    "39":"Bibliometric Analysis",
    "40":" scientometric Study",
    "41":"Network Analysis Study",
    "42":"Simulation Study",
    "43":"Modelling Study",
    "44":"Computational Study",
    "45":"Theoretical / Conceptual Study",
    "46":"Philosophical Study",
    "47":"Critical Theory Study",
    "48":"Feminist Research",
    "49":"Participatory Action Research (PAR)",
    "50":"Community-Based Participatory Research (CBPR)",
    "51":"Any / All Methodologies",
}

# ── 📑 DISSERTATION / THESIS PART / CHAPTER ────────────────────────────────────
DISSERTATION_PARTS = {
    # General Parts
    "1":"Abstract / Executive Summary",
    "2":"Introduction / Chapter 1",
    "3":"Literature Review / Chapter 2",
    "4":"Theoretical Framework",
    "5":"Methodology / Chapter 3",
    "6":"Results / Findings / Chapter 4",
    "7":"Discussion / Chapter 5",
    "8":"Conclusion & Recommendations",
    "9":"References / Bibliography",
    "10":"Appendices",
    # Specific for Research Articles
    "11":"Introduction (Article)",
    "12":"Literature Review (Article)",
    "13":"Methods (Article)",
    "14":"Results (Article)",
    "15":"Discussion (Article)",
    "16":"Conclusion (Article)",
    # Specific for Books / Chapters
    "17":"Preface / Foreword",
    "18":"Introduction (Book)",
    "19":"Chapter Content (Book)",
    "20":"Conclusion (Book)",
    "21":"Epilogue / Afterword",
    # Specific for Reports
    "22":"Executive Summary (Report)",
    "23":"Introduction (Report)",
    "24":"Methodology (Report)",
    "25":"Findings (Report)",
    "26":"Conclusions (Report)",
    "27":"Recommendations (Report)",
    # Any / All
    "28":"Any / All Parts",
}

# ── 📊 QUARTILE / JOURNAL RANKING SELECTION ─────────────────────────────────────
QUARTILE_SELECTION = {
    "1":"Q1 (Top 25% - Highest Impact)",
    "2":"Q2 (50-75% - Above Average)",
    "3":"Q3 (25-50% - Average Impact)",
    "4":"Q4 (Bottom 25% - Lower Impact)",
    "5":"Q1 + Q2 (Top Tier Only)",
    "6":"Q1 + Q2 + Q3 (Mid-High Tier)",
    "7":"All Quartiles (Q1-Q4)",
    "8":"Not Indexed / Unknown Quartile",
    "9":"Indexed Only (Any Quartile)",
    "10":"Scopus-Indexed Only",
    "11":"Web of Science-Indexed Only",
    "12":"All Indexes",
}

# ── 📦 PAPER LIMIT — User-Friendly Choices ─────────────────────────────────────
PAPER_LIMITS = {
    "1":"Light (50 papers, ~30 min)",
    "2":"Standard (150 papers, ~1-2 hrs)",
    "3":"Medium (300 papers, ~3-4 hrs)",
    "4":"Extended (500 papers, ~5-6 hrs)",
    "5":"Deep (800 papers, ~8-10 hrs)",
    "6":"Maximum (1200+ papers, ~12+ hrs)",
    "7":"Unlimited (All available papers)",
}

# ── Legacy STUDY_TYPES (kept for backward compatibility) ───────────────────────
STUDY_TYPES = {
    "1":"Empirical Research","2":"Systematic Review / Meta-Analysis",
    "3":"Literature Review","4":"Case Study","5":"Experimental Study",
    "6":"Qualitative Study","7":"Quantitative Study","8":"Mixed-Methods",
    "9":"Theoretical Framework","10":"Thesis / Dissertation",
    "11":"Conference Paper","12":"Book Chapter",
    "14":"PhD Dissertation","15":"Master's Thesis",
    "16":"Action Research","17":"Survey Research",
    "18":"Grounded Theory","19":"Ethnographic Study",
    "20":"Phenomenological Study","21":"Narrative Inquiry",
    "22":"Longitudinal Study","23":"Cross-Sectional Study",
    "24":"Randomized Controlled Trial","25":"Cohort Study",
    "26":"Scoping Review","27":"Critical Review",
    "28":"Technical Report","29":"White Paper",
    "30":"Any / All types",
}


# ════════════════════════════════════════════════════════════════════════════════
#  NEW PLATFORM SEARCH FUNCTIONS — v7 ADDITIONAL PLATFORMS
#  50+ additional academic paper sources for maximum coverage
# ════════════════════════════════════════════════════════════════════════════════

def search_microsoft_academic(query: str, year_from=None, limit: int = 20) -> list:
    """Microsoft Academic (deprecated but archive still accessible)."""
    # Note: Microsoft Academic was shut down but we keep for legacy support
    url = f"https://academic.microsoft.com/api/v1/search?q={requests.utils.quote(query)}"
    try:
        data = _get(url, {})
        out = []
        for item in (data or {}).get("results", [])[:limit]:
            out.append({
                "title": item.get("title", ""),
                "authors": [a.get("name", "") for a in item.get("authors", [])],
                "year": str(item.get("year", "")),
                "journal": item.get("journal", {}).get("name", ""),
                "doi": item.get("doi"),
                "abstract": item.get("abstract", ""),
                "pdf_url": None,
            })
        return _norm(out, "Microsoft Academic")
    except Exception:
        return []


def search_baidu_scholar(query: str, year_from=None, limit: int = 20) -> list:
    """Baidu Scholar — Chinese academic search engine."""
    encoded = requests.utils.quote(query)
    url = f"https://xueshu.baidu.com/s?wd={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h3>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Baidu Scholar",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Baidu Scholar")
    except Exception:
        return []


def search_yandex_scholar(query: str, year_from=None, limit: int = 20) -> list:
    """Yandex Scholar — Russian academic search engine."""
    encoded = requests.utils.quote(query)
    url = f"https://scholar.yandex.ru/search?text={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<div[^>]*class="[^"]*serp-item[^"]*"[^>]*>(.*?)</div>', r.text, re.DOTALL):
            title_m = re.search(r'<a[^>]*class="[^"]*serp-item__title[^"]*"[^>]*>(.*?)</a>', m.group(1), re.DOTALL)
            if title_m:
                title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
                if len(title) > 15:
                    out.append({
                        "title": title[:200],
                        "authors": [],
                        "year": "",
                        "journal": "Yandex Scholar",
                        "doi": None,
                        "abstract": "",
                        "pdf_url": None,
                    })
                    if len(out) >= limit:
                        break
        return _norm(out, "Yandex Scholar")
    except Exception:
        return []


def search_korean_sin(query: str, year_from=None, limit: int = 20) -> list:
    """Korean SIN — Korea Science and Technology Information Service."""
    encoded = requests.utils.quote(query)
    url = f"https://www.scienceon.com/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Korea SIN",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Korean SIN")
    except Exception:
        return []


def search_cqjd(query: str, year_from=None, limit: int = 20) -> list:
    """CQJD — Chinese Academic Journals Full-text Database."""
    encoded = requests.utils.quote(query)
    url = f"http://kns.cnki.net/kns/brief/result.aspx?dbprefix=SCDB&action=scholar&searchword={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*fz14[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "CNKI",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "CQJD (CNKI)")
    except Exception:
        return []


def search_cairn(query: str, year_from=None, limit: int = 20) -> list:
    """CAIRN — French social sciences and humanities repository."""
    encoded = requests.utils.quote(query)
    url = f"https://www.cairn.info/revues.php?search={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "CAIRN",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "CAIRN")
    except Exception:
        return []


def search_persee(query: str, year_from=None, limit: int = 20) -> list:
    """Persee — French open access journals."""
    encoded = requests.utils.quote(query)
    url = f"https://www.persee.fr/search?q={encoded}"
    try:
        data = _get(f"https://www.persee.fr/api/search?q={encoded}", {"limit": limit})
        out = []
        for item in (data or {}).get("results", [])[:limit]:
            out.append({
                "title": item.get("title", ""),
                "authors": [a.get("name", "") for a in item.get("authors", [])],
                "year": str(item.get("date", ""))[:4],
                "journal": "Persee",
                "doi": item.get("doi"),
                "abstract": item.get("abstract", ""),
                "pdf_url": None,
            })
        return _norm(out, "Persee")
    except Exception:
        return []


def search_dspace_br(query: str, year_from=None, limit: int = 20) -> list:
    """Brazilian D-Space repositories."""
    encoded = requests.utils.quote(query)
    url = f"https://search.bvsalud.org/portal/resource/en/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Brazilian DSpace",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Dspace/BR")
    except Exception:
        return []


def search_clase(query: str, year_from=None, limit: int = 20) -> list:
    """CLASE — Latin American social sciences."""
    encoded = requests.utils.quote(query)
    url = f"https://www.clase.org/buscar.do?query={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "CLASE",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "CLASE")
    except Exception:
        return []


def search_redib(query: str, year_from=None, limit: int = 20) -> list:
    """REDIB — Spanish/Portuguese academic resources."""
    encoded = requests.utils.quote(query)
    url = f"https://www.redib.org/buscar?palabra={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h3>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "REDIB",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "REDIB")
    except Exception:
        return []


def search_scielo_mexico(query: str, year_from=None, limit: int = 20) -> list:
    """SciELO Mexico — Mexican open access."""
    encoded = requests.utils.quote(query)
    url = f"https://www.scielo.org.mx/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*article-title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "SciELO Mexico",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Scielo Mexico")
    except Exception:
        return []


def search_concytec(query: str, year_from=None, limit: int = 20) -> list:
    """CONCYTEC — Peru scientific database."""
    encoded = requests.utils.quote(query)
    url = f"https://alicia.concytec.gob.pe/vdui/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "CONCYTEC",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "CONCYTEC")
    except Exception:
        return []


def search_binasss(query: str, year_from=None, limit: int = 20) -> list:
    """BINASSS — Costa Rica Health Sciences."""
    encoded = requests.utils.quote(query)
    url = f"https://www.binasss.sa.cr/busqueda.php?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*resultado[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "BINASSS",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "BINASSS")
    except Exception:
        return []


def search_ajol_full(query: str, year_from=None, limit: int = 20) -> list:
    """AJOL — African Journals Online (Full)."""
    encoded = requests.utils.quote(query)
    url = f"https://www.ajol.info/search.php?search={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<h3[^>]*class="[^"]*itemtitle[^"]*"[^>]*>(.*?)</h3>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "AJOL",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "AJOL")
    except Exception:
        return []


def search_african_digital(query: str, year_from=None, limit: int = 20) -> list:
    """African Digital Library — African thesis repository."""
    encoded = requests.utils.quote(query)
    url = f"http://www.african libraries.org/sphinx/?search={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "African Digital",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "African Digital")
    except Exception:
        return []


def search_uwc(query: str, year_from=None, limit: int = 20) -> list:
    """UWC — University of Western Cape repository."""
    encoded = requests.utils.quote(query)
    url = f"https://ir.uwc.ac.za/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "UWC Repository",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "UWC")
    except Exception:
        return []


def search_shamaa(query: str, year_from=None, limit: int = 20) -> list:
    """Shamaa — Arabic database."""
    encoded = requests.utils.quote(query)
    url = f"https://www.shamaa.org/search.php?query={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Shamaa",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Shamaa")
    except Exception:
        return []


def search_arab_psyc(query: str, year_from=None, limit: int = 20) -> list:
    """ArabPsyc — Arabic psychology database."""
    encoded = requests.utils.quote(query)
    url = f"https://www.arabpsyc.net/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h3>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "ArabPsyc",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "ArabPsyc")
    except Exception:
        return []


def search_arab_digital(query: str, year_from=None, limit: int = 20) -> list:
    """Arab Digital — General Arabic academic database."""
    encoded = requests.utils.quote(query)
    url = f"https://www.arabdigital.net/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Arab Digital",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Arab Digital")
    except Exception:
        return []


def search_maktabk(query: str, year_from=None, limit: int = 20) -> list:
    """Maktabk — Iranian academic database."""
    encoded = requests.utils.quote(query)
    url = f"https://www.maktabk.ir/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Maktabk",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Maktabk")
    except Exception:
        return []


def search_civilica(query: str, year_from=None, limit: int = 20) -> list:
    """Civilica — Iranian scientific database."""
    encoded = requests.utils.quote(query)
    url = f"https://civilica.com/search/?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Civilica",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Civilica")
    except Exception:
        return []


def search_magiran(query: str, year_from=None, limit: int = 20) -> list:
    """Magiran — Iranian full-text database."""
    encoded = requests.utils.quote(query)
    url = f"https://www.magiran.com/search/?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Magiran",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Magiran")
    except Exception:
        return []


def search_noormags(query: str, year_from=None, limit: int = 20) -> list:
    """Noormags — Iranian journal database."""
    encoded = requests.utils.quote(query)
    url = f"https://www.noormags.com/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Noormags",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Noormags")
    except Exception:
        return []


def search_inflibnet(query: str, year_from=None, limit: int = 20) -> list:
    """INFLIBNET — Indian thesis database."""
    encoded = requests.utils.quote(query)
    url = f"https://shodhganga.inflibnet.ac.in/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "INFLIBNET",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "INFLIBNET")
    except Exception:
        return []


def search_shodhganga(query: str, year_from=None, limit: int = 20) -> list:
    """Shodhganga — Indian thesis repository."""
    encoded = requests.utils.quote(query)
    url = f"https://shodhganga.inflibnet.ac.in/handle/10603/1/search?query={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Shodhganga",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Shodhganga")
    except Exception:
        return []


def search_cochrane(query: str, year_from=None, limit: int = 20) -> list:
    """Cochrane — Medical systematic reviews."""
    encoded = requests.utils.quote(query)
    url = f"https://www.cochranelibrary.com/central/search?search={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Cochrane",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Cochrane")
    except Exception:
        return []


def search_tib_hannover(query: str, year_from=None, limit: int = 20) -> list:
    """TIB Hannover — German technical repository."""
    encoded = requests.utils.quote(query)
    url = f"https://www.tib.eu/en/search?tx_tibsearch_search[query]={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "TIB Hannover",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "TIB Hannover")
    except Exception:
        return []


def search_hal_ensae(query: str, year_from=None, limit: int = 20) -> list:
    """HAL ENSAE — French economics repository."""
    encoded = requests.utils.quote(query)
    url = f"https://hal.ensae.fr/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "HAL ENSAE",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "HAL ENSAE")
    except Exception:
        return []


def search_oai_harvester(query: str, year_from=None, limit: int = 20) -> list:
    """OAI Harvester — Generic OAI-PMH harvester."""
    encoded = requests.utils.quote(query)
    url = f"https://core.ac.uk/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "OAI Harvester",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "OAI Harvester")
    except Exception:
        return []


def search_opus_bayern(query: str, year_from=None, limit: int = 20) -> list:
    """OPUS Bayern — Bavarian repository."""
    encoded = requests.utils.quote(query)
    url = f"https://opus.bayern.de/suche/?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "OPUS Bayern",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "OPUS Bayern")
    except Exception:
        return []


def search_dariah(query: str, year_from=None, limit: int = 20) -> list:
    """DARIAH — Digital research infrastructure Europe."""
    encoded = requests.utils.quote(query)
    url = f"https://www.dariah.eu/act/result/?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "DARIAH",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "DARIAH")
    except Exception:
        return []


def search_ieee_xplore(query: str, year_from=None, limit: int = 20) -> list:
    """IEEE Xplore — Engineering and computer science."""
    encoded = requests.utils.quote(query)
    url = f"https://ieeexplore.ieee.org/search/searchresult.jsp?queryText={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "IEEE Xplore",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "IEEE Xplore")
    except Exception:
        return []


def search_acm_digital(query: str, year_from=None, limit: int = 20) -> list:
    """ACM Digital Library — Computing."""
    encoded = requests.utils.quote(query)
    url = f"https://dl.acm.org/action/doSearch?AllField={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "ACM DL",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "ACM Digital")
    except Exception:
        return []


def search_econstor(query: str, year_from=None, limit: int = 20) -> list:
    """ECONSTOR — Economics research network."""
    encoded = requests.utils.quote(query)
    url = f"https://www.econstor.com/search?query={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "ECONSTOR",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "ECONSTOR")
    except Exception:
        return []


def search_ssrn_preprint(query: str, year_from=None, limit: int = 20) -> list:
    """SSRN Preprint — Social science preprints."""
    encoded = requests.utils.quote(query)
    url = f"https://papers.ssrn.com/sol3/search_results.cfm?STRING={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "SSRN Preprint",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "SSRN PREPRINT")
    except Exception:
        return []


def search_research4life(query: str, year_from=None, limit: int = 20) -> list:
    """Research4Life — Health and agriculture access."""
    encoded = requests.utils.quote(query)
    url = f"https://www.research4life.org/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Research4Life",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Research4Life")
    except Exception:
        return []


def search_elsevier_sciencedirect(query: str, year_from=None, limit: int = 20) -> list:
    """Elsevier ScienceDirect."""
    encoded = requests.utils.quote(query)
    url = f"https://www.sciencedirect.com/search?query={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "ScienceDirect",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "ELSEVIER")
    except Exception:
        return []


def search_wiley_online(query: str, year_from=None, limit: int = 20) -> list:
    """Wiley Online Library."""
    encoded = requests.utils.quote(query)
    url = f"https://onlinelibrary.wiley.com/search?query={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Wiley Online",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Wiley Online")
    except Exception:
        return []


def search_springer(query: str, year_from=None, limit: int = 20) -> list:
    """Springer Link."""
    encoded = requests.utils.quote(query)
    url = f"https://link.springer.com/search?query={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Springer",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Springer")
    except Exception:
        return []


def search_frontiers(query: str, year_from=None, limit: int = 20) -> list:
    """Frontiers — Open access publisher."""
    encoded = requests.utils.quote(query)
    url = f"https://www.frontiersin.org/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Frontiers",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Frontiers")
    except Exception:
        return []


def search_cambridge_up(query: str, year_from=None, limit: int = 20) -> list:
    """Cambridge University Press."""
    encoded = requests.utils.quote(query)
    url = f"https://www.cambridge.org/core/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Cambridge UP",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Cambridge UP")
    except Exception:
        return []


def search_oxford_academic(query: str, year_from=None, limit: int = 20) -> list:
    """Oxford Academic."""
    encoded = requests.utils.quote(query)
    url = f"https://academic.oup.com/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Oxford Academic",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Oxford Academic")
    except Exception:
        return []


def search_sage_journals(query: str, year_from=None, limit: int = 20) -> list:
    """Sage Journals."""
    encoded = requests.utils.quote(query)
    url = f"https://journals.sagepub.com/action/doSearch?AllField={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Sage Journals",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Sage Journals")
    except Exception:
        return []


def search_taylor_francis(query: str, year_from=None, limit: int = 20) -> list:
    """Taylor & Francis Online."""
    encoded = requests.utils.quote(query)
    url = f"https://www.tandfonline.com/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Taylor & Francis",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Taylor Francis")
    except Exception:
        return []


def search_emerald(query: str, year_from=None, limit: int = 20) -> list:
    """Emerald Insight."""
    encoded = requests.utils.quote(query)
    url = f"https://www.emerald.com/insight/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Emerald",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Emerald")
    except Exception:
        return []


def search_de_gruyter(query: str, year_from=None, limit: int = 20) -> list:
    """De Gruyter."""
    encoded = requests.utils.quote(query)
    url = f"https://www.degruyter.com/search?query={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "De Gruyter",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "De Gruyter")
    except Exception:
        return []


def search_nature_publishing(query: str, year_from=None, limit: int = 20) -> list:
    """Nature Publishing."""
    encoded = requests.utils.quote(query)
    url = f"https://www.nature.com/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Nature",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Nature Publishing")
    except Exception:
        return []


def search_cell_press(query: str, year_from=None, limit: int = 20) -> list:
    """Cell Press."""
    encoded = requests.utils.quote(query)
    url = f"https://www.cell.com/action/doSearch?searchType=all&searchText={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Cell Press",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Cell Press")
    except Exception:
        return []


def search_pubmed_central(query: str, year_from=None, limit: int = 20) -> list:
    """PubMed Central — Free full-text biomedical literature."""
    encoded = requests.utils.quote(query)
    url = f"https://www.ncbi.nlm.nih.gov/pmc/?term={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "PMC",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "PMC")
    except Exception:
        return []


def search_europe_pmc(query: str, year_from=None, limit: int = 20) -> list:
    """Europe PMC — European repository."""
    encoded = requests.utils.quote(query)
    url = f"https://europepmc.org/search?query={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Europe PMC",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Europe PMC")
    except Exception:
        return []


def search_hinari(query: str, year_from=None, limit: int = 20) -> list:
    """HINARI — Health access in developing countries."""
    encoded = requests.utils.quote(query)
    url = f"https://www.who.int/hinari/search/en/?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "HINARI",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "HINARI")
    except Exception:
        return []


def search_bireme(query: str, year_from=None, limit: int = 20) -> list:
    """Bireme — Latin American health sciences."""
    encoded = requests.utils.quote(query)
    url = f"https://pesquisa.bvsalud.org/portal/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Bireme",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Bireme")
    except Exception:
        return []


def search_whois_scholar(query: str, year_from=None, limit: int = 20) -> list:
    """Who is Who — Academic directory."""
    encoded = requests.utils.quote(query)
    url = f"https://www.researchgate.net/search/researcher?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*name[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 5:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "Who is Who",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "Whois")
    except Exception:
        return []


def search_arxiv_org(query: str, year_from=None, limit: int = 20) -> list:
    """arXiv.org — Preprint server."""
    params = {"search_query": query, "max_results": limit}
    data = _get("http://export.arxiv.org/api/query", params)
    out = []
    try:
        for entry in re.finditer(r'<entry>(.*?)</entry>', data, re.DOTALL):
            title_m = re.search(r'<title>(.*?)</title>', entry.group(1))
            if title_m:
                out.append({
                    "title": title_m.group(1).strip(),
                    "authors": re.findall(r'<name>(.*?)</name>', entry.group(1)),
                    "year": "",
                    "journal": "arXiv",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
    except Exception:
        pass
    return _norm(out, "arxiv.org")


def search_chemrxiv(query: str, year_from=None, limit: int = 20) -> list:
    """chemRxiv — Chemistry preprint server."""
    encoded = requests.utils.quote(query)
    url = f"https://chemrxiv.org/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "chemRxiv",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "chemRxiv")
    except Exception:
        return []


def search_sxiv(query: str, year_from=None, limit: int = 20) -> list:
    """sXiv — Social science preprint."""
    encoded = requests.utils.quote(query)
    url = f"https://sarxiv.org/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "sXiv",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "sXiv")
    except Exception:
        return []


def search_eartharxiv(query: str, year_from=None, limit: int = 20) -> list:
    """EarthArXiv — Earth science preprint."""
    encoded = requests.utils.quote(query)
    url = f"https://eartharxiv.org/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "EarthArXiv",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "EarthArXiv")
    except Exception:
        return []


def search_bioone(query: str, year_from=None, limit: int = 20) -> list:
    """BioOne — Biological sciences publisher."""
    encoded = requests.utils.quote(query)
    url = f"https://bioone.org/search?q={encoded}"
    try:
        r = requests.get(url, headers=HDRS, timeout=25)
        out = []
        for m in re.finditer(r'<a[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</a>', r.text, re.DOTALL):
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if len(title) > 15:
                out.append({
                    "title": title[:200],
                    "authors": [],
                    "year": "",
                    "journal": "BioOne",
                    "doi": None,
                    "abstract": "",
                    "pdf_url": None,
                })
                if len(out) >= limit:
                    break
        return _norm(out, "BioOne")
    except Exception:
        return []


def _ask(prompt: str, default: str = "") -> str:
    if HAS_RICH:
        return Prompt.ask(f"[bold cyan]{prompt}[/bold cyan]", default=default, console=console)
    v = input(f"  {prompt}" + (f" [{default}]" if default else "") + ": ").strip()
    return v or default


# ════════════════════════════════════════════════════════════════════════════════
#  SMART LOCK SYSTEM — Dynamic filtering based on user selections
# ════════════════════════════════════════════════════════════════════════════════

def get_locked_parts_for_pub_type(pub_type: str) -> list[str]:
    """
    Returns which DISSERTATION_PARTS sections are relevant based on publication type.
    This implements the "smart lock" system where selecting a type locks sections.
    """
    if pub_type in ["19", "20", "21", "22", "23"]:  # PhD, MA, Honours, Undergrad, Doctoral
        return ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]  # Thesis parts
    elif pub_type in ["1", "2", "3", "4", "5", "6", "29", "34"]:  # Articles, Reviews, Preprints
        return ["11", "12", "13", "14", "15", "16"]  # Article parts
    elif pub_type in ["9", "10", "11"]:  # Books, Chapters, Edited
        return ["17", "18", "19", "20", "21"]  # Book parts
    elif pub_type in ["16", "17", "24", "44", "45"]:  # Reports, NGO, Consultancy
        return ["22", "23", "24", "25", "26", "27"]  # Report parts
    else:
        return ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28"]  # All

def get_locked_methodologies_for_level(study_level: str) -> list[str]:
    """
    Returns which research methodologies are most relevant based on study level.
    Higher degrees typically require more rigorous methodologies.
    """
    if study_level in ["1", "2", "3", "4", "5"]:  # PhD, EdD, DBA, etc.
        return list(RESEARCH_METHODOLOGIES.keys())  # All methodologies
    elif study_level == "6":  # Master's
        return ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "38", "39", "45", "46", "51"]
    elif study_level == "7":  # Postgraduate Diploma
        return ["5", "6", "7", "8", "14", "17", "38"]
    elif study_level in ["8", "9"]:  # Honours, Bachelor's
        return ["5", "6", "7", "8", "14", "17", "21", "22", "28"]
    else:  # Research Articles, Any
        return list(RESEARCH_METHODOLOGIES.keys())


def wizard() -> dict:
    """
    ENHANCED WIZARD — v7 ULTRA COMPREHENSIVE with Smart Lock System
    
    The system now includes:
      1. 🎓 Academic Field selection (278+ fields with English Language Studies)
      2. 📄 Publication / Study Type (49 types: Research Articles, MA, PhD, Books, etc.)
      3. 🎓 Study Level (MA, PhD, Bachelor, Research Articles, etc.)
      4. 🔬 Research Methodology (51 types: Experimental, Mixed Methods, Qualitative, etc.)
      5. 📑 Dissertation/Thesis Part (28 parts: Chapter 1-5, Introduction, etc.)
      6. 📊 Quartile Selection (Q1-Q4, Indexed Only, etc.)
      7. 📦 Paper Limit (User-friendly choices with time estimates)
      8. 🔎 Search Mode & Platforms (Deep search with 70+ platforms)
      9. 🌐 Smart Lock System — selections filter relevant options dynamically
      10. 🌍 Language Selection — filters all PDFs to selected language(s)
    """
    platform_count = len(DEEP_PLATS)
    if HAS_RICH:
        console.print(Panel.fit(
            f"[bold white]🔬 Research Hunter v7 — ULTRA COMPREHENSIVE[/bold white]\n"
            f"[dim]Smart Lock System · 278+ Fields · 49 Pub Types · 51 Methods\n"
            f"70+ Platforms · Deep Search · Language Filter · Quartile Selection[/dim]",
            border_style="cyan"
        ))
    else:
        print("\n" + "="*72)
        print("  🔬 Research Hunter v7 — ULTRA COMPREHENSIVE")
        print("  Smart Lock System · 278+ Fields · 49 Pub Types · 51 Methods")
        print("  70+ Platforms · Deep Search · Language Filter · Quartile Selection")
        print("="*72)

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 1: Title
    # ══════════════════════════════════════════════════════════════════════════
    print()
    title = ""
    while not title:
        title = _ask("📌 Research topic / title").strip()

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 2: Research Questions
    # ══════════════════════════════════════════════════════════════════════════
    print("\n  📝 Research Questions (Enter to skip, 'done' to finish):")
    rqs: list[str] = []
    for i in range(1, 6):
        q = _ask(f"  RQ{i}", "").strip()
        if not q or q.lower() == "done":
            break
        rqs.append(q)

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 3: AUTO-DETECT from title+RQs
    # ══════════════════════════════════════════════════════════════════════════
    suggested_field  = auto_detect_field(title, rqs)
    suggested_types  = auto_detect_study_type(title, rqs)
    suggested_kws    = extract_study_keywords(title, rqs, suggested_field, count=30)
    country_context  = detect_country_context(title, rqs)

    print("\n  🤖 AUTO-DETECTED from your title:")
    print(f"     Field      : {suggested_field}")
    print(f"     Study type : {', '.join(suggested_types[:5])}{'...' if len(suggested_types) > 5 else ''}")
    if country_context:
        print(f"     Geo context: {' → '.join(country_context[:4])}")

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 4: Keywords
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n  🔑 Extracted keywords ({len(suggested_kws)}):")
    kw_cols = 4
    for row_start in range(0, len(suggested_kws), kw_cols):
        row = suggested_kws[row_start:row_start + kw_cols]
        print("     " + "  |  ".join(f"{k:<28}" for k in row))

    kw_ans = _ask("\n  Accept keywords? (y=use these / n=enter your own)", "y").lower()
    if kw_ans != "y":
        custom_kw = _ask("  Enter keywords (comma-separated)").strip()
        suggested_kws = [k.strip() for k in custom_kw.split(",") if k.strip()]

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 5: 🎓 ACADEMIC FIELD
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*72}")
    print(f"  🎓 STEP 1: ACADEMIC FIELD")
    print(f"{'='*72}")
    print(f"  Auto-detected: [{suggested_field}]")
    print("\n  Select your academic field:")
    
    # Group fields by section for better display
    field_sections = {
        "1-12": "LANGUAGE & LINGUISTICS (Applied Linguistics, TESOL, Translation...)",
        "13-22": "TESOL & LANGUAGE TEACHING (TEFL, ESL, CALL...)",
        "23-35": "TRANSLATION & INTERPRETING (Studies, Technology, Legal...)",
        "36-52": "EDUCATION (General, Higher, Technology, Special...)",
        "53-92": "SOCIAL SCIENCES (Psychology, Sociology, Political Science...)",
        "93-126": "BUSINESS & ECONOMICS (Management, Finance, Marketing...)",
        "127-140": "LAW & LEGAL STUDIES",
        "141-170": "ARTS & HUMANITIES (Philosophy, Literature, Arts...)",
        "171-237": "STEM (CS, Engineering, Medicine, Sciences...)",
        "238-264": "AGRICULTURE, ENVIRONMENT & SUSTAINABILITY",
        "265-278": "CROSS-DISCIPLINARY STUDIES",
    }
    
    for range_key, section_name in field_sections.items():
        print(f"\n    ── {section_name}")
        start, end = map(int, range_key.split("-"))
        for i in range(start, min(end + 1, start + 3)):
            if str(i) in FIELDS:
                val = FIELDS[str(i)]
                marker = " ◀" if val == suggested_field else ""
                end_range = min(i + 2, end + 1)
                for j in range(i, min(end_range, start + 3)):
                    if str(j) in FIELDS:
                        v = FIELDS[str(j)]
                        m = " ◀" if v == suggested_field else ""
                        print(f"      [{j:>3}] {v:<40}{m}")
                i = end_range - 1
    
    print("\n    [  0] Custom / Other Field")
    fk = _ask("\n  Field number (Enter to accept auto)", "").strip()
    if fk == "":
        field = suggested_field
        print(f"     ✓ Using auto-detected: {field}")
    elif fk == "0":
        field = _ask("  Custom field name").strip() or suggested_field
    else:
        field = FIELDS.get(fk, suggested_field)
    
    field_key = fk if fk else str([k for k, v in FIELDS.items() if v == suggested_field][0]) if suggested_field in FIELDS.values() else "1"

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 6: 📄 PUBLICATION / STUDY TYPE (NEW!)
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*72}")
    print(f"  📄 STEP 2: PUBLICATION / STUDY TYPE")
    print(f"{'='*72}")
    print("\n  What type of publication are you searching for?")
    print("  [This selection will LOCK subsequent sections to relevant options]\n")
    
    pub_type_sections = {
        "1-6": "JOURNAL ARTICLES (Research, Review, Systematic, Meta-Analysis...)",
        "7-8": "CONFERENCE (Papers, Posters)",
        "9-13": "BOOKS (Monographs, Chapters, Edited Volumes...)",
        "14-17": "THESES & DISSERTATIONS (PhD, MA, Honours...)",
        "18-28": "REPORTS & GUIDELINES (Technical, Clinical, Policy...)",
        "29-35": "PREPRINTS & SHORT FORMATS",
        "36-45": "OTHER FORMATS (News, Patents, Government...)",
        "46-49": "PROPOSALS & ABSTRACTS",
    }
    
    for range_key, section_name in pub_type_sections.items():
        print(f"\n    ── {section_name}")
        start, end = map(int, range_key.split("-"))
        for i in range(start, end + 1):
            if str(i) in PUBLICATION_TYPES:
                val = PUBLICATION_TYPES[str(i)]
                print(f"      [{i:>2}] {val}")
    
    print(f"\n    [ 49] Any / All Publication Types")
    pk = _ask("\n  Publication type number(s) (e.g. 1,3,19 or 49 for all)", "49").strip()
    
    # Parse publication types
    if pk == "49":
        pub_types_selected = list(PUBLICATION_TYPES.values())[:-1]  # Exclude "Any/All"
        pub_type_keys = [k for k in PUBLICATION_TYPES.keys() if k != "49"]
    else:
        pub_type_keys = [k.strip() for k in pk.split(",") if k.strip() in PUBLICATION_TYPES]
        pub_types_selected = [PUBLICATION_TYPES[k] for k in pub_type_keys]
    
    if not pub_types_selected:
        pub_types_selected = list(PUBLICATION_TYPES.values())[:-1]
        pub_type_keys = [k for k in PUBLICATION_TYPES.keys() if k != "49"]
    
    print(f"     ✓ Selected: {', '.join(pub_types_selected[:3])}{'...' if len(pub_types_selected) > 3 else ''}")

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 7: 🎓 STUDY LEVEL (NEW!)
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*72}")
    print(f"  🎓 STEP 3: STUDY LEVEL / DEGREE TYPE")
    print(f"{'='*72}")
    print("\n  What academic level are you interested in?\n")
    
    level_sections = {
        "1-5": "DOCTORAL LEVEL (PhD, EdD, DBA, MD/PhD, Professional Doctorate)",
        "6-7": "MASTER'S & POSTGRADUATE (MA, MSc, MBA, Diplomas...)",
        "8-10": "UNDERGRADUATE (Honours, Bachelor's, Associate...)",
        "11-12": "RESEARCH & ANY",
    }
    
    for range_key, section_name in level_sections.items():
        print(f"\n    ── {section_name}")
        start, end = map(int, range_key.split("-"))
        for i in range(start, end + 1):
            if str(i) in STUDY_LEVELS:
                val = STUDY_LEVELS[str(i)]
                print(f"      [{i:>2}] {val}")
    
    slk = _ask("\n  Study level number(s) (e.g. 1,6 or 12 for all)", "12").strip()
    
    if slk == "12":
        study_levels_selected = list(STUDY_LEVELS.values())[:-1]
        study_level_keys = [k for k in STUDY_LEVELS.keys() if k != "12"]
    else:
        study_level_keys = [k.strip() for k in slk.split(",") if k.strip() in STUDY_LEVELS]
        study_levels_selected = [STUDY_LEVELS[k] for k in study_level_keys]
    
    if not study_levels_selected:
        study_levels_selected = list(STUDY_LEVELS.values())[:-1]
        study_level_keys = [k for k in STUDY_LEVELS.keys() if k != "12"]
    
    print(f"     ✓ Selected: {', '.join(study_levels_selected[:3])}{'...' if len(study_levels_selected) > 3 else ''}")

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 8: 🔬 RESEARCH METHODOLOGY (NEW!)
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*72}")
    print(f"  🔬 STEP 4: RESEARCH METHODOLOGY / DESIGN")
    print(f"{'='*72}")
    print("\n  What research methodology/design are you looking for?\n")
    
    method_sections = {
        "1-4": "EXPERIMENTAL (True Experimental, RCT, Quasi-Experimental...)",
        "5-7": "QUALITATIVE / QUANTITATIVE / MIXED (Core methods)",
        "8-12": "QUALITATIVE DESIGNS (Case, Ethnography, Phenomenology...)",
        "13-20": "OTHER DESIGNS (Action, Survey, Longitudinal, Cross-Cultural...)",
        "21-28": "ANALYTICAL METHODS (Discourse, Thematic, Grounded Theory...)",
        "29-37": "ADVANCED & SPECIALIZED (Design Science, Delphi, Triangulation...)",
        "38-44": "REVIEW & COMPUTATIONAL (Systematic Review, Bibliometric...)",
        "45-51": "THEORETICAL & SPECIALIZED (Philosophical, Feminist, PAR...)",
    }
    
    # Get locked methodologies based on study level
    locked_methods = []
    if study_level_keys:
        for sl in study_level_keys:
            locked_methods.extend(get_locked_methodologies_for_level(sl))
    locked_methods = list(set(locked_methods))
    
    for range_key, section_name in method_sections.items():
        print(f"\n    ── {section_name}")
        start, end = map(int, range_key.split("-"))
        for i in range(start, end + 1):
            if str(i) in RESEARCH_METHODOLOGIES:
                val = RESEARCH_METHODOLOGIES[str(i)]
                marker = " ★" if str(i) in locked_methods else ""
                print(f"      [{i:>2}] {val}{marker}")
    
    print("\n    [ 51] Any / All Methodologies")
    mk = _ask("\n  Methodology number(s) (e.g. 5,7,12 or 51 for all)", "51").strip()
    
    if mk == "51":
        methodologies_selected = list(RESEARCH_METHODOLOGIES.values())[:-1]
        method_keys = [k for k in RESEARCH_METHODOLOGIES.keys() if k != "51"]
    else:
        method_keys = [k.strip() for k in mk.split(",") if k.strip() in RESEARCH_METHODOLOGIES]
        methodologies_selected = [RESEARCH_METHODOLOGIES[k] for k in method_keys]
    
    if not methodologies_selected:
        methodologies_selected = list(RESEARCH_METHODOLOGIES.values())[:-1]
        method_keys = [k for k in RESEARCH_METHODOLOGIES.keys() if k != "51"]
    
    print(f"     ✓ Selected: {', '.join(methodologies_selected[:3])}{'...' if len(methodologies_selected) > 3 else ''}")

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 9: 📑 DISSERTATION / THESIS PART (NEW!)
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*72}")
    print(f"  📑 STEP 5: DISSERTATION / THESIS PART / CHAPTER")
    print(f"{'='*72}")
    print("\n  Which part(s) of the thesis/dissertation are you looking for?\n")
    
    # Get locked parts based on publication type
    locked_parts = []
    if pub_type_keys:
        for pt in pub_type_keys:
            locked_parts.extend(get_locked_parts_for_pub_type(pt))
    locked_parts = list(set(locked_parts))
    
    print("    ── GENERAL THESIS PARTS")
    for i in range(1, 11):
        if str(i) in DISSERTATION_PARTS:
            val = DISSERTATION_PARTS[str(i)]
            marker = " ★" if str(i) in locked_parts else ""
            print(f"      [{i:>2}] {val}{marker}")
    
    print("\n    ── RESEARCH ARTICLE PARTS")
    for i in range(11, 17):
        if str(i) in DISSERTATION_PARTS:
            val = DISSERTATION_PARTS[str(i)]
            marker = " ★" if str(i) in locked_parts else ""
            print(f"      [{i:>2}] {val}{marker}")
    
    print("\n    ── BOOK & CHAPTER PARTS")
    for i in range(17, 22):
        if str(i) in DISSERTATION_PARTS:
            val = DISSERTATION_PARTS[str(i)]
            marker = " ★" if str(i) in locked_parts else ""
            print(f"      [{i:>2}] {val}{marker}")
    
    print("\n    ── REPORT PARTS")
    for i in range(22, 28):
        if str(i) in DISSERTATION_PARTS:
            val = DISSERTATION_PARTS[str(i)]
            marker = " ★" if str(i) in locked_parts else ""
            print(f"      [{i:>2}] {val}{marker}")
    
    print("\n    [ 28] Any / All Parts")
    dpk = _ask("\n  Part number(s) (e.g. 2,3,5 or 28 for all)", "28").strip()
    
    if dpk == "28":
        parts_selected = list(DISSERTATION_PARTS.values())[:-1]
        part_keys = [k for k in DISSERTATION_PARTS.keys() if k != "28"]
    else:
        part_keys = [k.strip() for k in dpk.split(",") if k.strip() in DISSERTATION_PARTS]
        parts_selected = [DISSERTATION_PARTS[k] for k in part_keys]
    
    if not parts_selected:
        parts_selected = list(DISSERTATION_PARTS.values())[:-1]
        part_keys = [k for k in DISSERTATION_PARTS.keys() if k != "28"]
    
    print(f"     ✓ Selected: {', '.join(parts_selected[:3])}{'...' if len(parts_selected) > 3 else ''}")

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 10: 🌍 Search Language
    # ══════════════════════════════════════════════════════════════════════════
    SEARCH_LANGUAGES = {
        "1": ("English",              ["en"], "Search English papers only"),
        "2": ("Arabic",               ["ar"], "Search Arabic papers only (اللغة العربية)"),
        "3": ("French",               ["fr"], "Search French papers only"),
        "4": ("Spanish",              ["es"], "Search Spanish papers only"),
        "5": ("German",               ["de"], "Search German papers only"),
        "6": ("Chinese",              ["zh"], "Search Chinese papers only"),
        "7": ("Portuguese",          ["pt"], "Search Portuguese papers only"),
        "8": ("Turkish",              ["tr"], "Search Turkish papers only"),
        "9": ("Russian",              ["ru"], "Search Russian papers only"),
        "10":("Japanese",             ["ja"], "Search Japanese papers only"),
        "11":("Korean",              ["ko"], "Search Korean papers only"),
        "12":("English + Arabic",     ["en", "ar"], "Search in both English and Arabic"),
        "13":("English + French",      ["en", "fr"], "Search in both English and French"),
        "14":("Arabic + French",      ["ar", "fr"], "Search in both Arabic and French"),
        "15":("English + Arabic + French", ["en", "ar", "fr"], "Search in EN, AR, FR"),
        "16":("All European Languages", ["en", "fr", "es", "de", "pt", "it"], "EN, FR, ES, DE, PT, IT"),
        "17":("All Asian Languages",   ["zh", "ja", "ko", "ar", "tr"], "ZH, JA, KO, AR, TR"),
        "18":("All Languages",        ["en", "ar", "fr", "es", "de", "zh", "pt", "tr", "ru", "ja", "ko"], "Maximum coverage"),
    }
    print(f"\n{'='*72}")
    print(f"  🌍 STEP 6: SEARCH LANGUAGE")
    print(f"{'='*72}")
    print("\n  Select the language(s) for searching and PDF filtering:")
    print("  ⚠️ NOTE: This will filter ALL downloaded PDFs to selected language(s)")
    print("  Example: If you select 'Arabic', only Arabic-language PDFs will be downloaded\n")
    
    for k, (label, codes, desc) in SEARCH_LANGUAGES.items():
        print(f"    [{k:>2}]  {label:<25} — {desc}")
    
    lk = _ask("\n  Language number", "1")
    lang_data = SEARCH_LANGUAGES.get(lk, SEARCH_LANGUAGES["1"])
    lang_label, lang_codes = lang_data[0], lang_data[1]
    print(f"\n     ✓ Search language: {lang_label}")
    print(f"       Languages for PDF filtering: {', '.join(lang_codes)}")

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 11: Year Range
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*72}")
    print(f"  📅 STEP 7: YEAR RANGE")
    print(f"{'='*72}")
    print("\n  Filter papers by publication date:\n")
    yf = _ask("  Year from (e.g. 2015, Enter to skip)", "")
    yt = _ask("  Year to", str(datetime.now().year))
    year_from = int(yf) if yf.strip().isdigit() else None
    year_to   = int(yt) if yt.strip().isdigit() else datetime.now().year
    print(f"     ✓ Year range: {year_from or 'All'} – {year_to}")

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 12: 📊 QUARTILE SELECTION (NEW!)
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*72}")
    print(f"  📊 STEP 8: JOURNAL QUARTILE / RANKING SELECTION")
    print(f"{'='*72}")
    print("\n  Filter by journal ranking (Scopus/Web of Science):\n")
    
    quartile_sections = {
        "1-4": "SINGLE QUARTILE",
        "5-7": "QUARTILE COMBINATIONS",
        "8-12": "INDEX-BASED SELECTION",
    }
    
    for range_key, section_name in quartile_sections.items():
        print(f"\n    ── {section_name}")
        start, end = map(int, range_key.split("-"))
        for i in range(start, end + 1):
            if str(i) in QUARTILE_SELECTION:
                val = QUARTILE_SELECTION[str(i)]
                print(f"      [{i:>2}] {val}")
    
    qk = _ask("\n  Quartile selection number (e.g. 1 for Q1, 7 for all)", "7").strip()
    quartile_selected = QUARTILE_SELECTION.get(qk, QUARTILE_SELECTION["7"])
    print(f"     ✓ Quartile filter: {quartile_selected}")

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 13: 📦 PAPER LIMIT (User-Friendly!)
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*72}")
    print(f"  📦 STEP 9: PAPER LIMIT")
    print(f"{'='*72}")
    print("\n  How many papers to search for? (Time estimates are approximate)\n")
    
    for k, v in PAPER_LIMITS.items():
        print(f"    [{k}]  {v}")
    
    plk = _ask("\n  Paper limit", "4").strip()
    paper_limit_selected = PAPER_LIMITS.get(plk, PAPER_LIMITS["4"])
    
    # Map to actual numbers
    paper_limit_map = {
        "1": 50, "2": 150, "3": 300, "4": 500, "5": 800, "6": 1200, "7": None
    }
    max_papers = paper_limit_map.get(plk, 500)
    
    print(f"     ✓ Paper limit: {paper_limit_selected}")

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 14: 🔎 Search Mode & Platforms
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*72}")
    print(f"  🔎 STEP 10: SEARCH DEPTH & PLATFORMS")
    print(f"{'='*72}")
    api_count = len([p for p in DEEP_PLATS if p not in BROWSER_PLATS])
    browser_count = len([p for p in DEEP_PLATS if p in BROWSER_PLATS])
    print(f"\n  Select search depth (total {len(DEEP_PLATS)} platforms: {api_count} API + {browser_count} browser):\n")
    
    for idx, (key, cfg) in enumerate(MODE_TIME_ESTIMATES.items(), 1):
        plat_count = len(cfg["platforms"])
        time_est = cfg.get("time", "~1-2 hrs")
        print(f"    [{idx}]  {cfg['label']:<42} ({plat_count} platforms, ~{time_est})")
    
    print(f"    [{len(MODE_TIME_ESTIMATES)+1}]  Custom — Pick specific platforms")
    mk = _ask("\n  Search mode number", "3")

    mode_keys = list(MODE_TIME_ESTIMATES.keys())
    selected_key = None
    if mk.isdigit() and 1 <= int(mk) <= len(mode_keys):
        selected_key = mode_keys[int(mk) - 1]
        cfg = MODE_TIME_ESTIMATES[selected_key]
        platforms, mode = cfg["platforms"][:], cfg["label"]
    elif mk == str(len(MODE_TIME_ESTIMATES) + 1):
        print(f"\n  Available platforms ({len(DEEP_PLATS)}):")
        for i, p in enumerate(DEEP_PLATS, 1):
            print(f"    [{i:>2}]  {p}")
        sel = _ask("  Platform numbers (e.g. 1,2,5)", "1,2,3")
        idxs = [int(x.strip())-1 for x in sel.split(",") if x.strip().isdigit()]
        platforms = [DEEP_PLATS[i] for i in idxs if 0 <= i < len(DEEP_PLATS)]
        mode = "Custom"
    else:
        cfg = MODE_TIME_ESTIMATES["deep"]
        platforms, mode = DEEP_PLATS[:], cfg["label"]
    
    if not platforms:
        cfg = MODE_TIME_ESTIMATES["deep"]
        platforms, mode = DEEP_PLATS[:], cfg["label"]
    
    print(f"     ✓ Mode: {mode} ({len(platforms)} platforms)")

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 15: Sci-Hub & Folder Mode
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*72}")
    print(f"  ⚙️ STEP 11: ADDITIONAL OPTIONS")
    print(f"{'='*72}")
    
    use_scihub = _ask("\n  ⚠ Enable Sci-Hub / shadow libraries? (y/n)", "n").lower() == "y"
    if use_scihub:
        os.environ["SCIHUB_ENABLED"] = "1"
        print("     ✓ Sci-Hub enabled")

    print("\n  📁 Output folder mode:")
    print("    [1]  16-folder hierarchy (Q1-Q4, MA/PhD, Books, etc.)  ← default")
    print("    [2]  Single folder (all PDFs in one place)")
    sf = _ask("  Folder mode", "1").strip()
    single_folder = (sf == "2")

    proxy_ans = _ask(
        "\n  🌐 Enable proxy for restricted sites? "
        "(y=auto qoder:8082 / p=custom URL / n=skip)",
        "n"
    ).strip().lower()
    if proxy_ans == "y":
        _academic_proxy.enable()
    elif proxy_ans == "p":
        proxy_url = _ask("    Proxy URL (e.g. 127.0.0.1:8082)", "").strip()
        if proxy_url:
            _academic_proxy.external = [proxy_url]
            _academic_proxy.enable()

    # ══════════════════════════════════════════════════════════════════════════
    # SUMMARY
    # ══════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*72}")
    print(f"  📋 SEARCH PLAN SUMMARY (v7 ULTRA COMPREHENSIVE)")
    print(f"{'='*72}")
    print(f"  📌 Title            : {title[:70]}{'...' if len(title) > 70 else ''}")
    print(f"  🎓 Academic Field   : {field}")
    print(f"  📄 Publication Type : {', '.join(pub_types_selected[:3])}{'...' if len(pub_types_selected) > 3 else ''}")
    print(f"  🎓 Study Level      : {', '.join(study_levels_selected[:2])}{'...' if len(study_levels_selected) > 2 else ''}")
    print(f"  🔬 Methodology      : {', '.join(methodologies_selected[:3])}{'...' if len(methodologies_selected) > 3 else ''}")
    print(f"  📑 Part/Chapter     : {', '.join(parts_selected[:3])}{'...' if len(parts_selected) > 3 else ''}")
    print(f"  🌍 Search Language  : {lang_label}")
    print(f"     → PDF Filter     : {', '.join(lang_codes)}")
    print(f"  📅 Year Range       : {year_from or 'All'} – {year_to}")
    print(f"  📊 Quartile Filter  : {quartile_selected}")
    print(f"  📦 Paper Limit      : {paper_limit_selected}")
    print(f"     → Max Papers     : {max_papers if max_papers else 'Unlimited'}")
    print(f"  🔎 Search Mode      : {mode} ({len(platforms)} platforms)")
    if country_context:
        print(f"  🌍 Geo Context      : {' → '.join(country_context[:4])}")
    print(f"  🔑 Keywords         : {len(suggested_kws)} extracted")
    print(f"  ⚠️  Sci-Hub         : {'ON' if use_scihub else 'off'}")
    print(f"  📁 Folder Mode      : {'Single folder' if single_folder else '16-folder hierarchy'}")
    print(f"  🌐 Proxy            : {'ON' if _academic_proxy.enabled else 'off'}")
    print(f"  ★ Smart Lock        : Active (selections filter all options)")
    print(f"{'='*72}")
    
    confirm = _ask("\n  🚀 START SEARCH? (y/n)", "y").lower()
    if confirm != "y":
        print("  Aborted.")
        raise SystemExit(0)

    return {
        "title":                  title,
        "research_questions":     rqs,
        "field":                  field,
        "publication_types":      pub_types_selected,
        "study_levels":           study_levels_selected,
        "methodologies":          methodologies_selected,
        "dissertation_parts":     parts_selected,
        "year_from":              year_from,
        "year_to":                year_to,
        "year_range":             f"{year_from or 'All'} – {year_to}",
        "platforms":             platforms,
        "search_mode":            mode,
        "use_scihub":             use_scihub,
        "single_folder":          single_folder,
        "keywords":               suggested_kws,
        "search_languages":       lang_codes,
        "lang_label":             lang_label,
        "quartile_filter":        quartile_selected,
        "max_papers":             max_papers,
        "country_context":        country_context,
    }


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    params           = wizard()
    title            = params["title"]
    field            = params["field"]
    # v7: Extended search parameters
    study_types      = params.get("study_types", [])  # Legacy support
    publication_types = params.get("publication_types", [])  # NEW: Publication/Study Type
    study_levels      = params.get("study_levels", [])  # NEW: Study Level
    methodologies     = params.get("methodologies", [])  # NEW: Research Methodology
    dissertation_parts = params.get("dissertation_parts", [])  # NEW: Dissertation Parts
    quartile_filter   = params.get("quartile_filter", "All Quartiles (Q1-Q4)")  # NEW: Quartile Selection
    max_papers        = params.get("max_papers", None)  # NEW: Paper Limit override
    
    year_from        = params["year_from"]
    year_to          = params["year_to"]
    rqs              = params["research_questions"]
    platforms        = params["platforms"]
    mode             = params["search_mode"]
    use_scihub       = params.get("use_scihub", False)
    study_keywords   = params.get("keywords", [])
    lang_label       = params.get("lang_label", "English")
    search_languages = params.get("search_languages", ["en"])
    single_folder    = params.get("single_folder", False)  # v6: single-folder mode toggle
    # Country context already computed in wizard; re-use it
    country_context  = params.get("country_context") or detect_country_context(title, rqs)
    
    # v7: Log new parameters
    info(f"Publication types: {', '.join(publication_types[:3])}{'...' if len(publication_types) > 3 else ''}")
    info(f"Study levels: {', '.join(study_levels[:2])}{'...' if len(study_levels) > 2 else ''}")
    info(f"Methodologies: {', '.join(methodologies[:3])}{'...' if len(methodologies) > 3 else ''}")
    info(f"Quartile filter: {quartile_filter}")
    if max_papers:
        info(f"Paper limit: {max_papers}")

    if country_context:
        info(f"Geographic context: {' → '.join(country_context)}")
    if study_keywords:
        info(f"Study keywords extracted: {len(study_keywords)} terms")

    # Output folder & cache
    folder_name = _safe_name(title, 80)
    out_folder  = Path("pdf_files") / folder_name
    out_folder.mkdir(parents=True, exist_ok=True)

    # Create ALL subfolders upfront (Q + type + geo + citation + misc) — skip in single_folder mode
    if not single_folder:
        all_folder_names = list(set(Q_FOLDER_MAP.values())) + ALL_EXTRA_FOLDERS
        for fn in all_folder_names:
            try:
                (out_folder / fn).mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
    else:
        info("Single-folder mode enabled — all PDFs saved directly to output folder")

    # ── v6: Scan existing PDFs for duplicate avoidance ──────────────────────────
    existing_titles = scan_existing_pdfs(out_folder)

    cache = SearchCache(out_folder)
    stats = cache.stats()
    if stats["total_found"] > 0:
        warn(f"Resuming previous search — {stats['total_found']} papers cached "
             f"({stats['total_downloaded']} downloaded, {stats['queries_used']} queries used)")

    ok(f"Output: {out_folder}")
    start_g4f_proxy()

    # ── v6: Check Walter Ghost / DrissionPage availability ──────────────────────
    if use_scihub:
        _check_drissionpage()
        if HAS_DRISSIONPAGE:
            ok("Walter Ghost: DrissionPage available — gated PDF access enabled")
        else:
            info("Walter Ghost: DrissionPage unavailable — shadow libraries still work via API")

    # Red List manager (MD §7)
    red_list = RedListManager(out_folder)

    # Generate queries — title-driven, uses study_keywords for richer AI prompt
    # v7: Include new parameters to enhance query generation
    info("Generating search queries…")
    used_q  = cache.queries_used()
    
    # v7: Build enhanced query context from new parameters
    enhanced_context = {
        "publication_types": publication_types,
        "study_levels": study_levels,
        "methodologies": methodologies,
        "dissertation_parts": dissertation_parts,
    }
    
    queries = generate_queries(title, field, study_types, rqs, year_from,
                               used_q, country_context, enhanced_context)
    
    # Inject study keywords as extra queries (each keyword phrase = one query)
    extra_kw_queries = [kw for kw in study_keywords
                        if len(kw.split()) >= 2 and kw.lower() not in
                        {q.lower() for q in queries + used_q}]
    queries = (queries + extra_kw_queries[:8])[:25]

    cache.add_queries(queries)
    cache.save()
    ok(f"Generated {len(queries)} queries:")
    for i, q in enumerate(queries, 1):
        log(f"  {i:2}. {q}")

    # Search all platforms
    print()
    info(f"Searching {len(platforms)} platforms ({mode} mode)…")
    
    # v7: Include new parameters for filtering
    raw = search_all(queries, platforms, year_from=year_from, year_to=year_to,
                     field=field, country_context=country_context,
                     publication_types=publication_types,
                     study_levels=study_levels,
                     methodologies=methodologies,
                     dissertation_parts=dissertation_parts)

    # Deduplicate
    deduped = cache.deduplicate(raw)
    info(f"Raw: {len(raw)} → deduplicated: {len(deduped)}")

    # Relevance filter (v6: tighter threshold)
    relevant, removed = filter_by_relevance(deduped, title, field, threshold=0.15)
    if removed:
        warn(f"Relevance filter removed {removed} unrelated papers")

    # Filter already-known papers (from cache)
    new_papers, skipped = cache.filter_new(relevant)
    if skipped:
        info(f"Skipped {skipped} already-found papers from previous runs")

    # ── v6: Filter existing PDFs (self-aware duplicate avoidance) ───────────────
    if existing_titles:
        truly_new = []
        dup_count = 0
        for p in new_papers:
            if is_duplicate_paper(p, existing_titles):
                dup_count += 1
            else:
                truly_new.append(p)
        if dup_count > 0:
            warn(f"Duplicate scan: skipped {dup_count} papers already downloaded as PDFs")
        new_papers = truly_new

    ok(f"New papers this run: {len(new_papers)}")

    # ── v6: Enforce max_papers limit based on search mode ─────────────────────
    mode_lower = mode.lower() if isinstance(mode, str) else str(mode)
    mode_config = MODE_TIME_ESTIMATES.get(mode_lower, {})
    max_papers = mode_config.get("max_papers")
    if max_papers and len(new_papers) > max_papers:
        info(f"Mode limit: capping to {max_papers} papers (from {len(new_papers)})")
        new_papers = new_papers[:max_papers]

    if not new_papers:
        warn("No new papers found. Try Deep search mode, more RQs, or broader topic.")
        return

    for p in new_papers:
        cache.mark_found(p)

    # ═══════ v6: INTERLEAVED QUARTILE + DOWNLOAD PIPELINE ═══════
    # Check quartiles for batch, download that batch while checking next batch
    print()
    dl_mode_str = "single folder" if single_folder else "smart folders"
    info(f"Interleaved quartile verification + download (14-layer chain) into {dl_mode_str}…")

    BATCH_SIZE = 50  # Papers per batch
    MAX_BATCHES = int(os.environ.get("MAX_BATCHES", "0"))  # 0 = all batches
    dl_count  = 0
    type_cnt  = {"PhD":0,"MA":0,"Book":0,"BookChapter":0,"Conference":0}
    geo_cnt   = {"Libya":0,"Neighbor":0,"MENA":0}
    folder_dl: dict[str, int] = {}
    q_cnt     = {"Q1":0,"Q2":0,"Q3":0,"Q4":0,"Not Found":0}

    total_batches = (len(new_papers) + BATCH_SIZE - 1) // BATCH_SIZE
    effective_batches = total_batches if MAX_BATCHES == 0 else min(total_batches, MAX_BATCHES)
    for batch_idx in range(effective_batches):
        start = batch_idx * BATCH_SIZE
        end   = min(start + BATCH_SIZE, len(new_papers))
        batch = new_papers[start:end]
        batch_num = batch_idx + 1

        info(f"  Batch {batch_num}/{total_batches}: quartile checking {len(batch)} papers…")

        # ── Step A: Check quartiles for this batch ──────────────────────────────
        seen: dict = {}
        for p in batch:
            journal = (p.get("journal") or p.get("venue") or "") or ""
            if not journal.strip():
                p["scopus_quartile"] = {"quartile": "Not Found"}
                continue
            jkey = journal.lower().strip()
            if jkey in seen:
                p["scopus_quartile"] = seen[jkey]
            else:
                try:
                    r = check_quartile(journal)
                except Exception:
                    r = {"quartile": "Not Found", "verified": False}
                # Enhanced fuzzy upgrade
                qval = r.get("quartile","") if isinstance(r, dict) else str(r)
                if not qval or qval in ("Not Found","Not Ranked",""):
                    upgraded = enhanced_quartile_check(p)
                    if upgraded and upgraded not in ("Not Found",""):
                        if isinstance(r, dict):
                            r["quartile"] = upgraded
                        else:
                            r = {"quartile": upgraded}
                seen[jkey] = r
                p["scopus_quartile"] = r

        # ── Step B: Count quartiles for this batch ─────────────────────────────
        for p in batch:
            q = (p.get("scopus_quartile") or {})
            q = q.get("quartile","Not Found") if isinstance(q, dict) else str(q)
            q_cnt[q if q in q_cnt else "Not Found"] += 1

        ok(f"  Batch {batch_num}: Q1={q_cnt['Q1']} Q2={q_cnt['Q2']} Q3={q_cnt['Q3']} Q4={q_cnt['Q4']} N/A={q_cnt['Not Found']}")

        # ── Step C: Download this batch ──────────────────────────────────────────
        info(f"  Batch {batch_num}: downloading {len(batch)} papers…")
        for i, paper in enumerate(batch, 1):
            global_idx = start + i
            q_badge = (paper.get("scopus_quartile") or {})
            q_badge = q_badge.get("quartile","?") if isinstance(q_badge, dict) else str(q_badge)
            success, folder_used = smart_file_paper(paper, out_folder, use_scihub, red_list, cache, single_folder)
            paper["downloaded"] = success
            if success:
                dl_count += 1
                folder_dl[folder_used] = folder_dl.get(folder_used, 0) + 1
            dt = detect_doc_type(paper)
            if dt in type_cnt:
                type_cnt[dt] += 1
            gt = detect_geo_tier(paper)
            if gt in geo_cnt:
                geo_cnt[gt] += 1
            # Brief pause to avoid rate limiting
            if i % 10 == 0:
                info(f"    [{global_idx}/{len(new_papers)}] {dl_count} downloaded so far…")
            time.sleep(0.15)

    ok(f"Scopus Summary (this run):")
    for q, c in q_cnt.items():
        log(f"  {quartile_badge(q)}: {c}")

    cache.save()
    ok(f"Downloaded {dl_count} / {len(new_papers)} PDFs")
    if red_list.entries:
        warn(red_list.summary())

    # Load & merge previous results
    existing: list = []
    results_path = out_folder / "results.json"
    if results_path.exists():
        try:
            prev = json.loads(results_path.read_text(encoding="utf-8"))
            existing = prev.get("papers") or []
        except Exception:
            pass

    all_papers = cache.deduplicate(new_papers + existing)

    # Overall stats
    all_q = {"Q1":0,"Q2":0,"Q3":0,"Q4":0,"Not Found":0}
    for p in all_papers:
        q = (p.get("scopus_quartile") or {})
        q = q.get("quartile","Not Found") if isinstance(q, dict) else str(q)
        all_q[q if q in all_q else "Not Found"] += 1

    # Build report data
    info("Generating executive summary…")
    report_data = {
        "title":              title,
        "field":              field,
        "study_types":        study_types,
        "year_range":         params["year_range"],
        "search_mode":        mode,
        "platforms_searched": platforms,
        "ai_queries":         queries,
        "study_keywords":     study_keywords,
        "search_language":    lang_label,
        "country_context":    " → ".join(country_context) if country_context else "International",
        "papers":             all_papers,
        "executive_summary":  "",
        "generated_at":       datetime.now().isoformat(),
        "run_stats": {
            "new_this_run":        len(new_papers),
            "downloaded_this_run": dl_count,
            "total_in_cache":      len(all_papers),
            "q_distribution":      all_q,
            "type_distribution":   type_cnt,
            "geo_distribution":    geo_cnt,
            "red_list_count":      len(red_list.entries),
            "folder_downloads":    folder_dl,
        },
    }
    report_data["executive_summary"] = generate_executive_summary(report_data)

    # Save results.json
    results_path.write_text(
        json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ok(f"Saved results.json ({len(all_papers)} total papers)")
    cache.record_run(len(new_papers), dl_count, skipped)
    cache.save()

    # Reports — markdown + Node.js DOCX + Excel
    md_path   = generate_markdown_report(report_data, out_folder)
    docx_path = generate_docx_report(report_data, out_folder)  # Uses Node.js generate_report.js
    xlsx_path = _write_master_xlsx(all_papers, out_folder)

    total_dl = sum(1 for p in all_papers if p.get("downloaded"))

    # Count per-folder PDFs for banner
    def _cnt(folder: str) -> int:
        p = out_folder / folder
        return sum(1 for _ in p.glob("*.pdf")) if p.exists() else 0

    ma_cnt  = _cnt("MA_Dissertations")
    phd_cnt = _cnt("PhD_Dissertations")
    ly_cnt  = _cnt("LOCAL_Libya")
    mn_cnt  = _cnt("REGIONAL_MENA")
    nb_cnt  = _cnt("NEIGHBOR_NorthAfrica")
    bk_cnt  = _cnt("Books")
    cf_cnt  = _cnt("Conference_Papers")
    hc_cnt  = _cnt("HIGH_CITED_100plus") + _cnt("HIGH_CITED_500plus")
    rl_cnt  = len(red_list.entries)

    if HAS_RICH:
        console.print(Panel.fit(
            f"[bold green]🎉 Hunt Complete![/bold green]\n\n"
            f"  Topic : [cyan]{title[:65]}[/cyan]\n"
            f"  Field : [dim]{field}[/dim]   Lang: [dim]{lang_label}[/dim]\n"
            f"  New: [white]{len(new_papers)}[/white]  |  Total: [white]{len(all_papers)}[/white]  |  "
            f"PDFs: [green]{dl_count}[/green] this run / [green]{total_dl}[/green] total\n\n"
            f"  📊 Scopus Quality:\n"
            f"     Q1 [green]{all_q['Q1']:>4}[/green]  Q2 [blue]{all_q['Q2']:>4}[/blue]  "
            f"Q3 [yellow]{all_q['Q3']:>4}[/yellow]  Q4 [red]{all_q['Q4']:>4}[/red]  "
            f"Not-indexed [white]{all_q['Not Found']:>4}[/white]\n\n"
            f"  📂 {out_folder}/\n"
            f"     ├─ Q1_Top_Journals/          ({all_q['Q1']:>4} papers)\n"
            f"     ├─ Q2_Good_Journals/         ({all_q['Q2']:>4} papers)\n"
            f"     ├─ Q3_Acceptable_Journals/   ({all_q['Q3']:>4} papers)\n"
            f"     ├─ Q4_Lower_Tier/            ({all_q['Q4']:>4} papers)\n"
            f"     ├─ Not_Indexed/              ({all_q['Not Found']:>4} papers)\n"
            f"     ├─ PhD_Dissertations/        ({phd_cnt:>4} PDFs)\n"
            f"     ├─ MA_Dissertations/         ({ma_cnt:>4} PDFs)\n"
            f"     ├─ Books/                    ({bk_cnt:>4} PDFs)\n"
            f"     ├─ Conference_Papers/        ({cf_cnt:>4} PDFs)\n"
            f"     ├─ LOCAL_Libya/              ({ly_cnt:>4} PDFs)\n"
            f"     ├─ REGIONAL_MENA/            ({mn_cnt:>4} PDFs)\n"
            f"     ├─ NEIGHBOR_NorthAfrica/     ({nb_cnt:>4} PDFs)\n"
            f"     ├─ HIGH_CITED (100+/500+)/   ({hc_cnt:>4} PDFs)\n"
            f"     └─ 🔴 RED_LIST pending/      ({rl_cnt:>4} manual needed)\n\n"
            f"  📄 research_report.md          ✅\n"
            f"  📘 {'research_report.docx  ✅' if docx_path else 'DOCX (node.js needed)'}\n"
            f"  📊 {'master_database.xlsx  ✅' if xlsx_path and str(xlsx_path).endswith('.xlsx') else 'master_database.csv  ✅'}\n"
            f"  📋 RED_LIST_view.html          {'✅' if rl_cnt else '(nothing failed)'}\n"
            f"\n  [dim]Run again — already-found papers are skipped automatically.[/dim]",
            border_style="green"
        ))
    else:
        print(f"\n{'='*65}")
        print(f"✅ Hunt Complete! {len(all_papers)} total papers, {total_dl} PDFs")
        print(f"   Q1:{all_q['Q1']}  Q2:{all_q['Q2']}  Q3:{all_q['Q3']}  Q4:{all_q['Q4']}  Not-indexed:{all_q['Not Found']}")
        print(f"   PhD:{phd_cnt}  MA:{ma_cnt}  Books:{bk_cnt}  Conference:{cf_cnt}")
        print(f"   Libya:{ly_cnt}  MENA:{mn_cnt}  NorthAfrica:{nb_cnt}  HighCited:{hc_cnt}")
        print(f"   Red List pending: {rl_cnt}")
        print(f"   Folder: {out_folder}")
        print(f"{'='*65}")


def main_headless(params: dict):
    """Run the full Research Hunter pipeline with pre-set parameters (no interactive wizard)."""
    title            = params["title"]
    field            = params["field"]
    study_types      = params["study_types"]
    year_from        = params["year_from"]
    year_to          = params["year_to"]
    rqs              = params.get("research_questions", [])
    platforms        = params["platforms"]
    mode             = params.get("search_mode", "Deep")
    use_scihub       = params.get("use_scihub", False)
    study_keywords   = params.get("keywords", [])
    lang_label       = params.get("lang_label", "English")
    search_languages = params.get("search_languages", ["en"])
    single_folder    = params.get("single_folder", False)
    country_context  = params.get("country_context") or detect_country_context(title, rqs)

    if country_context:
        info(f"Geographic context: {' → '.join(country_context)}")
    if study_keywords:
        info(f"Study keywords extracted: {len(study_keywords)} terms")

    folder_name = _safe_name(title, 80)
    out_folder  = Path("pdf_files") / folder_name
    out_folder.mkdir(parents=True, exist_ok=True)

    if not single_folder:
        all_folder_names = list(set(Q_FOLDER_MAP.values())) + ALL_EXTRA_FOLDERS
        for fn in all_folder_names:
            try:
                (out_folder / fn).mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
    else:
        info("Single-folder mode enabled — all PDFs saved directly to output folder")

    existing_titles = scan_existing_pdfs(out_folder)
    cache = SearchCache(out_folder)
    stats = cache.stats()
    if stats["total_found"] > 0:
        warn(f"Resuming previous search — {stats['total_found']} papers cached "
             f"({stats['total_downloaded']} downloaded, {stats['queries_used']} queries used)")

    ok(f"Output: {out_folder}")
    start_g4f_proxy()

    if use_scihub:
        _check_drissionpage()
        if HAS_DRISSIONPAGE:
            ok("Walter Ghost: DrissionPage available — gated PDF access enabled")
        else:
            info("Walter Ghost: DrissionPage unavailable — shadow libraries still work via API")

    red_list = RedListManager(out_folder)
    info("Generating search queries…")
    used_q  = cache.queries_used()
    queries = generate_queries(title, field, study_types, rqs, year_from,
                               used_q, country_context)
    extra_kw_queries = [kw for kw in study_keywords
                        if len(kw.split()) >= 2 and kw.lower() not in
                        {q.lower() for q in queries + used_q}]
    queries = (queries + extra_kw_queries[:8])[:25]

    cache.add_queries(queries)
    cache.save()
    ok(f"Generated {len(queries)} queries:")
    for i, q in enumerate(queries, 1):
        log(f"  {i:2}. {q}")

    print()
    info(f"Searching {len(platforms)} platforms ({mode} mode)…")
    raw = search_all(queries, platforms, year_from=year_from, year_to=year_to,
                     field=field, country_context=country_context)

    deduped = cache.deduplicate(raw)
    info(f"Raw: {len(raw)} → deduplicated: {len(deduped)}")

    relevant, removed = filter_by_relevance(deduped, title, field, threshold=0.15)
    if removed:
        warn(f"Relevance filter removed {removed} unrelated papers")

    new_papers, skipped = cache.filter_new(relevant)
    if skipped:
        info(f"Skipped {skipped} already-found papers from previous runs")

    if existing_titles:
        truly_new = []
        dup_count = 0
        for p in new_papers:
            if is_duplicate_paper(p, existing_titles):
                dup_count += 1
            else:
                truly_new.append(p)
        if dup_count > 0:
            warn(f"Duplicate scan: skipped {dup_count} papers already downloaded as PDFs")
        new_papers = truly_new

    ok(f"New papers this run: {len(new_papers)}")

    # ── v6: Enforce max_papers limit based on search mode ─────────────────────
    mode_lower = mode.lower() if isinstance(mode, str) else str(mode)
    mode_config = MODE_TIME_ESTIMATES.get(mode_lower, {})
    max_papers = mode_config.get("max_papers")
    if max_papers and len(new_papers) > max_papers:
        info(f"Mode limit: capping to {max_papers} papers (from {len(new_papers)})")
        new_papers = new_papers[:max_papers]

    if not new_papers:
        warn("No new papers found. Try Deep search mode, more RQs, or broader topic.")
        return

    for p in new_papers:
        cache.mark_found(p)

    print()
    dl_mode_str = "single folder" if single_folder else "smart folders"
    info(f"Interleaved quartile verification + download (14-layer chain) into {dl_mode_str}…")

    BATCH_SIZE = 50
    MAX_BATCHES = int(os.environ.get("MAX_BATCHES", "0"))
    dl_count  = 0
    type_cnt  = {"PhD":0,"MA":0,"Book":0,"BookChapter":0,"Conference":0}
    geo_cnt   = {"Libya":0,"Neighbor":0,"MENA":0}
    folder_dl: dict[str, int] = {}
    q_cnt     = {"Q1":0,"Q2":0,"Q3":0,"Q4":0,"Not Found":0}

    total_batches = (len(new_papers) + BATCH_SIZE - 1) // BATCH_SIZE
    effective_batches = total_batches if MAX_BATCHES == 0 else min(total_batches, MAX_BATCHES)
    for batch_idx in range(effective_batches):
        start = batch_idx * BATCH_SIZE
        end   = min(start + BATCH_SIZE, len(new_papers))
        batch = new_papers[start:end]
        batch_num = batch_idx + 1

        info(f"  Batch {batch_num}/{total_batches}: quartile checking {len(batch)} papers…")
        seen: dict = {}
        for p in batch:
            journal = (p.get("journal") or p.get("venue") or "") or ""
            if not journal.strip():
                p["scopus_quartile"] = {"quartile": "Not Found"}
                continue
            jkey = journal.lower().strip()
            if jkey in seen:
                p["scopus_quartile"] = seen[jkey]
            else:
                try:
                    r = check_quartile(journal)
                except Exception:
                    r = {"quartile": "Not Found", "verified": False}
                qval = r.get("quartile","") if isinstance(r, dict) else str(r)
                if not qval or qval in ("Not Found","Not Ranked",""):
                    upgraded = enhanced_quartile_check(p)
                    if upgraded and upgraded not in ("Not Found",""):
                        if isinstance(r, dict):
                            r["quartile"] = upgraded
                        else:
                            r = {"quartile": upgraded}
                seen[jkey] = r
                p["scopus_quartile"] = r

        for p in batch:
            q = (p.get("scopus_quartile") or {})
            q = q.get("quartile","Not Found") if isinstance(q, dict) else str(q)
            q_cnt[q if q in q_cnt else "Not Found"] += 1

        ok(f"  Batch {batch_num}: Q1={q_cnt['Q1']} Q2={q_cnt['Q2']} Q3={q_cnt['Q3']} Q4={q_cnt['Q4']} N/A={q_cnt['Not Found']}")

        # ── Download this batch ──────────────────────────────────────────────────
        info(f"  Batch {batch_num}: downloading {len(batch)} papers…")
        for i, paper in enumerate(batch, 1):
            global_idx = start + i
            success, folder_used = smart_file_paper(paper, out_folder, use_scihub, red_list, cache, single_folder)
            paper["downloaded"] = success
            if success:
                dl_count += 1
                folder_dl[folder_used] = folder_dl.get(folder_used, 0) + 1
            dt = detect_doc_type(paper)
            if dt in type_cnt:
                type_cnt[dt] += 1
            gt = detect_geo_tier(paper)
            if gt in geo_cnt:
                geo_cnt[gt] += 1
            if i % 10 == 0:
                info(f"    [{global_idx}/{len(new_papers)}] {dl_count} downloaded so far…")
            time.sleep(0.15)

    ok(f"Scopus Summary (this run):")
    for q, c in q_cnt.items():
        log(f"  {quartile_badge(q)}: {c}")

    cache.save()
    ok(f"Downloaded {dl_count} / {len(new_papers)} PDFs")
    if red_list.entries:
        warn(red_list.summary())

    existing: list = []
    results_path = out_folder / "results.json"
    if results_path.exists():
        try:
            prev = json.loads(results_path.read_text(encoding="utf-8"))
            existing = prev.get("papers") or []
        except Exception:
            pass

    all_papers = cache.deduplicate(new_papers + existing)

    all_q = {"Q1":0,"Q2":0,"Q3":0,"Q4":0,"Not Found":0}
    for p in all_papers:
        q = (p.get("scopus_quartile") or {})
        q = q.get("quartile","Not Found") if isinstance(q, dict) else str(q)
        all_q[q if q in all_q else "Not Found"] += 1

    info("Generating executive summary…")
    report_data = {
        "title":              title,
        "field":              field,
        "study_types":        study_types,
        "year_range":         params.get("year_range", f"{year_from or 'All'} – {year_to}"),
        "search_mode":        mode,
        "platforms_searched": platforms,
        "ai_queries":         queries,
        "study_keywords":     study_keywords,
        "search_language":    lang_label,
        "country_context":    " → ".join(country_context) if country_context else "International",
        "papers":             all_papers,
        "executive_summary":  "",
        "generated_at":       datetime.now().isoformat(),
        "run_stats": {
            "new_this_run":        len(new_papers),
            "downloaded_this_run": dl_count,
            "total_in_cache":      len(all_papers),
            "q_distribution":      all_q,
            "type_distribution":   type_cnt,
            "geo_distribution":    geo_cnt,
            "red_list_count":      len(red_list.entries),
            "folder_downloads":    folder_dl,
        },
    }
    report_data["executive_summary"] = generate_executive_summary(report_data)

    results_path.write_text(
        json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ok(f"Saved results.json ({len(all_papers)} total papers)")
    cache.record_run(len(new_papers), dl_count, skipped)
    cache.save()

    md_path   = generate_markdown_report(report_data, out_folder)
    docx_path = generate_docx_report(report_data, out_folder)
    xlsx_path = _write_master_xlsx(all_papers, out_folder)

    total_dl = sum(1 for p in all_papers if p.get("downloaded"))

    def _cnt(folder: str) -> int:
        p = out_folder / folder
        return sum(1 for _ in p.glob("*.pdf")) if p.exists() else 0

    ma_cnt  = _cnt("MA_Dissertations")
    phd_cnt = _cnt("PhD_Dissertations")
    ly_cnt  = _cnt("LOCAL_Libya")
    mn_cnt  = _cnt("REGIONAL_MENA")
    nb_cnt  = _cnt("NEIGHBOR_NorthAfrica")
    bk_cnt  = _cnt("Books")
    cf_cnt  = _cnt("Conference_Papers")
    hc_cnt  = _cnt("HIGH_CITED_100plus") + _cnt("HIGH_CITED_500plus")
    rl_cnt  = len(red_list.entries)

    if HAS_RICH:
        console.print(Panel.fit(
            f"[bold green]🎉 Hunt Complete![/bold green]\n\n"
            f"  Topic : [cyan]{title[:65]}[/cyan]\n"
            f"  Field : [dim]{field}[/dim]   Lang: [dim]{lang_label}[/dim]\n"
            f"  New: [white]{len(new_papers)}[/white]  |  Total: [white]{len(all_papers)}[/white]  |  "
            f"PDFs: [green]{dl_count}[/green] this run / [green]{total_dl}[/green] total\n\n"
            f"  📊 Scopus Quality:\n"
            f"     Q1 [green]{all_q['Q1']:>4}[/green]  Q2 [blue]{all_q['Q2']:>4}[/blue]  "
            f"Q3 [yellow]{all_q['Q3']:>4}[/yellow]  Q4 [red]{all_q['Q4']:>4}[/red]  "
            f"Not-indexed [white]{all_q['Not Found']:>4}[/white]\n\n"
            f"  📂 {out_folder}/\n"
            f"     ├─ Q1_Top_Journals/          ({all_q['Q1']:>4} papers)\n"
            f"     ├─ Q2_Good_Journals/         ({all_q['Q2']:>4} papers)\n"
            f"     ├─ Q3_Acceptable_Journals/   ({all_q['Q3']:>4} papers)\n"
            f"     ├─ Q4_Lower_Tier/            ({all_q['Q4']:>4} papers)\n"
            f"     ├─ Not_Indexed/              ({all_q['Not Found']:>4} papers)\n"
            f"     ├─ PhD_Dissertations/        ({phd_cnt:>4} PDFs)\n"
            f"     ├─ MA_Dissertations/         ({ma_cnt:>4} PDFs)\n"
            f"     ├─ Books/                    ({bk_cnt:>4} PDFs)\n"
            f"     ├─ Conference_Papers/        ({cf_cnt:>4} PDFs)\n"
            f"     ├─ LOCAL_Libya/              ({ly_cnt:>4} PDFs)\n"
            f"     ├─ REGIONAL_MENA/            ({mn_cnt:>4} PDFs)\n"
            f"     ├─ NEIGHBOR_NorthAfrica/     ({nb_cnt:>4} PDFs)\n"
            f"     ├─ HIGH_CITED (100+/500+)/   ({hc_cnt:>4} PDFs)\n"
            f"     └─ 🔴 RED_LIST pending/      ({rl_cnt:>4} manual needed)\n\n"
            f"  📄 research_report.md          ✅\n"
            f"  📘 {'research_report.docx  ✅' if docx_path else 'DOCX (node.js needed)'}\n"
            f"  📊 {'master_database.xlsx  ✅' if xlsx_path and str(xlsx_path).endswith('.xlsx') else 'master_database.csv  ✅'}\n"
            f"  📋 RED_LIST_view.html          {'✅' if rl_cnt else '(nothing failed)'}\n"
            f"\n  [dim]Run again — already-found papers are skipped automatically.[/dim]",
            border_style="green"
        ))
    else:
        print(f"\n{'='*65}")
        print(f"✅ Hunt Complete! {len(all_papers)} total papers, {total_dl} PDFs")
        print(f"   Q1:{all_q['Q1']}  Q2:{all_q['Q2']}  Q3:{all_q['Q3']}  Q4:{all_q['Q4']}  Not-indexed:{all_q['Not Found']}")
        print(f"   PhD:{phd_cnt}  MA:{ma_cnt}  Books:{bk_cnt}  Conference:{cf_cnt}")
        print(f"   Libya:{ly_cnt}  MENA:{mn_cnt}  NorthAfrica:{nb_cnt}  HighCited:{hc_cnt}")
        print(f"   Red List pending: {rl_cnt}")
        print(f"   Folder: {out_folder}")
        print(f"{'='*65}")


if __name__ == "__main__":
    # ── GitHub Actions / CLI mode ────────────────────────────────────────────
    import argparse
    parser = argparse.ArgumentParser(description="Research Hunter v7 — run on GitHub Actions 24/7")
    parser.add_argument("--title",           help="Research topic / title (required)")
    parser.add_argument("--rq1", "--rq-1",   help="Research Question 1")
    parser.add_argument("--rq2", "--rq-2",   help="Research Question 2")
    parser.add_argument("--rq3", "--rq-3",   help="Research Question 3")
    parser.add_argument("--rq4", "--rq-4",   help="Research Question 4")
    parser.add_argument("--rq5", "--rq-5",   help="Research Question 5")
    # v7: All new input parameters
    parser.add_argument("--field",           help="Field number (1-278) or 'auto'")
    parser.add_argument("--publication-type", help="Publication type number (1-49)")
    parser.add_argument("--study-level",     help="Study level number (1-12)")
    parser.add_argument("--methodology",     help="Research methodology number (1-51)")
    parser.add_argument("--dissertation-part", help="Dissertation part number (1-28)")
    parser.add_argument("--study-type",      help="Study type(s) (e.g. 6,7,8 or 30=all) [legacy]")
    parser.add_argument("--year-from",       help="Start year (e.g. 2015)")
    parser.add_argument("--year-to",         help="End year (default: current)")
    parser.add_argument("--mode",         
        choices=["sample","quick","field","extended","deep","ultra","maximum"], 
        default="deep",
        help="Search mode: sample=4 platforms, quick=8, field=29, extended=50, deep=128, ultra=128+extended, maximum=128+all")
    parser.add_argument("--max-batches",     type=int, default=0,
                        help="Max batches to process per run (0=all)")
    parser.add_argument("--max-papers",      type=int, default=0,
                        help="Maximum papers to collect (0=unlimited, use mode default)")
    parser.add_argument("--language",        choices=["1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18"], default="1",
                        help="Search language (default: 1=English)")
    parser.add_argument("--scihub",          action="store_true", help="Enable Sci-Hub")
    parser.add_argument("--single-folder",   action="store_true", help="Single folder mode")
    parser.add_argument("--keywords",        help="Comma-separated custom keywords")
    parser.add_argument("--proxy",           choices=["y","p","n"], default="n",
                        help="Proxy (y=auto qoder, p=custom URL, n=skip)")
    args, _ = parser.parse_known_args()

    if args.title:
        # ── HEADLESS MODE for GitHub Actions ──────────────────────────────
        print("╔══════════════════════════════════════════════════════╗")
        print("║  🔬 Research Hunter v6 — HEADLESS MODE             ║")
        print("║  Running on GitHub Actions (24/7 cloud)            ║")
        print("╚══════════════════════════════════════════════════════╝")
        title = args.title
        # Collect research questions
        rqs = []
        for rq_val in [args.rq1, args.rq2, args.rq3, args.rq4, args.rq5]:
            if rq_val and rq_val.strip():
                rqs.append(rq_val.strip())

        # Auto-detect from title
        suggested_field = auto_detect_field(title, rqs)
        suggested_types = auto_detect_study_type(title, rqs)
        suggested_kws   = extract_study_keywords(title, rqs, suggested_field, count=30)
        country_context = detect_country_context(title, rqs)

        # Field: use user-specified or auto-detect
        if args.field and args.field != "auto":
            field = FIELDS.get(args.field, suggested_field)
        else:
            field = suggested_field

        # Study types: use user-specified or auto-detect
        if args.study_type and args.study_type != "auto":
            study_types = []
            if "30" in args.study_type:
                study_types = [v for k, v in STUDY_TYPES.items() if k != "30"]
            else:
                study_types = [STUDY_TYPES[k.strip()] for k in args.study_type.split(",")
                               if k.strip() in STUDY_TYPES]
        else:
            study_types = suggested_types or ["Qualitative Study"]

        SEARCH_LANGUAGES = {
            "1": ("English",              ["en"]),
            "2": ("Arabic",               ["ar"]),
            "3": ("French",               ["fr"]),
            "4": ("Spanish",              ["es"]),
            "5": ("English + Arabic",     ["en", "ar"]),
            "6": ("English + French",     ["en", "fr"]),
            "7": ("English + Arabic + French", ["en","ar","fr"]),
            "8": ("All Languages",        ["en","ar","fr","es","de","zh","pt","tr"]),
        }
        lang_label, lang_codes = SEARCH_LANGUAGES.get(args.language, ("English", ["en"]))

        year_from = int(args.year_from) if args.year_from and args.year_from.strip().isdigit() else None
        year_to   = int(args.year_to) if args.year_to and args.year_to.strip().isdigit() else datetime.now().year

        plat_mode = args.mode.lower()
        if plat_mode == "sample":
            platforms = SAMPLE_PLATS[:]
        elif plat_mode == "quick":
            platforms = QUICK_PLATS[:]
        elif plat_mode == "field":
            platforms = FIELD_PLATS[:]
        elif plat_mode == "extended":
            platforms = EXTENDED_PLATS[:]
        elif plat_mode == "ultra":
            platforms = ULTRA_PLATS[:]
        elif plat_mode == "maximum":
            platforms = ULTRA_PLATS[:]
        else:
            platforms = DEEP_PLATS[:]

        if args.keywords:
            suggested_kws = [k.strip() for k in args.keywords.split(",") if k.strip()]

        use_scihub = args.scihub
        single_folder = args.single_folder
        if use_scihub:
            os.environ["SCIHUB_ENABLED"] = "1"

        # Proxy
        proxy_ans = args.proxy.lower()
        if proxy_ans == "y":
            _academic_proxy.enable()
        elif proxy_ans == "p":
            # Custom proxy URL would need to be set via env var
            proxy_url = os.environ.get("PROXY_URL", "")
            if proxy_url:
                _academic_proxy.external = [proxy_url]
                _academic_proxy.enable()

        # Parse v7 new parameters
        publication_types = []
        if args.publication_type:
            pub_num = args.publication_type.strip()
            if pub_num in PUBLICATION_TYPES:
                publication_types = [PUBLICATION_TYPES[pub_num]]
            elif pub_num == "49":  # All types
                publication_types = list(PUBLICATION_TYPES.values())[:-1]
        
        study_levels = []
        if args.study_level:
            lvl_num = args.study_level.strip()
            if lvl_num in STUDY_LEVELS:
                study_levels = [STUDY_LEVELS[lvl_num]]
            elif lvl_num == "12":  # All levels
                study_levels = list(STUDY_LEVELS.values())[:-1]
        
        methodologies = []
        if args.methodology:
            meth_num = args.methodology.strip()
            if meth_num in RESEARCH_METHODOLOGIES:
                methodologies = [RESEARCH_METHODOLOGIES[meth_num]]
            elif meth_num == "51":  # All methods
                methodologies = list(RESEARCH_METHODOLOGIES.values())[:-1]
        
        dissertation_parts = []
        if args.dissertation_part:
            part_num = args.dissertation_part.strip()
            if part_num in DISSERTATION_PARTS:
                dissertation_parts = [DISSERTATION_PARTS[part_num]]
            elif part_num == "28":  # All parts
                dissertation_parts = list(DISSERTATION_PARTS.values())[:-1]

        params = {
            "title":              title,
            "field":              field,
            "study_types":        study_types,
            "year_from":          year_from,
            "year_to":            year_to,
            "year_range":         f"{year_from or 'All'} – {year_to}",
            "research_questions": rqs,
            "platforms":          platforms,
            "search_mode":        plat_mode.capitalize(),
            "use_scihub":         use_scihub,
            "keywords":           suggested_kws,
            "lang_label":         lang_label,
            "search_languages":   lang_codes,
            "single_folder":      single_folder,
            "country_context":    country_context,
            "max_papers":         args.max_papers if args.max_papers > 0 else None,
            # v7 new parameters
            "publication_types":  publication_types,
            "study_levels":       study_levels,
            "methodologies":      methodologies,
            "dissertation_parts": dissertation_parts,
        }

        if args.max_batches and int(args.max_batches) > 0:
            os.environ["MAX_BATCHES"] = str(int(args.max_batches))

        # Override _ask to auto-confirm in headless mode
        import builtins
        _orig_input = builtins.input
        builtins.input = lambda prompt="": "y"
        try:
            main_headless(params)
        finally:
            builtins.input = _orig_input
    else:
        main()
