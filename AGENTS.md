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
- `hunt_intake.py` — /hunt2 intake state machine (`HUNT_STEPS`, 14 steps: research_type, title, field, rq_angle, research_questions, year_range, language, country, paper_type, quartile_filter, open_access, platforms, max_papers, download_pdfs). Only `title` is required; every other step is skippable. Wired into `telegram_bot._run_v2_hunt_from_intake` with heartbeat every 5 min.
- `fulltext_reader.py` — no-download full-text reader. Reads the *content* of open-access papers from Europe PMC (JATS XML) and CORE APIs WITHOUT downloading any PDF, filling introduction/methodology/results/discussion with real text. Also provides `extract_quotes_from_text()` and `paraphrase_quote()` (3 deterministic strategies: semantic/summary/structure). The no-download counterpart to the PDF extraction in `research_hunter_v2-4.py`.
- `paper_db.py` — SQLite-backed paper store (the single source of truth). Replaces the JSON-based SearchCache for large (10k–100k paper) multi-day runs. WAL mode, incremental crash-safe transactions, indexed O(log n) dedup, no giant results.json load/merge at the end (generates results.json from the DB only for report compat). Drop-in compatible with SearchCache for the pipeline surface (`mark_found`, `mark_downloaded`, `filter_new`, `deduplicate`, `add_queries`, `queries_used`, `record_run`, `stats`, `save`). Extra: `upsert_paper`, `bulk_upsert`, `get_all_papers`, `iter_papers`, `export_results_json`, `vacuum`. Tests in `tests/test_paper_db.py` (46 tests incl. 10k stress + concurrency + corruption recovery) and `tests/test_pipeline_db.py` (25 tests incl. multi-chunk accumulation simulation).
- `run_guard.py` — runtime safety guards for long (6-10 day) continuous runs: `disk_guard()` (abort chunk gracefully on ENOSPC, the #1 killer of long chains; emits emergency chain progress so the next chunk can retry after the artifact upload frees space), `DBMaintenance` (periodic SQLite VACUUM to bound growth across 100k papers), `CircuitBreaker` (per-platform fail-fast: 5 failures in 10 min → skip that source for the rest of the chunk so one flaky platform can't burn the 3-hour budget). Wired into `search_all` (per-platform skip + failure recording) and `run_hunt` (disk check before search, DB maintenance after each batch). `error_handler.TransientHTTPError` (HTTP 429/5xx) is now retryable by default. Tests in `tests/test_run_guard.py` (21 tests: disk low/high/never-raise, log cleanup, DB VACUUM threshold, circuit trip/half-open/reset, TransientHTTPError retry).

## Stability hardening (6-10 day continuous runs)

Key risks for 100k-paper / multi-day runs and how they're handled:

- **JSON corruption / memory** — the old SearchCache loaded+merged+wrote the whole results.json (100s of MB at 100k papers) at the end of every chunk; one write failure = total loss, and holding 100k dicts in memory risks OOM. PaperDB fixes this: papers persist incrementally in SQLite transactions (a mid-chunk crash never loses found papers), dedup is an indexed lookup, and results.json is generated atomically (`.tmp` + `os.replace`) from the DB only when a report is needed.
- **Disk exhaustion (ENOSPC)** — GitHub runners have ~14 GB; PDFs + DB + artifacts can fill it over many chunks. `disk_guard()` checks free space before search and aborts the chunk cleanly (emitting chain progress) so the next chunk retries after the artifact upload frees space. `cleanup_old_logs` bounds log accumulation.
- **One flaky platform dragging the run** — `CircuitBreaker` skips a platform after 5 failures in 10 min, so a single broken source can't consume the whole chunk's budget.
- **Lost chain signal on crash** — previously, if `run_hunt` crashed, no `_chain_progress.json` was emitted, so the workflow stopped the chain (losing the run). Now a top-level `__main__` guard catches any fatal exception, prints the traceback, and emits an emergency `_chain_progress.json` so the auto-chain step can decide. The process exits 0 so the workflow step doesn't fail the whole run.
- **Infinite loop** — a bug could make the chain never exhaust queries and re-run forever. A hard safety cap stops the chain at ~80 chunks (≈ 10 days at 3h/chunk) even if work technically remains; override with `CI_MAX_CHUNKS` for longer runs.
- **DB bloat** — `DBMaintenance` VACUUMs every ~15k new papers (configurable via `CI_VACUUM_EVERY`) so the DB + WAL don't grow unbounded.
- **Transient HTTP errors** — `error_handler.retry` now retries HTTP 429/5xx (`TransientHTTPError`) in addition to connection/timeout errors, with exponential backoff.
- **Atomic writes** — both `results.json` and `_chain_progress.json` are written via `.tmp` + `os.replace` so a crash mid-write never leaves a truncated file.

## No-download vs Download modes (symmetric design)

The pipeline now has two symmetric full-text paths that populate the SAME report fields (introduction/methodology/results/discussion + exact quotes), so the 40+ Excel sheets, DOCX, and PDF reports carry genuine content in either mode:

| Mode | How full text is obtained | OCR? | Storage |
|---|---|---|---|
| **No-download** (DOWNLOAD PDFs OFF) | Europe PMC `fullTextXML` + CORE API — no file saved | n/a (XML is selectable text) | reports only (Excel + DOCX + PDF) |
| **Download** (DOWNLOAD PDFs ON) | reads each downloaded PDF page-by-page via pdfplumber/PyMuPDF (ALL pages, no cap) | Tesseract fallback for scanned/image PDFs | reports + PDF files |

Paywalled papers in no-download mode fall back to the abstract only. The Excel `_load_real_papers` shows "Abstract used (no OA full text)" for those.

## Auto-chain (multi-version runs over many days)

`research.yml`'s `research` job runs in 3-hour chunks (GitHub's job limit). After each chunk, "Auto-trigger next run" checks `_chain_progress.json` (emitted by the Python pipeline) and either stops or dispatches the same workflow again, preserving ALL inputs. Completion signals (work in BOTH modes):
- `queries_exhausted` = True → a chunk found no new papers (all queries explored); stop.
- `limit_reached` = True → cumulative unique papers >= the selected `paper_limit`; stop.
- (download mode only) all found papers downloaded; stop.

Each chunk downloads the previous run's artifact (`research-data-<folder>`) and merges (`cache.deduplicate(new + existing)`), so the final ZIP is cumulative. The `_chain_progress.json` file replaces the old broken logic that read non-existent `papers_found`/`queries_exhausted` keys from the SearchCache JSON.

Safety guard: if `paper_limit` >= 10,000 (keys 9–12) AND `download_pdfs` ON, the workflow forces no-download (the Excel still has every DOI/URL link) because downloading 10k+ PDFs exceeds GitHub's 10 GB artifact cap and the runner disk.


- `run_no_download.py` — NEW. Run the hunt WITHOUT downloading PDFs. Searches all platforms, checks quartiles, dedupes, then produces the 40-sheet Excel (from REAL results) + full DOCX report + PDF report + master XLSX + markdown. Usage: `python3 run_no_download.py "<topic>" [field] --platforms crossref,openalex --max-papers N`. The `skip_download=True` param on `run_hunt` powers it (PDF fetch is skipped; quartile + doctype + geo detection still run).
- `generate_ultimate_excel_v10.py` — 40+ sheet Excel generator. Default mode uses built-in sample data. Real-data mode: pass a `results.json` path as the first CLI arg and it maps real hunt papers into the 40-sheet layout. Narrative sections (introduction/methodology/results/discussion) are filled with REAL text from Europe PMC/CORE (no-download mode) or the downloaded PDF (download mode), falling back to the abstract for paywalled papers. Also produces dedicated "Exact Quotes", "Paraphrase - Semantic", "Paraphrase - Summary", and "Paraphrase - Structure" sheets.
- `report_pdf.py` — DOCX→PDF via LibreOffice (6 paths + `/usr/lib/libreoffice/program/soffice`) or docx2pdf. Sets `LD_LIBRARY_PATH` to the resolved soffice program dir because some Linux wrappers don't export it (libreglo.so not found otherwise).

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
- `ci.yml` — runs automatically on every PR + push. Fast, deterministic, offline checks: compile (warnings = errors), import smoke, unit tests (state_manager, pdf_parser, verify_refs, hunt_intake, report_pdf, drive_integration, future_studies) + health check. No ollama, no network.
- `test.yml` — `workflow_dispatch` only. Full suite including the network/ollama end-to-end smoke tests (`test_hunt_smoke`, `test_verify_refs_smoke`). Requires ollama: the job runs `ollama serve` then `ollama pull qwen2.5vl:3b` (the model precision_engine uses) — without the pull, every `_call_ollama` returns a parse failure → score 0.00 → all refs UNVERIFIED.
- `research.yml` — the user-facing "Run workflow" entry. Has a **`download_pdfs` toggle button** (default OFF): OFF = reports only (40-sheet Excel + DOCX + PDF, no PDF downloads); ON = reports + actual PDF file downloads. Generates the 40-sheet `ULTIMATE_RESEARCH_SYNTHESIS_V10.xlsx` from `results.json` and converts the DOCX report to PDF via LibreOffice (auto-installed if missing).

## No-download run mode

- `run_no_download.py` — standalone CLI: runs `hunt_pipeline.run_hunt(skip_download=True)`, then builds the 40-sheet Excel from `results.json`, and reports all DOCX/PDF/XLSX/MD outputs. Searches + dedupes + quartile/doc-type/geo detection still run; only the `smart_file_paper` PDF download step is skipped.
- `hunt_pipeline.run_hunt(skip_download=...)` — when True, 0 PDFs are downloaded (fast), but all report generation (master_papers.xlsx, research_report.md/.docx, future studies) still runs.
- `generate_ultimate_excel_v10.py <results.json>` — first CLI arg = a real `results.json` path → builds the 40-sheet workbook from actual hunt papers. No arg = sample mode (40 sheets of demo data). Default output path is script-relative (no hardcoded Windows path); auto-mkdirs.

## Common pitfalls

- **ollama "alive" but model not pulled** — `curl localhost:11434/api/tags` succeeds as soon as `ollama serve` starts, but scoring returns 0.00 until `ollama pull qwen2.5vl:3b` completes. Always pull the model before scoring-dependent tests.
- **Wrong xlsx filename** — `hunt_pipeline.run_hunt` produces `master_papers.xlsx` (via v2-4 `_write_master_xlsx`), NOT `master_database.xlsx` (that's the CSV name + a legacy label in the summary string).
- **verify_refs report kwarg** — `build_excel_report`/`build_docx_report` take `source_description=` (not `source_desc=`). The orchestrator passes `source_description=source_desc`.
- **ollama not running** — first step in every workflow is `/usr/local/bin/ollama-start.sh`. If the script is missing, the ollama model is still in the image but needs a server.
- **MemoryError on big PDFs** — `pdf_parser.parse_chapter_references` caps `full_text` at 50k chars.
- **Drive 15 GB cap** — supervisor email should be added to folder ACL for auto-sharing.
- **No Node.js in image** — `write-chapter.yml` installs Node.js 20 via `actions/setup-node@v4` BEFORE running chapter_writer.py.
- **Google OAuth expired** — refresh token is long-lived, but if it expires, user must re-authorize via `oauth_flow.py`.
