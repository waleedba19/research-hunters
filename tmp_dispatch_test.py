import json, urllib.request, urllib.error, subprocess, sys, os

token = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True).stdout.strip()
if not token:
    print("ERROR: no token", file=sys.stderr)
    sys.exit(1)

payload_data = json.dumps({
    "ref": "main",
    "inputs": {
        "chat_id": "6792230101",
        "params_json": json.dumps({
            "title": "AI-driven drug discovery for antibiotic resistance",
            "field": "biomedical",
            "research_questions": ["What ML models are used for antibiotic discovery?", "How effective are GNNs for molecular property prediction?"],
            "year_from": 2020,
            "year_to": 2025,
            "platforms": ["google_scholar", "pubmed", "arxiv"],
            "max_papers": 15,
            "download_pdfs": False,
        }),
    },
})

req = urllib.request.Request(
    "https://api.github.com/repos/wo312092-creator/literature-review-verifier/actions/workflows/hunt-run.yml/dispatches",
    data=payload_data.encode(),
    method="POST",
)
req.add_header("Authorization", f"Bearer {token}")
req.add_header("Accept", "application/vnd.github.v3+json")
req.add_header("Content-Type", "application/json")
req.add_header("User-Agent", "SearchSleepingBot-test")

try:
    with urllib.request.urlopen(req, timeout=15) as r:
        print(f"Dispatched! Status: {r.status}")
        print(f"Body: {r.read().decode()[:200]}")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.reason}", file=sys.stderr)
    print(e.read().decode()[:1000], file=sys.stderr)
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
