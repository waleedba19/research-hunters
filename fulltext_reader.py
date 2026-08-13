"""Open-access full-text reader for no-download mode.

Reads the *content* of open-access papers directly from public APIs —
WITHOUT downloading any PDF file — so the Excel/DOCX/PDF reports can be
filled with genuine introduction / methodology / results / discussion
text (and exact quotes) even when the user chose "DOWNLOAD PDFs OFF".

Sources (all free, no API key required):
  1. Europe PMC `fullTextXML` REST service — returns the full article body
     as JATS XML for open-access life-sciences papers.
  2. CORE API v3 — returns the full text of open-access works.

Paywalled papers (no OA copy available) gracefully fall back to the
abstract only; their section fields are marked accordingly.

This module is the no-download counterpart to the PDF text extraction in
research_hunter_v2-4.py (extract_pdf_text / enrich_paper_with_pdf_content),
which reads local PDF files page-by-page in DOWNLOAD mode.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Optional

import requests

from logger import get_logger

log = get_logger(__name__)

_HDRS = {
    "User-Agent": "ResearchHunter/5.0 (academic; mailto:research@hunter.edu)",
    "Accept": "application/json, text/xml, */*",
}
_TIMEOUT = 15

# Section-title patterns used to split JATS XML <sec> blocks into the four
# canonical report sections. Matches the <title> text of each <sec>.
_INTRO_RE = re.compile(r"introduc", re.I)
_METHODS_RE = re.compile(r"method|material", re.I)
_RESULTS_RE = re.compile(r"result|finding", re.I)
_DISCUSSION_RE = re.compile(r"discuss|conclusion", re.I)


def _strip(text: Optional[str]) -> str:
    """Collapse whitespace and drop XML-ish tags from a text fragment."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)        # drop any nested tags
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _get(url: str, params=None, want: str = "json",
         timeout: int = _TIMEOUT) -> Optional[object]:
    """Simple GET that returns parsed JSON or raw text (for XML)."""
    try:
        r = requests.get(url, params=params, headers=_HDRS, timeout=timeout)
        if r.status_code != 200 or not r.text:
            return None
        return r.json() if want == "json" else r.text
    except Exception as e:
        log.debug("fulltext GET failed %s: %s", url, e)
        return None


# ═══════════════════════════════════════════════════════════════════════════
#  Europe PMC fullTextXML — JATS XML full body for OA life-sciences papers
# ═══════════════════════════════════════════════════════════════════════════
def _europepmc_fulltext_xml(doi: str, pmcid: str = "") -> Optional[str]:
    """Return the JATS XML body of an open-access Europe PMC article.

    Europe PMC exposes full text via the REST endpoint:
        https://www.ebi.ac.uk/europepmc/webservices/rest/{PMCID}/fullTextXML
    We resolve the PMCID from the DOI first when needed.
    """
    if not doi and not pmcid:
        return None
    # Resolve PMCID from DOI if not supplied.
    if not pmcid and doi:
        try:
            data = _get(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                params={"query": f"DOI:{doi}", "format": "json"},
            )
            if data:
                hits = (data.get("resultList") or {}).get("result") or []
                if hits:
                    pmcid = hits[0].get("pmcid") or ""
                    if not pmcid:
                        # hasText = "N" means no OA full text available
                        if hits[0].get("hasText", "N") == "N":
                            return None
        except Exception:
            return None
    if not pmcid:
        return None
    xml_text = _get(
        f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML",
        want="text", timeout=20,
    )
    return xml_text or None


def _parse_jats_sections(xml_text: str) -> dict:
    """Split a JATS fullTextXML body into intro/methods/results/discussion.

    Returns a dict with keys introduction/methodology/results/discussion.
    Each value is the concatenated paragraph text of the matching <sec>.
    """
    out = {"introduction": "", "methodology": "",
           "results": "", "discussion": ""}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        # Fall back to crude regex extraction if the XML is malformed.
        return _parse_jats_sections_regex(xml_text)

    # Find <body> (namespaced or not). JATS uses no namespace in EPMC output.
    body = root.find(".//body")
    if body is None:
        body = root
    for sec in body.findall(".//sec"):
        title_el = sec.find("title")
        title = _strip(title_el.text if title_el is not None else "")
        if not title:
            continue
        # Collect paragraph text inside this section (descendants included).
        paras = [_strip(p.text) for p in sec.findall(".//p")]
        paras = [p for p in paras if len(p) > 25]
        text = " ".join(paras)
        if not text:
            continue
        if _INTRO_RE.search(title) and not out["introduction"]:
            out["introduction"] = text
        elif _METHODS_RE.search(title) and not out["methodology"]:
            out["methodology"] = text
        elif _RESULTS_RE.search(title) and not out["results"]:
            out["results"] = text
        elif _DISCUSSION_RE.search(title) and not out["discussion"]:
            out["discussion"] = text
    return out


def _parse_jats_sections_regex(xml_text: str) -> dict:
    """Regex fallback for malformed JATS XML."""
    out = {"introduction": "", "methodology": "",
           "results": "", "discussion": ""}
    # Match <sec>...<title>X</title>...(<p>...</p>)...</sec> loosely.
    for m in re.finditer(r"<sec[^>]*>(.*?)</sec>", xml_text, re.S):
        block = m.group(1)
        tm = re.search(r"<title[^>]*>(.*?)</title>", block, re.S)
        title = _strip(tm.group(1)) if tm else ""
        paras = [_strip(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", block, re.S)]
        text = " ".join(p for p in paras if len(p) > 25)
        if not title or not text:
            continue
        if _INTRO_RE.search(title) and not out["introduction"]:
            out["introduction"] = text
        elif _METHODS_RE.search(title) and not out["methodology"]:
            out["methodology"] = text
        elif _RESULTS_RE.search(title) and not out["results"]:
            out["results"] = text
        elif _DISCUSSION_RE.search(title) and not out["discussion"]:
            out["discussion"] = text
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  CORE API v3 — full text of open-access works
# ═══════════════════════════════════════════════════════════════════════════
def _core_fulltext(title: str) -> Optional[str]:
    """Return the full text body from CORE for an open-access work."""
    if not title:
        return None
    try:
        data = _get(
            "https://api.core.ac.uk/v3/search/works",
            params={"q": f'title:"{title[:80]}"', "limit": 3}, timeout=18,
        )
        for item in (data or {}).get("results", []):
            # CORE exposes the full text in 'fullText' (or 'description').
            ft = item.get("fullText") or item.get("description") or ""
            if ft and len(ft) > 400:
                return _strip(ft)
    except Exception:
        return None
    return None


def _naive_split_sections(text: str) -> dict:
    """Best-effort split of a flat full-text blob into the four sections.

    Used for CORE text (which is one big string, not JATS). Looks for
    heading-like lines; otherwise dumps everything into 'introduction'.
    """
    out = {"introduction": "", "methodology": "",
           "results": "", "discussion": ""}
    if not text:
        return out
    # Try to find section headings in the flat text.
    markers = [
        ("introduction", _INTRO_RE),
        ("methodology", _METHODS_RE),
        ("results", _RESULTS_RE),
        ("discussion", _DISCUSSION_RE),
    ]
    # Find positions of each marker line.
    positions = []
    lowered_lines = text.split("\n")
    for idx, line in enumerate(lowered_lines):
        low = line.strip().lower().strip(":.")
        if len(low) < 40:  # headings are short
            for key, rx in markers:
                if rx.search(low) and not any(idx == p for p, _ in positions):
                    positions.append((idx, key))
                    break
    if not positions:
        out["introduction"] = text[:8000]
        return out
    positions.sort()
    for i, (start, key) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(lowered_lines)
        chunk = " ".join(lowered_lines[start + 1:end])
        chunk = _strip(chunk)
        if chunk:
            out[key] = chunk[:6000]
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════════════
def fetch_oa_fulltext(paper: dict) -> dict:
    """Fetch open-access full-text sections for one paper (no download).

    Returns a dict with keys:
      introduction, methodology, results, discussion (str),
      fulltext_source ("europepmc" | "core" | ""),
      has_fulltext (bool).

    Mutates `paper` in place, setting the same keys, plus
    `paper["fulltext_source"]`. The caller can then use these to populate
    the Excel/DOCX/PDF report sheets with real text.

    Paywalled / unavailable papers: sections stay "" and has_fulltext False;
    the caller should fall back to the abstract.
    """
    doi = (paper.get("doi") or paper.get("DOI") or "").strip()
    title = (paper.get("title") or "").strip()
    sections = {"introduction": "", "methodology": "",
                "results": "", "discussion": ""}

    source = ""
    # 1) Europe PMC JATS XML (richest structured text).
    if doi:
        xml = _europepmc_fulltext_xml(doi)
        if xml and "<body" in xml:
            parsed = _parse_jats_sections(xml)
            if any(parsed.values()):
                sections.update(parsed)
                source = "europepmc"

    # 2) CORE full text fallback.
    if not source and title:
        ft = _core_fulltext(title)
        if ft:
            sections.update(_naive_split_sections(ft))
            # If naive split found nothing, put the blob in introduction.
            if not sections["introduction"] and ft:
                sections["introduction"] = ft[:6000]
            source = "core"

    result = {
        "introduction": sections["introduction"],
        "methodology": sections["methodology"],
        "results": sections["results"],
        "discussion": sections["discussion"],
        "fulltext_source": source,
        "has_fulltext": bool(source and any(sections.values())),
    }
    # Mutate the paper dict for convenience.
    paper.update(result)
    return result


def extract_quotes_from_text(text: str, keywords: list,
                             max_quotes: int = 12) -> list:
    """Extract exact quoted sentences relevant to the study keywords.

    Identical behaviour to research_hunter_v2-4.extract_quotes_from_text
    but operates on abstracts / OA full text in no-download mode.
    Returns a list of {"quote": str, "keyword": str} dicts.
    """
    if not text or not keywords:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    scored = []
    kws = [k.lower() for k in keywords if k]
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 30 or len(sent) > 600:
            continue
        hits = [kw for kw in kws if kw in sent.lower()]
        if hits:
            scored.append((len(hits), hits[0], sent))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [{"quote": s, "keyword": kw} for _, kw, s in scored[:max_quotes]]


def paraphrase_quote(quote: str, strategy: str = "semantic") -> str:
    """Produce a paraphrase of an exact quote using a deterministic strategy.

    Three strategies are supported (no LLM required, fully deterministic):
      - "semantic": reorder clauses / swap synonyms from a small academic map.
      - "summary":  condense to the core claim (first clause + main verb).
      - "structure": change the sentence frame (active<->passive-ish).

    These are deliberately conservative so they stay faithful to the source
    (no fabricated content) while demonstrating three distinct paraphrasing
    approaches for the Excel "Paraphrasing Strategies" sheets.
    """
    q = (quote or "").strip()
    if not q:
        return ""
    q = q.rstrip(".!?") + "."

    _SYN = {
        "study": "research", "studies": "studies", "show": "indicate",
        "found": "reported", "findings": "results", "results": "outcomes",
        "significant": "notable", "demonstrate": "illustrate",
        "important": "key", "however": "nonetheless", "therefore": "thus",
        "examined": "investigated", "investigate": "examine",
        "increase": "rise", "decrease": "decline", "impact": "effect",
        "affect": "influence", "use": "utilize", "using": "utilizing",
        "students": "learners", "learning": "acquisition",
    }

    if strategy == "summary":
        # Keep only up to the first clause ending — the core claim.
        first = re.split(r"[,;:]\s+", q, maxsplit=1)[0]
        return first.rstrip(".!?") + "."
    if strategy == "structure":
        # Simple frame change: prefix a hedged attribution.
        return f"According to the source, {q[0].lower()}{q[1:]}"
    # "semantic" default: swap a few academic synonyms.
    words = q.split()
    out = [_SYN.get(w.lower(), w) for w in words]
    s = " ".join(out)
    # Capitalize the first letter of the result sentence.
    if s:
        s = s[0].upper() + s[1:]
    return s


if __name__ == "__main__":
    # Quick smoke test against the live Europe PMC API (no download).
    p = {"doi": "10.1371/journal.pone.0000001", "title": ""}
    r = fetch_oa_fulltext(p)
    print("source:", r["fulltext_source"], "has_fulltext:", r["has_fulltext"])
    for k in ("introduction", "methodology", "results", "discussion"):
        v = r[k]
        print(f"  {k}: {len(v)} chars -> {v[:90]!r}")
    qs = extract_quotes_from_text(
        r["introduction"] or r["results"], ["open", "access", "data"])
    print("quotes:", len(qs))
    if qs:
        print("  Q:", qs[0]["quote"][:90])
        print("  para-semantic:", paraphrase_quote(qs[0]["quote"], "semantic")[:90])
        print("  para-summary :", paraphrase_quote(qs[0]["quote"], "summary")[:90])
        print("  para-structure:", paraphrase_quote(qs[0]["quote"], "structure")[:90])
