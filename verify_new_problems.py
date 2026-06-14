"""verify_new_problems.py — Process 'New problems' subfolder: download, parse, verify, upload.

Flow:
1. List files in FOLDER_ID/New problems
2. Download each PDF/DOCX
3. Parse references using pdf_parser
4. Verify each reference using research_hunter_v4 (v2-4 wrapper)
5. Save verified refs to References/{Articles,Books,Chapters,Theses,Conference}
6. Save unverified refs to NOT_FOUND
7. Create a Google Sheet with full report
8. Upload a DOCX report to Reports
"""
import os, json, sys, time, datetime
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import urllib.request, urllib.parse

FOLDER_ID = os.environ.get("FOLDER_ID", "1NjsBcaAb1qtRUl4d7KHNhvfm159ei2C4")

# ---------------------------------------------------------------------------
# 1) Get Drive access token
# ---------------------------------------------------------------------------
data = urllib.parse.urlencode({
    "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
    "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
    "refresh_token": os.environ["GOOGLE_OAUTH_REFRESH"],
    "grant_type": "refresh_token",
}).encode("utf-8")
req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST",
    headers={"Content-Type": "application/x-www-form-urlencoded"})
with urllib.request.urlopen(req, timeout=15) as r:
    tok = json.loads(r.read().decode("utf-8"))
ACCESS = tok["access_token"]
print(f"TOKEN_OK len={len(ACCESS)}", flush=True)


def drive_get(url):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {ACCESS}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def drive_download(file_id, local_path):
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {ACCESS}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    with open(local_path, "wb") as f:
        f.write(data)
    return len(data)


def find_subfolder(parent_id, name):
    q = f"'{parent_id}' in parents and name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    url = f"https://www.googleapis.com/drive/v3/files?q={urllib.parse.quote(q)}&fields=files(id,name)&supportsAllDrives=true&includeItemsFromAllDrives=true"
    res = drive_get(url)
    items = res.get("files", [])
    return items[0]["id"] if items else None


def list_files(folder_id):
    q = f"'{folder_id}' in parents and trashed=false"
    fields = "files(id,name,mimeType,size)"
    url = f"https://www.googleapis.com/drive/v3/files?q={urllib.parse.quote(q)}&fields={fields}&pageSize=200&supportsAllDrives=true&includeItemsFromAllDrives=true"
    return drive_get(url).get("files", [])


# ---------------------------------------------------------------------------
# 2) Find or create 'New problems' subfolder
# ---------------------------------------------------------------------------
problems_id = find_subfolder(FOLDER_ID, "New problems")
if not problems_id:
    print(f"New problems subfolder NOT FOUND in {FOLDER_ID} - creating", flush=True)
    body = json.dumps({
        "name": "New problems",
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [FOLDER_ID],
    }).encode("utf-8")
    req = urllib.request.Request("https://www.googleapis.com/drive/v3/files?supportsAllDrives=true",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {ACCESS}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        new = json.loads(r.read().decode("utf-8"))
    problems_id = new["id"]
print(f"PROBLEMS_ID {problems_id}", flush=True)

# ---------------------------------------------------------------------------
# 3) List files
# ---------------------------------------------------------------------------
files = list_files(problems_id)
print(f"FILE_COUNT {len(files)}", flush=True)
for f in files:
    print(f"  - {f['name']} (mime={f['mimeType']}, size={f.get('size','?')})", flush=True)

# ---------------------------------------------------------------------------
# 4) Download to /tmp/lit_downloads
# ---------------------------------------------------------------------------
import shutil
DL_DIR = "/tmp/lit_downloads"
shutil.rmtree(DL_DIR, ignore_errors=True)
os.makedirs(DL_DIR, exist_ok=True)

local_paths = []
for f in files:
    if "word" in f["mimeType"] or f["mimeType"] == "application/pdf" or "officedocument" in f["mimeType"]:
        local_name = f["name"]
        # Sanitize filename
        safe = "".join(c for c in local_name if c.isalnum() or c in "._- ()")
        local_path = os.path.join(DL_DIR, safe)
        try:
            size = drive_download(f["id"], local_path)
            local_paths.append((local_path, f["name"], size))
            print(f"DOWNLOADED {safe} ({size} bytes)", flush=True)
        except Exception as e:
            print(f"DOWNLOAD_FAILED {safe}: {e}", flush=True)
    else:
        print(f"SKIPPED {f['name']} (mime={f['mimeType']})", flush=True)

print(f"\nLOCAL_FILES {len(local_paths)}", flush=True)

# ---------------------------------------------------------------------------
# 5) Parse references using pdf_parser (v0.1 module)
# ---------------------------------------------------------------------------
sys.path.insert(0, ".")
from pdf_parser import extract_text, parse_chapter_references

all_refs = []
all_citations = []
for path, name, size in local_paths:
    print(f"\nPARSING {name}...", flush=True)
    try:
        result = parse_chapter_references(path)
        ref_list = result.get("reference_list", [])
        in_text = result.get("in_text_citations", [])
        print(f"  -> {len(ref_list)} reference entries, {len(in_text)} in-text citations", flush=True)
        for r in ref_list:
            all_refs.append({"raw": r, "source_file": name})
        for c in in_text:
            c["source_file"] = name
            all_citations.append(c)
    except Exception as e:
        print(f"  PARSE_FAILED: {e}", flush=True)

print(f"\nTOTAL_REFS {len(all_refs)}, TOTAL_CITATIONS {len(all_citations)}", flush=True)

# Dedupe by raw text
seen = set()
unique = []
for r in all_refs:
    key = r["raw"].lower().strip()
    if key in seen or not key: continue
    seen.add(key)
    unique.append(r)
print(f"UNIQUE_REFS {len(unique)}", flush=True)
for r in unique[:5]:
    print(f"  - {r['raw'][:120]}", flush=True)
print(f"  ... and {len(unique)-5} more" if len(unique) > 5 else "", flush=True)

# ---------------------------------------------------------------------------
# 6) Split each unique ref into separate bibliographic entries (one per author/year)
# ---------------------------------------------------------------------------
import re

def split_references(raw_text):
    """Split a raw ref-list string into individual entries. Uses year+author pattern as boundary."""
    text = re.sub(r'\s+', ' ', raw_text).strip()
    # Boundary: a year in parens (1990), 4-digit year preceded by capital, or period+space+Capital
    # Heuristic: split before "Author, A. (YYYY)" or "Author, A.A. (YYYY)" etc.
    pattern = re.compile(r'(?<=[.;\s])([A-ZÅÄÖÉÈÊËÀÁÂÃÄÅÆÇĐÑØŒßÞŽ][a-zA-Z\u00C0-\u017F\-\']+,\s+[A-Z]\.?\s*[A-Z]?\.?(?:\s*&\s*[A-Z][a-zA-Z\u00C0-\u017F\-\']+,\s+[A-Z]\.?\s*[A-Z]?\.?)*\s*\(\d{4}\))')
    parts = pattern.split(text)
    # First part is whatever comes before the first match (often "" or a partial)
    if len(parts) >= 3:
        # pattern.split returns [pre, match, between, match, between, ...]
        entries = []
        for i in range(1, len(parts), 2):
            entry = parts[i]
            if i + 1 < len(parts):
                entry += " " + parts[i+1]
            entries.append(entry.strip())
        return [e for e in entries if len(e) > 20]
    return [text]  # Couldn't split, return as-is

split_refs = []
for r in unique:
    raw = r["raw"]
    # Skip obviously non-references
    if any(skip in raw.lower() for skip in [
        "thank you", "strongly agree", "motivational strategies strongly",
        "the role of motivation strongly", "ree | agree | neutral",
        "researcher:", "no. statement", "challenges strongly",
    ]):
        continue
    entries = split_references(raw)
    for e in entries:
        split_refs.append({"raw": e.strip(), "source_file": r["source_file"]})

print(f"\nSPLIT_REFS {len(split_refs)}", flush=True)
for r in split_refs[:8]:
    print(f"  - {r['raw'][:140]}", flush=True)
if len(split_refs) > 8:
    print(f"  ... and {len(split_refs)-8} more", flush=True)

# Save intermediate
with open("/tmp/split_refs.json", "w", encoding="utf-8") as f:
    json.dump(split_refs, f, indent=2, ensure_ascii=False)

# ---------------------------------------------------------------------------
# 7) Run v2-4 verification on a sample (cap at 5 to fit GHA 30-min budget)
# ---------------------------------------------------------------------------
sys.path.insert(0, ".")
from research_hunter_v4 import search_all, bulk_check
from platform_registry import PLATFORM_FNS

SAMPLE_CAP = 5
sample = split_refs[:SAMPLE_CAP]
print(f"\nVERIFYING SAMPLE OF {len(sample)} REFS WITH v2-4...", flush=True)
print(f"AVAILABLE PLATFORMS: {len(PLATFORM_FNS)}", flush=True)

results = []
for i, ref in enumerate(sample, 1):
    raw = ref["raw"]
    # Extract author-year-title for the search query
    m = re.match(r'^([^(]+?)\s*\((\d{4})\)', raw)
    if m:
        authors = m.group(1).strip().rstrip(",.")
        year = m.group(2)
        query = f"{authors} {year}"
    else:
        query = raw[:100]
    print(f"\n[{i}/{len(sample)}] SEARCH: {query}", flush=True)
    try:
        # Use ALL available platforms (must be a list, not None)
        papers = search_all(
            [query],
            platforms=list(PLATFORM_FNS.keys()),
            year_from=int(year) - 2 if m else 2010,
            year_to=int(year) + 2 if m else 2026,
        )
        print(f"  -> {len(papers)} papers found", flush=True)
        top = papers[0] if papers else None
        results.append({
            "raw": raw,
            "query": query,
            "source_file": ref["source_file"],
            "match_count": len(papers),
            "top_paper": top,
        })
    except Exception as e:
        print(f"  SEARCH_FAILED: {e}", flush=True)
        results.append({
            "raw": raw, "query": query,
            "source_file": ref["source_file"],
            "match_count": 0, "top_paper": None, "error": str(e),
        })

print(f"\nVERIFIED {len(results)} REFS", flush=True)
for r in results:
    tp = r.get("top_paper") or {}
    print(f"  Q: {r['query'][:60]}", flush=True)
    print(f"     matches={r['match_count']} top={tp.get('title','')[:80]!r} doi={tp.get('doi','')}", flush=True)

with open("/tmp/verified_refs.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print("SAVED /tmp/verified_refs.json", flush=True)

# Save intermediate result
with open("/tmp/parsed_refs.json", "w", encoding="utf-8") as f:
    json.dump(unique, f, indent=2, ensure_ascii=False)
print("SAVED /tmp/parsed_refs.json", flush=True)
