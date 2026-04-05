.PHONY: install dev docker-up docker-down docker-build test open stop clean logs help installer installer-start installer-stop installer-status installer-clean

help:
	@echo "DR.CODE-v2 Makefile"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  install            Install all dependencies (npm + pip)"
	@echo "  dev                Start local development (backend + frontend)"
	@echo "  docker-up          Start services with Docker Compose"
	@echo "  docker-down         Stop Docker services"
	@echo "  docker-build       Build Docker images"
	@echo "  test               Run backend tests"
	@echo "  open               Open frontend in browser"
	@echo "  stop               Stop all running services"
	@echo "  clean              Remove node_modules and __pycache__"
	@echo "  logs               View Docker logs"
	@echo ""
	@echo "  installer          Install via drcode_installer (Docker required)"
	@echo "  installer-start    Start services via installer"
	@echo "  installer-stop     Stop services via installer"
	@echo "  installer-status   Show service status"
	@echo "  installer-clean    Remove all data"

install:
	@echo "Installing dependencies..."
	@cd frontend && npm install --legacy-peer-deps
	@echo "Frontend dependencies installed"

dev:
	@echo "Starting local development..."
	@echo "Backend: http://localhost:8002"
	@echo "Frontend: http://localhost:3001"
	@cd backend && uvicorn server:app --port 8002 --reload &
	@cd frontend && PORT=3001 npm start

docker-up:
	@if [ ! -f .env.docker ] && [ -f .env.docker.sample ]; then cp .env.docker.sample .env.docker; fi
	docker-compose up -d
	@echo "Services started. Frontend: http://localhost:3001"

docker-down:
	docker-compose down

docker-build:
	docker-compose build

test:
	cd backend && python -m pytest tests/ -v

open:
	@xdg-open http://localhost:3001 2>/dev/null || open http://localhost:3001 2>/dev/null || echo "Open http://localhost:3001 in your browser"

stop:
	@pkill -f "uvicorn server:app" 2>/dev/null || true
	@docker-compose down 2>/dev/null || true

clean:
	@rm -rf frontend/node_modules
	@find backend -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned"

logs:
	docker-compose logs -f

installer:
	@cd drcode_installer && ./install.sh

installer-start:
	@cd drcode_installer && ./install.sh start

installer-stop:
	@cd drcode_installer && ./install.sh stop

installer-status:
	@cd drcode_installer && ./install.sh status

installer-clean:
	@cd drcode_installer && ./install.sh clean
