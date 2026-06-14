"""
tests/test_report_pdf.py — Unit tests for the report_pdf module.

Verifies:
  - Module imports cleanly
  - is_pdf_generation_available() returns a bool
  - docx_to_pdf() on a non-existent file returns None (no exception)
  - docx_to_pdf() on a non-.docx file returns None (no exception)
"""
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import report_pdf  # noqa: E402


def test_module_imports():
    """report_pdf module loads with all expected functions."""
    assert hasattr(report_pdf, "docx_to_pdf")
    assert hasattr(report_pdf, "is_pdf_generation_available")
    assert hasattr(report_pdf, "_find_libreoffice")
    print("[test] Module imports OK")


def test_availability_check():
    """is_pdf_generation_available returns a bool (true or false — depends on env)."""
    result = report_pdf.is_pdf_generation_available()
    assert isinstance(result, bool)
    if result:
        print("[test] PDF generation is available (LibreOffice or docx2pdf installed)")
    else:
        print("[test] PDF generation not available in this env "
              "(LibreOffice/Word not installed — DOCX still works)")


def test_nonexistent_file():
    """docx_to_pdf on a non-existent file returns None (no exception)."""
    result = report_pdf.docx_to_pdf("/nonexistent/path/fake.docx")
    assert result is None
    print("[test] Nonexistent file returns None (no exception)")


def test_non_docx_file():
    """docx_to_pdf on a non-.docx file returns None (no exception)."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"hello world")
        tmp_path = f.name
    try:
        result = report_pdf.docx_to_pdf(tmp_path)
        assert result is None
        print("[test] Non-.docx file returns None (no exception)")
    finally:
        os.unlink(tmp_path)


def test_libreoffice_search():
    """_find_libreoffice returns list (with LibreOffice) or None (without)."""
    result = report_pdf._find_libreoffice()
    if result is not None:
        assert isinstance(result, list)
        assert len(result) >= 1
        print(f"[test] LibreOffice found: {' '.join(result)}")
    else:
        print("[test] LibreOffice not found (this is fine — DOCX is the fallback)")


if __name__ == "__main__":
    print("=" * 60)
    print("  report_pdf unit tests")
    print("=" * 60)
    test_module_imports()
    test_availability_check()
    test_nonexistent_file()
    test_non_docx_file()
    test_libreoffice_search()
    print("=" * 60)
    print("  ALL TESTS PASSED")
    print("=" * 60)
