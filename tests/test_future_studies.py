"""
tests/test_future_studies.py — Unit tests for the future_studies module.

Verifies:
  - Module imports cleanly
  - _parse_ai_response correctly parses structured AI output
  - _deterministic_fallback always returns suggestions
  - generate_future_studies works with no ollama (uses fallback)
  - to_markdown produces a clean markdown section
  - max_suggestions is respected
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import future_studies  # noqa: E402


def test_module_imports():
    """future_studies module loads with all expected functions."""
    for fn in ("generate_future_studies", "to_markdown",
               "_parse_ai_response", "_deterministic_fallback", "_safe_str"):
        assert hasattr(future_studies, fn), f"missing {fn}"
    print("[test] Module imports OK")


def test_safe_str_handles_types():
    """_safe_str handles None, dict, list, str, int cleanly."""
    assert future_studies._safe_str(None) == ""
    assert future_studies._safe_str("hello") == "hello"
    assert future_studies._safe_str(42) == "42"
    assert "k" in future_studies._safe_str({"k": "v"})
    assert "a" in future_studies._safe_str(["a", "b"])
    print("[test] _safe_str handles all input types")


def test_parse_ai_response_single_block():
    """A single structured block is parsed correctly."""
    raw = """TITLE: A new study on ML in education
TYPE: PhD Dissertation
RQ1: What is the impact?
RQ2: How is it measured?
RQ3: What factors matter?
AIM1: To investigate
AIM2: To explore
AIM3: To identify
METHODOLOGY: Mixed-methods
SIGNIFICANCE: Important
ADVANTAGES: Novel
SUMMARY: A summary
---"""
    result = future_studies._parse_ai_response(raw)
    assert len(result) == 1, f"Expected 1 suggestion, got {len(result)}"
    s = result[0]
    assert s["title"] == "A new study on ML in education"
    assert s["type"] == "PhD Dissertation"
    assert s["rq1"] == "What is the impact?"
    assert s["methodology"] == "Mixed-methods"
    print("[test] _parse_ai_response parses a single block correctly")


def test_parse_ai_response_multiple_blocks():
    """Multiple blocks separated by --- are all parsed."""
    raw = """TITLE: Study 1
TYPE: MA Dissertation
RQ1: Q1
AIM1: A1
METHODOLOGY: M1
---
TITLE: Study 2
TYPE: PhD Dissertation
RQ1: Q1
AIM1: A1
METHODOLOGY: M2
---
TITLE: Study 3
TYPE: Article
RQ1: Q1
AIM1: A1
METHODOLOGY: M3"""
    result = future_studies._parse_ai_response(raw)
    assert len(result) == 3, f"Expected 3 suggestions, got {len(result)}"
    assert [s["title"] for s in result] == ["Study 1", "Study 2", "Study 3"]
    print("[test] _parse_ai_response parses multiple blocks")


def test_parse_ai_response_empty():
    """Empty or very short input returns empty list."""
    assert future_studies._parse_ai_response("") == []
    assert future_studies._parse_ai_response("hi") == []  # < 100 chars
    print("[test] _parse_ai_response returns [] for empty/short input")


def test_parse_ai_response_ignores_blocks_without_title():
    """Blocks without a TITLE are dropped."""
    raw = """TITLE:
TYPE: Missing
RQ1: No title block
AIM1: A
SIGNIFICANCE: S
ADVANTAGES: AD
SUMMARY: SM
---
TITLE: Valid block
TYPE: MA Dissertation
RQ1: Q
AIM1: A
METHODOLOGY: Mixed-methods
SIGNIFICANCE: Important
ADVANTAGES: Novel
SUMMARY: A summary"""
    result = future_studies._parse_ai_response(raw)
    assert len(result) == 1, f"Expected 1, got {len(result)}"
    assert result[0]["title"] == "Valid block"
    print("[test] _parse_ai_response drops blocks without TITLE")


def test_deterministic_fallback_returns_5():
    """_deterministic_fallback always returns 5 suggestions."""
    result = future_studies._deterministic_fallback(
        "ML in education", "education", "Libya", "MENA"
    )
    assert len(result) == 5
    for s in result:
        assert s.get("title")
        assert s.get("type")
        assert s.get("methodology")
    print("[test] _deterministic_fallback returns 5 suggestions")


def test_generate_future_studies_no_ollama():
    """When ollama fails, generate_future_studies still returns suggestions
    via the deterministic fallback."""
    with patch("precision_engine._call_ollama", return_value=""):
        result = future_studies.generate_future_studies(
            title="ML in education", field="education",
            papers=[{"title": "Paper 1", "journal": "Journal A"}],
            country_context=["Libya", "MENA"],
            max_suggestions=5,
        )
    assert len(result) == 5, f"Expected 5, got {len(result)}"
    for s in result:
        assert s.get("title")
    print(f"[test] generate_future_studies (no ollama): PASS ({len(result)} fallback suggestions)")


def test_generate_future_studies_with_ollama():
    """When ollama gives a valid response, the AI suggestions are used."""
    ai_response = """TITLE: AI-generated study 1 on advanced machine learning in higher education
TYPE: PhD Dissertation
RQ1: What is the impact of ML on student outcomes?
RQ2: How do faculty adopt ML tools in teaching?
RQ3: What barriers exist for adoption in MENA universities?
AIM1: To investigate the impact of ML on learning outcomes
AIM2: To explore faculty adoption patterns
AIM3: To identify systemic barriers
METHODOLOGY: Mixed-methods with surveys and interviews
SIGNIFICANCE: Addresses a critical gap in MENA higher education research
ADVANTAGES: Novel context with rigorous design
SUMMARY: A comprehensive study that fills a clear gap in the literature
---
TITLE: AI-generated study 2 on AI literacy programs in Libyan schools
TYPE: MA Dissertation
RQ1: How effective are AI literacy programs for teachers?
RQ2: What training is needed for sustainable adoption?
AIM1: To evaluate program effectiveness
AIM2: To identify training gaps
METHODOLOGY: Qualitative case study with focus groups
SIGNIFICANCE: First study of AI literacy in Libyan K-12 context
ADVANTAGES: Rich qualitative data, practical implications
SUMMARY: A focused study on a novel context"""
    with patch("precision_engine._call_ollama", return_value=ai_response):
        result = future_studies.generate_future_studies(
            title="ML", field="education", papers=[],
            max_suggestions=5,
        )
    assert len(result) == 5
    # First 2 should be AI-generated, rest are fallback
    assert "AI-generated" in result[0]["title"]
    assert "AI-generated" in result[1]["title"]
    print(f"[test] generate_future_studies (with ollama): PASS "
          f"({len(result)} suggestions, 2 AI + 3 fallback)")


def test_generate_future_studies_respects_max():
    """max_suggestions is strictly respected."""
    with patch("precision_engine._call_ollama", return_value=""):
        result = future_studies.generate_future_studies(
            title="T", field="F", papers=[], max_suggestions=3,
        )
    assert len(result) == 3, f"Expected 3, got {len(result)}"
    print(f"[test] max_suggestions respected: PASS (3 of 3)")


def test_to_markdown_empty():
    """to_markdown returns empty string for empty list."""
    assert future_studies.to_markdown([]) == ""
    print("[test] to_markdown handles empty list")


def test_to_markdown_renders_well():
    """to_markdown produces a clean markdown section."""
    suggestions = [{
        "title": "Test Study",
        "type": "PhD",
        "rq1": "Q1", "rq2": "Q2", "rq3": "Q3",
        "aim1": "A1", "aim2": "A2", "aim3": "A3",
        "methodology": "Mixed-methods",
        "significance": "Important",
        "advantages": "Novel",
        "summary": "A summary",
    }]
    md = future_studies.to_markdown(suggestions, title="ML in education")
    assert "## 🌟 Future Research Directions" in md
    assert "Test Study" in md
    assert "PhD" in md
    assert "Mixed-methods" in md
    assert "Q1" in md
    assert "A1" in md
    assert "ML in education" in md
    print(f"[test] to_markdown renders all sections ({len(md)} chars)")


# ── v6.5.1: research_questions auto-generation tests ─────────────────────


def test_generate_research_questions_no_ollama():
    """When ollama is unavailable, returns 3 deterministic RQs."""
    with patch("precision_engine._call_ollama", return_value=""):
        rqs = future_studies.generate_research_questions(
            title="ML in education", field="education",
            country_context=["Libya", "MENA"], max_questions=3,
        )
    assert len(rqs) == 3, f"Expected 3, got {len(rqs)}"
    for q in rqs:
        assert isinstance(q, str) and len(q) > 20
    assert "Libya" in rqs[1] or "local" in rqs[0] or "literature" in rqs[0]
    print(f"[test] generate_research_questions (no ollama): PASS ({len(rqs)} fallback RQs)")


def test_generate_research_questions_with_ollama():
    """When ollama gives a valid response, those RQs are used."""
    ai_response = """RQ1: How does ML impact student outcomes in MENA universities?
RQ2: What barriers prevent ML adoption in Libyan schools?
RQ3: What training programs are needed for sustainable AI adoption?"""
    with patch("precision_engine._call_ollama", return_value=ai_response):
        rqs = future_studies.generate_research_questions(
            title="ML in education", field="education", max_questions=3,
        )
    assert len(rqs) == 3
    assert "ML" in rqs[0] and "student" in rqs[0]
    assert "Libyan" in rqs[1] or "Libya" in rqs[1] or "school" in rqs[1]
    print(f"[test] generate_research_questions (with ollama): PASS (3 AI RQs)")


def test_generate_research_questions_with_ollama_partial():
    """When ollama gives fewer RQs than requested, deterministic fallback fills in."""
    ai_response = """RQ1: How does ML impact education?
RQ2: What is the adoption rate?"""
    with patch("precision_engine._call_ollama", return_value=ai_response):
        rqs = future_studies.generate_research_questions(
            title="ML in education", field="education", max_questions=3,
        )
    assert len(rqs) == 3
    # First 2 from ollama, last from fallback
    assert "ML" in rqs[0]
    print(f"[test] generate_research_questions (partial ollama): PASS (2 AI + 1 fallback = 3)")


def test_generate_research_questions_max_respected():
    """max_questions=5 returns 5 RQs."""
    with patch("precision_engine._call_ollama", return_value=""):
        rqs = future_studies.generate_research_questions(
            title="Quantum computing", field="physics", max_questions=5,
        )
    assert len(rqs) == 5
    print(f"[test] generate_research_questions max=5: PASS (5 RQs)")


if __name__ == "__main__":
    print("=" * 60)
    print("  future_studies unit tests")
    print("=" * 60)
    print()
    test_module_imports()
    test_safe_str_handles_types()
    test_parse_ai_response_single_block()
    test_parse_ai_response_multiple_blocks()
    test_parse_ai_response_empty()
    test_parse_ai_response_ignores_blocks_without_title()
    test_deterministic_fallback_returns_5()
    test_generate_future_studies_no_ollama()
    test_generate_future_studies_with_ollama()
    test_generate_future_studies_respects_max()
    test_to_markdown_empty()
    test_to_markdown_renders_well()
    test_generate_research_questions_no_ollama()
    test_generate_research_questions_with_ollama()
    test_generate_research_questions_with_ollama_partial()
    test_generate_research_questions_max_respected()
    print()
    print("=" * 60)
    print("  ALL TESTS PASSED")
    print("=" * 60)
