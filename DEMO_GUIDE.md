# DR.CODE-v2 — Demo Guide

> AI-powered code quality analysis with automated GitHub PR review comments.

## What It Does

DR.CODE-v2 receives GitHub pull request webhooks, analyzes changed files for code quality issues (security risks, hardcoded secrets, anti-patterns), and posts inline review comments + a summary back to the PR — all powered by a local LLM (Ollama).

## 60-Second Setup

```bash
git clone https://github.com/whoshotu/DR.Code-v2.git
cd DR.Code-v2
./setup.sh          # auto-detects MongoDB + Ollama, starts services
```

**Ports:** Backend `8002` | Frontend `3001`

## Demo Flow (3 minutes)

### 1. Show the Dashboard
Open http://localhost:3001 — dark-mode UI with analysis stats.

### 2. Show Code Analysis
- Go to the Analyze tab
- Paste any Python/JS code snippet
- Click Analyze → see issues, severity scores, fix suggestions

### 3. Show GitHub Integration
- Go to Settings → GitHub Integration section
- Show token input + webhook secret fields
- Show masked token display (secrets never shown in plaintext)

### 4. Trigger Webhook Demo
```bash
./scripts/test_webhook.sh 8002
```
Shows the webhook endpoint accepting a mock PR event and returning `skipped-no-token` (no GitHub PAT configured — graceful degradation).

### 5. Show Test Coverage
```bash
cd backend && source venv/bin/activate
REACT_APP_BACKEND_URL=http://localhost:8002 pytest tests/test_webhook_pipeline.py tests/test_github_webhook_regression.py -v
```
21 tests pass — signature verification, graceful degradation, backward compatibility.

## Webhook Test Command

```bash
./scripts/test_webhook.sh 8002
```

## Health Check

```bash
curl http://localhost:8002/api/health
```

## Architecture

```
GitHub PR → Webhook → FastAPI (8002) → Rule-based analysis + Ollama LLM → Inline PR comments
                              ↓
                         SQLite (drcode.db)
                              ↓
                    React Dashboard (3001)
```

## Key Features

| Feature | Status |
|---------|--------|
| Code quality analysis | ✅ |
| Severity scoring (critical/high/medium/low) | ✅ |
| GitHub PR webhook pipeline | ✅ |
| HMAC signature verification | ✅ |
| Encrypted secret storage | ✅ |
| Graceful degradation (no token) | ✅ |
| Backward-compatible stub payloads | ✅ |
| Multi-provider LLM routing | ✅ |
| Repository bulk analysis | ✅ |
