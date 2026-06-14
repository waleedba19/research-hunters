"""
verify_refs/cli.py — Interactive CLI for reference-list-driven verification.

Usage:
  python -m verify_refs.cli                          # interactive mode
  python -m verify_refs.cli --input <path>           # non-interactive
  python -m verify_refs.cli --input file.pdf --output-folder MyReview
  python -m verify_refs.cli --pasted "1. Smith 2020..." --output-folder MyReview
"""
import argparse
import os
import sys
from typing import List, Optional

from logger import get_logger
from verify_refs.orchestrator import run_verification

log = get_logger("verify_refs.cli")


def _ask(prompt: str, default: str = "") -> str:
    """Prompt user for input, with a default."""
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        return default
    return val or default


def _ask_yn(prompt: str, default: bool = True) -> bool:
    """Yes/no prompt."""
    suffix = " [Y/n]" if default else " [y/N]"
    try:
        val = input(f"{prompt}{suffix}: ").strip().lower()
    except EOFError:
        return default
    if not val:
        return default
    return val in ("y", "yes", "1", "true")


def _read_pasted_list() -> str:
    """Read multi-line input from stdin until user types a single '.'."""
    print("Paste your references below.")
    print("Send a single '.' on its own line when done (or Ctrl+D / Ctrl+Z).")
    print("-" * 60)
    lines: List[str] = []
    try:
        while True:
            line = input()
            if line.strip() == ".":
                break
            lines.append(line)
    except EOFError:
        pass
    return "\n".join(lines)


def interactive_mode() -> int:
    """Run the interactive wizard."""
    print("=" * 60)
    print("  Literature Reference Verification — Interactive Mode")
    print("=" * 60)
    print()
    print("I will help you verify a list of references.")
    print()
    print("STEP 1: Choose your input source")
    print("  1) Single file (PDF, DOCX, TXT, MD)")
    print("  2) Folder containing multiple files")
    print("  3) Paste a list of references (one per line)")
    print()
    choice = _ask("Choice (1/2/3)", "1")

    if choice == "1":
        input_path = _ask("File path")
        if not input_path or not os.path.exists(input_path):
            print(f"Error: file not found: {input_path}")
            return 1
    elif choice == "2":
        input_path = _ask("Folder path")
        if not input_path or not os.path.isdir(input_path):
            print(f"Error: folder not found: {input_path}")
            return 1
    elif choice == "3":
        text = _read_pasted_list()
        if not text.strip():
            print("Error: empty input")
            return 1
        input_path = "PASTED:" + text
    else:
        print(f"Invalid choice: {choice}")
        return 1

    print()
    print("STEP 2: Output folder name")
    output_folder = _ask("Output folder name (used for the report files + Drive folder)", "My_Reference_Verification")

    print()
    print("STEP 3: PDF download")
    print("  Should I try to download PDFs for VERIFIED references?")
    print("  (uses the 14-layer download chain — Unpaywall, OA.mg, Anna's Archive, etc.)")
    download = _ask_yn("Download PDFs?", True)

    print()
    print("STEP 4: Thresholds (optional — press Enter to use defaults)")
    t_v_str = _ask("VERIFIED threshold (0-1, default 0.85)", "0.85")
    t_l_str = _ask("LIKELY threshold (0-1, default 0.60)", "0.60")
    try:
        threshold_verified = float(t_v_str)
    except ValueError:
        threshold_verified = 0.85
    try:
        threshold_likely = float(t_l_str)
    except ValueError:
        threshold_likely = 0.60

    print()
    print("=" * 60)
    print(f"  Starting verification...")
    print(f"  Input:   {input_path[:80]}")
    print(f"  Output:  {output_folder}")
    print(f"  PDFs:    {'yes' if download else 'no'}")
    print(f"  Thresholds: VERIFIED>={threshold_verified}  LIKELY>={threshold_likely}")
    print("=" * 60)
    print()

    result = run_verification(
        input_path=input_path,
        output_folder_name=output_folder,
        download_pdfs=download,
        threshold_verified=threshold_verified,
        threshold_likely=threshold_likely,
    )

    print()
    print("=" * 60)
    if not result.get("success"):
        print(f"  FAILED: {result.get('error', 'unknown error')}")
        print("=" * 60)
        return 1
    print(f"  Verification complete!")
    print(f"  Output dir:        {result['output_dir']}")
    print(f"  Total references:  {result['total_refs']}")
    print(f"  VERIFIED:          {result['verified']}")
    print(f"  LIKELY:            {result['likely']}")
    print(f"  UNVERIFIED:        {result['unverified']}")
    print(f"  FAKE:              {result['fake']}")
    print(f"  PDFs downloaded:   {result['pdfs_downloaded']}")
    print()
    print(f"  Excel report: {result['excel_path']}")
    print(f"  DOCX report:  {result['docx_path']}")
    print("=" * 60)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Literature Reference Verification — list-driven mode")
    parser.add_argument("--input", help="Path to folder or file with references")
    parser.add_argument("--pasted", help="Pasted list of references (one per line)")
    parser.add_argument("--output-folder", default="My_Reference_Verification",
                        help="Output folder name (used for reports + Drive)")
    parser.add_argument("--output-dir", help="Base output directory (default: pdf_files/)")
    parser.add_argument("--no-download", action="store_true",
                        help="Skip PDF download for verified refs")
    parser.add_argument("--threshold-verified", type=float, default=0.85,
                        help="Ollama score threshold for VERIFIED status")
    parser.add_argument("--threshold-likely", type=float, default=0.60,
                        help="Ollama score threshold for LIKELY status")
    args = parser.parse_args(argv)

    if not args.input and not args.pasted:
        return interactive_mode()

    if args.pasted:
        input_path = "PASTED:" + args.pasted
    else:
        input_path = args.input
        if not os.path.exists(input_path):
            print(f"Error: input not found: {input_path}", file=sys.stderr)
            return 1

    result = run_verification(
        input_path=input_path,
        output_folder_name=args.output_folder,
        base_output_dir=args.output_dir,
        download_pdfs=not args.no_download,
        threshold_verified=args.threshold_verified,
        threshold_likely=args.threshold_likely,
    )

    if not result.get("success"):
        print(f"FAILED: {result.get('error', 'unknown error')}", file=sys.stderr)
        return 1
    print(f"\nVERIFIED={result['verified']} LIKELY={result['likely']} "
          f"UNVERIFIED={result['unverified']} FAKE={result['fake']} "
          f"PDFs={result['pdfs_downloaded']}")
    print(f"Excel: {result['excel_path']}")
    print(f"DOCX:  {result['docx_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
