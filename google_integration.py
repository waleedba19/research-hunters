"""
google_integration.py — Google Drive + Sheets + Docs integration.

Authentication strategy (v6.6.1 — PROVEN, end-all-nightmare edition):
  1. PRIMARY:  Service Account (no user consent, no token refresh).
               Used by opportunity-hunter-v2 + captcha-solution-automation.
               Path: credentials/drive-service-account.json (copied from
               D:/Downloads/workspace-mcp-497516-c9c8d1419336.json).
               Service account: opportunity-hunter-bot@workspace-mcp-497516.iam.gserviceaccount.com
               Must be shared with the user as Editor on the target Drive folder.

  2. FALLBACK: OAuth refresh token (the OLD approach; kept for compatibility).
               If you see `unauthorized_client` errors, the refresh token was
               generated for a different OAuth client. Use the service account.

  3. FALLBACK: env var GOOGLE_SERVICE_ACCOUNT_JSON (full JSON contents).
               Useful for CI / GitHub Actions where you can't put a file.

Public API (unchanged):
  create_drive_folder, upload_to_drive, upload_folder_recursive,
  download_from_drive, upload_results_to_drive, upload_hunt_to_drive,
  list_files_in_folder, create_doi_sheet
"""
import os
import json
import io
import base64
from typing import Dict, List, Any, Optional
from logger import get_logger
from error_handler import retry

log = get_logger("google_integration")

DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"
ROOT_FOLDER_NAME = "Literature_Review_Verifier"

# Service account file paths (in order of preference)
_SA_PATH_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials", "drive-service-account.json"),
    os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", ""),
]

# Scope required for the literature-review-verifier
_ALL_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
]

# 25+ columns for the reference Sheet
SHEET_COLUMNS: List[str] = [
    "Chapter", "In-text mentions", "Citation APA", "Title", "Authors", "Year",
    "Journal", "Volume", "Issue", "Pages", "Publisher", "ISSN/ISBN", "DOI", "URL",
    "Source URL (no DOI)", "PDF in Drive", "Match Score", "Cross-source Validated",
    "Verified By", "Format", "Cover Image", "Citation Count", "Quartile",
    "Open Access", "Notes", "Added At", "Reference Type", "Abstract", "Keywords",
    "Affiliation", "Language",
]


# ─────────────────────────────────────────────────────────────────────────────
# Credential discovery — single source of truth
# ─────────────────────────────────────────────────────────────────────────────

def get_credential_status() -> Dict[str, Any]:
    """Return what credentials are present, missing, or invalid.
    Used by the /drivesetup command and the startup health check.
    """
    status = {
        "service_account": {
            "present": False,
            "path": None,
            "client_email": None,
            "project_id": None,
        },
        "oauth_refresh": {
            "present": False,
            "client_id_present": False,
            "client_secret_present": False,
        },
        "recommended_action": None,
    }
    # 1. Service account file
    for p in _SA_PATH_CANDIDATES:
        if p and os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    sa = json.load(f)
                if sa.get("type") == "service_account":
                    status["service_account"]["present"] = True
                    status["service_account"]["path"] = p
                    status["service_account"]["client_email"] = sa.get("client_email")
                    status["service_account"]["project_id"] = sa.get("project_id")
                    break
            except Exception as e:
                log.warning(f"Found service account file {p} but cannot parse: {e}")
    # 2. OAuth refresh token
    refresh = os.environ.get("GOOGLE_OAUTH_REFRESH", "")
    status["oauth_refresh"]["present"] = bool(refresh)
    status["oauth_refresh"]["client_id_present"] = bool(os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""))
    status["oauth_refresh"]["client_secret_present"] = bool(os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", ""))
    # Recommend
    if status["service_account"]["present"]:
        status["recommended_action"] = (
            f"✅ Service account ready: {status['service_account']['client_email']}\n"
            f"   Project: {status['service_account']['project_id']}\n"
            f"   Path: {status['service_account']['path']}"
        )
    elif status["oauth_refresh"]["present"]:
        status["recommended_action"] = (
            "⚠️ OAuth refresh token found but no service account. The refresh token "
            "may fail with `unauthorized_client` (mismatched client ID).\n"
            "→ Recommended: copy your service account JSON to "
            "credentials/drive-service-account.json (see /drivesetup for the step-by-step)."
        )
    else:
        status["recommended_action"] = (
            "❌ No Google credentials found.\n"
            "→ /drivesetup — guided setup wizard (takes 2 min)"
        )
    return status


def _get_service_account_info() -> Optional[Dict[str, Any]]:
    """Load service account JSON. Returns the dict or None."""
    # 1. From file
    for p in _SA_PATH_CANDIDATES:
        if p and os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    sa = json.load(f)
                if sa.get("type") == "service_account" and sa.get("private_key"):
                    log.debug(f"Using service account from {p}")
                    return sa
            except Exception as e:
                log.warning(f"Cannot load service account {p}: {e}")
    # 2. From env var (full JSON)
    env_sa = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if env_sa:
        try:
            sa = json.loads(env_sa)
            if sa.get("type") == "service_account" and sa.get("private_key"):
                log.debug("Using service account from GOOGLE_SERVICE_ACCOUNT_JSON env var")
                return sa
        except Exception as e:
            log.warning(f"Cannot parse GOOGLE_SERVICE_ACCOUNT_JSON: {e}")
    return None


def _get_oauth_refresh_token() -> str:
    """Get the refresh token from env or memory.json."""
    token = os.environ.get("GOOGLE_OAUTH_REFRESH", "")
    if token:
        return token
    # Fall back to memory.json
    try:
        mem_path = os.environ.get("MEMORY_JSON_PATH", r"D:\opencode\memory.json")
        with open(mem_path, "r", encoding="utf-8") as f:
            mem = json.load(f)
        # Try both the legacy key and the canonical one
        return (mem.get("secrets", {}).get("GOOGLE_OAUTH_REFRESH", "")
                or mem.get("GOOGLE_REFRESH_TOKEN", ""))
    except Exception as e:
        log.debug(f"No GOOGLE_OAUTH_REFRESH: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Credential builders
# ─────────────────────────────────────────────────────────────────────────────

def _get_service_account_creds():
    """Build google.oauth2.service_account.Credentials. Returns Credentials or None."""
    try:
        from google.oauth2.service_account import Credentials as SACredentials  # type: ignore
    except ImportError:
        log.error("google-auth library not installed (need google-auth>=2.0)")
        return None
    sa_info = _get_service_account_info()
    if not sa_info:
        return None
    try:
        return SACredentials.from_service_account_info(sa_info, scopes=_ALL_SCOPES)
    except Exception as e:
        log.error(f"Service account credentials build failed: {e}")
        return None


def _get_oauth_client() -> Optional[Any]:
    """Build a Google OAuth2 client (FALLBACK). Returns google.oauth2.credentials or None."""
    try:
        from google.oauth2.credentials import Credentials  # type: ignore
        from google.auth.transport.requests import Request  # type: ignore
    except ImportError:
        log.error("google-auth library not installed")
        return None
    refresh = _get_oauth_refresh_token()
    if not refresh:
        return None
    creds = Credentials(
        token=None,
        refresh_token=refresh,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""),
        client_secret=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", ""),
        scopes=_ALL_SCOPES,
    )
    try:
        creds.refresh(Request())
    except Exception as e:
        log.error(f"OAuth refresh failed: {e}")
        return None
    return creds


def _get_credentials():
    """Return credentials for the Drive/Sheets/Docs API.

    Strategy:
      1. If OAuth refresh token is present AND has matching client_id/secret,
         use it.  OAuth uses the USER's storage quota (15GB free), so uploads
         of large PDFs and DOCX files work reliably.
      2. If no OAuth, fall back to the service account.  Service account can
         read files and write to Shared Drives, but cannot CREATE new files
         in a regular Drive folder (no storage quota).  Uploads will fail
         with `storageQuotaExceeded`.
    """
    # Prefer OAuth for upload-heavy operations
    oauth = _get_oauth_client()
    if oauth:
        return oauth
    log.info("OAuth refresh token unavailable or failed; falling back to service account")
    return _get_service_account_creds()


def _get_drive_service():
    try:
        from googleapiclient.discovery import build  # type: ignore
    except ImportError:
        log.error("google-api-python-client not installed")
        return None
    creds = _get_credentials()
    if not creds:
        return None
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _get_sheets_service():
    try:
        from googleapiclient.discovery import build  # type: ignore
    except ImportError:
        return None
    creds = _get_credentials()
    if not creds:
        return None
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


@retry(max_attempts=2, base_delay=2.0)
def create_drive_folder(chapter_name: str) -> Optional[str]:
    """Create the per-chapter folder structure in Drive. Returns the chapter folder ID."""
    svc = _get_drive_service()
    if not svc:
        return None
    chapter_folder_id = _find_or_create_folder(svc, chapter_name, parent_id=None)
    if not chapter_folder_id:
        return None
    # Subfolders
    for sub in ("References", "NOT_FOUND", "Reports"):
        _find_or_create_folder(svc, sub, parent_id=chapter_folder_id)
    refs_id = _find_or_create_folder(svc, "References", parent_id=chapter_folder_id)
    if refs_id:
        for kind in ("Articles", "Books", "Chapters", "Theses", "Conference"):
            _find_or_create_folder(svc, kind, parent_id=refs_id)
    log.info(f"Created Drive folder structure for chapter: {chapter_name}")
    return chapter_folder_id


def _find_or_create_folder(svc, name: str, parent_id: Optional[str]) -> Optional[str]:
    """Find a folder by name under parent, or create it."""
    try:
        safe_name = name.replace("'", "\\'")
        if parent_id:
            q = f"name='{safe_name}' and '{parent_id}' in parents and mimeType='{DRIVE_FOLDER_MIME}' and trashed=false"
        else:
            q = f"name='{safe_name}' and mimeType='{DRIVE_FOLDER_MIME}' and trashed=false"
        results = svc.files().list(q=q, fields="files(id, name)").execute()
        items = results.get("files", [])
        if items:
            return items[0]["id"]
        metadata = {"name": name, "mimeType": DRIVE_FOLDER_MIME}
        if parent_id:
            metadata["parents"] = [parent_id]
        folder = svc.files().create(body=metadata, fields="id").execute()
        return folder.get("id")
    except Exception as e:
        log.error(f"_find_or_create_folder({name}) failed: {e}")
        return None


@retry(max_attempts=2, base_delay=2.0)
def upload_to_drive(local_path: str, drive_folder_id: str, mime_type: str = "application/pdf") -> Optional[str]:
    """Upload a local file to a Drive folder. Returns the file ID."""
    svc = _get_drive_service()
    if not svc:
        return None
    try:
        from googleapiclient.http import MediaFileUpload  # type: ignore
        file_name = os.path.basename(local_path)
        file_metadata = {"name": file_name, "parents": [drive_folder_id]}
        media = MediaFileUpload(local_path, mimetype=mime_type, resumable=True)
        uploaded = svc.files().create(
            body=file_metadata, media_body=media, fields="id, webViewLink"
        ).execute()
        log.info(f"Uploaded {file_name} -> Drive id={uploaded.get('id')}")
        return uploaded.get("webViewLink") or uploaded.get("id")
    except Exception as e:
        log.error(f"upload_to_drive failed for {local_path}: {e}")
        return None


# MIME types for common research output files
_MIME_BY_EXT = {
    ".pdf":  "application/pdf",
    ".md":   "text/markdown",
    ".txt":  "text/plain",
    ".json": "application/json",
    ".csv":  "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".html": "text/html",
}


def _detect_mime(local_path: str) -> str:
    ext = os.path.splitext(local_path)[1].lower()
    return _MIME_BY_EXT.get(ext, "application/octet-stream")


@retry(max_attempts=2, base_delay=2.0)
def upload_folder_recursive(local_folder: str, drive_parent_id: str, prefix: str = "") -> Dict[str, int]:
    """Recursively upload a local folder to a Drive folder, preserving structure.

    Creates subfolders in Drive for each subdirectory. Uploads all files at each
    level. The Drive folder ends up mirroring the local folder structure.

    Parameters:
        local_folder: path to local folder to upload
        drive_parent_id: Drive folder ID to upload into (subfolders created here)
        prefix: optional prefix prepended to all uploaded file names (for uniqueness)

    Returns:
        dict with keys: "files_uploaded", "folders_created", "errors", "folder_url"
    """
    svc = _get_drive_service()
    if not svc:
        return {"files_uploaded": 0, "folders_created": 0, "errors": 1, "folder_url": None}

    if not os.path.isdir(local_folder):
        log.error(f"upload_folder_recursive: not a directory: {local_folder}")
        return {"files_uploaded": 0, "folders_created": 0, "errors": 1, "folder_url": None}

    files_uploaded = 0
    folders_created = 0
    errors = 0
    folder_url = None

    # Try to get the webViewLink of the parent once (for return value)
    try:
        meta = svc.files().get(fileId=drive_parent_id, fields="webViewLink").execute()
        folder_url = meta.get("webViewLink")
    except Exception:
        pass

    try:
        for entry in sorted(os.listdir(local_folder)):
            full_path = os.path.join(local_folder, entry)
            if os.path.isdir(full_path):
                # Recurse: create subfolder in Drive, then upload contents
                sub_id = _find_or_create_folder(svc, entry, parent_id=drive_parent_id)
                if sub_id:
                    folders_created += 1
                    sub_result = upload_folder_recursive(full_path, sub_id, prefix=prefix)
                    files_uploaded += sub_result["files_uploaded"]
                    folders_created += sub_result["folders_created"]
                    errors += sub_result["errors"]
            else:
                # Upload file
                mime = _detect_mime(full_path)
                name = (prefix + entry) if prefix else entry
                try:
                    from googleapiclient.http import MediaFileUpload  # type: ignore
                    file_metadata = {"name": name, "parents": [drive_parent_id]}
                    media = MediaFileUpload(full_path, mimetype=mime, resumable=True)
                    uploaded = svc.files().create(
                        body=file_metadata, media_body=media, fields="id,webViewLink"
                    ).execute()
                    files_uploaded += 1
                    log.info(f"Uploaded {name} -> Drive id={uploaded.get('id')}")
                except Exception as e:
                    log.error(f"upload_folder_recursive: failed to upload {full_path}: {e}")
                    errors += 1
    except Exception as e:
        log.error(f"upload_folder_recursive: failed to walk {local_folder}: {e}")
        errors += 1

    return {
        "files_uploaded": files_uploaded,
        "folders_created": folders_created,
        "errors": errors,
        "folder_url": folder_url,
    }


@retry(max_attempts=2, base_delay=2.0)
def download_from_drive(file_id: str, local_path: str) -> Optional[str]:
    """Download a Drive file to a local path. Returns the local path or None."""
    svc = _get_drive_service()
    if not svc:
        return None
    try:
        from googleapiclient.http import MediaIoBaseDownload  # type: ignore
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        request = svc.files().get_media(fileId=file_id)
        with io.FileIO(local_path, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request, chunksize=1024 * 1024)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        log.info(f"Downloaded Drive id={file_id} -> {local_path}")
        return local_path
    except Exception as e:
        log.error(f"download_from_drive failed for file_id={file_id}: {e}")
        return None


@retry(max_attempts=2, base_delay=2.0)
def upload_results_to_drive(local_path: str, folder_name: str) -> Optional[str]:
    """Upload a file to a named Drive folder (creates if missing). Returns webViewLink."""
    folder_id = create_drive_folder(folder_name)
    if not folder_id:
        return None
    return upload_to_drive(local_path, folder_id)


def _find_root_folder(svc, name: str = "Literature_Review_Verifier") -> Optional[str]:
    """Find the top-level 'Literature_Review_Verifier' folder, or create it."""
    fid = _find_or_create_folder(svc, name, parent_id=None)
    return fid


@retry(max_attempts=2, base_delay=5.0)
def upload_hunt_to_drive(local_output_folder: str, title: str) -> Dict[str, Any]:
    """Upload a hunt's full output folder to Drive, mirroring the local structure.

    Creates the Drive structure:
        Drive: Literature_Review_Verifier/
            └── <title>/                       <- per-title main folder
                ├── 01_PDFs/                   <- subfolders mirror local
                ├── 02_Quartile_Reports/
                ├── ...
                ├── research_report.md
                ├── results.json
                ├── master_database.xlsx
                └── (any other files at root of local_output_folder)

    Parameters:
        local_output_folder: path to the local pdf_files/<title>/ folder
        title: the research topic/title (used for Drive folder name)

    Returns:
        dict with: {"success": bool, "folder_url": str, "files_uploaded": int,
                    "folders_created": int, "errors": int}
    """
    svc = _get_drive_service()
    if not svc:
        return {"success": False, "folder_url": None, "files_uploaded": 0,
                "folders_created": 0, "errors": 1}

    if not os.path.isdir(local_output_folder):
        log.error(f"upload_hunt_to_drive: not a directory: {local_output_folder}")
        return {"success": False, "folder_url": None, "files_uploaded": 0,
                "folders_created": 0, "errors": 1}

    # 1. Get or create root folder
    root_id = _find_root_folder(svc)
    if not root_id:
        return {"success": False, "folder_url": None, "files_uploaded": 0,
                "folders_created": 0, "errors": 1}

    # 2. Get or create per-title folder under root
    title_folder_id = _find_or_create_folder(svc, title, parent_id=root_id)
    if not title_folder_id:
        return {"success": False, "folder_url": None, "files_uploaded": 0,
                "folders_created": 0, "errors": 1}

    # 3. Recursively upload the local folder into the per-title folder
    log.info(f"Uploading hunt '{title}' to Drive folder {title_folder_id}")
    result = upload_folder_recursive(local_output_folder, title_folder_id)

    return {
        "success": result["errors"] == 0,
        "folder_url": result["folder_url"],
        "files_uploaded": result["files_uploaded"],
        "folders_created": result["folders_created"],
        "errors": result["errors"],
    }


def list_files_in_folder(folder_id: str) -> List[Dict[str, str]]:
    """List files in a Drive folder. Returns [{id, name, mimeType}]."""
    svc = _get_drive_service()
    if not svc:
        return []
    try:
        q = f"'{folder_id}' in parents and trashed=false"
        results = svc.files().list(q=q, fields="files(id, name, mimeType)").execute()
        return results.get("files", [])
    except Exception as e:
        log.error(f"list_files_in_folder({folder_id}) failed: {e}")
        return []


@retry(max_attempts=2, base_delay=2.0)
def create_doi_sheet(chapter_name: str, papers: List[Dict[str, Any]]) -> Optional[str]:
    """Create a Google Sheet for the chapter. Returns the sheet URL or None."""
    svc = _get_sheets_service()
    if svc is None:
        return None
    try:
        body = {"properties": {"title": f"References — {chapter_name}"}}
        sheet = svc.spreadsheets().create(body=body, fields="spreadsheetId,spreadsheetUrl").execute()
        sheet_id = sheet.get("spreadsheetId")
        sheet_url = sheet.get("spreadsheetUrl")
        # Write header row
        values = [SHEET_COLUMNS]
        for p in papers:
            values.append([str(p.get(col, "")) for col in SHEET_COLUMNS])
        svc.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="A1",
            valueInputOption="RAW",
            body={"values": values},
        ).execute()
        log.info(f"Created sheet {sheet_id} with {len(papers)} rows")
        return sheet_url
    except Exception as e:
        log.error(f"create_doi_sheet failed: {e}")
        return None
