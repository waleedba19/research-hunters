# AGENTS.md — For future AI sessions

This file is loaded by AI coding assistants (like opencode) when working on this repo.

## No longer using container images

The system previously used `ghcr.io/wo312092-creator/runner-base:latest` but now runs directly on `ubuntu-latest` GitHub runners. All dependencies are installed fresh each run via pip and shell commands.

## Module overview

- `research_hunter_v4.py` — main entry. Imports from `research_hunter_v2_4.py` (the v6 SUPER LOADED GOD MODE) and adds 11 glue functions. If v2-4 is missing, v4 falls back to a stub registry with a warning.
- `telegram_bot.py` — long-polling bot. Uses stdlib `urllib` for Telegram API (no `python-telegram-bot` dep needed). Also has `requests` in requirements for file uploads. Has `/verifyrefs` command for reference-list-driven mode.
- `wizard.py` — pure state machine. 11 research types. Every step has a Skip except research type + chapter name.
- `precision_engine.py` — ollama via HTTP (`/api/generate`) with CLI fallback.
- `google_integration.py` — uses OAuth refresh token from `GOOGLE_OAUTH_REFRESH` env var. Falls back to `memory.json` if env not set.
- `state_manager.py` — JSON file per chat_id. Atomic write via `.tmp` + `os.replace`.
- `pdf_parser.py` — pdfplumber for PDF, python-docx for DOCX, odfpy for ODT. Citation patterns: APA (paren), Harvard (inline), Vancouver [n].
- `metadata_extractor.py` — regex-based, no ollama needed.
- `platform_registry.py` — wraps v2-4's PLATFORM_FNS dict with tier-based priority.
- `chapter_writer.py` — v0.2 STUB. Real implementation comes after MVP.
- `error_handler.py` — `@retry` decorator with exponential backoff.
- `logger.py` — `get_logger(name)` returns logger with console + rotating file handlers.
- `verify_refs/` — Reference-list-driven verification (v1.0 NEW).
  - `input_parser.py` — accept folder / PDF / DOCX / TXT / pasted list → list of refs.
  - `orchestrator.py` — per-ref: search 81 platforms → ollama score → classify → optionally download.
  - `reports.py` — Excel (openpyxl, color-coded) + DOCX (python-docx, professional styling).
  - `cli.py` — `python -m verify_refs.cli --input <path> --output-folder <name>`.
  - Status: VERIFIED (≥0.85 score), LIKELY (0.60-0.85), UNVERIFIED, FAKE.
- `report_pdf.py` — v6.4 DOCX→PDF via LibreOffice (6 paths) or docx2pdf. Heavy report for Telegram delivery.
- `future_studies.py` — v6.5 AI-powered research gap suggestions. Uses `precision_engine._call_ollama` to generate 3-5 (configurable) gap-filling study proposals. Falls back to 5 deterministic templates if ollama fails. `to_markdown()` renders suggestions for the report section.
- `hunt_intake.py` — v6.3 5-step /hunt2 state machine (title, research_type, platforms, max_papers, download_pdfs). Wired into `telegram_bot._run_v2_hunt_from_intake` with heartbeat every 5 min.

## Conventions

- All functions have docstrings.
- All logging via `log = get_logger(__name__)` (logger name = module basename).
- All state mutations go through `state_manager.py`.
- All ollama calls go through `precision_engine._call_ollama`.
- All Google API calls go through `google_integration.py`.
- All Telegram API calls go through `telegram_bot._tg_call`.

## Testing locally

```bash
# 1. Set env vars
export TELEGRAM_BOT_TOKEN=...
export GOOGLE_OAUTH_REFRESH=...

# 2. Run unit tests (no GHA needed)
python -m compileall -q .
python -c "import telegram_bot, precision_engine, wizard, google_integration, pdf_parser" && echo OK

# 3. Run a single /find
python -c "
import telegram_bot
# Send /find to chat 12345 manually...
"

# 4. Test precision engine without Telegram
python -c "
from precision_engine import precision_search
r = precision_search('Smith 2020 deep learning', threshold=0.85)
print(f'Got {len(r)} results')
for p in r[:3]:
    print(f'  {p.get(\"title\",\"\")[:60]} (score={p.get(\"match_score\",0):.2f})')
"
```

## GHA workflows

- `bot-polling.yml` — runs every 5 min. Long-polls Telegram, processes up to 25 updates per cycle, exits. Total compute: ~144 min/day.
- `test.yml` — runs on PR + push. Unit tests for state_manager, wizard, pdf_parser.
- `backup.yml` — weekly tar.gz of state + logs, uploaded as artifact.
- `write-chapter.yml` — v0.2. Multi-job chapter writer via repository_dispatch.

## Common pitfalls

- **ollama not running** — first step in every workflow is `/usr/local/bin/ollama-start.sh`. If the script is missing, the ollama model is still in the image but needs a server.
- **MemoryError on big PDFs** — `pdf_parser.parse_chapter_references` caps `full_text` at 50k chars.
- **Drive 15 GB cap** — supervisor email should be added to folder ACL for auto-sharing.
- **No Node.js in image** — `write-chapter.yml` installs Node.js 20 via `actions/setup-node@v4` BEFORE running chapter_writer.py.
- **Wizard in bad state** — `/cancel` or `/reset` clears the chat state file.
- **Google OAuth expired** — refresh token is long-lived, but if it expires, user must re-authorize via `oauth_flow.py`.
