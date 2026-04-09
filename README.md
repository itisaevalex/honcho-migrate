# honcho-migrate

```
 _                      _                          _                 _
| |__   ___  _ __   ___| |__   ___    _ __ ___   (_) __ _ _ __ __ _| |_ ___
| '_ \ / _ \| '_ \ / __| '_ \ / _ \  | '_ ` _ \  | |/ _` | '__/ _` | __/ _ \
| | | | (_) | | | | (__| | | | (_) | | | | | | | | | (_| | | | (_| | ||  __/
|_| |_|\___/|_| |_|\___|_| |_|\___/  |_| |_| |_| |_|\__, |_|  \__,_|\__\___|
                                                      |___/
```

**Migrate, backup, and self-host [Honcho](https://honcho.dev) memory across any instance.**

Move your AI agent memories between Honcho Cloud, self-hosted instances, and other machines. Zero lock-in.

---

## What is Honcho?

[Honcho](https://github.com/plastic-labs/honcho) is an open-source memory system for AI agents. It stores conversations, extracts observations about users, consolidates memories over time (via "dreams"), and lets agents recall context across sessions.

This tool lets you:

- **Migrate** between any two Honcho instances (cloud ↔ self-hosted ↔ self-hosted)
- **Self-host** Honcho with Ollama models (no OpenAI/Anthropic keys needed)
- **Backup** and restore your memory database
- **Upgrade** safely with patch management

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/honcho-migrate.git
cd honcho-migrate
pip install requests
```

### Migrate between instances

```bash
# See what would be migrated (dry run)
python3 migrate.py \
  --source http://localhost:8000 \
  --target https://api.honcho.dev \
  --target-key hch-v3-your-key \
  --dry-run

# Run the migration
python3 migrate.py \
  --source http://localhost:8000 \
  --target https://api.honcho.dev \
  --target-key hch-v3-your-key
```

### Self-host Honcho with Ollama

```bash
# One-command setup
bash setup.sh
```

## Migration Directions

```
                    ┌──────────────────┐
                    │   Honcho Cloud   │
                    │ api.honcho.dev   │
                    └───────┬──────────┘
                            │
              migrate.py    │    migrate.py
              --source ↑    │    ↓ --target
                            │
┌──────────────┐     ┌──────┴──────────┐     ┌──────────────┐
│  Machine A   │ ←──→│   migrate.py    │←──→ │  Machine B   │
│  Self-hosted │     │                 │     │  Self-hosted  │
│  :8000       │     │  Any direction  │     │  :8000        │
└──────────────┘     └─────────────────┘     └──────────────┘
```

| Direction | Command |
|-----------|---------|
| Local → Cloud | `python3 migrate.py --source http://localhost:8000 --target https://api.honcho.dev --target-key KEY` |
| Cloud → Local | `python3 migrate.py --source https://api.honcho.dev --source-key KEY --target http://localhost:8000` |
| Local → Remote (Tailscale) | `python3 migrate.py --source http://localhost:8000 --target http://100.x.x.x:8000` |
| Cloud → Cloud | `python3 migrate.py --source https://api.honcho.dev --source-key KEY1 --target https://api.honcho.dev --target-key KEY2` |

## What Gets Migrated

| Data | Migrated | Rebuilt |
|------|----------|---------|
| Workspaces | Yes | — |
| Peers | Yes | — |
| Sessions | Yes | — |
| Messages | Yes | — |
| Peer observer config | Yes | — |
| Observations/conclusions | — | Yes (deriver re-extracts) |
| Peer cards | — | Yes (deriver rebuilds) |
| Summaries | — | Yes (deriver rebuilds) |
| Dream consolidations | — | Trigger manually after migration |

Messages are the source of truth. Everything else rebuilds from them.

## Options

```
usage: migrate.py [-h] --target TARGET [--source SOURCE]
                  [--source-key KEY] [--target-key KEY]
                  [--dry-run] [--delay SECONDS]
                  [--workspace WS] [--batch-size N]

Options:
  --source URL        Source Honcho API (default: http://localhost:8000)
  --source-key KEY    Source API key (if auth enabled)
  --target URL        Target Honcho API (required)
  --target-key KEY    Target API key (if auth enabled)
  --dry-run           Show what would be migrated without doing it
  --delay SECONDS     Delay between API calls (default: 0.3 for cloud, 0 for local)
  --workspace WS      Migrate only this workspace (default: all)
  --batch-size N      Messages per batch (default: 20)
```

## Self-Hosting Guide

### Prerequisites

- Docker and Docker Compose
- Ollama (local or cloud subscription) for LLM inference
- ~2GB disk for the embedding model

### Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Docker Compose                      │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐ │
│  │ Honcho   │  │ Deriver  │  │ PostgreSQL         │ │
│  │ API      │  │ Worker   │  │ + pgvector         │ │
│  │ :8000    │  │          │  │ :5432              │ │
│  └────┬─────┘  └────┬─────┘  └────────────────────┘ │
│       │              │                                │
│       │         ┌────┴─────┐  ┌────────────────────┐ │
│       │         │ Ollama   │  │ Redis              │ │
│       │         │ Cloud    │  │ :6379              │ │
│       │         │ (LLMs)   │  │                    │ │
│       │         └──────────┘  └────────────────────┘ │
│       │                                              │
│  ┌────┴──────────────────────────────┐               │
│  │ Local Ollama (embedding: bge-m3)  │               │
│  │ :11434                            │               │
│  └───────────────────────────────────┘               │
└─────────────────────────────────────────────────────┘
```

### Setup

```bash
# Clone Honcho
git clone https://github.com/plastic-labs/honcho.git
cd honcho

# Copy our config
cp /path/to/honcho-migrate/configs/env.example .env
cp /path/to/honcho-migrate/configs/docker-compose.yml.example docker-compose.yml

# Edit .env with your Ollama API key
nano .env

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

### Model Configuration

The `.env` file controls which models Honcho uses. All models must support tool/function calling.

| Role | What it does | Recommended | Alternatives |
|------|-------------|-------------|--------------|
| Deriver | Extracts observations from messages | qwen3.5:397b | glm-5, minimax-m2.7 |
| Dialectic (low) | Quick memory recall | qwen3.5:397b | any tool-calling model |
| Dialectic (high) | Deep memory reasoning | minimax-m2.7 | glm-5.1 |
| Dreamer | Memory consolidation | minimax-m2.7 | glm-5.1 |
| Embeddings | Vector search | bge-m3 (local) | nomic-embed-text, qwen3-embedding |

**Avoid for tool calling:** Kimi K2.5 (broken template), Qwen3.5 local variants (template mismatch). Cloud variants work.

### Tailscale Remote Access

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Your Honcho is now at http://YOUR_TAILSCALE_IP:8000
tailscale ip -4
```

Bind the API to `0.0.0.0:8000` in docker-compose.yml (done by default in our config).

### Firewall Setup (UFW + Docker)

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

## Troubleshooting

### Deriver not processing messages

**Symptom:** Messages stored but queue stays pending, no observations extracted.

**Cause 1:** Stale queue claims from previous container.
```bash
docker compose exec database psql -U postgres -c "DELETE FROM active_queue_sessions;"
docker compose restart deriver
```

**Cause 2:** Batch threshold not met (default: 1024 tokens).
```bash
# Add to .env:
DERIVER_FLUSH_ENABLED=true
# Then restart:
docker compose restart deriver
```

### Embedding dimension mismatch

**Symptom:** `column cannot have more than 2000 dimensions for hnsw index` or vector insert errors.

**Cause:** The DB schema dimensions don't match the embedding model output.

- bge-m3: 1024 dims
- nomic-embed-text: 768 dims
- qwen3-embedding:8b: 4096 dims (too high for HNSW, needs truncation)

Set `VECTOR_STORE_DIMENSIONS` in `.env` to match your model, and use `HONCHO_FRESH_INSTALL=true` on first start.

### Docker can't reach local Ollama

**Symptom:** Embedding requests timeout from inside Docker containers.

**Fix:** See [Firewall Setup](#firewall-setup-ufw--docker) above.

### Redis port conflict

**Symptom:** `address already in use` on port 6379.

**Fix:** Remap Docker Redis to a different port in docker-compose.yml:
```yaml
redis:
  ports:
    - "127.0.0.1:6380:6379"
```

## License

MIT
