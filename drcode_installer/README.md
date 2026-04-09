# Dr.Code-II v2 Installer

One-command install for **Dr.Code-II** — the AI-powered code analysis platform.

---

## Quickstart (2 min)

```bash
git clone https://github.com/whoshotu/Dr.Code-II.git
cd Dr.Code-II
./setup.sh
docker compose up -d
```

---

## How It Works

Dr.Code-II v2 is built for zero-config simplicity using a high-performance SQLite backend.

| Component | Source | Description |
| :--- | :--- | :--- |
| **Backend** | GHCR | `ghcr.io/whoshotu/dr-code-ii-backend:latest` |
| **Frontend** | GHCR | `ghcr.io/whoshotu/dr-code-ii-frontend:latest` |
| **Database** | Native | SQLite (Local file persistence) |

## Installer Commands (CLI)

| Command | Description |
| :--- | :--- |
| `./install.sh` | Full installation and service start. |
| `./install.sh stop` | Stop all Docker containers. |
| `./install.sh status` | Check service health and port status. |
| `./install.sh clean` | Purge all data and environment configs. |

## After Install

| Service | Default URL |
| :--- | :--- |
| **Dashboard** | [http://localhost:3001](http://localhost:3001) |
| **API Health** | [http://localhost:8002/api/health](http://localhost:8002/api/health) |

---

## Requirements

- **Docker** 20.10+
- **Docker Compose** v2+
- **Ollama** (Optional for local-only LLM analysis)

## Troubleshooting

### Port Conflicts

Dr.Code-II auto-detects ports during the first run. If you manually change ports in `.env`, re-run `./setup.sh` to sync the configuration across services.

### AI Provider Config

If the backend starts but analysis fails, check your **Settings** page in the dashboard to ensure your AI provider (Ollama, OpenAI, Gemini, or Anthropic) is correctly configured with a valid model and key.

---

## Support & Issues

- **GitHub Repository**: [https://github.com/whoshotu/Dr.Code-II](https://github.com/whoshotu/Dr.Code-II)
- **Report Bugs**: [https://github.com/whoshotu/Dr.Code-II/issues](https://github.com/whoshotu/Dr.Code-II/issues)
