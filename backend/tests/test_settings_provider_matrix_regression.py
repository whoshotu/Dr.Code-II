import os
import uuid

import pytest
import requests

# Settings/provider routing regression: legacy compatibility + new schema persistence + key secrecy + downstream workflow safety
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


class TestSettingsProviderMatrixRegression:
    def test_get_settings_returns_provider_matrix_routing_and_legacy_fields(
        self, api_client, base_url
    ):
        response = api_client.get(f"{base_url}/api/settings")
        assert response.status_code == 200
        data = response.json()

        assert "providers" in data
        assert "routing" in data
        assert "severity" in data

        for provider in ["ollama", "openai_compatible", "gemini", "anthropic"]:
            assert provider in data["providers"]
            assert "enabled" in data["providers"][provider]
            assert "base_url" in data["providers"][provider]
            assert "model" in data["providers"][provider]
            assert "key_configured" in data["providers"][provider]

        # Legacy compatibility fields must still be present
        assert "use_ollama" in data
        assert "ollama_base_url" in data
        assert "ollama_model" in data

        assert data["routing"]["primary_provider"] in [
            "ollama",
            "openai_compatible",
            "gemini",
            "anthropic",
        ]
        assert isinstance(data["routing"]["fallback_enabled"], bool)
        assert data["routing"]["fallback_provider"] in [
            "ollama",
            "openai_compatible",
            "gemini",
            "anthropic",
        ]

    def test_put_settings_legacy_payload_still_works(self, api_client, base_url):
        before = api_client.get(f"{base_url}/api/settings")
        assert before.status_code == 200
        previous = before.json()

        payload = {
            "use_ollama": True,
            "ollama_base_url": "http://localhost:11434",
            "ollama_model": "llama3.1:8b",
            "severity": previous.get(
                "severity", {"critical": 85, "high": 70, "medium": 45, "low": 0}
            ),
        }

        update = api_client.put(f"{base_url}/api/settings", json=payload)
        assert update.status_code == 200
        updated = update.json()

        assert updated["use_ollama"] is True
        assert updated["ollama_base_url"] == "http://localhost:11434"
        assert updated["ollama_model"] == "llama3.1:8b"

        verify = api_client.get(f"{base_url}/api/settings")
        assert verify.status_code == 200
        verify_data = verify.json()
        assert verify_data["use_ollama"] is True
        assert verify_data["ollama_base_url"] == "http://localhost:11434"
        assert verify_data["ollama_model"] == "llama3.1:8b"

    def test_put_settings_new_payload_persists_routing_and_encrypted_key_flags(
        self, api_client, base_url
    ):
        unique_suffix = str(uuid.uuid4())[:8]
        test_key = f"TEST_OPENAI_KEY_{unique_suffix}_ABCDEFGHIJK"

        payload = {
            "severity": {"critical": 85, "high": 70, "medium": 45, "low": 0},
            "providers": {
                "ollama": {
                    "enabled": True,
                    "base_url": "http://localhost:11434",
                    "model": "llama3.1:8b",
                },
                "openai_compatible": {
                    "enabled": True,
                    "base_url": "https://api.openai.com/v1",
                    "model": "gpt-5.2",
                    "api_key": test_key,
                },
                "gemini": {
                    "enabled": False,
                    "base_url": "https://generativelanguage.googleapis.com/v1beta",
                    "model": "gemini-2.5-pro",
                },
                "anthropic": {
                    "enabled": False,
                    "base_url": "https://api.anthropic.com/v1",
                    "model": "claude-sonnet-4-6",
                },
            },
            "routing": {
                "primary_provider": "openai_compatible",
                "fallback_enabled": True,
                "fallback_provider": "ollama",
            },
        }

        update = api_client.put(f"{base_url}/api/settings", json=payload)
        assert update.status_code == 200
        updated = update.json()

        assert updated["routing"]["primary_provider"] == "openai_compatible"
        assert updated["routing"]["fallback_enabled"] is True
        assert updated["routing"]["fallback_provider"] == "ollama"

        openai_conf = updated["providers"]["openai_compatible"]
        assert openai_conf["enabled"] is True
        assert openai_conf["key_configured"] is True
        assert isinstance(openai_conf.get("api_key_masked"), str)
        assert "..." in openai_conf["api_key_masked"]
        assert openai_conf["api_key_masked"] != test_key

        verify = api_client.get(f"{base_url}/api/settings")
        assert verify.status_code == 200
        verify_data = verify.json()
        assert verify_data["routing"]["primary_provider"] == "openai_compatible"
        assert verify_data["providers"]["openai_compatible"]["key_configured"] is True

    def test_settings_never_return_plaintext_api_keys(self, api_client, base_url):
        sentinel = f"TEST_PLAINTEXT_GUARD_{str(uuid.uuid4())[:8]}_XYZ123456"

        set_payload = {
            "severity": {"critical": 85, "high": 70, "medium": 45, "low": 0},
            "providers": {
                "ollama": {
                    "enabled": True,
                    "base_url": "http://localhost:11434",
                    "model": "llama3.1:8b",
                },
                "openai_compatible": {
                    "enabled": True,
                    "base_url": "https://api.openai.com/v1",
                    "model": "gpt-5.2",
                    "api_key": sentinel,
                },
                "gemini": {
                    "enabled": False,
                    "base_url": "https://generativelanguage.googleapis.com/v1beta",
                    "model": "gemini-2.5-pro",
                },
                "anthropic": {
                    "enabled": False,
                    "base_url": "https://api.anthropic.com/v1",
                    "model": "claude-sonnet-4-6",
                },
            },
            "routing": {
                "primary_provider": "ollama",
                "fallback_enabled": True,
                "fallback_provider": "openai_compatible",
            },
        }

        put_resp = api_client.put(f"{base_url}/api/settings", json=set_payload)
        assert put_resp.status_code == 200

        get_resp = api_client.get(f"{base_url}/api/settings")
        assert get_resp.status_code == 200
        body_text = get_resp.text
        body_data = get_resp.json()

        assert sentinel not in body_text
        assert "api_key" not in body_data["providers"]["openai_compatible"]
        assert "api_key_encrypted" not in body_data["providers"]["openai_compatible"]
        assert body_data["providers"]["openai_compatible"]["key_configured"] is True


class TestDownstreamRegressionAfterSettingsChanges:
    def test_analyze_still_works_with_new_settings_schema(self, api_client, base_url):
        payload = {
            "filename": "TEST_settings_regression.py",
            "language": "python",
            "code": "def f(a,b):\n    return a+b\nsecret='abc'",
        }
        response = api_client.post(f"{base_url}/api/analyze", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "TEST_settings_regression.py"
        assert isinstance(data["report_id"], str)
        assert data["mode"] in ["rule-based", "hybrid"]
        assert isinstance(data["issues"], list)

    def test_repository_fix_endpoints_still_functional(self, api_client, base_url):
        suffix = str(uuid.uuid4())[:8]
        analyze_payload = {
            "repository_name": f"TEST-settings-repo-{suffix}",
            "files": [
                {"path": "src/main.py", "content": "api_key = 'abc'\nprint('ok')\n"},
                {
                    "path": "src/helper.js",
                    "content": "const api_token = 'xyz';\nconsole.log(api_token);\n",
                },
            ],
        }

        analyze_resp = api_client.post(
            f"{base_url}/api/repository/analyze", json=analyze_payload
        )
        assert analyze_resp.status_code == 200
        analyzed = analyze_resp.json()
        assert analyzed["status"] == "analyzed"
        assert isinstance(analyzed["session_id"], str)
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
        session_data = session_resp.json()
        assert session_data["status"] == "applied"
