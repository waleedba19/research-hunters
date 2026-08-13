"""test_pipeline_db.py — Integration tests for the PaperDB-backed pipeline.

Simulates multi-chunk research accumulation (the 6-10 day continuous-run
scenario) WITHOUT network: feeds mock platform results into PaperDB across
two "chunks" and verifies:
  - chunk 1 inserts its papers incrementally,
  - chunk 2 deduplicates against chunk 1 + adds new ones,
  - a chunk with no new papers → queries_exhausted=True (chain stops),
  - results.json exported from the DB matches cumulative state,
  - chain progress keys are correct in both modes.

Run:  python3 tests/test_pipeline_db.py
No network, no ollama.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from paper_db import PaperDB  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name}  {detail}")


def _paper(title, doi, **kw):
    p = {"title": title, "authors": ["A. Author"], "year": 2024,
         "journal": "Nature", "abstract": f"Abstract for {title}.",
         "source": "mock", "doi": doi}
    p.update(kw)
    return p


def _chunk1_papers():
    return [
        _paper("Chunk1 Paper A", "10.100/c1a",
               introduction="Intro A", methodology="Method A"),
        _paper("Chunk1 Paper B", "10.100/c1b",
               results="Results B"),
        _paper("Chunk1 Paper C", "10.100/c1c"),
    ]


def _chunk2_papers():
    # B is a duplicate (same DOI); D, E are new
    return [
        _paper("Chunk1 Paper B DUP", "10.100/c1b",  # dup
               results="Results B updated"),
        _paper("Chunk2 Paper D", "10.200/c2d",
               introduction="Intro D"),
        _paper("Chunk2 Paper E", "10.200/c2e"),
    ]


def _run_chunk(db, papers, queries, paper_limit=0):
    """Mimic what run_hunt does per chunk (search→dedup→filter_new→record)."""
    db.add_queries(queries)
    new, skipped = db.filter_new(papers)
    all_papers = db.get_all_papers()
    progress = {
        "total_found": len(all_papers),
        "new_this_run": len(new),
        "queries_exhausted": bool(len(new) == 0),
        "limit_reached": bool(paper_limit and
                               len(all_papers) >= paper_limit),
    }
    db.record_run(n_found=len(new), queries_exhausted=progress["queries_exhausted"],
                  limit_reached=progress["limit_reached"], download_mode="off")
    return new, skipped, progress


# ─────────────────────────────────────────────────────────────────────────
def test_multi_chunk_accumulation():
    print("\n[1] multi-chunk accumulation + dedup + exhaustion")
    d = tempfile.mkdtemp()
    db = PaperDB(d)

    # Chunk 1
    new1, sk1, p1 = _run_chunk(db, _chunk1_papers(),
                               ["query one", "query two"])
    check("chunk1: 3 new", len(new1) == 3, str(len(new1)))
    check("chunk1: 0 skipped", sk1 == 0)
    check("chunk1: not exhausted", p1["queries_exhausted"] is False)
    check("chunk1: total 3", p1["total_found"] == 3)

    # Chunk 2: 1 dup + 2 new
    new2, sk2, p2 = _run_chunk(db, _chunk2_papers(),
                               ["query one", "query two", "query three"])
    check("chunk2: 2 new", len(new2) == 2, str(len(new2)))
    check("chunk2: 1 skipped", sk2 == 1, str(sk2))
    check("chunk2: total 5", p2["total_found"] == 5, str(p2["total_found"]))
    check("chunk2: not exhausted", p2["queries_exhausted"] is False)

    # Chunk 3: empty results → queries_exhausted (chain should stop)
    new3, sk3, p3 = _run_chunk(db, [], ["query one", "query two", "query three"])
    check("chunk3: 0 new", len(new3) == 0)
    check("chunk3: exhausted=True", p3["queries_exhausted"] is True)
    check("chunk3: total still 5", p3["total_found"] == 5)
    db.close()


def test_limit_reached_signal():
    print("\n[2] paper_limit reached → limit_reached=True")
    d = tempfile.mkdtemp()
    db = PaperDB(d)
    # 5 papers, limit 5
    _run_chunk(db, [_paper(f"L{i}", f"10.3/{i}") for i in range(5)],
               ["q1"], paper_limit=5)
    all_p = db.get_all_papers()
    check("5 papers stored", len(all_p) == 5)
    new, sk, p = _run_chunk(db, [], ["q1"], paper_limit=5)
    check("limit_reached=True", p["limit_reached"] is True)
    db.close()


def test_export_matches_db():
    print("\n[3] export_results_json matches DB state")
    d = tempfile.mkdtemp()
    db = PaperDB(d)
    _run_chunk(db, _chunk1_papers() + _chunk2_papers(),
               ["q1", "q2"])
    out = db.export_results_json(Path(d) / "results.json",
                                 meta={"field": "Education"})
    data = json.loads(out.read_text())
    check("export has 5 papers", len(data["papers"]) == 5,
          str(len(data["papers"])))
    dois = {p["doi"] for p in data["papers"]}
    check("all DOIs present", dois == {"10.100/c1a", "10.100/c1b",
          "10.100/c1c", "10.200/c2d", "10.200/c2e"}, str(dois))
    # enriched sections survive export
    p_b = [p for p in data["papers"] if p["doi"] == "10.100/c1b"][0]
    check("section text in export", p_b["results"] == "Results B",
          p_b.get("results"))
    db.close()


def test_db_persists_across_chunks():
    print("\n[4] DB persists across chunk reopen (simulate new GHA job)")
    d = tempfile.mkdtemp()
    db = PaperDB(d)
    _run_chunk(db, _chunk1_papers(), ["q1"])
    db.close()
    # New job reopens the same DB
    db2 = PaperDB(d)
    check("reopened: 3 papers", db2.count() == 3, str(db2.count()))
    check("reopened: 1 query", len(db2.queries_used()) == 1)
    # chunk 2 adds new
    new2, _, p2 = _run_chunk(db2, _chunk2_papers(), ["q1", "q2"])
    check("reopened chunk2: 2 new", len(new2) == 2)
    check("reopened chunk2: total 5", p2["total_found"] == 5)
    db2.close()


def test_excel_mapper_reads_db_export():
    print("\n[5] Excel _load_real_papers reads DB-exported results.json")
    d = tempfile.mkdtemp()
    db = PaperDB(d)
    _run_chunk(db, [
        _paper("Excel Test", "10.5/x", introduction="Intro text",
               methodology="Method text", results="Results text",
               discussion="Discussion text", fulltext_source="europepmc",
               has_fulltext=True, keywords="test, excel"),
    ], ["q"])
    rj = db.export_results_json(Path(d) / "results.json",
                                meta={"field": "Education"})
    # Use the real Excel mapper
    import generate_ultimate_excel_v10 as gen
    papers = gen._load_real_papers(str(rj))
    check("mapper loaded 1 paper", len(papers) == 1, str(len(papers)))
    p = papers[0]
    check("intro from OA full text", p["introduction"] == "Intro text",
          p["introduction"])
    check("methodology from OA full text", p["methodology"] == "Method text",
          p["methodology"])
    check("results from OA full text", p["results"] == "Results text")
    check("fulltext_source set", p["fulltext_source"] == "europepmc")
    db.close()


def main():
    for k, v in list(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
    print(f"\n{'='*60}\nPipeline-DB tests: {PASS} passed, {FAIL} failed\n{'='*60}")
    if FAIL:
        sys.exit(1)
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
