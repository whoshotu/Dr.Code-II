#!/bin/bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# --- Port Detection ---
is_port_in_use() {
    local port=$1
    (echo >/dev/tcp/localhost/"$port") &>/dev/null
    return $?
}

find_next_open_port() {
    local start_port=$1
    local port=$start_port
    while is_port_in_use "$port"; do
        echo -e "${YELLOW}Port $port is occupied, trying $((port + 1))...${NC}"
        port=$((port + 1))
        if [ "$port" -gt $((start_port + 20)) ]; then
            echo -e "${RED}Error: Could not find an open port after 20 attempts.${NC}"
            exit 1
        fi
    done
    echo "$port"
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

detect_ollama() {
    if command -v ollama &> /dev/null; then
        if ! curl -sf http://localhost:11434/api/tags &>/dev/null; then
            echo -e "${YELLOW}Ollama CLI found but server not responding.${NC}"
            read -p "Would you like to try starting the local Ollama server? [y/N]: " start_ollama
            if [[ "$start_ollama" =~ ^[Yy]$ ]]; then
                ollama serve >/dev/null 2>&1 &
                sleep 3
            fi
        fi
        
        if curl -sf http://localhost:11434/api/tags &>/dev/null; then
            OLLAMA_BASE_URL="http://localhost:11434"
            echo -e "${GREEN}✓ Ollama is running locally on localhost:11434${NC}"
            return 0
        fi
    fi
    return 1
}

setup_ports() {
    echo ""
    echo -e "${CYAN}Step 1: Network Configuration${NC}"
    echo "Scanning for available ports..."
    BACKEND_PORT=$(find_next_open_port ${BACKEND_PORT:-8002})
    FRONTEND_PORT=$(find_next_open_port ${FRONTEND_PORT:-3001})
    echo -e "${GREEN}✓ Backend assigned to port: $BACKEND_PORT${NC}"
    echo -e "${GREEN}✓ Frontend assigned to port: $FRONTEND_PORT${NC}"
}

setup_ai() {
    echo ""
    echo -e "${CYAN}Step 2: AI Provider Configuration${NC}"
    echo "Current settings: Provider=${ACTIVE_PROVIDER:-ollama}, Model=${AI_MODEL_NAME:-$OLLAMA_MODEL}"
    echo "1) Local Ollama (Privacy-first, requires local GPU/CPU)"
    echo "2) Hosted Provider (OpenAI, Gemini, Anthropic)"
    read -p "Choose AI infrastructure [${USE_OLLAMA_CHOICE:-1}]: " ai_choice
    ai_choice=${ai_choice:-${USE_OLLAMA_CHOICE:-1}}

    if [ "$ai_choice" = "1" ]; then
        USE_OLLAMA=true
        if detect_ollama; then
            echo -e "${GREEN}Available Ollama models:${NC}"
            ollama list | tail -n +2 || echo "None found."
            read -p "Enter model name [${OLLAMA_MODEL:-(leave blank if unknown)}]: " USER_OLLAMA_MODEL
            OLLAMA_MODEL=${USER_OLLAMA_MODEL:-$OLLAMA_MODEL}
            OLLAMA_BASE_URL="http://localhost:11434"
        else
            echo -e "${YELLOW}⚠ Ollama not detected. Please install it from https://ollama.com${NC}"
            read -p "Proceed anyway with default settings? [y/N]: " proceed
            if [[ ! "$proceed" =~ ^[Yy]$ ]]; then exit 1; fi
            OLLAMA_BASE_URL="http://localhost:11434"
            OLLAMA_MODEL=""
        fi
    else
        USE_OLLAMA=false
        echo "Select Hosted Provider:"
        echo "  1) OpenAI"
        echo "  2) Gemini"
        echo "  3) Anthropic"
        read -p "Choose [${HOSTED_CHOICE:-1}]: " provider_choice
        provider_choice=${provider_choice:-${HOSTED_CHOICE:-1}}
        
        case $provider_choice in
            1) ACTIVE_PROVIDER="openai"; DEFAULT_MODEL="gpt-4o" ;;
            2) ACTIVE_PROVIDER="gemini"; DEFAULT_MODEL="gemini-1.5-pro" ;;
            3) ACTIVE_PROVIDER="anthropic"; DEFAULT_MODEL="claude-3-5-sonnet-20240620" ;;
        esac
        
        # Load existing API key if available
        EXISTING_KEY_VAR="${ACTIVE_PROVIDER^^}_API_KEY"
        read -p "Enter API Key for $ACTIVE_PROVIDER [${!EXISTING_KEY_VAR:-(Keep Existing)}]: " PROVIDER_API_KEY
        PROVIDER_API_KEY=${PROVIDER_API_KEY:-${!EXISTING_KEY_VAR}}
        
        read -p "Enter model name [${AI_MODEL_NAME:-$DEFAULT_MODEL}]: " AI_MODEL_NAME
        AI_MODEL_NAME=${AI_MODEL_NAME:-${AI_MODEL_NAME:-$DEFAULT_MODEL}}
    fi
}

setup_github() {
    echo ""
    echo -e "${CYAN}Step 3: GitHub Integration (Optional)${NC}"
    
    read -p "GitHub Token [${GITHUB_TOKEN:-(Enter to skip)}]: " GITHUB_TOKEN
    GITHUB_TOKEN=${GITHUB_TOKEN:-$GITHUB_TOKEN}
    if [ -n "$GITHUB_TOKEN" ]; then
        read -p "Webhook Secret [${GITHUB_WEBHOOK_SECRET:-(Required if token provided)}]: " GITHUB_WEBHOOK_SECRET
        GITHUB_WEBHOOK_SECRET=${GITHUB_WEBHOOK_SECRET:-$GITHUB_WEBHOOK_SECRET}
    fi
}

save_config() {
    echo ""
    echo -e "${CYAN}Saving configuration...${NC}"
    
    # Core .env
    cat > .env << EOF
# Dr.Code-II Environment
BACKEND_PORT=$BACKEND_PORT
FRONTEND_PORT=$FRONTEND_PORT
REACT_APP_BACKEND_URL=http://localhost:$BACKEND_PORT
CORS_ORIGINS=http://localhost:$FRONTEND_PORT
DB_TYPE=sqlite
EOF

    if [ "$USE_OLLAMA" = true ]; then
        echo "OLLAMA_BASE_URL=$OLLAMA_BASE_URL" >> .env
        echo "OLLAMA_MODEL=$OLLAMA_MODEL" >> .env
    else
        echo "ACTIVE_PROVIDER=$ACTIVE_PROVIDER" >> .env
        echo "${ACTIVE_PROVIDER^^}_API_KEY=$PROVIDER_API_KEY" >> .env
        echo "AI_MODEL_NAME=$AI_MODEL_NAME" >> .env
    fi

    [ -n "$GITHUB_TOKEN" ] && echo "GITHUB_TOKEN=$GITHUB_TOKEN" >> .env
    [ -n "$GITHUB_WEBHOOK_SECRET" ] && echo "GITHUB_WEBHOOK_SECRET=$GITHUB_WEBHOOK_SECRET" >> .env

    # .env.docker
    cat > .env.docker << EOF
# Dr.Code-II Environment (Docker)
BACKEND_PORT=$BACKEND_PORT
FRONTEND_PORT=$FRONTEND_PORT
REACT_APP_BACKEND_URL=http://localhost:$BACKEND_PORT
CORS_ORIGINS=http://localhost:$FRONTEND_PORT
DB_TYPE=sqlite
EOF

    if [ "$USE_OLLAMA" = true ]; then
        echo "OLLAMA_BASE_URL=http://host.docker.internal:11434" >> .env.docker
        echo "OLLAMA_MODEL=$OLLAMA_MODEL" >> .env.docker
    else
        echo "ACTIVE_PROVIDER=$ACTIVE_PROVIDER" >> .env.docker
        echo "${ACTIVE_PROVIDER^^}_API_KEY=$PROVIDER_API_KEY" >> .env.docker
        echo "AI_MODEL_NAME=$AI_MODEL_NAME" >> .env.docker
    fi
    
    [ -n "$GITHUB_TOKEN" ] && echo "GITHUB_TOKEN=$GITHUB_TOKEN" >> .env.docker
    [ -n "$GITHUB_WEBHOOK_SECRET" ] && echo "GITHUB_WEBHOOK_SECRET=$GITHUB_WEBHOOK_SECRET" >> .env.docker
    
    echo -e "${GREEN}✓ Config saved to .env and .env.docker${NC}"
}

start_services() {
    echo ""
    echo -e "${CYAN}Starting DR.CODE services...${NC}"
    if docker compose version &>/dev/null; then COMPOSE_CMD="docker compose"; else COMPOSE_CMD="docker-compose"; fi
    
    if [ "$USE_OLLAMA" = true ]; then
        echo "Starting local Ollama container..."
        $COMPOSE_CMD up -d ollama
    fi
    
    $COMPOSE_CMD up -d backend frontend
}

run_health_checks() {
    echo ""
    echo -e "${CYAN}Running startup health checks...${NC}"
    echo "  Waiting for container to initialize on port ${BACKEND_PORT}..."
    for i in {1..15}; do
        if curl -sf http://localhost:${BACKEND_PORT}/api/health &>/dev/null; then break; fi
        sleep 2
    done
    if curl -sf http://localhost:${BACKEND_PORT}/api/health &>/dev/null; then
        echo -e "${GREEN}✓ DR.CODE Subsystem (${BACKEND_PORT}): OK${NC}"
    else
        echo -e "${RED}✗ Health check failed${NC}"
    fi
}

print_summary() {
    echo ""
    echo -e "${GREEN}======================================"
    echo "  DR.CODE v2 - Deployment Summary"
    echo -e "======================================${NC}"
    echo ""
    echo "  Service Endpoints:"
    echo "    - API/Backend: http://localhost:${BACKEND_PORT}"
    echo "    - Web UI (Expected): http://localhost:${FRONTEND_PORT}"
    [ "$USE_OLLAMA" = true ] && echo "    - Provider: Ollama ($OLLAMA_MODEL)" || echo "    - Provider: $ACTIVE_PROVIDER ($AI_MODEL_NAME)"
    echo ""
}

full_setup() {
    check_docker
    setup_ports
    setup_ai
    setup_github
    save_config
    start_services
    run_health_checks
    print_summary
}

echo -e "${CYAN}======================================"
echo "  DR.CODE v2 - Advanced Orchestration"
echo -e "======================================${NC}"
echo "1) Fresh setup"
echo "2) Re-run setup (keep existing config)"
echo "3) Reset config and re-setup"
read -p "Choose [1]: " choice
choice=${choice:-1}

case $choice in
    1)
        full_setup
        ;;
    2)
        if [ -f .env ]; then
            echo -e "${YELLOW}Loading existing configuration...${NC}"
            # Export to make them available in functions
            set -a; source .env; set +a
            [ -n "$OLLAMA_BASE_URL" ] && USE_OLLAMA_CHOICE=1 || USE_OLLAMA_CHOICE=2
            case "$ACTIVE_PROVIDER" in
                openai) HOSTED_CHOICE=1 ;;
                gemini) HOSTED_CHOICE=2 ;;
                anthropic) HOSTED_CHOICE=3 ;;
            esac
        fi
        full_setup
        ;;
    3)
        echo -e "${RED}Resetting configuration...${NC}"
        rm -f .env .env.docker
        full_setup
        ;;
    *)
        echo "Invalid choice."
        exit 1
        ;;
esac
