"""explore_new_folder.py — Recursively list everything in the new Drive folder."""
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

def list_in(folder_id, depth=0, path="Untitled_Chapter"):
    q = f"'{folder_id}' in parents and trashed=false"
    fields = "files(id,name,mimeType,size,modifiedTime,webViewLink)"
    url = f"https://www.googleapis.com/drive/v3/files?q={urllib.parse.quote(q)}&fields={fields}&pageSize=200&supportsAllDrives=true&includeItemsFromAllDrives=true"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.loads(r.read().decode("utf-8"))
    for f in res.get("files", []):
        indent = "  " * depth
        size = f.get("size", "0")
        try: size_kb = int(size) / 1024
        except: size_kb = 0
        if f["mimeType"] == "application/vnd.google-apps.folder":
            print(f"{indent}{f['name']}/  (id={f['id']})", flush=True)
            list_in(f["id"], depth + 1, path + "/" + f["name"])
        else:
            print(f"{indent}{f['name']}  ({f['mimeType']}, {size_kb:.1f} KB)  id={f['id']}", flush=True)

print(f"=== Exploring {FOLDER_ID} ===", flush=True)
list_in(FOLDER_ID)
