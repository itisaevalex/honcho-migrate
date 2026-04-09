
```
 ██╗  ██╗ ██████╗ ███╗   ██╗ ██████╗██╗  ██╗ ██████╗
 ██║  ██║██╔═══██╗████╗  ██║██╔════╝██║  ██║██╔═══██╗
 ███████║██║   ██║██╔██╗ ██║██║     ███████║██║   ██║
 ██╔══██║██║   ██║██║╚██╗██║██║     ██╔══██║██║   ██║
 ██║  ██║╚██████╔╝██║ ╚████║╚██████╗██║  ██║╚██████╔╝
 ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝ ╚═════╝
 ███╗   ███╗██╗ ██████╗ ██████╗  █████╗ ████████╗███████╗
 ████╗ ████║██║██╔════╝ ██╔══██╗██╔══██╗╚══██╔══╝██╔════╝
 ██╔████╔██║██║██║  ███╗██████╔╝███████║   ██║   █████╗
 ██║╚██╔╝██║██║██║   ██║██╔══██╗██╔══██║   ██║   ██╔══╝
 ██║ ╚═╝ ██║██║╚██████╔╝██║  ██║██║  ██║   ██║   ███████╗
 ╚═╝     ╚═╝╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚══════╝

        ┌───────────┐              ┌───────────┐
        │  Cloud    │ ◄──────────► │  Local    │
        │  Honcho   │  migrate.py  │  Honcho   │
        └───────────┘   any dir    └───────────┘
```

**Migrate, backup, and self-host [Honcho](https://honcho.dev) memory across any instance.**

Move your AI agent memories between Honcho Cloud, self-hosted instances, and other machines. Your memories, your infrastructure, zero lock-in.

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
git clone https://github.com/itisaevalex/honcho-migrate.git
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
│  Self-hosted │     │                 │     │  Self-hosted │
│  :8000       │     │  Any direction  │     │  :8000       │
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
│       │         │ Cloud    │  │ :6379              │ │
│       │         │ (LLMs)   │  │                    │ │
│       │         └──────────┘  └────────────────────┘ │
│       │                                              │
│  ┌────┴──────────────────────────────┐               │
│  │ Local Ollama (embedding: bge-m3)  │               │
│  │ :11434                            │               │
│  └───────────────────────────────────┘               │
└──────────────────────────────────────────────────────┘
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

## Benchmarks

We benchmarked the self-hosted setup against Honcho Cloud (`api.honcho.dev`) to verify memory quality is equivalent.

### Smoke Test (Custom — 5 Phases)

Tests memory ingestion, deriver processing, dialectic recall, semantic search, and cross-session persistence using 10 diverse conversations.

```
Phase 1  Memory Ingestion     10/10 (100%)
Phase 2  Deriver Processing   10/10 (100%)
Phase 3  Memory Recall        10/10 (100%)
Phase 4  Search Accuracy       8/8  (100%)
Phase 5  Cross-session         5/5  (100%)
──────────────────────────────────────────
Total                         43/43 (100%)
```

We also ran this against Honcho Cloud (84%) but the comparison was unfair — cloud scores were lower due to API rate limiting dropping a conversation and the shared deriver not finishing before we queried. The LoCoMo benchmark below gives a fair head-to-head with proper deriver wait times.

### LoCoMo Academic Benchmark

[LoCoMo](https://github.com/snap-research/locomo) evaluates long-term conversational memory across multi-session dialogues (~300 turns, 19 sessions per conversation). Both instances had **full deriver processing + dream consolidation** before evaluation — a fair comparison.

```
                              Local           Cloud
Single-hop (direct recall)    3.0/5  (60%)    4.0/5  (80%)
Multi-hop  (cross-fact)       0.0/8   (0%)    0.0/8   (0%)
Temporal   (time-based)       0.0/1   (0%)    0.0/1   (0%)
Open-domain (commonsense)     1.5/2  (75%)    1.0/2  (50%)
─────────────────────────────────────────────────────
Total                         4.5/16 (28%)    5.0/16 (31%)
```

**Essentially a draw.** Both share the same weakness on temporal/multi-hop questions — Honcho extracts semantic observations ("user is vegetarian"), not timestamped event logs ("user said X on May 7"). This is by design; Honcho is built for understanding people, not timeline reconstruction.

### Model Stack Comparison

| Role | Self-hosted (Ollama) | Cloud (Honcho managed) |
|------|---------------------|----------------------|
| Deriver | qwen3.5:397b | Gemini 2.5 Flash Lite |
| Dialectic (low) | qwen3.5:397b | Gemini 2.5 Flash Lite |
| Dialectic (high) | minimax-m2.7 | Claude Haiku 4.5 |
| Dreamer | minimax-m2.7 | Claude Sonnet 4 |
| Embeddings | bge-m3 (1024d, local) | text-embedding-3-small (1536d) |

Open-weight models via Ollama Cloud match proprietary models on memory quality.

### Migration Test Suite

17 automated tests covering dry run, basic migration, edge cases (unicode, HTML injection, 3000-char messages), empty workspaces, workspace filtering, and idempotency. All passing.

```bash
python3 tests/test_migrate.py
# Results: 17/17 passed
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

MIT - see [LICENSE](LICENSE).

This is a community tool for [Honcho](https://github.com/plastic-labs/honcho) by Plastic Labs. Honcho itself is AGPL-3.0 licensed. The patches in `patches/` are modifications to Honcho source and are subject to Honcho's license when applied.
