"""
wizard.py — 7-step input wizard for collecting chapter inputs via Telegram.
Steps: 1) Research type, 2) Chapter name, 3) Title, 4) Research questions,
       5) Aims, 6) Methodology, 7) Existing references (upload)
Every step has a SKIP button. User can /cancel to start over.
"""
from typing import Dict, Any, List, Optional
from logger import get_logger
from state_manager import save_chapter_state, load_chapter_state, clear_chapter_state

log = get_logger("wizard")

# 11 research types with full outline templates
RESEARCH_TYPES: Dict[str, Dict[str, Any]] = {
    "MA": {
        "label": "MA Thesis",
        "components": ["intro", "lit_review", "methodology", "results", "discussion", "conclusion"],
        "word_count": 15000,
        "outlines": {
            "intro": "Background, problem statement, research questions, significance",
            "lit_review": "Thematic synthesis of 30-50 key sources",
            "methodology": "Mixed/qual/quant design, sampling, instruments, ethics",
            "results": "Data presentation, tables, figures",
            "discussion": "Interpretation, comparison with literature, implications",
            "conclusion": "Summary, limitations, future research",
        },
    },
    "PhD": {
        "label": "PhD Dissertation",
        "components": ["intro", "lit_review", "methodology", "results", "discussion", "conclusion", "abstract", "appendices"],
        "word_count": 80000,
        "outlines": {
            "intro": "Multi-paragraph background, gap statement, objectives, contribution",
            "lit_review": "Critical synthesis, theoretical framework, 100+ sources",
            "methodology": "Rigorous design, validity, reliability, ethics approval",
            "results": "Comprehensive data analysis, statistical tests",
            "discussion": "Theoretical implications, comparison with global studies",
            "conclusion": "Synthesis, contributions to knowledge, limitations, future work",
        },
    },
    "MA-P": {"label": "MA Project (Applied)", "components": ["intro", "lit_review", "methodology", "implementation", "results", "conclusion"], "word_count": 12000, "outlines": {}},
    "PhD-P": {"label": "PhD by Publication", "components": ["intro", "papers", "synthesis", "conclusion"], "word_count": 40000, "outlines": {}},
    "RA": {"label": "Research Article", "components": ["intro", "method", "results", "discussion"], "word_count": 8000, "outlines": {}},
    "SR": {"label": "Systematic Review", "components": ["protocol", "search", "screening", "quality_assessment", "synthesis", "PRISMA"], "word_count": 12000, "outlines": {}},
    "EX": {"label": "Experimental Study", "components": ["intro", "hypothesis", "method", "results", "discussion"], "word_count": 10000, "outlines": {}},
    "CS": {"label": "Case Study", "components": ["intro", "background", "case_description", "analysis", "discussion"], "word_count": 9000, "outlines": {}},
    "TC": {"label": "Theoretical/Conceptual", "components": ["intro", "theory", "framework", "implications"], "word_count": 8000, "outlines": {}},
    "BC": {"label": "Book Chapter", "components": ["intro", "background", "main", "conclusion"], "word_count": 6000, "outlines": {}},
    "CP": {"label": "Conference Paper", "components": ["intro", "method", "results", "discussion", "references"], "word_count": 6000, "outlines": {}},
}


WIZARD_STEPS: List[Dict[str, Any]] = [
    {
        "key": "research_type",
        "prompt": "📚 *Step 1/7: Research type*\n\nWhat type of work are you writing?",
        "options": [(k, v["label"]) for k, v in RESEARCH_TYPES.items()],
        "allow_skip": False,
    },
    {
        "key": "chapter_name",
        "prompt": "📖 *Step 2/7: Chapter name*\n\nWhat is the chapter title? (Used for the Drive folder + Sheet name)",
        "allow_skip": False,
    },
    {
        "key": "title",
        "prompt": "🔖 *Step 3/7: Paper/work title*\n\nWhat is the title of the work you're looking for? (or the chapter title if you're uploading)",
        "allow_skip": True,
    },
    {
        "key": "questions",
        "prompt": "❓ *Step 4/7: Research questions*\n\nWhat are the main research questions? (One per line, or paste them as a list)\n\n_Send Skip if not yet defined._",
        "allow_skip": True,
    },
    {
        "key": "aims",
        "prompt": "🎯 *Step 5/7: Aims & objectives*\n\nWhat are the aims/objectives of the work? (Bullet list)\n\n_Send Skip if not yet defined._",
        "allow_skip": True,
    },
    {
        "key": "methodology",
        "prompt": "🔬 *Step 6/7: Methodology*\n\nBriefly describe the methodology (qualitative / quantitative / mixed / review / etc.)\n\n_Send Skip if not yet defined._",
        "allow_skip": True,
    },
    {
        "key": "upload",
        "prompt": "📎 *Step 7/7: Upload references*\n\nUpload your chapter PDF / DOCX, OR paste a single reference, OR send Skip to start a fresh search.\n\n_You can also send up to 50 references as text, one per line._",
        "allow_skip": True,
    },
]


def start_wizard(chat_id: int) -> Dict[str, Any]:
    """Initialize a fresh wizard state for a chat."""
    clear_chapter_state(chat_id)
    state = {
        "wizard_active": True,
        "step_index": 0,
        "answers": {},
    }
    save_chapter_state(chat_id, state)
    log.info(f"Started wizard for chat {chat_id}")
    return state


def get_current_step(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the current step definition, or None if wizard is complete."""
    i = state.get("step_index", 0)
    if i < 0 or i >= len(WIZARD_STEPS):
        return None
    return WIZARD_STEPS[i]


def record_answer(chat_id: int, step_key: str, value: Any) -> Dict[str, Any]:
    """Record an answer and advance to the next step."""
    state = load_chapter_state(chat_id) or {}
    state.setdefault("answers", {})[step_key] = value
    state["step_index"] = state.get("step_index", 0) + 1
    if state["step_index"] >= len(WIZARD_STEPS):
        state["wizard_active"] = False
        state["wizard_complete"] = True
    save_chapter_state(chat_id, state)
    log.info(f"Chat {chat_id} answered {step_key!r}, now at step {state['step_index']}")
    return state


def skip_step(chat_id: int) -> Dict[str, Any]:
    """Skip the current step and advance."""
    state = load_chapter_state(chat_id) or {}
    step = get_current_step(state)
    if step is None:
        return state
    state.setdefault("answers", {})[step["key"]] = None
    state["step_index"] = state.get("step_index", 0) + 1
    if state["step_index"] >= len(WIZARD_STEPS):
        state["wizard_active"] = False
        state["wizard_complete"] = True
    save_chapter_state(chat_id, state)
    log.info(f"Chat {chat_id} skipped {step['key']!r}")
    return state


def is_wizard_active(chat_id: int) -> bool:
    state = load_chapter_state(chat_id)
    return bool(state and state.get("wizard_active"))


def get_answers(chat_id: int) -> Dict[str, Any]:
    state = load_chapter_state(chat_id)
    return (state or {}).get("answers", {})


def cancel_wizard(chat_id: int) -> None:
    clear_chapter_state(chat_id)
    log.info(f"Wizard cancelled for chat {chat_id}")
