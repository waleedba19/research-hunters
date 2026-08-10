# AGENTS.md — For future AI sessions

This file is loaded by AI coding assistants (like opencode) when working on this repo.

## No longer using container images

The system previously used `ghcr.io/wo312092-creator/runner-base:latest` but now runs directly on `ubuntu-latest` GitHub runners. All dependencies are installed fresh each run via pip and shell commands.

## IMPORTANT: Telegram / Google Drive layer REMOVED

The Telegram bot, wizard, and Google Drive integration modules were removed from
this repo (commit "Fix test workflow - remove all Telegram/Drive references").
The following files were renamed to `*.removed` and are dead weight:
- `telegram_bot.py` → `telegram_bot.py.removed`
- `telegram_ui.py` → `telegram_ui.py.removed`
- `wizard.py` → `wizard.py.removed`
- `google_integration.py` → `google_integration.py.removed`

**Do NOT import these modules.** The core research engine (`research_hunter_v2-4.py`,
`hunt_pipeline.py`, `verify_refs/`, `precision_engine.py`) works **standalone**
with no Telegram, no Google Drive, and no secrets required. `research_hunter_v4.py`
guards all optional-module imports so it degrades gracefully when they are absent.

## Active module overview

- `research_hunter_v2-4.py` — the v6 SUPER LOADED engine (378 KB, 70+ search platforms, 14-layer PDF download chain). Runs standalone. This is the single source of truth for the search engine.
- `research_hunter_v2_4.py` — importlib shim that loads `research_hunter_v2-4.py` (dash name) under the underscore name Python requires. Re-exports the full surface.
- `research_hunter_v4.py` — wrapper over v2-4 with 11 glue functions for precision/wizard/Drive/Sheets. Optional modules are guarded with try/except so v4 imports even when they are absent.
- `hunt_pipeline.py` — non-interactive wrapper around v2-4's pipeline. `run_hunt(params, progress_callback=None) -> dict`. This is the primary entry point for GHA and local runs.
- `precision_engine.py` — ollama via HTTP (`/api/generate`) with CLI fallback. All ollama calls go through `_call_ollama`.
- `pdf_parser.py` — pdfplumber for PDF, python-docx for DOCX, odfpy for ODT. Citation patterns: APA (paren), Harvard (inline), Vancouver [n].
- `metadata_extractor.py` — regex-based, no ollama needed.
- `platform_registry.py` — wraps v2-4's PLATFORM_FNS dict with tier-based priority. Loads 81 platforms.
- `state_manager.py` — JSON file per chat_id. Atomic write via `.tmp` + `os.replace`.
- `error_handler.py` — `@retry` decorator with exponential backoff.
- `logger.py` — `get_logger(name)` returns logger with console + rotating file handlers.
- `verify_refs/` — Reference-list-driven verification (v1.0).
  - `input_parser.py` — accept folder / PDF / DOCX / TXT / pasted list → list of refs.
  - `orchestrator.py` — per-ref: search 81 platforms → ollama score → classify → optionally download.
  - `reports.py` — Excel (openpyxl, color-coded) + DOCX (python-docx, professional styling).
  - `cli.py` — `python -m verify_refs.cli --input <path> --output-folder <name>`.
  - Status: VERIFIED (≥0.85 score), LIKELY (0.60-0.85), UNVERIFIED, FAKE.
- `report_pdf.py` — DOCX→PDF via LibreOffice (6 paths) or docx2pdf. Heavy report for delivery.
- `future_studies.py` — AI-powered research gap suggestions. Uses `precision_engine._call_ollama` to generate 3-5 (configurable) gap-filling study proposals. Falls back to deterministic templates if ollama fails. `to_markdown()` renders suggestions for the report section.
- `search_cache.py` — persistent search cache (papers found vs downloaded).
- `scopus_checker.py` — quartile badge lookup.
- `run.py` — local entry point: `python run.py "<topic>"` runs `hunt_pipeline.run_hunt`.
- `gha_run_hunt.py` — GHA entry point (called by hunt-run.yml); runs `hunt_pipeline` and prints a summary.
- `hunt_intake.py` — /hunt2 intake state machine (14 steps). Telegram-dependent; guarded with fallback to `state_manager` when `telegram_bot` is absent.

## Conventions

- All functions have docstrings.
- All logging via `log = get_logger(__name__)` (logger name = module basename).
- All state mutations go through `state_manager.py`.
- All ollama calls go through `precision_engine._call_ollama`.
- All Google API calls go through `google_integration.py` (currently removed — guard imports).

## Testing locally

```bash
# 1. Install deps
pip install -r requirements.txt

# 2. Run unit tests (no GHA needed, no ollama needed)
python -m compileall -q .
python -c "import logger, error_handler, state_manager, scoring_prompts, pdf_parser, metadata_extractor, platform_registry, precision_engine, hunt_pipeline, verify_refs, verify_refs.orchestrator, verify_refs.reports, verify_refs.input_parser" && echo OK

# 3. Run specific unit tests
python tests/test_verify_refs.py --no-e2e
python tests/test_report_pdf.py
python tests/test_future_studies.py
python tests/test_health.py
python tests/generate_sample_reports.py

# 4. Run a local hunt
python run.py "impact of AI on education" --max-papers 10

# 5. Test precision engine without ollama (will skip if ollama down)
python -c "
from precision_engine import precision_search
r = precision_search('Smith 2020 deep learning', threshold=0.85)
print(f'Got {len(r)} results')
for p in r[:3]:
    print(f'  {p.get(\"title\",\"\")[:60]} (score={p.get(\"match_score\",0):.2f})')
"
```

## GHA workflows

- `research.yml` — `workflow_dispatch` only. The main research workflow: 3 jobs (verify, daily_learn, research). Has 25 inputs (278 fields, 58 study types). Runs v2-4 directly. Auto-chains subsequent runs for long research sessions.
- `ci.yml` — runs automatically on every PR + push. Fast, deterministic, offline checks: compile (warnings = errors), import smoke, unit tests (state_manager, pdf_parser, verify_refs, report_pdf, future_studies) + health check. No ollama, no network.
- `test.yml` — `workflow_dispatch` only. Full suite including the network/ollama end-to-end smoke tests (`test_hunt_smoke`, `test_verify_refs_smoke`, `scripts/verify.py`) that can't run reliably offline.
- `diagnostic.yml` — `workflow_dispatch` only. Diagnoses the core engine (v2-4, hunt_pipeline, precision_engine, ollama, platform count).
- `hunt-run.yml` — `workflow_dispatch` only. Runs `hunt_pipeline.run_hunt` with simple inputs, uploads results as artifacts.
- `bot-polling.yml` — `workflow_dispatch` only. DISABLED (Telegram bot removed); exits immediately with a notice.
- `backup.yml` — weekly tar.gz of state + logs, uploaded as artifact.
- `write-chapter.yml` — v0.2. Multi-job chapter writer via repository_dispatch.

## Common pitfalls

- **ollama not running** — workflows install ollama fresh via `curl -fsSL https://ollama.com/install.sh | sh`. If the install fails, ollama tests are skipped (not failed).
- **MemoryError on big PDFs** — `pdf_parser.parse_chapter_references` caps `full_text` at 50k chars.
- **Don't import removed modules** — `telegram_bot`, `telegram_ui`, `wizard`, `google_integration` are `.removed`. Importing them crashes. Use the guarded wrappers in `research_hunter_v4.py` or `hunt_pipeline.py` instead.
- **Sci-Hub is opt-in** — shadow-library downloads are gated behind the `scihub` workflow input / `use_scihub` param (off by default). See `DISCLAIMER.md`.
- **research.yml auto-chain** — the workflow re-dispatches itself to continue long research. It stops when `.search_complete` is written or when all found papers are downloaded. There is a hard cap to prevent runaway loops.
- **v2-4 filename has a dash** — `research_hunter_v2-4.py` cannot be imported normally; use the `research_hunter_v2_4.py` shim.
