# DR.CODE-v2 — Demo Checklist

## Pre-Demo Setup (5 min before judges)

- [ ] Backend running: `curl -sf http://localhost:8002/api/health` returns 200
- [ ] Frontend running: `curl -sf http://localhost:3001` returns 200
- [ ] Ollama running: `curl -sf http://localhost:11434/api/tags` returns 200
- [ ] No stale processes: `ps aux | grep uvicorn` shows only one backend

## Demo Sequence

### Step 1: Open Dashboard (30 sec)
- [ ] Open http://localhost:3001 in browser
- [ ] Point out: dark-mode UI, analysis stats, clean layout

### Step 2: Code Analysis (45 sec)
- [ ] Navigate to Analyze tab
- [ ] Paste this code:
  ```python
  password = "admin123"
  api_key = "sk-12345"
  eval(user_input)
  ```
- [ ] Click Analyze
- [ ] Show results: severity scores, issue categories, fix suggestions

### Step 3: GitHub Integration Settings (30 sec)
- [ ] Navigate to Settings
- [ ] Scroll to GitHub Integration section
- [ ] Show token input (masked after save)
- [ ] Show webhook secret field
- [ ] Explain: all secrets encrypted with Fernet before storage

### Step 4: Webhook Demo (30 sec)
- [ ] Open terminal
- [ ] Run: `./scripts/test_webhook.sh 8002`
- [ ] Show output: `"status": "skipped-no-token"` — graceful degradation
- [ ] Explain: with a real GitHub PAT, this would analyze PR files and post inline comments

### Step 5: Test Coverage (15 sec)
- [ ] Run: `cd backend && pytest tests/test_webhook_pipeline.py -v`
- [ ] Show: 9/9 tests passing
- [ ] Mention: 21 total v2 tests pass (webhook + API + GitHub regression)

## Fallback Paths

### If GitHub token unavailable:
- Show `skipped-no-token` response — explain this is intentional graceful degradation
- The webhook pipeline is fully implemented, just needs a PAT to post to real PRs

### If Ollama unavailable:
- Analysis falls back to rule-based mode (no LLM)
- Still detects hardcoded secrets, eval(), SQL injection, XSS, etc.
- Show rule-based analysis results

### If frontend won't start:
- Demo via curl commands only:
  ```bash
  curl http://localhost:8002/api/health
  curl -X POST http://localhost:8002/api/analyze -H "Content-Type: application/json" -d '{"code":"password = \"secret\"","filename":"test.py","language":"python"}'
  ./scripts/test_webhook.sh 8002
  ```

## Post-Demo Cleanup
- [ ] Stop backend: `pkill -f uvicorn`
- [ ] Clear test data if needed: `rm backend/drcode.db`
