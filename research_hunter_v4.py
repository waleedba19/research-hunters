"""
research_hunter_v4.py — Main v4 wrapper.
Imports everything from research_hunter_v2_4 (the v6 SUPER LOADED GOD MODE) and
adds 11 new glue functions for the Telegram bot, wizard, precision, Drive, Sheets.

This file is the v4 layer: v2-4's 70+ search platforms + 14-layer PDF chain stay
untouched. The new functions are mostly thin orchestrators that call v2-4 + the
new precision/wizard/google modules.
"""
import os
import sys
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from logger import get_logger
from error_handler import retry
from pdf_parser import parse_chapter_references
from metadata_extractor import extract_page1_metadata, merge_with_crossref_meta
from precision_engine import precision_search, score_paper_match, cross_source_validate, detect_reference_type
from platform_registry import search_all_platforms, get_all_platform_names
import google_integration as gdrive
from state_manager import save_chapter_state, load_chapter_state

log4 = get_logger("research_hunter_v4")

# Bring in the v2-4 universe (so callers can still do `from research_hunter_v4 import search_crossref, ...`)
try:
    sys.path.insert(0, os.path.dirname(__file__))
    from research_hunter_v2_4 import *  # noqa: F401,F403  — re-exports all 70+ search funcs + helpers
    log4.info("research_hunter_v4: re-exported v2-4 surface")
except ImportError as e:
    log4.warning(f"research_hunter_v2_4 not importable: {e}. v4 will use stub search.")

# Alias back to `log` for the rest of the file (the v2-4 `log` function is exposed as `v24_log`)
log = log4
v24_log = log4  # in case v2-4 code imported v4 to get a logger


# ============================================================================
# NEW GLUE FUNCTIONS (the 11 from the spec)
# ============================================================================

def wizard_collect_inputs(chat_id: int) -> Dict[str, Any]:
    """Stateful wizard entry point. Returns the current step's prompt dict.
    Telegram bot calls this on every incoming message; it dispatches to wizard.py.
    """
    from wizard import start_wizard, get_current_step, is_wizard_active
    if not is_wizard_active(chat_id):
        start_wizard(chat_id)
    state = load_chapter_state(chat_id)
    step = get_current_step(state or {})
    return {"state": state, "step": step}


def parse_chapter_references_w(file_path: str) -> Dict[str, Any]:
    """Wrapper that v2-4's other modules can call. Delegates to pdf_parser."""
    return parse_chapter_references(file_path)


def precision_search_w(reference_text: str, threshold: float = 0.85) -> List[Dict[str, Any]]:
    """High-precision search: 70+ platforms → ollama score → keep >= threshold."""
    return precision_search(reference_text, threshold=threshold)


def score_paper_match_w(paper: Dict[str, Any], reference_text: str) -> Dict[str, Any]:
    """Ask ollama to score 0-1 a single paper vs reference text."""
    return score_paper_match(paper, reference_text)


def cross_source_validate_w(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Confirm each paper appears in 2+ sources to eliminate hallucinations."""
    return cross_source_validate(papers)


def create_drive_folder_w(chapter_name: str) -> Optional[str]:
    """Create per-chapter folder structure in Google Drive."""
    return gdrive.create_drive_folder(chapter_name)


def create_doi_sheet_w(chapter_name: str, papers: List[Dict[str, Any]]) -> Optional[str]:
    """Create the Google Sheet with one row per verified reference."""
    return gdrive.create_doi_sheet(chapter_name, papers)


def upload_to_drive_w(local_path: str, drive_folder_id: str) -> Optional[str]:
    """Upload a downloaded PDF to a specific Drive folder."""
    return gdrive.upload_to_drive(local_path, drive_folder_id)


def telegram_send_rich_result_w(chat_id: int, papers: List[Dict[str, Any]],
                                 sheet_url: Optional[str] = None,
                                 drive_url: Optional[str] = None) -> Dict[str, Any]:
    """Build a rich result payload that the Telegram bot can send.
    The actual send is done by telegram_bot.py; this just builds the payload.
    """
    if not papers:
        return {"text": "❌ No papers matched. Try lowering the precision threshold or providing more context."}
    lines = ["📚 *Verified References:*\n"]
    for i, p in enumerate(papers[:15], 1):
        title = str(p.get("title", "Untitled"))[:100]
        authors = str(p.get("authors", "Unknown"))[:80]
        year = str(p.get("year", "n.d."))
        score = p.get("match_score", 0.0)
        doi = p.get("doi", "")
        sources = p.get("source_count", 1)
        validated = "✅" if p.get("cross_source_validated") else "⚠️"
        lines.append(f"{i}. {validated} *{title}*")
        lines.append(f"   _{authors} ({year})_")
        lines.append(f"   Score: {score:.2f} | Sources: {sources}")
        if doi:
            lines.append(f"   DOI: `{doi}`")
        lines.append("")
    if sheet_url:
        lines.append(f"\n📊 [View in Google Sheet]({sheet_url})")
    if drive_url:
        lines.append(f"📁 [View in Google Drive]({drive_url})")
    return {
        "text": "\n".join(lines),
        "parse_mode": "Markdown",
        "papers": papers,
    }


def telegram_edit_progress_w(chat_id: int, message_id: int, new_text: str) -> None:
    """Stub: actual edit happens in telegram_bot.py. This is for callers in v2-4 that want to log."""
    log.info(f"[progress] chat={chat_id} msg={message_id} text={new_text[:80]!r}")


def save_chapter_state_w(chat_id: int, state: Dict[str, Any]) -> None:
    """Persist per-chat state across bot restarts."""
    save_chapter_state(chat_id, state)


# ============================================================================
# Higher-level orchestration: the full "verify one reference" pipeline
# ============================================================================

def verify_one_reference(reference_text: str, chapter_name: str) -> Dict[str, Any]:
    """End-to-end: parse → precision_search → score → enrich → return.
    Returns: {"verified": [...], "not_found": [...], "paper_count": N, "errors": [...]}
    """
    log.info(f"verify_one_reference: chapter={chapter_name!r} ref={reference_text[:80]!r}")
    try:
        ref_type, conf = detect_reference_type(reference_text)
    except Exception as e:
        log.warning(f"detect_reference_type failed: {e}")
        ref_type, conf = "article", 0.0
    try:
        papers = precision_search(reference_text, threshold=0.85)
    except Exception as e:
        log.error(f"precision_search failed: {e}")
        return {"verified": [], "not_found": [reference_text], "paper_count": 0, "errors": [str(e)], "ref_type": ref_type}
    # Try downloading the top match's PDF using v2-4's chain
    if papers:
        top = papers[0]
        pdf_url = top.get("pdf_url") or top.get("url") or ""
        if pdf_url and "download_with_full_chain" in globals():
            try:
                from pathlib import Path
                paper_dict = {"pdf_url": pdf_url, "title": top.get("title", "untitled"), "doi": top.get("doi", "")}
                dest_dir = os.path.join(os.environ.get("LIT_REVIEW_DOWNLOADS", "/tmp/lit_downloads"), chapter_name)
                safe = re.sub(r'[\\/*?:"<>|]', '_', top.get("title", "untitled"))[:90]
                dest_path = Path(dest_dir) / f"{safe}.pdf"
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                download_with_full_chain(  # noqa: F405
                    paper_dict, dest_path,
                )
            except Exception as e:
                log.warning(f"PDF download failed: {e}")
    return {
        "verified": papers,
        "not_found": [] if papers else [reference_text],
        "paper_count": len(papers),
        "errors": [],
        "ref_type": ref_type,
    }


def verify_chapter_upload(file_path: str, chapter_name: str, max_refs: int = 35) -> Dict[str, Any]:
    """Parse a chapter file → extract references → verify each one.
    Used by the /upload command.
    """
    log.info(f"verify_chapter_upload: {file_path} chapter={chapter_name!r} max={max_refs}")
    parsed = parse_chapter_references(file_path)
    ref_list = parsed.get("reference_list", [])
    log.info(f"Extracted {len(ref_list)} reference entries from {file_path}")
    verified_all: List[Dict[str, Any]] = []
    not_found: List[str] = []
    errors: List[str] = []
    for i, ref in enumerate(ref_list[:max_refs]):
        try:
            result = verify_one_reference(ref, chapter_name)
            verified_all.extend(result.get("verified", []))
            not_found.extend(result.get("not_found", []))
            errors.extend(result.get("errors", []))
        except Exception as e:
            log.error(f"Reference {i+1} failed: {e}")
            errors.append(f"ref {i+1}: {e}")
    return {
        "chapter_name": chapter_name,
        "verified": verified_all,
        "not_found": not_found,
        "errors": errors,
        "in_text_citations_count": len(parsed.get("in_text_citations", [])),
        "reference_list_count": len(ref_list),
    }
