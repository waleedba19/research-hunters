"""Generate a real sample of the Excel + DOCX reports from a known dataset.

Run from the repo root:
  python tests/generate_sample_reports.py

Outputs:
  sample_reports/master_database_verifyrefs.xlsx
  sample_reports/literature_verification_report.docx
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verify_refs.reports import build_excel_report, build_docx_report

CLASSIFIED = [
    {
        "ref": "Vaswani A, Shazeer N, Parmar N, et al. Attention is all you need. Advances in Neural Information Processing Systems. 2017;30:5998-6008.",
        "status": "VERIFIED", "score": 0.97,
        "reason": "Exact title match in 4 platforms (crossref, openalex, semantic_scholar, arxiv); NeurIPS 2017 confirmed.",
        "matched_title": "Attention is all you need",
        "matched_doi": "10.5555/3295222.3295349",
        "matched_authors": "Vaswani A, Shazeer N, Parmar N, Uszkoreit J, Jones L, Gomez AN, Kaiser L, Polosukhin I",
        "matched_year": "2017", "source_platform": "crossref", "source_count": 4,
        "candidates_count": 12, "error": "", "matched_url": "https://papers.nips.cc/paper/7181-attention-is-all-you-need.pdf",
        "download_success": True, "download_path": "01_PDFs/001_Attention_is_all_you_need.pdf"
    },
    {
        "ref": "He K, Zhang X, Ren S, Sun J. Deep residual learning for image recognition. CVPR 2016:770-778.",
        "status": "VERIFIED", "score": 0.95,
        "reason": "Exact title match; CVPR 2016 proceedings; DOI confirmed in IEEE Xplore.",
        "matched_title": "Deep residual learning for image recognition",
        "matched_doi": "10.1109/CVPR.2016.90",
        "matched_authors": "He K, Zhang X, Ren S, Sun J",
        "matched_year": "2016", "source_platform": "crossref", "source_count": 5,
        "candidates_count": 8, "error": "",
        "matched_url": "https://www.cv-foundation.org/openaccess/content_cvpr_2016/papers/He_Deep_Residual_Learning_CVPR_2016_paper.pdf",
        "download_success": True, "download_path": "01_PDFs/002_Deep_Residual_Learning_CVPR_2016.pdf"
    },
    {
        "ref": "Devlin J, Chang MW, Lee K, Toutanova K. BERT: pre-training of deep bidirectional transformers for language understanding. NAACL-HLT 2019:4171-4186.",
        "status": "VERIFIED", "score": 0.93,
        "reason": "Title matches BERT paper; NAACL-HLT 2019 confirmed; DOI verified.",
        "matched_title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        "matched_doi": "10.18653/v1/N19-1423",
        "matched_authors": "Devlin J, Chang MW, Lee K, Toutanova K",
        "matched_year": "2019", "source_platform": "semantic_scholar", "source_count": 3,
        "candidates_count": 6, "error": "",
        "matched_url": "https://aclanthology.org/N19-1423.pdf",
        "download_success": True, "download_path": "01_PDFs/003_BERT_NAACL_2019.pdf"
    },
    {
        "ref": "Brown TB, Mann B, Ryder N, et al. Language models are few-shot learners. NeurIPS 2020;33:1877-1901.",
        "status": "LIKELY", "score": 0.78,
        "reason": "Title matches GPT-3 paper; year and venue correct, but author list truncated in source.",
        "matched_title": "Language Models are Few-Shot Learners",
        "matched_doi": "10.48550/arXiv.2005.14165",
        "matched_authors": "Brown TB, Mann B, Ryder N, et al.",
        "matched_year": "2020", "source_platform": "arxiv", "source_count": 2,
        "candidates_count": 4, "error": "", "matched_url": "https://arxiv.org/pdf/2005.14165.pdf",
        "download_success": False, "download_path": ""
    },
    {
        "ref": "LeCun Y, Bengio Y, Hinton G. Deep learning. Nature. 2015;521(7553):436-444.",
        "status": "VERIFIED", "score": 0.96,
        "reason": "Highly-cited review paper; Nature 2015 confirmed; 6 platforms indexed.",
        "matched_title": "Deep learning",
        "matched_doi": "10.1038/nature14539",
        "matched_authors": "LeCun Y, Bengio Y, Hinton G",
        "matched_year": "2015", "source_platform": "crossref", "source_count": 6,
        "candidates_count": 10, "error": "", "matched_url": "https://www.nature.com/articles/nature14539.pdf",
        "download_success": True, "download_path": "01_PDFs/004_Deep_learning_Nature_2015.pdf"
    },
    {
        "ref": "Hochreiter S, Schmidhuber J. Long short-term memory. Neural Computation. 1997;9(8):1735-1780.",
        "status": "VERIFIED", "score": 0.94,
        "reason": "Foundational LSTM paper; year and journal confirmed; DOI verified.",
        "matched_title": "Long Short-Term Memory",
        "matched_doi": "10.1162/neco.1997.9.8.1735",
        "matched_authors": "Hochreiter S, Schmidhuber J",
        "matched_year": "1997", "source_platform": "crossref", "source_count": 4,
        "candidates_count": 7, "error": "", "matched_url": "",
        "download_success": False, "download_path": ""
    },
    {
        "ref": "Smith J, Doe J, Fake X. A completely fabricated paper. Journal of Imaginary Studies. 2099;1(1):1-10.",
        "status": "FAKE", "score": 0.0, "reason": "",
        "matched_title": "", "matched_doi": "", "matched_authors": "",
        "matched_year": "", "source_platform": "", "source_count": 0,
        "candidates_count": 0,
        "error": "no candidates found in any platform (likely fabricated or hallucinated)",
        "matched_url": ""
    },
]


def main() -> int:
    out_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "sample_reports")
    os.makedirs(out_dir, exist_ok=True)
    xlsx_path = os.path.join(out_dir, "master_database_verifyrefs.xlsx")
    docx_path = os.path.join(out_dir, "literature_verification_report.docx")
    build_excel_report(CLASSIFIED, xlsx_path,
                       source_description="demo: 7 references (6 real + 1 fabricated)")
    build_docx_report(CLASSIFIED, docx_path,
                      source_description="demo: 7 references (6 real + 1 fabricated)")
    print("=" * 60)
    print("  Sample reports generated")
    print("=" * 60)
    print(f"  Excel: {xlsx_path}")
    print(f"    size: {os.path.getsize(xlsx_path):,} bytes")
    print(f"  DOCX:  {docx_path}")
    print(f"    size: {os.path.getsize(docx_path):,} bytes")
    print()
    counts = {"VERIFIED": 0, "LIKELY": 0, "UNVERIFIED": 0, "FAKE": 0}
    for c in CLASSIFIED:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    print(f"  VERIFIED   : {counts['VERIFIED']}")
    print(f"  LIKELY     : {counts['LIKELY']}")
    print(f"  UNVERIFIED : {counts['UNVERIFIED']}")
    print(f"  FAKE       : {counts['FAKE']}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
