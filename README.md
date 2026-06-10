# Research Hunter v6

> 🔬 Academic Research Automation — Search 70+ platforms for papers, download PDFs, and generate professional reports.

[![Research Hunter](https://img.shields.io/badge/Research%20Hunter-v6-blue.svg)](https://github.com/waleedba19/research-hunters)
[![Python](https://img.shields.io/badge/Python-3.12+-green.svg)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-20+-yellow.svg)](https://nodejs.org)
[![License](https://img.shields.io/badge/License-MIT-orange.svg)](LICENSE)
[![GitHub Actions](https://github.com/waleedba19/research-hunters/workflows/Research%20Hunter%2024%2F7%20Cloud%20Search/badge.svg)](https://github.com/waleedba19/research-hunters/actions)

**Research Hunter** is a powerful academic paper search and download tool that queries 70+ research platforms, retrieves PDFs, and organizes results by Scopus quartile (Q1-Q4). It runs 24/7 on GitHub Actions with checkpoint/resume support.

---

## ✨ Features

- **70+ Research Platforms** — Search across academic databases, preprint servers, government portals, and more
- **PDF Download Chain** — 14-layer fallback system for retrieving papers
- **Scopus Quartile Classification** — Automatic Q1-Q4 categorization
- **Checkpoint/Resume** — Never lose progress; recover from interruptions
- **Multi-Language Support** — English, Arabic, French, Spanish, German, Chinese, Portuguese, Turkish
- **Professional Reports** — Generate DOCX reports with cover page, executive summary, and references
- **24/7 Cloud Execution** — Runs on GitHub Actions with automatic chaining
- **Single-Folder Mode** — Optional toggle for simplified organization

---

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+ (for DOCX reports)
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/waleedba19/research-hunters.git
cd research-hunters

# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
npm install
```

### Usage (CLI)

```bash
# Basic search
python research_hunter_v2-4.py --title "Your research topic"

# With research questions
python research_hunter_v2-4.py --title "Effects of AI on education" \
  --rq1 "How does AI impact learning outcomes?" \
  --rq2 "What are the ethical concerns?"

# Specify field and study type
python research_hunter_v2-4.py --title "Language learning strategies" \
  --field "2 - Second Language Acquisition" \
  --study-type "6 - Qualitative Study" \
  --year-from 2015

# Deep mode with all platforms (4-8 hours)
python research_hunter_v2-4.py --title "Your Topic" --mode deep

# Sample mode (quick test, ~10 minutes)
python research_hunter_v2-4.py --title "Your Topic" --mode sample
```

### Command-Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--title` | Research topic/title (required) | - |
| `--rq1` to `--rq5` | Research questions | - |
| `--field` | Academic field (1-48) or "auto" | auto |
| `--study-type` | Study type (1-30) or "auto" | auto |
| `--year-from` | Start year | All years |
| `--year-to` | End year | Current year |
| `--mode` | Search mode: sample/quick/field/deep | deep |
| `--max-batches` | Max batches per run (0=all) | 0 |
| `--language` | Search language (1-8) | 1 (English) |
| `--scihub` | Enable Sci-Hub | false |
| `--single-folder` | Single folder mode | false |
| `--keywords` | Custom keywords (comma-separated) | auto |
| `--proxy` | Proxy: y=auto, p=custom, n=skip | n |

### Language Codes

| Code | Language |
|------|----------|
| 1 | English |
| 2 | Arabic |
| 3 | French |
| 4 | Spanish |
| 5 | English + Arabic |
| 6 | English + French |
| 7 | English + Arabic + French |
| 8 | All Languages |

---

## 📊 GitHub Actions Usage

Run the workflow manually via GitHub Actions:

1. Go to **Actions** tab in your repository
2. Select **"Research Hunter 24/7 Cloud Search"**
3. Click **Run workflow**
4. Fill in parameters:
   - **Title**: Your research topic
   - **Mode**: sample (~15min), quick (~30min), field (~2hr), deep (4-8hr+)
   - **Field**: Academic field or "auto"
   - **Study Type**: Type of research or "auto"
   - **Max Batches**: Papers per run (12 batches ≈ 600 papers in 6 hours)

The workflow automatically chains runs until complete, resuming from checkpoints.

---

## 📁 Output Structure

```
pdf_files/
└── RESEARCH_YOUR_TOPIC/
    ├── Q1_Journals/           # Top-tier papers
    ├── Q2_Journals/           # Good quality
    ├── Q3_Journals/           # Acceptable
    ├── Q4_Journals/           # Lower tier
    ├── MA_Theses/             # Master's theses
    ├── PhD_Dissertations/     # PhD dissertations
    ├── Books/                 # Academic books
    ├── Conference_Papers/     # Conference proceedings
    ├── Libya_Universities/    # Libyan institutions
    ├── MENA_Region/           # Middle East & North Africa
    ├── NEIGHBOR_NorthAfrica/  # neighboring countries
    ├── HIGH_CITED/            # Highly cited papers
    ├── 🔴RED_LIST/            # Pending downloads (manual)
    ├── search_cache.json      # Resume data
    ├── .checkpoint.json       # Progress checkpoint
    └── research_report.docx   # Generated report
```

---

## 🔧 Configuration

### Environment Variables (Optional)

Create a `.env` file for local development:

```bash
# Proxy settings (optional)
PROXY_URL=

# Sci-Hub enable flag
SCIHUB_ENABLED=0

# Max batches per run
MAX_BATCHES=12

# G4F proxy (auto-detected)
G4F_PROXY=
```

### GitHub Secrets

For GitHub Actions, add these in repository Settings → Secrets:

| Secret | Description |
|--------|-------------|
| - | (Currently no additional secrets required) |

---

## 📋 Supported Platforms

### Academic Databases
- Semantic Scholar, CrossRef, OpenAlex, PubMed, IEEE Xplore
- Springer, Elsevier (ScienceDirect), Wiley, Taylor & Francis
- ACM Digital Library, JSTOR, ERIC, PsycINFO

### Preprint Servers
- arXiv, bioRxiv, medRxiv, PsyArXiv, SocArXiv, OSF Preprints

### Open Access Publishers
- MDPI, PLOS, Frontiers, BMC, SpringerOpen, Wiley Open Access

### Government & Research Portals
- Science.gov, NASA NTRS, CERN Document Server, WorldWideScience
- WHO IRIS, UNESCO IBE, OECD iLibrary

### Regional & Institutional
- Libyan universities (UB, UTripoli, AlFateh, Sebha)
- Mandumah, CERIST, Redalyc, Bioline, SSOAR

*(70+ total platforms)*

---

## 🔐 Scopus Quartile Classification

Papers are classified by journal quartile:

| Quartile | Description | Color |
|----------|-------------|-------|
| Q1 | Top-tier (top 25%) | 🟢 Green |
| Q2 | Good quality (25-50%) | 🔵 Blue |
| Q3 | Acceptable (50-75%) | 🟡 Yellow |
| Q4 | Lower tier (75-100%) | 🔴 Red |
| Not Found | Not indexed | ⚪ Gray |

---

## 📝 Report Generation

Generate professional DOCX reports:

```bash
# After running the search
node generate_report.js report_data.json research_report.docx
```

The report includes:
- Cover page with metadata
- Executive summary
- Scopus quartile distribution
- Detailed papers table
- Top authors analysis
- References (APA 7th Edition)

---

## 🔄 Checkpoint & Resume

The system automatically saves progress every 5 papers:
- `._checkpoint.json` — Current phase and progress
- `search_cache.json` — Found/downloaded papers tracking

If interrupted, simply re-run with the same parameters to resume.

---

## 🛠️ Development

### Project Structure

```
research-hunters/
├── research_hunter_v2-4.py  # Main Python script
├── generate_report.js        # DOCX report generator
├── scopus_checker.py         # Quartile verification
├── search_cache.py          # Search state management
├── requirements.txt         # Python dependencies
├── package.json             # Node.js dependencies
├── .github/
│   └── workflows/
│       └── run.yml          # GitHub Actions workflow
└── docs/                    # Documentation (future)
```

### Running Tests

```bash
# Unit tests (when implemented)
python -m pytest tests/

# Lint
python -m flake8 .
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## 📌 Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

---

## 📧 Support

For questions or issues, please open an issue on GitHub.

---

**Made with ❤️ for researchers everywhere**