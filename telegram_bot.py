"""
telegram_bot.py — Telegram bot entry point.
Long-polling getUpdates handler. Wired to @Search_Sleeping_bot.

Commands:
  /start       - welcome + start wizard
  /hunt        - interactive research hunt with inline selection
  /find        - direct search by title
  /upload      - receive a chapter PDF/DOCX
  /verify      - verify a previously-uploaded chapter
  /sheet       - get the Google Sheet link
  /status      - current job queue + last results
  /cancel      - cancel current wizard
  /reset       - clear chat state
  /research    - start interactive research hunt (shows platforms, lets you select)
  /sleep       - set bot to "sleep mode" (passive monitoring)
  /wake        - wake bot from sleep mode

Run:  python telegram_bot.py

Enhanced v2 Features:
  - Interactive inline keyboards for selecting research type
  - Platform selection with visual feedback
  - Real-time progress updates during research
  - Results sent as rich formatted messages with buttons
  - Sleep mode for passive monitoring while you rest
"""

import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    import os
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")

import threading
import queue as Queue
import sys
import json
import re
import time
import os
from typing import Dict, Any, Optional, List
from logger import get_logger
from state_manager import load_chapter_state, save_chapter_state, clear_chapter_state
from wizard import (
    start_wizard, get_current_step, record_answer, skip_step,
    is_wizard_active, get_answers, cancel_wizard, WIZARD_STEPS, RESEARCH_TYPES,
)
from research_hunter_v4 import (
    verify_one_reference, verify_chapter_upload,
    telegram_send_rich_result_w, parse_chapter_references_w,
)
from hunt_pipeline import run_hunt, zip_results
import google_integration as gdrive
from precision_engine import precision_search, _call_ollama
from scoring_prompts import DETECT_INTENT_PROMPT
from pdf_parser import parse_chapter_references
import shutil
import tempfile
import urllib.request
import urllib.parse

import telegram_ui

log = get_logger("telegram_bot")

# ============================================================================
# Telegram client (pure stdlib, no extra deps needed)
# ============================================================================

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
TELEGRAM_FILE_API = "https://api.telegram.org/file/bot{token}/{path}"


def _get_token() -> str:
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if tok:
        log.info("Using TELEGRAM_BOT_TOKEN from environment")
        return tok
    
    # Fall back to memory.json (cross-platform paths)
    possible_paths = [
        os.environ.get("MEMORY_JSON_PATH", ""),
        "/tmp/memory.json",
        "./memory.json",
        os.path.expanduser("~/memory.json"),
        os.path.join(os.path.dirname(__file__), "memory.json"),
    ]
    
    for mem_path in possible_paths:
        if mem_path and os.path.exists(mem_path):
            try:
                with open(mem_path, "r", encoding="utf-8") as f:
                    mem = json.load(f)
                token = mem.get("secrets", {}).get("telegram_bots", {}).get("search_sleeping_bot", {}).get("token", "")
                if token:
                    log.info(f"Using token from {mem_path}")
                    return token
            except Exception as e:
                log.warning(f"Failed to read {mem_path}: {e}")
    
    # Check for token file in common locations
    token_paths = [
        "/secrets/telegram_token.txt",
        "/tmp/telegram_token.txt",
        "./telegram_token.txt",
    ]
    for token_path in token_paths:
        if os.path.exists(token_path):
            try:
                with open(token_path, "r") as f:
                    token = f.read().strip()
                if token:
                    log.info(f"Using token from {token_path}")
                    return token
            except Exception as e:
                log.warning(f"Failed to read {token_path}: {e}")
    
    log.error("TELEGRAM_BOT_TOKEN not found in environment or files!")
    log.error("Please set TELEGRAM_BOT_TOKEN environment variable or create secrets in GitHub Actions")
    return ""


def _tg_call(method: str, params: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Call a Telegram Bot API method. Returns the parsed JSON response."""
    token = _get_token()
    if not token:
        return {"ok": False, "error": "no token"}
    url = TELEGRAM_API.format(token=token, method=method)
    try:
        if files:
            import requests  # only needed for file uploads
            r = requests.post(url, data=params, files=files, timeout=60)
        else:
            data = urllib.parse.urlencode(params or {}).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode("utf-8")
            return json.loads(raw)
    except Exception as e:
        log.error(f"telegram {method} failed: {e}")
        return {"ok": False, "error": str(e)}


def _send_message(chat_id: int, text: str, parse_mode: str = "Markdown",
                  reply_markup: Optional[Dict[str, Any]] = None) -> Optional[int]:
    params: Dict[str, Any] = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        params["reply_markup"] = json.dumps(reply_markup)
    resp = _tg_call("sendMessage", params)
    if resp.get("ok"):
        return resp.get("result", {}).get("message_id")


def _dispatch_hunt_workflow(chat_id: int, params: Dict[str, Any]) -> bool:
    """Dispatch the hunt to GitHub Actions via workflow_dispatch API.
    Uses the default GITHUB_TOKEN from the current workflow run.
    Returns True if dispatched, False if token not available (fall back to local)."""
    token = os.environ.get("GITHUB_TOKEN", "")
    gh_repo = os.environ.get("GH_REPO", "wo312092-creator/literature-review-verifier")
    if not token:
        return False
    import urllib.request
    url = f"https://api.github.com/repos/{gh_repo}/actions/workflows/hunt-run.yml/dispatches"
    payload = {
        "ref": "main",
        "inputs": {
            "chat_id": str(chat_id),
            "params_json": json.dumps(params),
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "SearchSleepingBot/6.7")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            log.info(f"hunt dispatched via GITHUB_TOKEN for chat {chat_id}, status={r.status}")
            return True
    except Exception as e:
        log.warning(f"GHA dispatch failed for chat {chat_id}: {e}")
        return False


def _edit_message(chat_id: int, message_id: int, text: str, parse_mode: str = "Markdown",
                  reply_markup: Optional[Dict[str, Any]] = None) -> bool:
    params: Dict[str, Any] = {
        "chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": parse_mode,
    }
    if reply_markup:
        params["reply_markup"] = json.dumps(reply_markup)
    resp = _tg_call("editMessageText", params)
    return bool(resp.get("ok"))


def _answer_callback(callback_query_id: str, text: str = "") -> None:
    _tg_call("answerCallbackQuery", {"callback_query_id": callback_query_id, "text": text})


def _download_telegram_file(file_id: str) -> Optional[str]:
    """Download a Telegram file by file_id, save to a temp path, return the path."""
    info = _tg_call("getFile", {"file_id": file_id})
    if not info.get("ok"):
        return None
    file_path = info["result"].get("file_path")
    if not file_path:
        return None
    token = _get_token()
    url = TELEGRAM_FILE_API.format(token=token, path=file_path)
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            data = r.read()
        ext = os.path.splitext(file_path)[1] or ".bin"
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        tmp.write(data)
        tmp.close()
        return tmp.name
    except Exception as e:
        log.error(f"Download telegram file failed: {e}")
        return None


# ============================================================================
# Inline keyboards
# ============================================================================

def _keyboard_for_step(step: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build an InlineKeyboardMarkup for the current step."""
    buttons: List[List[Dict[str, str]]] = []
    if step.get("options"):
        for k, label in step["options"]:
            buttons.append([{"text": label, "callback_data": f"ans:{k}"}])
    # Add a Skip button if allowed
    if step.get("allow_skip"):
        buttons.append([{"text": "⏭ Skip", "callback_data": "skip"}])
    # Always offer Cancel
    buttons.append([{"text": "❌ Cancel", "callback_data": "cancel"}])
    if not buttons:
        return None
    return {"inline_keyboard": buttons}


def _keyboard_after_complete() -> Dict[str, Any]:
    return {"inline_keyboard": [
        [{"text": "🔍 Find more", "callback_data": "action:find"},
         {"text": "📎 Upload chapter", "callback_data": "action:upload"}],
        [{"text": "📊 Get Sheet", "callback_data": "action:sheet"},
         {"text": "🔄 New wizard", "callback_data": "action:new"}],
    ]}


# ============================================================================
# Sleep Mode & Passive Monitoring
# ============================================================================

# Global state for sleep mode
_sleep_mode: Dict[int, bool] = {}  # chat_id -> is_sleeping

def _cmd_sleep(chat_id: int) -> None:
    """Enable sleep mode - bot monitors but doesn't actively search."""
    _sleep_mode[chat_id] = True
    _send_message(
        chat_id,
        "😴 *Sleep Mode Enabled*\n\n"
        "I'll monitor incoming messages but won't run active searches.\n"
        "Use /wake to enable full functionality.\n\n"
        "You can still:\n"
        "• Send /status to check queue\n"
        "• Send /find <title> for quick search\n"
        "• Send /hunt to start a research hunt",
        parse_mode="Markdown",
    )


def _cmd_wake(chat_id: int) -> None:
    """Disable sleep mode - full functionality restored."""
    _sleep_mode[chat_id] = False
    _send_message(
        chat_id,
        "☀️ *Wake Mode Enabled*\n\n"
        "I'm fully awake and ready!\n"
        "You can:\n"
        "• /hunt - Start a full research hunt\n"
        "• /find <title> - Quick paper search\n"
        "• /start - Run the wizard\n"
        "• /status - Check queue status",
        parse_mode="Markdown",
    )


def _is_sleeping(chat_id: int) -> bool:
    return _sleep_mode.get(chat_id, False)


# ============================================================================
# Interactive Research Hunt (The Main Feature!)
# ============================================================================

def _cmd_hunt(chat_id: int, text: str = "") -> None:
    """
    Start a research hunt.
    - /hunt <topic> — fast path: runs full v2-4 pipeline immediately
    - /hunt — interactive path: selects research type + platforms, then runs
    """
    # Check sleep mode
    if _is_sleeping(chat_id):
        _send_message(
            chat_id,
            "😴 *I'm in sleep mode*\n\n"
            "Use /wake to enable full research hunting.",
            parse_mode="Markdown",
        )
        return
    
    # Parse any topic from command
    topic = text.replace("/hunt", "").replace("/research", "").strip()
    
    # Fast path: topic provided, run full v2-4 pipeline immediately
    if topic:
        msg = _send_message(
            chat_id,
            f"🔍 *Starting v2-4 Research Hunt*\n\n"
            f"Topic: *{topic[:80]}*\n"
            f"Platforms: all (70+)\n"
            f"Mode: normal\n\n"
            f"⏳ This will take several minutes. I'll send progress updates...",
            parse_mode="Markdown",
        )
        thread = threading.Thread(
            target=_run_v2_hunt,
            args=(chat_id, topic, ["all"], "general", msg),
        )
        thread.daemon = True
        thread.start()
        return
    
    # Interactive path: ask for research type first
    _send_message(
        chat_id,
        "🔍 *Research Hunt*\n\n"
        "What type of research do you want?\n\n"
        "ℹ️ *Tip:* Use `/hunt your topic` to skip straight to the full pipeline!",
        parse_mode="Markdown",
        reply_markup={
            "inline_keyboard": [
                [{"text": "📚 Literature Review", "callback_data": "hunt:lit_review"},
                {"text": "🎓 Dissertation Hunt", "callback_data": "hunt:dissertation"}],
                [{"text": "📰 News & Articles", "callback_data": "hunt:news"},
                {"text": "📄 Technical Papers", "callback_data": "hunt:technical"}],
                [{"text": "🌍 Geographic Focus", "callback_data": "hunt:geographic"},
                {"text": "🔬 Scientific Papers", "callback_data": "hunt:scientific"}],
            ]
        },
    )


# ============================================================================
# /hunt2 — Unified multi-step hunt intake (v6.3)
# ============================================================================

def _cmd_hunt_v2(chat_id: int, text: str = "") -> None:
    """Unified /hunt2 flow: ALWAYS uses the 5-step intake.

    /hunt2 <title>   - start with title pre-filled
    /hunt2           - start with no answers, ask title in step 2
    """
    from hunt_intake import start_hunt_intake, get_current_intake_step, HUNT_STEPS

    if _is_sleeping(chat_id):
        _send_message(chat_id, "😴 *I'm in sleep mode.* Use /wake first.",
                      parse_mode="Markdown")
        return

    # Pre-fill from /hunt2 <title>
    prefill = {}
    title = text.replace("/hunt2", "").strip()
    if title:
        prefill["title"] = title

    start_hunt_intake(chat_id, prefill=prefill)
    # Show the first step
    _show_hunt_intake_step(chat_id)


def _show_hunt_intake_step(chat_id: int) -> None:
    """Display the current hunt intake step to the user."""
    from hunt_intake import get_current_intake_step
    step = get_current_intake_step(chat_id)
    if not step:
        return
    text = step["prompt"]
    if step.get("options"):
        # Show inline keyboard for option-based steps (2 per row for compactness)
        keyboard = []
        row = []
        for i, (val, label) in enumerate(step["options"]):
            row.append({"text": label, "callback_data": f"hintake:{step['key']}:{val}"})
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        # Add a Skip button if allowed
        if step.get("allow_skip") and step.get("default") is not None:
            keyboard.append([{"text": f"⏭ Skip (use default: {step['default']})",
                              "callback_data": f"hintake:{step['key']}:__skip__"}])
        _send_message(chat_id, text, parse_mode="Markdown",
                      reply_markup={"inline_keyboard": keyboard})
    else:
        # Free-text step: also offer a Skip button
        if step.get("allow_skip") and step.get("default") is not None:
            kb = {"inline_keyboard": [[
                {"text": f"⏭ Skip (use default: {step['default']})",
                 "callback_data": f"hintake:{step['key']}:__skip__"}
            ]]}
            _send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)
        else:
            _send_message(chat_id, text, parse_mode="Markdown")


def _handle_hunt_intake_callback(chat_id: int, data: str) -> None:
    """Handle inline keyboard callbacks for the hunt intake."""
    from hunt_intake import (record_intake_answer, skip_intake_step,
                             is_intake_complete, get_intake_answers,
                             start_hunt_intake)
    # data format: hintake:<step_key>:<value>
    parts = data.split(":", 2)
    if len(parts) != 3 or parts[0] != "hintake":
        return
    step_key = parts[1]
    value = parts[2]
    if value == "__skip__":
        state = skip_intake_step(chat_id)
    else:
        state = record_intake_answer(chat_id, value)

    if is_intake_complete(chat_id):
        _on_hunt_intake_complete(chat_id)
    else:
        _show_hunt_intake_step(chat_id)


def _handle_hunt_intake_text(chat_id: int, text: str) -> bool:
    """Handle free-text answer during the hunt intake. Returns True if handled."""
    from hunt_intake import (is_intake_active, get_current_intake_step,
                             record_intake_answer, is_intake_complete)
    if not is_intake_active(chat_id):
        return False
    step = get_current_intake_step(chat_id)
    if not step:
        return False
    # If this step has options, the text is only valid for free-text steps
    if step.get("options"):
        return False
    text = text.strip()
    if text.lower() in ("skip", "/skip", "⏭"):
        from hunt_intake import skip_intake_step
        skip_intake_step(chat_id)
    else:
        record_intake_answer(chat_id, text)
    if is_intake_complete(chat_id):
        _on_hunt_intake_complete(chat_id)
    else:
        _show_hunt_intake_step(chat_id)
    return True


def _on_hunt_intake_complete(chat_id: int) -> None:
    """Called when the 7-step intake is done.

    v6.6: instead of auto-starting the hunt, show a *Review* screen with
    all 7 answers and ✅ Start / ✏️ Edit / ❌ Cancel buttons. The user
    confirms (hunt:start callback) before we kick off the heavy pipeline.
    """
    from hunt_intake import get_intake_answers
    answers = get_intake_answers(chat_id)
    text, kb = telegram_ui.build_review_screen(answers)
    _send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)
    log.info(f"Chat {chat_id} hunt intake complete — review screen shown")


def _safe_start_hunt_from_review(chat_id: int) -> None:
    """Thread-safe wrapper around _start_hunt_from_review. Catches ALL
    exceptions, logs them, and surfaces a user-facing error message so
    the bot never silently fails.
    """
    log.info(f"_safe_start_hunt_from_review: thread started for chat {chat_id}")
    try:
        _start_hunt_from_review(chat_id)
        log.info(f"_safe_start_hunt_from_review: thread completed for chat {chat_id}")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log.error(f"_safe_start_hunt_from_review: crashed for chat {chat_id}: {e}\n{tb}")
        try:
            _send_message(
                chat_id,
                f"⚠️ *Could not start the hunt.*\n\n"
                f"Error: `{e}`\n\n"
                f"Try /start → New Hunt again, or /cancel to reset.",
                parse_mode="Markdown",
            )
        except Exception as send_err:
            log.error(f"_safe_start_hunt_from_review: follow-up send also failed: {send_err}")


def _start_hunt_from_review(chat_id: int) -> None:
    """v6.7: Show the RQ package picker before kicking off the pipeline.

    Two sub-cases:
    - research_questions == "custom" (user wants to type their own):
        → ask them to type RQs, then run the hunt with those RQs
    - research_questions == "auto" (default): generate 3 packages,
        show them with package picker buttons. User picks one.

    When the user picks a package (hunt:rq:<id>), _on_rq_package_picked()
    is called, which actually runs the pipeline.

    For all other research_questions values (e.g. user typed RQs in step 5):
        → parse them, run the hunt immediately, no picker.
    """
    from hunt_intake import get_intake_answers
    log.info(f"_start_hunt_from_review: entry for chat {chat_id}")
    answers = get_intake_answers(chat_id)
    raw_rqs = answers.get("research_questions", "auto")

    # If user already typed their own RQs (non-empty, non-auto, non-custom),
    # parse them and skip the picker.
    parsed_rqs: List[str] = []
    if isinstance(raw_rqs, list):
        parsed_rqs = [str(q).strip() for q in raw_rqs if str(q).strip()]
    elif isinstance(raw_rqs, str):
        s = raw_rqs.strip()
        if s and s.lower() not in ("auto", "skip", "skipped", "default",
                                    "custom", ""):
            import re as _re
            for line in s.splitlines():
                line = line.strip()
                if not line:
                    continue
                line = _re.sub(r'^(RQ\s*\d+\s*[:\.\)]\s*|\d+[\.\)]\s*|-\s*)',
                               '', line, flags=_re.IGNORECASE).strip()
                if line and len(line) > 5:
                    parsed_rqs.append(line)

    if parsed_rqs:
        log.info(f"_start_hunt_from_review: user has {len(parsed_rqs)} RQs "
                 f"typed, running pipeline directly")
        _run_hunt_with_rqs(chat_id, parsed_rqs)
        return

    # raw_rqs is "auto" or "custom"
    if isinstance(raw_rqs, str) and raw_rqs.strip().lower() == "custom":
        log.info(f"_start_hunt_from_review: user picked custom RQs, asking them")
        state = load_chat_state(chat_id) or {}
        state["hunt_v2_awaiting_custom_rqs"] = True
        save_chat_state(chat_id, state)
        _send_message(
            chat_id,
            "✍️ *Type your research questions*\n\n"
            "Send 1-5 research questions, one per line. "
            "I'll run the hunt with them.",
            parse_mode="Markdown",
            reply_markup={
                "inline_keyboard": [[
                    {"text": "↩ Back to review", "callback_data": "hunt:back_to_review"},
                    {"text": "❌ Cancel", "callback_data": "hunt:cancel"},
                ]]
            },
        )
        return

    # Default: generate 3 RQ packages and show the picker
    log.info(f"_start_hunt_from_review: generating 3 RQ packages")
    title = answers.get("title", "")
    if not title:
        _send_message(chat_id, "⚠️ No title set. Tap ✏️ Edit step 2 first.",
                      parse_mode="Markdown")
        return

    _send_message(
        chat_id,
        "🧠 *Generating 3 RQ packages for your title...*\n\n"
        "_Each package focuses on a different angle (theoretical, empirical, "
        "applied). This takes 30-90 seconds._",
        parse_mode="Markdown",
    )
    try:
        from rq_packages import generate_rq_packages, format_packages_picker, packages_picker_keyboard
        import time as _t
        _t0 = _t.time()
        try:
            packages = generate_rq_packages(title, max_total_seconds=90)
        except Exception as gen_err:
            log.warning(f"generate_rq_packages failed: {gen_err}")
            from rq_packages import generate_rq_packages as _gen
            packages = _gen(title, ollama_fn=None, max_total_seconds=10)
        log.info(f"_start_hunt_from_review: {len(packages)} packages in "
                 f"{_t.time()-_t0:.1f}s")
    except Exception as e:
        log.error(f"RQ package generation crashed: {e}")
        from rq_packages import PACKAGE_ANGLES, _extract_keywords
        kw = _extract_keywords(title)
        packages = [
            {
                "id": a["id"], "emoji": a["emoji"], "label": a["label"],
                "title": f"{a['label']} lens on {kw[:60]}",
                "focus": a["default_focus"],
                "rqs": [t.format(kw=kw) for t in a["template_rqs"]],
                "why": a["default_why"],
            } for a in PACKAGE_ANGLES
        ]

    # Stash packages in state for the picker callback
    state = load_chat_state(chat_id) or {}
    state["hunt_v2_rq_packages"] = packages
    save_chat_state(chat_id, state)

    text = format_packages_picker(packages)
    kb = packages_picker_keyboard()
    _send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)
    log.info(f"_start_hunt_from_review: package picker shown with "
             f"{len(packages)} packages")


def _on_rq_package_picked(chat_id: int, package_id: str) -> None:
    """User tapped a button on the RQ package picker. Run the pipeline
    with the chosen package's RQs (or all packages, or ask for custom).
    """
    from hunt_intake import get_intake_answers
    log.info(f"_on_rq_package_picked: chat {chat_id} picked {package_id!r}")
    state = load_chat_state(chat_id) or {}
    packages = state.get("hunt_v2_rq_packages") or []

    if package_id == "custom":
        # Ask the user to type their own RQs
        state["hunt_v2_awaiting_custom_rqs"] = True
        save_chat_state(chat_id, state)
        _send_message(
            chat_id,
            "✍️ *Type your research questions*\n\n"
            "Send 1-5 research questions, one per line.",
            parse_mode="Markdown",
            reply_markup={
                "inline_keyboard": [[
                    {"text": "↩ Back to packages", "callback_data": "hunt:back_to_packages"},
                    {"text": "❌ Cancel", "callback_data": "hunt:cancel"},
                ]]
            },
        )
        return

    chosen: List[str] = []
    label = ""
    if package_id == "all":
        for pkg in packages:
            chosen.extend(pkg.get("rqs", []))
        label = "🎲 All packages (mixed)"
    else:
        for pkg in packages:
            if pkg.get("id") == package_id:
                chosen = list(pkg.get("rqs", []))
                label = f"{pkg.get('emoji','')} {pkg.get('label','')}"
                break
    if not chosen:
        _send_message(chat_id, "⚠️ Could not find that package. Try /start again.",
                      parse_mode="Markdown")
        return

    _send_message(
        chat_id,
        f"✅ *Package picked:* {label}\n\n"
        f"❓ *Research questions ({len(chosen)}):*\n"
        + "\n".join(f"   {i}. {q}" for i, q in enumerate(chosen, 1))
        + "\n\n⏳ Starting the pipeline...",
        parse_mode="Markdown",
    )
    _run_hunt_with_rqs(chat_id, chosen)


def _run_hunt_with_rqs(chat_id: int, research_questions: List[str]) -> None:
    """Common pipeline kick-off: take the final research_questions list,
    build the params dict, save state, spawn the runner thread.
    """
    from hunt_intake import get_intake_answers
    answers = get_intake_answers(chat_id)
    log.info(f"_run_hunt_with_rqs: chat {chat_id} with {len(research_questions)} RQs")

    # Apply platform aliasing
    plat_key = answers.get("platforms", "all")
    plat_map = {
        "all": ["all"],
        "tier12": ["crossref", "openalex", "semantic_scholar", "pubmed",
                   "arxiv", "eric", "doaj", "base", "core", "europe_pmc",
                   "core_api", "oa_mg", "zenodo", "zenodo_extended",
                   "openaire", "worldwidescience", "doaj", "ssoar",
                   "academic_eu", "google_scholar"],
        "tier1": ["crossref", "openalex", "semantic_scholar", "pubmed",
                  "arxiv", "eric", "doaj", "base", "core", "europe_pmc"],
    }
    platforms = plat_map.get(plat_key, ["all"])

    # Parse max_papers
    raw_max = answers.get("max_papers", "1000")
    if isinstance(raw_max, str) and raw_max.strip().lower() in ("0", "deep", "all", "max", "no cap", "infinite"):
        max_papers = 0
    else:
        try:
            n = int(raw_max)
            max_papers = max(5, n)
        except (TypeError, ValueError):
            max_papers = 1000

    download_pdfs = (str(answers.get("download_pdfs", "yes")).lower() in ("yes", "y", "true", "1"))
    research_type = answers.get("research_type", "general")
    field = answers.get("field", "general")
    rq_angle = answers.get("rq_angle", "empirical")
    language = answers.get("language", "en")
    country = answers.get("country", "world")
    paper_type = answers.get("paper_type", "all")
    quartile_filter = answers.get("quartile_filter", "any")
    open_access = (str(answers.get("open_access", "no")).lower() in ("yes", "y", "true", "1"))

    # Parse year_range
    raw_year = str(answers.get("year_range", "any")).strip().lower()
    year_from, year_to = None, None
    if raw_year and raw_year not in ("any", "all", "skip", "-"):
        if "-" in raw_year:
            parts = raw_year.split("-", 1)
            try: year_from = int(parts[0].strip())
            except (ValueError, IndexError): year_from = None
            try: year_to = int(parts[1].strip())
            except (ValueError, IndexError): year_to = None
        else:
            try:
                y = int(raw_year)
                year_from = y
                year_to = y
            except ValueError:
                year_from, year_to = None, None

    max_label = "🌊 DEEP (no cap)" if max_papers == 0 else f"{max_papers:,}"
    year_label = (f"{year_from}" if year_from == year_to
                  else f"{year_from or 'any'}–{year_to or 'present'}")
    rq_preview = "\n❓ *Research questions:*\n"
    for i, q in enumerate(research_questions[:5], 1):
        rq_preview += f"  {i}. {q[:120]}{'...' if len(q) > 120 else ''}\n"

    summary = (
        "✅ *All set! Starting your hunt...*\n\n"
        f"📚 Title: *{answers.get('title', '?')[:80]}*\n"
        f"📖 Type: *{research_type}*  |  🎓 Field: *{field}*\n"
        f"🧭 Angle: *{rq_angle}*  |  🌍 Region: *{country}*  |  🌐 Lang: *{language}*\n"
        f"📄 Paper type: *{paper_type}*  |  ⭐ Quartile: *{quartile_filter}*  |  🔓 OA: *{'yes' if open_access else 'no'}*\n"
        f"🌐 Platforms: *{plat_key}* ({len(platforms)} selected)\n"
        f"📅 Year range: *{year_label}*\n"
        f"📄 Max papers: *{max_label}*\n"
        f"📥 Download PDFs: *{'yes' if download_pdfs else 'no'}*"
        f"{rq_preview}\n"
        f"⏳ Pipeline starting in 3 seconds..."
    )
    progress_msg = _send_message(chat_id, summary, parse_mode="Markdown")
    log.info(f"_run_hunt_with_rqs: sent summary, message_id={progress_msg}")

    state = (load_chat_state(chat_id) or {})
    hunt_params = {
        "title": answers.get("title", ""),
        "research_type": research_type,
        "field": field,
        "rq_angle": rq_angle,
        "language": language,
        "country": country,
        "paper_type": paper_type,
        "quartile_filter": quartile_filter,
        "open_access": open_access,
        "research_questions": research_questions,
        "year_from": year_from,
        "year_to": year_to,
        "platforms": platforms,
        "max_papers": max_papers,
        "download_pdfs": download_pdfs,
    }
    state["hunt_v2_params"] = hunt_params
    state["hunt_v2_running"] = True
    state["hunt_v2_started_at"] = __import__("time").time()
    state["hunt_v2_current_stage"] = "starting"
    state["hunt_v2_current_pct"] = 0
    for k in list(state.keys()):
        if k.startswith("hunt_intake_") or k == "hunt_v2_awaiting_custom_rqs":
            state.pop(k, None)
    state.pop("hunt_v2_rq_packages", None)
    save_chat_state(chat_id, state)

    # Way A: always run locally. No GHA, no Drive, no RQ packages.
    # Skip the GHA dispatch path entirely — local is simpler and more reliable.
    log.info(f"_run_hunt_with_rqs: Way A — spawning local thread for chat {chat_id}")
    _edit_message(progress_msg,
                  "⏳ *Starting local hunt...*\n\n"
                  "Searching 6 fast academic platforms. ~1-2 min.\n"
                  "Results will arrive here as Telegram messages.",
                  parse_mode="Markdown")
    import threading
    thread = threading.Thread(
        target=_run_v2_hunt_local_simple,
        args=(chat_id, hunt_params, progress_msg),
        daemon=True,
    )
    thread.start()
    log.info(f"_run_hunt_with_rqs: local thread spawned for chat {chat_id}")


def _run_v2_hunt_from_intake(chat_id: int, params: Dict[str, Any],
                              progress_msg_id: Optional[int]) -> None:
    """Background runner that uses the new intake params + heartbeat + sends files."""
    from hunt_intake import cancel_intake
    try:
        field_map = {
            "MA": "education", "PhD": "education",
            "RA": "general", "SR": "general",
            "EX": "general", "CS": "general",
            "general": "general",
        }
        hunt_params = {
            "title": params.get("title", ""),
            "field": field_map.get(params.get("research_type", "general"), "general"),
            "study_types": [],
            "year_from": 2018,
            "year_to": 2025,
            "research_questions": [f"Find papers about {params.get('title', '')}"],
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
        progress_cb = _make_progress_callback(chat_id, progress_msg_id)
        # Start heartbeat thread
        stop_event = threading.Event()
        heartbeat_thread = threading.Thread(
            target=_hunt_heartbeat,
            args=(chat_id, stop_event, progress_msg_id),
            daemon=True,
        )
        heartbeat_thread.start()
        try:
            result = run_hunt(hunt_params, progress_callback=progress_cb)
        finally:
            stop_event.set()
            heartbeat_thread.join(timeout=2)

        # Update state
        state = load_chat_state(chat_id) or {}
        state["hunt_v2_running"] = False
        state["hunt_v2_finished_at"] = __import__("time").time()
        state["hunt_v2_last_result"] = {
            "success": result.get("success", False),
            "total_papers": result.get("total_papers", 0),
            "downloaded": result.get("downloaded", 0),
            "red_list_count": result.get("red_list_count", 0),
            "output_folder": result.get("output_folder", ""),
            "error": result.get("error", ""),
        }
        save_chat_state(chat_id, state)

        if not result.get("success", True):
            err = result.get("error", "Unknown error")
            _send_message(chat_id,
                          f"⚠️ *Hunt failed*\n\n`{err[:500]}`\n\n"
                          "Try a simpler topic or /hunt2 with fewer platforms.",
                          parse_mode="Markdown")
            cancel_intake(chat_id)
            return

        # Send final files
        _send_hunt_v2_result(chat_id, result, params)
        cancel_intake(chat_id)

    except Exception as e:
        log.error(f"_run_v2_hunt_from_intake failed: {e}", exc_info=True)
        _send_message(chat_id, f"⚠️ *Hunt error*\n\n`{str(e)[:500]}`",
                      parse_mode="Markdown")
        cancel_intake(chat_id)


def _run_v2_hunt_local_simple(chat_id: int, params: Dict[str, Any],
                                progress_msg_id: Optional[int]) -> None:
    """Way A: simple local-only hunt. No GHA, no Drive, no RQ packages,
    no PDF download, no quartile check. Just topic → 70+ platforms →
    relevance filter → top N papers → Telegram."""
    from hunt_intake import cancel_intake
    try:
        title = params.get("title", "Research Topic")
        year_from = params.get("year_from")
        year_to = params.get("year_to")
        max_papers = max(5, min(int(params.get("max_papers", 15) or 15), 50))

        progress_cb = _make_progress_callback(chat_id, progress_msg_id)

        from local_hunt import run_local_hunt, format_for_telegram
        result = run_local_hunt(
            topic=title,
            max_papers=max_papers,
            year_from=year_from, year_to=year_to,
            progress_callback=progress_cb,
        )

        # Update state
        state = load_chat_state(chat_id) or {}
        state["hunt_v2_running"] = False
        state["hunt_v2_finished_at"] = __import__("time").time()
        state["hunt_v2_last_result"] = {
            "success": result.get("success", False),
            "total_papers": result.get("stats", {}).get("relevant", 0),
            "papers_returned": len(result.get("papers", [])),
            "queries_used": len(result.get("queries", [])),
            "error": result.get("error", ""),
        }
        save_chat_state(chat_id, state)

        if not result.get("success", True):
            err = result.get("error", "Unknown error")
            _send_message(chat_id,
                          f"⚠️ *Hunt failed*\n\n`{err[:500]}`\n\n"
                          "Try a simpler topic or /hunt2 with fewer platforms.",
                          parse_mode="Markdown")
            cancel_intake(chat_id)
            return

        # Send results as Telegram message(s)
        chunks = format_for_telegram(result, topic=title)
        if isinstance(chunks, str):
            chunks = [chunks]
        for i, chunk in enumerate(chunks, 1):
            try:
                _send_message(chat_id, chunk, parse_mode="Markdown")
            except Exception as send_err:
                # Fall back to plain text if Markdown parse fails
                _send_message(chat_id, chunk)
            if i < len(chunks):
                time.sleep(0.3)  # avoid Telegram rate limits
        # Final note
        n = len(result.get("papers", []))
        _send_message(chat_id,
                      f"✅ Done — {n} papers sent. Click the links to read them.\n\n"
                      f"Run /hunt2 again to refine, or /cancel to start over.",
                      parse_mode="Markdown")
        cancel_intake(chat_id)

    except Exception as e:
        log.error(f"_run_v2_hunt_local_simple failed: {e}", exc_info=True)
        _send_message(chat_id, f"⚠️ *Hunt error*\n\n`{str(e)[:500]}`",
                      parse_mode="Markdown")
        cancel_intake(chat_id)


def _hunt_heartbeat(chat_id: int, stop_event, progress_msg_id: Optional[int]) -> None:
    """Background thread: send a 'still working' message every 5 min while
    the hunt is running. Stops when stop_event is set. Shows current stage
    + percentage read from chat state (written by _make_progress_callback)."""
    while not stop_event.is_set():
        if stop_event.wait(timeout=300):  # 5 min
            break
        try:
            # Read latest state to get current stage + %
            state = load_chat_state(chat_id) or {}
            elapsed_min = (__import__("time").time() - state.get("hunt_v2_started_at", 0)) / 60
            stage = state.get("hunt_v2_current_stage", "running")
            pct = state.get("hunt_v2_current_pct", 0)
            msg = state.get("hunt_v2_current_message", "")
            stage_label = stage.replace("_", " ").title()
            line2 = f"\n🔄 Current: *{stage_label}* [{pct}%]" if stage else ""
            if msg:
                line2 += f"\n_{msg[:120]}_"
            _send_message(
                chat_id,
                f"⏳ *Still working...* ({elapsed_min:.0f} min elapsed)"
                f"{line2}\n\n"
                f"I'll send the final report + files when done.\n"
                f"Send /status anytime to check.",
                parse_mode="Markdown",
            )
        except Exception as e:
            log.warning(f"heartbeat send failed: {e}")


def _send_hunt_v2_result(chat_id: int, result: Dict[str, Any],
                          params: Dict[str, Any]) -> None:
    """Send the final hunt result: summary + xlsx + md + Drive link."""
    total = result.get("total_papers", 0)
    downloaded = result.get("downloaded", 0)
    output_folder = result.get("output_folder", "")
    red_count = result.get("red_list_count", 0)
    results_data = result.get("results", {})
    run_stats = results_data.get("run_stats", {})
    q_dist = run_stats.get("q_distribution", {})

    # Summary text
    title = params.get("title", "?")[:60]
    elapsed = (__import__("time").time() - (load_chat_state(chat_id) or {}).get("hunt_v2_started_at", 0)) / 60
    future_studies_count = result.get("future_studies_count", 0)
    summary = (
        f"🎉 *Hunt Complete!*\n\n"
        f"📚 Title: *{title}*\n"
        f"⏱ Took: *{elapsed:.0f} min*\n"
        f"📄 Papers found: *{total}*\n"
        f"📥 PDFs downloaded: *{downloaded}*\n"
        f"📊 Quartiles: Q1:{q_dist.get('Q1', 0)} Q2:{q_dist.get('Q2', 0)} "
        f"Q3:{q_dist.get('Q3', 0)} Q4:{q_dist.get('Q4', 0)}\n"
    )
    if red_count > 0:
        summary += f"🔴 Manual download needed: *{red_count}*\n"
    if future_studies_count > 0:
        summary += f"🌟 Future research directions: *{future_studies_count}* (in .md and .docx)\n"

    # Drive folder (per-title) — surface errors to the user so they know
    # whether the files made it to their Drive.
    drive_url = None
    drive_error = None
    if output_folder:
        try:
            import google_integration as gdrive
            safe_title = _safe_name_for_drive(params.get("title", "hunt")[:50])
            drive_result = gdrive.upload_hunt_to_drive(
                output_folder, f"hunt_{safe_title}")
            if drive_result.get("folder_url"):
                drive_url = drive_result["folder_url"]
                files_n = drive_result.get("files_uploaded", 0)
                folders_n = drive_result.get("folders_created", 0)
                errors_n = drive_result.get("errors", 0)
                summary += (
                    f"\n📁 *Drive folder:* {drive_url}\n"
                    f"   ({files_n} files, {folders_n} subfolders"
                    + (f", {errors_n} upload errors" if errors_n else "")
                    + f")"
                )
            else:
                # No folder URL = Drive upload did not succeed
                errs = drive_result.get("errors", 0)
                drive_error = (
                    f"Drive upload returned no folder URL (errors={errs}). "
                    f"Check GOOGLE_OAUTH_REFRESH env var or memory.json."
                )
                log.error(f"Drive upload returned no URL: {drive_result}")
        except Exception as e:
            drive_error = f"{type(e).__name__}: {str(e)[:200]}"
            log.error(f"Drive upload failed: {e}", exc_info=True)

    if drive_error:
        # Tell the user immediately so they know files didn't reach Drive
        summary += (
            f"\n\n⚠️ *Drive upload failed*\n"
            f"`{drive_error}`\n"
            f"Local files are still in the chat below + on the runner."
        )

    summary += "\n📎 *Sending report files...*"
    _send_message(chat_id, summary, parse_mode="Markdown",
                  reply_markup=_keyboard_after_complete())

    # Send .xlsx as Telegram document
    pdfs_sent = 0
    if output_folder:
        # 1. Send the HEAVY PDF report first (if generated — requires LibreOffice/Word)
        # The PDF is preferred by academics over DOCX/MD.
        pdf_report = os.path.join(output_folder, "research_report.pdf")
        if os.path.isfile(pdf_report):
            size_mb = os.path.getsize(pdf_report) / (1024 * 1024)
            if size_mb <= 45:
                _send_document(chat_id, pdf_report,
                               caption=f"📕 research_report.pdf ({size_mb:.1f} MB) — HEAVY REPORT")
            else:
                _send_message(chat_id,
                              f"📕 research_report.pdf is *{size_mb:.0f} MB* — too large for Telegram, "
                              f"available in Drive folder.",
                              parse_mode="Markdown")

        # 2. Send .xlsx (master database with all papers)
        xlsx_path = os.path.join(output_folder, "master_database.xlsx")
        if os.path.isfile(xlsx_path):
            _send_document(chat_id, xlsx_path,
                           caption=f"📊 master_database.xlsx ({os.path.getsize(xlsx_path):,} bytes)")

        # 3. Send .docx (Word version — editable)
        docx_path = os.path.join(output_folder, "research_report.docx")
        if os.path.isfile(docx_path):
            _send_document(chat_id, docx_path,
                           caption=f"📄 research_report.docx ({os.path.getsize(docx_path):,} bytes)")

        # 4. Send .md report (markdown — easy to read)
        md_path = os.path.join(output_folder, "research_report.md")
        if os.path.isfile(md_path):
            with open(md_path, "rb") as f:
                md_bytes = f.read()
            # Telegram document limit 50MB; md should be well under
            _send_document(chat_id, md_path,
                           caption=f"📝 research_report.md ({len(md_bytes):,} chars)")

        # 5. Send results.json (full search + quartile data)
        results_json = os.path.join(output_folder, "results.json")
        if os.path.isfile(results_json):
            _send_document(chat_id, results_json,
                           caption="🔍 results.json (full search + quartile data)")

        # 6. Send top 5 downloaded PDFs (the actual papers)
        try:
            pdfs_dir = os.path.join(output_folder, "pdfs")
            if os.path.isdir(pdfs_dir):
                all_pdfs = [
                    (os.path.join(pdfs_dir, f), f)
                    for f in os.listdir(pdfs_dir)
                    if f.lower().endswith(".pdf")
                ]
                all_pdfs.sort(key=lambda x: os.path.getmtime(x[0]), reverse=True)
                for pdf_path, fname in all_pdfs[:5]:
                    try:
                        size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
                        if size_mb > 45:
                            log.warning(f"PDF too large to send via Telegram: {fname} ({size_mb:.1f} MB)")
                            continue
                        _send_document(chat_id, pdf_path,
                                       caption=f"📕 {fname} ({size_mb:.1f} MB)")
                        pdfs_sent += 1
                    except Exception as e:
                        log.warning(f"PDF send failed for {fname}: {e}")
        except Exception as e:
            log.warning(f"PDF directory scan failed: {e}")

    if pdfs_sent > 0:
        _send_message(
            chat_id,
            f"📚 Sent *{pdfs_sent}* of the best-matching PDFs directly here.\n"
            f"All PDFs ({downloaded} total) are in the Drive folder too.",
            parse_mode="Markdown",
        )

    # Send the search results table (top 10 papers, by score)
    try:
        all_papers = results_data.get("papers", [])
        if all_papers:
            # Sort by score (or match_score) descending; fall back to title
            sorted_papers = sorted(
                all_papers,
                key=lambda p: (
                    p.get("match_score") or p.get("score") or
                    p.get("final_score") or p.get("relevance_score") or 0
                ),
                reverse=True,
            )
            top_papers = sorted_papers[:10]
            table = "📋 *Top 10 papers found:*\n\n"
            for i, p in enumerate(top_papers, 1):
                tt = (p.get("title") or "?")[:60]
                yr = p.get("year", "?")
                q = p.get("scopus_quartile", "?")
                if isinstance(q, dict):
                    q = q.get("quartile", "?")
                doi = p.get("doi", "")
                downloaded_mark = "📥" if p.get("downloaded") else "  "
                table += f"{i}. {downloaded_mark} *{tt}* ({yr}) [Q{q}]\n"
                if doi:
                    table += f"   DOI: `{str(doi)[:40]}`\n"
            _send_message(chat_id, table, parse_mode="Markdown")
    except Exception as e:
        log.warning(f"top_papers formatting failed: {e}")


def _handle_hunt_callback(chat_id: int, data: str, step: str) -> None:
    """Handle research hunt callback queries."""
    
    if data.startswith("hunt:type:"):
        research_type = data.replace("hunt:type:", "")
        # Store research type in state
        state = load_chat_state(chat_id) or {}
        state["research_type"] = research_type
        save_chat_state(chat_id, state)
        
        _send_message(
            chat_id,
            f"✅ Research type: *{research_type}*\n\n"
            f"Step 2: What platforms should I search?\n\n"
            "Select platforms (you can select multiple):",
            parse_mode="Markdown",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "📖 Semantic Scholar", "callback_data": "hunt:platform:ss"},
                     {"text": "🔬 PubMed", "callback_data": "hunt:platform:pubmed"}],
                    [{"text": "📚 CrossRef", "callback_data": "hunt:platform:crossref"},
                     {"text": "🌐 OpenAlex", "callback_data": "hunt:platform:openalex"}],
                    [{"text": "📦 CORE", "callback_data": "hunt:platform:core"},
                     {"text": "🎓 Semantic Scholar +", "callback_data": "hunt:platform:s2plus"}],
                    [{"text": "✅ All (Recommended)", "callback_data": "hunt:platform:all"}],
                    [{"text": "➡️ Continue with selected", "callback_data": "hunt:confirm_platforms"}],
                ]
            },
        )
    
    elif data.startswith("hunt:platform:"):
        platform = data.replace("hunt:platform:", "")
        state = load_chat_state(chat_id) or {}
        
        if platform == "all":
            state["platforms"] = ["semantic_scholar", "pubmed", "crossref", "openalex", "core", "s2plus"]
        else:
            if "platforms" not in state:
                state["platforms"] = []
            if platform not in state["platforms"]:
                state["platforms"].append(platform)
        
        save_chat_state(chat_id, state)
        
        platforms_list = ", ".join(state.get("platforms", []))
        _send_message(
            chat_id,
            f"📌 Selected platforms: *{platforms_list}*\n\n"
            "Tap 'Continue' when ready:",
            parse_mode="Markdown",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "➡️ Continue", "callback_data": "hunt:confirm_platforms"}],
                    [{"text": "❌ Cancel", "callback_data": "cancel"}],
                ]
            },
        )
    
    elif data == "hunt:confirm_platforms":
        state = load_chat_state(chat_id) or {}
        research_type = state.get("research_type", "general")
        platforms = state.get("platforms", ["all"])
        
        # Ask for the topic
        state["awaiting_hunt_topic"] = True
        state["hunt_research_type"] = research_type
        state["hunt_platforms"] = platforms
        save_chat_state(chat_id, state)
        
        _send_message(
            chat_id,
            "📝 *Great! Now tell me the topic.*\n\n"
            f"Type: *{research_type}*\n"
            f"Platforms: *{', '.join(platforms)}*\n\n"
            "Send me the research topic you want to search for:",
            parse_mode="Markdown",
        )


def _run_research_hunt(chat_id: int, research_type: str, platforms: List[str]) -> None:
    """Background thread to run the research hunt."""
    try:
        from precision_engine import _call_ollama
        import requests
        
        # Generate search queries based on research type
        queries = _generate_queries(research_type)
        
        all_results = []
        
        for i, query in enumerate(queries):
            _send_message(chat_id, f"🔍 Searching: *{query[:50]}...* ({i+1}/{len(queries)})", parse_mode="Markdown")
            
            # Search CrossRef as primary source
            try:
                url = f'https://api.crossref.org/works?query={requests.utils.quote(query)}&rows=5'
                resp = requests.get(url, timeout=30)
                data = resp.json()
                items = data.get('message', {}).get('items', [])
                
                for item in items:
                    paper = {
                        'title': item.get('title', [''])[0] if item.get('title') else '',
                        'doi': item.get('DOI', ''),
                        'journal': item.get('container-title', [''])[0] if item.get('container-title') else '',
                        'year': str(item.get('published-print', {}).get('date-parts', [['']])[0][0]) if item.get('published-print') else '',
                        'authors': [a.get('given', '') + ' ' + a.get('family', '') for a in item.get('author', [])],
                    }
                    all_results.append(paper)
            except Exception as e:
                log.error(f"Search error: {e}")
        
        # Deduplicate
        seen = set()
        unique = []
        for r in all_results:
            if r['doi'] not in seen:
                seen.add(r['doi'])
                unique.append(r)
        
        # Send results
        if unique:
            _send_message(
                chat_id,
                f"🎉 *Found {len(unique)} papers!*\n\n"
                "Sending results...",
                parse_mode="Markdown",
            )
            
            for j, paper in enumerate(unique[:10]):  # Limit to 10 results
                title = paper.get('title', 'Unknown')[:60]
                doi = paper.get('doi', '')
                journal = paper.get('journal', 'Unknown')[:30]
                year = paper.get('year', 'Unknown')
                
                msg = (
                    f"📄 *{title}*\n"
                    f"📅 {year} | 📰 {journal}\n"
                    f"🔗 DOI: `{doi}`\n\n"
                    f"[Open Paper](https://doi.org/{doi})"
                )
                
                _send_message(
                    chat_id,
                    msg,
                    parse_mode="Markdown",
                    reply_markup={
                        "inline_keyboard": [
                            [{"text": "📊 Verify in Sheet", "callback_data": f"result:add_{j}"}],
                            [{"text": "🔍 Search Similar", "callback_data": f"result:similar_{j}"}],
                        ]
                    },
                )
        else:
            _send_message(
                chat_id,
                "❌ No papers found. Try a different topic or more platforms.",
                parse_mode="Markdown",
            )
        
        # Clear state
        clear_chat_state(chat_id)
        
    except Exception as e:
        log.error(f"Research hunt error: {e}")
        _send_message(
            chat_id,
            f"⚠️ *Error during research*\n\n`{str(e)}`\n\n"
            "Try again with /hunt or /find",
            parse_mode="Markdown",
        )


# ============================================================================
# v2-4 Full Pipeline Integration
# ============================================================================

def _safe_name_for_drive(name: str, mx: int = 50) -> str:
    """Build a Drive-friendly folder name from a topic string.
    - Removes characters illegal in Drive folder names (/\\:*?"<>|)
    - Collapses whitespace to underscores
    - Truncates to `mx` chars
    """
    import re
    s = re.sub(r'[\\/:*?"<>|]', '_', (name or "untitled"))
    s = re.sub(r'\s+', '_', s).strip('_')
    if not s:
        s = "untitled"
    if len(s) > mx:
        s = s[:mx].rstrip('_')
    return s


def _make_progress_callback(chat_id: int, progress_msg_id: Optional[int]):
    """Create a progress callback that sends Telegram updates."""
    last_progress = {"stage": "", "pct": -1}

    def cb(stage: str, message: str, progress: float):
        nonlocal last_progress
        pct = int(progress * 100)
        emoji = {
            "starting": "🚀",
            "generating_queries": "🧠",
            "searching": "🔍",
            "deduplicating": "🔎",
            "checking_quartiles": "📊",
            "downloading": "📥",
            "generating_report": "📝",
            "done": "✅",
        }.get(stage, "🔄")

        # Write to chat state so the heartbeat thread can read it
        try:
            state = load_chat_state(chat_id) or {}
            state["hunt_v2_current_stage"] = stage
            state["hunt_v2_current_pct"] = pct
            state["hunt_v2_current_message"] = message[:200] if message else ""
            save_chat_state(chat_id, state)
        except Exception:
            pass

        # Only send an update if progress changed by at least 5%
        if stage == last_progress["stage"] and abs(pct - last_progress["pct"]) < 5:
            return
        last_progress["stage"] = stage
        last_progress["pct"] = pct

        short_msg = message[:200] if len(message) > 200 else message
        text = f"{emoji} *{stage.replace('_', ' ').title()}* [{pct}%]\n{short_msg}"

        if progress_msg_id:
            try:
                _edit_message(chat_id, progress_msg_id, text, parse_mode="Markdown")
            except Exception:
                _send_message(chat_id, text, parse_mode="Markdown")
        else:
            _send_message(chat_id, text, parse_mode="Markdown")

    return cb


def _run_v2_hunt(chat_id: int, topic: str, platforms: List[str],
                  research_type: str, progress_msg_id: Optional[int]) -> None:
    """Background thread: run full v2-4 pipeline and report to Telegram."""
    try:
        # Build params
        field_map = {
            "lit_review": "general",
            "dissertation": "education",
            "news": "general",
            "technical": "computer_science",
            "geographic": "geography",
            "scientific": "general",
            "general": "general",
        }
        year_from = 2020  # sensible default for Telegram hunts
        year_to = 2025
        
        params = {
            "title": topic,
            "field": field_map.get(research_type, "general"),
            "study_types": [],
            "year_from": year_from,
            "year_to": year_to,
            "research_questions": [f"Find papers about {topic}"],
            "platforms": platforms,
            "search_mode": "normal",
            "use_scihub": False,
            "single_folder": True,
            "study_keywords": [],
            "lang_label": "English",
            "search_languages": ["en"],
        }
        
        progress_cb = _make_progress_callback(chat_id, progress_msg_id)

        # Run the pipeline
        result = run_hunt(params, progress_callback=progress_cb)

        # Check success flag (added in critical-fix)
        if not result.get("success", True):
            err = result.get("error", "Unknown error")
            log.error(f"Hunt pipeline returned failure: {err}")
            _send_message(
                chat_id,
                f"⚠️ *Hunt pipeline failed*\n\n"
                f"Topic: *{topic[:60]}*\n"
                f"Error: `{err[:500]}`\n\n"
                "The pipeline caught the error and exited cleanly. "
                "Try a simpler topic or fewer platforms via /hunt → custom.",
                parse_mode="Markdown",
                reply_markup=_keyboard_after_complete(),
            )
            clear_chat_state(chat_id)
            return

        total = result["total_papers"]
        downloaded = result["downloaded"]
        output_folder = result["output_folder"]
        red_count = result.get("red_list_count", 0)
        results_data = result.get("results", {})

        # Zip the results
        zip_path = None
        if total > 0:
            progress_cb("generating_report", "Zipping results for download...", 0.92)
            try:
                zip_path = zip_results(output_folder)
            except Exception as e:
                log.error(f"Zip failed: {e}")

        # Build summary
        run_stats = results_data.get("run_stats", {})
        all_q = run_stats.get("q_distribution", {})
        q_line = f"Q1:{all_q.get('Q1',0)} Q2:{all_q.get('Q2',0)} Q3:{all_q.get('Q3',0)} Q4:{all_q.get('Q4',0)}"

        summary = (
            f"🎉 *Hunt Complete!*\n\n"
            f"📚 Topic: *{topic[:60]}*\n"
            f"📄 New papers: *{total}*\n"
            f"📥 PDFs downloaded: *{downloaded}*\n"
            f"📊 Scopus: {q_line}\n"
        )

        type_dist = run_stats.get("type_distribution", {})
        if any(type_dist.values()):
            parts = [f"{k}:{v}" for k, v in type_dist.items() if v > 0]
            summary += f"📁 Types: {', '.join(parts)}\n"

        if red_count > 0:
            summary += f"🔴 Red list (manual): *{red_count}*\n"

        if output_folder:
            summary += f"\n📂 `{output_folder}`\n"

        # Per-title Drive folder: upload full folder structure (not just zip)
        # so users see all 16 subfolders directly under the title's main folder
        drive_url = None
        try:
            import google_integration as gdrive
            safe_title = _safe_name_for_drive(topic[:50])
            drive_result = gdrive.upload_hunt_to_drive(output_folder, f"hunt_{safe_title}")
            if drive_result.get("success") and drive_result.get("folder_url"):
                drive_url = drive_result["folder_url"]
                summary += (
                    f"\n📁 [Open Drive folder: {safe_title}]"
                    f"({drive_url}) "
                    f"({drive_result['files_uploaded']} files, "
                    f"{drive_result['folders_created']} subfolders)"
                )
            elif drive_result.get("errors", 0) > 0:
                log.error(f"Drive folder upload had {drive_result['errors']} errors")
        except Exception as e:
            log.error(f"Drive folder upload failed: {e}", exc_info=True)

        # Also upload the zip for easy one-click download
        if zip_path:
            upload_url = None
            try:
                import google_integration as gdrive
                upload_url = gdrive.upload_results_to_drive(
                    zip_path, f"hunt_{topic[:30]}"
                )
                if upload_url and upload_url.startswith("https://"):
                    summary += f"\n📦 [Download ZIP]({upload_url})"
            except Exception as e:
                log.error(f"Drive upload failed: {e}")

        # Send final summary
        _send_message(chat_id, summary, parse_mode="Markdown",
                      reply_markup=_keyboard_after_complete())

        # Clear state
        clear_chat_state(chat_id)

    except Exception as e:
        log.error(f"_run_v2_hunt failed: {e}", exc_info=True)
        _send_message(
            chat_id,
            f"⚠️ *Hunt pipeline error*\n\n`{str(e)[:500]}`\n\n"
            "Try again or use a simpler topic.",
            parse_mode="Markdown",
        )


def _generate_queries(research_type: str) -> List[str]:
    """Generate search queries based on research type."""
    base_queries = {
        "lit_review": [
            "machine learning education systematic review",
            "artificial intelligence learning review",
            "deep learning education literature",
        ],
        "dissertation": [
            "phd dissertation education technology",
            "doctoral thesis machine learning",
            "phd thesis artificial intelligence education",
        ],
        "news": [
            "AI education news 2024",
            "machine learning education latest",
            "education technology recent",
        ],
        "technical": [
            "machine learning technical paper",
            "neural networks research paper",
            "deep learning architecture paper",
        ],
        "geographic": [
            "education technology developing countries",
            "AI learning global south",
            "machine learning education regional",
        ],
        "scientific": [
            "scientific machine learning research",
            "AI education peer reviewed",
            "machine learning empirical study",
        ],
    }
    return base_queries.get(research_type, base_queries["technical"])


# ============================================================================
# Chat State Management (Simple JSON persistence)
# ============================================================================

def load_chat_state(chat_id: int) -> Optional[Dict[str, Any]]:
    """Load chat-specific state."""
    try:
        state_dir = os.environ.get("STATE_DIR", "/tmp/telegram_state")
        state_file = os.path.join(state_dir, f"chat_{chat_id}.json")
        if os.path.exists(state_file):
            with open(state_file, "r") as f:
                return json.load(f)
    except Exception as e:
        log.error(f"Load chat state failed: {e}")
    return None


def save_chat_state(chat_id: int, state: Dict[str, Any]) -> None:
    """Save chat-specific state."""
    try:
        state_dir = os.environ.get("STATE_DIR", "/tmp/telegram_state")
        os.makedirs(state_dir, exist_ok=True)
        state_file = os.path.join(state_dir, f"chat_{chat_id}.json")
        with open(state_file + ".tmp", "w") as f:
            json.dump(state, f)
        os.replace(state_file + ".tmp", state_file)
    except Exception as e:
        log.error(f"Save chat state failed: {e}")


def clear_chat_state(chat_id: int) -> None:
    """Clear chat-specific state."""
    try:
        state_dir = os.environ.get("STATE_DIR", "/tmp/telegram_state")
        state_file = os.path.join(state_dir, f"chat_{chat_id}.json")
        if os.path.exists(state_file):
            os.remove(state_file)
    except Exception as e:
        log.error(f"Clear chat state failed: {e}")


# ============================================================================
# Message handler (the heart of the bot)
# ============================================================================

def handle_message(update: Dict[str, Any]) -> None:
    """Process a single incoming message OR callback_query."""
    # 1) Callback queries (button presses)
    if "callback_query" in update:
        cb = update["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        message_id = cb["message"]["message_id"]
        data = cb.get("data", "")

        # OLD v6.3 wizard callbacks (from /hunt interactive command only).
        # These are the only callbacks that go to the legacy _handle_hunt_callback.
        # Everything else under "hunt:" (hunt:start, hunt:cancel, hunt:edit:*,
        # hunt:set:*, hunt:back_to_review) goes to the NEW _handle_hunt_review_callback
        # via _handle_callback below. v6.7 fix: previously ALL hunt:* callbacks
        # were misrouted to the legacy handler, which silently dropped them.
        if (data.startswith("hunt:type:") or
            data.startswith("hunt:platform:") or
            data == "hunt:confirm_platforms"):
            _handle_hunt_callback(chat_id, data, "")
            _answer_callback(cb.get("id", ""), "")
            return

        _handle_callback(chat_id, message_id, data, cb.get("id", ""))
        return

    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    text = (msg.get("text") or "").strip()
    document = msg.get("document")
    if not chat_id:
        return

    log.info(f"chat={chat_id} text={text[:80]!r} doc={bool(document)}")

    # NEW: Interactive Research Hunt commands
    if text.startswith("/hunt2"):
        _cmd_hunt_v2(chat_id, text)
        return

    if text.startswith("/hunt") or text.startswith("/research"):
        _cmd_hunt(chat_id, text)
        return

    if text.startswith("/sleep"):
        _cmd_sleep(chat_id)
        return
    
    if text.startswith("/wake"):
        _cmd_wake(chat_id)
        return

    # Service commands always work, even when the wizard is active.
    # This lets /listrefs, /verify, /sheet, /status, /help be used mid-wizard.
    if text.startswith("/listrefs") or text.startswith("/verify") or text.startswith("/sheet") \
            or text.startswith("/status") or text.startswith("/help") or text.startswith("/cancel") \
            or text.startswith("/reset") or text.startswith("/start") \
            or text.startswith("/verifyrefs") or text.lower() in ("hi", "hello", "مرحبا", "bonjour"):
        if text.startswith("/listrefs"):
            _cmd_listrefs(chat_id)
            return
        if text.startswith("/verifyrefs"):
            _cmd_verifyrefs(chat_id)
            return
        if text.startswith("/verify"):
            _cmd_verify(chat_id, text)
            return
        if text.startswith("/sheet"):
            _cmd_sheet(chat_id)
            return
        if text.startswith("/status"):
            _cmd_status(chat_id)
            return
        if text.startswith("/help"):
            _cmd_help(chat_id)
            return
        if text.startswith("/start") or text.lower() in ("hi", "hello", "مرحبا", "bonjour"):
            # v6.6: show rich main menu (cancels any active wizard/intake)
            try:
                cancel_wizard(chat_id)
            except Exception:
                pass
            try:
                from hunt_intake import cancel_intake
                cancel_intake(chat_id)
            except Exception:
                pass
            _cmd_start(chat_id)
            return
        # /cancel or /reset fall through to the wizard cancel below
        if text.startswith("/cancel") or text.startswith("/reset"):
            cancel_wizard(chat_id)
            state_v = load_chat_state(chat_id) or {}
            if state_v.get("mode") == "verifyrefs":
                clear_chat_state(chat_id)
            # Also cancel any active hunt intake
            try:
                from hunt_intake import cancel_intake
                cancel_intake(chat_id)
            except Exception:
                pass
            _send_message(chat_id, "🗑 Wizard cancelled. Send /start to begin again.")
            return

    # Check if user is responding to hunt topic prompt
    if not text.startswith("/"):
        state = load_chat_state(chat_id) or {}
        # v6.7: if user is typing custom RQs, accept them and run the pipeline
        if state.get("hunt_v2_awaiting_custom_rqs") and text.strip():
            state.pop("hunt_v2_awaiting_custom_rqs", None)
            save_chat_state(chat_id, state)
            import re as _re
            rqs: List[str] = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                line = _re.sub(r'^(RQ\s*\d+\s*[:\.\)]\s*|\d+[\.\)]\s*|-\s*)',
                               '', line, flags=_re.IGNORECASE).strip()
                if line and len(line) > 5:
                    rqs.append(line)
            if not rqs:
                _send_message(chat_id, "⚠️ Could not parse any questions. "
                              "Send 1-5 questions, one per line.")
                return
            _send_message(chat_id, f"✅ Got {len(rqs)} custom RQs. Starting the hunt...")
            _run_hunt_with_rqs(chat_id, rqs)
            return
        if state.get("awaiting_hunt_topic") and text.strip():
            topic = text.strip()
            research_type = state.get("hunt_research_type", "general")
            platforms = state.get("hunt_platforms", ["all"])
            # Clear hunt-awaiting state
            state["awaiting_hunt_topic"] = False
            save_chat_state(chat_id, state)
            
            msg = _send_message(
                chat_id,
                f"🔍 *Starting Full Research Hunt*\n\n"
                f"Topic: *{topic[:80]}*\n"
                f"Type: *{research_type}*\n"
                f"Platforms: {len(platforms)} selected\n\n"
                f"⏳ This will take several minutes. I'll send progress updates...",
                parse_mode="Markdown",
            )
            thread = threading.Thread(
                target=_run_v2_hunt,
                args=(chat_id, topic, platforms, research_type, msg),
            )
            thread.daemon = True
            thread.start()
            return
    
    # Wizard takes priority if active (only for non-command text and /find, /start, /upload)
    if is_wizard_active(chat_id) and text:
        _handle_wizard_text(chat_id, text)
        return

    # Commands (note: /start is handled above in the service-commands block
    # so it can override an active wizard)
    if text.startswith("/find") or text.startswith("/search"):
        query = text.split(maxsplit=1)[1] if " " in text else ""
        if not query:
            _send_message(chat_id, "🔍 Send me a title or reference to find. Example:\n`/find Smith 2020 deep learning`", parse_mode="Markdown")
        else:
            _cmd_find(chat_id, query)
    elif text.startswith("/upload"):
        _send_message(chat_id, "📎 Send me your chapter file (PDF, DOCX, ODT, or TXT).")
    elif text.startswith("/verify"):
        _cmd_verify(chat_id, text)
    elif text.startswith("/listrefs"):
        _cmd_listrefs(chat_id)
    elif text.startswith("/sheet"):
        _cmd_sheet(chat_id)
    elif text.startswith("/status"):
        _cmd_status(chat_id)
    elif text.startswith("/drivesetup") or text.startswith("/setup drive"):
        _cmd_drivesetup(chat_id)
    elif text.startswith("/cancel") or text.startswith("/reset"):
        cancel_wizard(chat_id)
        state_v = load_chat_state(chat_id) or {}
        if state_v.get("mode") == "verifyrefs":
            clear_chat_state(chat_id)
        _send_message(chat_id, "🗑 Wizard cancelled. Send /start to begin again.")
    elif text.startswith("/help"):
        _cmd_help(chat_id)
    elif document:
        # If we're in verifyrefs mode and a file is uploaded, treat it as input
        state_v = load_chat_state(chat_id) or {}
        if state_v.get("mode") == "verifyrefs" and state_v.get("step") == "awaiting_input":
            _handle_verifyrefs_document(chat_id, document)
        else:
            _handle_document(chat_id, document)
    else:
        # Check if user is in any active wizard (text-based input)
        state_v = load_chat_state(chat_id) or {}
        if state_v.get("mode") == "verifyrefs":
            step = state_v.get("step")
            if step == "awaiting_input":
                _handle_verifyrefs_input(chat_id, text)
                return
            if step == "awaiting_output_name":
                _handle_verifyrefs_output_name(chat_id, text)
                return
            if step == "awaiting_download_yn":
                # Accept yes/no text
                t = text.strip().lower()
                if t in ("yes", "y", "1", "true", "ok", "✅"):
                    _handle_verifyrefs_download(chat_id, True)
                elif t in ("no", "n", "0", "false", "❌"):
                    _handle_verifyrefs_download(chat_id, False)
                else:
                    _send_message(chat_id, "Please reply `yes` or `no`.")
                return
        # Hunt intake (v6.3) — also accepts text answers
        if state_v.get("hunt_intake_active"):
            if _handle_hunt_intake_text(chat_id, text):
                return
        # Natural language fallback: try to detect intent
        _handle_natural_language(chat_id, text)


def _handle_callback(chat_id: int, message_id: int, data: str, callback_query_id: str) -> None:
    """Handle inline keyboard button presses."""
    _answer_callback(callback_query_id)
    if not data:
        return
    # ── Rich UI: main menu callbacks (v6.6) ──────────────────────────
    if data.startswith("main:"):
        _handle_main_menu_callback(chat_id, message_id, data)
        return
    # ── Rich UI: hunt review screen callbacks (v6.6) ──────────────────
    if data.startswith("hunt:"):
        _handle_hunt_review_callback(chat_id, message_id, data)
        return
    # verifyrefs wizard callbacks
    if data.startswith("vrefs:"):
        _handle_verifyrefs_callback(chat_id, message_id, data)
        return
    # hunt intake (v6.3) callbacks
    if data.startswith("hintake:"):
        _handle_hunt_intake_callback(chat_id, data)
        try:
            _edit_message(chat_id, message_id, "✅ Recorded.")
        except Exception:
            pass
        return
    if data == "cancel":
        cancel_wizard(chat_id)
        _edit_message(chat_id, message_id, "🗑 Wizard cancelled. Send /start to begin again.")
        return
    if data == "skip":
        state = skip_step(chat_id)
        _show_step(chat_id, message_id, state)
        return
    if data.startswith("ans:"):
        answer = data[4:]
        state = load_chapter_state(chat_id) or {}
        step = get_current_step(state)
        if step:
            state = record_answer(chat_id, step["key"], answer)
            _show_step(chat_id, message_id, state)
        return
    if data == "action:find":
        _edit_message(chat_id, message_id, "🔍 Send me a title or reference to find.")
    elif data == "action:upload":
        _edit_message(chat_id, message_id, "📎 Send me your chapter file (PDF, DOCX, ODT, or TXT).")
    elif data == "action:sheet":
        _cmd_sheet(chat_id)
    elif data == "action:new":
        cancel_wizard(chat_id)
        _cmd_start(chat_id)


# ──────────────────────────────────────────────────────────────────────
# Rich UI handlers (v6.6)
# ──────────────────────────────────────────────────────────────────────

def _handle_main_menu_callback(chat_id: int, message_id: int, data: str) -> None:
    """Dispatch main:newhunt, main:verifyrefs, main:myreports, main:help, etc."""
    from hunt_intake import cancel_intake
    action = data.split(":", 1)[1] if ":" in data else ""
    if action == "start":
        _edit_message(chat_id, message_id, telegram_ui.MAIN_MENU_TEXT,
                      parse_mode="Markdown",
                      reply_markup=telegram_ui.main_menu_keyboard())
        return
    if action == "newhunt":
        # Cancel any existing state and start the 7-step intake
        cancel_wizard(chat_id)
        cancel_intake(chat_id)
        _cmd_hunt_v2(chat_id, "")
        try:
            _edit_message(chat_id, message_id, "📝 Starting the 7-step intake...")
        except Exception:
            pass
        return
    if action == "verifyrefs":
        _cmd_verifyrefs(chat_id)
        try:
            _edit_message(chat_id, message_id, "📋 Loading the verify-references flow...")
        except Exception:
            pass
        return
    if action == "myreports":
        _cmd_reports(chat_id, message_id)
        return
    if action == "help":
        try:
            _edit_message(chat_id, message_id, telegram_ui.HELP_TEXT,
                          parse_mode="Markdown",
                          reply_markup=telegram_ui.main_menu_keyboard())
        except Exception:
            _send_message(chat_id, telegram_ui.HELP_TEXT, parse_mode="Markdown",
                          reply_markup=telegram_ui.main_menu_keyboard())
        return
    if action == "settings":
        try:
            _edit_message(chat_id, message_id, telegram_ui.SETTINGS_TEXT,
                          parse_mode="Markdown",
                          reply_markup=telegram_ui.main_menu_keyboard())
        except Exception:
            _send_message(chat_id, telegram_ui.SETTINGS_TEXT, parse_mode="Markdown",
                          reply_markup=telegram_ui.main_menu_keyboard())
        return
    if action == "changelog":
        try:
            _edit_message(chat_id, message_id, telegram_ui.CHANGELOG_TEXT,
                          parse_mode="Markdown",
                          reply_markup=telegram_ui.main_menu_keyboard())
        except Exception:
            _send_message(chat_id, telegram_ui.CHANGELOG_TEXT, parse_mode="Markdown",
                          reply_markup=telegram_ui.main_menu_keyboard())
        return
    log.warning(f"Unknown main menu action: {data!r}")


def _handle_hunt_review_callback(chat_id: int, message_id: int, data: str) -> None:
    """v6.7: dispatch hunt:start, hunt:cancel, hunt:edit:<key>, hunt:set:<key>:<v>,
    hunt:back_to_review, hunt:rq:<id>, hunt:back_to_packages.
    """
    from hunt_intake import (
        get_intake_answers, cancel_intake, go_to_step,
        record_intake_answer, is_intake_complete,
    )
    parts = data.split(":", 2)
    action = parts[1] if len(parts) > 1 else ""

    if action == "start":
        # User confirmed — show the RQ package picker (in background thread).
        log.info(f"Chat {chat_id}: hunt:start callback received — kicking off background thread")
        try:
            _edit_message(chat_id, message_id, "🚀 *Starting your hunt...*\n\n_Preparing RQ packages..._",
                          parse_mode="Markdown")
        except Exception as e:
            log.warning(f"hunt:start edit_message failed: {e}")
            _send_message(chat_id, "🚀 *Starting your hunt...*\n\n_Preparing RQ packages..._",
                          parse_mode="Markdown")
        import threading
        thread = threading.Thread(
            target=_safe_start_hunt_from_review,
            args=(chat_id,),
            daemon=True,
        )
        thread.start()
        return

    if action == "rq":
        # hunt:rq:<id> — user picked an RQ package. Spawn a thread to run it.
        package_id = parts[2] if len(parts) > 2 else ""
        log.info(f"Chat {chat_id}: hunt:rq:{package_id} picked")
        try:
            _edit_message(chat_id, message_id,
                          f"⏳ *Setting up the hunt with Package "
                          f"{package_id}...*",
                          parse_mode="Markdown")
        except Exception:
            pass
        import threading
        thread = threading.Thread(
            target=_safe_rq_package_picked,
            args=(chat_id, package_id),
            daemon=True,
        )
        thread.start()
        return

    if action == "back_to_packages":
        # Re-show the RQ package picker (use the packages stashed in state)
        state = load_chat_state(chat_id) or {}
        packages = state.get("hunt_v2_rq_packages") or []
        if not packages:
            _edit_message(chat_id, message_id,
                          "⚠️ Packages expired. Tap *Start the hunt* again.",
                          parse_mode="Markdown")
            return
        from rq_packages import format_packages_picker, packages_picker_keyboard
        text = format_packages_picker(packages)
        kb = packages_picker_keyboard()
        try:
            _edit_message(chat_id, message_id, text,
                          parse_mode="Markdown", reply_markup=kb)
        except Exception:
            _send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)
        return

    if action == "cancel":
        # Cancel clears everything and returns to main menu
        cancel_intake(chat_id)
        state = load_chat_state(chat_id) or {}
        for k in list(state.keys()):
            if k.startswith("hunt_intake_") or k.startswith("hunt_v2_"):
                if k != "hunt_v2_history":  # keep history for /reports
                    state.pop(k, None)
        save_chat_state(chat_id, state)
        try:
            _edit_message(chat_id, message_id,
                          "❌ *Hunt cancelled.*\n\n"
                          "Tap a button on the main menu to start again.",
                          parse_mode="Markdown",
                          reply_markup=telegram_ui.main_menu_keyboard())
        except Exception:
            _send_message(chat_id,
                           "❌ *Hunt cancelled.*\n\nTap /start to begin again.",
                           parse_mode="Markdown",
                           reply_markup=telegram_ui.main_menu_keyboard())
        return

    if action == "back_to_review":
        answers = get_intake_answers(chat_id)
        text, kb = telegram_ui.build_review_screen(answers)
        try:
            _edit_message(chat_id, message_id, text, parse_mode="Markdown",
                          reply_markup=kb)
        except Exception:
            _send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)
        return

    if action == "edit":
        # hunt:edit:<key> — go back to that step
        key = parts[2] if len(parts) > 2 else ""
        if not key:
            return
        go_to_step(chat_id, key)
        _show_hunt_intake_step(chat_id)
        try:
            _edit_message(chat_id, message_id,
                          f"✏️ *Editing step: {key}*\n\n"
                          f"Re-enter your answer below (or tap Skip for default).",
                          parse_mode="Markdown")
        except Exception:
            _send_message(chat_id,
                           f"✏️ *Editing step: {key}*\n\n"
                           f"Re-enter your answer below (or tap Skip for default).",
                           parse_mode="Markdown")
        return

    if action == "set":
        # hunt:set:<key>:<value> — option-based edit (records value, returns to review)
        # parts[2] is "<key>:<value>"
        if len(parts) < 3:
            return
        kv = parts[2].split(":", 1)
        if len(kv) != 2:
            return
        key, value = kv
        # Set the editing flag so the next record_intake_answer goes back to review
        state = load_chat_state(chat_id) or {}
        state["hunt_intake_editing"] = True
        save_chat_state(chat_id, state)
        record_intake_answer(chat_id, value, via="edit_set")
        # After recording, jump back to the review screen
        answers = get_intake_answers(chat_id)
        text, kb = telegram_ui.build_review_screen(answers)
        try:
            _edit_message(chat_id, message_id, text, parse_mode="Markdown",
                          reply_markup=kb)
        except Exception:
            _send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)
        return

    log.warning(f"Unknown hunt review action: {data!r}")


def _safe_rq_package_picked(chat_id: int, package_id: str) -> None:
    """Thread wrapper around _on_rq_package_picked."""
    log.info(f"_safe_rq_package_picked: thread for chat {chat_id}, pkg={package_id!r}")
    try:
        _on_rq_package_picked(chat_id, package_id)
    except Exception as e:
        import traceback
        log.error(f"_safe_rq_package_picked crashed: {e}\n{traceback.format_exc()}")
        try:
            _send_message(chat_id, f"⚠️ Could not run with that package: `{e}`",
                          parse_mode="Markdown")
        except Exception:
            pass


def _handle_wizard_text(chat_id: int, text: str) -> None:
    """Process free-text answer during the wizard."""
    state = load_chapter_state(chat_id) or {}
    step = get_current_step(state)
    if not step:
        cancel_wizard(chat_id)
        _send_message(chat_id, "❌ Wizard state lost. Send /start to begin again.")
        return
    # "Skip" can also be sent as text
    if text.lower() in ("skip", "/skip", "⏭", "⏭ skip"):
        state = skip_step(chat_id)
        _show_step(chat_id, None, state)
        return
    state = record_answer(chat_id, step["key"], text)
    _show_step(chat_id, None, state)


def _show_step(chat_id: int, message_id: Optional[int], state: Dict[str, Any]) -> None:
    """Display the current wizard step (or completion)."""
    if state.get("wizard_complete"):
        answers = state.get("answers", {})
        _on_wizard_complete(chat_id, answers)
        return
    step = get_current_step(state)
    if not step:
        cancel_wizard(chat_id)
        if message_id:
            _edit_message(chat_id, message_id, "❌ Wizard error. Send /start to try again.")
        else:
            _send_message(chat_id, "❌ Wizard error. Send /start to try again.")
        return
    kb = _keyboard_for_step(step)
    if message_id:
        _edit_message(chat_id, message_id, step["prompt"], reply_markup=kb)
    else:
        _send_message(chat_id, step["prompt"], reply_markup=kb)


def _on_wizard_complete(chat_id: int, answers: Dict[str, Any]) -> None:
    """What to do when the user finishes the 7-step wizard."""
    chapter_name = answers.get("chapter_name") or "Untitled_Chapter"
    research_type = answers.get("research_type") or "MA"
    title = answers.get("title") or ""
    text = (
        f"✅ *Wizard complete!*\n\n"
        f"📖 Chapter: *{chapter_name}*\n"
        f"📚 Type: *{RESEARCH_TYPES.get(research_type, {}).get('label', research_type)}*\n"
    )
    if title:
        text += f"🔖 Title: *{title}*\n"
    text += "\n🚀 Creating your Drive folder + Sheet, then I'll search for matching references..."
    _send_message(chat_id, text, reply_markup=_keyboard_after_complete())

    # Create Drive folder + Sheet (async-safe fire-and-forget)
    folder_id = gdrive.create_drive_folder(chapter_name)
    if folder_id:
        save_chapter_state(chat_id, {"drive_folder_id": folder_id})

    # If user gave a title, do a precision search
    if title:
        _send_message(chat_id, f"🔍 Searching 70+ platforms for *{title}*...", parse_mode="Markdown")
        try:
            papers = precision_search(title, threshold=0.85)
        except Exception as e:
            log.error(f"precision_search failed: {e}")
            papers = []
        if papers:
            result = telegram_send_rich_result_w(chat_id, papers)
            _send_message(chat_id, result.get("text", ""))
            sheet_url = gdrive.create_doi_sheet(chapter_name, papers)
            if sheet_url:
                _send_message(chat_id, f"📊 Sheet created: {sheet_url}")
        else:
            _send_message(chat_id, "❌ No papers matched the title at 99% precision. Try /find with a different query.")


def _handle_document(chat_id: int, document: Dict[str, Any]) -> None:
    """Handle uploaded file (PDF/DOCX/ODX/TXT)."""
    file_id = document.get("file_id")
    file_name = document.get("file_name", "upload")
    if not file_id:
        return
    _send_message(chat_id, f"📎 Received *{file_name}*. Downloading...", parse_mode="Markdown")
    local = _download_telegram_file(file_id)
    if not local:
        _send_message(chat_id, "❌ Download failed. Please try again.")
        return
    # Save into a study dir keyed by chat_id
    state = load_chapter_state(chat_id) or {}
    chapter_name = state.get("answers", {}).get("chapter_name") or os.path.splitext(file_name)[0]
    study_dir = os.path.join(os.environ.get("LIT_REVIEW_DOWNLOADS", "/tmp/lit_downloads"), str(chat_id), chapter_name)
    os.makedirs(study_dir, exist_ok=True)
    target = os.path.join(study_dir, file_name)
    shutil.copy2(local, target)
    # Try to parse + verify
    _send_message(chat_id, f"🔬 Parsing *{file_name}* for references...", parse_mode="Markdown")
    try:
        result = verify_chapter_upload(target, chapter_name, max_refs=35)
        n_verified = len(result.get("verified", []))
        n_missing = len(result.get("not_found", []))
        n_refs = result.get("reference_list_count", 0)
        text = (
            f"✅ *Done.*\n\n"
            f"📖 Chapter: *{chapter_name}*\n"
            f"📚 References found: *{n_refs}*\n"
            f"✅ Verified: *{n_verified}*\n"
            f"❌ Not found: *{n_missing}*\n"
        )
        _send_message(chat_id, text, reply_markup=_keyboard_after_complete())
        # Send rich result card
        if result.get("verified"):
            rich = telegram_send_rich_result_w(chat_id, result["verified"])
            _send_message(chat_id, rich.get("text", ""), parse_mode="Markdown")
    except Exception as e:
        log.error(f"verify_chapter_upload failed: {e}")
        _send_message(chat_id, f"❌ Parsing/verification failed: {e}")


def _handle_natural_language(chat_id: int, text: str) -> None:
    """Fallback: ask ollama what the user wants."""
    prompt = DETECT_INTENT_PROMPT.format(message=text[:500])
    raw = _call_ollama(prompt)
    intent = "unknown"
    try:
        import re
        m = re.search(r'"intent"\s*:\s*"(\w+)"', raw)
        if m:
            intent = m.group(1)
    except Exception:
        pass
    if intent in ("search", "find"):
        _cmd_find(chat_id, text)
    elif intent == "upload":
        _send_message(chat_id, "📎 Send me your chapter file (PDF, DOCX, ODT, or TXT).")
    elif intent == "status":
        _cmd_status(chat_id)
    elif intent == "sheet":
        _cmd_sheet(chat_id)
    elif intent == "help":
        _cmd_help(chat_id)
    elif intent == "cancel":
        cancel_wizard(chat_id)
        _send_message(chat_id, "🗑 Reset. Send /start to begin again.")
    else:
        _send_message(chat_id, "🤔 I didn't understand. Try /help for commands.")


# ============================================================================
# Commands
# ============================================================================

def _cmd_start(chat_id: int) -> None:
    """v6.6 rich welcome + main menu (no auto-wizard)."""
    _send_message(chat_id, telegram_ui.MAIN_MENU_TEXT, parse_mode="Markdown",
                  reply_markup=telegram_ui.main_menu_keyboard())


def _cmd_reports(chat_id: int, message_id: Optional[int] = None) -> None:
    """List past hunts (the 'My Reports' main-menu button).

    Reads from a JSON index file in the state's reports directory.
    Falls back to scanning the local downloads folder for hunt outputs.
    """
    reports: List[Dict[str, Any]] = []
    try:
        # 1) Try a state-side reports index
        index_path = os.path.join(
            os.environ.get("LIT_REVIEW_STATE_DIR", "/tmp/telegram_state"),
            f"reports_{chat_id}.json",
        )
        if os.path.isfile(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                reports = json.load(f) or []
    except Exception as e:
        log.warning(f"_cmd_reports: failed to read index: {e}")

    if not reports:
        # 2) Fall back to scanning the local downloads folder
        try:
            dl_root = os.environ.get("LIT_REVIEW_DOWNLOADS", "/tmp/lit_downloads")
            user_dir = os.path.join(dl_root, str(chat_id))
            if os.path.isdir(user_dir):
                # Each subfolder is a hunt
                for entry in sorted(os.listdir(user_dir), reverse=True)[:20]:
                    sub = os.path.join(user_dir, entry)
                    if not os.path.isdir(sub):
                        continue
                    meta = _read_hunt_meta(sub)
                    reports.append({
                        "title": entry,
                        "date": meta.get("date", "?"),
                        "total_papers": meta.get("total_papers", 0),
                        "downloaded": meta.get("downloaded", 0),
                        "drive_url": meta.get("drive_url", ""),
                        "output_folder": sub,
                    })
        except Exception as e:
            log.warning(f"_cmd_reports: scan failed: {e}")

    text, kb = telegram_ui.build_reports_list(reports)
    if message_id:
        try:
            _edit_message(chat_id, message_id, text, parse_mode="Markdown",
                          reply_markup=kb)
            return
        except Exception:
            pass
    _send_message(chat_id, text, parse_mode="Markdown", reply_markup=kb)


def _read_hunt_meta(hunt_folder: str) -> Dict[str, Any]:
    """Read hunt metadata from a hunt output folder, if any."""
    meta: Dict[str, Any] = {}
    try:
        meta_path = os.path.join(hunt_folder, "hunt_meta.json")
        if os.path.isfile(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f) or {}
    except Exception as e:
        log.warning(f"_read_hunt_meta({hunt_folder}) failed: {e}")
    # If no meta, try to derive from files
    if not meta:
        try:
            files = os.listdir(hunt_folder)
            meta["date"] = time.strftime(
                "%Y-%m-%d",
                time.localtime(os.path.getmtime(hunt_folder)),
            )
            meta["total_papers"] = sum(
                1 for f in files if f.lower().endswith((".pdf", ".xlsx", ".md"))
            )
        except Exception:
            pass
    return meta


def _cmd_find(chat_id: int, query: str) -> None:
    progress_msg = _send_message(chat_id, f"🔍 Searching for *{query}*...", parse_mode="Markdown")
    try:
        # First try strict 0.85 threshold (the "verified" tier)
        papers = precision_search(query, threshold=0.85)
        # If none, fall back to a relaxed 0.50 threshold so the user gets
        # SOMETHING. We mark them as "candidates" rather than "verified".
        candidates = []
        if not papers:
            log.info(f"_cmd_find: no papers >= 0.85, falling back to threshold=0.50")
            candidates = precision_search(query, threshold=0.50)
            if candidates:
                for c in candidates:
                    c["match_uncertain"] = True  # flag as not strictly verified
        log.info(f"_cmd_find: query={query!r} verified={len(papers)} candidates={len(candidates)}")
    except Exception as e:
        log.error(f"_cmd_find failed: {e}")
        papers = []
        candidates = []
    if progress_msg:
        _edit_message(
            chat_id, progress_msg,
            f"✅ Found *{len(papers)}* verified matches"
            + (f" + *{len(candidates)}* candidates" if candidates else "")
            + ".",
            parse_mode="Markdown",
        )
    if not papers and not candidates:
        _send_message(
            chat_id,
            "❌ No matches at 99% precision. Try a different query or include more "
            "context (author + year + journal).",
        )
        return
    rich = telegram_send_rich_result_w(chat_id, papers if papers else candidates)
    _send_message(chat_id, rich.get("text", ""), parse_mode="Markdown",
                  reply_markup=_keyboard_after_complete())


def _cmd_verify(chat_id: int, text: str) -> None:
    """Verify all references in a Drive file.

    Usage:
        /verify                      — verify every file in the default Drive folder
        /verify <drive_file_id>      — verify one specific file by its Drive ID
        /verify <drive_url>          — verify one file by its Drive URL

    The bot downloads the file, extracts reference entries, looks each one up
    via v2-4 (70+ platforms + ollama), then writes a Google Sheet with the
    verification report. Sends the Sheet URL back to the user.
    """
    # Default folder for references (created via `create_drive_folder('Reference Library ...')`).
    # Can be overridden by an env var VERIFY_DEFAULT_FOLDER_ID for portability.
    DEFAULT_FOLDER = os.environ.get(
        "VERIFY_DEFAULT_FOLDER_ID",
        "1OGRIBJ5qDWQ0uG2W926WhJkbN3ltxf2H",  # the folder we just created
    )

    parts = text.split(maxsplit=1)
    target = parts[1].strip() if len(parts) > 1 else ""

    # Extract file_id from a URL or accept the bare ID
    file_id = _extract_drive_file_id(target) if target else None

    files_to_verify: list[tuple[str, str]] = []  # (file_id, file_name)
    if file_id:
        # Single file mode
        try:
            files_to_verify = [(file_id, _drive_get_name(file_id))]
        except Exception:
            _send_message(chat_id, f"❌ Could not access Drive file `{file_id}`. Check the ID/URL.")
            return
    else:
        # Folder mode: list every file in the default folder
        try:
            files_to_verify = [(f["id"], f["name"]) for f in gdrive.list_files_in_folder(DEFAULT_FOLDER)]
        except Exception as e:
            log.error(f"list_files_in_folder failed: {e}")
            files_to_verify = []
        if not files_to_verify:
            _send_message(
                chat_id,
                "❌ No reference files found in the default Drive folder.\n"
                f"Upload your references to folder `1OGRIBJ5qDWQ0uG2W926WhJkbN3ltxf2H` "
                "(or set VERIFY_DEFAULT_FOLDER_ID) and try again.",
            )
            return

    _send_message(
        chat_id,
        f"🔍 Verifying *{len(files_to_verify)}* file(s) from Google Drive...\n"
        "This may take several minutes (v2-4 + ollama scoring).",
        parse_mode="Markdown",
    )

    # Local download dir
    download_dir = os.environ.get("LIT_DOWNLOADS", "/tmp/lit_verify")
    os.makedirs(download_dir, exist_ok=True)

    all_verified: list[dict] = []
    all_not_found: list[str] = []
    all_errors: list[str] = []

    for fid, fname in files_to_verify:
        # 1) Download from Drive
        local = os.path.join(download_dir, fname)
        got = gdrive.download_from_drive(fid, local)
        if not got or not os.path.exists(local):
            all_errors.append(f"{fname}: download failed")
            continue
        # 2) Parse references
        try:
            parsed = parse_chapter_references(local)
        except Exception as e:
            all_errors.append(f"{fname}: parse failed: {e}")
            continue
        ref_list = parsed.get("reference_list", [])
        if not ref_list:
            all_errors.append(f"{fname}: no references found in document")
            continue
        # 3) Verify each one (cap at 5 to stay within the GHA cron budget — 5 refs * ~2 min = 10 min)
        for ref in ref_list[:5]:
            try:
                res = verify_one_reference(ref, chapter_name=fname)
                all_verified.extend(res.get("verified", []))
                all_not_found.extend(res.get("not_found", []))
                for err in res.get("errors", []):
                    all_errors.append(f"{fname}: {err}")
            except Exception as e:
                all_errors.append(f"{fname}: verify failed: {e}")

    # 4) Build a Google Sheet with the results
    sheet_url = gdrive.create_doi_sheet("Verify Report", all_verified)
    drive_url = f"https://drive.google.com/drive/folders/{DEFAULT_FOLDER}"

    summary = (
        f"✅ *Verification complete*\n\n"
        f"📄 Files scanned: *{len(files_to_verify)}*\n"
        f"📚 References verified: *{len(all_verified)}*\n"
        f"❌ Not found: *{len(all_not_found)}*\n"
        f"⚠️  Errors: *{len(all_errors)}*\n"
    )
    if sheet_url:
        summary += f"\n📊 [Verification Sheet]({sheet_url})\n"
    summary += f"📁 [Drive Folder]({drive_url})\n"

    # Telegram messages have a 4096-char limit. Send the summary first, then
    # the first few not-found/errors as follow-ups.
    _send_message(chat_id, summary, parse_mode="Markdown", disable_web_page_preview=True)
    if all_not_found:
        lines = ["*Not found (first 10):*"] + [f"• {x[:200]}" for x in all_not_found[:10]]
        _send_message(chat_id, "\n".join(lines), parse_mode="Markdown")
    if all_errors:
        lines = ["*Errors (first 5):*"] + [f"• {x[:200]}" for x in all_errors[:5]]
        _send_message(chat_id, "\n".join(lines), parse_mode="Markdown")


def _extract_drive_file_id(s: str) -> Optional[str]:
    """Parse a Drive file ID out of a URL or accept the bare ID."""
    s = (s or "").strip()
    if not s:
        return None
    # URL forms: https://drive.google.com/file/d/<id>/view, ?id=<id>, /d/<id>/
    m = re.search(r"/file/d/([a-zA-Z0-9_-]{10,})", s)
    if m:
        return m.group(1)
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]{10,})", s)
    if m:
        return m.group(1)
    m = re.search(r"/d/([a-zA-Z0-9_-]{10,})", s)
    if m:
        return m.group(1)
    if re.match(r"^[a-zA-Z0-9_-]{10,}$", s):
        return s
    return None


def _drive_get_name(file_id: str) -> str:
    """Get a Drive file's name (for log/display). Returns the ID if lookup fails."""
    try:
        svc = gdrive._get_drive_service()
        if not svc:
            return file_id
        meta = svc.files().get(fileId=file_id, fields="name").execute()
        return meta.get("name", file_id)
    except Exception:
        return file_id


def _cmd_listrefs(chat_id: int) -> None:
    """List reference files in the default Drive folder."""
    folder_id = os.environ.get(
        "VERIFY_DEFAULT_FOLDER_ID",
        "1OGRIBJ5qDWQ0uG2W926WhJkbN3ltxf2H",
    )
    files = gdrive.list_files_in_folder(folder_id)
    if not files:
        _send_message(
            chat_id,
            f"❌ No files in folder `{folder_id}`.\n"
            f"Upload references to the folder, then try again.",
        )
        return
    lines = [f"📁 *Reference files in Drive ({len(files)}):*"]
    for f in files:
        lines.append(f"• `{f['id'][:24]}…` {f['name']}")
    lines.append(f"\nRun `/verify` to verify all, or `/verify <id>` for one file.")
    _send_message(chat_id, "\n".join(lines), parse_mode="Markdown")


def _cmd_sheet(chat_id: int) -> None:
    state = load_chapter_state(chat_id) or {}
    sheet_url = state.get("sheet_url")
    if sheet_url:
        _send_message(chat_id, f"📊 Your Sheet: {sheet_url}")
    else:
        _send_message(chat_id, "❌ No sheet yet. Run the wizard first (/start) or /find a paper.")


def _cmd_status(chat_id: int) -> None:
    state = load_chapter_state(chat_id) or {}
    chat_state = load_chat_state(chat_id) or {}
    answers = state.get("answers", {})
    chapter = answers.get("chapter_name") or "(not set)"
    rtype = answers.get("research_type") or "(not set)"

    # Hunt v2 (intake) state
    hunt_intake_active = chat_state.get("hunt_intake_active", False)
    hunt_intake_complete = chat_state.get("hunt_intake_complete", False)
    hunt_v2_running = chat_state.get("hunt_v2_running", False)
    hunt_v2_started = chat_state.get("hunt_v2_started_at", 0)
    hunt_v2_finished = chat_state.get("hunt_v2_finished_at", 0)
    hunt_v2_last = chat_state.get("hunt_v2_last_result", {})
    now = __import__("time").time()
    elapsed = (now - hunt_v2_started) / 60 if hunt_v2_started else 0

    text = (
        f"📊 *Status:*\n\n"
        f"📖 Chapter wizard: type=*{rtype}*, chapter=*{chapter}*\n"
        f"🔄 Wizard active: *{state.get('wizard_active', False)}*, "
        f"complete: *{state.get('wizard_complete', False)}*\n"
    )

    # Hunt intake / running status
    if hunt_intake_active:
        from hunt_intake import intake_progress_text
        text += "\n📝 *Hunt intake in progress:*\n" + intake_progress_text(chat_id) + "\n"
    elif hunt_v2_running:
        text += (
            f"\n🚀 *Hunt RUNNING* — {elapsed:.0f} min elapsed\n"
            f"   Send /cancel to stop.\n"
        )
    elif hunt_v2_last:
        if hunt_v2_last.get("success"):
            text += (
                f"\n✅ *Last hunt finished* "
                f"({(hunt_v2_finished - hunt_v2_started) / 60:.0f} min):\n"
                f"   Papers: *{hunt_v2_last.get('total_papers', 0)}*\n"
                f"   PDFs: *{hunt_v2_last.get('downloaded', 0)}*\n"
                f"   Red list: *{hunt_v2_last.get('red_list_count', 0)}*\n"
                f"   Folder: `{hunt_v2_last.get('output_folder', '')}`\n"
            )
        else:
            text += f"\n❌ *Last hunt failed:* `{hunt_v2_last.get('error', '?')[:200]}`\n"

    # verifyrefs state
    if chat_state.get("mode") == "verifyrefs":
        text += f"\n📋 *Verify-refs mode active* — step: `{chat_state.get('step', '?')}`\n"

    text += f"\n🆔 State version: *{state.get('_version', 0)}*\n"
    _send_message(chat_id, text, parse_mode="Markdown")


def _cmd_drivesetup(chat_id: int) -> None:
    """Diagnose Google Drive setup and guide the user through fixes.

    Checks (in order):
      1. Service account file present? (proves working for opp-hunter-v2 etc.)
      2. OAuth refresh token + client_id/secret? (proves upload works)
      3. Live test: can we actually upload a tiny file?

    Surfaces a step-by-step fix with Google Cloud Console links.
    """
    try:
        import google_integration
    except Exception as e:
        _send_message(chat_id, f"❌ Cannot import google_integration: {e}")
        return

    status = google_integration.get_credential_status()

    # --- Part 1: Status summary ---
    sa = status["service_account"]
    oauth = status["oauth_refresh"]

    sa_line = ("✅ Service account ready" if sa["present"]
               else "❌ No service account file found")
    sa_email = f"`{sa['client_email']}`" if sa["client_email"] else "_(unknown)_"
    sa_path = f"`{sa['path']}`" if sa["path"] else "_(not found)_"

    oauth_line_parts = []
    if oauth["present"]:
        oauth_line_parts.append("✅ refresh token")
    else:
        oauth_line_parts.append("❌ refresh token MISSING")
    if oauth["client_id_present"]:
        oauth_line_parts.append("✅ client_id")
    else:
        oauth_line_parts.append("❌ client_id MISSING")
    if oauth["client_secret_present"]:
        oauth_line_parts.append("✅ client_secret")
    else:
        oauth_line_parts.append("❌ client_secret MISSING")
    oauth_line = " · ".join(oauth_line_parts)

    text = (
        "🔧 *Google Drive Setup Diagnostics*\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 *Service account:* {sa_line}\n"
        f"   Email: {sa_email}\n"
        f"   Path: {sa_path}\n\n"
        f"🔑 *OAuth refresh token:* {oauth_line}\n"
    )
    _send_message(chat_id, text, parse_mode="Markdown")

    # --- Part 2: Live test ---
    _send_message(chat_id, "🧪 *Live test:* trying to upload a tiny file...",
                  parse_mode="Markdown")
    import tempfile, os
    test_content = f"literature-review-verifier setup test\nTimestamp: test\n"
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write(test_content)
        tmp = f.name
    target = "1NjsBcaAb1qtRUl4d7KHNhvfm159ei2C4"  # user's base folder
    try:
        url = google_integration.upload_to_drive(tmp, target, mime_type="text/plain")
        if url:
            _send_message(
                chat_id,
                f"✅ *Upload WORKS!*\n"
                f"🔗 [View test file in Drive]({url})\n\n"
                f"You can delete it; it was just a sanity check.",
                parse_mode="Markdown",
            )
        else:
            _send_message(chat_id,
                "❌ *Upload FAILED.*\n"
                "See the fix guide below ⬇️",
                parse_mode="Markdown")
            _send_drive_setup_wizard(chat_id)
    except Exception as e:
        _send_message(chat_id,
            f"❌ *Upload crashed:* `{e}`\n\nSee fix guide below ⬇️",
            parse_mode="Markdown")
        _send_drive_setup_wizard(chat_id)
    finally:
        try: os.unlink(tmp)
        except: pass


def _send_drive_setup_wizard(chat_id: int) -> None:
    """Walk the user through fixing Drive setup. Used by /drivesetup."""
    text = (
        "📋 *Fix Guide — pick ONE of these 3 paths:*\n\n"
        "*Path A — Use OAuth refresh token (RECOMMENDED, 2 min):*\n"
        "1. Open: https://console.cloud.google.com/apis/credentials?project=workspace-mcp-497516\n"
        "2. Find OAuth client `682807635139-...` (Workspace MCP)\n"
        "3. Re-run consent flow: https://developers.google.com/oauthplayground/\n"
        "   - Step 1: select `https://www.googleapis.com/auth/drive` + Sheets + Docs\n"
        "   - Step 2: exchange for tokens → copy the *refresh token*\n"
        "4. Paste the new refresh token into `with_env.bat` line 7\n"
        "5. Restart the bot\n\n"
        "*Path B — Use service account + DWD (4-5 min):*\n"
        "1. Open: https://admin.google.com/ac/owl/domainwidedelegation\n"
        "2. Add client ID `102218440405254480415`\n"
        "3. Scopes: `https://www.googleapis.com/auth/drive,spreadsheets,documents`\n"
        "4. Wait 5 min for cache to clear\n"
        "5. I will add `subject=wo312092@gmail.com` to the service account call\n\n"
        "*Path C — Use service account + Shared Drive (10 min):*\n"
        "1. Go to https://drive.google.com/drive/u/0/shareddrives\n"
        "2. Create a Shared Drive named 'Research Hunters'\n"
        "3. Share it with the service account `opportunity-hunter-bot@workspace-mcp-497516.iam.gserviceaccount.com` as Manager\n"
        "4. Tell me the Shared Drive ID; I will update the code to upload there\n\n"
        "💡 *Easiest:* Path A (if you still have the OAuth consent screen bookmark)\n"
        "   or reply 'DWD' and I'll enable domain-wide delegation in the code."
    )
    _send_message(chat_id, text, parse_mode="Markdown")


def _cmd_help(chat_id: int) -> None:
    sleep_status = "😴 (sleeping)" if _is_sleeping(chat_id) else "☀️ (awake)"
    text = (
        f"📖 *Commands:* {sleep_status}\n\n"
        "🚀 *Quick start:*\n"
        "`/hunt2 <your topic>` — guided 5-step intake, then auto-runs the full pipeline.\n"
        "Example: `/hunt2 machine learning in education`\n\n"
        "🔍 *Research Hunt (legacy):*\n"
        "/hunt <topic> - Fast path (skips questions, runs immediately)\n"
        "/hunt - Interactive hunt with research-type selection\n"
        "/research - Same as /hunt\n"
        "/find <title> - Quick paper search\n\n"
        "📋 *Reference Verification (list-driven):*\n"
        "/verifyrefs - Verify a list of references you provide\n"
        "  - Upload a PDF/DOCX/TXT with a reference list, OR\n"
        "  - Paste a numbered list as a message\n"
        "  - Bot searches 81 platforms, scores with AI, downloads PDFs\n"
        "  - Outputs color-coded Excel + professional DOCX report\n\n"
        "😴 *Sleep Mode:*\n"
        "/sleep - Enable passive monitoring (you rest, I watch)\n"
        "/wake - Wake up for full functionality\n\n"
        "📄 *Chapter Verification:*\n"
        "/upload - Upload a chapter file for verification\n"
        "/verify - Verify all references in Drive folder\n"
        "/verify <drive_url> - Verify one file\n"
        "/listrefs - List reference files\n\n"
        "📊 *Info:*\n"
        "/sheet - Get Google Sheet link\n"
        "/status - Show current state + last hunt result\n"
        "/start - Welcome + main menu\n"
        "/cancel - Cancel current wizard/intake\n"
        "/help - This message\n"
    )
    _send_message(chat_id, text, parse_mode="Markdown")


# ============================================================================
# /verifyrefs — Reference-list-driven verification
# ============================================================================

VERIFYREFS_STATES = {
    "awaiting_input",        # waiting for file or pasted list
    "awaiting_output_name",  # waiting for output folder name
    "awaiting_download_yn",  # waiting for yes/no on PDF download
    "running",               # pipeline running
}


def _cmd_verifyrefs(chat_id: int) -> None:
    """Start the reference-list verification wizard.

    User can either:
      - Send a file (PDF/DOCX/TXT) containing references
      - Paste a numbered list of references as a message
      - Send a folder path (advanced)
    """
    state = load_chat_state(chat_id) or {}
    state["mode"] = "verifyrefs"
    state["step"] = "awaiting_input"
    save_chat_state(chat_id, state)
    text = (
        "📋 *Reference Verification Mode*\n\n"
        "I will verify each reference by:\n"
        "  1️⃣ Searching 81 academic platforms (CrossRef, OpenAlex, PubMed, etc.)\n"
        "  2️⃣ Scoring matches with local AI (ollama)\n"
        "  3️⃣ Downloading PDFs for verified references (optional)\n"
        "  4️⃣ Generating a color-coded Excel + professional DOCX report\n\n"
        "*Status legend:*\n"
        "🟢 VERIFIED — high-confidence match (AI ≥85%)\n"
        "🟡 LIKELY — moderate match (60-85%)\n"
        "🔴 UNVERIFIED — candidates found but no strong match\n"
        "⛔ FAKE — no candidates found (likely fabricated)\n\n"
        "📎 *Send me one of:*\n"
        "  • A *PDF, DOCX, or TXT file* containing your reference list\n"
        "  • A *folder path* (e.g. `C:\\Users\\me\\refs`) — I'll scan all files\n"
        "  • A *pasted numbered list* — one ref per line, send `.` on its own line when done\n\n"
        "Or send /cancel to exit."
    )
    _send_message(chat_id, text, parse_mode="Markdown")


def _handle_verifyrefs_input(chat_id: int, text: str) -> None:
    """Handle the first input from the user (file, folder, or pasted list)."""
    state = load_chat_state(chat_id) or {}
    mode = state.get("mode")
    if mode != "verifyrefs" or state.get("step") != "awaiting_input":
        return
    text = text.strip()
    if not text:
        return

    # Check if it's a folder path
    if os.path.isdir(text):
        state["input_path"] = text
        state["input_kind"] = "folder"
    # Check if it's a single file
    elif os.path.isfile(text):
        ext = os.path.splitext(text)[1].lower()
        if ext not in (".pdf", ".docx", ".odt", ".txt", ".md"):
            _send_message(chat_id,
                          f"❌ Unsupported file type {ext!r}. Use PDF, DOCX, ODT, TXT, or MD.")
            return
        state["input_path"] = text
        state["input_kind"] = "file"
    else:
        # Treat as pasted list
        state["input_path"] = "PASTED:" + text
        state["input_kind"] = "pasted"

    state["step"] = "awaiting_output_name"
    save_chat_state(chat_id, state)
    _send_message(
        chat_id,
        "✅ Got it!\n\n📝 *Step 2/3:* What should I name the output folder? "
        "(This will be the Google Drive folder name too)\n\n"
        "Example: `My_Thesis_References`",
        parse_mode="Markdown",
    )


def _handle_verifyrefs_output_name(chat_id: int, text: str) -> None:
    """Step 2: ask for output folder name."""
    state = load_chat_state(chat_id) or {}
    if state.get("mode") != "verifyrefs" or state.get("step") != "awaiting_output_name":
        return
    name = _safe_name_for_drive(text.strip(), mx=60) or "Reference_Verification"
    state["output_name"] = name
    state["step"] = "awaiting_download_yn"
    save_chat_state(chat_id, state)
    _send_message(
        chat_id,
        f"📁 Output folder: *{name}*\n\n"
        f"📥 *Step 3/3:* Should I download PDFs for VERIFIED references?\n"
        f"(uses the 14-layer download chain — Unpaywall, OA.mg, Anna's Archive, etc.)\n\n"
        f"Reply `yes` (default) or `no`.",
        parse_mode="Markdown",
        reply_markup={
            "inline_keyboard": [
                [{"text": "✅ Yes, download PDFs", "callback_data": "vrefs:dl_yes"},
                 {"text": "❌ No, just verify", "callback_data": "vrefs:dl_no"}]
            ]
        },
    )


def _handle_verifyrefs_download(chat_id: int, download: bool) -> None:
    """Step 3: handle yes/no for PDF download and run the pipeline."""
    state = load_chat_state(chat_id) or {}
    if state.get("mode") != "verifyrefs" or state.get("step") != "awaiting_download_yn":
        return
    state["download_pdfs"] = bool(download)
    state["step"] = "running"
    save_chat_state(chat_id, state)

    input_path = state.get("input_path", "")
    output_name = state.get("output_name", "Reference_Verification")

    _send_message(
        chat_id,
        f"🚀 *Starting verification...*\n\n"
        f"📋 Input: `{state.get('input_kind', '?')}`\n"
        f"📁 Output: *{output_name}*\n"
        f"📥 PDF download: *{'yes' if download else 'no'}*\n\n"
        f"This may take a few minutes. I'll keep you updated.",
        parse_mode="Markdown",
    )

    # Run in a thread (so the bot stays responsive)
    import threading
    def _run():
        try:
            from verify_refs.orchestrator import run_verification
            result = run_verification(
                input_path=input_path,
                output_folder_name=output_name,
                base_output_dir=os.environ.get(
                    "LIT_REVIEW_DOWNLOADS",
                    os.path.join(os.path.dirname(__file__), "pdf_files")),
                download_pdfs=download,
            )
            _send_verifyrefs_result(chat_id, result)
        except Exception as e:
            log.error(f"verifyrefs pipeline failed: {e}")
            import traceback
            log.error(traceback.format_exc())
            _send_message(chat_id, f"❌ Pipeline failed: {e}")
        finally:
            clear_chat_state(chat_id)
    threading.Thread(target=_run, daemon=True).start()


def _handle_verifyrefs_document(chat_id: int, document: Dict[str, Any]) -> None:
    """Handle a file uploaded during verifyrefs mode (Step 1)."""
    file_id = document.get("file_id")
    file_name = document.get("file_name", "upload")
    ext = os.path.splitext(file_name)[1].lower()
    if not file_id:
        return
    if ext not in (".pdf", ".docx", ".odt", ".txt", ".md"):
        _send_message(chat_id,
                      f"❌ Unsupported file type {ext!r}. Use PDF, DOCX, ODT, TXT, or MD.")
        return
    _send_message(chat_id, f"📎 Received *{file_name}*. Downloading...", parse_mode="Markdown")
    local = _download_telegram_file(file_id)
    if not local:
        _send_message(chat_id, "❌ Download failed. Please try again.")
        return

    state = load_chat_state(chat_id) or {}
    state["input_path"] = local
    state["input_kind"] = "file"
    state["step"] = "awaiting_output_name"
    save_chat_state(chat_id, state)
    _send_message(
        chat_id,
        "✅ Got it!\n\n📝 *Step 2/3:* What should I name the output folder? "
        "(This will be the Google Drive folder name too)\n\n"
        "Example: `My_Thesis_References`",
        parse_mode="Markdown",
    )


def _handle_verifyrefs_callback(chat_id: int, message_id: int, data: str) -> None:
    """Handle inline keyboard callbacks for the verifyrefs wizard."""
    if data == "vrefs:dl_yes":
        _handle_verifyrefs_download(chat_id, True)
        _edit_message(chat_id, message_id, "✅ Starting verification with PDF download...")
    elif data == "vrefs:dl_no":
        _handle_verifyrefs_download(chat_id, False)
        _edit_message(chat_id, message_id, "✅ Starting verification (no PDF download)...")


def _send_verifyrefs_result(chat_id: int, result: Dict[str, Any]) -> None:
    """Send the verification results to the user."""
    if not result.get("success"):
        _send_message(chat_id, f"❌ Verification failed: {result.get('error', 'unknown')}")
        return
    counts = (
        f"VERIFIED: {result['verified']}\n"
        f"LIKELY: {result['likely']}\n"
        f"UNVERIFIED: {result['unverified']}\n"
        f"FAKE: {result['fake']}\n"
    )
    summary = (
        f"✅ *Verification complete!*\n\n"
        f"📚 Total references: *{result['total_refs']}*\n"
        f"🟢 {counts}"
        f"📥 PDFs downloaded: *{result['pdfs_downloaded']}*\n\n"
        f"📁 Output folder: `{os.path.basename(result['output_dir'])}`"
    )
    _send_message(chat_id, summary, parse_mode="Markdown")

    # Send the Excel report
    if result.get("excel_path") and os.path.exists(result["excel_path"]):
        _send_document(chat_id, result["excel_path"],
                       caption="📊 master_database_verifyrefs.xlsx (color-coded)")
    # Send the DOCX report
    if result.get("docx_path") and os.path.exists(result["docx_path"]):
        _send_document(chat_id, result["docx_path"],
                       caption="📄 literature_verification_report.docx (professional)")

    # Drive upload (if available)
    try:
        title = os.path.basename(result["output_dir"])
        upload = gdrive.upload_hunt_to_drive(result["output_dir"], title=title)
        if upload.get("folder_url"):
            _send_message(
                chat_id,
                f"☁️ *Uploaded to Google Drive:*\n{upload['folder_url']}\n\n"
                f"📁 Folders created: {upload.get('folders_created', 0)}\n"
                f"📎 Files uploaded: {upload.get('files_uploaded', 0)}",
                parse_mode="Markdown",
            )
    except Exception as e:
        log.warning(f"Drive upload skipped/failed: {e}")


def _send_document(chat_id: int, file_path: str, caption: str = "") -> bool:
    """Upload a local file to Telegram and send as document."""
    token = _get_token()
    if not token:
        log.warning("No Telegram token, skipping document send")
        return False
    try:
        url = TELEGRAM_API.format(token=token, method="sendDocument")
        with open(file_path, "rb") as f:
            files = {"document": (os.path.basename(file_path), f)}
            data = {"chat_id": str(chat_id), "caption": caption[:1024]}
            req = urllib.request.Request(
                url, data=data, files=files,
                method="POST")
            with urllib.request.urlopen(req, timeout=180) as r:
                resp = json.loads(r.read().decode("utf-8"))
                if not resp.get("ok"):
                    log.error(f"Telegram sendDocument failed: {resp}")
                    return False
        return True
    except Exception as e:
        log.error(f"_send_document failed: {e}")
        return False


# ============================================================================
# Long-polling loop (the GHA-friendly runner)
# ============================================================================

def run_once(timeout: int = 30) -> int:
    """Long-poll one batch of updates and process them. Returns count of messages handled."""
    # Check token first
    token = _get_token()
    if not token:
        log.warning("No Telegram token - skipping poll cycle")
        log.warning("To fix: Set TELEGRAM_BOT_TOKEN in GitHub Actions secrets")
        return 0
    
    resp = _tg_call("getUpdates", {"timeout": timeout, "allowed_updates": json.dumps(["message", "callback_query"])})
    if not resp.get("ok"):
        error = resp.get("error", "unknown error")
        log.error(f"getUpdates failed: {error}")
        # Check for common errors
        if "not found" in str(error).lower():
            log.error("Bot token may be invalid or expired!")
        elif "unauthorized" in str(error).lower():
            log.error("Bot token is unauthorized - check permissions")
        return 0
    updates = resp.get("result", [])
    log.info(f"getUpdates returned {len(updates)} update(s)")
    if not updates:
        return 0
    last_id = 0
    for upd in updates:
        try:
            log.info(f"processing update_id={upd.get('update_id')}")
            handle_message(upd)
        except Exception as e:
            log.error(f"handle_message failed: {e}", exc_info=True)
        last_id = max(last_id, upd.get("update_id", 0))
    if last_id:
        # Acknowledge processed updates
        _tg_call("getUpdates", {"offset": last_id + 1, "timeout": 0})
    return len(updates)


def main() -> None:
    log.info("Starting Search Sleeping Bot (long-polling mode)...")
    # v6.7: Start the stuck-detector watchdog in a background thread.
    # It monitors: heartbeat silence, duplicate messages, file locks.
    # If the bot appears stuck for > 90s, it logs an incident and
    # can self-heal (clear counters, mark heartbeat, etc.)
    try:
        from stuck_detector import StuckDetector, watchdog_loop
        _bot_detector = StuckDetector(
            log_path="D:/opencode/bot_stuck_incidents.jsonl",
            stuck_seconds=90,
        )
        _bot_detector.heartbeat("bot started")
        _watchdog_thread = threading.Thread(
            target=watchdog_loop,
            args=(_bot_detector, 30.0),
            daemon=True,
        )
        _watchdog_thread.start()
        log.info("Stuck-detector watchdog started (interval=30s, threshold=90s)")
    except Exception as e:
        log.warning(f"Could not start stuck-detector watchdog: {e}")

    while True:
        try:
            n = run_once(timeout=25)
            if n == 0:
                time.sleep(1)
            # Heartbeat every poll cycle so the watchdog knows we're alive
            try:
                if '_bot_detector' in dir():
                    _bot_detector.heartbeat(f"poll cycle, n={n}")
            except Exception:
                pass
        except KeyboardInterrupt:
            log.info("Bot stopped by user")
            break
        except Exception as e:
            log.error(f"Loop error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
