"""
metadata_extractor.py — Rich PDF page 1-2 metadata extraction.
Returns 25+ fields for the Google Sheet / APA citation.
"""
import os
import re
import json
from typing import Dict, Any, List, Optional
from logger import get_logger

log = get_logger("metadata_extractor")

META_FIELDS: List[str] = [
    "title", "authors", "year", "journal", "volume", "issue", "pages",
    "publisher", "issn_isbn", "doi", "url", "abstract", "keywords",
    "type", "language", "country", "affiliation", "citation_count",
    "quartile", "open_access", "pdf_in_drive", "cover_image", "match_score",
    "cross_source_validated", "verified_by", "notes", "extracted_at",
]


def extract_page1_metadata(file_path: str) -> Dict[str, Any]:
    """Extract rich metadata from the first 1-2 pages of a PDF."""
    if not os.path.exists(file_path):
        return {"error": f"file not found: {file_path}"}

    try:
        import pdfplumber  # type: ignore
    except ImportError:
        log.error("pdfplumber not installed")
        return {"error": "pdfplumber missing"}

    meta: Dict[str, Any] = {k: "" for k in META_FIELDS}
    meta["pdf_in_drive"] = False
    meta["extracted_at"] = __import__("datetime").datetime.utcnow().isoformat() + "Z"
    meta["verified_by"] = "auto"

    try:
        with pdfplumber.open(file_path) as pdf:
            # Try first 2 pages for title + authors + abstract
            text_p1 = (pdf.pages[0].extract_text() or "") if pdf.pages else ""
            text_p2 = (pdf.pages[1].extract_text() or "") if len(pdf.pages) > 1 else ""
            text = text_p1 + "\n" + text_p2
    except Exception as e:
        log.error(f"pdfplumber failed on {file_path}: {e}")
        return meta

    # --- Title (first non-empty short line near the top) ---
    meta["title"] = _extract_title(text)

    # --- Authors (line below title, comma/and separated) ---
    meta["authors"] = _extract_authors(text)

    # --- Year (4-digit) ---
    meta["year"] = _extract_year(text)

    # --- DOI ---
    meta["doi"] = _extract_doi(text)

    # --- Abstract (between ABSTRACT and INTRODUCTION/Keywords) ---
    meta["abstract"] = _extract_abstract(text)

    # --- Keywords ---
    meta["keywords"] = _extract_keywords(text)

    # --- Journal (often at top: "Journal of X, Y(Z)") ---
    meta["journal"] = _extract_journal(text)

    # --- Type (article vs book vs thesis) ---
    meta["type"] = _guess_type(text)

    return meta


def _extract_title(text: str) -> str:
    """Pick the first plausible title from the first 30 lines."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines[:30]:
        if len(line) < 8:
            continue
        if re.match(r"^\d+$", line):
            continue
        if line.lower().startswith(("volume", "vol.", "issue", "pp.", "doi:", "received", "published")):
            continue
        # Title-case lines with at least 4 words and no sentence-ending punctuation
        if re.search(r"[a-z]", line) and not line.endswith("."):
            return line[:300]
    return lines[0][:300] if lines else ""


def _extract_authors(text: str) -> str:
    """Find author block: line(s) after title with comma/and separated names."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for i, line in enumerate(lines[:30]):
        # Skip title-like lines
        if len(line.split()) <= 2:
            continue
        if re.search(r"[,&]\s+[A-Z]", line) and re.search(r"\d", line) is None:
            return line[:400]
    return ""


def _extract_year(text: str) -> str:
    """Find the most likely publication year (4 digits, 1900-2030)."""
    candidates = re.findall(r"\b(19[5-9]\d|20[0-3]\d)\b", text[:3000])
    if not candidates:
        return ""
    # Prefer the year near "received" / "published" / "©"
    for c in candidates:
        idx = text.find(c)
        ctx = text[max(0, idx - 30):idx + 30].lower()
        if any(k in ctx for k in ("received", "published", "©", "copyright")):
            return c
    return candidates[0]


def _extract_doi(text: str) -> str:
    """Find DOI in the format 10.NNNN/...."""
    m = re.search(r"\b(10\.\d{4,9}/[^\s,;\"'<>]+)", text)
    return m.group(1).rstrip(".") if m else ""


def _extract_abstract(text: str) -> str:
    """Extract text between ABSTRACT and INTRODUCTION (or first major heading)."""
    m = re.search(r"(?is)\babstract\b[:.\s]*(.+?)(?=\b(?:introduction|keywords?|1\.\s+introduction|background)\b)", text)
    if m:
        return m.group(1).strip()[:2000]
    return ""


def _extract_keywords(text: str) -> str:
    m = re.search(r"(?is)\bkeywords?\b[:.\s]*(.+?)(?=\b(?:introduction|1\.|background|method)\b)", text)
    if m:
        return m.group(1).strip()[:500]
    return ""


def _extract_journal(text: str) -> str:
    """Journal name often appears as italicized text or all-caps near the top."""
    # Common pattern: "Journal of X, Vol. Y, No. Z"
    m = re.search(r"(?im)^\s*([A-Z][A-Za-z &\-]+(?:Journal|Review|Quarterly|Studies|Research|Sciences|Letters|Bulletin)[A-Za-z &\-]*)\s*[,]?\s*(?:Vol\.?|Volume)?", text)
    if m:
        return m.group(1).strip()[:200]
    return ""


def _guess_type(text: str) -> str:
    t = text.lower()
    if "thesis" in t[:1000] or "dissertation" in t[:1000]:
        return "thesis"
    if "chapter" in t[:1000]:
        return "chapter"
    if "conference" in t[:1000] and "proceedings" in t[:1500]:
        return "conference"
    if "monograph" in t[:1500] or re.search(r"(?im)^\s*isbn", text):
        return "book"
    return "article"


def merge_with_crossref_meta(local: Dict[str, Any], crossref: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Fill in missing fields from a CrossRef/OpenAlex record."""
    if not crossref:
        return local
    merged = dict(local)
    for k, v in crossref.items():
        if not merged.get(k) and v:
            merged[k] = v
    return merged
