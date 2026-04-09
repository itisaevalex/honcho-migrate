#!/bin/bash
# honcho-migrate: One-command self-hosted Honcho setup
#
# Prerequisites:
#   - Docker and Docker Compose
#   - Ollama installed (local or cloud)
#   - An Ollama API key (if using Ollama Cloud)
#
# Usage:
#   bash setup.sh
#   OLLAMA_API_KEY=your-key bash setup.sh
#   HONCHO_DIR=~/my-honcho bash setup.sh

set -e

# Configurable
HONCHO_DIR="${HONCHO_DIR:-$HOME/Documents/honcho}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-bge-m3}"

echo ""
echo "  _                      _           "
echo " | |__   ___  _ __   ___| |__   ___  "
echo " | '_ \ / _ \| '_ \ / __| '_ \ / _ \ "
echo " | | | | (_) | | | | (__| | | | (_) |"
echo " |_| |_|\___/|_| |_|\___|_| |_|\___/ "
echo ""
echo "  Self-Hosted Honcho Setup"
echo ""

# Step 1: Check prerequisites
echo "[1/7] Checking prerequisites..."

if ! command -v docker &>/dev/null; then
  echo "  Docker not found. Install it:"
  echo "    sudo apt-get install -y docker.io docker-compose-v2"
  exit 1
fi
echo "  Docker: $(docker --version | head -1)"

if ! command -v ollama &>/dev/null; then
  echo "  Ollama not found. Install it:"
  echo "    curl -fsSL https://ollama.com/install.sh | sh"
  exit 1
fi
echo "  Ollama: $(ollama --version 2>&1 || echo 'installed')"

# Step 2: Clone Honcho
echo ""
echo "[2/7] Setting up Honcho repo..."
if [ -d "$HONCHO_DIR/.git" ]; then
  echo "  Honcho repo already exists at $HONCHO_DIR"
else
  echo "  Cloning Honcho..."
  git clone https://github.com/plastic-labs/honcho.git "$HONCHO_DIR"
fi

# Step 3: Apply patches
echo ""
echo "[3/7] Applying patches for custom embedding support..."
bash "$SCRIPT_DIR/apply-patches.sh" "$HONCHO_DIR"

# Step 4: Configure
echo ""
echo "[4/7] Configuring..."

if [ ! -f "$HONCHO_DIR/.env" ]; then
  cp "$SCRIPT_DIR/configs/env.example" "$HONCHO_DIR/.env"
  echo "  Created .env from template"

  # Prompt for Ollama API key if not set
  if [ -z "$OLLAMA_API_KEY" ]; then
    echo ""
    echo "  Enter your Ollama Cloud API key (or press Enter to skip):"
    echo "  (Get one at https://ollama.com/settings/keys)"
    read -r OLLAMA_API_KEY
  fi

  if [ -n "$OLLAMA_API_KEY" ]; then
    sed -i "s|LLM_OPENAI_COMPATIBLE_API_KEY=.*|LLM_OPENAI_COMPATIBLE_API_KEY=$OLLAMA_API_KEY|" "$HONCHO_DIR/.env"
    echo "  API key configured"
  else
    echo "  Warning: No API key set. Edit $HONCHO_DIR/.env before starting."
  fi
else
  echo "  .env already exists, keeping current config"
fi

if [ ! -f "$HONCHO_DIR/docker-compose.yml" ]; then
  cp "$SCRIPT_DIR/configs/docker-compose.yml.example" "$HONCHO_DIR/docker-compose.yml"
  echo "  Created docker-compose.yml from template"
else
  echo "  docker-compose.yml already exists, keeping current config"
fi

# Step 5: Pull embedding model
echo ""
echo "[5/7] Pulling embedding model ($EMBEDDING_MODEL)..."
if ollama list 2>/dev/null | grep -q "$EMBEDDING_MODEL"; then
  echo "  $EMBEDDING_MODEL already pulled"
else
  ollama pull "$EMBEDDING_MODEL"
fi

# Step 6: Ensure Ollama is accessible from Docker
echo ""
echo "[6/7] Configuring Ollama for Docker access..."

# Check if Ollama listens on 0.0.0.0
if ss -tlnp 2>/dev/null | grep ":11434" | grep -q "0.0.0.0\|\*"; then
  echo "  Ollama already listening on all interfaces"
else
  echo "  Configuring Ollama to listen on 0.0.0.0..."
  sudo mkdir -p /etc/systemd/system/ollama.service.d
  echo -e '[Service]\nEnvironment="OLLAMA_HOST=0.0.0.0"' | \
    sudo tee /etc/systemd/system/ollama.service.d/override.conf >/dev/null
  sudo systemctl daemon-reload
  sudo systemctl restart ollama
  echo "  Done"
fi

# Add UFW rules if UFW is active
if sudo ufw status 2>/dev/null | grep -q "Status: active"; then
  echo "  Adding UFW rules for Docker → Ollama..."
  sudo ufw allow from 172.17.0.0/16 to any port 11434 proto tcp 2>/dev/null || true
  sudo ufw allow from 172.18.0.0/16 to any port 11434 proto tcp 2>/dev/null || true
fi

# Step 7: Start Honcho
echo ""
echo "[7/7] Starting Honcho..."
cd "$HONCHO_DIR"
docker compose up -d --build 2>&1 | tail -5

echo ""
echo "Waiting for API to start..."
for i in $(seq 1 30); do
  if curl -s http://localhost:8000/health >/dev/null 2>&1; then
    echo ""
    echo "============================================"
    echo "  Honcho is running!"
    echo ""
    echo "  API:       http://localhost:8000"
    echo "  Health:    http://localhost:8000/health"
    echo "  Docs:      http://localhost:8000/docs"
    echo ""
    echo "  Test it:"
    echo "    curl http://localhost:8000/health"
    echo ""
    echo "  Migrate data from cloud:"
    echo "    python3 $SCRIPT_DIR/migrate.py \\"
    echo "      --source https://api.honcho.dev \\"
    echo "      --source-key hch-v3-your-key \\"
    echo "      --target http://localhost:8000"
    echo "============================================"
    exit 0
  fi
  sleep 2
done

echo ""
echo "Warning: API didn't respond within 60s."
echo "Check logs: cd $HONCHO_DIR && docker compose logs"
