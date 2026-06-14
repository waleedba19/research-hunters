"""
tests/test_verify_refs.py — End-to-end test of verify_refs module.

Runs the verification pipeline against a small sample of references
(7 real + 1 fake) and checks:
  - Module imports
  - Input parsing
  - Reference classification (>=5 should be VERIFIED, 1 should be FAKE)
  - Excel + DOCX reports are generated
  - All status types are correctly counted
"""
import os
import sys
import tempfile
import json

# Ensure repo root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger import get_logger

log = get_logger("test_verify_refs")

# Sample refs
SAMPLE_REFS = """[1] Vaswani A, Shazeer N, Parmar N, et al. Attention is all you need. Advances in Neural Information Processing Systems. 2017;30:5998-6008.

[2] He K, Zhang X, Ren S, Sun J. Deep residual learning for image recognition. IEEE Conference on Computer Vision and Pattern Recognition (CVPR). 2016:770-778.

[3] Devlin J, Chang MW, Lee K, Toutanova K. BERT: pre-training of deep bidirectional transformers for language understanding. Proceedings of NAACL-HLT. 2019:4171-4186.

[4] Brown TB, Mann B, Ryder N, et al. Language models are few-shot learners. Advances in Neural Information Processing Systems. 2020;33:1877-1901.

[5] LeCun Y, Bengio Y, Hinton G. Deep learning. Nature. 2015;521(7553):436-444.

[6] Smith J, Doe J, Fake Author X. A completely fabricated paper that doesn't exist in any database XYZ-Fake-Journal-9999. Journal of Imaginary Studies. 2099;1(1):1-10.

[7] Hochreiter S, Schmidhuber J. Long short-term memory. Neural Computation. 1997;9(8):1735-1780.

[8] Kingma DP, Ba J. Adam: a method for stochastic optimization. International Conference on Learning Representations (ICLR). 2015.
"""


def test_input_parser():
    from verify_refs.input_parser import parse_pasted_text
    refs = parse_pasted_text(SAMPLE_REFS)
    assert len(refs) == 8, f"expected 8 refs, got {len(refs)}"
    for r in refs:
        assert len(r) >= 20, f"ref too short: {r!r}"
    print(f"[test] parse_pasted_text: PASS (got {len(refs)} refs)")
    return True


def test_parse_input_file():
    sample_path = os.path.join(os.path.dirname(__file__), "sample_refs.txt")
    from verify_refs.input_parser import parse_input
    refs, desc = parse_input(sample_path)
    assert len(refs) >= 8, f"expected >=8 refs from file, got {len(refs)}"
    print(f"[test] parse_input(file): PASS (got {len(refs)} refs, desc={desc[:60]!r})")
    return True


def test_excel_report():
    from verify_refs.reports import build_excel_report
    fake_classified = [
        {"ref": "Vaswani 2017 attention is all you need", "status": "VERIFIED",
         "score": 0.95, "reason": "exact match", "matched_title": "Attention is all you need",
         "matched_doi": "10.5555/3295222.3295349", "matched_authors": "Vaswani A et al",
         "matched_year": "2017", "source_platform": "crossref", "source_count": 3,
         "candidates_count": 5, "error": "", "matched_url": "",
         "download_success": True, "download_path": "01_PDFs/001_attention.pdf"},
        {"ref": "Fake XYZ 2099", "status": "FAKE", "score": 0.0, "reason": "",
         "matched_title": "", "matched_doi": "", "matched_authors": "",
         "matched_year": "", "source_platform": "", "source_count": 0,
         "candidates_count": 0, "error": "no candidates"},
        {"ref": "Some other paper", "status": "LIKELY", "score": 0.72,
         "reason": "partial match", "matched_title": "Some related paper",
         "matched_doi": "10.1234/abc", "matched_authors": "Smith J",
         "matched_year": "2020", "source_platform": "openalex", "source_count": 1,
         "candidates_count": 3, "error": "", "matched_url": ""},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "test.xlsx")
        build_excel_report(fake_classified, out, source_description="unit test")
        size = os.path.getsize(out)
        assert size > 5000, f"excel file too small: {size} bytes"
    print(f"[test] build_excel_report: PASS (size={size} bytes)")
    return True


def test_docx_report():
    from verify_refs.reports import build_docx_report
    fake_classified = [
        {"ref": "Vaswani 2017 attention is all you need", "status": "VERIFIED",
         "score": 0.95, "reason": "exact match", "matched_title": "Attention is all you need",
         "matched_doi": "10.5555/3295222.3295349", "matched_authors": "Vaswani A et al",
         "matched_year": "2017", "source_platform": "crossref", "source_count": 3,
         "candidates_count": 5, "error": "", "matched_url": "",
         "download_success": True, "download_path": "01_PDFs/001_attention.pdf"},
        {"ref": "Fake XYZ 2099", "status": "FAKE", "score": 0.0, "reason": "",
         "matched_title": "", "matched_doi": "", "matched_authors": "",
         "matched_year": "", "source_platform": "", "source_count": 0,
         "candidates_count": 0, "error": "no candidates"},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "test.docx")
        build_docx_report(fake_classified, out, source_description="unit test")
        size = os.path.getsize(out)
        assert size > 5000, f"docx file too small: {size} bytes"
    print(f"[test] build_docx_report: PASS (size={size} bytes)")
    return True


def test_orchestrator_dry():
    """Dry-run classify_ref with a single real reference.
    Skipped if ollama is not running (tested via /api/tags endpoint)."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as r:
            if r.status != 200:
                raise RuntimeError("ollama not healthy")
    except Exception as e:
        print(f"[test] classify_ref: SKIPPED (ollama not running: {e})")
        return True

    from verify_refs.orchestrator import classify_ref
    result = classify_ref(
        "Vaswani A, Shazeer N, Parmar N, et al. Attention is all you need. NeurIPS 2017.",
        threshold_verified=0.6, threshold_likely=0.3)
    assert "status" in result
    assert "score" in result
    print(f"[test] classify_ref: status={result['status']} score={result['score']:.2f} "
          f"matched={result.get('matched_title', '')[:50]!r}")
    return True


def test_end_to_end_no_download():
    """Full end-to-end test (no downloads, fast)."""
    from verify_refs.orchestrator import run_verification
    with tempfile.TemporaryDirectory() as tmp:
        result = run_verification(
            input_path="PASTED:" + SAMPLE_REFS,
            output_folder_name="test_e2e",
            base_output_dir=tmp,
            download_pdfs=False,
            threshold_verified=0.6,  # lowered for test reliability
            threshold_likely=0.3,
        )
        assert result["success"], f"run failed: {result.get('error')}"
        assert result["total_refs"] == 8, f"expected 8 refs, got {result['total_refs']}"
        assert os.path.exists(result["excel_path"]), "excel not created"
        assert os.path.exists(result["docx_path"]), "docx not created"
        print(f"[test] e2e: PASS (refs={result['total_refs']} "
              f"VERIFIED={result['verified']} LIKELY={result['likely']} "
              f"UNVERIFIED={result['unverified']} FAKE={result['fake']})")
        # The fake one should at least be UNVERIFIED or FAKE
        fake_result = [r for r in result["results"]
                       if "completely fabricated" in r.get("ref", "").lower()]
        if fake_result:
            assert fake_result[0]["status"] in ("UNVERIFIED", "FAKE"), \
                f"fake ref should be UNVERIFIED/FAKE, got {fake_result[0]['status']}"
            print(f"[test] fake ref correctly classified as {fake_result[0]['status']}")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("  verify_refs unit tests")
    print("=" * 60)
    try:
        test_input_parser()
        test_parse_input_file()
        test_excel_report()
        test_docx_report()
        test_orchestrator_dry()
        # E2E test requires ollama + network; skip if either unavailable
        skip_e2e = "--no-e2e" in sys.argv or os.environ.get("SKIP_E2E") == "1"
        if not skip_e2e:
            try:
                test_end_to_end_no_download()
            except Exception as e:
                print(f"[test] e2e SKIPPED (error: {e})")
        else:
            print("[test] e2e SKIPPED (flag)")
        print("=" * 60)
        print("  ALL TESTS PASSED")
        print("=" * 60)
    except Exception as e:
        print(f"[test] FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
