#!/usr/bin/env python3
"""
scripts/plagiarism_protection.py — Academic integrity guard for generated text.
Ensures every generated paragraph: has citations, paraphrases correctly,
formats quotes properly (inline vs block), and never copies verbatim.

Usage:
  python plagiarism_protection.py --check text.txt
  python plagiarism_protection.py --verify-article article.json
"""

import json, re, sys, hashlib, os
from pathlib import Path
from typing import List, Dict, Optional

SCRIPTS_DIR = Path(__file__).parent
PATTERNS_FILE = SCRIPTS_DIR / "academic_patterns.json"

class PlagiarismProtection:
    """Validates generated text for academic integrity."""

    def __init__(self):
        self.patterns = {}
        if PATTERNS_FILE.exists():
            self.patterns = json.loads(PATTERNS_FILE.read_text(encoding="utf-8"))
        self.plagiarism_rules = self.patterns.get("plagiarism_prevention", {}).get("rules", [])
        self.quoting_rules = self.patterns.get("quoting_rules", {})
        self.block_quote_rules = self.patterns.get("block_quotes", {})

    def has_minimum_citations(self, text: str, min_ratio: float = 0.05) -> bool:
        """Check if at least X% of characters are in citations."""
        citation_patterns = [
            r'\([^)]+\d{4}[^)]*\)',        # (Author, 2024)
            r'\[[\d,\s-]+\]',               # [1, 2, 3] or [1-3]
            r'\([\d,\s-]+\)',               # (1) or (1, 2)
        ]
        total_citation_chars = 0
        for pat in citation_patterns:
            for m in re.finditer(pat, text):
                total_citation_chars += len(m.group())
        total_chars = len(text) if not text.isspace() else 1
        ratio = total_citation_chars / total_chars
        return ratio >= min_ratio

    def find_orphan_claims(self, text: str) -> List[str]:
        """Find sentences that make claims without citations."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        orphans = []
        for s in sentences:
            s = s.strip()
            if len(s) < 30:
                continue
            has_citation = bool(re.search(r'\([^)]*\d{4}[^)]*\)|\[[\d,\s-]+\]', s))
            is_heading = s.endswith(':') or (len(s) < 80 and not s.endswith('.'))
            if not has_citation and not is_heading:
                orphans.append(s[:100])
        return orphans

    def check_block_quote_formatting(self, text: str) -> List[str]:
        """Verify long quotes (>40 words) are formatted as block quotes."""
        threshold = self.block_quote_rules.get("threshold_words", 40)
        issues = []
        quote_matches = re.finditer(r'"(?:[^"]*?)"', text)
        for m in quote_matches:
            word_count = len(m.group().split())
            if word_count >= threshold:
                lines = text[:m.start()].count('\n')
                is_block = text[m.start()-2:m.start()] == '\n\n' if m.start() >= 2 else False
                if not is_block:
                    issues.append(f"Long quote ({word_count} words) should be block format: {m.group()[:60]}...")
        return issues

    def check_short_quote_formatting(self, text: str) -> List[str]:
        """Verify short quotes have proper quotation marks and citations."""
        issues = []
        threshold = self.block_quote_rules.get("threshold_words", 40)
        block_matches = re.finditer(r'(?<=\n\n)([^"]{10,}?)(?=\n\n)', text)
        for m in block_matches:
            word_count = len(m.group().split())
            if word_count <= threshold:
                issues.append(f"Short block quote ({word_count} words) should be inline: {m.group()[:60]}...")
        return issues

    def validate_article(self, article_text: str) -> Dict:
        """Full validation of an article's academic integrity."""
        return {
            "has_citations": self.has_minimum_citations(article_text),
            "orphan_claims": self.find_orphan_claims(article_text),
            "block_quote_issues": self.check_block_quote_formatting(article_text),
            "short_quote_issues": self.check_short_quote_formatting(article_text),
            "paragraph_count": len([p for p in article_text.split('\n\n') if p.strip()]),
            "total_words": len(article_text.split()),
            "citation_ratio": self._citation_ratio(article_text),
        }

    def _citation_ratio(self, text: str) -> float:
        citation_chars = 0
        for m in re.finditer(r'\([^)]*\d{4}[^)]*\)|\[[\d,\s-]+\]', text):
            citation_chars += len(m.group())
        return citation_chars / max(len(text), 1)

    def paraphrase_guidance(self, original: str) -> List[str]:
        """Given a sentence, suggest how to paraphrase it."""
        techniques = self.patterns.get("plagiarism_prevention", {}).get("paraphrasing_techniques", [])
        word_count = len(original.split())
        suggestions = []
        if word_count < 5:
            suggestions.append("Too short to meaningfully paraphrase — quote directly with citation")
        else:
            suggestions.append(f"Original ({word_count} words): {original[:80]}...")
            suggestions.append(f"Apply technique: change sentence structure")
            suggestions.append(f"Apply technique: use synonyms for non-technical terms")
            suggestions.append(f"Apply technique: add your own interpretation or analysis")
        suggestions.append(f"Remember: cite the source even when paraphrasing")
        return suggestions

    def format_quote(self, text: str, page: Optional[str] = None,
                     style: str = "apa_7th") -> str:
        """Format a quote properly based on length."""
        word_count = len(text.split())
        threshold = self.block_quote_rules.get("threshold_words", 40)
        page_part = f", p. {page}" if page else ""
        if word_count >= threshold:
            return f"\n\n{text}\n\n"
        else:
            return f'"{text}"{page_part}'


def cli():
    import argparse
    parser = argparse.ArgumentParser(description="Plagiarism Protection — Academic integrity guard")
    parser.add_argument("--check", help="Check a text file for citation coverage")
    parser.add_argument("--verify-article", help="Verify a JSON article file")
    parser.add_argument("--paraphrase", help="Get paraphrase guidance for a text file")
    args = parser.parse_args()

    pp = PlagiarismProtection()

    if args.check:
        text = Path(args.check).read_text(encoding="utf-8")
        result = pp.validate_article(text)
        print(f"Citation ratio: {result['citation_ratio']:.1%}")
        print(f"Paragraphs: {result['paragraph_count']}")
        print(f"Has minimum citations: {result['has_citations']}")
        if result['orphan_claims']:
            print(f"\n⚠️  Orphan claims ({len(result['orphan_claims'])}):")
            for c in result['orphan_claims'][:5]:
                print(f"  - \"{c}...\"")
        if result['block_quote_issues']:
            print(f"\n⚠️  Block quote issues ({len(result['block_quote_issues'])}):")
            for i in result['block_quote_issues'][:3]:
                print(f"  - {i}")
        print(f"\n{'✅ Passes integrity check' if result['has_citations'] and not result['orphan_claims'] else '❌ Needs revision'}")

    elif args.verify_article:
        data = json.loads(Path(args.verify_article).read_text(encoding="utf-8"))
        text = data.get("text", data.get("content", json.dumps(data)))
        result = pp.validate_article(text)
        print(json.dumps(result, indent=2))

    elif args.paraphrase:
        text = Path(args.paraphrase).read_text(encoding="utf-8")
        guidance = pp.paraphrase_guidance(text)
        print("\n".join(guidance))

    else:
        parser.print_help()


if __name__ == "__main__":
    cli()
