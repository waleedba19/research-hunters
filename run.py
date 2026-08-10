#!/usr/bin/env python
"""
run.py — Convenience entrypoint.

Runs a local research hunt via hunt_pipeline.run_hunt. The Telegram bot layer
was removed from this repo; the core search engine works standalone.

Usage:
  python run.py "Your research topic"
  python run.py "Your research topic" --max-papers 50
"""
import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Run a local research hunt.")
    parser.add_argument("title", nargs="?", help="Research topic / title")
    parser.add_argument("--max-papers", type=int, default=30, help="Max papers to fetch")
    parser.add_argument("--field", default="general", help="Academic field")
    parser.add_argument("--year-from", type=int, default=2018)
    parser.add_argument("--year-to", type=int, default=2025)
    parser.add_argument("--no-download", action="store_true", help="Skip PDF downloads")
    args = parser.parse_args()

    print("=" * 60)
    print("Research Hunter — Local Hunt")
    print("=" * 60)

    if not args.title:
        print("\nUsage: python run.py \"<research topic>\" [--max-papers N]")
        print("Example: python run.py \"impact of AI on education\" --max-papers 20")
        return 1

    # Check v2-4 source
    v24_path = os.path.join(os.path.dirname(__file__), "research_hunter_v2_4.py")
    if not os.path.exists(v24_path):
        print(f"\n⚠️  research_hunter_v2_4.py not found at {v24_path}")
        print("Drop your v2-4 source there (see V2_4_README.md).")
        return 1

    try:
        from hunt_pipeline import run_hunt
    except Exception as e:
        print(f"\n❌ Failed to import hunt_pipeline: {e}")
        return 2

    params = {
        "title": args.title,
        "field": args.field,
        "study_types": [],
        "year_from": args.year_from,
        "year_to": args.year_to,
        "research_questions": [],
        "platforms": ["all"],
        "search_mode": "normal",
        "use_scihub": False,
        "single_folder": True,
        "study_keywords": [],
        "lang_label": "English",
        "search_languages": ["en"],
        "max_papers": args.max_papers,
        "download_pdfs": not args.no_download,
    }

    print(f"\n🚀 Starting hunt: {args.title!r}")
    print(f"   Max papers: {args.max_papers} | Years: {args.year_from}-{args.year_to}")
    try:
        result = run_hunt(params)
    except KeyboardInterrupt:
        print("\n👋 Hunt stopped.")
        return 0
    except Exception as e:
        print(f"\n❌ Hunt failed: {e}")
        return 2

    summary = {k: v for k, v in result.items() if k != "papers"}
    print(f"\n✅ Hunt complete:\n{json.dumps(summary, indent=2, default=str)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
