# Architecture

## 5-layer stack (transport-agnostic)

The Telegram long-polling bot was removed. The core hunt engine and verify_refs
pipeline run with zero secrets; Google Drive/Sheets and Telegram push are
optional transports layered on top when configured.

```
Entry point (CLI / hunt_pipeline / gha_run_hunt.py)
   ↓
[Layer 1: research_hunter_v4.py]  (orchestrator)
   - Re-exports full v2-4 surface (93 platforms)
   - 11 glue functions + verify_one_reference / verify_chapter_upload
   - Lazy google_integration import (degrades if Drive unconfigured)
   ↓
[Layer 2: research_hunter_v2_4.py → research_hunter_v2-4.py]
   (v6 SUPER LOADED GOD MODE, loaded via importlib shim)
   - 81 search platforms (PLATFORM_FNS dict)
   - 14-layer PDF download chain
   - APA citation builder
   - XLSX/MD/DOCX reporters
   - Walter Ghost, RedListManager, CheckpointManager
   ↓
[Layer 3: brain]
   - ollama (qwen2.5vl:3b) — precision scoring
   - pdfplumber / PyMuPDF — PDF parsing
   - tesseract — OCR
   - playwright + Chromium — JS-rendered sites
   ↓
[Layer 4: state & logging]
   - state_manager.py — per-chat JSON state (atomic .tmp + os.replace)
   - logger.py — console + rotating file handlers
   - error_handler.py — @retry with exponential backoff
   ↓
[Layer 5: optional transports]
   - google_integration.py — Drive folder + Sheets (25+ columns) + Docs
   - Telegram push — gha_run_hunt.py (env-gated: TG_ENABLED)
```

## v4 = v2-4 surface + 11 glue functions

| # | Function | Module | Purpose |
|---|----------|--------|---------|
| 1 | `wizard_collect_inputs` | wizard.py + state_manager.py | Input collection (11 research types, every step skippable except type + chapter) |
| 2 | `parse_chapter_references` | pdf_parser.py | Extract in-text + reference list from PDF/DOCX/ODT |
| 3 | `precision_search` | precision_engine.py | 93 platforms → ollama score → 0.85+ |
| 4 | `score_paper_match` | precision_engine.py | ollama strict 0-1 score |
| 5 | `cross_source_validate` | precision_engine.py | 2+ source check to eliminate hallucinations |
| 6 | `create_drive_folder_w` | google_integration.py (lazy) | Per-chapter folder structure |
| 7 | `create_doi_sheet_w` | google_integration.py (lazy) | 25+ column sheet |
| 8 | `upload_to_drive_w` | google_integration.py (lazy) | Upload downloaded PDF |
| 9 | `telegram_send_rich_result_w` | research_hunter_v4.py | Build rich result payload (caller delivers it) |
| 10 | `telegram_edit_progress_w` | research_hunter_v4.py | Log a progress update (caller may render it) |
| 11 | `save_chapter_state_w` | state_manager.py | Persist per-chat state |

## Data flow: a precision search

```
Caller: precision_search("Smith 2020 deep learning")
   ↓
precision_engine.precision_search()
   ├── platform_registry.search_all_platforms()
   │     ├── crossref
   │     ├── openalex
   │     ├── semantic_scholar
   │     ├── pubmed
   │     ├── arxiv
   │     ├── ... (76 more — 81 total)
   ├── cross_source_validate() — dedup by title, count sources
   ├── score_paper_match() — ollama 0-1
   └── filter: score >= 0.85 AND cross_source_validated
   ↓
Results: list of verified papers (title, authors, DOI, score, sources, PDF path)
   ↓
Optional: google_integration.create_doi_sheet() — 25+ columns (if configured)
   ↓
Caller renders/delivers results (CLI, report, Telegram push, ...)
```

## verify_refs pipeline

```
Input (folder / PDF / DOCX / TXT / pasted list)
   ↓ verify_refs.input_parser → list of refs
   ↓
For each ref:
   ├── search 93 platforms
   ├── ollama scores the match (0-1)
   └── classify: VERIFIED (≥0.85) / LIKELY (0.60-0.85) / UNVERIFIED / FAKE
   ↓ verify_refs.reports
Excel (openpyxl, color-coded) + DOCX (python-docx, professional styling)
```

## State persistence

- File per chat: `data/state/chat_<chat_id>.json` (override with `STATE_DIR` env)
- Atomic write via `.tmp` + `os.replace`
- Survives process restarts and GHA job boundaries
- `_version` counter + `_updated_at` timestamp on every save
- `state_manager` is the single mutation point (hunt_intake, wizard, v4 all go through it)

## Precision contract

- Each paper must score >= 0.85 by ollama strict prompt
- Each paper must appear in 2+ platforms
- ollama's `uncertain: true` flag forces rejection
- Year drift >3 years → score < 0.6
- Different authors → score < 0.5
- No DOI + no URL + no abstract → reject

## Dependency philosophy

- The core must load with **zero credentials**. Optional dependencies
  (`google_integration`) are imported lazily inside the functions that need them,
  wrapped in try/except, so the core never breaks when a transport is unconfigured.
- All system deps (ollama, tesseract, playwright) are installed fresh each run via
  `requirements.txt` + workflow shell steps on `ubuntu-latest` runners.
- `requests` is a hard core dependency (v2-4 imports it at top level); it must be
  installed or the 93-platform surface fails to load.
