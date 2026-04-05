# DR.CODE-v2 — Hackathon Demo Script

## 2-Minute Verbal Pitch

> "DR.CODE-v2 is an AI-powered code review bot that automatically analyzes pull requests and posts inline comments with quality issues and fix suggestions. It runs entirely self-hosted — no external SaaS, no code leaves your infrastructure. When a PR is opened, GitHub sends a webhook, DR.CODE fetches the changed files, runs rule-based detection plus local LLM analysis, and posts structured review comments back to the PR. All secrets are encrypted, all analysis is auditable, and the whole thing starts with one command."

## Exact Terminal Commands

### Pre-Demo (5 min before)

```bash
# Terminal 1 — Start backend
cd /home/whoshotu/Documents/Antigravity/DR.Code-v2-main/backend
source venv/bin/activate
uvicorn server:app --port 8002 --host 0.0.0.0

# Terminal 2 — Verify health
curl -s http://localhost:8002/api/health | python3 -m json.tool
```

Expected output:
```json
{
  "status": "ok",
  "ollama_configured": true,
  "ollama_ready": true,
  "active_provider": "ollama"
}
```

### Demo Sequence (3 minutes)

#### Step 1: Dashboard (30 sec)
- Open browser: http://localhost:3001
- Point to: dark-mode UI, analysis stats, clean navigation
- Say: "This is the DR.CODE dashboard — single pane of glass for all code quality data."

#### Step 2: Code Analysis (45 sec)
- Click "Analyze" in sidebar
- Paste this code:
  ```python
  password = "admin123"
  api_key = "sk-live-12345"
  result = eval(user_input)
  print(f"SELECT * FROM users WHERE id = {user_id}")
  ```
- Click "Analyze"
- Show results:
  - Hardcoded secret (critical, score 92)
  - eval() usage (high, score 86)
  - SQL injection risk (critical, score 94)
- Say: "Rule-based detection catches these instantly. With Ollama enabled, the LLM adds contextual analysis."

#### Step 3: GitHub Integration (30 sec)
- Click "Settings" in sidebar
- Scroll to GitHub Integration section
- Point to:
  - Token input field (show it's empty)
  - Webhook secret field
  - Status indicators (token: ❌, secret: ❌)
- Say: "All tokens are encrypted with Fernet before storage. The masked value is never returned in API responses."

#### Step 4: Webhook Demo (30 sec)
- Switch to terminal
- Run:
  ```bash
  cd /home/whoshotu/Documents/Antigravity/DR.Code-v2-main
  ./scripts/test_webhook.sh 8002
  ```
- Show output:
  ```
  HTTP Status: 200
  {
    "source": "github",
    "event_type": "pull_request",
    "status": "skipped-no-token",
    ...
  }
  Webhook accepted successfully
  ```
- Say: "The webhook endpoint received the PR event. It returns `skipped-no-token` because no GitHub PAT is configured. With a real token, this would fetch the changed files, analyze them, and post inline comments to the PR."

#### Step 5: Test Coverage (15 sec)
- Run:
  ```bash
  cd backend && pytest tests/test_webhook_pipeline.py tests/test_github_webhook_regression.py -v --tb=short 2>&1 | tail -25
  ```
- Show: 16/16 PASS
- Say: "Every webhook scenario is tested — signature verification, graceful degradation, backward compatibility."

## Fallback Paths

### If GitHub Token is Unavailable
**What to say:** "The webhook pipeline is fully implemented. Without a PAT, it gracefully returns `skipped-no-token` instead of crashing. With a token, it would:
1. Fetch PR changed files via GitHub API
2. Run rule-based + LLM analysis on each file
3. Post inline review comments on specific lines
4. Post a summary comment on the PR thread"

**Show instead:** The `skipped-no-token` response from the webhook test proves the pipeline handles missing credentials gracefully.

### If Webhook Comments Cannot Post Live
**What to say:** "The inline comment posting uses the GitHub REST API via the `GithubClient` class. In a live repo with a valid PAT, it posts:
- Individual fix proposals as inline review comments on the exact line
- A summary comment with total fixes and critical count"

**Show instead:** The `GithubClient` class in `backend/server.py` lines 2526-2720 — point to `post_pr_inline_comment()` and `post_pr_summary_comment()` methods.

### If Ollama is Not Running
**What to say:** "Without Ollama, DR.CODE falls back to pure rule-based detection. It still catches hardcoded secrets, eval(), SQL injection, XSS, weak cryptography, and dozens of other patterns. The LLM adds contextual analysis but isn't required for core functionality."

**Show instead:** The rule-based analysis output from Step 2 — all issues are detected without LLM.

### If Frontend Won't Start
**What to say:** "The entire API is accessible via curl. Let me demo the core functionality directly."

**Run instead:**
```bash
# Health check
curl http://localhost:8002/api/health | python3 -m json.tool

# Code analysis
curl -X POST http://localhost:8002/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"code":"password = \"secret\"\napi_key = \"sk-123\"","filename":"test.py","language":"python"}' | python3 -m json.tool

# Webhook test
./scripts/test_webhook.sh 8002
```

## Demo Order (Recommended)

1. **Dashboard** — visual impact, sets context
2. **Code Analysis** — shows core value proposition
3. **GitHub Settings** — shows security posture
4. **Webhook Test** — proves integration works
5. **Test Coverage** — proves engineering quality

Total time: 3 minutes. Leave 2 minutes for Q&A.

## Judge Questions to Expect

**Q: "How is this different from GitHub Copilot?"**
A: "Copilot writes code. DR.CODE reviews it — detecting security risks, anti-patterns, and hardcoded secrets before they merge. It's a quality gate, not a code generator."

**Q: "Can it analyze entire repositories?"**
A: "Yes — the repository analysis endpoint scans all files with supported extensions, generates fix proposals, and lets you apply them selectively or in bulk."

**Q: "What languages does it support?"**
A: "Rule-based detection works for Python, JavaScript, JSX, TypeScript, Go, and Java. LLM analysis is language-agnostic."

**Q: "Is this production-ready?"**
A: "The webhook pipeline is fully tested with 16 passing tests. The rule-based engine is mature. The SQLite backend is for demo simplicity — it supports MongoDB for production scale."
