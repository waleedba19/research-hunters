"""oneoff_drive_list.py — Run in GHA to list files in any Drive folder."""
import os, json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import urllib.request, urllib.parse

FOLDER_ID = os.environ.get("FOLDER_ID", "1NjsBcaAb1qtRUl4d7KHNhvfm159ei2C4")

# Get access token
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
access = tok["access_token"]
print(f"TOKEN_OK len={len(access)}", flush=True)

# Folder metadata
req = urllib.request.Request(
    f"https://www.googleapis.com/drive/v3/files/{FOLDER_ID}?fields=id,name,mimeType,createdTime,webViewLink",
    headers={"Authorization": f"Bearer {access}"})
with urllib.request.urlopen(req, timeout=15) as r:
    meta = json.loads(r.read().decode("utf-8"))
print(f"\nFOLDER_META name={meta['name']} id={meta['id']}", flush=True)
print(f"FOLDER_LINK {meta.get('webViewLink','')}", flush=True)

# List files
q = f"'{FOLDER_ID}' in parents and trashed=false"
fields = "files(id,name,mimeType,size,modifiedTime,webViewLink)"
url = f"https://www.googleapis.com/drive/v3/files?q={urllib.parse.quote(q)}&fields={fields}&pageSize=100&supportsAllDrives=true&includeItemsFromAllDrives=true"
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access}"})
with urllib.request.urlopen(req, timeout=15) as r:
    res = json.loads(r.read().decode("utf-8"))
files = res.get("files", [])
print(f"\nFILE_COUNT {len(files)}", flush=True)
for f in files:
    size = f.get("size", "0")
    try: size_kb = int(size) / 1024
    except: size_kb = 0
    print(f"FILE name={f['name']!r} id={f['id']} mime={f['mimeType']} size={size_kb:.1f}KB", flush=True)
    print(f"     link={f.get('webViewLink', 'N/A')}", flush=True)
