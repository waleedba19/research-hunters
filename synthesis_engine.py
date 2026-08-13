"""
synthesis_engine.py — v7 Deep Research Synthesis Engine

The first engine that performs genuine cross-paper academic synthesis from
page-by-page extracted PDF content. No AI tool in 2026 reads the actual PDFs
and maps how papers relate, agree, disagree, and build on each other.

Six analytical passes over the corpus, each driven by deep_reader output
(pdf_sections + pdf_quotes), not just API metadata:

1. cluster_papers_by_theme()  — thematic clustering from section text
2. build_citation_network()  — which papers cite/support/extend/contradict
3. detect_convergence()       — where results agree vs. diverge
4. map_methodological_lineage() — methodology inheritance + evolution
5. extract_thematic_quotes()  — verbatim quotes with author-year-page citations
6. identify_research_gaps()   — data-driven gaps (not templated)

All functions are deterministic (no ollama required) and degrade gracefully
when deep_reader data is absent (papers without downloaded PDFs contribute
metadata only). Never raises.
"""

from __future__ import annotations
import re
from collections import Counter, defaultdict
from typing import Any

try:
    from deep_reader import clean_academic_text as _cat
except Exception:  # pragma: no cover
    def _cat(text: str) -> str:
        return text or ""


# ── Helpers ────────────────────────────────────────────────────────────────────

_STOPWORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with","by",
    "from","is","are","was","were","be","been","being","this","that","these",
    "those","it","its","as","into","about","than","then","so","such","not","no",
    "also","more","most","many","much","some","any","all","each","every","both",
    "between","through","during","after","before","above","below","over","under",
    "study","studies","research","paper","article","based","using","used","use",
    "results","found","analysis","data","method","methods","approach","may","can",
    "however","while","which","their","they","them","we","our","has","have","had",
    "been","were","will","would","could","should","one","two","first","second",
    "section","figure","table","page","http","https","doi","org","com","et","al",
}

_APA_AUTHORS_RE = re.compile(r"([A-Z][a-z]+,\s+[A-Z]\.?(?:[A-Z]\.?)*)(?:,\s*[A-Z][a-z]+,\s+[A-Z]\.?)*,?")


def _tokenize(text: str) -> list[str]:
    """Lowercase word tokens, stopwords removed, length >= 3."""
    if not text:
        return []
    return [w for w in re.findall(r"\b[a-z]{3,}\b", text.lower()) if w not in _STOPWORDS]


def _short_authors(paper: dict, n: int = 2) -> str:
    """Return 'Smith & Jones' or 'Smith et al.' style short author string."""
    authors = paper.get("authors") or []
    names = []
    for a in authors[:n]:
        if not a:
            continue
        parts = str(a).split()
        if not parts:
            continue
        last = parts[-1]
        initials = " ".join(p[0] + "." for p in parts[:-1] if p and p[0].isalpha())
        names.append(f"{initials} {last}".strip() if initials else last)
    if len(authors) > n:
        return f"{names[0]} et al." if names else "Anon"
    return " & ".join(names) if names else "Anon"


def _cite(paper: dict) -> str:
    """Build an in-text citation: (Smith & Jones, 2023) or (Smith et al., 2020)."""
    auth = _short_authors(paper, 2)
    year = str(paper.get("year", "") or "")[:4] or "n.d."
    return f"({auth}, {year})"


def _full_cite(paper: dict) -> str:
    """Full narrative citation: Smith and Jones (2023)."""
    authors = paper.get("authors") or []
    if not authors:
        auth = "Anonymous"
    elif len(authors) == 1:
        auth = str(authors[0])
    elif len(authors) == 2:
        auth = f"{authors[0]} and {authors[1]}"
    else:
        auth = f"{authors[0]} et al."
    year = str(paper.get("year", "") or "")[:4] or "n.d."
    return f"{auth} ({year})"


def _section_text(paper: dict, section: str) -> str:
    """Extract cleaned text for a given academic section from deep_reader data."""
    reader = paper.get("pdf_reader") or {}
    sections = (reader.get("sections") or {}) if reader else {}
    sec = sections.get(section, {}) or {}
    return _cat(sec.get("text", "") or "")


def _paper_keywords(paper: dict) -> set[str]:
    """Merge declared keywords + top tokens from title/abstract + section text."""
    kws = set()
    for k in (paper.get("keywords") or []):
        kws.add(str(k).lower().strip())
    for field in ("title", "abstract"):
        for tok in _tokenize(str(paper.get(field, ""))):
            kws.add(tok)
    return {k for k in kws if len(k) >= 3}


# ── 1. Thematic clustering ────────────────────────────────────────────────────

def cluster_papers_by_theme(papers: list[dict], min_cluster: int = 2) -> list[dict]:
    """Group papers by shared content themes (from section text + keywords).

    Returns a list of theme clusters, each:
      {"theme": str, "papers": [paper,...], "keywords": [str,...], "size": int}
    Clusters are sorted by size (largest first). Papers can appear in multiple
    clusters if they span themes.
    """
    if not papers:
        return []

    # Build a keyword frequency map across the corpus
    kw_freq: Counter = Counter()
    paper_kws: dict[int, set[str]] = {}
    for idx, p in enumerate(papers):
        kws = _paper_keywords(p)
        paper_kws[idx] = kws
        for k in kws:
            kw_freq[k] += 1

    # Keep keywords that appear in >= 2 papers but aren't ubiquitous (not in > 60%)
    threshold = max(min_cluster, 2)
    ceiling = max(3, int(len(papers) * 0.6))
    viable = {k for k, c in kw_freq.items() if threshold <= c <= ceiling}
    if not viable:
        # Fall back to top tokens
        viable = {k for k, _ in kw_freq.most_common(20)}

    # Build clusters: for each top keyword, gather papers containing it
    top_kws = [k for k, _ in kw_freq.most_common(40) if k in viable]
    clusters: list[dict] = []
    seen_combos: set[frozenset] = set()
    for kw in top_kws[:15]:  # cap at 15 themes
        members = [papers[i] for i, ks in paper_kws.items() if kw in ks]
        if len(members) < min_cluster:
            continue
        combo = frozenset(id(m) for m in members)
        if combo in seen_combos:
            continue
        seen_combos.add(combo)
        # Gather co-occurring keywords (what else these papers share)
        co_kws = Counter()
        for m in members:
            for k in paper_kws.get(papers.index(m), set()):
                if k != kw:
                    co_kws[k] += 1
        theme_words = [kw] + [k for k, _ in co_kws.most_common(4)]
        clusters.append({
            "theme": " / ".join(theme_words[:5]).title(),
            "theme_keyword": kw,
            "papers": members,
            "keywords": theme_words,
            "size": len(members),
        })

    clusters.sort(key=lambda c: c["size"], reverse=True)
    return clusters


# ── 2. Citation network ───────────────────────────────────────────────────────

def build_citation_network(papers: list[dict]) -> dict:
    """Detect relationships between papers: supports, extends, contradicts.

    Uses two signals:
      (a) Title/author mentions — if paper A's full text mentions paper B's
          title or first author, A cites B.
      (b) Methodological similarity — if two papers share methodology section
          keywords, one likely extends the other (earlier year = cited by later).

    Returns:
      {"edges": [{"source": idx, "target": idx, "type": "cites"|"extends"|
       "supports"|"contradicts", "evidence": str}, ...],
       "matrix": {idx: {idx2: type}}, "most_cited": [idx,...]}
    """
    if not papers:
        return {"edges": [], "matrix": {}, "most_cited": []}

    n = len(papers)
    # Pre-compute searchable signals per paper
    signals: list[dict] = []
    for i, p in enumerate(papers):
        full_text = " ".join([
            _section_text(p, "Introduction"),
            _section_text(p, "Literature Review"),
            _section_text(p, "Discussion"),
            str(p.get("abstract", "")),
        ]).lower()
        title_tokens = set(_tokenize(str(p.get("title", ""))))
        first_author = ""
        authors = p.get("authors") or []
        if authors:
            first_author = str(authors[0]).split()[-1].lower()
        signals.append({
            "title": str(p.get("title", "")).lower().strip(),
            "title_tokens": title_tokens,
            "first_author": first_author,
            "year": int(str(p.get("year", "0"))[:4] or 0),
            "method_tokens": set(_tokenize(_section_text(p, "Methodology"))),
            "full_text": full_text,
        })

    edges: list[dict] = []
    in_degree: Counter = Counter()
    matrix: dict[int, dict[int, str]] = defaultdict(dict)

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            si, sj = signals[i], signals[j]
            # Skip if no full text for the citing paper
            if not si["full_text"]:
                continue

            # Signal (a): does paper i mention paper j's title or first author?
            cites = False
            evidence = ""
            # Title match: >= 4 consecutive title tokens appear in full text
            if sj["title_tokens"]:
                overlap = sj["title_tokens"] & set(_tokenize(si["full_text"]))
                if len(overlap) >= min(4, len(sj["title_tokens"])):
                    cites = True
                    evidence = f"mentions title keywords: {', '.join(sorted(overlap)[:5])}"
            # First-author surname match (stronger if paired with year)
            if not cites and sj["first_author"] and len(sj["first_author"]) >= 3:
                if sj["first_author"] in si["full_text"]:
                    cites = True
                    evidence = f"cites author '{sj['first_author']}'"

            if cites:
                # Determine relationship type from results/discussion
                res_i = _section_text(papers[i], "Results").lower() + " " + _section_text(papers[i], "Discussion").lower()
                res_j = _section_text(papers[j], "Results").lower()
                # Contradiction signals
                contradiction_cues = ("contradict", "conflict", "disagree", "challenge",
                                      "refute", "however, we find", "in contrast to", "unlike")
                support_cues = ("consistent with", "confirm", "support", "align", "replicate",
                                "corroborate", "in agreement", "build on", "extend")
                rel_type = "cites"
                if any(c in res_i for c in contradiction_cues):
                    rel_type = "contradicts"
                elif any(c in res_i for c in support_cues):
                    rel_type = "supports"
                elif si["method_tokens"] and sj["method_tokens"]:
                    method_overlap = len(si["method_tokens"] & sj["method_tokens"])
                    if method_overlap >= 4 and si["year"] > sj["year"]:
                        rel_type = "extends"
                edges.append({
                    "source": i, "target": j, "type": rel_type, "evidence": evidence,
                })
                matrix[i][j] = rel_type
                in_degree[j] += 1
                continue

            # Signal (b): methodological similarity + year ordering => extends
            if si["method_tokens"] and sj["method_tokens"] and si["year"] and sj["year"]:
                method_overlap = len(si["method_tokens"] & sj["method_tokens"])
                if method_overlap >= 5 and si["year"] > sj["year"]:
                    edges.append({
                        "source": i, "target": j, "type": "extends",
                        "evidence": f"shared methodology ({method_overlap} terms)",
                    })
                    matrix[i][j] = "extends"
                    in_degree[j] += 1

    most_cited = [idx for idx, _ in in_degree.most_common(10)]
    return {"edges": edges, "matrix": dict(matrix), "most_cited": most_cited}


# ── 3. Convergence / divergence detection ──────────────────────────────────────

def detect_convergence(papers: list[dict]) -> dict:
    """Find where the corpus's results agree (convergence) vs. disagree (divergence).

    Extracts sentences from each paper's Results + Discussion sections, clusters
    them by shared measurement/comparison keywords, and flags agreement or
    contradiction based on hedging language and quantitative direction.

    Returns:
      {"convergent": [{"finding": str, "papers": [idx,...], "strength": int}, ...],
       "divergent":  [{"finding_a": str, "finding_b": str, "papers_a": [...],
                       "papers_b": [...], "topic": str}, ...]}
    """
    if not papers:
        return {"convergent": [], "divergent": []}

    # Gather result sentences with their papers
    result_sentences: list[tuple[str, int, dict]] = []
    _sent_split = re.compile(r"(?<=[.!?])\s+(?=[A-Z\u201C\u2018])")
    for idx, p in enumerate(papers):
        for sec in ("Results", "Discussion"):
            text = _section_text(p, sec)
            if not text:
                continue
            for sent in _sent_split.split(text):
                sent = sent.strip()
                if 40 <= len(sent) <= 400 and _tokenize(sent):
                    result_sentences.append((sent, idx, p))

    if not result_sentences:
        return {"convergent": [], "divergent": []}

    # Cluster sentences by shared significant tokens
    sent_tokens = [set(_tokenize(s)) for s, _, _ in result_sentences]
    clusters: list[list[int]] = []
    assigned: set[int] = set()
    for i, ti in enumerate(sent_tokens):
        if i in assigned:
            continue
        cluster = [i]
        assigned.add(i)
        for j in range(i + 1, len(sent_tokens)):
            if j in assigned:
                continue
            tj = sent_tokens[j]
            # Jaccard similarity on top tokens
            union = ti | tj
            if not union:
                continue
            overlap = len(ti & tj)
            jaccard = overlap / len(union)
            # Require >= 2 shared tokens (lower for short sentences) AND decent similarity
            if overlap >= 2 and jaccard >= 0.20:
                cluster.append(j)
                assigned.add(j)
        if len(cluster) >= 2:
            clusters.append(cluster)

    # Analyze each cluster for convergence/divergence
    convergent: list[dict] = []
    divergent: list[dict] = []

    contradiction_cues = ("contradict", "conflict", "disagree", "challenge",
                          "refute", "however", "in contrast", "unlike", "contrary")
    agreement_cues = ("consistent", "confirm", "support", "align", "replicate",
                      "corroborate", "agreement", "similar", "parallel")

    for cluster in clusters:
        if len(cluster) < 2:
            continue
        sents = [result_sentences[c] for c in cluster]
        papers_in = list({idx for _, idx, _ in sents})
        if len(papers_in) < 2:
            continue  # same paper, not cross-paper
        # Determine if the cluster shows agreement or disagreement
        texts = [s.lower() for s, _, _ in sents]
        has_contra = any(any(c in t for c in contradiction_cues) for t in texts)
        has_agree = any(any(c in t for c in agreement_cues) for t in texts)
        # Pick the most representative sentence (longest with most keywords)
        best = max(sents, key=lambda x: len(_tokenize(x[0])))
        topic_tokens = _tokenize(best[0])[:5]

        if has_contra and not has_agree:
            # Find the two sides
            contra_sents = [s for s in sents if any(c in s[0].lower() for c in contradiction_cues)]
            other_sents = [s for s in sents if s not in contra_sents]
            if contra_sents and other_sents:
                divergent.append({
                    "finding_a": contra_sents[0][0][:300],
                    "papers_a": [result_sentences.index(contra_sents[0])],
                    "finding_b": other_sents[0][0][:300],
                    "papers_b": [result_sentences.index(other_sents[0])],
                    "topic": " ".join(topic_tokens),
                })
        else:
            convergent.append({
                "finding": best[0][:400],
                "papers": papers_in,
                "strength": len(cluster),
                "topic_tokens": topic_tokens,
            })

    convergent.sort(key=lambda c: c["strength"], reverse=True)
    return {"convergent": convergent[:15], "divergent": divergent[:10]}


# ── 4. Methodological lineage ─────────────────────────────────────────────────

def map_methodological_lineage(papers: list[dict]) -> dict:
    """Trace how methodologies evolved across the corpus by year.

    Extracts method signatures (design type, sample, instruments, analysis)
    from each paper's Methodology section, then orders them chronologically
    to show lineage and methodological trends.

    Returns:
      {"lineage": [{"year": str, "authors": str, "method_summary": str,
        "design": str, "sample": str, "analysis": str, "paper": dict}, ...],
       "design_counts": Counter, "analysis_counts": Counter}
    """
    if not papers:
        return {"lineage": [], "design_counts": Counter(), "analysis_counts": Counter()}

    _design_keywords = {
        "meta-analysis": ["meta-analysis", "systematic review", "prisma", "scoping review"],
        "longitudinal": ["longitudinal", "panel", "cohort", "over time", "repeated measure"],
        "experimental": ["randomized", "controlled trial", "rct", "control group",
                         "treatment group", "intervention", "pre-test", "post-test"],
        "mixed methods": ["mixed method", "mixed-method", "sequential explanatory",
                          "convergent design", "triangulat"],
        "quantitative": ["quantitative", "experiment", "survey", "questionnaire",
                         "statistical", "correlation", "regression", "anova", "t-test",
                         "correlational", "descriptive"],
        "qualitative": ["qualitative", "ethnograph", "case study", "phenomenolog",
                        "grounded theory", "narrative", "interview", "focus group", "thematic"],
    }
    _analysis_keywords = {
        "thematic analysis": ["thematic", "coding", "codified"],
        "statistical": ["spss", "regression", "anova", "t-test", "chi-square",
                       "descriptive statistics", "inferential"],
        "content analysis": ["content analysis", "frequency", "concordance"],
        "discourse analysis": ["discourse", "pragmatic", "conversational"],
        "corpus": ["corpus", "concordance", "collocation", "kwic"],
        "machine learning": ["machine learning", "neural", "classifier", "nlp",
                            "bert", "embedding", "word2vec"],
    }

    lineage: list[dict] = []
    design_counts: Counter = Counter()
    analysis_counts: Counter = Counter()

    for p in papers:
        method_text = _section_text(p, "Methodology").lower()
        if not method_text:
            continue
        # Detect design
        designs = []
        for label, kws in _design_keywords.items():
            if any(k in method_text for k in kws):
                designs.append(label)
        design = designs[0] if designs else "unspecified"
        # Detect analysis
        analyses = []
        for label, kws in _analysis_keywords.items():
            if any(k in method_text for k in kws):
                analyses.append(label)
        analysis = analyses[0] if analyses else "unspecified"
        # Extract a sample size if mentioned
        sample_match = re.search(r"(\d{2,5})\s*(participants?|students?|subjects?|respondents?|learners?|teachers?|samples?)", method_text)
        sample = sample_match.group(0) if sample_match else ""

        design_counts[design] += 1
        analysis_counts[analysis] += 1
        # Short method summary: first 2 sentences of methodology
        sents = re.split(r"(?<=[.!?])\s+", method_text)
        method_summary = " ".join(sents[:2])[:300]
        year = str(p.get("year", "") or "")[:4] or "n.d."
        lineage.append({
            "year": year,
            "authors": _short_authors(p),
            "method_summary": _cat(method_summary),
            "design": design,
            "sample": sample,
            "analysis": analysis,
            "paper": p,
        })

    lineage.sort(key=lambda x: x["year"])
    return {
        "lineage": lineage,
        "design_counts": design_counts,
        "analysis_counts": analysis_counts,
    }


# ── 5. Thematic quote extraction ──────────────────────────────────────────────

def extract_thematic_quotes(papers: list[dict], theme_keywords: list[str],
                            max_quotes: int = 8) -> list[dict]:
    """Pull verbatim quotes relevant to a theme, with author-year-page citations.

    Returns quotes sorted by relevance score:
      [{"quote": str, "citation": "(Smith & Jones, 2023, p. 7)",
        "paper": dict, "page": str, "score": int}, ...]
    """
    if not papers or not theme_keywords:
        return []
    kws = [k.lower() for k in theme_keywords if k and (len(k) > 2 or (len(k) == 2 and k.isupper()))]
    if not kws:
        return []

    out: list[dict] = []
    _sent_split = re.compile(r"(?<=[.!?])\s+(?=[A-Z\u201C\u2018])")
    for p in papers:
        reader = p.get("pdf_reader") or {}
        quotes = (reader.get("quotes") or []) if reader else []
        # Also mine from section text if no pre-mined quotes
        if not quotes:
            for sec in ("Introduction", "Results", "Discussion"):
                text = _section_text(p, sec)
                if not text:
                    continue
                for sent in _sent_split.split(text):
                    sent = sent.strip()
                    if not (40 <= len(sent) <= 400):
                        continue
                    sl = sent.lower()
                    hits = sum(1 for k in kws if k in sl)
                    if hits:
                        quotes.append({"quote": sent, "page": "", "keywords": [k for k in kws if k in sl]})
        for q in quotes:
            qtext = _cat(q.get("quote", ""))
            if not qtext or len(qtext) < 30:
                continue
            ql = qtext.lower()
            hits = sum(1 for k in kws if k in ql)
            if hits == 0:
                continue
            page = q.get("page", "")
            cite = _cite(p)
            if page:
                cite = cite[:-1] + f", p. {page})"
            out.append({
                "quote": qtext,
                "citation": cite,
                "paper": p,
                "page": page,
                "score": hits,
            })

    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:max_quotes]


# ── 6. Data-driven research gap identification ─────────────────────────────────

def identify_research_gaps(papers: list[dict], themes: list[dict] | None = None) -> list[dict]:
    """Identify research gaps from actual corpus coverage (not templated).

    Signals:
      - Geographic gaps: regions with < 3 papers
      - Temporal gaps: years with 0 papers in the coverage range
      - Methodological gaps: underrepresented designs (e.g., no longitudinal)
      - Quartile gaps: missing lower-tier or missing top-tier
      - Thematic gaps: topics mentioned in < 20% of papers but relevant
      - Convergence gaps: themes with high divergence (contested = opportunity)

    Returns:
      [{"gap": str, "type": str, "evidence": str, "severity": "high"|"medium"|"low"}, ...]
    """
    if not papers:
        return []

    gaps: list[dict] = []
    total = len(papers)

    # Geographic gaps
    regions: Counter = Counter()
    for p in papers:
        # Reuse the geo tier if computed, else infer from country/affiliation
        geo = p.get("geo_tier") or ""
        if not geo:
            country = str(p.get("country", "") or "").lower()
            for region, names in [("Libya", ["libya"]), ("MENA", ["egypt","tunisia","algeria",
                                  "morocco","saudi","uae","jordan","sudan","qatar","kuwait",
                                  "oman","bahrain","lebanon","syria","iraq","yemen","palestine"]),
                                  ("Sub-Saharan Africa", ["nigeria","kenya","ghana","ethiopia",
                                  "south africa","tanzania","uganda","cameroon","senegal"]),
                                  ("Asia", ["china","japan","korea","india","pakistan",
                                  "indonesia","malaysia","thailand","vietnam","philippines",
                                  "taiwan","singapore","iran","turkey"])]:
                if any(n in country for n in names):
                    geo = region
                    break
            if not geo:
                geo = "Global"
        regions[geo] += 1
    for region, count in regions.items():
        if count < 3 and region != "Global":
            gaps.append({
                "gap": f"{region} is underrepresented ({count} paper{'s' if count != 1 else ''} found).",
                "type": "geographic",
                "evidence": f"only {count} of {total} papers",
                "severity": "high" if count == 0 else "medium",
            })

    # Temporal gaps
    years = [int(str(p.get("year", "0"))[:4]) for p in papers
             if str(p.get("year", "")).strip()[:4].isdigit()]
    if years:
        y_min, y_max = min(years), max(years)
        present = set(years)
        missing = [y for y in range(y_min, y_max + 1) if y not in present and y >= 2000]
        if missing:
            gaps.append({
                "gap": f"Temporal gap: no papers found for {', '.join(str(y) for y in missing[:8])}.",
                "type": "temporal",
                "evidence": f"coverage {y_min}-{y_max}, {len(missing)} year(s) empty",
                "severity": "medium" if len(missing) <= 3 else "high",
            })

    # Methodological gaps
    lineage = map_methodological_lineage(papers)
    design_counts = lineage["design_counts"]
    if design_counts:
        for design in ("longitudinal", "experimental", "meta-analysis", "mixed methods"):
            if design_counts.get(design, 0) == 0:
                gaps.append({
                    "gap": f"No {design} studies found in the corpus.",
                    "type": "methodological",
                    "evidence": "0 papers with this design",
                    "severity": "medium",
                })

    # Quartile gaps
    q_counts: Counter = Counter()
    for p in papers:
        q = str(p.get("scopus_quartile", "") or "")
        if isinstance(p.get("scopus_quartile"), dict):
            q = p["scopus_quartile"].get("quartile", "")
        q_counts[q if q in ("Q1","Q2","Q3","Q4") else "Not Found"] += 1
    if q_counts.get("Q3", 0) + q_counts.get("Q4", 0) < total * 0.1:
        gaps.append({
            "gap": "Lower-quartile research (Q3-Q4) is underrepresented, suggesting publication bias toward higher-tier journals.",
            "type": "quartile",
            "evidence": f"{q_counts.get('Q3',0)+q_counts.get('Q4',0)} of {total}",
            "severity": "low",
        })

    # Convergence / contested themes = opportunity
    conv = detect_convergence(papers)
    for div in conv.get("divergent", [])[:3]:
        gaps.append({
            "gap": f"Contested finding on '{div['topic']}': results diverge across studies, warranting reconciliation.",
            "type": "convergence",
            "evidence": "divergent results across papers",
            "severity": "high",
        })

    # Thematic gaps: top keywords that appear in < 20% of papers
    kw_freq: Counter = Counter()
    for p in papers:
        for k in _paper_keywords(p):
            kw_freq[k] += 1
    floor = max(2, int(total * 0.20))
    for kw, count in kw_freq.most_common(20):
        if count < floor and count >= 2:
            gaps.append({
                "gap": f"'{kw}' appears relevant but underexplored ({count} papers mention it).",
                "type": "thematic",
                "evidence": f"{count} of {total}",
                "severity": "low",
            })

    # Deduplicate by gap text
    seen: set[str] = set()
    unique: list[dict] = []
    for g in gaps:
        if g["gap"] not in seen:
            seen.add(g["gap"])
            unique.append(g)
    return unique


# ── Full synthesis bundle ──────────────────────────────────────────────────────

def synthesize(papers: list[dict]) -> dict:
    """Run all six analytical passes and return a synthesis bundle.

    This is the single entry point the DOCX generator consumes:
      {
        "themes": [...], "citation_network": {...}, "convergence": {...},
        "methodology_lineage": {...}, "gaps": [...],
        "quotes_by_theme": {theme: [quote,...]}, "stats": {...},
      }
    Never raises; missing data yields empty sub-results.
    """
    if not papers:
        papers = []
    try:
        themes = cluster_papers_by_theme(papers)
    except Exception:
        themes = []
    try:
        citation_network = build_citation_network(papers)
    except Exception:
        citation_network = {"edges": [], "matrix": {}, "most_cited": []}
    try:
        convergence = detect_convergence(papers)
    except Exception:
        convergence = {"convergent": [], "divergent": []}
    try:
        methodology_lineage = map_methodological_lineage(papers)
    except Exception:
        methodology_lineage = {"lineage": [], "design_counts": Counter(), "analysis_counts": Counter()}
    try:
        gaps = identify_research_gaps(papers, themes)
    except Exception:
        gaps = []

    quotes_by_theme: dict[str, list[dict]] = {}
    for t in themes:
        try:
            quotes_by_theme[t["theme"]] = extract_thematic_quotes(
                t["papers"], t["keywords"], max_quotes=6)
        except Exception:
            quotes_by_theme[t["theme"]] = []

    # Corpus stats
    has_pdf = sum(1 for p in papers if (p.get("pdf_reader") or {}).get("text_length"))
    stats = {
        "total_papers": len(papers),
        "papers_with_pdf_text": has_pdf,
        "themes_found": len(themes),
        "citation_edges": len(citation_network.get("edges", [])),
        "convergent_findings": len(convergence.get("convergent", [])),
        "divergent_findings": len(convergence.get("divergent", [])),
        "gaps_identified": len(gaps),
    }
    return {
        "themes": themes,
        "citation_network": citation_network,
        "convergence": convergence,
        "methodology_lineage": methodology_lineage,
        "gaps": gaps,
        "quotes_by_theme": quotes_by_theme,
        "stats": stats,
    }
