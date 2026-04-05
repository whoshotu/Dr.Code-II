#!/bin/bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}======================================"
echo "  DR.CODE v2 - 'Judge-Ready' Setup"
echo -e "======================================${NC}"

# --- Detection with Timeout ---
check_with_timeout() {
    local cmd="$1"
    local timeout_sec="${2:-2}"
    timeout "$timeout_sec" bash -c "$cmd" &>/dev/null
    return $?
}


detect_ollama() {
    # Check 1: Native Ollama CLI
    if command -v ollama &> /dev/null; then
        if ! curl -sf http://localhost:11434/api/tags &>/dev/null; then
            echo -e "${YELLOW}Starting local Ollama server in background...${NC}"
            ollama serve >/dev/null 2>&1 &
            sleep 3
        fi
        OLLAMA_BASE_URL="http://localhost:11434"
        echo -e "${GREEN}✓ Ollama is running locally on localhost:11434${NC}"

        # Count available models (subtract 1 for the header line)
        local model_count=$(ollama list | tail -n +2 | grep -v "^$" | wc -l)
        if [ "$model_count" -eq 0 ]; then
            echo -e "${YELLOW}⚠ No models found locally.${NC}"
            read -p "Would you like to install a quick coding model (qwen2.5-coder:7b)? [y/N]: " install_model
            if [[ "$install_model" =~ ^[Yy]$ ]]; then
                echo -e "${CYAN}Installing model... this may take a few minutes.${NC}"
                ollama pull qwen2.5-coder:7b
                OLLAMA_MODEL="qwen2.5-coder:7b"
            fi
        else
            echo -e "${GREEN}Available Ollama models:${NC}"
            ollama list
        fi
        return 0
    fi
    
    # Check 2: Docker container named "ollama"
    if docker ps --format "{{.Names}}" 2>/dev/null | grep -qi "^ollama$"; then
        OLLAMA_BASE_URL="http://host.docker.internal:11434"
        echo -e "${GREEN}✓ Ollama detected in Docker container${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}⚠ No Ollama detected${NC}"
    return 1
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Error: Docker is not installed${NC}"
        echo "Install Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi
    if ! docker info &> /dev/null; then
        echo -e "${RED}Error: Docker is not running${NC}"
        echo "Start Docker and try again"
        exit 1
    fi
    echo -e "${GREEN}✓ Docker ready${NC}"
}

detect_all_deps() {
    echo -e "${CYAN}Detecting dependencies...${NC}"
    local deps_found=0
    
    # Try Ollama
    if detect_ollama; then
        deps_found=$((deps_found + 1))
    else
        echo "  → Configure Ollama later via Settings UI"
    fi
    
    # Auto-configure defaults if all found
    if [ $deps_found -eq 1 ]; then
        echo ""
        echo -e "${GREEN}✅ Quick Start: dependencies found, auto-configuring...${NC}"
        return 0
    else
        echo ""
        echo -e "${YELLOW}⚠ Some dependencies missing - will prompt for configuration${NC}"
        return 1
    fi
}

setup_ai() {
    echo ""
    echo -e "${CYAN}Step 1: AI Model Configuration${NC}"
    
    if [ -n "$OLLAMA_BASE_URL" ]; then
        echo -e "${GREEN}✓ Auto-detected: $OLLAMA_BASE_URL${NC}"
    else
        echo "  1) Use Local Ollama (Recommended)"
        echo "  2) Use OpenAI (Cloud)"
        echo "  3) Skip (Configure later)"
        read -p "Choose [1]: " ai_choice
        ai_choice=${ai_choice:-1}
        
        if [ "$ai_choice" = "1" ]; then
            OLLAMA_BASE_URL="http://localhost:11434"
        elif [ "$ai_choice" = "2" ]; then
            read -p "Enter OpenAI API key: " OPENAI_API_KEY
            OLLAMA_BASE_URL="https://api.openai.com/v1"
            OLLAMA_MODEL="gpt-4o"
            read -p "Enter OpenAI model [gpt-4o]: " OLLAMA_MODEL
            OLLAMA_MODEL=${OLLAMA_MODEL:-gpt-4o}
        fi
    fi
    
    if [ -z "$OLLAMA_MODEL" ]; then
        read -p "Enter model name [qwen2.5-coder:7b]: " OLLAMA_MODEL
        OLLAMA_MODEL=${OLLAMA_MODEL:-qwen2.5-coder:7b}
    fi
}

setup_github() {
    echo ""
    echo -e "${CYAN}Step 2: GitHub Integration (Optional)${NC}"
    
    if [ -z "$GITHUB_TOKEN" ]; then
        read -p "GitHub Token (Enter to skip): " GITHUB_TOKEN
        if [ -n "$GITHUB_TOKEN" ]; then
            read -p "Webhook Secret: " GITHUB_WEBHOOK_SECRET
        fi
    fi
}

save_config() {
    echo ""
    echo -e "${CYAN}Saving configuration...${NC}"
    
    # Never overwrite existing .env
    if [ -f .env ] && [ -s .env ]; then
        echo -e "${YELLOW}⚠ .env exists, not overwriting${NC}"
        USE_EXISTING_ENV=true
    else
        USE_EXISTING_ENV=false
    fi
    
    # Generate .env if doesn't exist
    if [ "$USE_EXISTING_ENV" = false ]; then
        cat > .env << EOF
# DR.CODE-v2 'Judge-Ready' Environment
OLLAMA_BASE_URL=${OLLAMA_BASE_URL:-http://localhost:11434}
OLLAMA_MODEL=${OLLAMA_MODEL:-qwen2.5-coder:7b}
CORS_ORIGINS=http://localhost:3001
DB_TYPE=sqlite
EOF

        if [ -n "$GITHUB_TOKEN" ]; then
            echo "GITHUB_TOKEN=$GITHUB_TOKEN" >> .env
        fi
        if [ -n "$GITHUB_WEBHOOK_SECRET" ]; then
            echo "GITHUB_WEBHOOK_SECRET=$GITHUB_WEBHOOK_SECRET" >> .env
        fi
        echo -e "${GREEN}✓ Config saved to .env${NC}"
    else
        echo -e "${GREEN}✓ Using existing .env configuration${NC}"
    fi

    # Always generate .env.docker (for Docker Compose)
    cat > .env.docker << EOF
# DR.CODE-v2 'Judge-Ready' Environment (Docker)
OLLAMA_BASE_URL=${OLLAMA_BASE_URL:-http://host.docker.internal:11434}
OLLAMA_MODEL=${OLLAMA_MODEL:-qwen2.5-coder:7b}
CORS_ORIGINS=http://localhost:3001
DB_TYPE=sqlite
EOF

    if [ -n "$GITHUB_TOKEN" ]; then
        echo "GITHUB_TOKEN=$GITHUB_TOKEN" >> .env.docker
    fi
    if [ -n "$GITHUB_WEBHOOK_SECRET" ]; then
        echo "GITHUB_WEBHOOK_SECRET=$GITHUB_WEBHOOK_SECRET" >> .env.docker
    fi
    
    echo -e "${GREEN}✓ Config saved to .env.docker${NC}"
}

run_health_checks() {
    echo ""
    echo -e "${CYAN}Running startup health checks...${NC}"
    
    # Wait for services to start
    echo "  Waiting for container to initialize..."
    for i in {1..15}; do
        if curl -sf http://localhost:8002/api/health &>/dev/null; then
            break
        fi
        sleep 2
    done
    
    # Unified health check
    if curl -sf http://localhost:8002/api/health &>/dev/null; then
        echo -e "${GREEN}✓ DR.CODE Subsystem (8002): OK${NC}"
    else
        echo -e "${RED}✗ Health check failed - check logs with 'docker compose logs'${NC}"
    fi
}

print_summary() {
    echo ""
    echo -e "${GREEN}======================================"
    echo "  DR.CODE v2 - Deployment Summary"
    echo -e "======================================${NC}"
    echo ""
    echo "  Service Endpoints:"
    echo "    - DR.CODE Web UI & API: http://localhost:8002"
    echo "    - Ollama Daemon: $OLLAMA_BASE_URL (auto-detected)"
    echo "    - Recommended Model: ${OLLAMA_MODEL:-qwen2.5-coder:7b}"
    echo "  "
    echo "  GitHub Integration:"
    if [ -n "$GITHUB_TOKEN" ]; then
        echo "    - Token: ✅ Configured"
        if [ -n "$GITHUB_WEBHOOK_SECRET" ]; then
            echo "    - Webhook Secret: ✅ Configured"
        else
            echo "    - Webhook Secret: ⚠ Not configured (HMAC check disabled)"
        fi
    else
        echo "    - Token: ⚠ Not configured (webhooks won't analyze)"
    fi
    echo "  "
    echo "Commands:"
    echo "  docker compose up -d    # Start services"
    echo "  docker compose down     # Stop services"
    echo "  docker compose logs -f  # View activity"
    echo "  curl http://localhost:8002/api/health  # Health check"
    echo ""
}

# Main Execution
check_docker

# Try auto-detection first
if detect_all_deps; then
    SKIP_PROMPTS=true
else
    SKIP_PROMPTS=false
fi

if [ "$SKIP_PROMPTS" = false ]; then
    setup_ai
    setup_github
fi

save_config

echo ""
echo -e "${CYAN}Starting DR.CODE services...${NC}"

# Try 'docker compose' (modern) fallback to 'docker-compose' (legacy)
if docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

$COMPOSE_CMD up -d

# Run health checks
run_health_checks

print_summary
