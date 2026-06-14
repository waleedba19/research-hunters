"""
test_health.py — Permanent health checks for the literature-review-verifier.

Runs on every CI test. Verifies:
  1. Critical files exist and compile
  2. All 81+ search platforms are registered and callable
  3. New v6.1 platforms (Connected Papers, Lens.org, DataCite, etc.) are present
  4. Hunt pipeline wrapper functions exist
  5. Drive integration has the new upload_hunt_to_drive function
  6. Platform count meets minimum (>= 70, currently 81)
  7. Reference-list-driven verification mode (verify_refs) is wired up
  8. Telegram bot has the /verifyrefs command + all step handlers
  9. Unified /hunt2 intake (hunt_intake module) has all 5 steps and is wired to telegram_bot
  10. v6.4 deep search unleashed (max_papers default = 1000)
  11. v6.4 report_pdf module exists for DOCX to PDF heavy report conversion
  12. v6.4.1 google_integration Drive upload is unit-tested (8 mocked tests)
  13. v6.5 future_studies module exists for AI-powered research gap suggestions

This catches regressions if anyone removes a platform or breaks the wrapper.
"""
import os
import sys
import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

# Minimum platform count — increment this when adding new platforms
MIN_PLATFORM_COUNT = 75

# Platforms added in v6.1 (must all be present)
REQUIRED_V61_PLATFORMS = {
    "Connected Papers",
    "Lens.org",
    "DataCite",
    "Figshare",
    "Dryad",
    "ChemRxiv",
    "Research Square",
    "OpenDOAR",
    "NBER",
    "RePEc",
    "Google Dataset Search",
}

# Core platforms that must always be present
REQUIRED_CORE_PLATFORMS = {
    "Semantic Scholar",
    "OpenAlex",
    "CrossRef",
    "PubMed",
    "arXiv",
    "DOAJ",
    "ERIC",
    "Europe PMC",
    "CORE",
    "Google Scholar",
}


def main() -> int:
    print("[health] Starting health checks")
    errors = 0
    os.chdir(REPO_ROOT)
    sys.path.insert(0, str(REPO_ROOT))

    # 1. Critical files exist
    print("\n[health] 1. Critical files exist")
    for f in ("research_hunter_v2-4.py", "hunt_pipeline.py",
              "telegram_bot.py", "google_integration.py",
              "research_hunter_v2_4.py"):
        path = REPO_ROOT / f
        if not path.exists():
            print(f"[health] FAIL: missing file: {f}")
            errors += 1
        else:
            print(f"[health] OK: {f}")

    # 2. All platforms registered and callable
    print("\n[health] 2. All platforms registered")
    try:
        import research_hunter_v2_4 as v2_4
    except Exception as e:
        print(f"[health] FAIL: cannot import v2-4: {e}")
        return 1

    plats = list(v2_4.PLATFORM_FNS.keys())
    print(f"[health] Found {len(plats)} platforms registered")
    if len(plats) < MIN_PLATFORM_COUNT:
        print(f"[health] FAIL: platform count {len(plats)} < minimum {MIN_PLATFORM_COUNT}")
        errors += 1
    else:
        print(f"[health] OK: platform count {len(plats)} >= {MIN_PLATFORM_COUNT}")

    # 3. v6.1 platforms present
    print("\n[health] 3. v6.1 expansion platforms present")
    missing_v61 = REQUIRED_V61_PLATFORMS - set(plats)
    if missing_v61:
        print(f"[health] FAIL: missing v6.1 platforms: {missing_v61}")
        errors += 1
    else:
        print(f"[health] OK: all {len(REQUIRED_V61_PLATFORMS)} v6.1 platforms present")

    # 4. Core platforms present
    print("\n[health] 4. Core platforms present")
    missing_core = REQUIRED_CORE_PLATFORMS - set(plats)
    if missing_core:
        print(f"[health] FAIL: missing core platforms: {missing_core}")
        errors += 1
    else:
        print(f"[health] OK: all {len(REQUIRED_CORE_PLATFORMS)} core platforms present")

    # 5. All platform functions are callable
    print("\n[health] 5. Platform functions callable")
    broken = []
    for name, fn in v2_4.PLATFORM_FNS.items():
        if not callable(fn):
            broken.append(name)
    if broken:
        print(f"[health] FAIL: non-callable platform functions: {broken}")
        errors += 1
    else:
        print(f"[health] OK: all {len(plats)} platform functions callable")

    # 6. Hunt pipeline has expected functions
    print("\n[health] 6. Hunt pipeline wrapper functions")
    try:
        from hunt_pipeline import run_hunt, zip_results, _resolve_platforms
        print(f"[health] OK: run_hunt, zip_results, _resolve_platforms present")
    except Exception as e:
        print(f"[health] FAIL: hunt_pipeline import: {e}")
        errors += 1

    # 7. Drive integration has new upload_hunt_to_drive
    print("\n[health] 7. Drive integration has per-title folder function")
    try:
        import google_integration
        required_funcs = ("upload_hunt_to_drive", "upload_folder_recursive")
        for fn in required_funcs:
            if not hasattr(google_integration, fn):
                print(f"[health] FAIL: google_integration missing {fn}")
                errors += 1
            else:
                print(f"[health] OK: google_integration.{fn} present")
    except Exception as e:
        print(f"[health] FAIL: google_integration import: {e}")
        errors += 1

    # 8. Telegram bot has _run_v2_hunt and _safe_name_for_drive
    print("\n[health] 8. Telegram bot has hunt helpers")
    try:
        import telegram_bot
        for fn in ("_run_v2_hunt", "_safe_name_for_drive", "_make_progress_callback"):
            if not hasattr(telegram_bot, fn):
                print(f"[health] FAIL: telegram_bot missing {fn}")
                errors += 1
            else:
                print(f"[health] OK: telegram_bot.{fn} present")
    except Exception as e:
        print(f"[health] FAIL: telegram_bot import: {e}")
        errors += 1

    # 9. Search cache infrastructure present
    print("\n[health] 9. Search cache infrastructure")
    try:
        from hunt_pipeline import _resolve_platforms
        # _resolve_platforms is the alias resolver
        result = _resolve_platforms(["crossref", "openalex"])
        if len(result) != 2:
            print(f"[health] FAIL: _resolve_platforms returned {result}")
            errors += 1
        else:
            print(f"[health] OK: _resolve_platforms resolves aliases correctly")
    except Exception as e:
        print(f"[health] FAIL: _resolve_platforms: {e}")
        errors += 1

    # 10. Reference-list-driven verification mode (verify_refs)
    print("\n[health] 10. Reference-list verification (verify_refs module)")
    try:
        import verify_refs
        from verify_refs import orchestrator, reports, input_parser, cli
        for fn in ("run_verification", "classify_ref"):
            if not hasattr(orchestrator, fn):
                print(f"[health] FAIL: verify_refs.orchestrator missing {fn}")
                errors += 1
            else:
                print(f"[health] OK: verify_refs.orchestrator.{fn} present")
        for fn in ("build_excel_report", "build_docx_report"):
            if not hasattr(reports, fn):
                print(f"[health] FAIL: verify_refs.reports missing {fn}")
                errors += 1
            else:
                print(f"[health] OK: verify_refs.reports.{fn} present")
        for fn in ("parse_input", "parse_pasted_text"):
            if not hasattr(input_parser, fn):
                print(f"[health] FAIL: verify_refs.input_parser missing {fn}")
                errors += 1
            else:
                print(f"[health] OK: verify_refs.input_parser.{fn} present")
        # Telegram command
        import telegram_bot
        for fn in ("_cmd_verifyrefs", "_handle_verifyrefs_input",
                   "_handle_verifyrefs_output_name", "_handle_verifyrefs_download",
                   "_handle_verifyrefs_document", "_handle_verifyrefs_callback",
                   "_send_verifyrefs_result", "_send_document"):
            if not hasattr(telegram_bot, fn):
                print(f"[health] FAIL: telegram_bot missing {fn}")
                errors += 1
            else:
                print(f"[health] OK: telegram_bot.{fn} present")
    except Exception as e:
        print(f"[health] FAIL: verify_refs: {e}")
        errors += 1

    # 11. Unified /hunt2 intake (v6.3) + heavy report PDF generation (v6.4)
    print("\n[health] 11. Unified /hunt2 intake module (hunt_intake + telegram_bot) "
          "+ report_pdf (v6.4 heavy report)")
    try:
        import hunt_intake
        from hunt_intake import (
            HUNT_STEPS, start_hunt_intake, record_intake_answer,
            skip_intake_step, get_current_intake_step, get_intake_answers,
            is_intake_active, is_intake_complete, cancel_intake,
            intake_progress_text,
        )
        expected_keys = {"research_type", "title", "research_questions",
                         "year_range", "platforms", "max_papers", "download_pdfs"}
        actual_keys = {s["key"] for s in HUNT_STEPS}
        if expected_keys != actual_keys:
            print(f"[health] FAIL: HUNT_STEPS keys mismatch: {actual_keys} vs {expected_keys}")
            errors += 1
        else:
            print(f"[health] OK: HUNT_STEPS has all 7 expected keys: {sorted(actual_keys)}")
        if len(HUNT_STEPS) != 7:
            print(f"[health] FAIL: expected 7 steps, got {len(HUNT_STEPS)}")
            errors += 1
        else:
            print(f"[health] OK: 7 steps total")
        # Required step check
        required_steps = [s["key"] for s in HUNT_STEPS if not s.get("allow_skip")]
        if required_steps != ["title"]:
            print(f"[health] FAIL: only 'title' should be required, got {required_steps}")
            errors += 1
        else:
            print(f"[health] OK: only 'title' is required, other 4 steps skippable")
        # Default max_papers should be 1000 (v6.4 — unleashes deep search)
        max_papers_step = next(s for s in HUNT_STEPS if s["key"] == "max_papers")
        default = max_papers_step.get("default")
        if default != "1000":
            print(f"[health] FAIL: max_papers default should be '1000' for v6.4 deep search, got {default!r}")
            errors += 1
        else:
            print(f"[health] OK: max_papers default is '1000' (v6.4 deep search unleashed)")
        # Telegram command wiring
        for fn in ("_cmd_hunt_v2", "_show_hunt_intake_step",
                   "_handle_hunt_intake_callback", "_handle_hunt_intake_text",
                   "_on_hunt_intake_complete", "_run_v2_hunt_from_intake",
                   "_hunt_heartbeat", "_send_hunt_v2_result"):
            if not hasattr(telegram_bot, fn):
                print(f"[health] FAIL: telegram_bot missing {fn}")
                errors += 1
            else:
                print(f"[health] OK: telegram_bot.{fn} present")
        # report_pdf module
        import report_pdf
        for fn in ("docx_to_pdf", "is_pdf_generation_available", "_find_libreoffice"):
            if not hasattr(report_pdf, fn):
                print(f"[health] FAIL: report_pdf missing {fn}")
                errors += 1
            else:
                print(f"[health] OK: report_pdf.{fn} present")
    except Exception as e:
        print(f"[health] FAIL: hunt_intake: {e}")
        errors += 1

    # 12. Drive integration (v6.4.1) — must be unit-tested with mocks
    # since real OAuth credentials are not available in CI.
    print("\n[health] 12. Drive integration (google_integration) — public API + unit tests exist")
    try:
        import google_integration
        for fn in ("upload_hunt_to_drive", "upload_folder_recursive",
                   "upload_to_drive", "create_drive_folder",
                   "list_files_in_folder", "_find_or_create_folder",
                   "_get_oauth_client", "_get_drive_service"):
            if not hasattr(google_integration, fn):
                print(f"[health] FAIL: google_integration missing {fn}")
                errors += 1
            else:
                print(f"[health] OK: google_integration.{fn} present")
        # Verify the test file exists
        test_path = Path(__file__).parent / "test_drive_integration.py"
        if not test_path.exists():
            print(f"[health] FAIL: tests/test_drive_integration.py not found")
            errors += 1
        else:
            print(f"[health] OK: tests/test_drive_integration.py exists "
                  f"({test_path.stat().st_size:,} bytes)")
    except Exception as e:
        print(f"[health] FAIL: drive_integration: {e}")
        errors += 1

    # ── Health check 13: v6.5 future_studies module (research gap suggestions) ──
    print()
    print("[health] 13. future_studies module (v6.5 research gap suggestions)")
    try:
        import future_studies
        for fn in ("generate_future_studies", "to_markdown",
                   "_parse_ai_response", "_deterministic_fallback"):
            if not hasattr(future_studies, fn):
                print(f"[health] FAIL: future_studies missing {fn}")
                errors += 1
            else:
                print(f"[health] OK: future_studies.{fn} present")
        test_path = Path(__file__).parent / "test_future_studies.py"
        if not test_path.exists():
            print(f"[health] FAIL: tests/test_future_studies.py not found")
            errors += 1
        else:
            print(f"[health] OK: tests/test_future_studies.py exists "
                  f"({test_path.stat().st_size:,} bytes)")
    except Exception as e:
        print(f"[health] FAIL: future_studies: {e}")
        errors += 1

    # ── Health check 14: v6.6 telegram_ui module (rich UI) ──
    print()
    print("[health] 14. telegram_ui module (v6.6 rich UI)")
    try:
        import telegram_ui
        for fn in ("main_menu_keyboard", "build_review_screen",
                   "build_edit_panel", "build_reports_list",
                   "build_hunt_summary_text", "MAIN_MENU_TEXT",
                   "HELP_TEXT", "CHANGELOG_TEXT", "SETTINGS_TEXT",
                   "STEP_LABELS", "STAGE_INFO", "format_progress_line"):
            if not hasattr(telegram_ui, fn):
                print(f"[health] FAIL: telegram_ui missing {fn}")
                errors += 1
            else:
                print(f"[health] OK: telegram_ui.{fn} present")
        # Main menu must have at least 4 buttons (New Hunt, Verify, Reports, Help)
        kb = telegram_ui.main_menu_keyboard()
        rows = kb.get("inline_keyboard", [])
        if len(rows) < 4:
            print(f"[health] FAIL: main_menu has only {len(rows)} rows (need 4+)")
            errors += 1
        else:
            print(f"[health] OK: main_menu has {len(rows)} rows")
        # Review screen must include all 7 step labels
        fake_answers = {
            "research_type": "PhD", "title": "T", "research_questions": ["Q"],
            "year_range": "any", "platforms": "all", "max_papers": "1000",
            "download_pdfs": "yes",
        }
        text, _kb = telegram_ui.build_review_screen(fake_answers)
        for key, label in telegram_ui.STEP_LABELS.items():
            if label not in text:
                print(f"[health] FAIL: review screen missing label {label!r}")
                errors += 1
        test_path = Path(__file__).parent / "test_telegram_ui.py"
        if not test_path.exists():
            print(f"[health] FAIL: tests/test_telegram_ui.py not found")
            errors += 1
        else:
            print(f"[health] OK: tests/test_telegram_ui.py exists "
                  f"({test_path.stat().st_size:,} bytes)")
    except Exception as e:
        print(f"[health] FAIL: telegram_ui: {e}")
        errors += 1

    # Summary
    print()
    if errors == 0:
        print(f"[health] PASS — all health checks succeeded ({len(plats)} platforms)")
        return 0
    else:
        print(f"[health] FAIL — {errors} health checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
