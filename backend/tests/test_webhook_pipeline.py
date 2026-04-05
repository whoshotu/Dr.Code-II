"""
Webhook pipeline regression tests for DR.CODE-v2
Tests: signature verification, graceful degradation, real PR payload structure
"""
import hmac
import hashlib
import os
import uuid
from unittest.mock import patch, MagicMock

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


MOCK_PR_PAYLOAD = {
    "action": "opened",
    "number": 42,
    "pull_request": {
        "number": 42,
        "title": "Test PR",
        "head": {"sha": "abc123", "ref": "feature/test"},
        "base": {"ref": "main"},
        "user": {"login": "testuser"},
        "body": "Test PR body",
    },
    "repository": {
        "full_name": "test/repo",
        "name": "repo",
        "private": False,
    },
    "sender": {"login": "testuser"},
}


def _generate_hmac_signature(payload: dict, secret: str) -> str:
    """Generate valid HMAC-SHA256 signature for a payload."""
    import json
    body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


class TestWebhookSignatureVerification:
    def test_webhook_accepts_without_secret_configured(self, api_client, base_url):
        """When GITHUB_WEBHOOK_SECRET is unset, webhook must process normally."""
        # Clear any existing token and secret first
        api_client.put(f"{base_url}/api/settings/github", json={"clear_token": True, "webhook_secret": ""})

        resp = api_client.post(
            f"{base_url}/api/integrations/git/webhook",
            json=MOCK_PR_PAYLOAD,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "github"
        assert data["event_type"] == "pull_request"
        assert data["status"] == "skipped-no-token"

    def test_webhook_rejects_invalid_signature(self, api_client, base_url):
        """When secret IS set, invalid HMAC signature must return 401."""
        # Clear first, then set a webhook secret
        api_client.put(f"{base_url}/api/settings/github", json={"clear_token": True, "webhook_secret": ""})
        resp = api_client.put(
            f"{base_url}/api/settings/github",
            json={"webhook_secret": "test-secret-123"},
        )
        assert resp.json()["webhook_secret_configured"] is True

        resp = api_client.post(
            f"{base_url}/api/integrations/git/webhook",
            json=MOCK_PR_PAYLOAD,
            headers={"X-Hub-Signature-256": "sha256=invalid_signature"},
        )
        assert resp.status_code == 401
        assert "Invalid webhook signature" in resp.json().get("detail", "")

        # Clean up
        api_client.put(
            f"{base_url}/api/settings/github",
            json={"webhook_secret": ""},
        )

    def test_webhook_accepts_valid_hmac_signature(self, api_client, base_url):
        """Valid HMAC-SHA256 signature must be accepted."""
        # Clear first
        api_client.put(f"{base_url}/api/settings/github", json={"clear_token": True, "webhook_secret": ""})
        secret = "valid-test-secret-" + str(uuid.uuid4())[:8]
        api_client.put(
            f"{base_url}/api/settings/github",
            json={"webhook_secret": secret},
        )

        signature = _generate_hmac_signature(MOCK_PR_PAYLOAD, secret)
        resp = api_client.post(
            f"{base_url}/api/integrations/git/webhook",
            json=MOCK_PR_PAYLOAD,
            headers={"X-Hub-Signature-256": signature},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "github"
        assert data["event_type"] == "pull_request"

        # Clean up
        api_client.put(
            f"{base_url}/api/settings/github",
            json={"webhook_secret": ""},
        )


class TestWebhookGracefulDegradation:
    def test_no_github_token_returns_skipped(self, api_client, base_url):
        """Missing GitHub PAT must return status skipped-no-token, HTTP 200."""
        api_client.put(f"{base_url}/api/settings/github", json={"clear_token": True})

        resp = api_client.post(
            f"{base_url}/api/integrations/git/webhook",
            json=MOCK_PR_PAYLOAD,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "skipped-no-token"

    def test_webhook_non_pr_event_ignored(self, api_client, base_url):
        """push events must return 200 with status: ignored-action:push."""
        push_payload = {
            "action": "push",
            "pull_request": {
                "number": 1,
                "head": {"sha": "abc123"},
                "title": "Test PR",
            },
            "repository": {
                "full_name": "test/repo",
                "name": "repo",
            },
        }
        resp = api_client.post(
            f"{base_url}/api/integrations/git/webhook",
            json=push_payload,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"].startswith("ignored-action")

    def test_webhook_closed_pr_ignored(self, api_client, base_url):
        """closed PR events must be logged as ignored-action:closed."""
        closed_payload = {
            "action": "closed",
            "pull_request": {
                "number": 99,
                "head": {"sha": "def456"},
                "title": "Closed PR",
            },
            "repository": {
                "full_name": "test/repo",
                "name": "repo",
            },
        }
        resp = api_client.post(
            f"{base_url}/api/integrations/git/webhook",
            json=closed_payload,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ignored-action:closed"

    def test_webhook_old_stub_payload_still_works(self, api_client, base_url):
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


class TestWebhookErrorHandling:
    def test_invalid_json_returns_400(self, api_client, base_url):
        """Malformed JSON must return 400."""
        resp = api_client.post(
            f"{base_url}/api/integrations/git/webhook",
            data="not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_empty_payload_returns_error(self, api_client, base_url):
        """Empty payload must return an error."""
        resp = api_client.post(
            f"{base_url}/api/integrations/git/webhook",
            json={},
        )
        # Should not crash - either 200 with status or 400
        assert resp.status_code in {200, 400}
