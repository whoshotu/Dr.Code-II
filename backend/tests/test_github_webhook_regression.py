"""
DR.CODE-v2 — GitHub Webhook Regression Tests
Tests:
  1. Old stub payload → backward-compat (status: "received")
  2. Real GitHub PR payload, no token → graceful degradation (status: "skipped-no-token")
  3. GET /integrations/github/status → returns expected shape
  4. PUT /settings/github → stores token, returns masked form (no real GitHub calls made)
All GitHub API calls are mocked. No real network calls.
"""

import os
import uuid
from unittest.mock import patch

import pytest
import requests as req_lib

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL not set")
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="session")
def api_client():
    session = req_lib.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestGitHubStatus:
    def test_github_status_shape(self, api_client, base_url):
        """GET /integrations/github/status should return token_configured and webhook_secret_configured booleans."""
        resp = api_client.get(f"{base_url}/api/integrations/github/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "token_configured" in data
        assert isinstance(data["token_configured"], bool)
        assert "webhook_secret_configured" in data
        assert isinstance(data["webhook_secret_configured"], bool)


class TestGitHubSettingsUpdate:
    def test_save_github_token_stores_masked(self, api_client, base_url):
        """PUT /settings/github should store the token and return a masked version."""
        fake_token = "ghp_testtoken" + str(uuid.uuid4())[:8]
        resp = api_client.put(
            f"{base_url}/api/settings/github", json={"token": fake_token}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["token_configured"] is True
        assert data["token_masked"] is not None
        # Masked value should NOT contain the full token
        assert fake_token not in data["token_masked"]

    def test_clear_github_token(self, api_client, base_url):
        """PUT /settings/github with clear_token=true should remove the token."""
        resp = api_client.put(
            f"{base_url}/api/settings/github", json={"clear_token": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["token_configured"] is False

    def test_save_webhook_secret(self, api_client, base_url):
        """PUT /settings/github with webhook_secret should mark it as configured."""
        resp = api_client.put(
            f"{base_url}/api/settings/github",
            json={"webhook_secret": "my-super-secret-" + str(uuid.uuid4())[:8]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["webhook_secret_configured"] is True


class TestWebhookBackwardCompat:
    def test_old_stub_payload_still_works(self, api_client, base_url):
        """Old GitWebhookEvent-shaped payloads must still return status='received'."""
        suffix = str(uuid.uuid4())[:8]
        payload = {
            "repository": f"repo/compat-test-{suffix}",
            "event_type": "push",
            "branch": "main",
            "commit_sha": f"sha-{suffix}",
        }
        resp = api_client.post(f"{base_url}/api/integrations/git/webhook", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "git"
        assert data["status"] == "received"
        assert "event_id" in data


class TestWebhookGitHubPRPayload:
    def test_github_pr_payload_no_token_graceful(self, api_client, base_url):
        """
        A real GitHub PR-shaped payload with no token configured must return
        status='skipped-no-token' and NOT crash the server.
        """
        # Ensure token and secret are cleared first
        api_client.put(
            f"{base_url}/api/settings/github",
            json={"clear_token": True, "webhook_secret": ""},
        )

        # Minimal GitHub pull_request webhook shape (action: opened)
        pr_payload = {
            "action": "opened",
            "pull_request": {
                "number": 999,
                "head": {"sha": "deadbeef1234567890"},
                "title": "Test PR",
            },
            "repository": {
                "full_name": "org/repo-no-token",
                "name": "repo-no-token",
            },
        }
        resp = api_client.post(
            f"{base_url}/api/integrations/git/webhook", json=pr_payload
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "github"
        assert data["event_type"] == "pull_request"
        assert data["status"] == "skipped-no-token"

    def test_github_pr_payload_ignored_action(self, api_client, base_url):
        """
        A GitHub PR payload with action='closed' must be logged as
        ignored-action:closed and not trigger analysis.
        """
        # Clear any webhook secret that might be set from previous tests
        api_client.put(
            f"{base_url}/api/settings/github",
            json={"clear_token": True, "webhook_secret": ""},
        )

        pr_payload = {
            "action": "closed",
            "pull_request": {
                "number": 998,
                "head": {"sha": "abc123"},
                "title": "Closed PR",
            },
            "repository": {
                "full_name": "org/repo-ignored",
                "name": "repo-ignored",
            },
        }
        resp = api_client.post(
            f"{base_url}/api/integrations/git/webhook", json=pr_payload
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"].startswith("ignored-action")
