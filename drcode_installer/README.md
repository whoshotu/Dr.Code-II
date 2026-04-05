# DR.CODE v2 Installer

One-command install for DR.CODE v2 - AI-powered code analysis platform.

## How It Works

| Component | Source | Description |
|-----------|--------|-------------|
| Backend | GHCR | `ghcr.io/whoshotu/dr-code-v2-backend:latest` |
| Frontend | GHCR | `ghcr.io/whoshotu/dr-code-v2-frontend:latest` |
| MongoDB | Docker Hub | `mongo:7` (official image) |

**No Docker Hub account needed** - only GitHub Container Registry (GHCR).

---

## Quick Start

### Linux / Mac / WSL

```bash
curl -sL https://raw.githubusercontent.com/whoshotu/DR.Code-v2/main/drcode_installer/install.sh | bash
```

Or download and run:

```bash
chmod +x install.sh
./install.sh
```

### Windows

```powershell
irm https://raw.githubusercontent.com/whoshotu/DR.Code-v2/main/drcode_installer/install.ps1 | iex
```

Or download and run in PowerShell:

```powershell
.\install.ps1
```

---

## Requirements

- Docker 20.10+
- Docker Compose v2+ (or docker-compose)
- Ports 3001, 8002, 27017 available

---

## Commands

| Command | Description |
|---------|-------------|
| `./install.sh` | Install and start (default) |
| `./install.sh start` | Start services |
| `./install.sh stop` | Stop services |
| `./install.sh status` | Show status |
| `./install.sh update` | Pull latest images and restart |
| `./install.sh clean` | Remove all data |
| `./install.sh help` | Show help |

---

## After Install

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3001 |
| Backend | http://localhost:8002 |
| API | http://localhost:8002/api |

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_TOKEN` | PAT for private GHCR images | (optional) |
| `GITHUB_ACTOR` | GitHub username | (auto-detected) |

Set `GITHUB_TOKEN` if pulling private images:

```bash
export GITHUB_TOKEN=ghp_xxxxx
./install.sh
```

---

## Uninstall

```bash
./install.sh clean
```

This removes all containers and data volumes.

---

## Configuration

Edit `.env.docker` after install:

```bash
# MongoDB (docker network - auto-discovered)
MONGO_URL=mongodb://mongo:27017/drcode

# Ollama (host machine)
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=codellama

DB_NAME=drcode
CORS_ORIGINS=http://localhost:3001
```

---

## Troubleshooting

### Ports in use
If ports are already in use, stop other services first:

```bash
# Check what's using the ports
lsof -i :3001
lsof -i :8002
lsof -i :27017
```

### Docker not running
Start Docker Desktop and try again.

### Images won't pull
If pulling fails, you may need to log in:

```bash
export GITHUB_TOKEN=ghp_your_token_here
./install.sh
```

---

## Desktop App (Linux)

A desktop entry is provided for Linux systems. After cloning the repo:

```bash
cd drcode_installer
./install-desktop.sh
```

This installs "DR.CODE Installer" to your app drawer with the project icon.

---

## Support

- Issues: https://github.com/whoshotu/DR.Code-v2/issues
