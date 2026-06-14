# Form Inputs → Python Script Mapping

## 🔬 Research Hunter v7 - Academic Intelligence System

### Form Fields → Python Arguments Mapping

| # | Form Input | Python Argument | Status |
|---|------------|-----------------|--------|
| 1 | `title` | `--title` | ✅ OK |
| 2 | `rq1` | `--rq1` | ✅ OK |
| 3 | `rq2` | `--rq2` | ✅ OK |
| 4 | `rq3` | `--rq3` | ✅ OK |
| 5 | `rq4` | `--rq4` | ✅ OK |
| 6 | `rq5` | `--rq5` | ✅ OK |
| 7 | `field` | `--field` | ✅ OK |
| 8 | `study_type` | `--study-type` | ✅ OK |
| 9 | `study_level` | `--study-level` | ✅ OK |
| 10 | `methodology` | `--methodology` | ✅ OK |
| 11 | `thesis_part` | `--dissertation-part` | ✅ OK |
| 12 | `quartile` | `--quartile-filter` | ✅ OK |
| 13 | `language` | `--language` | ✅ OK |
| 14 | `year_from` | `--year-from` | ✅ OK |
| 15 | `year_to` | `--year-to` | ✅ OK |
| 16 | `mode` | `--mode` | ✅ OK |
| 17 | `paper_limit` | `--max-batches` | ✅ OK |
| 18 | `scihub` | `--scihub` | ✅ OK |
| 19 | `folder_mode` | `--single-folder` | ✅ OK |
| 20 | `keywords` | `--keywords` | ✅ OK |
| 21 | `proxy` | `--proxy` | ✅ OK |
| 22 | `learn` | `--learn` | ✅ OK |
| 23 | `generate_paper` | `--generate-paper` | ✅ OK |
| 24 | `paper_type` | `--paper-type` | ✅ OK |
| 25 | `output_format` | `--output-format` | ✅ OK |
| 26 | `geographic_area` | (internal use) | ⚠️ Partial |

### 🤖 Ollama Integration (qwen2.5vl:3b)

The Python script uses two Ollama models:

| Model | Context | Use Case |
|-------|---------|----------|
| `qwen2.5vl:3b` | 4K | Default operations |
| `qwen2.5vl-3b-16k` | 16K | Long-form analysis, literature review |

#### LLM-Powered Functions:
- `llm_analyze_paper()` - Enhanced paper analysis
- `llm_enhance_search()` - Semantic search ranking
- `llm_generate_abstract()` - AI abstract synthesis
- `llm_generate_literature_review()` - Literature review generation
- `llm_compare_papers()` - Multi-paper comparison
- `llm_identify_themes()` - Theme identification

### Data Flow

```
GitHub Form Input → run.yml workflow → args builder → research_hunter_v2-4.py
                                                                        ↓
                                                    llm_research_hunter.py (Ollama)
                                                                        ↓
                                              qwen2.5vl:3b (4K) / qwen2.5vl-3b-16k (16K)
```