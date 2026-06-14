"""
verify_refs — Reference-list-driven verification mode.

Workflow:
  1. Accept input: folder of PDFs/DOCX, single PDF/DOCX/TXT/MD, or pasted list
  2. Extract individual reference strings
  3. For each reference: search 81 platforms → ollama scoring → classify
  4. For verified refs: try 14-layer PDF download chain
  5. Generate:
       - master_database_verifyrefs.xlsx  (color-coded)
       - literature_verification_report.docx (professional styling)

Status classification (per reference):
  VERIFIED     - match_score >= 0.85 in >=1 platform, cross-source OR DOI hit
  LIKELY       - match_score 0.60-0.84
  UNVERIFIED   - found candidates but no high-confidence match
  FAKE         - no platform returned any candidate
"""
__version__ = "1.0.0"
