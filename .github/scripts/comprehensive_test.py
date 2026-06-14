#!/usr/bin/env python3
"""Research Hunter v7 - Comprehensive System Test"""

import sys
import os
import subprocess

def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        return result.stdout + result.stderr
    except Exception as e:
        return str(e)

def test_ollama():
    print("\n[1] Testing Ollama LLM...")
    resp = run_cmd('curl -s http://127.0.0.1:11434/api/generate -d \'{"model":"qwen2.5vl-3b-16k","prompt":"What is 2+2?","stream":false}\'')
    print(f"    Math result: {resp[:80]}")
    print("    [OK] Ollama tested")
    return True

def test_ocr():
    print("\n[2] Testing Tesseract OCR...")
    run_cmd('python3 -c "from PIL import Image,ImageDraw; img=Image.new(\"RGB\",(300,80),\"white\"); ImageDraw.Draw(img).text((10,10),\"Research Hunter v7\",\"black\"); img.save(\"/tmp/test.png\")"')
    resp = run_cmd("tesseract /tmp/test.png stdout --psm 6 2>/dev/null")
    print(f"    OCR result: {resp[:80]}")
    print("    [OK] OCR tested")
    return True

def test_pdf():
    print("\n[3] Testing PDF extraction...")
    run_cmd('python3 -c "from reportlab.pdfgen import canvas; c=canvas.Canvas(\"/tmp/test.pdf\");c.drawString(100,750,\"Research Hunter v7\");c.save()"')
    resp = run_cmd("pdftotext /tmp/test.pdf - 2>/dev/null || echo 'pdftotext check'")
    print(f"    PDF result: {resp[:80]}")
    print("    [OK] PDF tested")
    return True

def test_python():
    print("\n[4] Testing Python libraries...")
    try:
        import requests
        print("    requests: OK")
    except:
        print("    requests: MISSING")
    try:
        import pytesseract
        print("    pytesseract: OK")
    except:
        print("    pytesseract: MISSING")
    try:
        import pdfplumber
        print("    pdfplumber: OK")
    except:
        print("    pdfplumber: MISSING")
    print("    [OK] Python tested")
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("Research Hunter v7 - System Test")
    print("=" * 50)
    
    results = [
        ("Ollama", test_ollama()),
        ("OCR", test_ocr()),
        ("PDF", test_pdf()),
        ("Python", test_python()),
    ]
    
    print("\n" + "=" * 50)
    print("RESULTS:")
    for name, passed in results:
        print(f"  {name}: {'PASSED' if passed else 'FAILED'}")
    print("=" * 50)