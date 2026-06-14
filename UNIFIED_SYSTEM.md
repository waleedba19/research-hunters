# 🔬 RESEARCH HUNTER v7 - UNIFIED SYSTEM

## The Problem (Before)

You had **6 scattered workflows** that were confusing:

```
❌ run.yml                 - Main research (overlapping features)
❌ test-comprehensive.yml  - Testing only
❌ final-verification.yml   - Verification only
❌ research-search.yml     - Search only
❌ run-integrated.yml      - Integrated system (partial)
❌ research-hunter-v8.yml  - v8 system (duplicates)
```

Each workflow had:
- Different form fields
- Overlapping features
- No clear central point
- Hard to debug when something broke

---

## The Solution (Now)

**ONE unified workflow** that combines everything:

```
✅ UNIFIED-research-hunter.yml  - THE ONLY WORKFLOW YOU NEED
```

```
┌─────────────────────────────────────────────────────────────────────┐
│                    UNIFIED RESEARCH HUNTER v7                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    ONE FORM, 5 MODES                         │   │
│  │                                                             │   │
│  │  1. verify-only    → Test system only                       │   │
│  │  2. research-only  → Search & download papers                │   │
│  │  3. learn-only     → Learn patterns from research           │   │
│  │  4. generate-only  → Generate paper from patterns           │   │
│  │  5. full-research  → All: Research + Learn + Generate        │   │
│  │                                                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                 CENTRAL ORCHESTRATOR                        │   │
│  │                                                              │   │
│  │   setup-ollama ──┬── verify-system ── research ── learn ── generate  │
│  │                  │          │              │              │         │
│  │                  ▼          ▼              ▼              ▼         │
│  │              [jobs run sequentially, outputs passed]                │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    FINAL SUMMARY                             │   │
│  │                                                              │   │
│  │   📊 Shows what ran, what succeeded, where to find results  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## How It Works

### Step 0: Setup Ollama (Always Runs First)
```
┌────────────────────────────────────────────────┐
│  🔧 setup-ollama                               │
│  ├── Checkout code                             │
│  ├── Install Ollama + qwen2.5vl:3b            │
│  ├── Install OCR (16 languages)               │
│  ├── Start Ollama server                      │
│  ├── Install Python dependencies              │
│  └── Test Ollama (math, translation, vision)  │
└────────────────────────────────────────────────┘
```

### Step 1: Verify System (If mode contains 'verify')
```
┌────────────────────────────────────────────────┐
│  🧪 verify-system (depends on setup-ollama)   │
│  ├── Test all Python libraries                │
│  ├── Test Document Processor                  │
│  ├── Test Learning Database                   │
│  ├── Test Research Hunter Core               │
│  └── Test Tesseract OCR                      │
└────────────────────────────────────────────────┘
```

### Step 2: Research (If mode contains 'research')
```
┌────────────────────────────────────────────────┐
│  🔍 research (depends on setup-ollama)         │
│  ├── Parse form inputs                         │
│  ├── Start Ollama server                      │
│  ├── Run research_hunter_v2-4.py              │
│  │   └── Searches 70+ platforms               │
│  │   └── Downloads PDFs                       │
│  │   └── Deduplicates                         │
│  ├── Check results                            │
│  └── Upload research data                      │
└────────────────────────────────────────────────┘
```

### Step 3: Learn (If mode contains 'learn')
```
┌────────────────────────────────────────────────┐
│  🧠 learn (depends on research)               │
│  ├── Connect to Learning Database             │
│  ├── Parse field & paper type                 │
│  ├── Create/update field patterns             │
│  ├── Learn methodology patterns               │
│  └── Store in academic_learning.db            │
└────────────────────────────────────────────────┘
```

### Step 4: Generate Paper (If mode contains 'generate')
```
┌────────────────────────────────────────────────┐
│  📝 generate (depends on learn)               │
│  ├── Create WorkflowConfig                     │
│  ├── Use Ollama to generate paper             │
│  ├── Save as Markdown (.md)                   │
│  ├── Save as DOCX (.docx)                    │
│  └── Upload generated papers                  │
└────────────────────────────────────────────────┘
```

### Step 5: Final Summary (Always Runs Last)
```
┌────────────────────────────────────────────────┐
│  📊 final-summary (always, after all jobs)    │
│  ├── Show which jobs ran                      │
│  ├── Show topic & settings                   │
│  ├── Show artifact locations                 │
│  └── Show run URL                            │
└────────────────────────────────────────────────┘
```

---

## The Single Form

Instead of 6 different forms, you now have **ONE form**:

### Operation Mode (Required)
| Option | What It Does |
|--------|--------------|
| `verify-only` | Test system only |
| `research-only` | Search & download papers |
| `learn-only` | Learn patterns from papers |
| `generate-only` | Generate paper from patterns |
| `full-research` | All: Research + Learn + Generate |

### Research Topic (Required)
Your research title/question

### Research Questions (Optional)
Up to 3 research questions

### Academic Field
25 common fields (Applied Linguistics, Education, CS, etc.)

### Paper Type
10 types (Research Article, Thesis, Systematic Review, etc.)

### Language
9 options (English, Arabic, French, Spanish, etc.)

### Search Mode
7 depths (Sample → Mega)

---

## Benefits

| Before | After |
|--------|-------|
| 6 workflow files | 1 workflow file |
| Overlapping features | Clear separation |
| Hard to debug | Easy to see which step failed |
| Duplicate code everywhere | DRY (Don't Repeat Yourself) |
| Confusing form options | ONE clear form |
| Unknown dependencies | Explicit job dependencies |

---

## How to Use

### 1. Go to GitHub Actions
```
https://github.com/waleedba19/research-hunters/actions
```

### 2. Select "UNIFIED-research-hunter"
You'll see ONE workflow with ONE form.

### 3. Choose Your Mode
- **verify-only**: Test if system is working
- **research-only**: Just search for papers
- **full-research**: Do everything

### 4. Fill the Form
All options in ONE place.

### 5. Run & Watch
See clear progress:
```
✅ setup-ollama
✅ verify-system
✅ research
✅ learn
✅ generate
✅ final-summary
```

---

## Debugging Made Easy

### Before (Confusing)
```
Which workflow has the bug?
run.yml? test-comprehensive.yml? research-hunter-v8.yml?
```

### After (Clear)
```
Job "learn" failed at step "Create/update field patterns"
→ Easy to find and fix in ONE file
```

---

## Adding New Features

### Before
```
Add feature to which workflow?
run.yml? research-search.yml? run-integrated.yml?
```

### After
```
Edit ONE file: UNIFIED-research-hunter.yml
Add step to the appropriate job:
- New setup step → setup-ollama
- New test → verify-system
- New search feature → research
- New learning → learn
- New output format → generate
```

---

## File Structure

```
.github/
├── workflows/
│   └── UNIFIED-research-hunter.yml    ← THE ONLY WORKFLOW
│   └── (OLD workflows - can be deleted)
├── actions/
│   └── ollama-ai/
│       └── action.yml                 ← Shared Ollama setup
```

---

## Legacy Workflows (Marked for Deletion)

These workflows are now obsolete and can be deleted:

1. `run.yml` - Replaced by unified workflow
2. `test-comprehensive.yml` - Use verify-only mode
3. `final-verification.yml` - Use verify-only mode
4. `research-search.yml` - Use research-only mode
5. `run-integrated.yml` - Use full-research mode
6. `research-hunter-v8.yml` - Use full-research mode

---

## Quick Reference

| Need | Mode to Use |
|------|-------------|
| Test system | `verify-only` |
| Find papers | `research-only` |
| Generate paper | `generate-only` |
| Do everything | `full-research` |

---

**Questions?** The system is now centralized and easy to understand! 🎯