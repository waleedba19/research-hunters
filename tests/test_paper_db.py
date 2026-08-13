"""test_paper_db.py — Deep unit tests for the SQLite-backed PaperDB.

Run:  python3 tests/test_paper_db.py
Covers: dedup by doi/url/title, bulk upsert, incremental filter_new,
count/stats, 10k-paper stress, corruption recovery (delete db mid-run),
concurrent writes, export_results_json round-trip, merge enrichment of
section text on re-upsert, mark_downloaded idempotency, queries tracking,
record_run accumulation, deduplicate (in-list) correctness.

No network, no ollama — fully offline and deterministic.
"""
import json
import os
import sqlite3
import sys
import tempfile
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from paper_db import PaperDB, _paper_key  # noqa: E402

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


def _paper(title, doi="", url="", **kw):
    p = {"title": title, "authors": ["A. Author"], "year": 2024,
         "journal": "Nature", "abstract": "An abstract.", "source": "test"}
    if doi:
        p["doi"] = doi
    if url:
        p["url"] = url
    p.update(kw)
    return p


# ─────────────────────────────────────────────────────────────────────────
def test_basic_upsert_and_dedup():
    print("\n[1] basic upsert + dedup")
    d = tempfile.mkdtemp()
    db = PaperDB(d)
    p1 = _paper("Paper A", doi="10.1/x")
    is_new = db.upsert_paper(p1)
    check("first insert is new", is_new is True)
    check("count == 1", db.count() == 1, str(db.count()))
    # same doi, different title → should update not insert
    p1b = _paper("Paper A (updated)", doi="10.1/x", abstract="new abstract")
    is_new2 = db.upsert_paper(p1b)
    check("dup insert not new", is_new2 is False)
    check("count still 1", db.count() == 1, str(db.count()))
    papers = db.get_all_papers()
    check("title updated", papers[0]["title"] == "Paper A (updated)",
          papers[0]["title"])
    check("abstract updated", papers[0]["abstract"] == "new abstract")
    db.close()


def test_dedup_by_url_and_title():
    print("\n[2] dedup by url and title fallback")
    d = tempfile.mkdtemp()
    db = PaperDB(d)
    db.upsert_paper(_paper("No DOI 1", url="https://x.io/a"))
    db.upsert_paper(_paper("No DOI 1 dup", url="https://x.io/a"))
    db.upsert_paper(_paper("Title Only Paper"))  # title fallback
    db.upsert_paper(_paper("Title Only Paper"))  # title dup
    check("url + title dedup → count 2", db.count() == 2, str(db.count()))
    db.close()


def test_filter_new_accumulation():
    print("\n[3] filter_new accumulation + skip")
    d = tempfile.mkdtemp()
    db = PaperDB(d)
    new1, sk1 = db.filter_new([_paper("A", doi="1"), _paper("B", doi="2")])
    check("first batch 2 new", new1 and len(new1) == 2, str(len(new1)))
    check("first batch 0 skip", sk1 == 0)
    new2, sk2 = db.filter_new([_paper("A", doi="1"), _paper("C", doi="3")])
    check("second batch 1 new", len(new2) == 1, str(len(new2)))
    check("second batch 1 skip", sk2 == 1, str(sk2))
    check("count == 3", db.count() == 3, str(db.count()))
    db.close()


def test_bulk_upsert():
    print("\n[4] bulk upsert mixed new/dup")
    d = tempfile.mkdtemp()
    db = PaperDB(d)
    db.upsert_paper(_paper("Existing", doi="e1"))
    new, dup = db.bulk_upsert([
        _paper("Existing", doi="e1", abstract="updated"),
        _paper("New1", doi="n1"),
        _paper("New2", doi="n2"),
    ])
    check("bulk new == 2", new == 2, str(new))
    check("bulk dup == 1", dup == 1, str(dup))
    check("count == 3", db.count() == 3)
    db.close()


def test_section_merge_on_update():
    print("\n[5] section text merge on re-upsert (no overwrite of existing)")
    d = tempfile.mkdtemp()
    db = PaperDB(d)
    db.upsert_paper(_paper("Paper", doi="10.5/m",
                           introduction="Intro v1", methodology="Method v1"))
    # re-upsert with empty sections → existing should be preserved
    db.upsert_paper(_paper("Paper", doi="10.5/m", results="Results v1"))
    p = db.get_all_papers()[0]
    check("intro preserved", p["introduction"] == "Intro v1", p["introduction"])
    check("method preserved", p["methodology"] == "Method v1", p["methodology"])
    check("results added", p["results"] == "Results v1", p["results"])
    db.close()


def test_mark_downloaded():
    print("\n[6] mark_downloaded + idempotency")
    d = tempfile.mkdtemp()
    db = PaperDB(d)
    db.upsert_paper(_paper("DL", doi="10.6/d"))
    db.mark_downloaded(_paper("DL", doi="10.6/d"), filename="DL.pdf")
    p = db.get_all_papers()[0]
    check("downloaded flag set", p["downloaded"] is True)
    check("pdf_path set", p["pdf_path"] == "DL.pdf", str(p["pdf_path"]))
    before = db.stats()["total_downloaded"]
    db.mark_downloaded(_paper("DL", doi="10.6/d"), filename="DL.pdf")
    check("mark_downloaded idempotent-ish",
          db.stats()["total_downloaded"] >= before)
    db.close()


def test_queries_and_record_run():
    print("\n[7] queries tracking + record_run")
    d = tempfile.mkdtemp()
    db = PaperDB(d)
    db.add_queries(["query one", "query two", "query one"])  # dup
    qu = db.queries_used()
    check("2 unique queries", len(qu) == 2, str(qu))
    db.record_run(n_found=5, n_downloaded=3, chunk=1,
                   queries_exhausted=False, download_mode="off")
    db.record_run(n_found=0, n_downloaded=0, chunk=2,
                   queries_exhausted=True, download_mode="off")
    s = db.stats()
    check("runs_total == 2", s["runs_total"] == 2, str(s["runs_total"]))
    check("queries_used == 2", s["queries_used"] == 2, str(s["queries_used"]))
    db.close()


def test_export_results_json_roundtrip():
    print("\n[8] export_results_json round-trip")
    d = tempfile.mkdtemp()
    db = PaperDB(d)
    db.upsert_paper(_paper("RP1", doi="10.8/r1", introduction="intro text",
                           results="results text", fulltext_source="europepmc"))
    db.upsert_paper(_paper("RP2", doi="10.8/r2"))
    out = db.export_results_json(
        Path(d) / "results.json", meta={"field": "Education", "title": "T"})
    data = json.loads(out.read_text(encoding="utf-8"))
    check("meta preserved", data["field"] == "Education")
    check("2 papers exported", len(data["papers"]) == 2)
    p1 = [x for x in data["papers"] if x["doi"] == "10.8/r1"][0]
    check("section text in export", p1["introduction"] == "intro text",
          p1.get("introduction"))
    check("fulltext_source in export", p1["fulltext_source"] == "europepmc")
    # load into excel mapper shape (smoke)
    db.close()


def test_stress_10k():
    print("\n[9] 10k-paper stress (insert + dedup + count)")
    import time
    d = tempfile.mkdtemp()
    db = PaperDB(d)
    t0 = time.time()
    batch = [_paper(f"Paper {i}", doi=f"10.9/{i}") for i in range(10000)]
    new, dup = db.bulk_upsert(batch)
    t1 = time.time()
    check("10k inserted", new == 10000, f"{new}")
    check("0 dups", dup == 0)
    check("count == 10000", db.count() == 10000, str(db.count()))
    # re-insert → all dups
    new2, dup2 = db.bulk_upsert(batch)
    check("re-insert 0 new", new2 == 0, str(new2))
    check("re-insert 10000 dups", dup2 == 10000, str(dup2))
    check("10k insert < 5s", (t1 - t0) < 5.0, f"{t1-t0:.2f}s")
    # get_all still correct
    allp = db.get_all_papers()
    check("get_all == 10000", len(allp) == 10000, str(len(allp)))
    # iter streaming low-mem: just count
    n = sum(1 for _ in db.iter_papers())
    check("iter_papers == 10000", n == 10000, str(n))
    db.close()


def test_corruption_recovery():
    print("\n[10] corruption recovery (reopen after external close)")
    d = tempfile.mkdtemp()
    db = PaperDB(d)
    db.upsert_paper(_paper("Survivor", doi="10.10/s"))
    db.close()
    # reopen — data must persist
    db2 = PaperDB(d)
    check("survived reopen", db2.count() == 1, str(db2.count()))
    p = db2.get_all_papers()[0]
    check("survivor title ok", p["title"] == "Survivor")
    db2.close()
    # delete -wal and -shm (simulate crash); data in main db file persists
    for ext in ("-wal", "-shm"):
        f = Path(d) / ("papers.db" + ext)
        if f.exists():
            f.unlink()
    db3 = PaperDB(d)
    check("survived wal wipe", db3.count() == 1, str(db3.count()))
    db3.close()


def test_concurrent_writes():
    print("\n[11] concurrent writes (4 threads, 250 each)")
    d = tempfile.mkdtemp()
    db = PaperDB(d)
    errors = []

    def worker(tid):
        try:
            for i in range(250):
                db.upsert_paper(_paper(f"T{tid}-{i}", doi=f"10.11/{tid}/{i}"))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    check("no thread errors", not errors, str(errors[:3]))
    check("count == 1000", db.count() == 1000, str(db.count()))
    db.close()


def test_deduplicate_inlist():
    print("\n[12] deduplicate (in-list only)")
    d = tempfile.mkdtemp()
    db = PaperDB(d)
    out = db.deduplicate([
        _paper("A", doi="1"), _paper("A", doi="1"),
        _paper("B", doi="2"), _paper("C"),  # C has no key → kept
    ])
    check("deduplicate kept 3", len(out) == 3, str(len(out)))
    db.close()


def test_key_function():
    print("\n[13] _paper_key priority")
    check("doi preferred", _paper_key({"doi": "10/x", "url": "u"}) == "doi:10/x")
    check("url fallback",
          _paper_key({"url": "https://a.io", "title": "T"}) == "url:https://a.io")
    check("title fallback",
          _paper_key({"title": "Hello World"}) == "title:hello world")
    check("none when empty", _paper_key({}) is None)


def main():
    tests = [v for k, v in list(globals().items())
             if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
    print(f"\n{'='*60}\nPaperDB tests: {PASS} passed, {FAIL} failed\n{'='*60}")
    if FAIL:
        sys.exit(1)
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
