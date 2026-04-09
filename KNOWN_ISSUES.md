# Dr.Code-II — Known Issues

## Environmental Pitfalls

### 1. IDE Import Resolve Errors

**Issue:** VS Code / Pyright may report missing imports for `aiosqlite`, `dotenv`, or `fastapi` even when the application runs perfectly.

**Cause:** This occurs when the IDE interpreter is not correctly pointed to `${workspaceFolder}/backend/venv/bin/python`.

**Fix:** Select the backend virtual environment as your active interpreter in your IDE.

## Scale & Architecture Limitations

1. **SQLite Native Mode** — Dr.Code-II uses a high-performance SQLite adapter for zero-config deployment. While stable for teams and individual usage, it is not designed for synchronous multi-tenant production scaling.

2. **Backend-First Testing** — The current test suite (65+ tests) has 100% coverage of backend logic and integrations. React component testing is currently deferred in favor of runtime validation.

3. **Cognitive Complexity Warnings** — Several legacy functions in `server.py` trigger cognitive complexity warnings. These are identified and slated for future modularization once the core integration lanes are finalized.

## What's 100% Functional

- ✅ **Hybrid Code Analysis** (Rule-based + LLM context)
- ✅ **Intelligent Setup** (Auto port detection & configuration persistence)
- ✅ **GitHub Webhook Pipeline** (HMAC verification & inline PR reviews)
- ✅ **Non-Destructive Resets** (Full Trash/Archival system)
- ✅ **Encrypted Secret Management** (Fernet symmetric encryption)
- ✅ **Graceful Provider Degradation** (Local AI -> Hosted AI -> Rule-based only)

## Deferred Features (Roadmap)

- **Webhook Event Replay**: Mechanism to re-trigger failed GitHub deliveries.
- **Advanced Analytics**: Time-series metrics and trend analysis for repo quality history.
- **Frontend Unit Tests**: Component-level coverage for the React dashboard.
