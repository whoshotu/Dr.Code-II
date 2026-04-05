# DR.CODE-v2 — Agent Execution Contract

> Read this file before making any change to the repository.
> If your work conflicts with this document, stop and report the conflict.

---

## 1. Mission

DR.CODE-v2 is a self-hosted AI-assisted code analysis platform with a dark-mode React dashboard and a FastAPI + SQLite backend.

This repository exists to support exactly three allowed work lanes:

1. Real GitHub PR Webhook Pipeline
2. GitHub Integration Settings UI
3. Repo hygiene audit and owner-approved cleanup for unused, obsolete, duplicate, or disorganized files

If a task does not directly support one of those lanes, it is out of scope unless the project owner explicitly approves it.

---

## 2. Scope Rules

### Lane 1 — GitHub PR Webhook Pipeline
Allowed:
- GitHub pull request webhook handling
- Fetching changed PR files
- Running analysis on webhook-triggered PRs
- Posting inline review comments and summary comments
- Graceful degradation for missing token, unsupported files, invalid signatures, and GitHub API failures
- Testing and validation required to make webhook flow reliable

### Lane 2 — GitHub Integration Settings UI
Allowed:
- GitHub token/settings UI
- Webhook URL display
- Setup guide in the frontend
- UI validation and integration behavior tied to GitHub settings
- Testing and validation required to make settings UI reliable

### Lane 3 — Repo Hygiene
Allowed:
- Read-only audit of unused, obsolete, duplicate, dead, or archival candidate files
- Cleanup planning and organization proposals
- Owner-approved cleanup or archive work after audit review
- Narrow reorganization only when approved by the lead and explicitly tied to repository hygiene

### Out of Scope
- New languages
- Rule engine expansion
- Authentication model changes
- New database collections beyond `integration_events` and `app_settings`
- Redesign of existing pages unrelated to GitHub settings
- Changes to `design_guidelines.json`
- New analytics, telemetry, or tracking
- New packages without explicit approval
- Broad CI/CD or deployment redesign
- Broad architectural rewrites
- Opportunistic cleanup unrelated to the assigned lane

When in doubt, classify the task first:
- Lane 1: GitHub PR Webhook Pipeline
- Lane 2: GitHub Integration Settings UI
- Lane 3: Repo Hygiene
- Required support validation
- Out of scope

If the task is out of scope, stop.

---

## 3. File Ownership Rules

### Backend
- Primary backend file: `backend/server.py`
- Do not split backend logic into new Python modules unless explicitly instructed
- Use existing FastAPI + async SQLite patterns
- Use Pydantic models for request/response schemas
- Do not introduce a new HTTP client library for GitHub calls
- Use existing request patterns and non-blocking wrapping where required
- Never log secrets
- Encrypt secrets before storage
- Preserve backward compatibility with existing webhook behavior

### Frontend
- Frontend lives under `frontend/src/`
- Use React + shadcn/ui only
- All HTTP calls go through `frontend/src/services/api.js`
- Dark mode only
- Every interactive element must have a `data-testid`
- Use toast notifications for success/error states
- Do not add light mode

### Repo Hygiene
- Repo hygiene starts with audit first
- No worker may delete, move, rename, or archive files until the lead approves a specific cleanup plan
- Hygiene work must provide evidence for every cleanup candidate
- Hygiene work must classify each candidate as:
  - safe to ignore
  - defer
  - validate manually
  - cleanup candidate
  - archive candidate

### Protected Files
- Do not edit `AGENTS.md` unless explicitly asked by the project owner
- Do not edit unrelated files for convenience cleanup
- Do not touch reference project `../DR.CODE/`

---

## 4. Testing Rules

- Every backend behavior change requires tests
- Existing tests must keep passing
- Mock all external GitHub calls in tests
- Add happy-path and graceful-failure coverage for new endpoint behavior
- Prefer focused regression tests over broad speculative rewrites

Useful backend test command:

```bash
cd backend
source venv/bin/activate
REACT_APP_BACKEND_URL=http://localhost:8002 pytest tests/ -v
```

---

## 5. Code Quality Rules

### Python
- Imports only at top of file
- Standard library -> third-party -> local import order
- No buried imports
- No sloppy suppressions for basic formatting/import issues
- Use modern Python typing
- Return types required
- No magic numbers or hardcoded secrets
- Use `logging.getLogger(__name__)`, never `print()`

### FastAPI
- `async def` routes
- Pydantic models first
- No raw unstructured endpoint responses
- Webhook failures must degrade gracefully, not crash the server
- If webhook secret exists, verify signature
- If webhook secret is absent, allow dev-safe bypass with warning logging
- Webhook-triggered analysis should record governance events consistently

### Frontend
- Keep to existing design system
- Respect existing router patterns
- Use `data-testid` consistently
- No direct `fetch()` or `axios` inside pages/components

---

## 6. Git Rules

- One logical change per commit
- Use specific commit prefixes: `feat:`, `fix:`, `test:`, `chore:`
- Do not commit `.env`, secrets, `node_modules/`, or cache files
- Work from a feature branch, not directly on protected baseline

---

## 7. Agent System

### Lead Agent
The lead agent must:
1. Break work into isolated tasks
2. Keep every task inside approved scope
3. Assign one owner per file surface
4. Prevent worker overlap
5. Review worker output before merge
6. Reject drift immediately
7. Require every worker to end with a handoff note for the next worker or a return-to-lead decision

### Worker Agents
Workers must:
- Start from `AGENTS.md` and `/orchestration lead`
- Do only the assigned task
- Stay inside allowed files
- Stop when acceptance criteria are met
- Report blockers instead of improvising architecture changes
- Avoid unrelated cleanup or refactors
- End with a handoff note for the next worker or lead

---

## 8. Delegation Format

Every worker assignment must include:
- Objective
- Why it is in scope
- Files allowed
- Files forbidden
- Acceptance criteria
- Output required
- Stop conditions
- Handoff expectation for the next worker

Use this structure:

WORKER:
[agent-name]

OBJECTIVE:
[one concrete result]

WHY THIS IS IN SCOPE:
[lane 1 / lane 2 / lane 3 / required support validation]

FILES YOU MAY EDIT:
- path
- path

FILES YOU MUST NOT EDIT:
- AGENTS.md
- path
- path

ACCEPTANCE CRITERIA:
- condition
- condition

OUTPUT BACK:
- changed files
- summary
- tests run
- blockers
- risks
- handoff recommendation

STOP WHEN:
- done
- blocked
- scope would expand

---

## 9. Enforcement Language

Use these exact phrases when needed:
- Out of scope under AGENTS.md. Deferred unless owner approves.
- Rejected: overlaps protected file ownership.
- Rejected: violates single-file backend rule.
- Rejected: violates frontend API-layer rule.
- Rejected: AGENTS.md may not be modified.
- Defer: unrelated cleanup not required for the current lane.
- Audit first: repo cleanup requires evidence before action.
- Owner approval required before delete/move/archive actions.

---

## 10. Final Checklist

Before submitting work:
- [ ] Tests pass
- [ ] No new package drift
- [ ] No plaintext secrets in diff
- [ ] No out-of-scope changes
- [ ] Interactive UI elements have `data-testid`
- [ ] Work stays inside an approved lane
- [ ] AGENTS.md was not modified without explicit approval
- [ ] A clear handoff note exists for the next worker or lead
