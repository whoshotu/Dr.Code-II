import os
import uuid

import pytest
import requests

# Repository fixes workflow regression: analyze -> approve selected/all -> validation guard -> session/download checks
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


def _make_repo_payload(repo_name: str, files: list[dict]):
    return {
        "repository_name": repo_name,
        "files": files,
    }


class TestRepositoryFixesWorkflow:
    def test_analyze_repository_creates_session_and_fixes(self, api_client, base_url):
        suffix = str(uuid.uuid4())[:8]
        payload = _make_repo_payload(
            f"TEST-repo-{suffix}",
            [
                {
                    "path": "src/app.py",
                    "content": "api_key = \"abc123\"\nprint('ok')\n",
                },
                {
                    "path": "src/client.js",
                    "content": 'const api_token = "xyz";\nconsole.log(api_token);\n',
                },
            ],
        )

        response = api_client.post(f"{base_url}/api/repository/analyze", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data["session_id"], str) and len(data["session_id"]) > 0
        assert data["repository_name"] == payload["repository_name"]
        assert data["status"] == "analyzed"
        assert data["file_count"] == 2
        assert isinstance(data["fixes"], list)
        assert len(data["fixes"]) >= 2

        first_fix = data["fixes"][0]
        assert "fix_id" in first_fix
        assert "file_path" in first_fix
        assert "replacement_line" in first_fix

    def test_apply_selected_fixes_updates_session_and_enables_download(
        self, api_client, base_url
    ):
        suffix = str(uuid.uuid4())[:8]
        payload = _make_repo_payload(
            f"TEST-selective-{suffix}",
            [
                {
                    "path": "service.py",
                    "content": 'secret = "token-value"\nprint(secret)\n',
                },
                {
                    "path": "utils.js",
                    "content": 'const db_password = "pw";\nconsole.log(db_password);\n',
                },
            ],
        )

        analyze = api_client.post(f"{base_url}/api/repository/analyze", json=payload)
        assert analyze.status_code == 200
        analyzed = analyze.json()
        assert len(analyzed["fixes"]) >= 2

        selected_fix_ids = [analyzed["fixes"][0]["fix_id"]]
        apply_resp = api_client.post(
            f"{base_url}/api/repository/apply-fixes",
            json={
                "session_id": analyzed["session_id"],
                "approve_all": False,
                "approved_fix_ids": selected_fix_ids,
            },
        )
        assert apply_resp.status_code == 200
        applied = apply_resp.json()

        assert applied["session_id"] == analyzed["session_id"]
        assert applied["status"] == "applied"
        assert applied["applied_fix_count"] == 1
        assert applied["updated_file_count"] == 1

        session_resp = api_client.get(
            f"{base_url}/api/repository/sessions/{analyzed['session_id']}"
        )
        assert session_resp.status_code == 200
        session_data = session_resp.json()
        assert session_data["status"] == "applied"
        assert session_data["applied_fix_count"] == 1

        approved = [fix for fix in session_data["fixes"] if fix.get("approved")]
        assert len(approved) == 1
        assert approved[0]["fix_id"] == selected_fix_ids[0]

        download_resp = api_client.get(
            f"{base_url}/api/repository/sessions/{analyzed['session_id']}/download"
        )
        assert download_resp.status_code == 200
        assert download_resp.headers.get("content-type", "").startswith(
            "application/zip"
        )

    def test_apply_all_approves_all_and_sets_applied_count(self, api_client, base_url):
        suffix = str(uuid.uuid4())[:8]
        payload = _make_repo_payload(
            f"TEST-approve-all-{suffix}",
            [
                {
                    "path": "main.py",
                    "content": 'password = "secret"\nvalue = eval("{\'a\':1}")\n',
                },
                {
                    "path": "frontend.js",
                    "content": 'const api_secret = "zzz";\n',
                },
            ],
        )

        analyze = api_client.post(f"{base_url}/api/repository/analyze", json=payload)
        assert analyze.status_code == 200
        analyzed = analyze.json()
        total_fixes = len(analyzed["fixes"])
        assert total_fixes >= 2

        apply_all_resp = api_client.post(
            f"{base_url}/api/repository/apply-fixes",
            json={
                "session_id": analyzed["session_id"],
                "approve_all": True,
                "approved_fix_ids": [],
            },
        )
        assert apply_all_resp.status_code == 200
        applied = apply_all_resp.json()
        assert applied["status"] == "applied"
        assert applied["applied_fix_count"] == total_fixes
        assert applied["updated_file_count"] >= 1

        session_resp = api_client.get(
            f"{base_url}/api/repository/sessions/{analyzed['session_id']}"
        )
        assert session_resp.status_code == 200
        session_data = session_resp.json()
        assert session_data["applied_fix_count"] == total_fixes
        assert all(fix.get("approved") for fix in session_data["fixes"])

    def test_future_import_order_remains_valid_after_apply(self, api_client, base_url):
        suffix = str(uuid.uuid4())[:8]
        payload = _make_repo_payload(
            f"TEST-future-import-{suffix}",
            [
                {
                    "path": "future_safe.py",
                    "content": (
                        "from __future__ import annotations\n"
                        'secret_token = "abc"\n'
                        "def make() -> dict[str, int]:\n"
                        "    return {'a': 1}\n"
                    ),
                }
            ],
        )

        analyze = api_client.post(f"{base_url}/api/repository/analyze", json=payload)
        assert analyze.status_code == 200
        analyzed = analyze.json()
        assert len(analyzed["fixes"]) >= 1

        apply_resp = api_client.post(
            f"{base_url}/api/repository/apply-fixes",
            json={
                "session_id": analyzed["session_id"],
                "approve_all": True,
                "approved_fix_ids": [],
            },
        )
        assert apply_resp.status_code == 200
        applied = apply_resp.json()
        assert applied["status"] == "applied"
        assert applied["applied_fix_count"] >= 1

        session_resp = api_client.get(
            f"{base_url}/api/repository/sessions/{analyzed['session_id']}"
        )
        assert session_resp.status_code == 200
        assert session_resp.json()["status"] == "applied"

    def test_validation_guard_blocks_apply_when_python_parse_fails(
        self, api_client, base_url
    ):
        suffix = str(uuid.uuid4())[:8]
        payload = _make_repo_payload(
            f"TEST-parse-guard-{suffix}",
            [
                {
                    "path": "broken_module.py",
                    "content": (
                        'secret_token = "abc"\n' "def broken(:\n" "    return 1\n"
                    ),
                }
            ],
        )

        analyze = api_client.post(f"{base_url}/api/repository/analyze", json=payload)
        assert analyze.status_code == 200
        analyzed = analyze.json()

        secret_fixes = [
            fix
            for fix in analyzed["fixes"]
            if "os.environ.get" in fix["replacement_line"]
        ]
        assert len(secret_fixes) == 1

        apply_resp = api_client.post(
            f"{base_url}/api/repository/apply-fixes",
            json={
                "session_id": analyzed["session_id"],
                "approve_all": False,
                "approved_fix_ids": [secret_fixes[0]["fix_id"]],
            },
        )
        assert apply_resp.status_code == 400
        detail = apply_resp.json().get("detail", "")
        assert "validation failed" in detail
        assert "syntax error" in detail.lower()

        session_resp = api_client.get(
            f"{base_url}/api/repository/sessions/{analyzed['session_id']}"
        )
        assert session_resp.status_code == 200
        session_data = session_resp.json()
        assert session_data["status"] == "analyzed"
        assert session_data["applied_fix_count"] == 0
