#!/usr/bin/env python3
"""
Test suite for fanout_merge.py — Fan-out → Merge unified research workflow.

Tests the merge logic (deduplication, stat aggregation, query union) and the
sub-topic splitting without requiring network access or ollama.

Usage:  python tests/test_fanout_merge.py
"""
import sys
import os
import tempfile
from pathlib import Path

# Ensure repo root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("STATE_DIR", tempfile.mkdtemp(prefix="fanout_test_"))


def _make_paper(title, doi="", url="", year=2023, source="OpenAlex",
                 pdf_reader=None, keywords=None):
    """Helper: build a minimal paper dict."""
    p = {
        "title": title, "doi": doi, "url": url, "year": year,
        "source": source, "authors": ["Test Author"], "journal": "Test Journal",
        "abstract": "Test abstract", "downloaded": False,
    }
    if pdf_reader:
        p["pdf_reader"] = pdf_reader
    if keywords:
        p["keywords"] = keywords
    return p


def _make_report(papers, title="Test Report", field="general",
                 queries=None, platforms=None, stats=None):
    """Helper: build a minimal report_data dict."""
    return {
        "title": title, "field": field, "papers": papers,
        "ai_queries": queries or [], "queries_used": queries or [],
        "platforms_searched": platforms or [],
        "study_keywords": [], "search_language": "English",
        "country_context": "International", "executive_summary": "",
        "user_filters": {}, "run_stats": stats or {
            "new_this_run": len(papers), "downloaded_this_run": 0,
            "q_distribution": {"Q1": 1, "Q2": 0, "Q3": 0, "Q4": 0, "Not Found": 0},
            "type_distribution": {"PhD": 0, "MA": 0, "Book": 0, "BookChapter": 0, "Conference": 0},
            "geo_distribution": {"Libya": 0, "Neighbor": 0, "MENA": 0},
            "red_list_count": 0, "folder_downloads": 0,
        },
    }


def test_dedup_by_doi():
    """Papers with the same DOI should be deduplicated."""
    from fanout_merge import merge_reports
    p1 = _make_paper("Paper A", doi="10.1234/test.001")
    p2 = _make_paper("Paper A (duplicate)", doi="10.1234/test.001")
    p3 = _make_paper("Paper B", doi="10.1234/test.002")
    r1 = _make_report([p1, p3], title="Sub 1")
    r2 = _make_report([p2], title="Sub 2")
    merged = merge_reports([r1, r2])
    assert len(merged["papers"]) == 2, f"Expected 2 papers, got {len(merged['papers'])}"
    assert merged["run_stats"]["duplicates_removed"] == 1
    print("[test] Dedup by DOI: 3 → 2 papers, 1 duplicate removed ✓")


def test_dedup_by_title_hash():
    """Papers with same title (no DOI) should dedup by title hash."""
    from fanout_merge import merge_reports
    p1 = _make_paper("The Effects of AI on Education: A Comprehensive Study")
    p2 = _make_paper("The Effects of AI on Education: A Comprehensive Study")  # exact dup
    p3 = _make_paper("A Completely Different Paper About Chemistry")
    r1 = _make_report([p1], title="Sub 1")
    r2 = _make_report([p2, p3], title="Sub 2")
    merged = merge_reports([r1, r2])
    assert len(merged["papers"]) == 2, f"Expected 2, got {len(merged['papers'])}"
    assert merged["run_stats"]["duplicates_removed"] == 1
    print("[test] Dedup by title hash: 3 → 2 papers, 1 duplicate removed ✓")


def test_dedup_by_url():
    """Papers with same URL (no DOI/title-match) should dedup."""
    from fanout_merge import merge_reports
    p1 = _make_paper("Short", url="https://example.com/paper1")
    p2 = _make_paper("Also Short", url="https://example.com/paper1")
    r1 = _make_report([p1], title="Sub 1")
    r2 = _make_report([p2], title="Sub 2")
    merged = merge_reports([r1, r2])
    assert len(merged["papers"]) == 1, f"Expected 1, got {len(merged['papers'])}"
    print("[test] Dedup by URL: 2 → 1 paper ✓")


def test_stat_aggregation():
    """Stats from multiple reports should be summed correctly."""
    from fanout_merge import merge_reports
    p1 = _make_paper("Paper A", doi="10.1/a")
    p2 = _make_paper("Paper B", doi="10.1/b")
    p3 = _make_paper("Paper C", doi="10.1/c")
    r1 = _make_report([p1], title="Sub 1", stats={
        "new_this_run": 10, "downloaded_this_run": 5,
        "q_distribution": {"Q1": 3, "Q2": 1, "Q3": 0, "Q4": 0, "Not Found": 0},
        "type_distribution": {"PhD": 2, "MA": 1, "Book": 0, "BookChapter": 0, "Conference": 0},
        "geo_distribution": {"Libya": 1, "Neighbor": 0, "MENA": 0},
        "red_list_count": 1, "folder_downloads": 2,
    })
    r2 = _make_report([p2, p3], title="Sub 2", stats={
        "new_this_run": 20, "downloaded_this_run": 10,
        "q_distribution": {"Q1": 2, "Q2": 3, "Q3": 1, "Q4": 0, "Not Found": 0},
        "type_distribution": {"PhD": 1, "MA": 0, "Book": 1, "BookChapter": 0, "Conference": 1},
        "geo_distribution": {"Libya": 0, "Neighbor": 1, "MENA": 1},
        "red_list_count": 2, "folder_downloads": 3,
    })
    merged = merge_reports([r1, r2])
    rs = merged["run_stats"]
    assert rs["new_this_run"] == 30, f"Expected 30, got {rs['new_this_run']}"
    assert rs["downloaded_this_run"] == 15
    assert rs["q_distribution"]["Q1"] == 5
    assert rs["q_distribution"]["Q2"] == 4
    assert rs["type_distribution"]["PhD"] == 3
    assert rs["geo_distribution"]["MENA"] == 1
    assert rs["red_list_count"] == 3
    assert rs["sub_reports_merged"] == 2
    print("[test] Stat aggregation: new=30, dl=15, Q1=5, PhD=3 ✓")


def test_query_platform_union():
    """Queries and platforms should be unioned (deduplicated, ordered)."""
    from fanout_merge import merge_reports
    p = _make_paper("P", doi="10.1/x")
    r1 = _make_report([p], title="S1",
                      queries=["AI in education", "machine learning"],
                      platforms=["OpenAlex", "CrossRef"])
    r2 = _make_report([_make_paper("Q", doi="10.1/y")], title="S2",
                      queries=["machine learning", "neural networks"],
                      platforms=["CrossRef", "Semantic Scholar"])
    merged = merge_reports([r1, r2])
    assert "AI in education" in merged["ai_queries"]
    assert "machine learning" in merged["ai_queries"]
    assert "neural networks" in merged["ai_queries"]
    # machine learning should appear only once
    assert merged["ai_queries"].count("machine learning") == 1
    assert "OpenAlex" in merged["platforms_searched"]
    assert "Semantic Scholar" in merged["platforms_searched"]
    assert merged["platforms_searched"].count("CrossRef") == 1
    print("[test] Query/platform union: deduped and ordered ✓")


def test_pdf_reader_merge():
    """When the same paper appears in 2 sub-hunts, pdf_reader data should merge."""
    from fanout_merge import merge_reports
    p1 = _make_paper("Deep Paper", doi="10.1/deep",
                      pdf_reader={"sections": {"Intro": {"text": "A", "pages": "1"}},
                                  "quotes": [{"quote": "Q1", "page": "1"}],
                                  "pages_read": 5, "text_length": 5000},
                      keywords=["AI", "education"])
    p2 = _make_paper("Deep Paper", doi="10.1/deep",
                      pdf_reader={"sections": {"Method": {"text": "B", "pages": "2"}},
                                  "quotes": [{"quote": "Q2", "page": "2"}],
                                  "pages_read": 10, "text_length": 8000},
                      keywords=["education", "neural"])
    r1 = _make_report([p1], title="S1")
    r2 = _make_report([p2], title="S2")
    merged = merge_reports([r1, r2])
    assert len(merged["papers"]) == 1
    paper = merged["papers"][0]
    pr = paper.get("pdf_reader", {})
    sections = pr.get("sections", {})
    assert "Intro" in sections, f"Missing Intro: {list(sections.keys())}"
    assert "Method" in sections, f"Missing Method: {list(sections.keys())}"
    # keywords should union
    kws = paper.get("keywords", [])
    assert "AI" in kws and "education" in kws and "neural" in kws
    print("[test] PDF reader + keyword merge: sections + keywords unioned ✓")


def test_split_into_subhunts_by_rq():
    """split_into_subhunts should create one sub-hunt per research question."""
    from fanout_merge import split_into_subhunts
    params = {
        "title": "AI in Education",
        "field": "Education",
        "research_questions": ["How does AI affect learning?", "What are the ethical concerns?"],
        "platforms": ["all"],
    }
    subhunts = split_into_subhunts(params)
    assert len(subhunts) == 2, f"Expected 2 sub-hunts, got {len(subhunts)}"
    assert "RQ1" in subhunts[0]["_subhunt_label"]
    assert "RQ2" in subhunts[1]["_subhunt_label"]
    assert "How does AI affect learning?" in subhunts[0]["title"]
    assert subhunts[0]["research_questions"] == ["How does AI affect learning?"]
    assert subhunts[1]["research_questions"] == ["What are the ethical concerns?"]
    print("[test] Split by research questions: 2 sub-hunts ✓")


def test_split_into_subhunts_by_keywords():
    """split_into_subhunts should fall back to keywords when no RQs."""
    from fanout_merge import split_into_subhunts
    params = {
        "title": "Climate Change",
        "field": "Environmental Science",
        "study_keywords": ["carbon capture", "renewable energy"],
    }
    subhunts = split_into_subhunts(params)
    assert len(subhunts) == 2
    assert "Aspect1" in subhunts[0]["_subhunt_label"]
    assert "Aspect2" in subhunts[1]["_subhunt_label"]
    print("[test] Split by keywords: 2 sub-hunts ✓")


def test_split_no_subtopics():
    """With no RQs or keywords, should return single-element list."""
    from fanout_merge import split_into_subhunts
    params = {"title": "Generic Topic", "field": "general"}
    subhunts = split_into_subhunts(params)
    assert len(subhunts) == 1
    assert subhunts[0]["title"] == "Generic Topic"
    print("[test] No sub-topics: single hunt ✓")


def test_single_report_passthrough():
    """Merging a single report should just enrich it, not dedup."""
    from fanout_merge import merge_reports
    p = _make_paper("Solo", doi="10.1/solo")
    r = _make_report([p], title="Only Report")
    merged = merge_reports([r], unified_title="Unified", unified_field="CS")
    assert merged["title"] == "Unified"
    assert merged["field"] == "CS"
    assert len(merged["papers"]) == 1
    print("[test] Single report passthrough: title/field overridden ✓")


def test_empty_merge():
    """Merging zero reports should return empty dict."""
    from fanout_merge import merge_reports
    merged = merge_reports([])
    assert merged == {}
    print("[test] Empty merge: returns {} ✓")


def test_doi_normalization():
    """DOI normalization should strip prefixes and lowercase."""
    from fanout_merge import _norm_doi, _paper_key
    assert _norm_doi("https://doi.org/10.1234/ABC") == "10.1234/abc"
    assert _norm_doi("DOI: 10.1234/test") == "10.1234/test"
    assert _norm_doi("") == ""
    assert _norm_doi(None) == ""
    # Paper key should prefer DOI
    p = {"doi": "10.1234/x", "title": "Some Title", "url": "https://x.com"}
    assert _paper_key(p) == ("doi", "10.1234/x")
    # No DOI → title hash
    p2 = {"title": "A Very Long Paper Title About Something", "url": "https://x.com"}
    kind, val = _paper_key(p2)
    assert kind == "title"
    # No DOI, short title → URL
    p3 = {"title": "short", "url": "https://example.com/p"}
    kind, val = _paper_key(p3)
    assert kind == "url"
    print("[test] DOI normalization + paper key priority: DOI→title→URL ✓")


def test_build_matrix():
    """build_matrix should produce a string-only matrix, one entry per sub-hunt."""
    from fanout_merge import build_matrix
    # 2 RQs → 2 matrix legs
    params = {"title": "AI in Education", "field": "Education",
              "research_questions": ["RQ one?", "RQ two?"]}
    m = build_matrix(params)
    assert len(m) == 2, f"Expected 2 legs, got {len(m)}"
    assert all(isinstance(v, str) for leg in m for v in leg.values()), "matrix values must be strings"
    assert m[0]["label"] == "RQ1" and m[1]["label"] == "RQ2"
    assert m[0]["index"] == "0" and m[1]["index"] == "1"
    assert "AI in Education" in m[0]["subhunt_title"]
    # No sub-topics → single leg
    m1 = build_matrix({"title": "Generic", "field": "general"})
    assert len(m1) == 1
    assert m1[0]["label"] in ("single", "Sub1")
    print("[test] build_matrix: 2 RQs → 2 legs, no RQ → 1 leg, all string values ✓")


def main():
    tests = [
        test_dedup_by_doi,
        test_dedup_by_title_hash,
        test_dedup_by_url,
        test_stat_aggregation,
        test_query_platform_union,
        test_pdf_reader_merge,
        test_split_into_subhunts_by_rq,
        test_split_into_subhunts_by_keywords,
        test_split_no_subtopics,
        test_single_report_passthrough,
        test_empty_merge,
        test_doi_normalization,
        test_build_matrix,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"[FAIL] {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
    print("=" * 60)
    if failed == 0:
        print(f"  ALL TESTS PASSED ({passed}/{passed})")
    else:
        print(f"  {passed} passed, {failed} failed")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
