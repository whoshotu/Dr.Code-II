import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL not set")
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="session")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# Health + settings stability
class TestHealthAndSettings:
    def test_health_endpoint_stable(self, api_client, base_url):
        response = api_client.get(f"{base_url}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert isinstance(data["ollama_configured"], bool)
        assert isinstance(data["ollama_ready"], bool)

    def test_settings_get_and_update_roundtrip(self, api_client, base_url):
        current = api_client.get(f"{base_url}/api/settings")
        assert current.status_code == 200
        current_data = current.json()
        assert "severity" in current_data

        updated_payload = {
            "use_ollama": current_data.get("use_ollama", False),
            "ollama_base_url": current_data.get("ollama_base_url"),
            "ollama_model": current_data.get("ollama_model"),
            "severity": {"critical": 90, "high": 75, "medium": 50, "low": 10},
        }
        update = api_client.put(f"{base_url}/api/settings", json=updated_payload)
        assert update.status_code == 200
        update_data = update.json()
        assert update_data["severity"]["critical"] == 90
        assert update_data["severity"]["high"] == 75
        assert update_data["severity"]["medium"] == 50
        assert update_data["severity"]["low"] == 10

        verify = api_client.get(f"{base_url}/api/settings")
        assert verify.status_code == 200
        verify_data = verify.json()
        assert verify_data["severity"] == updated_payload["severity"]


# Analyze + reports workflow
class TestAnalyzeAndReports:
    def test_analyze_creates_report_and_fields(self, api_client, base_url):
        payload = {
            "filename": "TEST_sample.py",
            "language": "python",
            "code": 'def add(a,b):\n  return a+b\npassword = "123"',
        }
        response = api_client.post(f"{base_url}/api/analyze", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "TEST_sample.py"
        assert data["language"] == "python"
        assert isinstance(data["summary"], str) and len(data["summary"]) > 0
        assert isinstance(data["documentation"], str) and len(data["documentation"]) > 0
        assert data["mode"] in ["rule-based", "hybrid"]
        assert isinstance(data["issues"], list)
        assert isinstance(data["report_id"], str)

    def test_reports_list_and_detail_load(self, api_client, base_url):
        create = api_client.post(
            f"{base_url}/api/analyze",
            json={
                "filename": "TEST_list_detail.py",
                "language": "python",
                "code": "x=1000\nprint(x)",
            },
        )
        assert create.status_code == 200
        created = create.json()

        list_resp = api_client.get(f"{base_url}/api/reports")
        assert list_resp.status_code == 200
        reports = list_resp.json()
        assert isinstance(reports, list)
        matching = [r for r in reports if r["report_id"] == created["report_id"]]
        assert len(matching) == 1
        assert matching[0]["filename"] == "TEST_list_detail.py"

        detail_resp = api_client.get(f"{base_url}/api/reports/{created['report_id']}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["report_id"] == created["report_id"]
        assert isinstance(detail["issues"], list)
        assert "documentation" in detail


# Git/CI integration stubs
class TestIntegrationStubs:
    def test_submit_git_ci_and_list_events(self, api_client, base_url):
        suffix = str(uuid.uuid4())[:8]
        git_payload = {
            "repository": f"repo/test-{suffix}",
            "event_type": "push",
            "branch": "main",
            "commit_sha": f"sha-{suffix}",
            "payload_preview": "TEST payload",
        }
        git_resp = api_client.post(
            f"{base_url}/api/integrations/git/webhook", json=git_payload
        )
        assert git_resp.status_code == 200
        git_data = git_resp.json()
        assert git_data["source"] == "git"
        assert git_data["event_type"] == "push"
        assert git_data["status"] == "received"

        ci_payload = {
            "pipeline": f"pipeline-{suffix}",
            "status": "passed",
            "branch": "main",
            "commit_sha": f"sha-{suffix}",
        }
        ci_resp = api_client.post(
            f"{base_url}/api/integrations/ci/event", json=ci_payload
        )
        assert ci_resp.status_code == 200
        ci_data = ci_resp.json()
        assert ci_data["source"] == "ci"
        assert ci_data["event_type"] == "pipeline-status"
        assert ci_data["status"] == "passed"

        events_resp = api_client.get(f"{base_url}/api/integrations/events")
        assert events_resp.status_code == 200
        events = events_resp.json()
        assert isinstance(events, list)
        found_git = [e for e in events if e["event_id"] == git_data["event_id"]]
        found_ci = [e for e in events if e["event_id"] == ci_data["event_id"]]
        assert len(found_git) == 1
        assert len(found_ci) == 1
