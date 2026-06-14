"""minimal_verify.py — Strip everything down to ONE test.

Test: Does v2-4 find a known reference (Dörnyei 2009) on a single platform (CrossRef)?
Output: a single line "FOUND: <doi>" or "NOT_FOUND" — that's it.
"""
import os, json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# === STEP 1: Can we even import v2-4? ===
print("STEP 1: Import v2-4", flush=True)
sys.path.insert(0, ".")
try:
    from research_hunter_v4 import search_all, PLATFORM_FNS
    print(f"  OK: {len(PLATFORM_FNS)} platforms loaded", flush=True)
except Exception as e:
    print(f"  FAIL: {e}", flush=True)
    sys.exit(1)

# === STEP 2: List platforms ===
print("\nSTEP 2: Available platforms", flush=True)
for p in sorted(PLATFORM_FNS.keys()):
    print(f"  - {p}", flush=True)

# === STEP 3: Search ONE known reference on CrossRef ONLY ===
print("\nSTEP 3: Search 'Dörnyei Z 2009 L2 motivational self system' on CrossRef only", flush=True)
try:
    papers = search_all(
        ["Dörnyei Z 2009 L2 motivational self system"],
        platforms=["crossref"],
        year_from=2008, year_to=2010,
    )
    print(f"  Found {len(papers)} papers", flush=True)
    for p in papers[:3]:
        print(f"    - {p.get('title','')[:80]!r} doi={p.get('doi','')}", flush=True)
except Exception as e:
    import traceback
    print(f"  FAIL: {e}", flush=True)
    traceback.print_exc()
