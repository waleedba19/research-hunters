# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Project documentation infrastructure
- MIT License for commercial use
- CONTRIBUTING.md for guidelines

### Planned
- Docker support for local development
- Comprehensive test suite
- API for programmatic access

---

## [6.0.0] - 2024-06-10

### Added
- **70+ Research Platforms** — Expanded from earlier versions
- **14-Layer PDF Download Chain** — Upgraded from 7 layers
- **Single-Folder Mode** — Optional toggle for simplified organization
- **Self-Aware Duplicate Scanning** — Skips existing PDFs
- **Research-Type Context-Aware Filtering** — Auto-limits by selected type
- **Walter Ghost Auto-Install** — Graceful fallback if missing
- **Concurrent Search+Download** — 5+ threads
- **Multi-Language Support** — EN/AR/FR/ES/DE/ZH/PT/TR
- **Title-Aware Search Intelligence** — Understands topic, finds related papers
- **AcademicProxy System** — Auto-detects qoder G4F proxy
- **RedListManager** — CSV + HTML tracking of failed downloads
- **16-Folder Hierarchy** — Q1-Q4, MA/PhD, Books, Conference, Libya/MENA/Neighbor
- **Extended Q1/Q2 Journal Database** — Fuzzy matching
- **Libyan University Deep Search** — UB, UTripoli, AlFateh, Sebha, Mandumah, CERIST
- **Preprint Repositories** — bioRxiv, medRxiv, PsyArXiv, SocArXiv, OSF Preprints
- **Open Access Publishers** — MDPI, OpenAIRE, PLoS, SpringerOpen, WileyOpen
- **Government/Research Portals** — Science.gov, NASA NTRS, CERN, WorldWideScience
- **Social Networks** — Academia.edu, PaperPanda
- **Regional OA** — Redalyc, Bioline, SSOAR, JSTOR Open, EBSCO Dissertations

### Changed
- **Checkpoint/Resume System** — Improved crash recovery
- **Enhanced Relevance Filtering** — Tighter thresholds
- **FIELDS Expansion** — 48 academic fields
- **STUDY_TYPES Expansion** — 30 study types
- **Professional DOCX Reports** — Cover page, executive summary, APA references

### Removed
- Academic writing engine (search only)

---

## [2.4] - Previous Version

### Added
- Initial GitHub Actions workflow
- Cumulative mode for continuous research
- Auto-trigger chaining for long-running searches

### Features
- Basic PDF download
- Simple report generation
- Limited platform support

---

## Version History

| Version | Date | Status |
|---------|------|--------|
| 6.0.0 | 2024-06-10 | Current |
| 2.4 | Earlier | Previous |

---

## Release Types

- **Major** (x.0.0) — Breaking changes, major feature additions
- **Minor** (6.x.0) — New features, backward compatible
- **Patch** (6.0.x) — Bug fixes, small improvements

---

## How to Update

```bash
# Pull latest changes
git pull origin main

# Update dependencies
pip install -r requirements.txt
npm update
```

---

## Deprecation Policy

- Minor versions may deprecate features with 2-release notice
- Breaking changes only in major versions
- Old features documented until removed

---

*This changelog follows [Keep a Changelog](https://keepachangelog.com/) standards.*