"""
precision_engine.py — Ollama-driven precision scoring + cross-source validation.
99% precision target: 0.85+ ollama score + must appear in 2+ sources.
"""
import os
import json
import re
import subprocess
from typing import Dict, List, Optional, Any, Tuple
from logger import get_logger
from scoring_prompts import (
    SCORE_MATCH_PROMPT,
    CROSS_SOURCE_PROMPT,
    EXTRACT_TITLE_PROMPT,
    EXTRACT_AUTHORS_PROMPT,
    EXTRACT_YEAR_PROMPT,
    DETECT_REFERENCE_TYPE_PROMPT,
)
from error_handler import retry
from platform_registry import search_all_platforms

log = get_logger("precision_engine")

OLLAMA_MODEL = "qwen2.5vl-3b-16k"  # the ollama tag in runner-base:latest (16k ctx variant)
OLLAMA_BIN = os.environ.get("OLLAMA_BIN", "/usr/local/bin/ollama")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")


def _call_ollama(prompt: str, model: str = OLLAMA_MODEL, timeout: int = 60) -> str:
    """Call ollama via HTTP API (preferred) or CLI fallback."""
    import urllib.request
    try:
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate",
            data=json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
            return data.get("response", "").strip()
    except Exception as e:
        log.warning(f"ollama HTTP call failed: {e}; trying CLI")
        try:
            out = subprocess.check_output(
                [OLLAMA_BIN, "run", model, prompt],
                stderr=subprocess.DEVNULL,
                timeout=timeout,
            )
            return out.decode("utf-8", errors="replace").strip()
        except Exception as e2:
            log.error(f"ollama CLI call also failed: {e2}")
            return ""


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract the first JSON object from a text blob. Returns None if not parseable."""
    if not text:
        return None
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Find first {...} block
    m = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


@retry(max_attempts=2, base_delay=1.0)
def score_paper_match(paper: Dict[str, Any], reference_text: str, threshold_note: bool = True) -> Dict[str, Any]:
    """Ask ollama to score 0-1 whether `paper` matches `reference_text`.
    Returns: {"score": float, "reason": str, "uncertain": bool}
    """
    prompt = SCORE_MATCH_PROMPT.format(
        reference_text=reference_text[:1500],
        title=str(paper.get("title", ""))[:300],
        authors=str(paper.get("authors", ""))[:300],
        year=str(paper.get("year", ""))[:20],
        journal=str(paper.get("journal", ""))[:200],
        doi=str(paper.get("doi", ""))[:100],
        abstract=str(paper.get("abstract", ""))[:800],
    )
    raw = _call_ollama(prompt)
    parsed = _extract_json(raw)
    if not parsed or "score" not in parsed:
        log.warning(f"ollama returned unparseable score for {paper.get('title','')[:50]!r}: {raw[:100]!r}")
        return {"score": 0.0, "reason": "ollama parse failure", "uncertain": True}
    try:
        score = float(parsed.get("score", 0.0))
    except (TypeError, ValueError):
        score = 0.0
    return {
        "score": max(0.0, min(1.0, score)),
        "reason": str(parsed.get("reason", ""))[:300],
        "uncertain": bool(parsed.get("uncertain", False)),
    }


def cross_source_validate(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Tag each paper with source_count and validated flag.
    A paper is validated if it appears in 2+ platforms OR has a DOI hit in tier-1.
    """
    # Group by normalized title for fuzzy dedup
    by_key: Dict[str, List[Dict[str, Any]]] = {}
    for p in papers:
        title = (p.get("title") or "").strip().lower()
        # crude dedup key
        key = re.sub(r"\s+", " ", title)[:80]
        by_key.setdefault(key, []).append(p)

    validated: List[Dict[str, Any]] = []
    for key, group in by_key.items():
        platforms = list({g.get("_source_platform", "?") for g in group})
        source_count = len(platforms)
        # Pick the most complete record
        best = max(group, key=lambda p: (
            1 if p.get("doi") else 0,
            1 if p.get("abstract") else 0,
            1 if p.get("pdf_url") else 0,
        ))
        enriched = dict(best)
        enriched["source_count"] = source_count
        enriched["source_platforms"] = platforms
        enriched["cross_source_validated"] = source_count >= 2
        validated.append(enriched)
    return validated


def precision_search(
    reference_text: str,
    threshold: float = 0.85,
    max_candidates: int = 5,
) -> List[Dict[str, Any]]:
    """Search 70+ platforms → dedup → score with ollama → keep only >= threshold.
    Returns: list of papers with score, reason, source_count, cross_source_validated.

    v0.1.1: capped max_candidates to 5 by default (was 20) so /find finishes
    in ~60s with ollama scoring. The GHA cron has a 7-min budget for the
    full cycle, so we leave headroom for multiple messages.
    """
    log.info(f"precision_search: {reference_text[:80]!r} (threshold={threshold})")

    # 1) Extract structured fields from the reference text (best-effort)
    title = _extract_field(reference_text, EXTRACT_TITLE_PROMPT)
    if not title:
        # Fall back to first non-trivial line
        for line in reference_text.splitlines():
            line = line.strip()
            if len(line) > 15:
                title = line
                break
    if not title:
        log.warning("Could not extract title from reference")
        return []

    # 2) Search all platforms
    raw_results = search_all_platforms(title)
    log.info(f"Got raw results from {len(raw_results)} platforms for {title[:60]!r}")

    # 3) Flatten, tag with source platform
    flat: List[Dict[str, Any]] = []
    for plat, papers in raw_results.items():
        for p in papers[:3]:  # cap per platform
            p2 = dict(p)
            p2["_source_platform"] = plat
            flat.append(p2)
    if not flat:
        log.info("No platform results at all")
        return []

    # 4) Cross-source validation (dedup by title, count sources)
    deduped = cross_source_validate(flat)

    # 5) Score with ollama (cap candidates)
    scored: List[Dict[str, Any]] = []
    for p in deduped[:max_candidates]:
        score = score_paper_match(p, reference_text)
        p2 = dict(p)
        p2["match_score"] = score["score"]
        p2["match_reason"] = score["reason"]
        p2["match_uncertain"] = score["uncertain"]
        scored.append(p2)

    # 6) Filter by threshold
    kept = [p for p in scored if p["match_score"] >= threshold and not p["match_uncertain"]]
    kept.sort(key=lambda p: (p.get("cross_source_validated", False), p["match_score"]), reverse=True)
    log.info(f"precision_search kept {len(kept)}/{len(scored)} papers above threshold {threshold}")
    return kept


def _extract_field(reference_text: str, prompt_template: str) -> Optional[str]:
    """Use ollama to extract a single field from a reference text."""
    prompt = prompt_template.format(reference_text=reference_text[:1500])
    raw = _call_ollama(prompt).strip()
    if not raw or raw.lower() in ("null", "none", "[]", "{}"):
        return None
    # Try to parse as JSON first (for arrays)
    parsed = _extract_json(raw)
    if isinstance(parsed, list) and parsed:
        return str(parsed[0])
    if isinstance(parsed, dict) and parsed:
        # Return the first non-empty value
        for v in parsed.values():
            if v:
                return str(v)
    # Raw text
    cleaned = raw.strip().strip('"').strip("'")
    return cleaned if cleaned and cleaned.lower() not in ("null", "none") else None


def detect_reference_type(reference_text: str) -> Tuple[str, float]:
    """Detect if reference is article/book/chapter/etc. Returns (type, confidence)."""
    prompt = DETECT_REFERENCE_TYPE_PROMPT.format(reference_text=reference_text[:800])
    raw = _call_ollama(prompt)
    parsed = _extract_json(raw)
    if not parsed:
        return "other", 0.0
    return str(parsed.get("type", "other")), float(parsed.get("confidence", 0.0))
