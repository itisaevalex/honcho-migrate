
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
```

**One-stop shop for multi-agent memory systems on [Honcho](https://honcho.dev).**

Self-host Honcho, migrate data between instances, connect your agents (Claude Code, Hermes, custom), and share persistent memory across machines via Tailscale.

---

## Quick Start

### Self-host Honcho

```bash
git clone https://github.com/itisaevalex/honcho-migrate.git
cd honcho-migrate
bash setup.sh
```

### Migrate between instances

```bash
pip install requests

# Dry run
python3 migrate.py \
  --source http://localhost:8000 \
  --target https://api.honcho.dev \
  --target-key hch-v3-your-key \
  --dry-run

# Run it
python3 migrate.py \
  --source http://localhost:8000 \
  --target https://api.honcho.dev \
  --target-key hch-v3-your-key
```

### Set up a client machine (Tailscale)

```bash
bash client/install-client.sh
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
| Local → Remote | `python3 migrate.py --source http://localhost:8000 --target http://100.x.x.x:8000` |

## What Gets Migrated

| Data | Migrated | Rebuilt |
|------|----------|---------|
| Workspaces | Yes | -- |
| Peers | Yes | -- |
| Sessions | Yes | -- |
| Messages | Yes | -- |
| Peer observer config | Yes | -- |
| Observations/conclusions | -- | Deriver re-extracts |
| Peer cards / summaries | -- | Deriver rebuilds |
| Dream consolidations | -- | Trigger manually |

Messages are the source of truth. Everything else rebuilds from them.

## Guides

| Guide | What it covers |
|-------|---------------|
| [Self-Hosting](docs/self-hosting.md) | Docker setup, Ollama models, backup/restore, upgrading |
| [Multi-Workspace Architecture](docs/multi-workspace.md) | Workspace/peer/session design, domain scoping, cross-agent coordination |
| [Claude Code Integration](docs/claude-code.md) | Official plugin, MCP server, auto-workspace routing |
| [Hermes Integration](docs/hermes.md) | Profiles, memory modes, multi-user bots, cron-to-conversation bridge |
| [Tailscale Remote Access](docs/tailscale.md) | Multi-machine setup, client installer, security |
| [API Quirks](docs/api-quirks.md) | v3 API gotchas, port reference, curl examples |
| [Benchmarks](docs/benchmarks.md) | Local vs cloud comparison, LoCoMo results |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and fixes |

## Repo Structure

```
honcho-migrate/
├── migrate.py              # Migration script (any direction)
├── setup.sh                # One-command server setup
├── apply-patches.sh        # Apply custom embedding patches
├── configs/                # Server-side config templates
│   ├── env.example
│   └── docker-compose.yml.example
├── patches/                # Honcho source patches
│   └── custom-embeddings.patch
├── client/                 # Client-side workspace tooling
│   ├── install-client.sh   # One-command client setup
│   ├── auto-workspace.sh   # Bashrc workspace resolver
│   ├── claude-shim         # Binary wrapper for Claude Code
│   └── workspace-map.conf.example
├── templates/              # Agent config templates
│   ├── honcho-config.json  # ~/.honcho/config.json
│   └── hermes-honcho.json  # Hermes profile honcho.json
├── docs/                   # Detailed guides
│   ├── self-hosting.md
│   ├── multi-workspace.md
│   ├── claude-code.md
│   ├── hermes.md
│   ├── tailscale.md
│   ├── api-quirks.md
│   ├── benchmarks.md
│   └── troubleshooting.md
└── tests/
    └── test_migrate.py     # 17 migration tests
```

## License

MIT -- see [LICENSE](LICENSE).

This is a community tool for [Honcho](https://github.com/plastic-labs/honcho) by Plastic Labs. Honcho itself is AGPL-3.0 licensed. Patches in `patches/` are subject to Honcho's license when applied.
