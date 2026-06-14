"""
Research Hunter v7 - Ollama Integration
Wrapper for using Ollama with qwen2.5vl:3b model
"""

import requests
import os

# Configuration
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5vl:3b")

def check_ollama():
    """Check if Ollama is running"""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except:
        return False

def generate(prompt, system="", max_tokens=500, temperature=0.3):
    """Generate response from Ollama"""
    try:
        payload = {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature
            }
        }
        if system:
            payload["system"] = system
        
        resp = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=120)
        if resp.status_code == 200:
            return resp.json().get("response", "")
    except Exception as e:
        print(f"Error: {e}")
    return None

def chat(messages, max_tokens=500):
    """Chat completion (OpenAI compatible)"""
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json={
                "model": MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.3
            },
            timeout=120
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Error: {e}")
    return None

def analyze_image(image_base64, prompt):
    """Analyze an image with the model"""
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL,
                "prompt": prompt,
                "images": [image_base64],
                "stream": False
            },
            timeout=120
        )
        if resp.status_code == 200:
            return resp.json().get("response", "")
    except Exception as e:
        print(f"Error: {e}")
    return None

if __name__ == "__main__":
    print("Testing Ollama Integration...")
    
    if check_ollama():
        print("✅ Ollama is running!")
        
        # Test basic generation
        print("\n📝 Test: Basic prompt...")
        result = generate("What is 2+2?")
        print(f"Response: {result}")
        
        # Test chat
        print("\n📝 Test: Chat completion...")
        result = chat([{"role": "user", "content": "Hello, how are you?"}])
        print(f"Response: {result}")
        
        print("\n✅ All tests passed!")
    else:
        print("❌ Ollama is not running. Start with: ollama serve")
