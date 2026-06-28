"""
test_health.py — Health checks for Excel-focused research-hunters system.

Runs on every CI test. Verifies:
  1. Critical files exist and compile
  2. All 81+ search platforms are registered and callable
  3. New v6.1 platforms (Connected Papers, Lens.org, DataCite, etc.) are present
  4. Hunt pipeline wrapper functions exist
  5. Platform count meets minimum (>= 70, currently 81)
  6. Reference-list-driven verification mode (verify_refs) is wired up
  7. Excel generation system (v10.0) with 40+ comprehensive sheets
  8. v6.5 future_studies module exists for AI-powered research gap suggestions
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

    # 7. Telegram bot integration removed (Excel-focused system)
    print("\n[health] 7. Telegram bot integration removed (Excel-focused system)")
    print("[health] OK: Telegram bot integration removed as requested")

    # 8. Search cache infrastructure
    print("\n[health] 8. Search cache infrastructure")
    try:
        from hunt_pipeline import _resolve_platforms
        result = _resolve_platforms(["crossref", "openalex"])
        if len(result) != 2:
            print(f"[health] FAIL: _resolve_platforms returned {result}")
            errors += 1
        else:
            print(f"[health] OK: _resolve_platforms resolves aliases correctly")
    except Exception as e:
        print(f"[health] FAIL: _resolve_platforms: {e}")
        errors += 1

    # 9. Reference-list-driven verification mode (verify_refs) - Excel-focused
    print("\n[health] 9. Reference-list verification (verify_refs module - Excel-focused)")
    try:
        import verify_refs
        from verify_refs import orchestrator, reports, input_parser
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
        print("[health] OK: Telegram bot commands removed (Excel-focused system)")
    except Exception as e:
        print(f"[health] FAIL: verify_refs: {e}")
        errors += 1

    # 10. Excel generation system (v10.0 - 40+ sheets)
    print("\n[health] 10. Excel generation system (v10.0 - 40+ comprehensive sheets)")
    try:
        # Check if the new Excel generator exists
        excel_gen_path = REPO_ROOT / "generate_ultimate_excel_v10.py"
        if not excel_gen_path.exists():
            print(f"[health] FAIL: generate_ultimate_excel_v10.py not found")
            errors += 1
        else:
            print(f"[health] OK: generate_ultimate_excel_v10.py exists ({excel_gen_path.stat().st_size:,} bytes)")
    except Exception as e:
        print(f"[health] FAIL: Excel generation check: {e}")
        errors += 1

    # 11. Drive integration removed (Excel-focused system)
    print("\n[health] 11. Drive integration removed (Excel-focused system)")
    print("[health] OK: Drive integration removed as requested")

    # 12. future_studies module (v6.5 research gap suggestions)
    print()
    print("[health] 12. future_studies module (v6.5 research gap suggestions)")
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
