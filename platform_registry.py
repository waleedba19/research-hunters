"""
platform_registry.py — Search platform registry.
v0.1: imports the 70+ PLATFORM_FNS from research_hunter_v2_4.
v0.2: will add ollama-driven dynamic platform discovery.
"""
import os
import sys
from typing import Dict, List, Optional, Callable, Any
from logger import get_logger

log = get_logger("platform_registry")

# Import the v2-4 platform function map. This file is a sibling in the repo.
try:
    sys.path.insert(0, os.path.dirname(__file__))
    import research_hunter_v2_4 as v24  # type: ignore
    PLATFORM_FNS: Dict[str, Callable] = getattr(v24, "PLATFORM_FNS", {})
    if PLATFORM_FNS:
        log.info(f"Loaded {len(PLATFORM_FNS)} platforms from research_hunter_v2_4")
    else:
        log.warning("research_hunter_v2_4.PLATFORM_FNS not found — using empty registry")
except ImportError as e:
    log.warning(f"research_hunter_v2_4 not importable: {e}. Using empty registry.")
    PLATFORM_FNS = {}


PRIORITY_TIERS: Dict[str, int] = {
    # Tier 1: highest-authority academic APIs (reliable, rich metadata, fast)
    "CrossRef": 1,
    "OpenAlex": 1,
    "Semantic Scholar": 1,
    "PubMed": 1,
    "arXiv": 1,
    "ERIC": 1,
    "DOAJ": 1,
    "BASE": 1,
    "Europe PMC": 1,
    "DBLP": 1,
    # Tier 2: solid OA repositories + major publishers
    "CORE": 2,
    "CORE API": 2,
    "HAL Archives": 2,
    "Zenodo": 2,
    "SciELO": 2,
    "PubMed Central": 2,
    "Unpaywall": 2,
    "OpenAIRE": 2,
    "PLoS ONE": 2,
    "MDPI": 2,
    "bioRxiv": 2,
    "medRxiv": 2,
    "Nature": 2,
    "ScienceDirect": 2,
    "Springer Open": 2,
    "Wiley Open": 2,
    "Taylor & Francis": 2,
    "Oxford UP": 2,
    "SSRN": 2,
    "Dimensions": 2,
    # Tier 3: regional / specialized / preprint / data
    "SciELO Brazil": 3,
    "Redalyc": 3,
    "Dialnet": 3,
    "Bioline Int'l": 3,
    "AJOL": 3,
    "CogPrints": 3,
    "PhilPapers": 3,
    "Directory of OA Books": 3,
    "SSOAR": 3,
    "J-STAGE": 3,
    "PsyArXiv": 3,
    "SocArXiv": 3,
    "OSF Preprints": 3,
    "ChemRxiv": 3,
    "Research Square": 3,
    "eLife Sciences": 3,
    "ScienceOpen": 3,
    "OA.mg": 3,
    "OpenDOAR": 3,
    "NBER": 3,
    "RePEc": 3,
    "WorldWideScience": 3,
    "CERN Document": 3,
    "Science.gov": 3,
    "NASA NTRS": 3,
    "OSTI.gov": 3,
    "ClinicalTrials.gov": 3,
    "Digital Commons": 3,
    "JSTOR Open": 3,
    "EBSCO Dissertations": 3,
    "Academia.edu": 3,
    "PaperPanda": 3,
    "DataCite": 3,
    "Figshare": 3,
    "Dryad": 3,
    "Google Dataset Search": 3,
    "Google Books": 3,
    "OpenSyllabus": 3,
    "Lens.org": 3,
    "Connected Papers": 3,
    "Scopus": 3,
    "Web of Science": 3,
    "ProQuest Dissertations": 3,
    "Open Academic Graph": 3,
    "Zenodo Extended": 3,
    "OhioLINK ETD": 3,
    "OATD": 3,
    "EThOS": 3,
    "AcademicianHelp": 3,
    "Internet Archive": 3,
    # Tier 4: shadow libraries + discovery/scraping (least reliable, last resort)
    "Anna's Archive": 4,
    "Sci-Hub Multi": 4,
    "Genemedi": 4,
    "Shadow Libraries": 4,
    "SciNet": 4,
    "SciBay": 4,
    "Grokipedia": 4,
    "Google Scholar": 4,
    "ResearchGate": 4,
    "Z-Library": 4,
    "LibGen": 4,
    "DuckDuckGo": 4,
    "Perplexica": 4,
}

# Build reverse lookup: lowercase -> canonical key
PLATFORM_ALIASES: Dict[str, str] = {}
for k in PLATFORM_FNS:
    PLATFORM_ALIASES[k.lower()] = k

def _resolve_platform(name: str) -> Optional[str]:
    """Resolve a platform name to its canonical key (case-insensitive)."""
    return PLATFORM_ALIASES.get(name.lower())

def get_platforms_by_tier(tier: int) -> List[str]:
    """Return canonical platform names in a given priority tier."""
    out: List[str] = []
    for name, t in PRIORITY_TIERS.items():
        if t == tier:
            canon = _resolve_platform(name)
            if canon:
                out.append(canon)
    return out


def get_all_platform_names() -> List[str]:
    """Return all registered platform names."""
    return list(PLATFORM_FNS.keys())


def get_platform_fn(name: str) -> Optional[Callable]:
    """Get a platform's search function by name."""
    return PLATFORM_FNS.get(name)


def call_platform(name: str, query: str, **kwargs) -> List[Dict[str, Any]]:
    """Call a platform's search function with a query. Returns list of papers."""
    fn = get_platform_fn(name)
    if fn is None:
        log.warning(f"Platform {name!r} not registered")
        return []
    try:
        results = fn(query, **kwargs)
        if results is None:
            return []
        return list(results) if isinstance(results, (list, tuple)) else []
    except Exception as e:
        log.error(f"Platform {name!r} raised: {e}")
        return []


def search_all_platforms(query: str, max_per_platform: int = 5, tiers: Optional[List[int]] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Run the search across all (or specified tier) platforms. Returns {platform: [papers]}.

    v0.1.1: prefer v2-4's parallel `search_all` (ThreadPoolExecutor with 8 workers)
    which is ~10x faster than the per-platform loop below. Falls back to the
    sequential loop only if v2-4's `search_all` is not importable.
    """
    # Fast path: v2-4's parallel search_all
    if hasattr(v24, "search_all") and callable(getattr(v24, "search_all", None)):
        try:
            # Build the platform list respecting tiers
            if tiers is None:
                # All platforms
                platforms = list(v24.PLATFORM_FNS.keys())
            else:
                platforms = []
                for t in tiers:
                    platforms.extend(get_platforms_by_tier(t))
            if not platforms:
                platforms = list(v24.PLATFORM_FNS.keys())
            # Use v2-4's search_all. It returns a flat list of paper dicts.
            flat = v24.search_all(
                queries=[query],
                platforms=platforms,
                year_from=None, year_to=None,
                field="", country_context=None,
            )
            # Re-shape flat list into {platform: [papers]} using each paper's "source" field
            results: Dict[str, List[Dict[str, Any]]] = {}
            for p in flat or []:
                plat = p.get("source") or p.get("platform") or p.get("_source_platform") or "unknown"
                if not isinstance(p, dict):
                    continue
                results.setdefault(plat, []).append(p)
            for k in results:
                results[k] = results[k][:max_per_platform]
            if results:
                return results
        except Exception as e:
            log.warning(f"v24.search_all failed ({e}); falling back to sequential loop")
    # Slow path: per-platform sequential loop
    if tiers is None:
        platform_names = get_all_platform_names()
    else:
        platform_names = []
        for t in tiers:
            platform_names.extend(get_platforms_by_tier(t))

    results = {}
    for name in platform_names:
        papers = call_platform(name, query)
        if papers:
            results[name] = papers[:max_per_platform]
    return results
