import requests
from typing import Dict, Any, Optional


def call_provider_local(prompt: str, config: dict[str, Any]) -> Optional[str]:
    base_url = config.get("base_url", "http://localhost:8003")
    model = config.get("model", "local-model")
    # Try Ollama-like endpoint first to maximize compatibility
    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "response" in data:
                return data["response"]
    except Exception:
        pass
    # Fallback to generic local /generate endpoint
    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=30,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data.get("response")
    except Exception:
        return None
