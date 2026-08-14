#!/usr/bin/env python
"""
run.py — System status & health entrypoint.

Reports the state of the research-hunters core: module imports, platform count,
optional transports (Google Drive/Sheets, Telegram push), and points the user at
the available entry points (verify_refs CLI, hunt_pipeline, gha_run_hunt).

The Telegram long-polling bot was removed; hunts now run via the hunt_pipeline
directly or via `gha_run_hunt.py` on GitHub Actions (Telegram push optional).
"""
import os
import sys


def main():
    print("=" * 60)
    print("Literature Review Verifier — System Status")
    print("=" * 60)

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # 1. Core import check
    print("\n1. Core modules:")
    core = [
        ("research_hunter_v4", "Main v4 wrapper (multi-platform surface)"),
        ("hunt_pipeline", "Hunt pipeline"),
        ("precision_engine", "Precision engine (ollama scoring)"),
        ("verify_refs.orchestrator", "verify_refs orchestrator"),
        ("verify_refs.reports", "verify_refs reports (Excel + DOCX)"),
        ("pdf_parser", "PDF/DOCX/ODT reference parser"),
        ("wizard", "Input wizard (11 research types)"),
        ("hunt_intake", "Hunt intake (14-step state machine)"),
        ("future_studies", "Future studies (v6.5 gap suggestions)"),
        ("report_pdf", "Report PDF generator"),
    ]
    ok = 0
    for name, desc in core:
        try:
            __import__(name)
            print(f"   ✅ {desc}")
            ok += 1
        except Exception as e:
            print(f"   ❌ {desc}: {e}")
    print(f"   ({ok}/{len(core)} core modules OK)")

    # 2. Platform count
    print("\n2. Search platforms:")
    try:
        import research_hunter_v2_4 as v2_4
        plats = list(v2_4.PLATFORM_FNS.keys())
        print(f"   ✅ {len(plats)} platforms registered (min 75)")
    except Exception as e:
        print(f"   ❌ Could not load platform registry: {e}")

    # 3. Optional transports
    print("\n3. Optional transports:")
    g_refresh = os.environ.get("GOOGLE_OAUTH_REFRESH", "")
    print(f"   Google Drive/Sheets: {'✅ GOOGLE_OAUTH_REFRESH set' if g_refresh else '⚠️  not set (Drive upload skipped)'}")
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    print(f"   Telegram push: {'✅ TELEGRAM_BOT_TOKEN set' if tg_token else 'ℹ️  not set (optional; hunts still run)'}")

    # 4. Entry points
    print("\n4. Entry points:")
    print("   • Verify a reference list:  python -m verify_refs.cli --input <path> --output-folder <name>")
    print("   • Run a hunt locally:       from hunt_pipeline import run_hunt; run_hunt({...})")
    print("   • Run a hunt on GHA:        trigger hunt-run.yml (Telegram push optional)")
    print("   • Fast offline checks:      the ci.yml workflow (every PR/push)")
    print("   • Full ollama suite:        the test.yml workflow (workflow_dispatch)")

    print("\n" + "=" * 60)
    if ok == len(core):
        print("✅ Core system healthy.")
        return 0
    print("❌ Some core modules failed to import — see above.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
