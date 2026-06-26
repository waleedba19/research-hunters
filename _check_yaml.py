import re

with open('.github/workflows/research.yml', encoding='utf-8') as f:
    text = f.read()

# Find all input blocks by splitting on 'type: choice'
blocks = []

# Split by input names at column 6
parts = re.split(r'\n      (\w+):\n', text)
issues = []
current_name = None

for i, part in enumerate(parts):
    if i == 0:
        continue
    if i % 2 == 1:
        current_name = part
        continue
    block = part
    if 'type: choice' not in block:
        continue
    m = re.search(r"default: '(.+?)'", block)
    default = m.group(1) if m else ''
    opts = re.findall(r"^- '(.+?)'$", block, re.MULTILINE)
    if not opts:
        opts = re.findall(r'^- (.+)$', block, re.MULTILINE)
    opts = [o.strip() for o in opts]
    if default and default not in opts:
        issues.append(f"MISMATCH: {current_name}")
        issues.append(f"  default: {repr(default[:80])}")
        if opts:
            for o in opts[:5]:
                issues.append(f"  option:  {repr(o[:80])}")

if issues:
    for l in issues:
        print(l)
else:
    print("ALL DEFAULTS MATCH OPTIONS")
