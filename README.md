# Dr.Code-II

> AI-powered code quality analysis with automated fix suggestions and GitHub PR integration.

---

## Quickstart (2 min)

Get up and running locally in seconds.

```bash
git clone https://github.com/whoshotu/Dr.Code-II.git
cd Dr.Code-II
./setup.sh   # Interactive — picks your AI provider, ports, and starts services
```

The setup wizard will prompt you to choose an AI provider (Ollama, OpenAI, Gemini, or Anthropic), configure ports, and launch the containers automatically.

Access the dashboard at **[http://localhost:3001](http://localhost:3001)**.

---

## Overview

Dr.Code-II is a self-hosted AI code review platform that analyzes pull requests, detects security risks and anti-patterns, and posts structured inline comments back to GitHub — all powered by a local LLM. No code leaves your infrastructure.

## Features

- **Optional AI Providers**: Support for local Ollama or hosted providers (OpenAI, Gemini, Anthropic).
- **Auto Port Detection**: Automatically selects the next available port for backend and frontend services.
- **Setup Orchestration**: Persistent setup re-run menu for changing configurations without data loss.
- **Trash & Archive**: Non-destructive "soft-delete" for analysis reports and sessions.
- **GitHub PR Integration**: Automated review on PR open/synchronize with HMAC signature verification.
- **Encrypted Storage**: All API keys and tokens are encrypted with Fernet before persistence.

## How It Works

```text
GitHub PR ──webhook──▶ FastAPI Backend ──▶ Rule-based Detection + LLM Analysis ──▶ Inline PR Comments
                            │
                          SQLite
                            │
                      React Dashboard
```

1. **Webhook received** — GitHub notifies the backend of PR activity.
2. **Analysis runs** — Rule-based checks combined with LLM analysis detect issues.
3. **Comments posted** — Structured review comments appear on the exact lines with fix suggestions.

## Key Modules

| Module | Description |
| --- | --- |
| **Analyzer** | Hybrid rule + LLM detection for security risks, anti-patterns, and code smells. |
| **Orchestrator** | Intelligent setup script managing ports, providers, and environment state. |
| **Trash System** | Secure archival storage for trashing/restoring analysis data. |
| **GitHub Bot** | Real-time PR interaction and code injection layer. |

---

## Documentation

- **[Quickstart](#quickstart-2-min)**: 2-minute setup.
- **[Development Guide](DEVELOPMENT.md)**: Manual setup, troubleshooting, and advanced config.
- **[Demo Guide](DEMO_GUIDE.md)**: Walkthrough for hackathon scenarios.
- **[Known Issues](KNOWN_ISSUES.md)**: Common environmental pitfalls.

## Security

- All API keys and tokens are encrypted with **Fernet symmetric encryption**.
- Webhook payloads are verified via **HMAC SHA-256** when a secret is configured.
- Minimal data exposure: Analysis runs locally or within your trusted environment.

## License

MIT License — see [LICENSE](LICENSE) for details.

---

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](https://github.com/whoshotu/Dr.Code-II/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Backend: FastAPI](https://img.shields.io/badge/Backend-FastAPI-blue.svg)](https://fastapi.tiangolo.com)
[![Frontend: React](https://img.shields.io/badge/Frontend-React-blue.svg)](https://reactjs.org)
