"""
report_pdf.py — Convert DOCX reports to PDF for the heavy report workflow.

Tries multiple methods in order of preference:
  1. LibreOffice (best quality, cross-platform: soffice, libreoffice, /usr/bin/libreoffice,
     C:\\Program Files\\LibreOffice\\program\\soffice.exe)
  2. docx2pdf (Windows with Word installed, macOS with Word installed)
  3. weasyprint (if docx-to-html conversion is available — fallback)
  4. Returns None on failure (does NOT raise)

Used by hunt_pipeline.py to generate the final PDF report after DOCX generation.
"""
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from logger import get_logger

log = get_logger(__name__)


def _find_libreoffice() -> Optional[list]:
    """Find a working LibreOffice executable. Returns the cmd as a list, or None."""
    candidates = [
        ["soffice"],
        ["libreoffice"],
        ["/usr/bin/libreoffice"],
        ["/usr/bin/soffice"],
        ["C:\\Program Files\\LibreOffice\\program\\soffice.exe"],
        ["C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe"],
        ["/Applications/LibreOffice.app/Contents/MacOS/soffice"],
    ]
    for cmd in candidates:
        try:
            r = subprocess.run(cmd + ["--version"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return cmd
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
    return None


def docx_to_pdf(docx_path: str | Path,
                timeout: int = 300) -> Optional[Path]:
    """Convert a DOCX file to PDF. Tries LibreOffice first, then docx2pdf.

    Args:
        docx_path: absolute path to the input .docx file
        timeout: max seconds to wait (default 300 = 5 min, large docs need this)

    Returns:
        Path to the generated .pdf, or None if conversion failed.
    """
    docx_path = Path(docx_path).resolve()
    if not docx_path.exists():
        log.error(f"docx_to_pdf: input not found: {docx_path}")
        return None
    if docx_path.suffix.lower() != ".docx":
        log.error(f"docx_to_pdf: input is not .docx: {docx_path}")
        return None

    pdf_path = docx_path.with_suffix(".pdf")
    out_dir = docx_path.parent

    # Method 1: LibreOffice
    lo_cmd = _find_libreoffice()
    if lo_cmd:
        try:
            log.info(f"Converting {docx_path.name} -> PDF via LibreOffice...")
            # Use a unique user profile dir per conversion to avoid lock conflicts
            profile_dir = out_dir / f".lo_profile_{int(time.time())}"
            profile_dir.mkdir(exist_ok=True)
            try:
                r = subprocess.run(
                    lo_cmd + [
                        "--headless",
                        "--norestore", "--nofirststartwizard",
                        f"-env:UserInstallation=file://{profile_dir}",
                        "--convert-to", "pdf",
                        "--outdir", str(out_dir),
                        str(docx_path),
                    ],
                    capture_output=True, text=True, timeout=timeout,
                )
                if r.returncode == 0 and pdf_path.exists() and pdf_path.stat().st_size > 1000:
                    log.info(f"OK PDF via LibreOffice: {pdf_path.name} "
                             f"({pdf_path.stat().st_size:,} bytes)")
                    try:
                        import shutil
                        shutil.rmtree(profile_dir, ignore_errors=True)
                    except Exception:
                        pass
                    return pdf_path
                else:
                    log.warning(f"LibreOffice returned {r.returncode}: "
                                f"{(r.stderr or r.stdout)[:300]}")
            finally:
                # Always clean up the profile dir
                try:
                    import shutil
                    shutil.rmtree(profile_dir, ignore_errors=True)
                except Exception:
                    pass
        except subprocess.TimeoutExpired:
            log.warning(f"LibreOffice timed out after {timeout}s")
        except Exception as e:
            log.warning(f"LibreOffice error: {e}")

    # Method 2: docx2pdf (Windows / macOS with Word)
    try:
        from docx2pdf import convert as docx2pdf_convert
        log.info(f"Trying docx2pdf for {docx_path.name}...")
        docx2pdf_convert(str(docx_path), str(pdf_path))
        if pdf_path.exists() and pdf_path.stat().st_size > 1000:
            log.info(f"OK PDF via docx2pdf: {pdf_path.name} "
                     f"({pdf_path.stat().st_size:,} bytes)")
            return pdf_path
    except ImportError:
        log.info("docx2pdf not installed (pip install docx2pdf)")
    except Exception as e:
        log.warning(f"docx2pdf error: {e}")

    log.error(f"PDF conversion failed for {docx_path.name}. "
              f"Install LibreOffice (https://www.libreoffice.org/) "
              f"or docx2pdf (pip install docx2pdf).")
    return None


def is_pdf_generation_available() -> bool:
    """Check if any PDF generation method is available."""
    if _find_libreoffice():
        return True
    try:
        import docx2pdf  # noqa: F401
        return True
    except ImportError:
        return False
    return False
