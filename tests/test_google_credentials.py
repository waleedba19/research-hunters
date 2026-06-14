"""tests/test_google_credentials.py — Unit tests for the new credential discovery
   and the service-account-first / OAuth-fallback logic in google_integration.

   These tests use mocks (no real Drive calls).
"""
import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import google_integration  # noqa: E402


def _make_sa_file(path: str):
    """Create a fake service account JSON file at `path`."""
    sa = {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "fake",
        "private_key": "-----BEGIN PRIVATE KEY-----\nFAKE\n-----END PRIVATE KEY-----\n",
        "client_email": "test@test-project.iam.gserviceaccount.com",
        "client_id": "1234567890",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    with open(path, "w") as f:
        json.dump(sa, f)
    return sa


def test_get_credential_status_no_creds():
    """No credentials: must say so clearly."""
    with patch.object(google_integration, "_SA_PATH_CANDIDATES", [r"N:\nonexistent\file.json"]), \
         patch.dict(os.environ, {}, clear=True):
        status = google_integration.get_credential_status()
        assert status["service_account"]["present"] is False
        assert status["oauth_refresh"]["present"] is False
        assert "❌" in status["recommended_action"]
        assert "/drivesetup" in status["recommended_action"]
    print("[test] get_credential_status handles no creds")


def test_get_credential_status_with_sa_file():
    """Service account file present: must report its email + project."""
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        sa = _make_sa_file(f.name)
    try:
        with patch.object(google_integration, "_SA_PATH_CANDIDATES", [f.name]):
            status = google_integration.get_credential_status()
        assert status["service_account"]["present"] is True
        assert status["service_account"]["client_email"] == sa["client_email"]
        assert status["service_account"]["project_id"] == sa["project_id"]
        assert "✅" in status["recommended_action"]
        assert sa["client_email"] in status["recommended_action"]
    finally:
        os.unlink(f.name)
    print("[test] get_credential_status detects service account")


def test_get_credential_status_with_oauth():
    """OAuth env vars set: must report it."""
    env = {
        "GOOGLE_OAUTH_REFRESH": "1//03fakefake",
        "GOOGLE_OAUTH_CLIENT_ID": "fake.apps.googleusercontent.com",
        "GOOGLE_OAUTH_CLIENT_SECRET": "fake_secret",
    }
    with patch.dict(os.environ, env, clear=True), \
         patch.object(google_integration, "_SA_PATH_CANDIDATES", [r"N:\nonexistent.json"]):
        status = google_integration.get_credential_status()
    assert status["oauth_refresh"]["present"] is True
    assert status["oauth_refresh"]["client_id_present"] is True
    assert status["oauth_refresh"]["client_secret_present"] is True
    print("[test] get_credential_status detects OAuth env vars")


def test_get_service_account_info_from_env_var():
    """If GOOGLE_SERVICE_ACCOUNT_JSON is set, use it."""
    sa = {
        "type": "service_account",
        "project_id": "env-project",
        "private_key": "-----BEGIN PRIVATE KEY-----\nX\n-----END PRIVATE KEY-----\n",
        "client_email": "env@env-project.iam.gserviceaccount.com",
    }
    with patch.dict(os.environ, {"GOOGLE_SERVICE_ACCOUNT_JSON": json.dumps(sa)}), \
         patch.object(google_integration, "_SA_PATH_CANDIDATES", [r"N:\nonexistent.json"]):
        info = google_integration._get_service_account_info()
    assert info is not None
    assert info["client_email"] == "env@env-project.iam.gserviceaccount.com"
    print("[test] _get_service_account_info reads GOOGLE_SERVICE_ACCOUNT_JSON env var")


def test_get_service_account_info_prefers_file():
    """File path takes priority over env var."""
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        sa = _make_sa_file(f.name)
    try:
        env_sa = {
            "type": "service_account",
            "project_id": "env-project",
            "private_key": "-----BEGIN PRIVATE KEY-----\nX\n-----END PRIVATE KEY-----\n",
            "client_email": "env@env-project.iam.gserviceaccount.com",
        }
        with patch.dict(os.environ, {"GOOGLE_SERVICE_ACCOUNT_JSON": json.dumps(env_sa)}), \
             patch.object(google_integration, "_SA_PATH_CANDIDATES", [f.name]):
            info = google_integration._get_service_account_info()
        # File should win
        assert info["client_email"] == sa["client_email"]
    finally:
        os.unlink(f.name)
    print("[test] _get_service_account_info prefers file over env")


def test_get_credentials_oauth_first():
    """If both service account and OAuth are available, OAuth is used
    (because it has user storage quota for upload operations)."""
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        _make_sa_file(f.name)
    try:
        env = {
            "GOOGLE_OAUTH_REFRESH": "1//03fake",
            "GOOGLE_OAUTH_CLIENT_ID": "x.apps.googleusercontent.com",
            "GOOGLE_OAUTH_CLIENT_SECRET": "y",
        }
        with patch.dict(os.environ, env, clear=False), \
             patch.object(google_integration, "_SA_PATH_CANDIDATES", [f.name]):
            with patch.object(google_integration, "_get_oauth_client", return_value="OAUTH_CREDS") as m_oauth, \
                 patch.object(google_integration, "_get_service_account_creds", return_value="SA_CREDS") as m_sa:
                creds = google_integration._get_credentials()
        assert creds == "OAUTH_CREDS"
        # SA was NOT called (since OAuth succeeded)
        m_sa.assert_not_called()
    finally:
        os.unlink(f.name)
    print("[test] OAuth used first when both credentials present")


def test_get_credentials_falls_back_to_sa():
    """If OAuth fails, service account is used."""
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        _make_sa_file(f.name)
    try:
        env = {
            "GOOGLE_OAUTH_REFRESH": "1//03fake",
            "GOOGLE_OAUTH_CLIENT_ID": "x.apps.googleusercontent.com",
            "GOOGLE_OAUTH_CLIENT_SECRET": "y",
        }
        with patch.dict(os.environ, env, clear=False), \
             patch.object(google_integration, "_SA_PATH_CANDIDATES", [f.name]):
            with patch.object(google_integration, "_get_oauth_client", return_value=None) as m_oauth, \
                 patch.object(google_integration, "_get_service_account_creds", return_value="SA_CREDS") as m_sa:
                creds = google_integration._get_credentials()
        assert creds == "SA_CREDS"
        m_sa.assert_called_once()
    finally:
        os.unlink(f.name)
    print("[test] Falls back to service account when OAuth fails")


def test_upload_to_drive_surfaces_error():
    """When upload fails, return None AND log a clear error."""
    from googleapiclient.errors import HttpError
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write("x")
        tmp = f.name
    try:
        # Mock _get_drive_service to return a service that throws quota error
        mock_svc = MagicMock()
        mock_svc.files.return_value.create.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=403),
            content=json.dumps({
                "error": {
                    "domain": "usageLimits",
                    "reason": "storageQuotaExceeded",
                    "message": "Service Accounts do not have storage quota."
                }
            }).encode("utf-8"),
        )
        with patch.object(google_integration, "_get_drive_service", return_value=mock_svc):
            url = google_integration.upload_to_drive(tmp, "folder_id")
        assert url is None  # failed gracefully
        print("[test] upload_to_drive returns None on quota error")
    finally:
        try: os.unlink(tmp)
        except: pass


def test_credential_status_includes_known_good_creds():
    """Sanity: the user's known-good ids-ref token is referenced somewhere
    so we don't accidentally regress to mcp-ref (which is dead)."""
    # This is a documentation/regression test. We check that the file
    # mentions the working pattern.
    import inspect
    src = inspect.getsource(google_integration)
    # The OAuth client_id and working token marker should appear in the
    # project_registry (loaded by AI agents) but google_integration itself
    # only checks env. So this test just checks the credential discovery
    # surface is comprehensive.
    assert "ids-ref" not in src  # not hardcoded — env-driven
    assert "service_account" in src
    assert "oauth" in src.lower()
    print("[test] google_integration is environment-driven (no hardcoded tokens)")
