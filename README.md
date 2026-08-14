# Research Hunters

> Transport-agnostic academic research engine: verifies references with high
> precision using 81 academic platforms + ollama scoring, with optional Google
> Drive/Sheets organization and optional Telegram push notifications.

The core hunt engine and reference-verification pipeline run with **zero
secrets**. Google Drive/Sheets and Telegram push are optional transports layered
on top when configured.

## Status

- **v0.1 (MVP, current)**: 93-platform search + chapter verify + verify_refs
  pipeline + Excel/DOCX reports + ollama scoring + optional Drive/Sheets.
- **v0.2 (next)**: Chapter writer (24-48h pipeline) + Node.js professional
  reports + dynamic platform expansion + multi-language.

## Architecture (5 layers)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Entry points (transport-agnostic)                       │
│    - verify_refs CLI (python -m verify_refs.cli ...)        │
│    - hunt_pipeline.run_hunt({...})                          │
│    - gha_run_hunt.py (GitHub Actions)                       │
└─────────────────────────────────────────────────────────────┘
                         ↓ research_hunter_v4.py
┌─────────────────────────────────────────────────────────────┐
│ 2. Orchestrator  (research_hunter_v4.py)                    │
│    - Re-exports full v2-4 surface (93 platforms)             │
│    - 11 glue functions + verify pipelines                   │
│    - Lazy Google integration (degrades if unconfigured)     │
└─────────────────────────────────────────────────────────────┘
                         ↓ imports from research_hunter_v2_4
┌─────────────────────────────────────────────────────────────┐
│ 3. v2-4 SUPER LOADED GOD MODE  (research_hunter_v2-4.py)    │
│    - 81 search platforms (PLATFORM_FNS dict)                │
│    - 14-layer PDF download chain (DOI→Sci-Hub fallback)     │
│    - APA citation builder, XLSX/MD/DOCX reporters           │
│    - Walter Ghost, RedListManager, CheckpointManager        │
└─────────────────────────────────────────────────────────────┘
                         ↓ ollama (local) + python libs
┌─────────────────────────────────────────────────────────────┐
│ 4. Brain                                                    │
│    - ollama qwen2.5vl:3b (precision scoring)                │
│    - pdfplumber + PyMuPDF (PDF parsing)                     │
│    - tesseract 5.3.0 (OCR)                                  │
│    - playwright + Chromium (JS-rendered sites)              │
└─────────────────────────────────────────────────────────────┘
                         ↓ optional (google-api-python-client)
┌─────────────────────────────────────────────────────────────┐
│ 5. Optional transports                                      │
│    - Google Drive: per-chapter folder + reference folders   │
│    - Google Sheets: 25+ columns of verified reference data  │
│    - Telegram: progress + result push (gha_run_hunt.py)     │
└─────────────────────────────────────────────────────────────┘
```

## Files

| File | Purpose |
|------|---------|
| `research_hunter_v4.py` | Main wrapper: re-exports v2-4 surface + 11 glue functions + verify pipelines |
| `research_hunter_v2-4.py` | 93-platform v6 SUPER LOADED GOD MODE (loaded via `v2_4` shim) |
| `hunt_pipeline.py` | Non-interactive hunt runner (`run_hunt(params, progress_callback)`) |
| `hunt_intake.py` | 14-step intake state machine (only `title` required; rest skippable) |
| `gha_run_hunt.py` | GitHub Actions hunt runner (Telegram push optional, env-gated) |
| `wizard.py` | 11-research-type input wizard (pure state machine) |
| `precision_engine.py` | Ollama scoring + cross-source validation |
| `google_integration.py` | Drive folder creation + Sheet generation (optional, lazy) |
| `pdf_parser.py` | PDF/DOCX/ODT/TXT reference extraction |
| `metadata_extractor.py` | Rich page 1-2 metadata (25+ fields) |
| `platform_registry.py` | Search platform registry + tier prioritization |
| `state_manager.py` | Per-chat JSON state persistence (honors `STATE_DIR` env) |
| `scoring_prompts.py` | Ollama prompt templates |
| `chapter_writer.py` | v0.2 placeholder (8-stage pipeline, TBD) |
| `error_handler.py` | Exponential backoff retry |
| `logger.py` | Timestamped console + rotating file logging |
| `report_pdf.py` | DOCX→PDF report generation |
| `future_studies.py` | AI-powered research gap suggestions (v6.5) |
| `verify_refs/` | Reference-list-driven verification (Excel + DOCX reports) |
| `run.py` | System status & health entrypoint |

## How it works

### Verify a reference list (`verify_refs`)

```bash
python -m verify_refs.cli --input references.txt --output-folder my_report
```

1. Parse the input (folder / PDF / DOCX / TXT / pasted list) into a list of refs.
2. For each ref: search 93 platforms → ollama scores the match (0-1) → classify.
3. Classification: VERIFIED (≥0.85), LIKELY (0.60-0.85), UNVERIFIED, FAKE.
4. Generate color-coded Excel + professionally-styled DOCX reports.

### Run a hunt (`hunt_pipeline`)

```python
from hunt_pipeline import run_hunt
result = run_hunt({
    "title": "deep learning for education",
    "max_papers": 50,
    "platforms": "tier1",
    # ... see hunt_intake.HUNT_STEPS for all options
}, progress_callback=print)
```

1. 93 platforms queried in parallel (CrossRef, OpenAlex, PubMed, arXiv, ERIC, DOAJ, HAL, BASE, ...).
2. Results deduplicated by title.
3. ollama scores each (0-1) with a strict prompt.
4. Only papers with score >= 0.85 AND appearing in 2+ sources are kept.
5. Top match's PDF downloaded via v2-4's 14-layer chain.
6. Outputs: XLSX + Markdown + results.json (+ optional PDFs).

## Local testing

```bash
# 1. Install deps
pip install -r requirements.txt

# 2. Fast offline checks (mirrors ci.yml)
python -W error::SyntaxWarning -m compileall -q .
python -c "import research_hunter_v4, wizard, google_integration, hunt_intake, hunt_pipeline, verify_refs.orchestrator" && echo OK
python tests/test_verify_refs.py --no-e2e
python tests/test_hunt_intake.py
python tests/test_hunt_intake_e2e.py
python tests/test_report_pdf.py
python tests/test_future_studies.py
python tests/test_health.py
python generate_ultimate_excel_v10.py
python run.py   # system status

# 3. Verify a reference list
python -m verify_refs.cli --input tests/sample_refs.txt --output-folder my_report
```

## CI/CD

- `ci.yml` — fast offline checks (compile, full import smoke, unit tests, health)
  on every PR + push. ~30s. No ollama, no network.
- `test.yml` — full suite incl. network/ollama end-to-end smoke tests
  (manual `workflow_dispatch`). Uploads reports as artifacts.
- `diagnostic.yml` — full system check: secrets, ollama, modules, google status,
  platform count (manual `workflow_dispatch`).
- `hunt-run.yml` — runs a hunt via `gha_run_hunt.py` (manual `workflow_dispatch`;
  Telegram push optional).
- `backup.yml` — weekly state + logs backup.
- `write-chapter.yml` — v0.2 multi-day chapter writer.
- `research.yml` — large workflow_dispatch research runner.

## Secrets (all optional)

The core pipeline needs **no secrets**. These enable optional transports:

| Secret | Purpose |
|--------|---------|
| `GOOGLE_OAUTH_REFRESH` | Google Drive/Sheets upload |
| `GOOGLE_OAUTH_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth client secret |
| `TELEGRAM_BOT_TOKEN` | Telegram push from `gha_run_hunt.py` (optional) |
| `GITHUB_TOKEN` | Auto-provided by GHA (for state dispatch) |

Set them in GitHub repo → Settings → Secrets and variables → Actions.

## Cost

- $0/month on free tier (GHA 2K min, Drive 15GB, all API sources free).
- ollama runs locally inside the runner (no API cost).
- Telegram is free (and now optional).

## License

MIT — see `LICENSE`.
