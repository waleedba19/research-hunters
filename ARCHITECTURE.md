# Architecture

## 5-layer stack

```
User (Telegram)
   ↓
[Telegram Bot API] @Search_Sleeping_bot
   ↓ long-poll (90s) via getUpdates
[Layer 1: telegram_bot.py]   (python stdlib + urllib for Telegram API)
   - Wizard state machine
   - Intent detection (ollama)
   - Inline keyboards + progress edits
   ↓
[Layer 2: research_hunter_v4.py]  (orchestrator)
   - 11 new glue functions
   - Imports everything from research_hunter_v2_4
   ↓
[Layer 3: brain in runner-base:latest]  (DO-NOT-TOUCH IMAGE)
   - ollama 0.30.4 (qwen2.5vl:3b-16k)
   - pdfplumber 0.11+ / PyMuPDF 1.24+
   - tesseract 5.3.0 (16 langs)
   - playwright 1.50 + Chromium
   ↓
[Layer 4: research_hunter_v2_4]  (v6 SUPER LOADED GOD MODE)
   - 70+ search platforms (PLATFORM_FNS dict)
   - 14-layer PDF download chain
   - APA citation builder
   - XLSX/MD/DOCX reporters
   - Walter Ghost, RedListManager, CheckpointManager
   - Libyan/MENA platform URLs
   ↓
[Layer 5: Google Workspace]
   - Drive: per-chapter folder + reference subfolders
   - Sheets: 25+ columns of verified reference data
   - Docs: (v0.2) final chapter drafts
```

## v4 = v2-4 + 11 glue functions

| # | Function | Module | Purpose |
|---|----------|--------|---------|
| 1 | `wizard_collect_inputs` | wizard.py + state_manager.py | 7-step input collection via inline keyboards |
| 2 | `parse_chapter_references` | pdf_parser.py | Extract in-text + reference list from PDF/DOCX/ODT |
| 3 | `precision_search` | precision_engine.py | 70+ platforms → ollama score → 0.85+ |
| 4 | `score_paper_match` | precision_engine.py | ollama strict 0-1 score |
| 5 | `cross_source_validate` | precision_engine.py | 2+ source check to eliminate hallucinations |
| 6 | `create_drive_folder` | google_integration.py | Per-chapter folder structure |
| 7 | `create_doi_sheet` | google_integration.py | 25+ column sheet |
| 8 | `upload_to_drive` | google_integration.py | Upload downloaded PDF |
| 9 | `telegram_send_rich_result` | telegram_bot.py | Rich result card w/ image + buttons |
| 10 | `telegram_edit_progress` | telegram_bot.py | Edit one message live (no spam) |
| 11 | `save_chapter_state` | state_manager.py | Persist per-chat state |

## Data flow: a single /find

```
User: /find Smith 2020 deep learning
   ↓
telegram_bot._cmd_find() sends "🔍 Searching..."
   ↓
precision_engine.precision_search()
   ├── platform_registry.search_all_platforms()
   │     ├── crossref
   │     ├── openalex
   │     ├── semantic_scholar
   │     ├── pubmed
   │     ├── arxiv
   │     ├── ... (65+ more)
   ├── cross_source_validate() — dedup by title, count sources
   ├── score_paper_match() — ollama 0-1
   └── filter: score >= 0.85 AND cross_source_validated
   ↓
google_integration.create_doi_sheet() — 25 columns
   ↓
telegram_send_rich_result() — markdown + inline keyboard
   ↓
User sees: ✅ papers, scores, sources, Sheet link, Drive link
```

## State persistence

- File per chat: `data/state/chat_<chat_id>.json`
- Atomic write via `.tmp` + `os.replace`
- Survives bot restarts and GHA job boundaries
- `_version` counter + `_updated_at` timestamp on every save

## Precision contract (99% target)

- Each paper must score >= 0.85 by ollama strict prompt
- Each paper must appear in 2+ platforms
- ollama's `uncertain: true` flag forces rejection
- Year drift >3 years → score < 0.6
- Different authors → score < 0.5
- No DOI + no URL + no abstract → reject

## Why the image is do-not-touch

`ghcr.io/wo312092-creator/runner-base:latest` is the **brain of a human being**:
- 7.11 GB carefully built, tested (9/9 tests pass in run 26985703239)
- ollama + qwen2.5vl-3b-16k + tesseract + playwright all pinned versions
- Re-building it for this project would burn hours and risk breaking unrelated repos
- All project-specific dependencies go in `requirements.txt` (pip in workflow)
- All Node.js dependencies go in `package.json` (npm in workflow step)
- Image stays a clean shared foundation
