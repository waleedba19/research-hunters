# 📥 v2-4 source: ALREADY DROPPED ✅

The v6 SUPER LOADED GOD MODE source has been pushed to the repo (commit `0466535`).
This README is kept for historical context only.

## Files present in the repo

- `research_hunter_v2-4.py` — the original v2-4 source (283 KB, dash in filename
  preserved from your local copy). This is the actual `v6 SUPER LOADED GOD MODE`
  with 70+ search platforms and the 14-layer PDF download chain.
- `research_hunter_v2_4.py` — a 1.4 KB shim. It loads `research_hunter_v2-4.py`
  via `importlib` and re-exports its full public surface, because Python module
  names cannot contain a dash. v4 imports from this shim:
  ```python
  from research_hunter_v2_4 import *  # underscore, via shim
  ```

## If you need to update v2-4

Drop a new `research_hunter_v2-4.py` into the repo root (overwriting the existing
one). The shim picks it up automatically. The v4 layer never modifies the
v2-4 source — it's treated as a black box.

## What v4 uses from v2-4

- All 70+ search functions (via `from research_hunter_v2_4 import *`)
- `download_with_full_chain(url, title, study_dir)` — for PDF download
- `parse_pdf_metadata(pdf_path)` — for rich metadata
- All citation/reporting helpers if v4 calls them

## What v4 adds on top

The 11 glue functions in `research_hunter_v4.py`:
- Wizard state machine (calls precision_engine)
- Ollama scoring (calls v2-4 results, filters by 0.85+ threshold)
- Cross-source validation
- Google Drive/Sheets upload
- Telegram bot (stdlib urllib)
- Per-chat state persistence

## v2-4 stays untouched

The v6 SUPER LOADED GOD MODE is treated as a black box. v4 never modifies it.
If v2-4 needs an update, the new version is dropped in as `research_hunter_v2-4.py`
(dash name) and the shim re-exports it. v4 picks it up automatically.
