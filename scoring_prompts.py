"""
scoring_prompts.py — Ollama prompt templates for precision scoring.
Used by precision_engine.py to evaluate paper-reference matches.
"""

# Strict 0-1 scoring prompt for paper match evaluation.
# Returns JSON: {"score": 0.0-1.0, "reason": "...", "uncertain": false}
SCORE_MATCH_PROMPT = """You are an academic reference verifier. Your job is to determine if PAPER exactly matches REFERENCE.

REFERENCE (what the user is looking for):
{reference_text}

PAPER (candidate from search):
Title: {title}
Authors: {authors}
Year: {year}
Journal: {journal}
DOI: {doi}
Abstract: {abstract}

Score 0.0 to 1.0 based on:
- 1.0 = exact match (same title, same authors, same year, same journal)
- 0.85-0.99 = strong match (minor differences in formatting only)
- 0.50-0.84 = partial match (same topic but different paper)
- 0.00-0.49 = different paper

CRITICAL RULES:
- If authors differ completely → score MUST be < 0.5
- If year differs by >3 years → score MUST be < 0.6
- If title is completely different → score MUST be < 0.3
- If uncertain, set "uncertain": true and lower the score

Reply ONLY with valid JSON, no other text:
{{"score": 0.X, "reason": "1-2 sentence explanation", "uncertain": false}}"""


# Cross-source validation prompt
CROSS_SOURCE_PROMPT = """You are validating that these two paper records describe the SAME paper.

RECORD A:
{a}

RECORD B:
{b}

Reply ONLY with JSON:
{{"same_paper": true/false, "confidence": 0.X, "reason": "brief explanation"}}"""


# Reference type detection prompt
DETECT_REFERENCE_TYPE_PROMPT = """Classify this reference into ONE category:
- article (journal article)
- book (monograph)
- chapter (book chapter)
- thesis (PhD/MA thesis)
- conference (conference paper)
- report (technical/government report)
- web (website/online document)
- other

REFERENCE: {reference_text}

Reply ONLY with JSON: {{"type": "article", "confidence": 0.X}}"""


# Wizard intent detection (natural language understanding)
DETECT_INTENT_PROMPT = """You are a Telegram bot intent classifier. Given a user message, classify into ONE:

- start (user said hello, /start, greeting)
- search (user wants to find/verify a paper or reference)
- upload (user wants to upload a chapter PDF/document)
- status (user wants to know current job status)
- sheet (user wants the Google Sheet link)
- help (user needs help / instructions)
- cancel (user wants to cancel / start over)
- unknown (cannot classify)

User message: {message}

Reply ONLY with JSON: {{"intent": "search", "confidence": 0.X}}"""


# Extract title from a freeform reference text
EXTRACT_TITLE_PROMPT = """Extract ONLY the paper/book title from this reference text. Return the title verbatim, no other text.

REFERENCE: {reference_text}

If no clear title, return: null"""


# Extract authors from reference text
EXTRACT_AUTHORS_PROMPT = """Extract the author list from this reference text. Return as a JSON array of "LastName, F." strings. No other text.

REFERENCE: {reference_text}

If no authors found, return: []"""


# Extract year
EXTRACT_YEAR_PROMPT = """Extract the 4-digit publication year from this reference text. Return only the year as a string, or "null" if not found.

REFERENCE: {reference_text}"""
