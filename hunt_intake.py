"""
hunt_intake.py — Unified multi-step intake for the /hunt command.

v6.7: 13 steps, each skippable (uses default if skipped):
  1.  research_type     - MA / PhD / RA / SR / general / etc.
  2.  title             - The hunt topic (or pre-filled from /hunt <title>)
  3.  field             - Academic discipline (education/medicine/...)
  4.  rq_angle          - Theoretical / Empirical / Applied / Methodological
  5.  research_questions - One per line, or "auto" / "skip" to auto-generate 3
  6.  year_range        - "any" / "2018-2024" / "2020" (default: any)
  7.  language          - English / Arabic / French / Any
  8.  country           - Libya / MENA / Africa / Worldwide / Any
  9.  paper_type        - Journal / Conference / Preprint / Thesis / All
  10. quartile_filter   - Q1 only / Q1+Q2 / Any
  11. open_access       - Yes (OA only) / No (any)
  12. platforms         - "all" / "tier1" / "tier12" (10 / 20 / 81 platforms)
  13. max_papers        - cap on results (default 1000)
  (14.) download_pdfs   - yes / no

State is stored via telegram_bot.save_chat_state / load_chat_state.
When all steps are answered, hunt_intake_complete = True and the
caller (telegram_bot._on_hunt_intake_complete) shows the review screen.
"""
from typing import Dict, Any, Optional, List
from logger import get_logger

log = get_logger("hunt_intake")

HUNT_STEPS: List[Dict[str, Any]] = [
    {
        "key": "research_type",
        "prompt": ("📚 *Step 1/13: Research type*\n\n"
                   "What type of work are you researching for?\n"
                   "(This helps me tailor the search and quartile check.)"),
        "options": [
            ("MA", "📘 MA Thesis"),
            ("PhD", "🎓 PhD Dissertation"),
            ("RA", "📰 Research Article"),
            ("SR", "🔍 Systematic Review"),
            ("EX", "🧪 Experimental Study"),
            ("CS", "📂 Case Study"),
            ("general", "🌐 General / Other"),
        ],
        "default": "general",
        "allow_skip": True,
    },
    {
        "key": "title",
        "prompt": ("🔖 *Step 2/13: Title / Topic*\n\n"
                   "What is the topic of your hunt?\n"
                   "_(e.g., 'machine learning in education' or "
                   "'Attention is all you need')_"),
        "allow_skip": False,
    },
    {
        "key": "field",
        "prompt": ("🎓 *Step 3/13: Field / discipline*\n\n"
                   "Which academic field is your topic in?\n"
                   "_(This picks the right platforms, journals, and quartile check.)_"),
        "options": [
            ("education",     "📚 Education"),
            ("medicine",      "🏥 Medicine / Health"),
            ("engineering",   "⚙️ Engineering"),
            ("computer_science", "💻 Computer Science / AI"),
            ("social_sciences","👥 Social Sciences"),
            ("humanities",    "📜 Humanities"),
            ("business",      "💼 Business / Management"),
            ("natural_sciences","🔬 Natural Sciences"),
            ("law",           "⚖️ Law"),
            ("arts",          "🎨 Arts / Design"),
            ("general",       "🌐 General / Interdisciplinary"),
        ],
        "default": "general",
        "allow_skip": True,
    },
    {
        "key": "rq_angle",
        "prompt": ("🧭 *Step 4/13: Research angle*\n\n"
                   "Which angle is your study approaching the topic from?\n"
                   "_(This drives the AI's RQ generation & search-query bias.)_"),
        "options": [
            ("theoretical",   "📘 Theoretical — concepts, frameworks, definitions"),
            ("empirical",     "🔬 Empirical — data, methods, measurements"),
            ("applied",       "🌍 Applied — real-world impact, policy, practice"),
            ("methodological","🛠 Methodological — new methods, comparisons"),
            ("comparative",   "🆚 Comparative — comparing countries/systems"),
            ("mixed",         "🌀 Mixed — combination of angles"),
        ],
        "default": "empirical",
        "allow_skip": True,
    },
    {
        "key": "research_questions",
        "prompt": ("❓ *Step 5/13: Research Questions*\n\n"
                   "How should I handle research questions?\n"
                   "_(I'll generate 3 RQ *packages* with different angles after "
                   "the intake. Pick the package you like, or type your own.)_"),
        "options": [
            ("auto",   "🧠 Auto — generate 3 packages, let me pick"),
            ("custom", "✍️ Custom — I'll type my own questions"),
        ],
        "default": "auto",
        "allow_skip": True,
    },
    {
        "key": "year_range",
        "prompt": ("📅 *Step 6/13: Year range*\n\n"
                   "Which years should I search?\n"
                   "_(Examples: '2020-2024', '2018', or just press Skip for any)_"),
        "default": "any",
        "allow_skip": True,
    },
    {
        "key": "language",
        "prompt": ("🌐 *Step 7/13: Language of papers*\n\n"
                   "Which language should the papers be in?"),
        "options": [
            ("en",    "🇬🇧 English"),
            ("ar",    "🇸🇦 Arabic"),
            ("fr",    "🇫🇷 French"),
            ("es",    "🇪🇸 Spanish"),
            ("de",    "🇩🇪 German"),
            ("zh",    "🇨🇳 Chinese"),
            ("any",   "🌍 Any / Multilingual"),
        ],
        "default": "en",
        "allow_skip": True,
    },
    {
        "key": "country",
        "prompt": ("🗺 *Step 8/13: Geographic focus*\n\n"
                   "Which region/countries should the study emphasize?\n"
                   "_(Filters & boosts region-specific repositories.)_"),
        "options": [
            ("libya",  "🇱🇾 Libya"),
            ("mena",   "🌍 MENA (Middle East & N. Africa)"),
            ("africa", "🌍 Africa"),
            ("arab",   "🌍 Arab world"),
            ("europe", "🇪🇺 Europe"),
            ("asia",   "🌏 Asia"),
            ("americas","🌎 Americas"),
            ("world",  "🌐 Worldwide / No filter"),
        ],
        "default": "world",
        "allow_skip": True,
    },
    {
        "key": "paper_type",
        "prompt": ("📄 *Step 9/13: Paper type*\n\n"
                   "Which types of papers should I look for?"),
        "options": [
            ("journal",    "📰 Journal articles"),
            ("conference", "🎤 Conference papers"),
            ("preprint",   "📝 Preprints (arXiv, SSRN, etc.)"),
            ("thesis",     "🎓 Theses & dissertations"),
            ("review",     "🔍 Review articles / Surveys"),
            ("all",        "🌐 All types"),
        ],
        "default": "all",
        "allow_skip": True,
    },
    {
        "key": "quartile_filter",
        "prompt": ("⭐ *Step 10/13: Quartile filter*\n\n"
                   "Should I limit by journal quartile (Scimago/JCR)?"),
        "options": [
            ("q1",    "⭐ Q1 only (top 25%)"),
            ("q1q2",  "⭐⭐ Q1 + Q2 (top 50%)"),
            ("any",   "🌐 Any quartile"),
        ],
        "default": "any",
        "allow_skip": True,
    },
    {
        "key": "open_access",
        "prompt": ("🔓 *Step 11/13: Open Access only?*\n\n"
                   "Should I restrict to open-access papers only?"),
        "options": [
            ("yes", "✅ Yes, open-access only"),
            ("no",  "🌐 Any access type"),
        ],
        "default": "no",
        "allow_skip": True,
    },
    {
        "key": "platforms",
        "prompt": ("🌐 *Step 12/13: Platforms*\n\n"
                   "Which platforms should I search?"),
        "options": [
            ("all", "🌍 All 81 platforms (best coverage, slowest)"),
            ("tier12", "⚡ Top 20 platforms (balanced speed + coverage)"),
            ("tier1", "🚀 Tier 1 only (10 platforms, fastest)"),
        ],
        "default": "all",
        "allow_skip": True,
    },
    {
        "key": "max_papers",
        "prompt": ("📄 *Step 13/13: Max papers*\n\n"
                   "How many papers should I aim to find?\n"
                   "_(Default: 1000. Type 0 or 'deep' for no cap. "
                   "5000 papers = 30-90 min on deep search.)_"),
        "default": "1000",
        "allow_skip": True,
    },
    {
        "key": "download_pdfs",
        "prompt": ("📥 *Step 14/14: Download PDFs?*\n\n"
                   "Should I download PDFs for the papers I find?\n"
                   "_(Takes 10-30 min extra, depends on availability)_"),
        "options": [
            ("yes", "✅ Yes, download PDFs"),
            ("no", "❌ No, just find papers"),
        ],
        "default": "yes",
        "allow_skip": True,
    },
]


def _get_state_funcs():
    """Lazy import to avoid circular dependency."""
    from telegram_bot import load_chat_state, save_chat_state
    return load_chat_state, save_chat_state


def start_hunt_intake(chat_id: int, prefill: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Start a fresh hunt intake. Optionally pre-fill some answers (e.g. title)."""
    load_fn, save_fn = _get_state_funcs()
    state = load_fn(chat_id) or {}
    state["hunt_intake_active"] = True
    state["hunt_intake_step"] = 0
    state["hunt_intake_answers"] = dict(prefill or {})
    state["hunt_intake_started_at"] = __import__("time").time()
    save_fn(chat_id, state)
    log.info(f"Started hunt intake for chat {chat_id}, prefill={list((prefill or {}).keys())}")
    return state


def get_intake_state(chat_id: int) -> Optional[Dict[str, Any]]:
    """Get the current intake state (or None if no active intake)."""
    load_fn, _ = _get_state_funcs()
    state = load_fn(chat_id) or {}
    if not state.get("hunt_intake_active") and not state.get("hunt_intake_complete"):
        return None
    return state


def is_intake_active(chat_id: int) -> bool:
    state = get_intake_state(chat_id)
    return bool(state and state.get("hunt_intake_active"))


def is_intake_complete(chat_id: int) -> bool:
    state = get_intake_state(chat_id)
    return bool(state and state.get("hunt_intake_complete"))


def get_current_intake_step(chat_id: int) -> Optional[Dict[str, Any]]:
    """Return the current step definition (or None if intake is complete)."""
    state = get_intake_state(chat_id)
    if not state or not state.get("hunt_intake_active"):
        return None
    step_idx = state.get("hunt_intake_step", 0)
    if step_idx < 0 or step_idx >= len(HUNT_STEPS):
        return None
    return dict(HUNT_STEPS[step_idx], _index=step_idx, _total=len(HUNT_STEPS))


def record_intake_answer(chat_id: int, value: Any, via: str = "text") -> Dict[str, Any]:
    """Record answer for the current step and advance. Returns the new state."""
    load_fn, save_fn = _get_state_funcs()
    state = load_fn(chat_id) or {}
    if not state.get("hunt_intake_active"):
        return state
    step_idx = state.get("hunt_intake_step", 0)
    if step_idx >= len(HUNT_STEPS):
        return state
    step = HUNT_STEPS[step_idx]
    # Normalize value
    if isinstance(value, str):
        value = value.strip()
    state.setdefault("hunt_intake_answers", {})[step["key"]] = value
    # If user is in the Edit flow (came from go_to_step), record the new
    # value for that step, then mark the intake complete again so they
    # land on the Review screen — no need to re-answer later steps.
    if state.pop("hunt_intake_editing", None):
        state["hunt_intake_step"] = len(HUNT_STEPS)  # end of intake
        state["hunt_intake_active"] = False
        state["hunt_intake_complete"] = True
        state["hunt_intake_completed_at"] = __import__("time").time()
        state["hunt_intake_return_to_review"] = True
    else:
        state["hunt_intake_step"] = step_idx + 1
        if state["hunt_intake_step"] >= len(HUNT_STEPS):
            state["hunt_intake_active"] = False
            state["hunt_intake_complete"] = True
            state["hunt_intake_completed_at"] = __import__("time").time()
    save_fn(chat_id, state)
    log.info(f"Chat {chat_id} answered {step['key']!r}={str(value)[:50]!r} (via {via}), "
             f"step now {state['hunt_intake_step']}")
    return state


def skip_intake_step(chat_id: int, via: str = "button") -> Dict[str, Any]:
    """Skip the current step (uses default if available)."""
    step = get_current_intake_step(chat_id)
    if not step:
        return get_intake_state(chat_id) or {}
    if not step.get("allow_skip"):
        log.info(f"Cannot skip required step {step['key']!r}")
        return get_intake_state(chat_id) or {}
    default = step.get("default")
    return record_intake_answer(chat_id, default, via=via)


def get_step_index(key: str) -> Optional[int]:
    """Return the index of a step in HUNT_STEPS by its key, or None."""
    for i, s in enumerate(HUNT_STEPS):
        if s["key"] == key:
            return i
    return None


def go_to_step(chat_id: int, key: str) -> Optional[Dict[str, Any]]:
    """Re-activate the intake and jump to a specific step (for the Edit
    flow in the review screen). Clears the answer for that step so the
    user can re-enter a new value.

    Returns the new state, or None if the key is invalid.
    """
    idx = get_step_index(key)
    if idx is None:
        return None
    load_fn, save_fn = _get_state_funcs()
    state = load_fn(chat_id) or {}
    # If intake was complete, re-open it
    if state.get("hunt_intake_complete"):
        state["hunt_intake_complete"] = False
        state["hunt_intake_completed_at"] = None
    # Drop the previous answer for this step
    answers = state.get("hunt_intake_answers", {}) or {}
    answers.pop(key, None)
    state["hunt_intake_answers"] = answers
    # Restart at this step
    state["hunt_intake_active"] = True
    state["hunt_intake_step"] = idx
    # Flag so that when the user finishes the edited step, we route them
    # back to the review screen instead of auto-starting the hunt.
    state["hunt_intake_editing"] = True
    save_fn(chat_id, state)
    log.info(f"Chat {chat_id} jumped to step {key!r} (idx={idx}) for edit")
    return state


def go_to_review(chat_id: int) -> Dict[str, Any]:
    """Re-mark the intake as complete (for the review screen flow) without
    touching the answers. Used after the user edited a step and answered
    it again — we re-mark complete so _on_hunt_intake_complete shows the
    review screen.
    """
    load_fn, save_fn = _get_state_funcs()
    state = load_fn(chat_id) or {}
    state["hunt_intake_active"] = False
    state["hunt_intake_complete"] = True
    state["hunt_intake_completed_at"] = __import__("time").time()
    save_fn(chat_id, state)
    return state


def get_intake_answers(chat_id: int) -> Dict[str, Any]:
    """Get all collected answers, filling in defaults for skipped required steps."""
    state = get_intake_state(chat_id)
    if not state:
        return {}
    answers = dict(state.get("hunt_intake_answers", {}))
    # Apply defaults for any not yet answered (e.g. if intake is in progress)
    for step in HUNT_STEPS:
        if step["key"] not in answers and step.get("default") is not None:
            answers[step["key"]] = step["default"]
    return answers


def cancel_intake(chat_id: int) -> None:
    """Cancel the intake (clear all hunt_intake_* keys from state)."""
    load_fn, save_fn = _get_state_funcs()
    state = load_fn(chat_id) or {}
    for k in list(state.keys()):
        if k.startswith("hunt_intake_"):
            state.pop(k, None)
    save_fn(chat_id, state)
    log.info(f"Cleared hunt intake for chat {chat_id}")


def intake_progress_text(chat_id: int) -> str:
    """Human-readable progress for /status."""
    state = get_intake_state(chat_id)
    if not state:
        return ""
    answers = get_intake_answers(chat_id)
    if state.get("hunt_intake_complete"):
        rqs = answers.get("research_questions", "auto")
        rqs_short = rqs if isinstance(rqs, str) and len(rqs) <= 80 else (
            f"{len(rqs)} questions" if isinstance(rqs, list) else str(rqs)[:80]
        )
        return ("✅ *Hunt intake complete*\n"
                f"Type: {answers.get('research_type', '?')}\n"
                f"Title: {answers.get('title', '?')[:50]}\n"
                f"RQs: {rqs_short}\n"
                f"Year range: {answers.get('year_range', 'any')}\n"
                f"Platforms: {answers.get('platforms', '?')}\n"
                f"Max papers: {answers.get('max_papers', '?')}\n"
                f"PDFs: {answers.get('download_pdfs', '?')}\n")
    step = get_current_intake_step(chat_id)
    if not step:
        return ""
    return (f"📝 *Hunt intake in progress* — Step {step['_index'] + 1}/{step['_total']}: "
            f"{step['key']}\n"
            f"Answered: {list(answers.keys())}")
