"""test_crossref_direct.py — Hit CrossRef API directly via curl."""
import os, json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import urllib.request, urllib.parse

# Test 1: Direct CrossRef API call with our query
query = "Dörnyei Z 2009 L2 motivational self system"
url = "https://api.crossref.org/works?" + urllib.parse.urlencode({
    "query": query,
    "rows": 3,
    "select": "title,author,published,DOI",
})
print(f"URL: {url}", flush=True)
req = urllib.request.Request(url, headers={"User-Agent": "literature-review-verifier/0.1 (mailto:test@example.com)"})
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    items = data.get("message", {}).get("items", [])
    print(f"Found {len(items)} items via DIRECT call", flush=True)
    for it in items:
        title = ((it.get("title") or [""])[0])[:80]
        doi = it.get("DOI")
        print(f"  - {title!r} doi={doi}", flush=True)
except Exception as e:
    print(f"DIRECT FAILED: {e}", flush=True)

print()
print("=" * 60)
print("Now test v2-4's wrapper:", flush=True)
sys.path.insert(0, ".")
from research_hunter_v2_4 import search_crossref
try:
    papers = search_crossref(query, year_from=2008, limit=3)
    print(f"v2-4 crossref returned {len(papers)} papers", flush=True)
    for p in papers:
        print(f"  - {p.get('title','')[:80]!r} doi={p.get('doi')}", flush=True)
except Exception as e:
    import traceback
    print(f"v2-4 crossref FAILED: {e}", flush=True)
    traceback.print_exc()
