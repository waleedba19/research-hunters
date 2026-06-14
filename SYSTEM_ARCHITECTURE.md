# 🗺️ RESEARCH HUNTER v2-4 - SYSTEM ARCHITECTURE MIND MAP

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RESEARCH HUNTER v2-4 - COMPLETE SYSTEM                      │
└─────────────────────────────────────────────────────────────────────────────┘

                                    ┌─────────────────┐
                                    │   USER INPUT     │
                                    │  (GitHub Form)   │
                                    └────────┬────────┘
                                             │
                        ┌────────────────────┼────────────────────┐
                        │                    │                    │
                        ▼                    ▼                    ▼
            ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
            │   WORKFLOW FORM   │ │   PAPER SEARCH   │ │  DIRECT ACCESS   │
            │                  │ │                  │ │                  │
            │ • research_topic │ │ • 128+ platforms │ │ • Process docs   │
            │ • academic_field │ │ • Multi-language │ │ • Generate paper │
            │ • paper_type     │ │ • Auto-filter    │ │ • Scrape web    │
            │ • methodology    │ │ • Deduplicate    │ │ • Learn pattern │
            │ • language       │ │                  │ │                  │
            └────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘
                     │                     │                     │
                     └─────────────────────┼─────────────────────┘
                                         │
                    ┌────────────────────┴────────────────────┐
                    │                                         │
                    ▼                                         ▼
    ┌───────────────────────────┐           ┌───────────────────────────┐
    │   🔒 OLLAMA CORE          │           │   📊 LEARNING DATABASE   │
    │   qwen2.5vl:3b            │◄──────────│   SQLite-based           │
    │   16k Context Window      │           │   • Tracks all searches   │
    │                           │           │   • Stores patterns       │
    │   NEVER TOUCH UNLESS      │           │   • Learns writing style │
    │   EXPLICITLY NEEDED       │           │   • Field-specific       │
    └─────────────┬─────────────┘           └─────────────┬───────────┘
                  │                                     │
                  │     ┌───────────────────────────────┤
                  │     │                               │
                  ▼     ▼                               ▼
    ┌─────────────────────────────┐   ┌─────────────────────────────────────┐
    │  📄 DOCUMENT PROCESSOR     │   │  🧠 ACADEMIC WRITING ENGINE        │
    │                            │   │                                      │
    │  Supported Formats:        │   │  Study Types:                       │
    │  ┌─────────┬─────────┐   │   │  ┌─────────────────────────────┐    │
    │  │ PDF     │ ✅      │   │   │  │ • Research Article (v2-4)  │    │
    │  │ DOCX    │ ✅      │   │   │  │ • PhD Dissertation         │    │
    │  │ EPUB    │ ✅      │   │   │  │ • Master's Thesis          │    │
    │  │ TXT     │ ✅      │   │   │  │ • Systematic Review        │    │
    │  │ Images  │ ✅ OCR  │   │   │  │ • Conference Paper         │    │
    │  │ HTML    │ ✅      │   │   │  │ • Book Chapter            │    │
    │  │ Excel   │ ✅      │   │   │  │ • Literature Review       │    │
    │  │ PowerPnt│ ✅      │   │   │  └─────────────────────────────┘    │
    │  └─────────┴─────────┘   │   │                                      │
    │                         │   │  Sections Generated:                  │
    │  Features:              │   │  ┌─────────────────────────────┐      │
    │  • Text extraction      │   │  │ ✅ Abstract                │      │
    │  • OCR scanning         │   │  │ ✅ Introduction            │      │
    │  • Table extraction     │   │  │ ✅ Literature Review       │      │
    │  • Metadata extraction  │   │  │ ✅ Methodology             │      │
    │  • Section parsing     │   │  │ ✅ Results                 │      │
    │  • Ollama enhancement  │   │  │ ✅ Discussion              │      │
    └─────────────┬───────────┘   │  │ ✅ Conclusion              │      │
                  │               │  │ ✅ References              │      │
                  │               │  └─────────────────────────────┘      │
                  └───────────────┼────────────────────────────────────┘
                                  │
                                  ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  🌐 PLAYWRIGHT INTEGRATION                                          │
    │                                                                     │
    │  Capabilities:                                                       │
    │  ┌───────────────────────────────────────────────────────────┐    │
    │  │ • Web Scraping (JavaScript-rendered pages)                  │    │
    │  │ • Academic Portal Access                                   │    │
    │  │ • Dynamic Content Loading                                  │    │
    │  │ • Research Database Queries                                │    │
    │  │ • AI Learning from Internet Sources                        │    │
    │  └───────────────────────────────────────────────────────────┘    │
    │                                                                     │
    │  Learning Sources:                                                  │
    │  ┌───────────────────────────────────────────────────────────┐    │
    │  │ • Google Scholar Trends          • Research Gate            │    │
    │  │ • arXiv / bioRxiv              • Academia.edu             │    │
    │  │ • Semantic Scholar             • Paperpile                │    │
    │  │ • Crossref                    • Zotero                  │    │
    │  └───────────────────────────────────────────────────────────┘    │
    └─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW DIAGRAM                                   │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
    │ GitHub  │────▶│Workflow │────▶│ Ollama  │────▶│Output   │
    │ Form    │     │ Config  │     │ (Brain) │     │ Files   │
    └─────────┘     └─────────┘     └────┬────┘     └─────────┘
                                        │
          ┌─────────────────────────────┼─────────────────────────────┐
          │                             │                             │
          ▼                             ▼                             ▼
    ┌───────────┐              ┌───────────┐              ┌───────────┐
    │ Document  │              │ Learning  │              │ Web       │
    │ Processor │              │ Database │              │ Scraper   │
    └─────┬─────┘              └─────┬─────┘              └─────┬─────┘
          │                         │                         │
          │    ┌────────────────────┴────────────────────┐    │
          │    │                                         │    │
          ▼    ▼                                         ▼    ▼
    ┌─────────────┐              ┌─────────────┐      ┌─────────────┐
    │ PDF/DOCX/   │              │ Patterns   │      │ Dynamic    │
    │ EPUB/Images │              │ Stored     │      │ Web Content│
    └─────────────┘              └─────────────┘      └─────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                    WORKFLOW FORM → PAPER GENERATION                          │
└─────────────────────────────────────────────────────────────────────────────┘

    GitHub Form Input                    Ollama Processing              Output
    ═══════════════════════════════════════════════════════════════════════════

    research_topic ──────────────────────▶ TOPIC
    │
    academic_field ─────────────────────▶ CONTEXT
    │   (279+ fields)                  • Field-specific vocabulary
    │                                   • Methodology expectations
    │                                   • Journal standards
    │
    publication_type ──────────────────▶ FORMAT
    │   (49 types)                     • Section requirements
    │                                   • Length expectations
    │                                   • Citation style
    │
    study_level ───────────────────────▶ DEPTH
    │   (PhD/MA/Conference/etc)        • Complexity level
    │                                   • Citation count
    │                                   • Chapter structure
    │
    methodology ───────────────────────▶ METHODS
    │   (51 types)                     • Methodology section style
    │                                   • Data analysis approach
    │                                   • Framework type
    │
    language ──────────────────────────▶ STYLE
    │   (EN/AR/FR/ES/etc)              • Writing style
    │                                   • RTL support (Arabic)
    │                                   • Terminology
    │
    year_range ────────────────────────▶ CONTEXT
    │   (2020-2026)                    • Historical depth
    │                                   • Recent vs classic citations
    │
    quartile_filter ───────────────────▶ QUALITY
        (Q1-Q4)                        • Journal standards
                                        • Research rigor


┌─────────────────────────────────────────────────────────────────────────────┐
│                    279+ ACADEMIC FIELDS (MAPPED)                          │
└─────────────────────────────────────────────────────────────────────────────┘

    Field Category          │ Count │ Examples
    ════════════════════════════════════════════════════════════════════════
    Languages              │  18   │ Applied Linguistics, Sociolinguistics, Translation
    Education              │  12   │ Higher Education, Educational Technology, Curriculum
    Psychology             │  10   │ Clinical Psychology, Cognitive Psychology, Social
    Social Sciences        │  15   │ Sociology, Anthropology, Political Science
    Business               │  18   │ Marketing, HR, Finance, Accounting, Management
    Computer Science       │  18   │ AI, ML, NLP, Cybersecurity, Data Science
    Engineering            │  13   │ Civil, Mechanical, Electrical, Biomedical
    Sciences               │  25   │ Physics, Chemistry, Biology, Math, Statistics
    Medical                │  12   │ Medicine, Nursing, Pharmacy, Public Health
    Humanities             │  20   │ History, Philosophy, Literature, Art, Music
    Law                    │   5   │ Law, International Law, Criminal Justice
    Architecture           │   8   │ Architecture, Urban Planning, Interior Design
    Agriculture            │   7   │ Agronomy, Animal Science, Food Science
    Communication          │  10   │ Journalism, Media Studies, Advertising
    Interdisciplinary      │  25   │ Gender Studies, Development, Peace Studies
    Other                  │  73   │ Library Science, Sports, Environment
    ════════════════════════════════════════════════════════════════════════
    TOTAL                  │ 279+  │


┌─────────────────────────────────────────────────────────────────────────────┐
│                    49 PUBLICATION TYPES (STRUCTURES)                        │
└─────────────────────────────────────────────────────────────────────────────┘

    Category              │ Types
    ════════════════════════════════════════════════════════════════════════
    Journal Articles      │ Research Article, Review, Systematic Review, Meta-Analysis
    Theses               │ PhD Dissertation, Master's Thesis, Bachelor's Thesis
    Conference           │ Conference Paper, Poster, Proceedings
    Books                │ Monograph, Book Chapter, Edited Volume
    Reports              │ Technical Report, Policy Brief, White Paper
    Preprints            │ arXiv, bioRxiv, medRxiv
    Government           │ Government Publication, NGO Report, Grant Proposal
    Other                │ Patent, Standard, Magazine Article, Blog Post


┌─────────────────────────────────────────────────────────────────────────────┐
│                    51 RESEARCH METHODOLOGIES                                │
└─────────────────────────────────────────────────────────────────────────────┘

    Quantitative         │ Experimental, Quasi-Experimental, Survey, Longitudinal
    Qualitative          │ Ethnographic, Phenomenological, Grounded Theory, Case Study
    Mixed Methods       │ Triangulation, Convergence, Embedded Design
    Analytical          │ Bibliometric, Scientometric, Content Analysis
    Computational       │ Simulation, Modeling, Network Analysis
    Historical          │ Archival, Documentary, Comparative Historical


┌─────────────────────────────────────────────────────────────────────────────┐
│                    SUPPORTED LANGUAGES (9)                                  │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌────────┬──────────┬─────────────┬──────────────────┐
    │ Code   │ Language  │ Direction   │ OCR Support      │
    ════════════════════════════════════════════════════════════
    │ en     │ English   │ LTR         │ ✅               │
    │ ar     │ العربية   │ RTL         │ ✅               │
    │ fr     │ Français  │ LTR         │ ✅               │
    │ es     │ Español   │ LTR         │ ✅               │
    │ de     │ Deutsch   │ LTR         │ ✅               │
    │ zh     │ 中文      │ LTR         │ ✅ (simplified)  │
    │ ru     │ Русский   │ LTR         │ ✅               │
    │ tr     │ Türkçe    │ LTR         │ ✅               │
    │ ur     │ اردو      │ RTL         │ ✅               │
    └────────┴──────────┴─────────────┴──────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                    DOCUMENT FORMAT SUPPORT MATRIX                            │
└─────────────────────────────────────────────────────────────────────────────┘

    Format     │ Extract │ OCR  │ Tables │ Images │ Metadata │ Ollama
    ════════════════════════════════════════════════════════════════════════
    PDF        │   ✅    │  ✅  │   ✅   │   ✅   │    ✅    │   ✅
    DOCX       │   ✅    │  ❌  │   ✅   │   ✅   │    ✅    │   ✅
    ODT        │   ✅    │  ❌  │   ✅   │   ✅   │    ✅    │   ✅
    RTF        │   ✅    │  ❌  │   ✅   │   ✅   │    ❌    │   ✅
    EPUB       │   ✅    │  ❌  │   ❌   │   ✅   │    ✅    │   ✅
    HTML       │   ✅    │  ❌  │   ❌   │   ✅   │    ✅    │   ✅
    TXT        │   ✅    │  ❌  │   ❌   │   ❌   │    ❌    │   ✅
    PNG        │   ❌    │  ✅  │   ❌   │  N/A   │    ❌    │   ✅
    JPG        │   ❌    │  ✅  │   ❌   │  N/A   │    ❌    │   ✅
    TIFF       │   ❌    │  ✅  │   ❌   │  N/A   │    ❌    │   ✅
    XLSX       │   ✅    │  ❌  │   ✅   │   ❌   │    ✅    │   ✅
    PPTX       │   ✅    │  ❌  │   ✅   │   ✅   │    ✅    │   ✅


┌─────────────────────────────────────────────────────────────────────────────┐
│                    SYSTEM PROTECTION RULES                                   │
└─────────────────────────────────────────────────────────────────────────────┘

    🔒 RULE #1: OLLAMA CORE PROTECTION
    ═══════════════════════════════════
    • qwen2.5vl:3b is the PERMANENT AI brain
    • DO NOT change model unless explicitly required
    • All intelligence flows through this model
    • 16k context window handles all tasks

    🔒 RULE #2: DATABASE INTEGRITY
    ═══════════════════════════════════
    • Learning database grows with every use
    • Patterns improve paper quality over time
    • DO NOT delete or reset without backup
    • Regular backups recommended

    🔒 RULE #3: WORKFLOW CONSISTENCY
    ═══════════════════════════════════
    • GitHub workflow form is the primary interface
    • All parameters must be stored in database
    • Changes to form = changes to learning

    🔒 RULE #4: DEPENDENCY MANAGEMENT
    ═══════════════════════════════════
    • Document processor handles ALL formats
    • Playwright for dynamic content only
    • Fallback methods always available


┌─────────────────────────────────────────────────────────────────────────────┐
│                    QUICK START COMMANDS                                     │
└─────────────────────────────────────────────────────────────────────────────┘

    # Initialize System
    python research_hunter_system.py

    # Run Research Workflow
    python -c "
    from research_hunter_system import *
    from academic_learning_database import *
    
    system = ResearchHunterSystem()
    config = WorkflowConfig(
        research_topic='Your topic here',
        academic_field='Applied Linguistics',
        publication_type='thesis_master',
        language='en'
    )
    paper = system.generate_paper(config)
    print(paper)
    "

    # Process Documents
    python -c "
    from universal_document_processor import *
    processor = UniversalDocumentProcessor()
    result = processor.process('path/to/document.pdf')
    print(result.full_text)
    "

    # Web Scraping
    python -c "
    from research_hunter_system import *
    system = ResearchHunterSystem()
    result = system.scrape_website('https://scholar.google.com/...')
    print(result)
    "


┌─────────────────────────────────────────────────────────────────────────────┐
│                    FILE STRUCTURE                                          │
└─────────────────────────────────────────────────────────────────────────────┘

    research-hunters/
    │
    ├── 📄 CORE FILES
    │   ├── research_hunter_v2-4.py      # Main search engine
    │   ├── research_hunter_system.py     # System orchestrator ⭐ NEW
    │   ├── universal_document_processor.py # Document handler ⭐ NEW
    │   └── academic_learning_database.py  # Learning engine ⭐ NEW
    │
    ├── 🗄️ SUPPORT FILES
    │   ├── ollama_wrapper.py            # Ollama API wrapper
    │   ├── learning_integration.py       # Learning system
    │   ├── llm_research_hunter.py       # LLM integration
    │   ├── scopus_checker.py            # Journal ranking
    │   └── search_cache.py              # Search caching
    │
    ├── ⚙️ GITHUB ACTIONS
    │   ├── actions/
    │   │   └── ollama-ai/               # Ollama setup (PROTECTED)
    │   └── workflows/
    │       ├── research-search.yml       # Main workflow
    │       └── run-integrated.yml       # Integrated system
    │
    └── 📚 DOCUMENTATION
        ├── README.md
        ├── INTEGRATION.md
        └── SYSTEM_ARCHITECTURE.md       # This file


┌─────────────────────────────────────────────────────────────────────────────┐
│                    VERSION HISTORY                                          │
└─────────────────────────────────────────────────────────────────────────────┘

    v2-4.0 - Base research hunter with 128+ platforms
    v2-4.1 - Added Ollama integration
    v2-4.2 - Protected Ollama core (qwen2.5vl:3b)
    v2-4.3 - Added document processor (all formats)
    v2-4.4 - Added learning database (patterns)
    v2-4.5 - Added Playwright (web scraping)
    v2-4.6 - Added academic writing engine
    v2-4.7 - Mapped workflow form to paper generation
    v2-4.8 - Comprehensive mind map documentation


                    🔬 RESEARCH HUNTER v2-4 - COMPLETE SYSTEM 🔬
                    Everything you need for academic research
                    Built on Ollama qwen2.5vl:3b (16k context)
