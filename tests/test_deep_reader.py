#!/usr/bin/env python3
"""Tests for deep_reader — section detection, quote mining, text cleanup.

Run: python tests/test_deep_reader.py
No network, no ollama, no PDFs required.
"""
import sys
import os
from pathlib import Path

# Allow running from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from deep_reader import (
    detect_sections,
    mine_quotes,
    clean_academic_text,
    read_pdf_deeply,
    enrich_paper,
    SECTION_ORDER,
)

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


SAMPLE_HEADING = """Title: AI in Education

1. Introduction
AI tools are changing education. Students use them daily.

2. Literature Review
Smith (2020) studied AI tutors. Jones (2021) found benefits. Lee (2022) disagreed.

3. Methodology
We surveyed 300 students over one year.

4. Results
Scores improved by 20%. Originality dropped 5%.

5. Discussion
The results confirm Smith's findings but partly support Lee's critique.

6. Conclusion
AI helps structurally but needs careful use.
"""

SAMPLE_NO_HEADINGS = (
    "AI is transforming education in many ways. Students now use AI tools "
    "for writing and research. The literature shows mixed results across studies. "
    "Smith found improvements while Lee found concerns. Our methodology involved "
    "300 students surveyed over a year. We collected both quantitative and "
    "qualitative data. The results showed a 20% improvement in structure. "
    "However originality dropped by 5%. These findings suggest AI helps with "
    "form but may reduce creative depth. We conclude that AI tools offer "
    "benefits but require pedagogical oversight to be effective."
)


def test_section_detection_headings():
    print("\n[Test] Section detection via headings")
    sec = detect_sections(SAMPLE_HEADING)
    for key in SECTION_ORDER:
        v = sec[key]
        check(f"{key} detected via heading", not v["inferred"] and v["char_count"] > 0,
              f"inferred={v['inferred']} chars={v['char_count']}")
    # Introduction should mention AI/education.
    check("intro content correct", "AI tools" in sec["introduction"]["text"])
    # Methodology should mention survey/students.
    check("methodology content correct", "300 students" in sec["methodology"]["text"])


def test_section_detection_position_fallback():
    print("\n[Test] Section detection position fallback (no headings)")
    sec = detect_sections(SAMPLE_NO_HEADINGS)
    inferred_count = sum(1 for k in SECTION_ORDER if sec[k]["inferred"])
    check("falls back to position when <2 headings", inferred_count == len(SECTION_ORDER),
          f"inferred_count={inferred_count}")
    # Each section should have some text.
    for key in SECTION_ORDER:
        check(f"{key} has text in fallback", sec[key]["char_count"] > 0)


def test_section_detection_empty():
    print("\n[Test] Section detection on empty/tiny text")
    sec = detect_sections("")
    check("empty returns all sections", len(sec) == len(SECTION_ORDER))
    check("empty sections have no text", all(sec[k]["char_count"] == 0 for k in SECTION_ORDER))
    sec2 = detect_sections("short")
    check("tiny text returns all sections", len(sec2) == len(SECTION_ORDER))


def test_quote_mining():
    print("\n[Test] Quote mining")
    text = "Artificial intelligence helps students write better. The weather is nice today. AI feedback improves drafts significantly. Cats are popular pets."
    quotes = mine_quotes(text, ["artificial intelligence", "AI"], max_per_section=5)
    check("quotes found", len(quotes) >= 2, f"got {len(quotes)}")
    check("quotes contain keywords", all("AI" in q["quote"] or "artificial" in q["quote"].lower() for q in quotes))
    check("quotes sorted by score", quotes[0]["score"] >= quotes[-1]["score"])
    # Empty input.
    check("empty text no quotes", mine_quotes("", ["AI"]) == [])
    check("no keywords no quotes", mine_quotes("some text", []) == [])


def test_quote_length_bounds():
    print("\n[Test] Quote length bounds")
    long_text = "AI " * 200 + ". " + "short. " + "AI matters."
    quotes = mine_quotes(long_text, ["AI"])
    for q in quotes:
        check("quote >=30 chars", len(q["quote"]) >= 30, f"len={len(q['quote'])}")
        check("quote <=400 chars", len(q["quote"]) <= 400, f"len={len(q['quote'])}")


def test_clean_academic_text():
    print("\n[Test] Text cleanup")
    dirty = "It is important to note that *I found* the results\u2014which were significant\u2014to be **very** compelling. In conclusion, delve into the data."
    clean = clean_academic_text(dirty)
    check("removes 'I found'", "*I found*" not in clean and "I found" not in clean, clean)
    check("removes 'important to note'", "important to note" not in clean.lower(), clean)
    check("removes em-dash", "\u2014" not in clean, clean)
    check("removes bold markers", "**" not in clean, clean)
    check("removes 'In conclusion'", "In conclusion" not in clean, clean)
    check("removes 'delve into'", "delve into" not in clean.lower(), clean)
    check("empty input", clean_academic_text("") == "")


def test_clean_artifacts():
    print("\n[Test] Cleanup of markdown artifacts")
    dirty = "## Heading\n\nSome [1] text with [12] markers and --- horizontal rule."
    clean = clean_academic_text(dirty)
    check("removes markdown header #", "##" not in clean, clean)
    check("removes [1] markers", "[1]" not in clean, clean)
    check("removes [12] markers", "[12]" not in clean, clean)


def test_curly_quotes():
    print("\n[Test] Curly quote normalization")
    dirty = "She said \u201Chello\u201D and \u2018bye\u2019."
    clean = clean_academic_text(dirty)
    check("curly double quotes normalized", "\u201C" not in clean and "\u201D" not in clean, clean)
    check("curly single quotes normalized", "\u2018" not in clean and "\u2019" not in clean, clean)


def test_read_pdf_nonexistent():
    print("\n[Test] read_pdf_deeply on non-existent PDF")
    r = read_pdf_deeply(Path("/nonexistent_file_xyz.pdf"), ["AI"])
    check("reader is none", r["pdf_reader"] == "none")
    check("no text", r["pdf_text_length"] == 0)
    check("no quotes", len(r["pdf_quotes"]) == 0)
    check("has all section keys", len(r["pdf_sections"]) == len(SECTION_ORDER))


def test_enrich_paper_no_pdf():
    print("\n[Test] enrich_paper without PDF (no-op)")
    paper = {"title": "Test"}
    enrich_paper(paper, Path("/nonexistent.pdf"), ["AI"])
    check("pdf_text_length set", paper.get("pdf_text_length") == 0)
    check("pdf_sections present", "pdf_sections" in paper)
    check("pdf_quotes present", "pdf_quotes" in paper)
    check("pdf_reader is none", paper.get("pdf_reader") == "none")


def test_enrich_paper_none_path():
    print("\n[Test] enrich_paper with None path (no crash)")
    paper = {"title": "Test"}
    enrich_paper(paper, None, ["AI"])  # type: ignore
    check("did not crash", "title" in paper)


def main():
    print("=" * 60)
    print("deep_reader tests")
    print("=" * 60)
    test_section_detection_headings()
    test_section_detection_position_fallback()
    test_section_detection_empty()
    test_quote_mining()
    test_quote_length_bounds()
    test_clean_academic_text()
    test_clean_artifacts()
    test_curly_quotes()
    test_read_pdf_nonexistent()
    test_enrich_paper_no_pdf()
    test_enrich_paper_none_path()
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
