"""
chapter_writer.py — v0.2 placeholder.

The full 8-stage chapter writer pipeline (read PDFs → summarize → themes →
outline → user approves → write sections → Node.js format → Google Doc)
will be implemented after the MVP ships. For now, this is a stub that:

- Loads the chapter state (chat_id + chapter_name from GHA env)
- If no state yet, exits gracefully (no-op for v0.1)
- Posts a Telegram message acknowledging the v0.2 request

The real implementation will:
- 1. Read all PDFs from the chapter's Drive folder, page by page (pdfplumber)
- 2. For each paper: extract full text, summarize via ollama, store summary
- 3. Cluster summaries into themes (ollama + simple keyword overlap)
- 4. Generate outline from themes + research type (wizard research_type field)
- 5. Send outline to user for approval via Telegram inline keyboard
- 6. On approval: write section-by-section draft, with exact quotes (no fabrication)
- 7. Run Node.js scripts to format into DOCX (TOC, headers) + PDF (puppeteer) + Markdown
- 8. Upload formatted DOCX to Google Docs, share with user
- 9. Multi-job chaining: each job saves state, posts repository_dispatch resume event
- 10. User gets /write_status, /write_cancel, /write_resume commands

This stub only does step 0: acknowledge the request.
"""
import os
import json
import sys
from typing import Optional
from logger import get_logger
from state_manager import load_chapter_state, save_chapter_state

log = get_logger("chapter_writer")


def main() -> int:
    chat_id = os.environ.get("CHAT_ID")
    chapter_name = os.environ.get("CHAPTER_NAME", "Untitled")
    if not chat_id:
        log.warning("CHAT_ID not provided — chapter writer is a no-op for v0.1")
        return 0
    log.info(f"chapter_writer v0.2 stub: chat_id={chat_id} chapter={chapter_name!r}")
    state = load_chapter_state(int(chat_id)) or {}
    answers = state.get("answers", {})
    # Just record that v0.2 was requested
    state["write_chapter_requested"] = True
    state["write_chapter_requested_at"] = __import__("datetime").datetime.utcnow().isoformat() + "Z"
    save_chapter_state(int(chat_id), state)
    # In v0.2 this would send: "Starting chapter writer for {chapter_name}. This will take 24-48h."
    # and start the pipeline.
    print(f"chapter_writer: acknowledged v0.2 request for chat {chat_id}, chapter {chapter_name!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
