#!/usr/bin/env python3
"""
tests/test_synthesis_engine.py — tests for the v7 deep synthesis engine.

Run: python tests/test_synthesis_engine.py
All tests are offline (no ollama, no network, no PDFs).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synthesis_engine import (
    cluster_papers_by_theme, build_citation_network, detect_convergence,
    map_methodological_lineage, extract_thematic_quotes, identify_research_gaps,
    synthesize, _cite, _full_cite, _short_authors, _tokenize,
)
from deep_reader import clean_academic_text

_PASSED = 0
_FAILED = 0

def check(label, cond):
    global _PASSED, _FAILED
    if cond:
        _PASSED += 1
        print(f"  PASS  {label}")
    else:
        _FAILED += 1
        print(f"  FAIL  {label}")

def _make_paper(title, authors, year, sections=None, abstract="", keywords=None):
    p = {"title": title, "authors": authors, "year": year, "journal": "J",
         "doi": "", "url": "", "pdf_url": "", "source": "test", "abstract": abstract,
         "downloaded": bool(sections), "keywords": keywords or []}
    if sections:
        p["pdf_reader"] = {"sections": sections, "quotes": [], "pages_read": 10, "text_length": 5000}
    return p

def _sec(text, pages="1"):
    return {"text": text, "pages": pages}


print("\n[Test] Citation helpers")
check("short authors 2", _short_authors({"authors": ["John Smith", "Jane Doe"]}) == "J. Smith & J. Doe")
check("short authors 3 -> et al", _short_authors({"authors": ["A One", "B Two", "C Three"]}) == "A. One et al.")
check("short authors empty", _short_authors({"authors": []}) == "Anon")
check("cite has year", "2023" in _cite({"authors": ["X Y"], "year": "2023"}))
check("full cite narrative", "John Smith" in _full_cite({"authors": ["John Smith"], "year": "2020"}))
check("full cite et al", "et al." in _full_cite({"authors": ["A", "B", "C"], "year": "2021"}))

print("\n[Test] Tokenize")
toks = _tokenize("The students learned grammar through writing exercises")
check("stopwords removed", "the" not in toks and "through" not in toks)
check("content kept", "students" in toks and "grammar" in toks)
check("short words filtered", all(len(t) >= 3 for t in toks))
check("empty input", _tokenize("") == [])

print("\n[Test] Thematic clustering")
papers = [
    _make_paper("AI Tutors in Writing", ["A One"], "2023", {"Methodology": _sec("mixed methods ANOVA")}, "AI writing ESL grammar"),
    _make_paper("Automated Feedback Effects", ["B Two"], "2022", {"Methodology": _sec("qualitative interview")}, "AI feedback writing ESL"),
    _make_paper("Unrelated Ocean Chemistry", ["C Three"], "2021", {"Methodology": _sec("ocean sampling")}, "ocean chemistry marine biology"),
]
clusters = cluster_papers_by_theme(papers)
check("clusters found", len(clusters) >= 1)
check("writing papers cluster together", any("writing" in str(c["keywords"]) for c in clusters))
check("cluster has size >= 2", any(c["size"] >= 2 for c in clusters))
check("empty input no crash", cluster_papers_by_theme([]) == [])

print("\n[Test] Citation network")
citing = _make_paper("New Study on Writing", ["A New"], "2024",
    {"Introduction": _sec("Prior work by Old (2020) explored this. The writing study addressed gaps."),
     "Results": _sec("These results are consistent with prior work."),
     "Discussion": _sec("We extend the writing methodology of prior research.")})
cited = _make_paper("Old Writing Study", ["Z Old"], "2020",
    {"Methodology": _sec("We used a mixed methods design with surveys and ANOVA."),
     "Results": _sec("Writing improved over time.")})
net = build_citation_network([citing, cited])
check("edges found", len(net["edges"]) >= 1)
check("most_cited exists", isinstance(net["most_cited"], list))
check("empty input", build_citation_network([]) == {"edges": [], "matrix": {}, "most_cited": []})

print("\n[Test] Convergence detection")
conv_papers = [
    _make_paper("Study A", ["A Auth"], "2023",
        {"Results": _sec("The grammar scores improved significantly. These results are consistent with prior findings."),
         "Discussion": _sec("The findings confirm that AI feedback helps writing.")}),
    _make_paper("Study B", ["B Auth"], "2022",
        {"Results": _sec("Grammar improvement was observed. The results align with existing research."),
         "Discussion": _sec("We confirm that feedback supports learning.")}),
]
conv = detect_convergence(conv_papers)
check("convergent found", len(conv["convergent"]) >= 1)
check("convergent has strength", all("strength" in c for c in conv["convergent"]))
check("empty input", detect_convergence([]) == {"convergent": [], "divergent": []})

print("\n[Test] Methodology lineage")
lin_papers = [
    _make_paper("Qual Study", ["A Q"], "2020", {"Methodology": _sec("We conducted a qualitative case study with interviews and thematic analysis.")}),
    _make_paper("Mixed Study", ["B M"], "2023", {"Methodology": _sec("We used a mixed methods design. Statistical analysis used ANOVA. 50 students participated.")}),
    _make_paper("Quant Study", ["C Q"], "2024", {"Methodology": _sec("A quantitative survey with regression analysis. 200 respondents completed the questionnaire.")}),
]
lin = map_methodological_lineage(lin_papers)
check("lineage has entries", len(lin["lineage"]) == 3)
check("lineage sorted by year", lin["lineage"][0]["year"] <= lin["lineage"][-1]["year"])
check("qualitative detected", lin["design_counts"].get("qualitative", 0) >= 1)
check("mixed methods detected", lin["design_counts"].get("mixed methods", 0) >= 1)
check("quantitative detected", lin["design_counts"].get("quantitative", 0) >= 1)
check("sample extracted", any("50" in m["sample"] or "200" in m["sample"] for m in lin["lineage"]))
check("empty input", map_methodological_lineage([])["lineage"] == [])

print("\n[Test] Thematic quotes")
q_papers = [
    _make_paper("AI Study", ["A One"], "2023",
        {"Introduction": _sec("AI tutors significantly improve grammar acquisition in ESL learners."),
         "Results": _sec("The 23% improvement in grammar confirms AI feedback effectiveness.")},
        keywords=["AI", "grammar"]),
    _make_paper("Writing Study", ["B Two"], "2022",
        {"Results": _sec("Writing development was measured using corpus methods and grammar analysis.")},
        keywords=["writing", "corpus"]),
]
quotes = extract_thematic_quotes(q_papers, ["AI", "grammar"], max_quotes=5)
check("quotes found", len(quotes) >= 1)
check("quote has citation", all("citation" in q for q in quotes))
check("quote has score", all("score" in q for q in quotes))
check("quotes sorted by score", quotes == sorted(quotes, key=lambda x: x["score"], reverse=True))
check("page in citation when present",
      "p." in extract_thematic_quotes(
          [{"authors":["A"],"year":"2020","pdf_reader":{"quotes":[{"quote":"AI helps grammar significantly.","page":"7","keywords":["AI"]}]}}],
          ["AI"])[0]["citation"])
check("empty keywords no crash", extract_thematic_quotes(q_papers, []) == [])
check("acronym keyword kept", len(extract_thematic_quotes(q_papers, ["AI"])) >= 1)

print("\n[Test] Research gaps")
gap_papers = [
    _make_paper("Paper 1", ["A"], "2023", {"Methodology": _sec("quantitative survey")}),
    _make_paper("Paper 2", ["B"], "2021", {"Methodology": _sec("quantitative regression")}),
    _make_paper("Paper 3", ["C"], "2022"),
]
gaps = identify_research_gaps(gap_papers)
check("gaps found", len(gaps) >= 1)
check("gap has type", all("type" in g for g in gaps))
check("gap has severity", all("severity" in g for g in gaps))
check("methodological gap flagged", any(g["type"] == "methodological" for g in gaps))
check("empty input", identify_research_gaps([]) == [])

print("\n[Test] Full synthesize bundle")
bundle = synthesize(lin_papers)
check("bundle has themes", "themes" in bundle)
check("bundle has citation_network", "citation_network" in bundle)
check("bundle has convergence", "convergence" in bundle)
check("bundle has methodology_lineage", "methodology_lineage" in bundle)
check("bundle has gaps", "gaps" in bundle)
check("bundle has quotes_by_theme", "quotes_by_theme" in bundle)
check("bundle has stats", "stats" in bundle)
check("stats has total_papers", bundle["stats"]["total_papers"] == 3)
check("synthesize empty no crash", synthesize([])["stats"]["total_papers"] == 0)

print("\n[Test] Never crashes on malformed input")
check("None papers no crash", synthesize(None)["stats"]["total_papers"] == 0)
malformed = [{"title": "No fields"}, {"authors": ["X"], "year": None}, {}]
check("malformed papers no crash", isinstance(synthesize(malformed), dict))

print("\n============================================================")
print(f"Results: {_PASSED} passed, {_FAILED} failed")
print("============================================================")
sys.exit(1 if _FAILED else 0)
