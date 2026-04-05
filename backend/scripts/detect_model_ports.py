import json
import requests
from typing import List, Dict, Any, Optional


def probe_port(port: int) -> Optional[dict[str, Any]]:
    base = f"http://localhost:{port}"

    # Try Ollama-like /api/tags endpoint
    try:
        r = requests.get(f"{base}/api/tags", timeout=2)
        if r.status_code == 200:
            data = r.json() if 'Content-Type' in r.headers and r.headers['Content-Type'].startswith('application/json') else {}
            models = []
            if isinstance(data, dict):
                if isinstance(data.get("models"), list):
                    models = [m.get("name", "") for m in data["models"]]
                elif isinstance(data.get("model"), str):
                    models = [data["model"]]
            return {"port": port, "provider": "ollama", "models": models}
    except Exception:
        pass

    # Try LM Studio style endpoint
    try:
        r = requests.get(f"{base}/v1/models", timeout=2)
        if r.status_code == 200:
            data = r.json() if isinstance(r.json(), dict) else {}
            models = data.get("models", []) if isinstance(data.get("models", []), list) else []
            return {"port": port, "provider": "lmstudio", "models": models}
    except Exception:
        pass

    # Try a plain /generate ping endpoint for local servers
    try:
        resp = requests.post(f"{base}/generate", json={"model": "default", "prompt": "ping", "stream": False}, timeout=2)
        if resp.status_code == 200:
            return {"port": port, "provider": "local", "models": []}
    except Exception:
        pass

    return None


def detect_model_ports(ports: Optional[list[int]] = None) -> list[dict[str, Any]]:
    if ports is None:
        ports = [11434, 8003, 8004, 1234, 1235, 8080, 8000]
    results: list[dict[str, Any]] = []
    for p in ports:
        info = probe_port(p)
        if info:
            results.append(info)
    return results


if __name__ == "__main__":
    import sys
    ports = None
    if len(sys.argv) > 1:
        try:
            ports = [int(x) for x in sys.argv[1].split(",")]
        except Exception:
            ports = None
    data = detect_model_ports(ports)
    print(json.dumps({"providers": data}, indent=2))
