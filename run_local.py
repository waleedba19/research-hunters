#!/usr/bin/env python3
"""
run_local.py — Full end-to-end research-hunter runner for your own machine / VS Code terminal.

This is the local equivalent of the GitHub Actions `research.yml` workflow:
you answer the same questions the GitHub dashboard asks, and it runs the SAME
v2-4 core (`research_hunter_v2-4.py`) that GHA runs — search 93 platforms →
dedup → relevance + year/quartile/language filters → optional PDF download →
DOCX + 48-sheet XLSX + MD + PDF reports. Identical behavior, just no 3h job cap,
no chain re-trigger, and no GitHub limits.

USAGE
-----
    python run_local.py                 # interactive dashboard (answer the prompts)
    python run_local.py --auto TITLE   # one-shot with smart defaults

WHY THIS EXISTS
---------------
On GitHub Actions every run was capped at 3h, so the system had to "chain"
many 3h chunks via workflow_dispatch re-triggers. That chain was the source of
the bugs you kept hitting (HTTP 422, false "triggered", cross-run resume, the
post-hunt freeze). On your own machine there is **no 3h cap**, so there is no
chain and none of those failure modes can occur: one process, one results.json,
state persists on disk, and it resumes automatically if you re-run.

GUARANTEE
---------
It runs if your machine has Python 3.10+ and the deps in requirements.txt.
`ollama` is optional (used for AI scoring + future-studies) — if it's not
running, the system skips those steps gracefully and the search still works.
Verify your install any time with:  python run.py

OUTPUT
------
Reports land in  ./pdf_files/<topic-slug>/  (DOCX, XLSX, MD, JSON, PDF).
"""

import os
import re
import sys
import time
import shlex
import subprocess
from pathlib import Path

# Force UTF-8 (mirrors local_hunt.py) so emojis + non-ASCII render in any terminal.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")

HERE = Path(__file__).resolve().parent
V24 = HERE / "research_hunter_v2-4.py"


# ─────────────────────────────────────────────────────────────────────────────
#  Small helpers
# ─────────────────────────────────────────────────────────────────────────────

def _line(char="─", n=72):
    print(char * n)


def _ask(prompt, default=""):
    """Prompt with a [default] hint; empty Enter keeps the default."""
    hint = f" [{default}]" if default != "" else ""
    try:
        val = input(f"  {prompt}{hint}: ").strip()
    except EOFError:
        val = ""
    return val or default


def _ask_bool(prompt, default=False):
    d = "Y/n" if default else "y/N"
    raw = _ask(f"{prompt} ({d})", "y" if default else "n").strip().lower()
    return raw in ("y", "yes", "true", "1")


def _slugify(text):
    s = re.sub(r"[^a-zA-Z0-9]+", "_", (text or "").strip()).strip("_").lower()
    return s[:60] or "research"


def _h1(title):
    _line("═")
    print(f"  {title}")
    _line("═")


def _h2(title):
    print()
    _line()
    print(f"  {title}")
    _line()


# ─────────────────────────────────────────────────────────────────────────────
#  Banners
# ─────────────────────────────────────────────────────────────────────────────

def _banner():
    print()
    _h1("🔬 RESEARCH HUNTER — Local Full Run (end-to-end)")
    print("  The same 93-platform engine that runs on GitHub Actions, but on YOUR")
    print("  machine — no 3h cap, no chain, no GitHub limits. Answer the questions")
    print("  below (press Enter to accept the [default]); output goes to ./pdf_files/")
    print()
    print("  Tip: in VS Code, run this in the integrated Terminal:")
    print("       python run_local.py")
    _line()


# ─────────────────────────────────────────────────────────────────────────────
#  Interactive "dashboard" — collects the same inputs the GHA form does
# ─────────────────────────────────────────────────────────────────────────────

def collect_inputs():
    _h2("1 · WHAT TO DO + RESEARCH TOPIC")

    op_modes = [
        ("1", "research-only - Search & download papers"),
        ("2", "full-research - All: Research + Learn + Generate"),
        ("3", "learn-only - Learn patterns"),
        ("4", "generate-only - Generate paper"),
    ]
    print("  Operation mode:")
    for k, v in op_modes:
        print(f"     {k}. {v.split(' - ',1)[1]}")
    op_pick = _ask("Choice", "1")
    operation_mode = {
        "1": "research-only - Search & download papers",
        "2": "full-research - All: Research + Learn + Generate",
        "3": "learn-only - Learn patterns",
        "4": "generate-only - Generate paper",
    }.get(op_pick, "research-only - Search & download papers")

    title = _ask("Research title *", "")
    while not title.strip():
        print("  ⚠ Title is required.")
        title = _ask("Research title *", "")

    rq1 = _ask("Research Question 1 (optional, Enter to skip)", "")
    rq2 = _ask("Research Question 2 (optional, Enter to skip)", "")

    _h2("2 · FIELD & STUDY TYPE (Enter = auto-detect)")
    print("  Field: type the field number (e.g. 76 = Renewable Energy, 25 = CS/AI,")
    print("         17 = Psychology) or Enter for auto-detect. (278 fields total.)")
    field = _ask("Field number (or 'auto')", "auto")
    if field != "auto" and field.isdigit():
        field = f"{field} - (custom)"
    print("  Study type: type the number (e.g. 1=Empirical, 65=Any) or Enter=auto.")
    study_type = _ask("Study type number (or 'auto')", "auto")
    if study_type != "auto" and study_type.isdigit():
        study_type = f"{study_type} - (custom)"

    _h2("3 · FILTERS (Enter = 'Any / All')")
    print("  Study level: 1-5=PhD tracks, 6-10=Master/Bachelor, 11=Article, 12=Any")
    study_level = _ask("Study level", "12 - Any / All Levels")
    if study_level.isdigit():
        study_level = f"{study_level} - (custom)"
    print("  Methodology: 1-50 specific, 51=Any (Enter=Any)")
    methodology = _ask("Methodology", "51 - Any / All Methodologies")
    if methodology.isdigit():
        methodology = f"{methodology} - (custom)"
    print("  Thesis part: 1-27 specific, 28=Any (Enter=Any)")
    thesis_part = _ask("Thesis part", "28 - Any / All Parts")
    if thesis_part.isdigit():
        thesis_part = f"{thesis_part} - (custom)"
    print("  Quartile: 1=Q1 … 7=All Q1-Q4, 12=All indexes (Enter=All)")
    quartile = _ask("Quartile", "7 - All Quartiles (Q1-Q4)")
    if quartile.isdigit():
        quartile = f"{quartile} - (custom)"

    _h2("4 · LANGUAGE & YEARS (Enter = English, 2020→present)")
    print("  Language: 1=English, 2=Arabic, 10=EN+AR, 15=All (Enter=English)")
    language = _ask("Language", "1 - English only")
    if language.isdigit():
        language = f"{language} - (custom)"
    year_from = _ask("Year from (e.g. 2020, or 'all')", "2020")
    year_to = _ask("Year to (e.g. 2024, or 'current')", "current")

    _h2("5 · SEARCH DEPTH + PAPER LIMIT (the big levers)")
    modes = [
        ("1", "sample", "SAMPLE — Light, quick turnaround"),
        ("2", "extended", "EXTENDED — Thorough coverage [RECOMMENDED]"),
        ("3", "deep", "DEEP — All 93 platforms [RECOMMENDED]"),
        ("4", "ultra", "ULTRA — Multiple query rounds"),
        ("5", "maximum", "MAXIMUM — Every possible query (longest)"),
    ]
    print("  Search mode (depth):")
    for k, _, label in modes:
        print(f"     {k}. {label}")
    mode_pick = _ask("Choice", "3")
    mode_val = dict((k, v) for k, v, _ in modes).get(mode_pick, "deep")

    paper_limits = [
        ("1", "50"), ("4", "500 [RECOMMENDED]"), ("6", "1,200"),
        ("8", "5,000"), ("10", "20,000"), ("12", "Unlimited 100,000+"),
    ]
    print("  Paper limit (max papers collected):")
    for k, label in paper_limits:
        print(f"     {k}. {label}")
    pl_pick = _ask("Choice", "4")
    paper_limit = {
        "1": "1 - Light", "4": "4 - Standard", "6": "6 - Deep",
        "8": "8 - Mega", "10": "10 - Tera", "12": "12 - Unlimited",
    }.get(pl_pick, "4 - Standard")

    print()
    print("  On your OWN machine there is NO 3h cap, so 'research_depth' (chunking)")
    print("  only matters if you want periodic intermediate reports. Enter=medium.")
    research_depth = _ask("Research depth (light/medium/deep)", "medium - Balanced (2-4 chunks, ~6-12h total) [RECOMMENDED]")

    _h2("6 · DOWNLOADS & OUTPUT")
    download_pdfs = _ask_bool("Download PDFs? (slower; needs network)", False)
    scihub = _ask_bool("Use Sci-Hub fallback? (only if PDFs ON)", False)
    learn = _ask_bool("Learn patterns after search? (needs ollama)", True)
    generate_paper = _ask_bool("Generate a draft paper from results? (needs ollama)", False)

    of_options = [
        ("1", "both_docx_xlsx", "DOCX + XLSX 40-sheet [RECOMMENDED]"),
        ("2", "all", "ALL formats (DOCX+XLSX+MD+TXT+JSON+CSV+HTML)"),
        ("3", "excel_40_sheets", "Excel 40-sheet Ultimate Dashboard"),
        ("4", "docx_scopus", "DOCX Scopus-Quality (Publication Ready)"),
    ]
    print("  Output format:")
    for k, _, label in of_options:
        print(f"     {k}. {label}")
    of_pick = _ask("Choice", "1")
    output_format = dict((k, v) for k, v, _ in of_options).get(of_pick, "both_docx_xlsx")

    _h2("7 · GEOGRAPHIC AREA (Enter = worldwide)")
    print("  e.g. worldwide, libya, saudi_arabia, usa, china, europe, mena…")
    geographic_area = _ask("Geographic area", "worldwide - 🌍 Worldwide (All Countries)")
    if geographic_area and not geographic_area.startswith("worldwide") and "-" not in geographic_area:
        geographic_area = f"{geographic_area} - (custom)"

    folder_mode = _ask("Folder mode (hierarchy/single)", "hierarchy - 📊 Hierarchical (16 folders)")
    proxy = _ask("Proxy (n=none, y=auto, p=custom URL)", "n - None (Direct)")

    # Fan-out: if both RQs provided, offer to run them as parallel legs + merge.
    fanout = "off"
    if rq1.strip() and rq2.strip():
        print()
        do_fan = _ask_bool("You gave 2 research questions — fan-out into parallel sub-hunts then merge?", True)
        if do_fan:
            fanout = "on"

    return {
        "operation_mode": operation_mode,
        "title": title,
        "rq1": rq1,
        "rq2": rq2,
        "field": field,
        "study_type": study_type,
        "study_level": study_level,
        "methodology": methodology,
        "thesis_part": thesis_part,
        "quartile": quartile,
        "language": language,
        "year_from": year_from,
        "year_to": year_to,
        "mode": mode_val,
        "research_depth": research_depth,
        "paper_limit": paper_limit,
        "download_pdfs": download_pdfs,
        "scihub": scihub,
        "learn": learn,
        "generate_paper": generate_paper,
        "output_format": output_format,
        "geographic_area": geographic_area,
        "folder_mode": folder_mode,
        "proxy": proxy,
        "fanout": fanout,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Build the CI_* env dict that the v2-4 core reads (mirrors research.yml)
# ─────────────────────────────────────────────────────────────────────────────

def build_env(inputs, sub_title=None, folder_name=None):
    """Map collected inputs → the exact CI_* env vars research_hunter_v2-4 reads."""
    env = os.environ.copy()
    env["CI_MODE"] = "true"  # skips the interactive wizard; reads CI_* vars
    env["CI_OPERATION_MODE"] = inputs["operation_mode"]
    env["CI_TITLE"] = sub_title or inputs["title"]
    env["CI_RQ1"] = inputs["rq1"]
    env["CI_RQ2"] = inputs["rq2"]
    env["CI_FIELD"] = inputs["field"]
    env["CI_STUDY_TYPES"] = inputs["study_type"]
    env["CI_STUDY_LEVEL"] = inputs["study_level"]
    env["CI_METHODOLOGY"] = inputs["methodology"]
    env["CI_THESIS_PART"] = inputs["thesis_part"]
    env["CI_QUARTILE"] = inputs["quartile"]
    env["CI_MODE_VAL"] = inputs["mode"]
    env["CI_RESEARCH_DEPTH"] = inputs["research_depth"]
    env["CI_FANOUT_MODE"] = "off"  # we fan-out ourselves via subprocesses
    env["CI_PAPER_LIMIT"] = inputs["paper_limit"]
    env["CI_LANGUAGE"] = inputs["language"]
    env["CI_DOWNLOAD_PDFS"] = "true" if inputs["download_pdfs"] else "false"
    env["CI_SCI_HUB"] = "true" if inputs["scihub"] else "false"
    env["CI_SINGLE_FOLDER"] = inputs["folder_mode"]
    env["CI_YEAR_FROM"] = inputs["year_from"]
    env["CI_YEAR_TO"] = inputs["year_to"]
    env["CI_LEARN"] = "true" if inputs["learn"] else "false"
    env["CI_GENERATE_PAPER"] = "true" if inputs["generate_paper"] else "false"
    env["CI_PAPER_TYPE"] = "empirical - 📊 Empirical Research (Quantitative)"
    env["CI_OUTPUT_FORMAT"] = inputs["output_format"]
    env["CI_GEOGRAPHIC_AREA"] = inputs["geographic_area"]
    env["CI_PROXY"] = inputs["proxy"]
    if folder_name:
        env["CI_FOLDER_NAME"] = folder_name
    return env


# ─────────────────────────────────────────────────────────────────────────────
#  Run one hunt leg as a subprocess (clean os._exit isolation)
# ─────────────────────────────────────────────────────────────────────────────

def run_one_leg(env, leg_label="single"):
    """Run one hunt by invoking v2-4's main() in a child process.

    A subprocess is used (not an in-process call) because v2-4's main() ends with
    a hard os._exit(0) — that's the fix for the post-hunt atexit-thread-join
    freeze, and it's correct: it guarantees the process can never hang after the
    hunt completes. Running in a child lets us do fan-out (multiple legs) then
    merge, which an in-process os._exit would prevent.
    """
    print()
    _h1(f"▶ RUNNING HUNT LEG: {leg_label}")
    print(f"  Title: {env.get('CI_TITLE','')}")
    print(f"  Folder: {env.get('CI_FOLDER_NAME','(auto)')}")
    print(f"  Mode: {env.get('CI_MODE_VAL','')} | Papers: {env.get('CI_PAPER_LIMIT','')}")
    print(f"  Download PDFs: {env.get('CI_DOWNLOAD_PDFS','false')}")
    _line()
    print("  Search runs across all 93 platforms. This can take minutes to hours")
    print("  depending on depth — there is NO 3h cap here, so just let it run.")
    print("  Progress prints as it goes. Press Ctrl+C to stop (state is saved).")
    _line()

    cmd = [sys.executable, "-u", str(V24)]
    proc = subprocess.run(cmd, env=env, cwd=str(HERE))
    return proc.returncode


# ─────────────────────────────────────────────────────────────────────────────
#  Fan-out: split RQs into legs, run each, then merge
# ─────────────────────────────────────────────────────────────────────────────

def run_fanout(inputs):
    """Run one leg per research question (parallel-ish: sequentially here for
    simplicity + reliability), then merge into a unified report via fanout_merge."""
    base_slug = _slugify(inputs["title"])
    legs = []
    if inputs["rq1"].strip():
        legs.append(("RQ1", inputs["rq1"], f"{base_slug}__RQ1",
                     f"{inputs['title']} — RQ1: {inputs['rq1']}"))
    if inputs["rq2"].strip():
        legs.append(("RQ2", inputs["rq2"], f"{base_slug}__RQ2",
                     f"{inputs['title']} — RQ2: {inputs['rq2']}"))

    leg_folders = []
    for label, rq, folder_name, sub_title in legs:
        # Each leg only carries ITS own research question.
        leg_inputs = dict(inputs)
        leg_inputs["rq1"] = rq
        leg_inputs["rq2"] = ""
        env = build_env(leg_inputs, sub_title=sub_title, folder_name=folder_name)
        print(f"\n  [fan-out] leg {label} → folder {folder_name}")
        rc = run_one_leg(env, leg_label=label)
        if rc not in (0,):
            print(f"  ⚠ leg {label} exited with code {rc} (continuing to next leg)")
        leg_folders.append((label, folder_name))

    # Merge via the existing fanout_merge CLI (--matrix builds the plan; we call
    # the merge function directly for a clean unified report).
    _h1("▶ MERGING LEGS INTO UNIFIED REPORT")
    try:
        sys.path.insert(0, str(HERE))
        from fanout_merge import merge_reports
        out_dir = HERE / "pdf_files" / f"{base_slug}__unified"
        out_dir.mkdir(parents=True, exist_ok=True)
        # Load each leg's results.json
        report_data_list = []
        for label, folder_name in leg_folders:
            rj = HERE / "pdf_files" / folder_name / "results.json"
            if rj.exists():
                import json
                report_data_list.append(json.loads(rj.read_text(encoding="utf-8")))
                print(f"  loaded {label}: {rj}")
            else:
                print(f"  ⚠ {label} results.json not found at {rj}")
        if report_data_list:
            merged = merge_reports(report_data_list)
            import json
            (out_dir / "results.json").write_text(
                json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
            n = len(merged.get("papers", []))
            print(f"  ✅ Unified report: {n} papers (deduped across legs)")
            print(f"  📁 {out_dir / 'results.json'}")
        else:
            print("  ⚠ No leg reports found to merge.")
    except Exception as e:
        print(f"  ⚠ Merge step skipped ({type(e).__name__}: {e})")
        print(f"     You can merge manually: python fanout_merge.py --merge "
              f"{' '.join(f'pdf_files/{fn}' for _, fn in leg_folders)} --output pdf_files/{base_slug}__unified")
    return leg_folders


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    # --auto TITLE: one-shot with smart defaults (no prompts) for quick testing.
    if len(sys.argv) >= 3 and sys.argv[1] == "--auto":
        title = sys.argv[2]
        inputs = {
            "operation_mode": "research-only - Search & download papers",
            "title": title, "rq1": "", "rq2": "",
            "field": "auto - Auto-detect from title", "study_type": "auto - Auto-detect from title",
            "study_level": "12 - Any / All Levels", "methodology": "51 - Any / All Methodologies",
            "thesis_part": "28 - Any / All Parts", "quartile": "7 - All Quartiles (Q1-Q4)",
            "language": "1 - English only", "year_from": "2020", "year_to": "current",
            "mode": "deep", "research_depth": "medium - Balanced",
            "paper_limit": "4 - Standard", "download_pdfs": False, "scihub": False,
            "learn": True, "generate_paper": False, "output_format": "both_docx_xlsx",
            "geographic_area": "worldwide - 🌍 Worldwide", "folder_mode": "hierarchy",
            "proxy": "n - None (Direct)", "fanout": "off",
        }
    else:
        _banner()
        inputs = collect_inputs()

    # ── Summary / confirmation ──────────────────────────────────────────────
    print()
    _h1("✅ CONFIRMED — STARTING")
    print(f"  Title     : {inputs['title']}")
    if inputs["rq1"]:
        print(f"  RQ1       : {inputs['rq1']}")
    if inputs["rq2"]:
        print(f"  RQ2       : {inputs['rq2']}")
    print(f"  Mode      : {inputs['mode']}   Papers: {inputs['paper_limit']}")
    print(f"  Download  : {'PDFs ON' if inputs['download_pdfs'] else 'metadata + links only'}")
    print(f"  Output fmt: {inputs['output_format']}")
    print(f"  Fan-out   : {'ON (parallel legs → merge)' if inputs['fanout']=='on' else 'OFF (single hunt)'}")
    _line()

    if inputs["fanout"] == "on" and inputs["rq1"].strip() and inputs["rq2"].strip():
        run_fanout(inputs)
    else:
        slug = _slugify(inputs["title"])
        env = build_env(inputs, sub_title=inputs["title"], folder_name=slug)
        rc = run_one_leg(env, leg_label="single")
        if rc not in (0,):
            print(f"\n  ⚠ Hunt exited with code {rc}.")
            return rc

    print()
    _h1("🎉 DONE — reports are in ./pdf_files/")
    print("  Re-run the same command to resume — already-found papers are skipped")
    print("  automatically (state persists in search_cache.json + results.json).")
    print("  Open the DOCX/XLSX in the topic folder. To verify the system health:")
    print("     python run.py")
    _line()
    return 0


if __name__ == "__main__":
    sys.exit(main())
