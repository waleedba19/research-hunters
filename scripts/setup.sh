#!/usr/bin/env bash
set -euo pipefail

MODEL="${1:-qwen2.5vl:3b}"
OLLAMA_VERSION="${2:-0.30.4}"

echo "=== Research Hunter — Unified Setup ==="
echo "Model: $MODEL"
echo ""

# ── System packages ──────────────────────────────────────────
if command -v apt-get &>/dev/null; then
    echo "Installing Tesseract OCR + languages..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq tesseract-ocr \
        tesseract-ocr-ara tesseract-ocr-fra tesseract-ocr-deu \
        tesseract-ocr-spa tesseract-ocr-chi-sim tesseract-ocr-jpn \
        tesseract-ocr-kor tesseract-ocr-rus tesseract-ocr-por \
        tesseract-ocr-ita tesseract-ocr-tur tesseract-ocr-hin \
        tesseract-ocr-urd tesseract-ocr-fas poppler-utils
    sudo apt-get clean
    echo "  OK"
else
    echo "Skipping apt-get (not Linux)"
fi

# ── Python dependencies ──────────────────────────────────────
echo "Installing Python packages..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
pip install -q -r "$PROJECT_DIR/requirements.txt"
echo "  OK"

# ── Ollama ───────────────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
    echo "Installing Ollama $OLLAMA_VERSION..."
    curl -fsSL https://ollama.ai/install.sh | sh
fi

echo "Starting Ollama server..."
pkill -f "ollama serve" 2>/dev/null || true
sleep 1
nohup ollama serve > /tmp/ollama.log 2>&1 &
for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
        echo "  Ollama server running"
        break
    fi
    sleep 1
done

echo "Pulling model $MODEL..."
ollama pull "$MODEL"
echo "  OK"

# ── Verify ───────────────────────────────────────────────────
echo ""
echo "=== Running verification ==="
python "$SCRIPT_DIR/verify.py" --model "$MODEL"
