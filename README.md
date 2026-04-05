# DR.CODE-v2

> AI-powered code quality analysis with automated fix suggestions and GitHub PR integration.

[![Test](https://github.com/whoshotu/DR.Code-v2/actions/workflows/test.yml/badge.svg)](https://github.com/whoshotu/DR.Code-v2/actions/workflows/test.yml)
[![Build](https://github.com/whoshotu/DR.Code-v2/actions/workflows/build.yml/badge.svg)](https://github.com/whoshotu/DR.Code-v2/actions/workflows/build.yml)

---

## Overview

DR.CODE-v2 is a self-hosted AI code review platform that analyzes pull requests, detects security risks and anti-patterns, and posts structured inline comments back to GitHub — all powered by a local LLM. No code leaves your infrastructure.

## The Problem

Code review is slow, inconsistent, and security issues slip through. Existing tools either require sending code to external SaaS platforms or lack the contextual understanding that a local LLM provides. DR.CODE-v2 solves this by running entirely on your own machine or server.

## What It Does

- **Analyzes code** in real-time for security risks, anti-patterns, and code quality issues
- **Generates fix proposals** with severity scoring (critical / high / medium / low)
- **Reviews GitHub PRs automatically** via webhook — posts inline comments on exact lines
- **Scans entire repositories** for bulk analysis and selective fix application
- **Encrypts all secrets** before storage — tokens are never returned in plaintext

## How It Works

```
GitHub PR ──webhook──▶ FastAPI Backend ──▶ Rule-based Detection + Local LLM ──▶ Inline PR Comments
                            │
                      SQLite / MongoDB
                            │
                      React Dashboard
```

1. **Webhook received** — GitHub notifies DR.CODE when a PR is opened or updated
2. **Files fetched** — Changed files are retrieved via the GitHub API
3. **Analysis runs** — Rule-based detection catches known patterns; a local LLM adds contextual analysis
4. **Comments posted** — Structured review comments appear on the exact lines with fix suggestions
5. **Dashboard updates** — All analysis results are visible in the web UI

## Key Features

| Feature | Description |
|---------|-------------|
| **Code Analysis** | Rule-based + LLM hybrid detection for security risks, anti-patterns, and "slop" |
| **Severity Scoring** | Customizable critical / high / medium / low thresholds with confidence scores |
| **Multi-Provider AI** | Ollama (local), OpenAI-compatible, Gemini, Anthropic — switch in Settings |
| **GitHub PR Integration** | Automated review on PR open/synchronize with HMAC signature verification |
| **Repository Scanning** | Multi-file analysis with selective or bulk fix application |
| **Encrypted Storage** | All API keys and tokens encrypted with Fernet before persistence |
| **Graceful Degradation** | Works without a GitHub token, without Ollama, or without MongoDB |

---

## Quick Start

### One-Command Setup (Recommended)

```bash
git clone https://github.com/whoshotu/DR.Code-v2.git
cd DR.Code-v2
./setup.sh
```

The setup script auto-detects Docker, MongoDB, and Ollama, then starts everything. Access the dashboard at **http://localhost:3001**.

### Using the Makefile

```bash
make install      # Install all dependencies
make docker-up    # Start services
make test         # Run the test suite
make open         # Open the dashboard in your browser
```

---

## Local Development

### Prerequisites

- **Python 3.10+** (backend)
- **Node.js 18+** (frontend)
- **Ollama** (local AI — optional, falls back to rule-based detection)

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Edit with your values
uvicorn server:app --port 8002 --reload
```

### Frontend

```bash
cd frontend
npm install --legacy-peer-deps
PORT=3001 npm start
```

### Verify It Works

1. Open **http://localhost:3001**
2. Go to **Settings** → configure your AI provider (Ollama base URL + model)
3. Go to **Analyze** → paste any code snippet and click Analyze

---

## Environment Variables

All variables are documented in `.env.example`. The key ones:

| Variable | Required | Description |
|----------|----------|-------------|
| `DB_TYPE` | No | Set to `sqlite` for local mode (default) |
| `MONGO_URL` | No* | MongoDB connection string (*required if not using SQLite) |
| `OLLAMA_BASE_URL` | Yes* | LLM endpoint (*required for AI analysis) |
| `OLLAMA_MODEL` | Yes* | LLM model name (*required for AI analysis) |
| `CORS_ORIGINS` | Yes | Frontend URL(s), comma-separated |
| `SECRET_KEY` | No | Encryption key (auto-generated if not set) |
| `GITHUB_TOKEN` | No | GitHub PAT for PR review comments |
| `GITHUB_WEBHOOK_SECRET` | No | HMAC secret for webhook verification |
| `REACT_APP_BACKEND_URL` | No | Backend API URL for the frontend (default: `http://localhost:8002`) |

---

## GitHub Webhook Integration

DR.CODE can automatically review pull requests when configured with a GitHub webhook:

1. **Create a GitHub PAT** with `repo` and `pull_requests:write` scopes
2. **Add the token** in Settings → GitHub Integration
3. **Configure a webhook** on your repository pointing to `https://<your-url>/api/integrations/git/webhook`
4. **(Optional)** Set a webhook secret for HMAC signature verification

When a PR is opened or updated, DR.CODE fetches the changed files, analyzes them, and posts inline review comments with fix suggestions.

### Testing Webhooks Locally

Use [ngrok](https://ngrok.com) to expose your local backend:

```bash
ngrok http 8002
```

Then configure your GitHub webhook with the ngrok URL. Or test locally with the included script:

```bash
./scripts/test_webhook.sh 8002
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.12, FastAPI, Uvicorn |
| **Frontend** | React, shadcn/ui, Tailwind CSS |
| **Database** | SQLite (local) / MongoDB Atlas (production) |
| **AI** | Ollama (local), OpenAI-compatible providers |
| **Deployment** | Docker, Docker Compose, GHCR |
| **Testing** | pytest, requests |

---

## Project Structure

```
DR.Code-v2/
├── backend/
│   ├── server.py              # FastAPI application (all endpoints)
│   ├── database_sqlite.py     # SQLite adapter with Mongo-compatible API
│   ├── generators/            # Code generation modules (tests, docstrings, diagrams)
│   ├── tests/                 # Backend test suite
│   ├── requirements.txt       # Python dependencies
│   └── Dockerfile
├── frontend/
│   ├── src/                   # React application source
│   │   ├── pages/             # Dashboard, Reports, Settings, etc.
│   │   ├── components/        # UI components (shadcn/ui + custom panels)
│   │   ├── services/api.js    # HTTP client for backend API
│   │   └── hooks/             # Custom React hooks
│   ├── public/                # Static assets
│   └── Dockerfile
├── scripts/                   # Helper scripts (webhook test, health check)
├── drcode_installer/          # Standalone installer for end users
├── setup.sh                   # One-command setup script
├── Makefile                   # Common development commands
└── docker-compose.yml         # Container orchestration
```

---

## Security

- All API keys and tokens are encrypted with **Fernet symmetric encryption** before storage
- Secrets are **never returned** in API responses
- Webhook payloads are verified via **HMAC SHA-256** when a secret is configured
- Environment variables are the recommended method for production secrets

---

## License

MIT License — see [LICENSE](LICENSE) for details.

[![Tests Passing](https://img.shields.io/badge/tests-65%2F65-brightgreen.svg)](https://github.com/whoshotu/Dr.Code-II/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Backend: FastAPI](https://img.shields.io/badge/Backend-FastAPI-blue.svg)](https://fastapi.tiangolo.com)
[![Frontend: React](https://img.shields.io/badge/Frontend-React-blue.svg)](https://reactjs.org)


[![Tests Passing](https://img.shields.io/badge/tests-65%2F65-brightgreen.svg)](https://github.com/whoshotu/Dr.Code-II/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Backend: FastAPI](https://img.shields.io/badge/Backend-FastAPI-blue.svg)](https://fastapi.tiangolo.com)
[![Frontend: React](https://img.shields.io/badge/Frontend-React-blue.svg)](https://reactjs.org)

