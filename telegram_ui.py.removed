"""
telegram_ui.py — Rich UI components for the Search Sleeping Bot.

Provides reusable helpers for:
  - Main menu (rich welcome with all capabilities + interactive buttons)
  - Review screen (shows all 14 intake answers with per-step edit buttons)
  - Edit panel (back to a specific step to change/remove answer)
  - Calendar / report list (past hunts)
  - Progress display (emoji-rich stage status)

v6.7: now handles 14 steps with exhaustive review screen.

All functions are stateless except where they read chat state. They build
inline keyboard layouts and message text. They do NOT call the Telegram
API directly — they return data for telegram_bot to send.
"""
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from logger import get_logger

log = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# Main menu
# ──────────────────────────────────────────────────────────────────────────

MAIN_MENU_TEXT = (
    "👋 *Welcome to Search Sleeping Bot!*\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "🎓 *Your AI research assistant for dissertations, theses & papers.*\n\n"
    "🌟 *What I can do for you:*\n\n"
    "🔍 *Search 81+ academic platforms*\n"
    "   _CrossRef, OpenAlex, PubMed, arXiv, ERIC, DOAJ, JSTOR, "
    "Sci-Hub, Zenodo, BASE, CORE, Semantic Scholar, ..._\n\n"
    "🤖 *AI-powered relevance scoring*\n"
    "   _ollama reads every abstract, scores 0–1, cross-validates across sources._\n\n"
    "📥 *Download real PDFs*\n"
    "   _14-layer download chain (CrossRef → Unpaywall → PMC → LibGen → Sci-Hub)._\n\n"
    "📊 *Heavy reports — every format*\n"
    "   _PDF (LibreOffice), DOCX, Excel (color-coded), Markdown, JSON._\n\n"
    "☁️ *Auto-upload to Google Drive*\n"
    "   _Per-title folder structure for your supervisor._\n\n"
    "✅ *Verify your references*\n"
    "   _Paste your reference list or upload a chapter PDF — I'll check "
    "every citation exists, classify as VERIFIED / LIKELY / UNVERIFIED / FAKE._\n\n"
    "🧠 *3 RQ packages to choose from*\n"
    "   _Theoretical / Empirical / Applied — pick the angle that fits._\n\n"
    "🌟 *Suggest future research*\n"
    "   _Based on the gaps I find in the literature._\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "🚀 *Pick a button to begin:*"
)


def main_menu_keyboard() -> Dict[str, Any]:
    """Inline keyboard for the main menu.

    Each callback starts with 'main:' so telegram_bot._handle_callback
    can route them.
    """
    return {
        "inline_keyboard": [
            [{"text": "🔍 New Hunt  →  search a new topic",
              "callback_data": "main:newhunt"}],
            [{"text": "✅ Verify References  →  check your chapter's citations",
              "callback_data": "main:verifyrefs"}],
            [{"text": "📊 My Reports  →  see past hunts + Drive folder",
              "callback_data": "main:myreports"}],
            [{"text": "❓ Help / About  →  what each button does",
              "callback_data": "main:help"}],
            [{"text": "⚙️ Settings  →  Drive folder, max papers, defaults",
              "callback_data": "main:settings"}],
            [{"text": "🆕 What's New  →  v6.7 features",
              "callback_data": "main:changelog"}],
        ]
    }


# ──────────────────────────────────────────────────────────────────────────
# Help / About
# ──────────────────────────────────────────────────────────────────────────

HELP_TEXT = (
    "❓ *HELP — Search Sleeping Bot*\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "*🔍 New Hunt (v6.7 — 14 steps)*\n"
    "1.  Research type (PhD, MA, RA, ...)\n"
    "2.  Title / topic\n"
    "3.  Field / discipline (Education, Medicine, ...)\n"
    "4.  Research angle (Theoretical, Empirical, Applied, ...)\n"
    "5.  Research questions (auto-generate 3 packages, pick one)\n"
    "6.  Year range\n"
    "7.  Language (English, Arabic, French, ...)\n"
    "8.  Country / region (Libya, MENA, Africa, Worldwide)\n"
    "9.  Paper type (Journal, Conference, Preprint, Thesis)\n"
    "10. Quartile filter (Q1 only, Q1+Q2, Any)\n"
    "11. Open access only?\n"
    "12. Platforms (all 81, top 20, top 10)\n"
    "13. Max papers (default 1000)\n"
    "14. Download PDFs (yes/no)\n\n"
    "Then a *Review* screen shows ALL 14 choices with per-step Edit buttons. "
    "After you confirm, I'll show *3 RQ packages* — pick the angle that fits.\n\n"

    "*✅ Verify References*\n"
    "Paste a reference list, upload a chapter PDF, or point at a folder.\n"
    "I'll check every citation:\n"
    "🟢 VERIFIED (≥0.85 score)  →  real paper\n"
    "🟡 LIKELY (0.60–0.85)       →  probably real\n"
    "🔴 UNVERIFIED              →  no source found\n"
    "⛔ FAKE                     →  no candidate at all\n\n"

    "*📊 My Reports*\n"
    "List of your past hunts with date, paper count, Drive link.\n\n"

    "*⚙️ Settings*\n"
    "Default max papers, default platforms, Drive folder ID.\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "💡 Tip: every step has a *Skip* button → uses the default."
)


# ──────────────────────────────────────────────────────────────────────────
# Changelog
# ──────────────────────────────────────────────────────────────────────────

CHANGELOG_TEXT = (
    "🆕 *WHAT'S NEW — v6.7*\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "✨ *v6.7 — 14-step intake + 3 RQ packages*\n"
    "_Expanded to 14 steps (was 7). Added field, RQ angle, language, "
    "country, paper type, quartile filter, open access. 3 RQ packages "
    "with AI explanations to choose from._\n\n"
    "✨ *v6.6 — Rich UI overhaul*\n"
    "_Main menu, review screen with per-step Edit, My Reports, Help, "
    "Settings, What's New._\n\n"
    "✨ *v6.5.1 — 7-step intake*\n"
    "_Added Research Questions + Year Range steps with auto-generate._\n\n"
    "📊 *v6.4 — Unleashed deep search*\n"
    "_Default 1000 papers (was 30). 'deep' = no cap._\n\n"
    "📕 *v6.4 — Heavy PDF report*\n"
    "_LibreOffice DOCX→PDF, delivered first in Telegram._\n\n"
    "☁️ *v6.4.1 — Drive integration unit-tested*\n"
    "_8 mocked tests + bot surfaces Drive errors to user._\n\n"
    "✅ *v6.3.1 — Top-10 papers in delivery*\n"
    "_Fixed silent bug where Top 10 never sent._\n\n"
    "🎯 *v6.3 — /hunt2 unified 5→7 step intake*\n"
    "_Heartbeat every 5 min, file delivery in chat._\n\n"
    "🔍 *v6.2 — /verifyrefs command*\n"
    "_Check your reference list with 4-tier classification._\n\n"
    "🌐 *v6.1 — 81 platforms*\n"
    "_Connected Papers, Lens.org, DataCite, Dryad, Figshare, Zenodo, ..._"
)


# ──────────────────────────────────────────────────────────────────────────
# Review screen — shown after all 7 steps, before starting
# ──────────────────────────────────────────────────────────────────────────

# Human-readable labels for the 14 step keys (v6.7)
STEP_LABELS = {
    "research_type":     "📖 Research type",
    "title":             "🔖 Title / Topic",
    "field":             "🎓 Field / discipline",
    "rq_angle":          "🧭 Research angle",
    "research_questions":"❓ Research questions",
    "year_range":        "📅 Year range",
    "language":          "🌐 Language",
    "country":           "🗺 Geographic focus",
    "paper_type":        "📄 Paper type",
    "quartile_filter":   "⭐ Quartile filter",
    "open_access":       "🔓 Open access only",
    "platforms":         "🌐 Platforms",
    "max_papers":        "📄 Max papers",
    "download_pdfs":     "📥 Download PDFs",
}


_LANG_LABELS = {
    "en": "🇬🇧 English", "ar": "🇸🇦 Arabic", "fr": "🇫🇷 French",
    "es": "🇪🇸 Spanish", "de": "🇩🇪 German", "zh": "🇨🇳 Chinese",
    "any": "🌍 Any / Multilingual",
}

_COUNTRY_LABELS = {
    "libya": "🇱🇾 Libya", "mena": "🌍 MENA",
    "africa": "🌍 Africa", "arab": "🌍 Arab world",
    "europe": "🇪🇺 Europe", "asia": "🌏 Asia",
    "americas": "🌎 Americas", "world": "🌐 Worldwide",
}

_FIELD_LABELS = {
    "education": "📚 Education", "medicine": "🏥 Medicine",
    "engineering": "⚙️ Engineering", "computer_science": "💻 CS / AI",
    "social_sciences": "👥 Social Sciences", "humanities": "📜 Humanities",
    "business": "💼 Business", "natural_sciences": "🔬 Natural Sciences",
    "law": "⚖️ Law", "arts": "🎨 Arts / Design",
    "general": "🌐 General / Interdisciplinary",
}

_ANGLE_LABELS = {
    "theoretical": "📘 Theoretical", "empirical": "🔬 Empirical",
    "applied": "🌍 Applied", "methodological": "🛠 Methodological",
    "comparative": "🆚 Comparative", "mixed": "🌀 Mixed",
}

_PAPER_TYPE_LABELS = {
    "journal": "📰 Journal", "conference": "🎤 Conference",
    "preprint": "📝 Preprint", "thesis": "🎓 Thesis",
    "review": "🔍 Review", "all": "🌐 All types",
}

_QUARTILE_LABELS = {
    "q1": "⭐ Q1 only", "q1q2": "⭐⭐ Q1+Q2", "any": "🌐 Any",
}


def _format_answer_value(key: str, value: Any) -> str:
    """Render a single intake answer as a short human-readable string."""
    if value is None or value == "":
        return "_(not set)_"
    if key == "research_questions" and isinstance(value, list):
        if not value:
            return "_(auto-generate 3 packages)_"
        if len(value) == 1:
            return f"_{value[0][:100]}_"
        return f"_{len(value)} questions: " + "; ".join(
            q[:40] + ("..." if len(q) > 40 else "") for q in value[:3]
        ) + ("..." if len(value) > 3 else "") + "_"
    if key == "research_questions" and isinstance(value, str):
        s = str(value).strip()
        if s.lower() in ("auto", "skip", "skipped", "default", ""):
            return "_🧠 auto (generate 3 packages)_"
        return f"_{s[:100]}_"
    if key == "year_range":
        if value == "any" or not value:
            return "_any year_"
        return f"_{value}_"
    if key == "max_papers":
        if str(value) in ("0", "deep"):
            return "_🌊 DEEP (no cap)_"
        try:
            return f"_{int(value):,}_"
        except (TypeError, ValueError):
            return f"_{value}_"
    if key == "platforms":
        plat_labels = {"all": "🌍 All 81 platforms",
                       "tier12": "⚡ Top 20 platforms",
                       "tier1": "🚀 Top 10 platforms"}
        if isinstance(value, list):
            return f"_{len(value)} selected_"
        return f"_{plat_labels.get(value, value)}_"
    if key == "download_pdfs":
        return "✅ Yes" if str(value).lower() in ("yes", "y", "true", "1") else "❌ No"
    if key == "open_access":
        return "✅ Yes (OA only)" if str(value).lower() in ("yes", "y", "true", "1") else "🌐 Any"
    if key == "research_type":
        rt_labels = {"MA": "📘 MA Thesis", "PhD": "🎓 PhD Dissertation",
                     "RA": "📰 Research Article", "SR": "🔍 Systematic Review",
                     "EX": "🧪 Experimental Study", "CS": "📂 Case Study",
                     "general": "🌐 General / Other"}
        return rt_labels.get(value, f"_{value}_")
    if key == "field":
        return _FIELD_LABELS.get(value, f"_{value}_")
    if key == "rq_angle":
        return _ANGLE_LABELS.get(value, f"_{value}_")
    if key == "language":
        return _LANG_LABELS.get(value, f"_{value}_")
    if key == "country":
        return _COUNTRY_LABELS.get(value, f"_{value}_")
    if key == "paper_type":
        return _PAPER_TYPE_LABELS.get(value, f"_{value}_")
    if key == "quartile_filter":
        return _QUARTILE_LABELS.get(value, f"_{value}_")
    s = str(value)
    if len(s) > 80:
        s = s[:80] + "..."
    return f"_{s}_"


def build_review_screen(answers: Dict[str, Any],
                        title_fallback: str = "Research Hunt") -> Tuple[str, Dict[str, Any]]:
    """Build the review-screen text + keyboard.

    v6.7: shows ALL 14 steps (was 7) as a long exhaustive list.
    Returns (text, reply_markup) tuple. The keyboard has:
      - An "Edit" button next to each of the 14 steps (callback: hunt:edit:<key>)
      - A "✅ Start the hunt" button at the bottom (callback: hunt:start)
      - A "❌ Cancel" button (callback: hunt:cancel)
    """
    n = len(STEP_LABELS)
    lines = [
        "📋 *REVIEW YOUR HUNT CONFIGURATION*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"_Exhaustive list of all {n} choices — tap any to edit._",
        "",
    ]
    rows: List[List[Dict[str, str]]] = []
    # Two edit buttons per row to keep the keyboard compact
    edit_buttons: List[Dict[str, str]] = []
    for i, (key, label) in enumerate(STEP_LABELS.items(), 1):
        value = answers.get(key)
        rendered = _format_answer_value(key, value)
        lines.append(f"*{i}.* {label}: {rendered}")
        edit_buttons.append({
            "text": f"✏️ {i}. {key}",
            "callback_data": f"hunt:edit:{key}",
        })
        if len(edit_buttons) == 2:
            rows.append(edit_buttons)
            edit_buttons = []
    if edit_buttons:
        rows.append(edit_buttons)
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 *Total: {n} choices recorded.*")
    lines.append("")
    lines.append("✅ Looks good? → tap *Start the hunt*")
    lines.append("✏️ Want to change something? → tap an Edit button above")
    lines.append("❌ Changed your mind? → Cancel")

    # Final action buttons
    rows.append([
        {"text": "✅ Start the hunt", "callback_data": "hunt:start"},
        {"text": "❌ Cancel", "callback_data": "hunt:cancel"},
    ])
    return "\n".join(lines), {"inline_keyboard": rows}


# ──────────────────────────────────────────────────────────────────────────
# Edit panel — after tapping "Edit step N"
# ──────────────────────────────────────────────────────────────────────────

def build_edit_panel(key: str, current_value: Any) -> Tuple[str, Dict[str, Any]]:
    """Build the edit panel for a single step.

    Shows current value + a small keyboard with options appropriate to
    that step. If the step is option-based, the option buttons are shown.
    If free-text (title, year_range, max_papers), we show a hint to type
    the new value. v6.7: handles all 14 steps.
    """
    label = STEP_LABELS.get(key, key)
    rendered = _format_answer_value(key, current_value)
    text = (
        f"✏️ *EDIT — {label}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*Current value:* {rendered}\n\n"
    )
    kb: List[List[Dict[str, str]]] = []

    def _two_col(opts):
        row: List[Dict[str, str]] = []
        for v, lab in opts:
            row.append({"text": lab, "callback_data": f"hunt:set:{key}:{v}"})
            if len(row) == 2:
                kb.append(row); row = []
        if row:
            kb.append(row)

    if key == "research_type":
        text += "Tap a new value, or tap *Keep current* to leave it as-is."
        _two_col([
            ("MA", "📘 MA"), ("PhD", "🎓 PhD"), ("RA", "📰 Article"),
            ("SR", "🔍 Review"), ("EX", "🧪 Exp"), ("CS", "📂 Case"),
            ("general", "🌐 General"),
        ])
    elif key == "field":
        text += "Tap a new field, or tap *Keep current* to leave it as-is."
        _two_col([
            ("education", "📚 Education"), ("medicine", "🏥 Medicine"),
            ("engineering", "⚙️ Eng"), ("computer_science", "💻 CS / AI"),
            ("social_sciences", "👥 Social"), ("humanities", "📜 Hum"),
            ("business", "💼 Business"), ("natural_sciences", "🔬 Sci"),
            ("law", "⚖️ Law"), ("arts", "🎨 Arts"),
            ("general", "🌐 General"),
        ])
    elif key == "rq_angle":
        text += "Tap a new angle, or tap *Keep current* to leave it as-is."
        _two_col([
            ("theoretical", "📘 Theoretical"), ("empirical", "🔬 Empirical"),
            ("applied", "🌍 Applied"), ("methodological", "🛠 Methodological"),
            ("comparative", "🆚 Comparative"), ("mixed", "🌀 Mixed"),
        ])
    elif key == "language":
        text += "Tap a new language, or tap *Keep current* to leave it as-is."
        _two_col([
            ("en", "🇬🇧 EN"), ("ar", "🇸🇦 AR"), ("fr", "🇫🇷 FR"),
            ("es", "🇪🇸 ES"), ("de", "🇩🇪 DE"), ("zh", "🇨🇳 ZH"),
            ("any", "🌍 Any"),
        ])
    elif key == "country":
        text += "Tap a new region, or tap *Keep current* to leave it as-is."
        _two_col([
            ("libya", "🇱🇾 Libya"), ("mena", "🌍 MENA"),
            ("africa", "🌍 Africa"), ("arab", "🌍 Arab"),
            ("europe", "🇪🇺 EU"), ("asia", "🌏 Asia"),
            ("americas", "🌎 Americas"), ("world", "🌐 World"),
        ])
    elif key == "paper_type":
        text += "Tap a new paper type, or tap *Keep current* to leave it as-is."
        _two_col([
            ("journal", "📰 Journal"), ("conference", "🎤 Conf"),
            ("preprint", "📝 Preprint"), ("thesis", "🎓 Thesis"),
            ("review", "🔍 Review"), ("all", "🌐 All"),
        ])
    elif key == "quartile_filter":
        text += "Tap a quartile preset, or tap *Keep current* to leave it as-is."
        _two_col([
            ("q1", "⭐ Q1 only"), ("q1q2", "⭐⭐ Q1+Q2"), ("any", "🌐 Any"),
        ])
    elif key == "open_access":
        text += "Tap Yes / No, or tap *Keep current* to leave it as-is."
        kb.append([
            {"text": "✅ Yes (OA only)", "callback_data": f"hunt:set:{key}:yes"},
            {"text": "🌐 Any access",    "callback_data": f"hunt:set:{key}:no"},
        ])
    elif key == "platforms":
        text += "Tap a new tier, or tap *Keep current* to leave it as-is."
        for v, lab in [
            ("all", "🌍 All 81"),
            ("tier12", "⚡ Top 20"),
            ("tier1", "🚀 Top 10"),
        ]:
            kb.append([{"text": lab, "callback_data": f"hunt:set:{key}:{v}"}])
    elif key == "download_pdfs":
        text += "Tap Yes / No, or tap *Keep current* to leave it as-is."
        kb.append([
            {"text": "✅ Yes", "callback_data": f"hunt:set:{key}:yes"},
            {"text": "❌ No", "callback_data": f"hunt:set:{key}:no"},
        ])
    elif key == "year_range":
        text += ("Type a new range (e.g. *2020-2024* or *2018*),\n"
                 "or tap *Keep current* / *Any year*.")
        kb.append([
            {"text": "📅 Any year", "callback_data": f"hunt:set:{key}:any"},
        ])
    elif key == "max_papers":
        text += ("Type a new number, or tap a preset.\n"
                 "*0* or *deep* = no cap.")
        kb.append([
            {"text": "50",  "callback_data": f"hunt:set:{key}:50"},
            {"text": "100", "callback_data": f"hunt:set:{key}:100"},
            {"text": "500", "callback_data": f"hunt:set:{key}:500"},
            {"text": "1000","callback_data": f"hunt:set:{key}:1000"},
            {"text": "🌊 deep", "callback_data": f"hunt:set:{key}:0"},
        ])
    elif key == "research_questions":
        text += ("Type 1-5 research questions, one per line.\n"
                 "Or tap *Auto* to generate 3 packages at Start time.")
        kb.append([
            {"text": "🧠 Auto (generate 3 packages)", "callback_data": f"hunt:set:{key}:auto"},
        ])
    else:
        # Free-text fields: title
        text += f"Just *type your new {label.split(' ', 1)[1].lower()}* below."
    kb.append([
        {"text": "↩ Keep current (back to review)",
         "callback_data": "hunt:back_to_review"},
        {"text": "❌ Cancel hunt", "callback_data": "hunt:cancel"},
    ])
    return text, {"inline_keyboard": kb}


# ──────────────────────────────────────────────────────────────────────────
# Calendar / past hunts
# ──────────────────────────────────────────────────────────────────────────

def build_reports_list(reports: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    """Build a 'My Reports' list from a list of past hunt summaries.

    Each report dict has: title, date, total_papers, downloaded,
    drive_url, output_folder.
    """
    if not reports:
        return (
            "📊 *MY REPORTS*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "You have no past hunts yet.\n\n"
            "Tap *🔍 New Hunt* on the main menu to start your first one!",
            main_menu_keyboard(),
        )
    lines = ["📊 *MY REPORTS*", "━━━━━━━━━━━━━━━━━━━━━━━━━━", ""]
    rows: List[List[Dict[str, str]]] = []
    for i, r in enumerate(reports[:20], 1):
        title = r.get("title", "?")[:50]
        date = r.get("date", "?")
        n = r.get("total_papers", 0)
        dl = r.get("downloaded", 0)
        drive = r.get("drive_url", "")
        lines.append(f"{i}. *{title}*\n"
                     f"   📅 {date}  |  📄 {n} papers  |  📥 {dl} PDFs")
        if drive:
            lines.append(f"   ☁️ [Open in Drive]({drive})")
        rows.append([{
            "text": f"📂 {i}. {title[:25]}",
            "callback_data": f"reports:open:{i}",
        }])
    lines.append("")
    lines.append(f"_Showing {min(20, len(reports))} of {len(reports)} reports._")
    rows.append([{"text": "↩ Back to main menu", "callback_data": "main:start"}])
    return "\n".join(lines), {"inline_keyboard": rows}


# ──────────────────────────────────────────────────────────────────────────
# Settings panel
# ──────────────────────────────────────────────────────────────────────────

SETTINGS_TEXT = (
    "⚙️ *SETTINGS*\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "*Current defaults:*\n"
    "📄 Max papers: 1000 (use 0/deep for no cap)\n"
    "🌐 Platforms: all 81 (best coverage)\n"
    "📅 Year range: any\n"
    "📥 Download PDFs: yes\n"
    "☁️ Drive root: `Literature_Review_Verifier/`\n\n"
    "💡 *Tip:* defaults can be changed per-hunt via the intake steps. "
    "Persistent settings are read from environment variables:\n"
    "  `DEFAULT_MAX_PAPERS`, `DEFAULT_PLATFORMS`, `DRIVE_ROOT_FOLDER`."
)


# ──────────────────────────────────────────────────────────────────────────
# Progress display
# ──────────────────────────────────────────────────────────────────────────

STAGE_INFO = {
    "starting":            ("🚀", "Initializing hunt pipeline"),
    "generating_queries":  ("🧠", "Generating AI search queries"),
    "searching":           ("🔍", "Searching platforms"),
    "deduplicating":       ("🔎", "Deduplicating & filtering"),
    "checking_quartiles":  ("📊", "Checking quartiles & downloading"),
    "downloading":         ("📥", "Downloading PDFs"),
    "generating_report":   ("📝", "Generating reports"),
    "done":                ("✅", "Hunt complete"),
}


def format_progress_line(stage: str, pct: int, message: str = "") -> str:
    """Format a single progress line for the chat."""
    emoji, label = STAGE_INFO.get(stage, ("🔄", stage.replace("_", " ").title()))
    line = f"{emoji} *{label}* [{pct}%]"
    if message:
        msg = message[:120] + ("..." if len(message) > 120 else "")
        line += f"\n   _{msg}_"
    return line


# ──────────────────────────────────────────────────────────────────────────
# Hunt summary (final delivery header)
# ──────────────────────────────────────────────────────────────────────────

def build_hunt_summary_text(params: Dict[str, Any],
                            result: Dict[str, Any]) -> str:
    """Build the final hunt summary text shown to the user with all details."""
    title = params.get("title", "?")[:80]
    rqs = params.get("research_questions") or []
    rqs_text = ""
    if rqs:
        rqs_text = "\n❓ *Research questions:*\n"
        for i, q in enumerate(rqs[:5], 1):
            rqs_text += f"   {i}. {q[:90]}{'...' if len(q) > 90 else ''}\n"

    total = result.get("total_papers", 0)
    downloaded = result.get("downloaded", 0)
    red_count = result.get("red_list_count", 0)
    run_stats = result.get("results", {}).get("run_stats", {})
    q_dist = run_stats.get("q_distribution", {})
    fs_count = len(result.get("results", {}).get("future_studies", []) or [])

    elapsed_min = result.get("elapsed_min", 0)

    lines = [
        "🎉 *HUNT COMPLETE!*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📚 *Title:* {title}",
        f"📖 *Type:* {params.get('research_type', 'general')}",
        f"📅 *Year range:* {params.get('year_from', 'any')}–{params.get('year_to', 'any')}",
        f"🌐 *Platforms:* {params.get('platforms_key', 'all')}",
        f"📄 *Max papers:* {params.get('max_papers', 1000)}",
        f"📥 *Download PDFs:* {'yes' if params.get('download_pdfs') else 'no'}",
        f"{rqs_text}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📊 *RESULTS*",
        f"   📄 Papers found: *{total}*",
        f"   📥 PDFs downloaded: *{downloaded}*",
        f"   🔴 Manual download needed: *{red_count}*",
        f"   ⏱ Took: *{elapsed_min:.0f} min*",
    ]
    if q_dist:
        lines.append(
            f"   📊 Quartiles: Q1:{q_dist.get('Q1', 0)} "
            f"Q2:{q_dist.get('Q2', 0)} Q3:{q_dist.get('Q3', 0)} "
            f"Q4:{q_dist.get('Q4', 0)}"
        )
    if fs_count:
        lines.append(f"   🌟 Future research directions: *{fs_count}* (in .md + .docx)")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Drive link
    drive_url = result.get("drive_folder_url")
    if drive_url:
        lines.append(f"☁️ *All files in Google Drive:*\n   {drive_url}")
    elif result.get("drive_error"):
        lines.append(f"⚠️ *Drive upload failed:* {result['drive_error']}")

    return "\n".join(lines)
