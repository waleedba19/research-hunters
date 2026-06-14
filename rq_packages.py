"""
rq_packages.py — v6.7

Generate 2-3 alternative "research question packages" for a topic, each with
a different angle/focus and a short AI explanation. The user picks one
package (or "auto") before the hunt starts.

This runs AFTER the user has set their topic + research type, BEFORE the
review screen. Result is stored in chat state and offered as 3 inline
keyboard buttons.

3 packages per title:
  1. 📘 THEORETICAL — focuses on concepts, frameworks, definitions
  2. 🔬 EMPIRICAL   — focuses on data, methods, measurements
  3. 🌍 APPLIED     — focuses on real-world impact, policy, practice

Each package has:
  - title   : short theme label (e.g. "Conceptual foundations")
  - focus   : 1-sentence description of the angle
  - rqs     : 2-3 research questions matching the angle
  - why     : 1-sentence AI explanation of why this package fits the topic

Generation:
  - Tries ollama HTTP first (precision_engine._call_ollama)
  - Falls back to deterministic templates if ollama fails
  - Total budget: 90s (each of 3 packages has 30s)
"""
from typing import List, Dict, Any, Optional
import json
import re
import time

from logger import get_logger

log = get_logger(__name__)


PACKAGE_ANGLES = [
    {
        "id": "theoretical",
        "emoji": "📘",
        "label": "Theoretical",
        "default_focus": "Concepts, frameworks, definitions",
        "default_why": "Best for a literature review that needs to clarify terminology "
                       "and build a theoretical lens before the empirical work.",
        "template_rqs": [
            "What does the existing literature define as {kw}?",
            "What theoretical frameworks have been used to study {kw}?",
            "How do scholars distinguish {kw} from related concepts?",
        ],
    },
    {
        "id": "empirical",
        "emoji": "🔬",
        "label": "Empirical",
        "default_focus": "Data, methods, measurements",
        "default_why": "Best when you have (or plan to collect) data and need "
                       "research questions that lead to measurable, testable claims.",
        "template_rqs": [
            "What methods have researchers used to study {kw}?",
            "What measurable effects of {kw} have been reported in prior studies?",
            "What gaps remain in the empirical evidence on {kw}?",
        ],
    },
    {
        "id": "applied",
        "emoji": "🌍",
        "label": "Applied",
        "default_focus": "Real-world impact, policy, practice",
        "default_why": "Best for dissertations that aim to inform practice or "
                       "policy — questions grounded in real problems.",
        "template_rqs": [
            "How is {kw} applied in professional practice?",
            "What policy or programme implications follow from research on {kw}?",
            "What challenges do practitioners face when applying {kw}?",
        ],
    },
]


def _extract_keywords(title: str) -> str:
    """Pull a short keyword phrase from a topic title for template substitution."""
    if not title:
        return "this topic"
    title = re.sub(r"^(a|an|the)\s+", "", title.strip(), flags=re.IGNORECASE)
    title = re.sub(
        r"^(an?\s+(?:investigation|exploration|examination|study|analysis|review)\s+"
        r"(?:of|into|on)\s+)",
        "", title, flags=re.IGNORECASE,
    )
    return title.strip().rstrip("?.!").strip()


def _parse_ai_package_response(raw: str) -> Optional[Dict[str, Any]]:
    """Parse a JSON object from an ollama response. Be tolerant of markdown
    fences, leading text, and trailing commentary.
    """
    if not raw:
        return None
    raw = raw.strip()
    # Strip ```json fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    # Find first { and last }
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = raw[start:end + 1]
    try:
        return json.loads(candidate)
    except Exception:
        pass
    # Try to repair common JSON errors (trailing commas)
    candidate = re.sub(r",\s*}", "}", candidate)
    candidate = re.sub(r",\s*]", "]", candidate)
    try:
        return json.loads(candidate)
    except Exception:
        return None


def _generate_one_package(title: str, angle: Dict[str, Any], ollama_fn=None,
                          timeout: int = 30) -> Dict[str, Any]:
    """Generate one RQ package for the given angle. Returns a dict with
    title, focus, rqs (list of strings), why.
    """
    kw = _extract_keywords(title)
    pkg = {
        "id": angle["id"],
        "emoji": angle["emoji"],
        "label": angle["label"],
        "title": f"{angle['label']} lens on {kw[:60]}",
        "focus": angle["default_focus"],
        "rqs": [tpl.format(kw=kw) for tpl in angle["template_rqs"]],
        "why": angle["default_why"],
    }

    if ollama_fn is None:
        try:
            from precision_engine import _call_ollama
            ollama_fn = _call_ollama
        except Exception:
            ollama_fn = None

    if ollama_fn is None:
        return pkg

    prompt = (
        f"You are helping a researcher frame 2-3 research questions for the "
        f"topic: \"{title}\".\n\n"
        f"Angle: {angle['label']} ({angle['default_focus']})\n\n"
        f"Return ONLY valid JSON in this exact shape (no extra text):\n"
        f"{{\n"
        f'  "focus": "<1 short sentence describing the angle for this topic>",\n'
        f'  "rqs": ["<research question 1>", "<research question 2>", "<research question 3>"],\n'
        f'  "why": "<1 sentence explaining why this angle fits the topic>"\n'
        f"}}\n\n"
        f"Requirements:\n"
        f"- 2 to 3 research questions (3 preferred)\n"
        f"- Each question 8-25 words\n"
        f"- Make them specific to \"{title}\", not generic\n"
        f"- The 'why' should be 1 sentence, max 25 words\n"
    )

    try:
        raw = ollama_fn(prompt, timeout=timeout)
    except Exception as e:
        log.warning(f"_generate_one_package ollama call failed: {e}")
        return pkg

    parsed = _parse_ai_package_response(raw)
    if not parsed or not isinstance(parsed, dict):
        log.warning(f"_generate_one_package: could not parse ollama output for {angle['id']}")
        return pkg

    new_focus = (parsed.get("focus") or "").strip()
    new_why = (parsed.get("why") or "").strip()
    new_rqs = parsed.get("rqs") or []
    if not isinstance(new_rqs, list):
        new_rqs = []
    new_rqs = [str(q).strip() for q in new_rqs if str(q).strip()]

    if new_focus and 5 <= len(new_focus) <= 200:
        pkg["focus"] = new_focus
    if new_why and 5 <= len(new_why) <= 300:
        pkg["why"] = new_why
    if 2 <= len(new_rqs) <= 4 and all(5 <= len(q) <= 200 for q in new_rqs):
        pkg["rqs"] = new_rqs[:3]
    return pkg


def generate_rq_packages(title: str, ollama_fn=None,
                         max_total_seconds: int = 90) -> List[Dict[str, Any]]:
    """Generate 3 RQ packages for a topic. Each package = label + focus + 2-3
    RQs + why-this-fits. Returns a list of 3 dicts.
    """
    if not title:
        title = "this topic"
    per_call_budget = max(15, max_total_seconds // 3)
    packages = []
    for angle in PACKAGE_ANGLES:
        t0 = time.time()
        try:
            pkg = _generate_one_package(title, angle, ollama_fn=ollama_fn,
                                        timeout=per_call_budget)
        except Exception as e:
            log.warning(f"generate_rq_packages: failed for angle {angle['id']}: {e}")
            pkg = _generate_one_package(title, angle, ollama_fn=None)
        log.info(f"generate_rq_packages: {angle['id']} package in {time.time()-t0:.1f}s")
        packages.append(pkg)
    return packages


def format_package_short(pkg: Dict[str, Any], idx: int) -> str:
    """Format a single package as a short multi-line text block (no buttons)."""
    lines = [
        f"{pkg['emoji']} *Package {idx}: {pkg['label']}* — {pkg.get('title', '')}",
        f"   🎯 Focus: {pkg.get('focus', '')}",
    ]
    for i, q in enumerate(pkg.get("rqs", []), 1):
        lines.append(f"   {i}. {q[:130]}{'...' if len(q) > 130 else ''}")
    lines.append(f"   💡 Why: {pkg.get('why', '')}")
    return "\n".join(lines)


def format_packages_picker(packages: List[Dict[str, Any]]) -> str:
    """Format a 'pick a package' message that introduces all 3 packages
    and recommends one based on the research type. Returned as a single
    text string (the keyboard is built separately).
    """
    if not packages:
        return "❌ Could not generate research question packages."
    lines = [
        "🧠 *RESEARCH QUESTION PACKAGES*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "I generated *3 different angles* for your topic. Each package has "
        "2-3 questions and an explanation of why it fits your study.",
        "",
    ]
    for i, pkg in enumerate(packages, 1):
        lines.append(format_package_short(pkg, i))
        lines.append("")
    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "🎯 *Pick the package that best matches your study's angle:*",
    ])
    return "\n".join(lines)


def packages_picker_keyboard() -> Dict[str, Any]:
    """Inline keyboard for picking a package. Each button is hunt:rq:<id>.
    A final 'Use any of them' button lets the system pick the most balanced.
    """
    rows: List[List[Dict[str, str]]] = []
    for i, pkg in enumerate(PACKAGE_ANGLES, 1):
        rows.append([{
            "text": f"{pkg['emoji']} Use Package {i} ({pkg['label']})",
            "callback_data": f"hunt:rq:{pkg['id']}",
        }])
    rows.append([{
        "text": "🎲 Use all (mix across packages)",
        "callback_data": "hunt:rq:all",
    }])
    rows.append([
        {"text": "✍️ I'll write my own questions", "callback_data": "hunt:rq:custom"},
    ])
    rows.append([
        {"text": "↩ Back to review", "callback_data": "hunt:back_to_review"},
        {"text": "❌ Cancel", "callback_data": "hunt:cancel"},
    ])
    return {"inline_keyboard": rows}
