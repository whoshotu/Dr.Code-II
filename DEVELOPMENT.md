# Dr.Code-II — Development Guide

This guide is for developers and maintainers of Dr.Code-II.

---

## Quickstart (2 min)

For standard usage, use the automated setup:

```bash
./setup.sh
docker compose up -d
```

---

## Manual Development Setup

If you need to run services individually for debugging or feature development.

### Backend

1. **Virtual Environment**:

   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Start Server**:

   ```bash
   # Default port: 8002
   uvicorn server:app --port 8002 --reload
   ```

### Frontend

1. **Install Dependencies**:

   ```bash
   cd frontend
   npm install --legacy-peer-deps
   ```

2. **Start Dev Server**:

   ```bash
   # Default port: 3001
   PORT=3001 npm start
   ```

---

## Troubleshooting

### Interpreter & Import Errors

If your IDE (VS Code/Pyright) reports missing imports for `aiosqlite`, `dotenv`, or `fastapi`:

1. Ensure the backend virtual environment is active.
2. Verify the Python interpreter path is set to `${workspaceFolder}/backend/venv/bin/python`.
3. These are typically local environment configuration issues and do not impact runtime or Docker builds.

### Port Conflicts

Dr.Code-II automatically detects available ports. If you need to force a specific port:

1. Edit the `.env` file in the root.
2. Update `BACKEND_PORT` or `FRONTEND_PORT`.
3. Update `REACT_APP_BACKEND_URL` to match.
4. Re-run `./setup.sh` (Option 2) to sync configurations.

### Database Resets

To clear the application state:

1. Run `./setup.sh` and select **Option 3 (Reset config)**.
2. Or manually delete `backend/drcode.db`, `.env`, and `.env.docker`.

---

## Advanced Configuration

### GitHub Integration

To test webhooks locally:

1. Use `ngrok` or `localtunnel` to expose port 8002.
2. Set the `GITHUB_WEBHOOK_SECRET` in `.env` to enable HMAC verification.
3. Use `./scripts/test_webhook.sh 8002` to simulate payload delivery.

### AI Providers

Dr.Code-II supports multiple backends. Configure these in the **Settings** page:

- **Local**: Ollama (ensure `OLLAMA_BASE_URL` is accessible).
- **Hosted**: OpenAI-compatible, Google Gemini, Anthropic Claude.
- **Model**: Default coding model is `qwen2.5-coder:7b`.
