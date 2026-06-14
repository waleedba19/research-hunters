#!/usr/bin/env python
"""
run.py — Convenience entrypoint.

Tries to run the Telegram bot. If credentials are missing, prints setup help.
"""
import os
import sys


def main():
    print("=" * 60)
    print("Literature Review Verifier — Search Sleeping Bot")
    print("=" * 60)

    # Check required env vars
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    g_refresh = os.environ.get("GOOGLE_OAUTH_REFRESH", "")

    missing = []
    if not tg_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not g_refresh:
        missing.append("GOOGLE_OAUTH_REFRESH")

    if missing:
        print(f"\n⚠️  Missing env vars: {', '.join(missing)}")
        print("Set them in .env (see .env.example) or export them, then run again.")
        print("\nQuick start:")
        print("  cp .env.example .env")
        print("  # Edit .env with your tokens")
        print("  python run.py")
        return 1

    # Check v2-4 source
    v24_path = os.path.join(os.path.dirname(__file__), "research_hunter_v2_4.py")
    if not os.path.exists(v24_path):
        print(f"\n⚠️  research_hunter_v2_4.py not found at {v24_path}")
        print("Drop your v2-4 source there (see V2_4_README.md).")
        print("The bot will still work, but /find will return no results until then.")
        print()

    # Try to import and run
    try:
        import telegram_bot
        print("\n✅ Starting bot in long-polling mode (Ctrl+C to stop)...")
        telegram_bot.main()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped.")
    except Exception as e:
        print(f"\n❌ Bot failed to start: {e}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
