# Self-Hosting Guide

This guide walks through running your own Honcho instance with Ollama models, so you can keep all memory processing on your own infrastructure without needing OpenAI or Anthropic API keys.

## Prerequisites

- Docker and Docker Compose
- Ollama (local or cloud subscription) for LLM inference
- ~2GB disk for the embedding model

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Docker Compose                      │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐  │
│  │ Honcho   │  │ Deriver  │  │ PostgreSQL         │  │
│  │ API      │  │ Worker   │  │ + pgvector         │  │
│  │ :8000    │  │          │  │ :5432              │  │
│  └────┬─────┘  └─────┬────┘  └────────────────────┘  │
│       │              │                               │
│       │         ┌────┴─────┐  ┌────────────────────┐ │
│       │         │ Ollama   │  │ Redis              │ │
│       │         │ Cloud    │  │ :6379 (host: 6380) │ │
│       │         │ (LLMs)   │  │                    │ │
│       │         └──────────┘  └────────────────────┘ │
│       │                                              │
│  ┌────┴──────────────────────────────┐               │
│  │ Local Ollama (embedding: bge-m3)  │               │
│  │ :11434                            │               │
│  └───────────────────────────────────┘               │
└──────────────────────────────────────────────────────┘
```

## Setup

```bash
# Clone Honcho
git clone https://github.com/plastic-labs/honcho.git
cd honcho

# Copy our config
cp /path/to/honcho-migrate/configs/env.example .env
cp /path/to/honcho-migrate/configs/docker-compose.yml.example docker-compose.yml

# Edit .env with your Ollama API key
nano .env

# In .env — required for first-run schema creation:
HONCHO_FRESH_INSTALL=true
VECTOR_STORE_DIMENSIONS=1024

# After first successful start, set HONCHO_FRESH_INSTALL=false
# to prevent schema re-creation on subsequent restarts.

# Apply patches for custom embedding support
cd /path/to/honcho-migrate
bash apply-patches.sh /path/to/honcho

# Pull embedding model locally
ollama pull bge-m3

# Start everything
cd /path/to/honcho
docker compose up -d

# Verify
curl http://localhost:8000/health
```

## Model Configuration

The `.env` file controls which models Honcho uses. All models must support tool/function calling.

| Role | What it does | Recommended | Alternatives |
|------|-------------|-------------|--------------|
| Deriver | Extracts observations from messages | qwen3.5:397b | glm-5, minimax-m2.7 |
| Dialectic (low) | Quick memory recall | qwen3.5:397b | any tool-calling model |
| Dialectic (high) | Deep memory reasoning | minimax-m2.7 | glm-5.1 |
| Dreamer | Memory consolidation | minimax-m2.7 | glm-5.1 |
| Embeddings | Vector search | bge-m3 (local) | nomic-embed-text, qwen3-embedding |

**Avoid for tool calling:** Kimi K2.5 (broken template), Qwen3.5 local variants (template mismatch). Cloud variants work.

## Tailscale Remote Access

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Your Honcho is now at http://YOUR_TAILSCALE_IP:8000
tailscale ip -4
```

Bind the API to `0.0.0.0:8000` in docker-compose.yml (done by default in our config).

## Firewall Setup (UFW + Docker)

If using UFW, allow Docker containers to reach local Ollama:

```bash
sudo ufw allow from 172.17.0.0/16 to any port 11434 proto tcp
sudo ufw allow from 172.18.0.0/16 to any port 11434 proto tcp
```

Also ensure Ollama listens on all interfaces:

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d
echo -e '[Service]\nEnvironment="OLLAMA_HOST=0.0.0.0"' | \
  sudo tee /etc/systemd/system/ollama.service.d/override.conf
sudo systemctl daemon-reload && sudo systemctl restart ollama
```

## Backup & Restore

```bash
# Backup (run from honcho directory)
docker compose exec -T database pg_dump -U postgres --clean --if-exists > backup.sql

# Restore
docker compose stop api deriver
docker compose exec -T database psql -U postgres < backup.sql
docker compose exec -T database psql -U postgres -c "DELETE FROM active_queue_sessions;"
docker compose start api deriver
```

Set up daily automated backups:

```bash
# Add to crontab
crontab -e
# Add: 0 3 * * * cd /path/to/honcho && docker compose exec -T database pg_dump -U postgres > /path/to/backups/honcho-$(date +\%F).sql
```

## Upgrading Honcho

```bash
cd /path/to/honcho

# Save your patches
git diff HEAD > ~/honcho-patches.diff
git stash

# Pull latest
git pull origin main

# Re-apply patches
git stash pop  # resolve conflicts if any

# Rebuild
docker compose up -d --build
```
