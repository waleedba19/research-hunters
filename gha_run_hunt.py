"""Called by hunt-run.yml on GitHub Actions. Runs hunt pipeline, uploads results.

The Telegram notification and Google Drive upload layers were removed from this
repo; this script now runs the core hunt_pipeline and prints a summary that GHA
captures as step output. Results are uploaded as artifacts by the workflow.
"""
import json, os, sys, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hunt_pipeline import run_hunt, zip_results

params_path = os.environ.get("HUNT_PARAMS_PATH", "/tmp/hunt_params.json")
with open(params_path) as f:
    params = json.load(f)


def progress_cb(stage, message, progress):
    pct = int(progress * 100)
    label = stage.replace("_", " ").title()
    print(f"[{label}] {pct}% — {message[:200]}")


title = params.get("title", "")[:80]
print(f"🚀 Hunt started: {title}")

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
    sys.exit(1)

if not result.get("success", True):
    err = result.get("error", "Unknown error")
    print(f"⚠️ Hunt failed: {err}", file=sys.stderr)
    sys.exit(0)

total = result.get("total_papers", 0)
downloaded = result.get("downloaded", 0)
red_count = result.get("red_list_count", 0)
output_folder = result.get("output_folder", "")

print(
    f"✅ Hunt Complete!\n"
    f"  📚 {title}\n"
    f"  📄 Papers found: {total}\n"
    f"  📥 PDFs downloaded: {downloaded}\n"
    f"  ❌ Red-listed: {red_count}\n"
    f"  📁 Output: {output_folder}"
)

zip_path = zip_results(output_folder) if output_folder else None
if zip_path and os.path.exists(zip_path):
    print(f"📦 ZIP: {zip_path} ({os.path.getsize(zip_path)} bytes)")

print("Hunt completed successfully")
