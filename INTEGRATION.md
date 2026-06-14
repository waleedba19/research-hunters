# 🔬 Research Hunter v7 - System Integration

## Overview

This document explains how Research Hunter v7 integrates with Ollama AI for research paper analysis.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    GitHub Actions Workflow                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐      ┌──────────────────────────────┐    │
│  │  ollama-ai action │ ───► │  run-integrated.yml          │    │
│  │  (.github/actions)│      │  (.github/workflows)          │    │
│  └──────────────────┘      └──────────────────────────────┘    │
│           │                            │                        │
│           ▼                            ▼                        │
│  ┌──────────────────┐      ┌──────────────────────────────┐    │
│  │ Caches:          │      │ research_hunter_v2-4.py       │    │
│  │ • Ollama v0.30.4 │      │ (uses qwen2.5vl:3b model)     │    │
│  │ • qwen2.5vl:3b   │      │                              │    │
│  │ • Tesseract OCR  │      │ _call_kimi() ──────────────► │    │
│  └──────────────────┘      │     └─► Ollama API          │    │
│                             │         (qwen2.5vl:3b)    │    │
│                             └──────────────────────────────┘    │
│                                                                    │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Ollama Action (`.github/actions/ollama-ai/action.yml`)

This reusable action sets up the AI environment:

| Component | Version | Purpose |
|-----------|---------|---------|
| Ollama | 0.30.4 | Local LLM server |
| Model | qwen2.5vl:3b | Vision + text model (16k context) |
| Tesseract | 5.x | OCR for scanned documents |
| Languages | 16 | AR, FR, DE, ES, ZH, JA, KO, RU, etc. |

**Key Features:**
- Caches model after first download (~3.2GB)
- Subsequent runs use cache (fast startup)
- Tests model before declaring ready

### 2. Integrated Workflow (`run-integrated.yml`)

Three modes available:

| Mode | Description | Time |
|------|-------------|------|
| `verify-only` | Quick system check | ~3 min |
| `verify-then-research` | Full analysis | ~10 min |
| `research-only` | Skip verification | ~7 min |

### 3. Research Hunter Script (`research_hunter_v2-4.py`)

The main script that uses Ollama:

```python
def _call_kimi(prompt: str) -> str | None:
    """
    Uses qwen2.5vl:3b model (verified working)
    """
    r = requests.post(
        "http://localhost:11434/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        json={"model": "qwen2.5vl:3b",
              "messages": [{"role": "user", "content": prompt}],
              "max_tokens": 1400, "temperature": 0.2},
        timeout=60,
    )
    ...
```

### 4. Ollama Wrapper (`ollama_wrapper.py`)

Clean API for Ollama operations:

```python
from ollama_wrapper import check_ollama, generate, chat, analyze_image

# Check if running
if check_ollama():
    # Generate text
    result = generate("Analyze this research topic...")
    
    # Chat
    result = chat([{"role": "user", "content": "Hello!"}])
    
    # Analyze images
    result = analyze_image(base64_image, "What do you see?")
```

## How Caching Works

### First Run (~5-10 minutes)
```
1. GitHub Actions starts
2. Cache miss → Downloads Ollama (~100MB)
3. Downloads model qwen2.5vl:3b (~3.2GB)
4. Installs Tesseract OCR
5. Caches all to GitHub Actions cache
```

### Subsequent Runs (~1-2 minutes)
```
1. GitHub Actions starts
2. Cache hit → Uses cached Ollama + model
3. Starts Ollama server
4. Runs research
```

## Usage

### Option 1: Use run-integrated.yml

1. Go to **Actions** tab
2. Select **"Research Hunter v7 - Integrated System"**
3. Click **"Run workflow"**
4. Choose mode and enter research topic
5. Click **Run**

### Option 2: Use research_hunter_v2-4.py directly

1. Install Ollama:
   ```bash
   curl -fsSL https://ollama.ai/install.sh | sh
   ollama pull qwen2.5vl:3b
   ```

2. Start server:
   ```bash
   ollama serve
   ```

3. Run script:
   ```bash
   python research_hunter_v2-4.py --title "Your Topic"
   ```

## Troubleshooting

### "Model not found" error
```bash
ollama pull qwen2.5vl:3b
```

### "Connection refused" error
```bash
ollama serve
# Keep running in background
nohup ollama serve > /tmp/ollama.log 2>&1 &
```

### "Ollama not installed" error
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

## Verification

Run the integrated workflow and check for these outputs:

```
✅ Ollama server running!
✅ qwen2.5vl:3b model ready
✅ All Python libraries working
✅ System verification complete
```

## Files

| File | Purpose |
|------|---------|
| `.github/actions/ollama-ai/action.yml` | Reusable action for Ollama setup |
| `.github/workflows/run-integrated.yml` | Main workflow with verification |
| `research_hunter_v2-4.py` | Research script using Ollama |
| `ollama_wrapper.py` | Clean API wrapper for Ollama |
| `research_database.py` | SQLite tracking database |
| `ollama_processor.py` | LLM processing with chunking |

## Security

- No API keys needed (runs locally)
- All data stays in GitHub Actions
- Model cached securely
- No external calls except Ollama download