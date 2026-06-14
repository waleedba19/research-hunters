"""
pdf_parser.py — Parse PDF/DOCX/ODT/EPUB/TXT to extract in-text citations and reference list.
"""
import os
import re
from typing import Dict, List, Tuple, Optional
from logger import get_logger

log = get_logger("pdf_parser")

# Citation patterns (APA, Harvard, Vancouver, IEEE, MLA, Chicago — most common)
CITE_PATTERNS = [
    # APA: (Smith, 2020), (Smith & Jones, 2020), (Smith et al., 2020)
    re.compile(r"\(([A-Z][A-Za-z\u00C0-\u017F'\-]+(?:\s*(?:et\s+al\.?|&\s+[A-Z][A-Za-z\u00C0-\u017F'\-]+))?),\s*(\d{4}[a-z]?)\)"),
    # APA with page: (Smith, 2020, p. 12)
    re.compile(r"\(([A-Z][A-Za-z\u00C0-\u017F'\-]+(?:\s*(?:et\s+al\.?|&\s+[A-Z][A-Za-z\u00C0-\u017F'\-]+))?),\s*(\d{4}[a-z]?),\s*pp?\.\s*(\d+(?:-\d+)?)\)"),
    # Harvard: Smith (2020), Smith and Jones (2020)
    re.compile(r"\b([A-Z][A-Za-z\u00C0-\u017F'\-]+)(?:\s+(?:and|&)\s+([A-Z][A-Za-z\u00C0-\u017F'\-]+))?\s*\((\d{4}[a-z]?)\)"),
    # Numeric Vancouver: [1], [12, 15]
    re.compile(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\]"),
    # IEEE numeric: [1] or [12]
    re.compile(r"\[(\d+)\]"),
]

# Reference list starters
REF_LIST_HEADER_RE = re.compile(
    r"(?im)^\s*(references|bibliography|works\s+cited|literature\s+cited|bibliograph(?:y|ie))\s*$"
)


def _read_pdf_text(file_path: str, max_pages: Optional[int] = None) -> str:
    """Read text from a PDF using pdfplumber (already in v2-4 deps)."""
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        log.error("pdfplumber not installed")
        return ""
    text_parts: List[str] = []
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            if max_pages is not None and i >= max_pages:
                break
            t = page.extract_text() or ""
            text_parts.append(t)
    return "\n".join(text_parts)


def _read_docx_text(file_path: str) -> str:
    """Read text from a DOCX file."""
    try:
        import docx  # type: ignore
    except ImportError:
        log.error("python-docx not installed")
        return ""
    d = docx.Document(file_path)
    return "\n".join(p.text for p in d.paragraphs)


def _read_odt_text(file_path: str) -> str:
    """Read text from an ODT file."""
    try:
        from odf.opendocument import load  # type: ignore
        from odf.text import P  # type: ignore
    except ImportError:
        log.error("odfpy not installed")
        return ""
    doc = load(file_path)
    parts: List[str] = []
    for elem in doc.getElementsByType(P):
        parts.append("".join(n.data for n in elem.getElementsByType(__import__("odf.text", fromlist=["P"]).P) if hasattr(n, "data")))
    return "\n".join(parts)


def _read_txt_text(file_path: str) -> str:
    """Read text from a plain text file."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def extract_text(file_path: str, max_pages: Optional[int] = None) -> str:
    """Dispatch to the right parser based on file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return _read_pdf_text(file_path, max_pages=max_pages)
    if ext == ".docx":
        return _read_docx_text(file_path)
    if ext == ".odt":
        return _read_odt_text(file_path)
    if ext in (".txt", ".md"):
        return _read_txt_text(file_path)
    log.warning(f"Unsupported file extension: {ext}")
    return ""


def _find_reference_list_start(text: str) -> int:
    """Find the character index where the reference list begins."""
    m = REF_LIST_HEADER_RE.search(text)
    return m.start() if m else -1


def _parse_reference_entries(ref_text: str) -> List[str]:
    """Parse reference-list entries.
    Handles three common styles:
      (a) Numbered: "1. Smith, J. (2020)..." or "[1] Smith..."
      (b) Blank-line separated blocks
      (c) Author-year hanging indent (entries separated by single newlines)
    """
    # Strip the "References" / "Bibliography" header line if present
    cleaned = re.sub(
        r"(?im)^\s*(references|bibliography|works\s+cited|literature\s+cited|bibliograph(?:y|ie))\s*\n",
        "",
        ref_text,
    ).strip()

    entries: List[str] = []

    # Style (a): numbered list. Look for lines starting with a number or [n].
    numbered = re.findall(
        r"(?:^|\n)\s*(?:\[\d+\]|\d+\.)\s+(.+?)(?=(?:\n\s*(?:\[\d+\]|\d+\.))|\Z)",
        cleaned,
        re.DOTALL,
    )
    if len(numbered) >= 2:
        for n in numbered:
            n = re.sub(r"\s+", " ", n).strip()
            if len(n) >= 20:
                entries.append(n)
        if entries:
            return entries

    # Style (b): split on blank lines.
    blocks = re.split(r"\n\s*\n", cleaned)
    for b in blocks:
        b = re.sub(r"\s+", " ", b).strip()
        if len(b) >= 20:
            entries.append(b)
    if len(entries) >= 2:
        return entries

    # Style (c): single block — split at year positions, walking back to find entry start.
    # Each entry starts with: Author(s) (YEAR). Title. Journal/Source.
    # A new entry's year is the FIRST year in the string after a ".\s" boundary.
    if entries:
        first = entries[0]
        entries = _split_by_year_positions(first)
        if len(entries) >= 2:
            return entries

    if not entries and cleaned:
        entries = _split_by_year_positions(cleaned)

    if not entries and cleaned:
        whole = re.sub(r"\s+", " ", cleaned).strip()
        if whole:
            entries.append(whole)
    return entries


def _split_by_year_positions(text: str) -> List[str]:
    """Split text on year positions, walking back from each year to find entry start.
    Entry start = the last ".\s" that comes before the year, where what's after
    looks like an author name (Capital + word + maybe comma + maybe "et al.").
    """
    year_re = re.compile(r"\([12][0-9]{3}[a-z]?\)")
    year_positions = [m.start() for m in year_re.finditer(text)]
    if len(year_positions) < 2:
        whole = re.sub(r"\s+", " ", text).strip()
        return [whole] if whole else []

    entries: List[str] = []
    entry_starts: List[int] = [0]  # first entry always starts at 0

    for i, ypos in enumerate(year_positions):
        if i == 0:
            continue  # first year is in the first entry
        # Find the entry start for this year: look back from ypos to find a
        # position where the text after the boundary is an author name.
        # Author name pattern: Capital word, optionally followed by ", X." or "et al."
        # The boundary is just before "et al." or before the author name.
        # Walk back: the entry start is the position right after the previous
        # entry's closing period+space.

        # Find the most recent ".\s" before ypos that is preceded by a complete word
        # (i.e., not part of "et al." or initials like "J.")
        boundary = _find_entry_boundary(text, ypos)
        if boundary is not None and boundary > entry_starts[-1]:
            entry_starts.append(boundary)
    entry_starts.append(len(text))

    for j in range(len(entry_starts) - 1):
        chunk = text[entry_starts[j]:entry_starts[j + 1]]
        chunk = re.sub(r"\s+", " ", chunk).strip()
        if len(chunk) >= 20:
            entries.append(chunk)
    return entries


def _find_entry_boundary(text: str, year_pos: int) -> Optional[int]:
    """Walk back from year_pos to find the position where the current entry starts.
    Returns the character index right after the ".\s" that ends the previous entry.
    Strategy: find the ".\s" + Capital letter pattern, with a minimum distance
    of 10 chars from the year (so we skip "et al." and initials like "A.").
    """
    # Walk back from year_pos looking for ". " followed by a Capital letter.
    # Stop at the first one that's >= 10 chars before year_pos.
    # Also skip "et al." patterns (they don't end a previous entry).
    best = None
    for j in range(year_pos - 1, 0, -1):
        if text[j] == "." and j + 1 < year_pos and text[j + 1] in (" ", "\n", "\t"):
            # Skip the ". " inside "et al." — the char after is "e" not Capital
            # and inside initials like "A." — the char after is space, then might be "et" or "," or "and"
            after = text[j + 2] if j + 2 < len(text) else ""
            if after.isupper() and year_pos - (j + 2) >= 10:
                # Check that what comes after is a word of at least 2 chars (a surname)
                # and that we're not in "A. et al." (which has "et" lowercase)
                # by checking the chars after the capital
                next_chars = text[j + 2:j + 12]
                if re.match(r"[A-Z][a-z'\-]+", next_chars):
                    # Make sure this isn't followed by "et al" (which would mean it's "A. et al.")
                    if not next_chars[1:].lower().startswith("et"):
                        return j + 2
        # Don't search the whole way back — cap at 60 chars
        if year_pos - j > 80:
            break
    return best


def parse_chapter_references(file_path: str, max_pages: Optional[int] = None) -> Dict[str, any]:
    """Parse a chapter file and return:
        {
            "in_text_citations": [ {"raw": str, "author": str, "year": str, "page": str|None, "context": str}, ... ],
            "reference_list": [str, ...],  # each entry as a single string
            "full_text": str,  # raw extracted text (truncated)
        }
    """
    full_text = extract_text(file_path, max_pages=max_pages)
    if not full_text:
        log.warning(f"No text extracted from {file_path}")
        return {"in_text_citations": [], "reference_list": [], "full_text": ""}

    # Find in-text citations throughout the document
    in_text = _extract_in_text_citations(full_text)

    # Find the reference list section
    ref_start = _find_reference_list_start(full_text)
    if ref_start >= 0:
        ref_text = full_text[ref_start:]
        ref_list = _parse_reference_entries(ref_text)
    else:
        # No explicit header — assume last 30% is references
        cut = int(len(full_text) * 0.7)
        ref_text = full_text[cut:]
        ref_list = _parse_reference_entries(ref_text)

    log.info(f"Parsed {file_path}: {len(in_text)} in-text citations, {len(ref_list)} reference entries")
    return {
        "in_text_citations": in_text,
        "reference_list": ref_list,
        "full_text": full_text[:50_000],  # cap to 50k chars
    }


def _extract_in_text_citations(text: str) -> List[Dict[str, str]]:
    """Find all in-text citations and their surrounding context (1 sentence).
    Runs regex on the FULL text (not sentence-by-sentence) so citations
    like '(Smith, 2020, p. 5)' aren't broken at the inner period.
    """
    results: List[Dict[str, str]] = []
    seen: set = set()

    # Build a paren-aware sentence map: for each position, find its enclosing sentence.
    # We split on sentence boundaries OUTSIDE parens only.
    paren_depth = 0
    sentence_starts = [0]
    for i, ch in enumerate(text):
        if ch == "(":
            paren_depth += 1
        elif ch == ")":
            paren_depth = max(0, paren_depth - 1)
        elif ch in ".!?" and paren_depth == 0:
            # Mark end of sentence; start of next is i+1
            if i + 1 < len(text) and text[i + 1] in (" ", "\n", "\t"):
                sentence_starts.append(i + 1)
    # Build sentence ranges
    sentences: List[Tuple[int, int]] = []
    for j, start in enumerate(sentence_starts):
        end = sentence_starts[j + 1] if j + 1 < len(sentence_starts) else len(text)
        # Trim leading whitespace from the start position
        while start < end and text[start] in (" ", "\n", "\t"):
            start += 1
        if end > start:
            sentences.append((start, end))

    # Now run citation regex on the FULL text (so a citation never spans a sentence boundary)
    for pat in CITE_PATTERNS[:2]:
        for m in pat.finditer(text):
            raw = m.group(0)
            if raw in seen:
                continue
            seen.add(raw)
            # Find which sentence contains the match start
            ctx_start = ctx_end = m.start()
            for s_start, s_end in sentences:
                if s_start <= m.start() < s_end:
                    ctx_start, ctx_end = s_start, s_end
                    break
            entry = {
                "raw": raw,
                "context": text[ctx_start:ctx_end][:300].strip(),
            }
            if pat is CITE_PATTERNS[0]:
                entry["author"] = m.group(1)
                entry["year"] = m.group(2)
                entry["page"] = None
            elif pat is CITE_PATTERNS[1]:
                entry["author"] = m.group(1)
                entry["year"] = m.group(2)
                entry["page"] = m.group(3)
            results.append(entry)
    return results
