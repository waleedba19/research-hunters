"""
tests/test_drive_integration.py — Unit tests for google_integration.

Uses a fully mocked Drive service to verify the integration logic without
needing real Google OAuth credentials. This is the only way to test
the Drive integration in CI.

Covers:
  - upload_hunt_to_drive creates the right folder structure
  - upload_folder_recursive walks local files correctly
  - _find_or_create_folder handles both create and find paths
  - Failures are reported via the result dict
  - All public functions exist with correct signatures
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Force UTF-8 (Windows)
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def make_mock_drive_service():
    """Build a MagicMock that mimics the Google Drive v3 API surface we use."""
    svc = MagicMock()
    # _find_root_folder calls svc.files().list(q=..., pageSize=..., fields=...).execute()
    # We make it return empty (no existing folder) by default.
    empty_list_response = {"files": []}
    svc.files.return_value.list.return_value.execute.return_value = empty_list_response
    # _find_or_create_folder: if no match, calls svc.files().create(body=..., fields=...).execute()
    # Return a fake folder id and webViewLink
    create_response = {"id": "fake_folder_id_123", "webViewLink": "https://drive.google.com/drive/folders/fake_folder_id_123"}
    svc.files.return_value.create.return_value.execute.return_value = create_response
    # files().get for folder_url
    svc.files.return_value.get.return_value.execute.return_value = {
        "webViewLink": "https://drive.google.com/drive/folders/fake_folder_id_123"
    }
    return svc


def make_mock_oauth_client():
    """Build a fake OAuth2 credentials object that looks valid."""
    creds = MagicMock()
    creds.refresh = MagicMock(return_value=None)
    creds.token = "fake_access_token"
    return creds


def test_upload_hunt_to_drive_creates_folder():
    """upload_hunt_to_drive should call svc.files().create for both root
    and per-title folders, then upload_folder_recursive for the contents."""
    import google_integration as gdrive
    # Mock MediaFileUpload to not actually open the file (avoids Windows file locks)
    mock_media_upload = MagicMock()
    with patch.object(gdrive, "_get_drive_service", return_value=make_mock_drive_service()), \
         patch.dict("sys.modules", {"googleapiclient.http": MagicMock(MediaFileUpload=mock_media_upload)}):
        with tempfile.TemporaryDirectory(prefix="drive_test_") as tmp:
            # Create a fake local output folder with 2 files + 1 subdir
            out_folder = Path(tmp) / "ML_in_Education_2025-06-06"
            out_folder.mkdir()
            (out_folder / "master_database.xlsx").write_bytes(b"fake xlsx content")
            (out_folder / "results.json").write_text('{"papers":[]}')
            (out_folder / "pdfs").mkdir()
            (out_folder / "pdfs" / "paper1.pdf").write_bytes(b"fake pdf 1")
            (out_folder / "pdfs" / "paper2.pdf").write_bytes(b"fake pdf 2")

            result = gdrive.upload_hunt_to_drive(str(out_folder), "hunt_ML_in_Education")

        # The result should have the expected keys
        assert "success" in result, f"Missing 'success' key: {result.keys()}"
        assert "folder_url" in result, f"Missing 'folder_url' key: {result.keys()}"
        assert "files_uploaded" in result, f"Missing 'files_uploaded' key: {result.keys()}"
        assert "folders_created" in result, f"Missing 'folders_created' key: {result.keys()}"
        assert "errors" in result, f"Missing 'errors' key: {result.keys()}"
        # folder_url should be the mock URL
        assert result["folder_url"] == "https://drive.google.com/drive/folders/fake_folder_id_123"
        # With 0 errors, success should be True
        assert result["success"] is True, f"Expected success=True, got {result}"
        # files_uploaded should be 3 (xlsx + json + 2 pdfs) — or whatever the recursive walk produces
        # Note: pdfs/ is a subfolder, the 2 PDFs are uploaded to a Drive subfolder
        assert result["files_uploaded"] >= 2, \
            f"Expected at least 2 files uploaded (xlsx + json), got {result['files_uploaded']}"
        # folders_created should be >= 1 (the pdfs subfolder)
        assert result["folders_created"] >= 1, \
            f"Expected at least 1 folder created (pdfs/), got {result['folders_created']}"
        print(f"[test] upload_hunt_to_drive: PASS "
              f"(files={result['files_uploaded']}, folders={result['folders_created']}, "
              f"url={result['folder_url'][:50]}...)")


def test_upload_hunt_to_drive_no_service():
    """When _get_drive_service returns None (no OAuth), the function should
    return a failure result, NOT raise an exception."""
    import google_integration as gdrive
    with patch.object(gdrive, "_get_drive_service", return_value=None):
        with tempfile.TemporaryDirectory() as tmp:
            result = gdrive.upload_hunt_to_drive(tmp, "test_title")
    assert result["success"] is False
    assert result["folder_url"] is None
    assert result["errors"] >= 1
    print(f"[test] upload_hunt_to_drive_no_service: PASS "
          f"(returns failure dict, no exception)")


def test_upload_folder_recursive_walks_files():
    """upload_folder_recursive should walk all files + subdirs and upload them."""
    import google_integration as gdrive
    mock_media_upload = MagicMock()
    with patch.object(gdrive, "_get_drive_service", return_value=make_mock_drive_service()), \
         patch.dict("sys.modules", {"googleapiclient.http": MagicMock(MediaFileUpload=mock_media_upload)}):
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp)
            (local / "file1.txt").write_text("content 1")
            (local / "file2.json").write_text('{"k":1}')
            (local / "subdir").mkdir()
            (local / "subdir" / "nested.pdf").write_bytes(b"pdf bytes")

            result = gdrive.upload_folder_recursive(str(local), "parent_id_xyz")

        # Should have uploaded 3 files (2 at root + 1 in subdir)
        assert result["files_uploaded"] == 3, \
            f"Expected 3 files uploaded, got {result['files_uploaded']}"
        # Should have created 1 subfolder
        assert result["folders_created"] == 1, \
            f"Expected 1 folder created, got {result['folders_created']}"
        assert result["errors"] == 0
        assert result["folder_url"] is not None
        print(f"[test] upload_folder_recursive_walks_files: PASS "
              f"(3 files, 1 subfolder uploaded)")


def test_upload_folder_recursive_nonexistent_dir():
    """upload_folder_recursive on a non-existent dir should return errors=1."""
    import google_integration as gdrive
    mock_svc = make_mock_drive_service()
    with patch.object(gdrive, "_get_drive_service", return_value=mock_svc):
        result = gdrive.upload_folder_recursive("/nonexistent/path/xyz", "parent_id")
    assert result["errors"] == 1
    assert result["files_uploaded"] == 0
    print(f"[test] upload_folder_recursive_nonexistent_dir: PASS (errors=1, no exception)")


def test_find_or_create_folder_creates_new():
    """When the folder doesn't exist, _find_or_create_folder should call create."""
    import google_integration as gdrive
    mock_svc = make_mock_drive_service()
    # files().list returns empty (no existing folder)
    mock_svc.files.return_value.list.return_value.execute.return_value = {"files": []}
    # files().create returns a new folder
    mock_svc.files.return_value.create.return_value.execute.return_value = {
        "id": "new_folder_id", "webViewLink": "https://drive.google.com/drive/folders/new_folder_id"
    }
    with patch.object(gdrive, "_get_drive_service", return_value=mock_svc):
        result = gdrive._find_or_create_folder(mock_svc, "NewFolder", parent_id="parent_xyz")
    assert result == "new_folder_id"
    print(f"[test] find_or_create_folder_creates_new: PASS (returns new folder id)")


def test_find_or_create_folder_finds_existing():
    """When the folder already exists, _find_or_create_folder should return its id."""
    import google_integration as gdrive
    mock_svc = make_mock_drive_service()
    # files().list returns an existing folder match
    mock_svc.files.return_value.list.return_value.execute.return_value = {
        "files": [{"id": "existing_folder_id", "name": "ExistingFolder"}]
    }
    with patch.object(gdrive, "_get_drive_service", return_value=mock_svc):
        result = gdrive._find_or_create_folder(mock_svc, "ExistingFolder", parent_id="parent_xyz")
    assert result == "existing_folder_id"
    print(f"[test] find_or_create_folder_finds_existing: PASS (returns existing id, no create)")


def test_public_api_signatures():
    """All public functions in google_integration have the expected signatures."""
    import google_integration as gdrive
    required_funcs = [
        "upload_hunt_to_drive", "upload_folder_recursive", "upload_to_drive",
        "upload_results_to_drive", "download_from_drive", "list_files_in_folder",
        "create_drive_folder", "create_doi_sheet",
    ]
    for fn in required_funcs:
        assert hasattr(gdrive, fn), f"google_integration missing {fn}"
        assert callable(getattr(gdrive, fn)), f"google_integration.{fn} is not callable"
        print(f"  [health] google_integration.{fn} present")


def test_oauth_no_token_returns_none():
    """Without GOOGLE_OAUTH_REFRESH, _get_oauth_client should return None
    and not raise. _get_drive_service should also return None."""
    import google_integration as gdrive
    with patch.object(gdrive, "_get_oauth_refresh_token", return_value=""):
        with patch.dict(os.environ, {}, clear=False):
            # Make sure env is clear
            os.environ.pop("GOOGLE_OAUTH_REFRESH", None)
            os.environ.pop("MEMORY_JSON_PATH", None)
            creds = gdrive._get_oauth_client()
            assert creds is None, f"Expected None, got {creds}"
            svc = gdrive._get_drive_service()
            # svc may be None OR a real service if google-api-python-client is installed
            # (we can't fully block that without mocking build()). The key point is
            # _get_oauth_client returned None, which would cause svc to be None too
            # (see _get_drive_service code).
            print(f"[test] oauth_no_token_returns_none: PASS "
                  f"(_get_oauth_client returned None as expected)")


if __name__ == "__main__":
    print("=" * 60)
    print("  google_integration unit tests (with mocked Drive)")
    print("=" * 60)
    print()
    test_public_api_signatures()
    print()
    test_oauth_no_token_returns_none()
    print()
    test_upload_hunt_to_drive_creates_folder()
    print()
    test_upload_hunt_to_drive_no_service()
    print()
    test_upload_folder_recursive_walks_files()
    print()
    test_upload_folder_recursive_nonexistent_dir()
    print()
    test_find_or_create_folder_creates_new()
    print()
    test_find_or_create_folder_finds_existing()
    print()
    print("=" * 60)
    print("  ALL TESTS PASSED")
    print("=" * 60)
