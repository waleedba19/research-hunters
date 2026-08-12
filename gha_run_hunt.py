"""Called by hunt-run.yml on GitHub Actions. Runs the hunt pipeline and reports results.

Reporting is transport-agnostic:
  - Always: progress + summary printed to stdout (visible in the GHA run log).
  - Optional: if TELEGRAM_BOT_TOKEN + CHAT_ID are both set, results are also
    pushed to that Telegram chat. If either is missing, Telegram is skipped
    silently (no crash) so the hunt still completes and the ZIP is uploaded.
"""
import json, os, sys, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hunt_pipeline import run_hunt, zip_results

with open("/tmp/hunt_params.json") as f:
    params = json.load(f)

chat_id = os.environ.get("CHAT_ID")
bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
TG_ENABLED = bool(chat_id and bot_token)


def notify(text, parse_mode="Markdown"):
    """Always print to stdout; additionally send to Telegram if configured."""
    print(text)
    if TG_ENABLED:
        import urllib.request, urllib.parse
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id, "text": text, "parse_mode": parse_mode,
        }).encode()
        try:
            urllib.request.urlopen(urllib.request.Request(url, data=data, method="POST"), timeout=10)
        except Exception as e:
            print(f"Telegram send failed: {e}", file=sys.stderr)


def progress_cb(stage, message, progress):
    pct = int(progress * 100)
    label = stage.replace("_", " ").title()
    line = f"\U0001f504 {label} [{pct}%] {message[:200]}"
    print(line)
    if TG_ENABLED:
        notify(f"\U0001f504 *{label}* [{pct}%]\n{message[:200]}")


title = params.get("title", "")[:80]
notify(
    f"\U0001f680 Hunt started on GitHub servers!\n\n"
    f"\U0001f4da {title}\n\n"
    f"\u23f3 Running on GitHub Actions \u2014 results will arrive here."
)

try:
    hunt_params = {
        "title": params.get("title", ""),
        "field": params.get("field", "general"),
        "study_types": [],
        "year_from": params.get("year_from", 2018),
        "year_to": params.get("year_to", 2025),
        "research_questions": params.get("research_questions", []),
        "platforms": params.get("platforms", ["all"]),
        "search_mode": "normal",
        "use_scihub": False,
        "single_folder": True,
        "study_keywords": [],
        "lang_label": "English",
        "search_languages": ["en"],
        "max_papers": params.get("max_papers", 30),
        "download_pdfs": params.get("download_pdfs", True),
    }
    result = run_hunt(hunt_params, progress_callback=progress_cb)
except Exception as e:
    tb = traceback.format_exc()
    print(f"Hunt crashed: {e}\n{tb}", file=sys.stderr)
    notify(f"\u26a0\ufe0f Hunt failed: {str(e)[:500]}")
    sys.exit(1)

if not result.get("success", True):
    err = result.get("error", "Unknown error")
    notify(f"\u26a0\ufe0f Hunt failed: {err[:500]}")
    sys.exit(0)

total = result.get("total_papers", 0)
downloaded = result.get("downloaded", 0)
red_count = result.get("red_list_count", 0)
output_folder = result.get("output_folder", "")

summary = (
    f"\u2705 Hunt Complete!\n\n"
    f"\U0001f4da {title}\n"
    f"\U0001f4c4 Papers found: {total}\n"
    f"\U0001f4e5 PDFs downloaded: {downloaded}\n"
    f"\u274c Red-listed: {red_count}\n"
    f"\U0001f4c1 Output: {output_folder}"
)

try:
    import google_integration as gdrive
except Exception as e:
    print(f"google_integration unavailable (Drive upload skipped): {e}", file=sys.stderr)
    gdrive = None

zip_path = zip_results(output_folder)
if zip_path and os.path.exists(zip_path) and gdrive is not None:
    try:
        upload_url = gdrive.upload_results_to_drive(zip_path, f"hunt_{title[:30]}")
        if upload_url and str(upload_url).startswith("https://"):
            summary += f"\n\U0001f4e6 Download ZIP: {upload_url}"
    except Exception as e:
        print(f"Drive upload failed: {e}", file=sys.stderr)
elif zip_path and os.path.exists(zip_path):
    summary += f"\n\U0001f4e6 ZIP ready locally: {zip_path}"

notify(summary)
print("Hunt completed successfully")
