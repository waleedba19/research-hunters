"""Deep PDF reader — page-by-page extraction, section detection, and quote mining.

This module turns a downloaded PDF into structured academic content:
  - full text (capped for memory safety)
  - per-section text (Introduction, Literature Review, Methodology, Results,
    Discussion, Conclusion) detected by headings or inferred by position
  - direct quotes (verbatim, with page numbers) relevant to the study keywords
  - a cleaned text pass (no AI-sounding artifacts: em-dashes, *I found*, filler)

Imported lazily by research_hunter_v2-4.py so the core still loads without
pdfplumber/PyMuPDF installed.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

MAX_PAGES = 60
MAX_TEXT_CHARS = 200_000  # hard memory cap (~50 pages of dense text)

# ─── Section detection ────────────────────────────────────────────────────────

# Canonical section keys in document order.
SECTION_ORDER = [
    "introduction",
    "literature_review",
    "methodology",
    "results",
    "discussion",
    "conclusion",
]

# Heading patterns. Matched case-insensitively at line start, possibly numbered
# ("1. Introduction", "1 Introduction", "I. INTRODUCTION").
_HEADING_PATTERNS = {
    "introduction": [
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?introduction\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?background\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?statement of (?:the )?problem\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?aims and (?:objectives|scope)\b",
    ],
    "literature_review": [
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?literature review\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?review of (?:the )?literature\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?theoretical framework\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?related work\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?related literature\b",
    ],
    "methodology": [
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?method(?:ology|s)?\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?research method(?:ology|s)?\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?materials and methods\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?research design\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?data (?:collection|analysis)\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?participants and (?:procedure|setting)s?\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?instrument(?:ation|s)?\b",
    ],
    "results": [
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?results?\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?findings?\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?analysis(?: of (?:the )?results)?\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?presentation of (?:the )?results?\b",
    ],
    "discussion": [
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?discussion\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?interpretation of (?:the )?results?\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?discussion of (?:the )?findings?\b",
    ],
    "conclusion": [
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?conclusion(?:s)?\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?summary and conclusion\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?concluding remarks?\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?limitations and (?:future|recommendation)\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?implications\b",
        r"^\s*(?:\d+[.\s]+|[ivxlcdm]+[.\s]+)?recommendations?\b",
    ],
}

# Pre-compiled, case-insensitive, multiline.
_COMPILED = {
    key: [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in pats]
    for key, pats in _HEADING_PATTERNS.items()
}

# Position-based fallback fractions of total text length (start, end).
_POSITION_FALLBACK = {
    "introduction":      (0.00, 0.15),
    "literature_review": (0.15, 0.40),
    "methodology":       (0.40, 0.55),
    "results":           (0.55, 0.75),
    "discussion":        (0.75, 0.88),
    "conclusion":        (0.88, 1.00),
}


def detect_sections(text: str) -> dict:
    """Split full text into academic sections.

    Returns a dict keyed by canonical section name with values:
        {"text": str, "page_hint": int|None, "inferred": bool, "char_count": int}

    Detection strategy:
      1. Heading-based: scan line-by-line for canonical section headings.
         When found, text is assigned until the next heading.
      2. Position fallback: if fewer than 2 headings matched, split by
         document-position fractions and mark ``inferred=True``.
    """
    out = {
        key: {"text": "", "page_hint": None, "inferred": True, "char_count": 0}
        for key in SECTION_ORDER
    }
    if not text or len(text) < 200:
        return out

    lines = text.split("\n")
    # Map line index -> (section_key, heading_line_index)
    heading_hits: list[tuple[int, str]] = []
    for li, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or len(stripped) > 80:
            continue  # real headings are short; body lines are long
        for key in SECTION_ORDER:
            if any(pat.match(stripped) for pat in _COMPILED[key]):
                # Avoid double-counting: only record the first heading per key.
                if not any(h[1] == key for h in heading_hits):
                    heading_hits.append((li, key))
                break

    if len(heading_hits) >= 2:
        heading_hits.sort()
        for idx, (start_li, key) in enumerate(heading_hits):
            end_li = heading_hits[idx + 1][0] if idx + 1 < len(heading_hits) else len(lines)
            # Skip the heading line itself.
            section_text = "\n".join(lines[start_li + 1:end_li]).strip()
            out[key] = {
                "text": section_text,
                "page_hint": _estimate_page(lines, start_li),
                "inferred": False,
                "char_count": len(section_text),
            }
        return out

    # Fallback: position-based split.
    total = len(text)
    for key, (frac_start, frac_end) in _POSITION_FALLBACK.items():
        s = int(total * frac_start)
        e = int(total * frac_end)
        section_text = text[s:e].strip()
        out[key] = {
            "text": section_text,
            "page_hint": None,
            "inferred": True,
            "char_count": len(section_text),
        }
    return out


def _estimate_page(lines: list[str], line_idx: int) -> Optional[int]:
    """Rough page number estimate from line index (assumes ~45 lines/page)."""
    return max(1, line_idx // 45 + 1)


# ─── Quote mining ─────────────────────────────────────────────────────────────

# Sentence splitter that keeps terminators.
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"\u201C\u2018])")


def mine_quotes(text: str, keywords: list, max_per_section: int = 6) -> list:
    """Extract verbatim quotes relevant to the study keywords.

    Returns a list of dicts:
        {"quote": str, "page": int|None, "score": int, "section": str|None}

    Quotes are whole sentences (30-400 chars) containing >=1 keyword.
    """
    if not text or not keywords:
        return []
    # Keep keywords >=3 chars, OR 2-char all-caps acronyms (AI, ML, NLP, ESL).
    kws = [k.lower() for k in keywords if k and (len(k) > 2 or (len(k) == 2 and k.isupper()))]
    if not kws:
        return []

    sentences = _SENT_SPLIT.split(text)
    scored: list[tuple[int, str]] = []
    for sent in sentences:
        sent = sent.strip().strip("\"'\u201C\u201D\u2018\u2019")
        if len(sent) < 30 or len(sent) > 400:
            continue
        score = sum(1 for kw in kws if kw in sent.lower())
        if score > 0:
            scored.append((score, sent))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"quote": q, "page": None, "score": s, "section": None}
        for s, q in scored[:max_per_section]
    ]


# ─── Text cleanup (Phase D) ───────────────────────────────────────────────────

# AI/robotic filler phrases to strip (case-insensitive, whole-phrase).
_FILLER_PATTERNS = [
    re.compile(r"\bI found\b", re.IGNORECASE),
    re.compile(r"\bIt is important to note that\b", re.IGNORECASE),
    re.compile(r"\bIt['\u2019]s important to note that\b", re.IGNORECASE),
    re.compile(r"\bIt is worth noting that\b", re.IGNORECASE),
    re.compile(r"\bIt should be noted that\b", re.IGNORECASE),
    re.compile(r"\bIn today['\u2019]s world\b", re.IGNORECASE),
    re.compile(r"\bIn the modern era\b", re.IGNORECASE),
    re.compile(r"\bIn this day and age\b", re.IGNORECASE),
    re.compile(r"\bLet['\u2019]s delve into\b", re.IGNORECASE),
    re.compile(r"\bDelve into\b", re.IGNORECASE),
    re.compile(r"\bNavigating the (?:complex|intricate) (?:landscape|world) of\b", re.IGNORECASE),
    re.compile(r"\bAt the end of the day\b", re.IGNORECASE),
    re.compile(r"\bWhen it comes to\b", re.IGNORECASE),
    re.compile(r"\bIn the realm of\b", re.IGNORECASE),
    re.compile(r"\bIn conclusion,\s*", re.IGNORECASE),
    re.compile(r"\bAs an AI\b", re.IGNORECASE),
    re.compile(r"\bAs a language model\b", re.IGNORECASE),
]


def clean_academic_text(text: str) -> str:
    """Normalize text to clean academic prose.

    Removes:
      - Markdown emphasis asterisks used by AI toning (*I found*, **bold**)
      - Em-dashes (\u2014) and en-dashes (\u2013) -> " - " or hyphen
      - AI filler phrases ("it is important to note that", etc.)
      - Stray markdown artifacts ([1], **, ##)
      - Collapses repeated whitespace
      - Curly quotes -> straight quotes
    """
    if not text:
        return ""

    # Curly quotes -> straight.
    text = text.replace("\u201C", '"').replace("\u201D", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")

    # Em-dash / en-dash -> spaced hyphen (not the AI-typical unspaced em-dash).
    text = text.replace("\u2014", " - ").replace("\u2013", " - ")
    text = text.replace("\u2026", "...")  # ellipsis char -> three dots

    # Remove markdown bold/italic markers but keep the inner text.
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"\1", text)

    # Remove markdown headers / horizontal rules.
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^---+\s*$", "", text, flags=re.MULTILINE)

    # Remove bare numeric reference markers like [1], [12] when they float.
    text = re.sub(r"\[(\d{1,3})\]", "", text)

    # Strip filler phrases.
    for pat in _FILLER_PATTERNS:
        text = pat.sub("", text)

    # Collapse whitespace.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ─── Top-level enrichment ─────────────────────────────────────────────────────


def read_pdf_deeply(pdf_path: Path, keywords: list, max_pages: int = MAX_PAGES) -> dict:
    """Read a PDF page-by-page and return structured content.

    Returns:
        {
          "pdf_text_length": int,
          "pdf_full_text": str,         # capped at MAX_TEXT_CHARS
          "pdf_sections": dict,         # detect_sections() output
          "pdf_quotes": list,           # mine_quotes() output
          "pdf_pages_read": int,
          "pdf_reader": "pdfplumber"|"pymupdf"|"none",
        }

    Never raises — PDF parsing failures return an empty-structured dict so the
    pipeline continues for other papers.
    """
    result = {
        "pdf_text_length": 0,
        "pdf_full_text": "",
        "pdf_sections": {k: {"text": "", "page_hint": None, "inferred": True, "char_count": 0} for k in SECTION_ORDER},
        "pdf_quotes": [],
        "pdf_pages_read": 0,
        "pdf_reader": "none",
    }
    if not pdf_path or not Path(pdf_path).exists():
        return result

    text = ""
    pages_read = 0
    reader = "none"

    # Prefer pdfplumber (better layout), fall back to PyMuPDF.
    try:
        import pdfplumber  # type: ignore
        with pdfplumber.open(str(pdf_path)) as pdf:
            for i, page in enumerate(pdf.pages[:max_pages]):
                page_text = page.extract_text() or ""
                if page_text:
                    text += f"\n{page_text}"
                    pages_read += 1
                if len(text) >= MAX_TEXT_CHARS:
                    break
        if text:
            reader = "pdfplumber"
    except Exception:
        text = ""

    if not text:
        try:
            import fitz  # type: ignore  # PyMuPDF
            doc = fitz.open(str(pdf_path))
            for i in range(min(max_pages, doc.page_count)):
                page_text = doc.load_page(i).get_text() or ""
                if page_text:
                    text += f"\n{page_text}"
                    pages_read += 1
                if len(text) >= MAX_TEXT_CHARS:
                    break
            doc.close()
            if text:
                reader = "pymupdf"
        except Exception:
            pass

    if not text:
        return result

    text = text[:MAX_TEXT_CHARS]
    text = clean_academic_text(text)

    sections = detect_sections(text)
    quotes = mine_quotes(text, keywords)

    # Attach section labels to quotes by locating them in section text.
    for q in quotes:
        for sec_key, sec_val in sections.items():
            if q["quote"][:40] in sec_val["text"]:
                q["section"] = sec_key
                q["page"] = sec_val["page_hint"]
                break

    result.update({
        "pdf_text_length": len(text),
        "pdf_full_text": text,
        "pdf_sections": sections,
        "pdf_quotes": quotes,
        "pdf_pages_read": pages_read,
        "pdf_reader": reader,
    })
    return result


def enrich_paper(paper: dict, pdf_path: Path, keywords: list) -> None:
    """Mutate a paper dict in place, adding deep-read fields.

    Safe to call on papers without a PDF (no-op).
    """
    if not pdf_path:
        return
    deep = read_pdf_deeply(pdf_path, keywords)
    paper["pdf_text_length"] = deep["pdf_text_length"]
    paper["pdf_full_text"] = deep["pdf_full_text"]
    paper["pdf_sections"] = deep["pdf_sections"]
    paper["pdf_quotes"] = deep["pdf_quotes"]
    paper["pdf_pages_read"] = deep["pdf_pages_read"]
    paper["pdf_reader"] = deep["pdf_reader"]
