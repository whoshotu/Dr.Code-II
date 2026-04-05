# DR.CODE-v2 — Known Issues

## Resolved

### Repository Fix Application Tests (was 5 failing)
**Fixed:** SQLite adapter now recognizes `session_id` as a document identifier in `insert_one`, `find_one`, and `update_one`. All 5 repository-fix regression tests pass. Full suite: 65/65.

## Scale Limitations

1. **SQLite instead of MongoDB** — The "Judge-Ready" mode uses SQLite with a Mongo-compatible adapter. This works for single-user demo scenarios but isn't designed for concurrent multi-user production loads.

2. **No frontend testing** — Zero unit/integration tests for React components. All test coverage is backend-only.

3. **No real-time PR comment posting** — The webhook pipeline is fully implemented and tested with mock payloads, but posting actual inline comments to GitHub PRs requires a valid GitHub PAT with `repo` scope. Without a token, the pipeline gracefully returns `skipped-no-token`.

## Intentionally Deferred

1. **CI/CD pipeline** — No GitHub Actions workflows for automated testing/deployment
2. **Rate limiting** — No API rate limiting on webhook or analysis endpoints
3. **Authentication** — Uses header-based actor system (no OAuth/JWT)
4. **Multi-language LLM analysis** — Rule-based detection works for Python/JS/Go/Java; LLM analysis is language-agnostic but prompt-optimized for Python
5. **Webhook event replay** — No mechanism to replay failed webhook deliveries
6. **Dashboard analytics** — No time-series metrics or trend analysis

## What Works for Demo

- ✅ Code analysis (rule-based + LLM hybrid)
- ✅ GitHub webhook pipeline (full implementation)
- ✅ HMAC signature verification
- ✅ Encrypted secret storage
- ✅ Graceful degradation (no token, no Ollama)
- ✅ Settings UI with GitHub integration
- ✅ 65/65 backend tests passing
- ✅ Health endpoint
- ✅ Backward-compatible stub payloads
