# Claude Code Integration

Three ways to connect Claude Code to your Honcho instance, from simplest to most powerful.

## Approach 1: Official Plugin (plastic-labs/claude-honcho)

The plugin reads `~/.honcho/config.json` and automatically injects Honcho memory into Claude Code sessions. No MCP setup required.

### Install

```bash
# Install the plugin (check plastic-labs/claude-honcho for latest instructions)
claude plugin install plastic-labs/claude-honcho
```

### Configure

Create `~/.honcho/config.json`:

```json
{
  "apiKey": "not-required-for-self-hosted",
  "peerName": "alex",
  "endpoint": {
    "baseUrl": "http://localhost:8000/v3"
  },
  "sessionStrategy": "per-directory",
  "enabled": true,
  "hosts": {
    "claude_code": {
      "workspace": "my-project"
    }
  }
}
```

| Field | Purpose |
|-------|---------|
| `apiKey` | Required for Honcho Cloud. For self-hosted, any non-empty string works. |
| `peerName` | Your identity in the workspace. Honcho builds a profile of this peer over time. |
| `endpoint.baseUrl` | Your Honcho API. Use `http://localhost:8000/v3` for local, or your Tailscale IP for remote. |
| `sessionStrategy` | `per-directory` creates one session per project directory. Other options: `single`, `per-branch`. |
| `hosts.claude_code.workspace` | Which Honcho workspace to use when running inside Claude Code. |

### Tailscale / Remote

If Honcho runs on another machine:

```json
{
  "endpoint": {
    "baseUrl": "http://100.100.223.89:8000/v3"
  }
}
```

### Verify

```bash
# Check Honcho is reachable from where Claude Code runs
curl http://localhost:8000/health
```

The plugin handles session creation, message logging, and memory injection transparently. You just use Claude Code normally.

---

## Approach 2: Auto-Workspace Routing

The plugin uses whatever workspace is in config.json. If you work across multiple projects, you need the workspace to change automatically.

Two options: a bashrc function (simpler) or a binary shim (works everywhere).

### Option A: Bashrc Function

Add to `~/.bashrc`:

```bash
claude() {
  local dir="$(pwd)"
  local workspace="default"
  local config_file="$HOME/.honcho/config.json"
  local map_file="$HOME/.honcho/workspace-map.conf"

  # Read workspace-map.conf and find first matching pattern
  if [[ -f "$map_file" ]]; then
    while IFS='=' read -r pattern ws; do
      # Skip comments and blank lines
      [[ "$pattern" =~ ^[[:space:]]*# ]] && continue
      [[ -z "$pattern" ]] && continue
      # Trim whitespace
      pattern="$(echo "$pattern" | xargs)"
      ws="$(echo "$ws" | xargs)"
      if [[ "$dir" == $pattern ]]; then
        workspace="$ws"
        break
      fi
    done < "$map_file"
  fi

  # Patch config.json with the resolved workspace
  if command -v jq &>/dev/null && [[ -f "$config_file" ]]; then
    local tmp
    tmp=$(jq --arg ws "$workspace" '.hosts.claude_code.workspace = $ws' "$config_file")
    echo "$tmp" > "$config_file"
  fi

  # Launch the real claude binary
  command claude "$@"
}
```

### Workspace Map

Create `~/.honcho/workspace-map.conf`:

```conf
# pattern = workspace
# Patterns use bash glob syntax (matched against $PWD)

/home/alex/Documents/LocalHermes*    = localhermes
/home/alex/Documents/honcho*         = honcho-dev
/home/alex/projects/sales-agent*     = sales-agent
/home/alex/projects/website*         = website
*                                    = default
```

First match wins. The `*` at the end is the fallback.

### Option B: Binary Shim

The bashrc function only works when you launch `claude` from a terminal. If Claude Code is launched by an editor, a desktop shortcut, or another tool, the function never runs.

A binary shim fixes this by sitting in your PATH before the real `claude` binary.

Place in `~/bin/claude` (or anywhere earlier in PATH than the real binary):

```bash
#!/usr/bin/env bash
set -euo pipefail

REAL_CLAUDE="/usr/local/bin/claude"  # adjust to your actual claude binary location
CONFIG="$HOME/.honcho/config.json"
MAP="$HOME/.honcho/workspace-map.conf"

dir="$(pwd)"
workspace="default"

if [[ -f "$MAP" ]]; then
  while IFS='=' read -r pattern ws; do
    [[ "$pattern" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$pattern" ]] && continue
    pattern="$(echo "$pattern" | xargs)"
    ws="$(echo "$ws" | xargs)"
    if [[ "$dir" == $pattern ]]; then
      workspace="$ws"
      break
    fi
  done < "$MAP"
fi

if command -v jq &>/dev/null && [[ -f "$CONFIG" ]]; then
  tmp=$(jq --arg ws "$workspace" '.hosts.claude_code.workspace = $ws' "$CONFIG")
  echo "$tmp" > "$CONFIG"
fi

exec "$REAL_CLAUDE" "$@"
```

```bash
chmod +x ~/bin/claude
```

Make sure `~/bin` comes before the real claude location in your PATH:

```bash
export PATH="$HOME/bin:$PATH"
```

### Which to use

| Scenario | Recommendation |
|----------|----------------|
| Always launch claude from terminal | Bashrc function |
| Launch from VS Code, editors, scripts | Binary shim |
| Both | Binary shim (covers all cases) |

---

## Approach 3: MCP Server (Full Tool Surface)

The plugin gives you transparent memory. The MCP server gives you the full Honcho API as Claude Code tools: inspect workspaces, search messages, query conclusions, create peers, schedule dreams, and more.

Use this when you want Claude Code to actively reason about and manipulate Honcho data, not just passively benefit from memory injection.

### Start the MCP Server

```bash
cd ~/Documents/honcho/mcp
bun install
bun run dev  # starts wrangler dev on port 8787
```

This runs the Honcho MCP bridge locally at `http://localhost:8787`.

### Register with Claude Code

Add a per-workspace MCP entry:

```bash
claude mcp add \
  --transport stdio \
  honcho-myproject \
  -- bunx mcp-remote \
  http://localhost:8787 \
  --header "Authorization:Bearer local" \
  --header "X-Honcho-Base-URL:http://localhost:8000" \
  --header "X-Honcho-Workspace-ID:my-project" \
  --header "X-Honcho-User-Name:alex"
```

Replace `my-project` with your workspace name. Repeat for each workspace:

```bash
claude mcp add --transport stdio honcho-sales \
  -- bunx mcp-remote http://localhost:8787 \
  --header "Authorization:Bearer local" \
  --header "X-Honcho-Base-URL:http://localhost:8000" \
  --header "X-Honcho-Workspace-ID:sales-agent" \
  --header "X-Honcho-User-Name:alex"

claude mcp add --transport stdio honcho-website \
  -- bunx mcp-remote http://localhost:8787 \
  --header "Authorization:Bearer local" \
  --header "X-Honcho-Base-URL:http://localhost:8000" \
  --header "X-Honcho-Workspace-ID:website" \
  --header "X-Honcho-User-Name:alex"
```

### Available Tools

Once registered, Claude Code gets these tools:

| Tool | What it does |
|------|-------------|
| `inspect_workspace` | Overview: peers, sessions, metadata, config |
| `list_workspaces` | Discover all accessible workspaces |
| `search` | Semantic search across messages (workspace/peer/session scope) |
| `get_metadata` / `set_metadata` | Read/write metadata on workspaces, peers, or sessions |
| `create_peer` | Register a new participant (user or agent) |
| `list_peers` | List all peers in the workspace |
| `chat` | Ask Honcho a natural-language question about a peer |
| `get_peer_card` / `set_peer_card` | Read/write biographical facts about a peer |
| `get_peer_context` | Full picture: representation + peer card combined |
| `get_representation` | Text summary built from a peer's conclusions |
| `create_session` / `list_sessions` / `delete_session` | Session CRUD |
| `clone_session` | Fork a conversation at any message |
| `inspect_session` | Session overview: peers, message count, summaries |
| `add_messages_to_session` / `get_session_messages` / `get_session_message` | Message operations |
| `get_session_context` | Optimized context window for LLM prompts |
| `add_peers_to_session` / `remove_peers_from_session` / `get_session_peers` | Session membership |
| `list_conclusions` / `query_conclusions` | Read derived facts (list or semantic search) |
| `create_conclusions` / `delete_conclusion` | Manually inject or remove knowledge |
| `schedule_dream` | Trigger memory consolidation |
| `get_queue_status` | Check if the deriver is still processing |

### Example: Claude Code querying memory

After registering the MCP, you can ask Claude Code things like:

> "What does Honcho know about the user alex in the sales-agent workspace?"

Claude Code will call `chat` or `get_peer_context` to answer.

> "Search for any conversations about the Acme Corp deal."

Claude Code will call `search` with your query.

> "Schedule a dream to consolidate what you've learned about me."

Claude Code will call `schedule_dream`.

---

## Port Clarity

Two services, two ports. Do not confuse them.

```
Claude Code  -->  MCP bridge (8787)  -->  Honcho API (8000)  -->  PostgreSQL
                                              ^
Plugin (Approach 1/2)  -->  config.json  -->  Honcho API (8000) directly
```

| Port | Service | What lives there |
|------|---------|-----------------|
| 8000 | Honcho API | The actual memory system. REST API, PostgreSQL, deriver worker. |
| 8787 | MCP bridge | A thin adapter that translates MCP tool calls into Honcho API requests. |

- The **plugin** (Approaches 1 and 2) talks to port 8000 directly. No MCP involved.
- The **MCP server** (Approach 3) runs on port 8787 and proxies to port 8000. Claude Code talks to 8787; it never hits 8000 directly.
- You can use Approach 1 and Approach 3 simultaneously. The plugin provides passive memory; the MCP gives active tools.

### Remote setup

If Honcho runs on a different machine (e.g., via Tailscale):

```bash
# Plugin config
"baseUrl": "http://100.100.223.89:8000/v3"

# MCP registration (MCP bridge still runs locally, points to remote Honcho)
--header "X-Honcho-Base-URL:http://100.100.223.89:8000"
```

The MCP bridge always runs locally alongside Claude Code. Only the Honcho API can be remote.

---

## Combining Approaches

| Setup | What you get |
|-------|-------------|
| Plugin only | Transparent memory. Claude Code automatically remembers past sessions. |
| Plugin + workspace routing | Same, but workspace switches automatically per project directory. |
| Plugin + MCP | Transparent memory plus active tools for querying, searching, and managing Honcho data. |
| MCP only | Full tools but no automatic memory injection. You must explicitly ask Claude Code to use Honcho. |

Recommended: start with Approach 1. Add Approach 2 when you have 3+ projects. Add Approach 3 when you need Claude Code to actively inspect or manipulate memory.
