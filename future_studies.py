"""
future_studies.py — Generate gap-filling research study suggestions.

After a hunt completes, this module uses ollama (via precision_engine)
to suggest 3-5 genuinely new research directions that have NOT been
conducted before, based on the gaps detected in the collected literature.

Adapted from research_hunter_v2-6.py's generate_future_studies() function
(ported + simplified for our precision_engine integration).

Output:
  - List of structured suggestion dicts (title, type, RQs, aims, methodology, etc.)
  - Markdown section ready to append to the hunt report
  - Always falls back to deterministic suggestions if ollama is unavailable
"""
import re
from typing import Any, Dict, List, Optional

from logger import get_logger

log = get_logger(__name__)


def _safe_str(x: Any) -> str:
    """Safely convert any value to string (handles dicts, lists, None)."""
    if x is None:
        return ""
    if isinstance(x, dict):
        return " ".join(f"{k}: {v}" for k, v in x.items())
    if isinstance(x, list):
        return " ".join(_safe_str(i) for i in x)
    return str(x)


def _parse_ai_response(raw: str) -> List[Dict[str, str]]:
    """Parse the structured AI response into a list of suggestion dicts.

    Expected format per suggestion (separated by '---'):
        TITLE: ...
        TYPE: ...
        RQ1: ...
        RQ2: ...
        RQ3: ...
        AIM1: ...
        AIM2: ...
        AIM3: ...
        METHODOLOGY: ...
        SIGNIFICANCE: ...
        ADVANTAGES: ...
        SUMMARY: ...
    """
    if not raw or len(raw) < 100:
        return []
    blocks = re.split(r'\n---+\n', raw)
    suggestions: List[Dict[str, str]] = []
    keys_to_find = ["TITLE", "TYPE", "RQ1", "RQ2", "RQ3", "AIM1", "AIM2", "AIM3",
                    "METHODOLOGY", "SIGNIFICANCE", "ADVANTAGES", "SUMMARY"]
    for block in blocks:
        if not block.strip():
            continue
        s: Dict[str, str] = {}
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue
            head, _, value = stripped.partition(":")
            head_clean = head.strip().upper()
            value_clean = value.strip()
            if head_clean in keys_to_find and value_clean:
                s[head_clean.lower()] = value_clean
        if s.get("title"):
            suggestions.append(s)
    return suggestions


def _deterministic_fallback(title: str, field: str,
                             country: str, region: str) -> List[Dict[str, str]]:
    """Hardcoded fallback suggestions if ollama is unavailable.
    Generates 5 template-based study suggestions using the title/field/country."""
    base_field = field.split("/")[0].strip() or "the field"
    country_safe = country or "the local context"
    region_safe = region or "the regional context"
    templates = [
        {
            "type": "PhD Dissertation",
            "methodology": "Mixed-methods: questionnaire + semi-structured interviews",
            "significance": "Addresses an underexplored intersection of theory and local practice.",
            "advantages": "Novel context, rigorous design, clear contribution to the field",
        },
        {
            "type": "MA Dissertation",
            "methodology": "Qualitative: phenomenological study with focus groups",
            "significance": "Captures lived experiences of practitioners in the field.",
            "advantages": "Rich qualitative data, practical implications, manageable scope",
        },
        {
            "type": "Research Article",
            "methodology": "Quantitative: experimental pre-test/post-test design",
            "significance": "Tests a causal relationship not yet established in the literature.",
            "advantages": "Strong evidence, publishable, replicable methodology",
        },
        {
            "type": "Systematic Review",
            "methodology": "Systematic review following PRISMA 2020 guidelines",
            "significance": "Synthesizes scattered evidence into actionable recommendations.",
            "advantages": "Comprehensive coverage, transparent methodology, high citation potential",
        },
        {
            "type": "Mixed-Methods Study",
            "methodology": "Sequential explanatory design: survey followed by interviews",
            "significance": "Combines breadth (survey) with depth (interviews) for holistic insight.",
            "advantages": "Mixed-methods rigor, complementary data, broad relevance",
        },
    ]
    topics = [
        f"The Impact of Digital Technology on {base_field} Instruction in {country_safe}",
        f"Teacher Resilience and Professional Identity in {base_field}: A {country_safe} Perspective",
        f"Learner Autonomy in {base_field}: A Comparative Study of {country_safe} and {region_safe}",
        f"AI-Assisted Tools in {base_field} Assessment: Practitioner Perceptions",
        f"Mobile-Assisted Approaches in {base_field}: Evidence from {region_safe}",
    ]
    suggestions = []
    for i, t in enumerate(topics):
        tmpl = templates[i % len(templates)]
        suggestions.append({
            "title": f"[{t}]",
            "type": tmpl["type"],
            "rq1": f"What is the current state of {t.lower()}?",
            "rq2": f"What factors influence outcomes in this context?",
            "rq3": f"What recommendations emerge from the findings?",
            "aim1": f"To investigate the current state of {t.lower()}",
            "aim2": f"To explore the factors that influence outcomes",
            "aim3": f"To develop evidence-based recommendations",
            "methodology": tmpl["methodology"],
            "significance": tmpl["significance"],
            "advantages": tmpl["advantages"],
            "summary": f"This study on '{t}' would address a clear gap in the {base_field} literature, particularly for {country_safe} contexts.",
        })
    return suggestions


def generate_future_studies(title: str, field: str,
                             papers: List[Dict[str, Any]],
                             country_context: Optional[List[str]] = None,
                             max_suggestions: int = 5) -> List[Dict[str, str]]:
    """Generate 3-5 new research study suggestions based on the literature gaps.

    Args:
        title: the research topic the user searched for
        field: the academic field (e.g., "education", "computer science")
        papers: the list of papers found by the hunt (for context)
        country_context: optional list [country, region] for localized suggestions
        max_suggestions: how many suggestions to generate (default 5, max 10)

    Returns:
        List of suggestion dicts, each with keys: title, type, rq1-3, aim1-3,
        methodology, significance, advantages, summary.
    """
    country = (country_context or ["the local context"])[0] if country_context else "the local context"
    region = country_context[1] if country_context and len(country_context) > 1 else "the regional context"
    field_safe = field or "the field"

    # Build context from found papers
    journals_found = list({
        _safe_str(p.get("journal", ""))
        for p in papers[:50]
        if p.get("journal") and len(_safe_str(p.get("journal", ""))) > 5
    })[:8]
    authors_found = []
    for p in papers[:20]:
        for a in (p.get("authors") or [])[:1]:
            s = _safe_str(a).split()
            if s:
                authors_found.append(s[-1])
    key_authors = ", ".join(authors_found[:6]) or "leading researchers in the field"

    # Try ollama first
    raw = ""
    try:
        from precision_engine import _call_ollama
        prompt = (
            f"You are a leading academic researcher in {field_safe}. "
            f"Generate exactly {max_suggestions} creative, gap-filling research study "
            f"suggestions that have NEVER been conducted before in {country} or similar contexts.\n\n"
            f"Current study: '{title}'\n"
            f"Field: {field_safe} | Region: {country} / {region}\n"
            f"Key scholars in the field: {key_authors}\n"
            f"Found {len(papers)} papers across journals: {', '.join(journals_found[:5]) or 'various'}.\n\n"
            f"For EACH of the {max_suggestions} suggestions, provide:\n"
            f"TITLE: [A specific, original, never-done-before academic title]\n"
            f"TYPE: [MA Dissertation / PhD Dissertation / Research Article / Mixed-Methods Study / Systematic Review]\n"
            f"RQ1: [First research question]\n"
            f"RQ2: [Second research question]\n"
            f"RQ3: [Third research question]\n"
            f"AIM1: [First aim — To investigate...]\n"
            f"AIM2: [Second aim — To explore...]\n"
            f"AIM3: [Third aim — To identify...]\n"
            f"METHODOLOGY: [Specific method — e.g. Mixed-methods: questionnaire + interviews]\n"
            f"SIGNIFICANCE: [Why this study matters — 2 sentences]\n"
            f"ADVANTAGES: [3 key advantages of conducting this study]\n"
            f"SUMMARY: [One paragraph explaining the study's contribution]\n"
            f"---\n"
            f"Make each title genuinely original, addressing real gaps. "
            f"Focus on pressing educational, social, or scientific problems "
            f"that have real-world community impact. "
            f"Vary types: include both MA and PhD options, articles, and reviews. "
            f"Some should be local ({country}), some regional ({region}), some global.\n"
            f"Format each suggestion with the exact labels above separated by '---' on its own line."
        )
        raw = _call_ollama(prompt, timeout=120) or ""
        log.info(f"generate_future_studies: ollama returned {len(raw)} chars")
    except Exception as e:
        log.warning(f"generate_future_studies: ollama call failed: {e}")
        raw = ""

    suggestions = _parse_ai_response(raw) if raw and len(raw) > 200 else []

    # Fallback if ollama didn't give us enough
    if len(suggestions) < max_suggestions:
        log.info(f"generate_future_studies: ollama gave {len(suggestions)}/{max_suggestions}, "
                 f"supplementing with deterministic fallback")
        fallback = _deterministic_fallback(title, field_safe, country, region)
        # Add fallbacks only if ollama didn't cover them
        existing_titles = {s.get("title", "").lower() for s in suggestions}
        for fb in fallback:
            if len(suggestions) >= max_suggestions:
                break
            if fb.get("title", "").lower() not in existing_titles:
                suggestions.append(fb)

    # Cap to max_suggestions
    suggestions = suggestions[:max_suggestions]

    log.info(f"generate_future_studies: returning {len(suggestions)} suggestions for '{title}'")
    return suggestions


def to_markdown(suggestions: List[Dict[str, str]], title: str = "") -> str:
    """Render the suggestions list as a markdown section for the report."""
    if not suggestions:
        return ""
    md = f"\n\n## 🌟 Future Research Directions\n\n"
    if title:
        md += f"_Based on gaps detected in the literature on **{title}**_\n\n"
    for i, s in enumerate(suggestions, 1):
        md += f"### {i}. {s.get('title', 'Untitled')}\n\n"
        if s.get("type"):
            md += f"**Type:** {s['type']}\n\n"
        if s.get("methodology"):
            md += f"**Methodology:** {s['methodology']}\n\n"
        rqs = [s.get(f"rq{i}", "") for i in (1, 2, 3) if s.get(f"rq{i}")]
        if rqs:
            md += "**Research Questions:**\n"
            for rq in rqs:
                md += f"- {rq}\n"
            md += "\n"
        aims = [s.get(f"aim{i}", "") for i in (1, 2, 3) if s.get(f"aim{i}")]
        if aims:
            md += "**Aims:**\n"
            for aim in aims:
                md += f"- {aim}\n"
            md += "\n"
        if s.get("significance"):
            md += f"**Significance:** {s['significance']}\n\n"
        if s.get("advantages"):
            md += f"**Advantages:** {s['advantages']}\n\n"
        if s.get("summary"):
            md += f"**Summary:** {s['summary']}\n\n"
        md += "---\n\n"
    return md


def generate_research_questions(title: str, field: str = "general",
                                  country_context: Optional[List[str]] = None,
                                  max_questions: int = 3) -> List[str]:
    """Generate research questions for the given title.

    Used as the fallback when the user skips the research_questions step
    in the /hunt2 intake. Returns 3 (configurable) questions tailored
    to the title + field + country context.

    Tries ollama first; falls back to 3 deterministic template questions.
    """
    title_safe = (title or "the topic").strip()[:200]
    field_safe = (field or "this field").strip()
    country = (country_context or ["the local context"])[0] if country_context else "the local context"

    rqs: List[str] = []
    raw = ""
    try:
        from precision_engine import _call_ollama
        prompt = (
            f"You are an experienced academic supervisor. A graduate student "
            f"is researching: '{title_safe}' in {field_safe} ({country} context).\n\n"
            f"Generate exactly {max_questions} clear, answerable research questions "
            f"that would guide a literature review + empirical study.\n\n"
            f"Format strictly as:\n"
            f"RQ1: <question>\n"
            f"RQ2: <question>\n"
            f"RQ3: <question>\n"
        )
        raw = _call_ollama(prompt, timeout=60) or ""
    except Exception as e:
        log.info(f"generate_research_questions: ollama call failed: {e}")

    if raw and len(raw) >= 50:
        for line in raw.splitlines():
            line = line.strip()
            m = re.match(r"^RQ\s*(\d+)\s*[:.]\s*(.+)$", line, re.IGNORECASE)
            if m:
                q = m.group(2).strip()
                if 10 < len(q) < 300:  # reasonable length
                    rqs.append(q)
            if len(rqs) >= max_questions:
                break

    if len(rqs) < max_questions:
        log.info(f"generate_research_questions: ollama gave {len(rqs)}/{max_questions}, "
                 f"supplementing with deterministic fallback")
        # Deterministic fallback: 6 template RQs (universally applicable) +
        # 2 country-specific ones. We pick `max_questions` of them.
        fallback = [
            f"What does the current literature say about the key concepts, "
            f"theories, and methodologies used in research on '{title_safe}'?",
            f"What gaps, contradictions, or underexplored areas exist in the "
            f"existing body of work on '{title_safe}', particularly in the "
            f"{country} context?",
            f"What research design, methodology, and analytical framework would "
            f"be most appropriate to address an identified gap in '{title_safe}' "
            f"research within {field_safe}?",
            f"What are the practical implications, applications, and policy "
            f"recommendations that emerge from the current body of work on "
            f"'{title_safe}' for stakeholders in {country}?",
            f"How have methodological approaches in '{title_safe}' evolved over "
            f"time, and what future trends are emerging in the field?",
            f"What are the main barriers, challenges, and ethical considerations "
            f"facing researchers and practitioners working on '{title_safe}' in "
            f"the {country} context?",
            f"How do sociocultural, economic, and political factors in {country} "
            f"influence the development and adoption of '{title_safe}'?",
            f"What comparative insights can be drawn from '{title_safe}' research "
            f"across different national and regional contexts?",
        ]
        existing = {q.lower()[:40] for q in rqs}
        for fq in fallback:
            if len(rqs) >= max_questions:
                break
            if fq.lower()[:40] not in existing:
                rqs.append(fq)

    log.info(f"generate_research_questions: returning {len(rqs)} questions for '{title_safe}'")
    return rqs[:max_questions]
    return md
