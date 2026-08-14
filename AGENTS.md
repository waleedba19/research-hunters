# AGENTS.md — For future AI sessions

This file is loaded by AI coding assistants (like opencode) when working on this repo.

## Architecture (post-stabilization, Aug 2026)

The Telegram long-polling bot was **removed** (not required). The system is now a
transport-agnostic research core: the **93-platform** hunt engine + verify_refs pipeline
run with **zero secrets**. Google Drive/Sheets and Telegram push are **optional
transports** layered on top when configured.

- `research_hunter_v4.py` — main entry. Re-exports the full v2-4 surface (93 platforms)
  + 11 glue functions + `verify_one_reference` / `verify_chapter_upload` pipelines.
  Imports `google_integration` **lazily** (inside the 3 Drive wrapper functions) so the
  core loads even when Drive isn't configured. Same for `wizard` (already lazy).
- `research_hunter_v2_4.py` — shim that loads `research_hunter_v2-4.py` (dash name) via
  importlib. The dash file is the 378 KB v7 SUPER LOADED (93 platforms + 14-layer
  download chain + deep Excel with clickable hyperlinks + DOCX synthesis).
- `hunt_pipeline.py` — non-interactive wrapper around v2-4's pipeline. `run_hunt(params, progress_callback)`.
- `gha_run_hunt.py` — called by hunt-run.yml on GHA. Telegram push is **env-gated**
  (`TG_ENABLED = bool(CHAT_ID and TELEGRAM_BOT_TOKEN)`); hunt + console + Drive always work.
- `hunt_intake.py` — /hunt2 intake state machine (14 steps). State now goes through
  `state_manager` (was `telegram_bot`). Only `title` is required; every other step skippable.
- `wizard.py` — pure state machine. 11 research types. Every step has Skip except
  research type + chapter name. No Telegram coupling in its body.
- `google_integration.py` — Drive + Sheets + Docs. Service-account-first, OAuth-fallback,
  env-var fallback. Graceful `get_credential_status()`. Imports cleanly without creds.
- `precision_engine.py` — ollama via HTTP (`/api/generate`) with CLI fallback.
- `pdf_parser.py` — pdfplumber for PDF, python-docx for DOCX, odfpy for ODT.
- `metadata_extractor.py` — regex-based, no ollama needed.
- `platform_registry.py` — wraps v2-4's PLATFORM_FNS dict with tier-based priority.
- `chapter_writer.py` — v0.2 STUB. Real implementation comes after MVP.
- `error_handler.py` — `@retry` decorator with exponential backoff.
- `logger.py` — `get_logger(name)` returns logger with console + rotating file handlers.
- `state_manager.py` — JSON file per chat_id. Atomic write via `.tmp` + `os.replace`.
  Honors `STATE_DIR` env var (used by tests for isolation).
- `run.py` — system status & health entrypoint (was the Telegram launcher). Reports
  module health, platform count, transport status, and entry points.
- `verify_refs/` — Reference-list-driven verification (v1.0).
  - `input_parser.py` — accept folder / PDF / DOCX / TXT / pasted list → list of refs.
  - `orchestrator.py` — per-ref: search 93 platforms → ollama score → classify → optionally download.
  - `reports.py` — Excel (openpyxl, color-coded) + DOCX (python-docx, professional styling).
  - `cli.py` — `python -m verify_refs.cli --input <path> --output-folder <name>`.
  - Status: VERIFIED (≥0.85 score), LIKELY (0.60-0.85), UNVERIFIED, FAKE.
- `report_pdf.py` — v6.4 DOCX→PDF via LibreOffice (6 paths) or docx2pdf. On Linux,
  injects `LD_LIBRARY_PATH` for LibreOffice's bundled libs (libreglo.so) via
  `_libreoffice_env()` — scoped to the soffice subprocess only, never global.
- `deep_reader.py` — v7 PDF deep-reading engine. Reads downloaded PDFs page
  by page (pdfplumber→PyMuPDF fallback, capped at 60 pages / 200k chars),
  splits text into academic sections (Introduction / Literature Review /
  Methodology / Results / Discussion / Conclusion) via heading regex with
  position-based fallback (flagged `inferred`), mines verbatim quotes with
  page hints, and applies `clean_academic_text()` (strips `*I found*`,
  em-dashes, markdown bold/italic, `[1]` ref markers, AI filler phrases,
  curly-quote normalization). Called from `smart_file_paper()` via
  `enrich_paper_with_pdf_content()` after every successful download. Stores
  `pdf_full_text`, `pdf_sections`, `pdf_quotes`, `pdf_pages_read`, `pdf_reader`
  on each paper dict. Never raises — failures are no-ops so the pipeline
  continues. Imported lazily so the core loads without pdfplumber/PyMuPDF.
- `generate_ultimate_excel_v10.py` — 40-sheet standalone Excel builder (v10).
  `research_hunter_v2-4.py._write_master_xlsx()` is the live 48-sheet builder
  used by hunts: dashboard + folder sheets + Master Metadata + Download Links
  (clickable PDF/DOI/Source hyperlinks) + 6 Deep section sheets (page-by-page
  extracted text, color-tinted) + Author Quotes + Source URL List + APA refs.
- `future_studies.py` — v6.5 AI-powered research gap suggestions. Falls back to
  deterministic templates if ollama fails.
- `fanout_merge.py` — Fan-out → Merge unified workflow. Splits a research topic
  into parallel sub-hunts (one per research question / aspect), runs each via
  `hunt_pipeline.run_hunt`, then merges all `report_data` dicts into one unified
  report with deduplication (DOI → title-hash → URL priority), stat aggregation
  (q/type/geo distributions summed), and query/platform union. `merge_reports()`
  is the core merge; `split_into_subhunts()` splits; `fanout_and_merge()` runs
  the full pipeline and generates unified DOCX + Excel + PDF. Activated in v2-4's
  `main()` when `params["fanout_mode"] == "on"` (set via `CI_FANOUT_MODE` env).
- `synthesis_engine.py` — v7 **deep research synthesis engine**. Six deterministic
  analytical passes over the corpus, driven by deep_reader output (pdf_sections +
  pdf_quotes), not just metadata:
  1. `cluster_papers_by_theme()` — thematic clustering from section text + keywords
  2. `build_citation_network()` — detects cites / extends / supports / contradicts
     by scanning full text for title + author mentions + methodological inheritance
  3. `detect_convergence()` — clusters Results/Discussion sentences, flags agreement
     vs. contradiction
  4. `map_methodological_lineage()` — extracts design + analysis + sample, orders
     chronologically to show method evolution
  5. `extract_thematic_quotes()` — verbatim quotes with (Author, Year, p. N) citations
  6. `identify_research_gaps()` — data-driven gaps (geographic, temporal,
     methodological, quartile, convergence, thematic), not templated
  `synthesize(papers)` returns one bundle the DOCX generator consumes. Never raises.
- `chapter_writer.py` — v0.2 STUB. Real implementation comes after MVP.

## REMOVED (do not resurrect)

- `telegram_bot.py`, `telegram_ui.py` — deleted (long-polling bot not required).
- `bot-polling.yml` — deleted (depended on telegram_bot).
- Telegram-only tests: `smoke_telegram_ui.py`, `test_telegram_ui.py`.
- `.git-rewrite/`, `nohup.out`, `tmp_dispatch_test.py`, `send_test.py` — junk removed.

## Conventions

- All functions have docstrings.
- All logging via `log = get_logger(__name__)` (logger name = module basename).
- All state mutations go through `state_manager.py` (`load_chapter_state`/`save_chapter_state`).
- All ollama calls go through `precision_engine._call_ollama`.
- All Google API calls go through `google_integration.py`.
- **Optional dependencies must be imported lazily** (inside functions, try/except) so the
  core loads with zero credentials. Do not add top-level `import google_integration` etc.

## Testing locally

```bash
# 1. Install deps
pip install -r requirements.txt

# 2. Fast offline checks (mirrors ci.yml)
python -W error::SyntaxWarning -m compileall -q .
python -c "import logger, error_handler, state_manager, wizard, scoring_prompts, pdf_parser, metadata_extractor, platform_registry, google_integration, precision_engine, research_hunter_v4, hunt_intake, hunt_pipeline, future_studies, report_pdf, chapter_writer, deep_reader, synthesis_engine, verify_refs, verify_refs.orchestrator, verify_refs.reports, verify_refs.input_parser" && echo OK
python tests/test_verify_refs.py --no-e2e
python tests/test_deep_reader.py
python tests/test_synthesis_engine.py
python tests/test_hunt_intake.py
python tests/test_fanout_merge.py
python tests/test_hunt_intake_e2e.py
python tests/test_report_pdf.py
python tests/test_future_studies.py
python tests/test_health.py
python generate_ultimate_excel_v10.py
python run.py   # system status

# 3. Verify a reference list
python -m verify_refs.cli --input tests/sample_refs.txt --output-folder my_report
```

## GHA workflows

- `ci.yml` — runs on every PR + push. Fast, deterministic, offline: compile (warnings =
  errors), full import smoke (covers v4/wizard/google_integration/hunt_intake), unit tests
  (state_manager, wizard, pdf_parser, verify_refs, hunt_intake, google_integration API
  surface, report_pdf, future_studies), sample reports, Excel v10, health check. No ollama.
- `test.yml` — `workflow_dispatch` only. Full suite including the network/ollama end-to-end
  smoke tests (`test_hunt_smoke`, `test_verify_refs_smoke`). Uploads reports as artifacts.
- `diagnostic.yml` — `workflow_dispatch`. Full system check: secrets, ollama, all modules,
  google_integration status, platform count. No telegram.
- `hunt-run.yml` — `workflow_dispatch`. Runs gha_run_hunt.py (Telegram push optional).
- `backup.yml` — weekly tar.gz of state + logs, uploaded as artifact.
- `write-chapter.yml` — v0.2. Multi-job chapter writer via repository_dispatch.
- `research.yml` — large workflow_dispatch research runner. Has a `fanout_mode`
  input (off/on). When "on", the `merge` job runs after `research` to generate
  the unified DOCX + Excel + PDF from the merged report_data.

## Common pitfalls

- **`requests` must be installed** — v2-4 imports it at top level. If missing, the whole
  v2-4 surface fails to load (and v4/platform_registry fall back to empty). It's in requirements.txt.
- **ollama not running** — first step in test.yml/diagnostic.yml is ollama install + serve.
  Tests requiring ollama skip gracefully if it's not up.
- **MemoryError on big PDFs** — `pdf_parser.parse_chapter_references` caps `full_text` at 50k chars.
- **Drive 15 GB cap** — supervisor email should be added to folder ACL for auto-sharing.
- **No hardcoded paths** — `generate_ultimate_excel_v10.py` was fixed to use `Path(__file__)`
  instead of a Windows path. Don't reintroduce hardcoded OS-specific paths.
- **Google OAuth expired** — refresh token is long-lived, but if it expires, re-authorize.
- **State isolation in tests** — set `STATE_DIR` env var to a temp dir; state_manager honors it.

## Chain workflow (multi-day runs) — critical design

The `.github/workflows/research.yml` workflow chains multiple 3h-limited GitHub Actions runs into one logical multi-day run via `workflow_dispatch` self-retriggering. SIX bugs defeated this (all fixed); do not reintroduce them:

1. **Chain breaks on 3h timeout** — the python step must write `results.json` (and `cache.save()`) IMMEDIATELY after the search phase, BEFORE downloads. If results.json only exists at the end, a timeout cancel mid-download means `check_results` sees 0 results → `status=no_results` → the auto-trigger `if:` never fires → chunk 2 never runs → all search progress lost. The auto-trigger uses `if: always() && steps.check_results.outputs.status == 'success'` — `always()` is REQUIRED so it fires even when the research job is `cancelled` by the timeout. `check_results` must treat search_cache.json OR results.json OR PDFs as progress.

2. **Download resume across chunks** — `search_cache.SearchCache` tracks `_downloaded_keys` SEPARATELY from `_seen_keys` (found keys). The download phase builds its queue from `new_papers + cache.pending_downloads(ckpt_existing)`. Without separate tracking, chunk 2 would skip ALL papers found in chunk 1 (they're in seen_keys) even if they were never downloaded. Do NOT collapse these two sets back into one.

3. **DOAB API returns bare lists** — `search_doab()` must handle `data` being a `list`, a `dict` with a `result` key, or `None`. `link` and `contributor` items may be strings, not dicts — guard with `isinstance(l, dict)`.

4. **Downloads hang** — Wave C of `download_with_full_chain` (DrissionPage "Walter Ghost", Anna's Archive, LibGen scraping) has no per-layer timeout. The download batch must use `wait(timeout=120)` (not `as_completed` which blocks forever) so a hung batch is abandoned and stragglers cancelled. `socket.setdefaulttimeout(60)` at `main()` start is a global backstop. A 6-PDFs-in-3h run means workers are hanging — investigate ghost/scraping layers. NOTE: the search phase has the SAME hang class via `search_all`'s `ThreadPoolExecutor`. The old `with ThreadPoolExecutor(...) as ex:` block's `__exit__` ALWAYS calls `shutdown(wait=True)`, so even after the deadline path did `ex.shutdown(wait=False, cancel_futures=True)`, exiting the `with` block re-blocked for 20-30 min on ~200 hung browser/scrape threads. That re-block outlasted the 3h GHA job cap, so `results.json` was NEVER written — every chained run lost ~6500 found papers and the next chunk started fresh (infinite loop). FIX: `search_all` now manages the executor manually (`ex = ThreadPoolExecutor(...)` + `try/finally: ex.shutdown(wait=False, cancel_futures=True)`) so BOTH the normal and deadline paths escape immediately and the post-search `results.json` checkpoint is reached. Do NOT reintroduce a `with` block around this executor.

5. **Chunk counter stuck at 1 (cross-run artifact download)** — `actions/download-artifact@v4` can ONLY download artifacts from the CURRENT run unless `run-id` is provided. Without `run-id`, every chained run starts fresh — `chunk_state.json` from the previous run is never restored → the chunk counter resets to 1 every time. FIX: a "Find previous run" step queries the GitHub API for the most recent completed run ID, then passes it as `run-id` to `download-artifact@v4`. The download+restore steps MUST run BEFORE the "Calculate chunk plan" step so `chunk_state.json` is available to increment. Also, `upload-artifact@v4` needs `overwrite: true` (otherwise it fails when an artifact with the same name from a previous run exists). CRITICAL COROLLARY: the "Find previous run" step must accept `conclusion == 'cancelled'` runs, NOT just `'success'`. Chained research runs are almost always `cancelled` (the 3h job cap kills the long search/download step). Filtering for `'success'` only → finds nothing → `prev_run_id` empty → download skipped → always "starting fresh" → chunk counter resets → infinite loop of re-searching the same ~6500 papers and losing them. The step now accepts `('success', 'cancelled')` AND verifies the run actually has the matching `research-data-<folder>` artifact (non-zero bytes) before resuming, since cancelled runs still upload artifacts via `if: always()`.

6. **Chain dispatches on stale branch** — the auto-trigger must dispatch on `main` (default branch), not whatever branch the initial run was started from. Otherwise chained runs execute stale code. FIX: `TRIGGER_BRANCH: main` env var is passed and used as the `ref` in the dispatch payload.

7. **Bare-list `.get()` crashes across ALL search platforms** — many APIs (DOAB, EuropePMC, Dataverse, etc.) return a bare JSON list instead of a dict at the top level. The old pattern `(data or {}).get("key", [])` crashes with `AttributeError: 'list' object has no attribute 'get'`. FIX: the `_safe_get(data, *keys, default=...)` helper in `research_hunter_v2-4.py` safely traverses nested dicts, returning `default` when `data` is a list/None. ALL 40+ search functions now use `_safe_get` instead of `(data or {}).get(...)`.

