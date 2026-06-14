"""
verify_refs/input_parser.py — Accept folder / file / pasted list, return list of reference strings.
"""
import os
import re
from typing import List, Optional, Tuple
from logger import get_logger

log = get_logger("verify_refs.input_parser")

# Extensions we can parse
PARSABLE_EXT = {".pdf", ".docx", ".odt", ".txt", ".md"}

# Numbered prefix at line start: [1], 1., 1)
NUMBERED_PREFIX_RE = re.compile(r"^\s*(?:\[\d+\]|\d+[\.\)])\s+(.+)$", re.DOTALL)
# Year-in-parens anywhere (for "by-year" splitting)
YEAR_RE = re.compile(r"\((1[89]\d\d|20\d\d|21\d\d)\)?[a-z]?\)")


def _is_pasted_list(text: str) -> bool:
    """Heuristic: a pasted list is a string with multiple newlines, no
    'References' header, and at least 2 numbered lines or year markers."""
    has_ref_header = bool(re.search(
        r"(?im)^\s*(references|bibliography|works\s+cited)\s*$", text))
    if has_ref_header:
        return False
    lines = [l for l in text.splitlines() if l.strip()]
    numbered = sum(1 for l in lines if re.match(r"^\s*(\[\d+\]|\d+[\.\)])", l))
    year_marks = len(YEAR_RE.findall(text))
    return numbered >= 2 or year_marks >= 3


def _split_pasted_list(text: str) -> List[str]:
    """Split a pasted list of references into individual entries.

    Handles:
      (a) Numbered lines: '[1] Smith 2020...' or '1. Smith 2020...'
      (b) Blank-line separated blocks
      (c) Year-position based splitting (fallback)
    """
    cleaned = text.strip()
    if not cleaned:
        return []

    # (a) Numbered lines
    entries: List[str] = []
    matches = list(re.finditer(
        r"(?:^|\n)\s*(?:\[\d+\]|\d+[\.\)])\s+(.+?)(?=(?:\n\s*(?:\[\d+\]|\d+[\.\)]))|\Z)",
        cleaned, re.DOTALL))
    if len(matches) >= 2:
        for m in matches:
            entry = re.sub(r"\s+", " ", m.group(1)).strip()
            if len(entry) >= 20:
                entries.append(entry)
        if entries:
            return entries

    # (b) Blank-line separated
    blocks = re.split(r"\n\s*\n+", cleaned)
    entries = []
    for b in blocks:
        b = re.sub(r"\s+", " ", b).strip()
        if len(b) >= 20:
            entries.append(b)
    if len(entries) >= 2:
        return entries

    # (c) Fallback: one entry per non-empty line
    entries = []
    for line in cleaned.splitlines():
        line = line.strip()
        if len(line) >= 20:
            entries.append(line)
    return entries


def _parse_pdf_or_docx(file_path: str) -> List[str]:
    """Use pdf_parser.parse_chapter_references for PDF/DOCX/ODT files."""
    try:
        from pdf_parser import parse_chapter_references
    except ImportError:
        log.error("pdf_parser not importable")
        return []
    try:
        result = parse_chapter_references(file_path)
        ref_list = result.get("reference_list") or []
        log.info(f"Parsed {file_path}: {len(ref_list)} reference entries")
        return ref_list
    except Exception as e:
        log.error(f"Failed to parse {file_path}: {e}")
        return []


def _parse_txt_or_md(file_path: str) -> List[str]:
    """Read a text file and split into reference entries."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception as e:
        log.error(f"Failed to read {file_path}: {e}")
        return []

    # If text contains a 'References' header, take everything after it
    m = re.search(
        r"(?im)^\s*(references|bibliography|works\s+cited|literature\s+cited)\s*\n",
        text)
    if m:
        text = text[m.end():]

    return _split_pasted_list(text) if _is_pasted_list(text) else [text.strip()] if text.strip() else []


def parse_input(input_path: str) -> Tuple[List[str], str]:
    """Parse the input and return (list of reference strings, source description).

    Args:
        input_path: either a folder path, a single file path, or pasted text
                    starting with "PASTED:" prefix to force text mode.

    Returns:
        (refs, description) - the list of reference strings and a human
        description of what was parsed (for the report header).
    """
    # Pasted text mode
    if input_path.startswith("PASTED:"):
        text = input_path[len("PASTED:"):]
        refs = _split_pasted_list(text)
        return refs, f"pasted list ({len(refs)} entries)"

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input not found: {input_path}")

    # Folder mode
    if os.path.isdir(input_path):
        all_refs: List[str] = []
        files_processed: List[str] = []
        for root, _, files in os.walk(input_path):
            for fname in sorted(files):
                ext = os.path.splitext(fname)[1].lower()
                full = os.path.join(root, fname)
                if ext == ".pdf" or ext == ".docx" or ext == ".odt":
                    refs = _parse_pdf_or_docx(full)
                    all_refs.extend(refs)
                    if refs:
                        files_processed.append(f"{fname} ({len(refs)} refs)")
                elif ext in (".txt", ".md"):
                    refs = _parse_txt_or_md(full)
                    all_refs.extend(refs)
                    if refs:
                        files_processed.append(f"{fname} ({len(refs)} refs)")
        return all_refs, f"folder: {input_path} — {len(files_processed)} files: " + ", ".join(files_processed[:5])

    # Single file mode
    ext = os.path.splitext(input_path)[1].lower()
    if ext not in PARSABLE_EXT:
        raise ValueError(
            f"Unsupported extension {ext!r}. Use one of: {sorted(PARSABLE_EXT)}")
    if ext in (".pdf", ".docx", ".odt"):
        refs = _parse_pdf_or_docx(input_path)
    else:
        refs = _parse_txt_or_md(input_path)
    return refs, f"file: {os.path.basename(input_path)} ({len(refs)} refs)"


def parse_pasted_text(text: str) -> List[str]:
    """Parse a pasted text block into references. Used by Telegram /verifyrefs
    when the user pastes a list as a chat message."""
    return _split_pasted_list(text) if _is_pasted_list(text) else [text.strip()] if text.strip() else []
