# Literature Review Verifier

> Telegram bot (@Search_Sleeping_bot) that verifies dissertation references with 99% precision using 70+ academic platforms + ollama scoring + Google Drive/Sheets organization.

## Status

- **v0.1 (MVP, current)**: Search + chapter verify + Drive/Sheets + Telegram bot + wizard + 99% precision.
- **v0.2 (next)**: Chapter writer (24-48h pipeline) + Node.js professional reports + dynamic platform expansion + multi-language.

## Architecture (5 layers)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Telegram UI (@Search_Sleeping_bot)                       │
│    User sends /start, /find, /upload, /verify, /sheet      │
└─────────────────────────────────────────────────────────────┘
                         ↓ python-telegram-bot (long-poll, 90s)
┌─────────────────────────────────────────────────────────────┐
│ 2. AI Chat Handler  (telegram_bot.py)                      │
│    - 7-step wizard with Skip on every step                  │
│    - Natural language intent detection (ollama)             │
│    - Inline keyboards + live progress edits                 │
└─────────────────────────────────────────────────────────────┘
                         ↓ research_hunter_v4.py (this repo)
┌─────────────────────────────────────────────────────────────┐
│ 3. Brain (runner-base:latest, do-not-touch)                 │
│    - ollama qwen2.5vl:3b-16k (precision scoring)            │
│    - pdfplumber + PyMuPDF (PDF parsing)                     │
│    - tesseract 5.3.0 (OCR)                                  │
│    - playwright + Chromium (JS-rendered sites)              │
└─────────────────────────────────────────────────────────────┘
                         ↓ imports from research_hunter_v2_4
┌─────────────────────────────────────────────────────────────┐
│ 4. v2-4 SUPER LOADED GOD MODE  (research_hunter_v4.py)      │
│    - 70+ search platforms (PLATFORM_FNS dict)               │
│    - 14-layer PDF download chain (DOI→Sci-Hub fallback)     │
│    - APA citation builder, XLSX/MD/DOCX reporters           │
│    - Walter Ghost, RedListManager, CheckpointManager        │
│    - Libyan/MENA platform support                           │
└─────────────────────────────────────────────────────────────┘
                         ↓ google-api-python-client
┌─────────────────────────────────────────────────────────────┐
│ 5. Google Workspace                                         │
│    - Drive: per-chapter folder + reference subfolders       │
│    - Sheets: 25+ columns of verified reference data         │
│    - Docs: (v0.2) final chapter drafts                      │
└─────────────────────────────────────────────────────────────┘
```

## Files

| File | Purpose |
|------|---------|
| `research_hunter_v4.py` | Main wrapper: imports v2-4 + 11 new glue functions |
| `telegram_bot.py` | Bot handlers, long-polling, inline keyboards |
| `wizard.py` | 7-step input wizard (research type → chapter → title → questions → aims → method → upload) |
| `precision_engine.py` | Ollama scoring + cross-source validation (99% precision) |
| `google_integration.py` | Drive folder creation + Sheet generation |
| `pdf_parser.py` | PDF/DOCX/ODT/TXT reference extraction |
| `metadata_extractor.py` | Rich page 1-2 metadata (25+ fields) |
| `platform_registry.py` | Search platform registry + tier prioritization |
| `state_manager.py` | Per-chat JSON state persistence |
| `scoring_prompts.py` | Ollama prompt templates |
| `chapter_writer.py` | v0.2 placeholder (8-stage pipeline, TBD) |
| `error_handler.py` | Exponential backoff retry |
| `logger.py` | Timestamped console + rotating file logging |

## How it works

1. User opens Telegram, sends `/start`.
2. Bot starts a 7-step wizard (research type, chapter name, title, questions, aims, method, references).
3. User can **Skip** any step except research type and chapter name.
4. On wizard completion: bot creates a Drive folder for the chapter + a Google Sheet.
5. User can `/find <title>` for a single paper search:
   - 70+ platforms queried in parallel (CrossRef, OpenAlex, PubMed, arXiv, ERIC, DOAJ, HAL, BASE, ...)
   - Results deduplicated by title
   - ollama scores each (0-1) with strict prompt
   - Only papers with score >= 0.85 AND appearing in 2+ sources kept
   - Top match's PDF downloaded via v2-4's 14-layer chain
6. User can `/upload` a chapter PDF/DOCX:
   - Parses all in-text citations + reference list
   - Verifies up to 35 references per chapter
   - Uploads verified PDFs to per-paper Drive folders
   - Updates the Sheet with one row per reference

## Hosting

- **GitHub Actions** cron workflow every 5 min (`bot-polling.yml`).
- **Container**: `ghcr.io/wo312092-creator/runner-base:latest` (do-not-touch).
- **Node.js** installed in workflow step (image is do-not-touch, no Node.js inside).

## Local testing

```bash
# 1. Set env
cp .env.example .env
# Edit .env with your TELEGRAM_BOT_TOKEN, GOOGLE_OAUTH_REFRESH, ...

# 2. Install deps
pip install -r requirements.txt

# 3. Run the bot (long-polling)
python telegram_bot.py
```

## CI/CD

- `bot-polling.yml` — runs the bot in 5-min cycles via GHA.
- `test.yml` — runs unit tests on every push.
- `backup.yml` — weekly state + logs backup.
- `write-chapter.yml` — v0.2 multi-day chapter writer.

## Secrets (set in GitHub repo → Settings → Secrets)

| Secret | Purpose |
|--------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `GOOGLE_OAUTH_REFRESH` | Google OAuth refresh token |
| `GOOGLE_OAUTH_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth client secret |
| `GITHUB_TOKEN` | Auto-provided by GHA (for state dispatch) |

## Cost

- $0/month on free tier (GHA 2K min, Telegram free, Drive 15GB, all API sources free).
- ollama runs locally inside the container (no API cost).

## License

MIT — see `LICENSE`.
