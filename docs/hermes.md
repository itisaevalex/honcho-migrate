# Hermes Agent Integration

How to connect [Hermes](https://github.com/NousResearch/hermes-agent) agents to Honcho for persistent memory across conversations, platforms, and users.

## What is Hermes

Hermes is a multi-platform AI agent framework. One agent definition can run on Telegram, Discord, CLI, HTTP, and other surfaces. Each agent lives in a **profile** — a directory containing its configuration, personality (SOUL.md), and tool settings.

Honcho gives Hermes agents memory that persists across sessions, platforms, and restarts. Without Honcho, every conversation starts from zero.

## Creating a Hermes Profile

```bash
# Using the hermes CLI
hermes profile create mybot

# Or manually
mkdir -p ~/.hermes/profiles/mybot/
```

This creates:

```
~/.hermes/profiles/mybot/
├── config.yaml        # Main agent config
├── SOUL.md            # Personality and instructions
├── honcho.json        # Honcho memory config (you create this)
└── tools/             # Custom tools directory
```

## Honcho Configuration

Create `~/.hermes/profiles/mybot/honcho.json`:

```json
{
  "apiKey": "local",
  "baseUrl": "http://localhost:8000",
  "workspace": "my-project",
  "peerName": "user-name",
  "aiPeer": "mybot",
  "enabled": true,
  "recallMode": "hybrid",
  "observationMode": "directional"
}
```

| Field | Purpose |
|-------|---------|
| `apiKey` | `"local"` for self-hosted. Your Honcho Cloud key if using `api.honcho.dev`. |
| `baseUrl` | Honcho API endpoint. `http://localhost:8000` for local, or Tailscale IP for remote. |
| `workspace` | Honcho workspace name. All sessions for this bot live here. |
| `peerName` | The human user's peer ID. Used to identify who the bot is talking to. |
| `aiPeer` | The bot's peer ID. Honcho tracks what the bot learns about users under this identity. |
| `enabled` | Toggle Honcho integration on/off without removing config. |
| `recallMode` | How the bot retrieves memory. See [Memory Modes](#memory-modes) below. |
| `observationMode` | `"directional"` means the bot observes the user (not itself). `"unified"` observes both. |

### Remote Honcho (Tailscale)

```json
{
  "baseUrl": "http://100.100.223.89:8000"
}
```

---

## Memory Modes

The `recallMode` field controls how memory reaches the agent's context.

### `hybrid` (recommended)

Memory is both auto-injected into the system prompt and available as tools the agent can call.

```json
{ "recallMode": "hybrid" }
```

At the start of each turn, Hermes:
1. Calls Honcho's dialectic to get relevant memory for the current message
2. Injects it into the system prompt as context
3. Also registers `honcho_search`, `honcho_recall`, and `honcho_chat` as callable tools

The agent gets automatic context and can also actively query for more when it needs specific facts.

### `context` (auto-inject only)

Memory is injected into the system prompt but no Honcho tools are exposed.

```json
{ "recallMode": "context" }
```

Simpler. The agent cannot actively search memory — it only gets what the system decides is relevant. Good for lightweight bots that should not be distracted by tool-calling overhead.

### `tools` (manual only)

No auto-injection. The agent must explicitly call Honcho tools to retrieve memory.

```json
{ "recallMode": "tools" }
```

Maximum control. The agent decides when and what to remember. Use this for agents that need to reason about whether to recall (e.g., "should I bring up our last conversation about this topic?").

| Mode | Auto-inject | Tools available | Best for |
|------|------------|----------------|----------|
| `hybrid` | Yes | Yes | Most agents |
| `context` | Yes | No | Simple bots, low-latency |
| `tools` | No | Yes | Agents that reason about memory |

---

## Multi-User Telegram Bot

One bot, multiple allowed users. Honcho tracks each user as a separate peer.

### SOUL.md User ID Table

In `~/.hermes/profiles/mybot/SOUL.md`, define who can talk to the bot and their roles:

```markdown
# MyBot

You are a personal assistant with persistent memory.

## Authorized Users

| Telegram ID | Name | Role | Notes |
|-------------|------|------|-------|
| 123456789 | Alex | owner | Full access. Primary user. |
| 987654321 | Sofia | user | Alex's partner. Can ask about shared plans. |
| 555111222 | Jordan | user | Colleague. Work topics only. |

## Behavior

- If a message comes from an unknown Telegram ID, respond politely but do not store memory.
- Differentiate context by user. What Alex tells you is separate from what Sofia tells you.
- When Alex asks "what did Sofia say about the trip?", use Honcho's cross-peer query (chat tool with target_peer_id).
```

### How It Works

When a Telegram message arrives:

1. Hermes extracts the sender's Telegram user ID
2. Looks up the ID in SOUL.md (or a users config file) to resolve the peer name
3. Sets `peerName` dynamically for that message
4. Honcho tracks observations per peer: what the bot learns about Alex stays under Alex's peer, what it learns about Sofia stays under Sofia's peer

```
Telegram message from 123456789 (Alex)
  → peerName = "alex"
  → Honcho session: workspace=mybot, peer=alex

Telegram message from 987654321 (Sofia)
  → peerName = "sofia"
  → Honcho session: workspace=mybot, peer=sofia
```

### Overseer Pattern

Alex DMs the same bot as Sofia, but Alex is the overseer. The bot should give Alex visibility into all users' interactions.

In SOUL.md:

```markdown
## Overseer Rules

Alex (owner) can:
- Ask "what has Sofia been asking about?" → query Sofia's peer context
- Ask "summarize all conversations today" → iterate all peer sessions
- Ask "what does Jordan know about the Q3 plan?" → query Jordan's conclusions

Other users cannot query other users' data.
```

In `honcho.json`, the bot's `aiPeer` (e.g., `"mybot"`) observes all human peers. When Alex asks about Sofia, the bot uses Honcho's `chat` endpoint with `peer_id=mybot` and `target_peer_id=sofia` to retrieve what it has learned about Sofia.

---

## Cron-to-Conversation Bridge

### The Problem

Hermes supports cron-based check-ins: the bot sends a scheduled message to a user (e.g., "Good morning, any priorities today?"). But these are fire-and-forget. When the user replies, the bot has no memory of what it just asked because the check-in was not part of a Honcho session.

### The Solution

After delivering a cron check-in, write it into a Honcho session so the reply has context.

### Config

In `config.yaml`:

```yaml
cron:
  - schedule: "0 8 * * 1-5"         # Weekdays at 8am
    action: "morning_checkin"
    message: "Good morning! Any priorities for today?"
    persist_to_honcho: true

  - schedule: "0 17 * * 5"           # Friday at 5pm
    action: "weekly_review"
    message: "End of week. Want to review what we accomplished?"
    persist_to_honcho: true

  honcho:
    workspace: "my-project"
    session_prefix: "cron"            # sessions named cron-morning_checkin, cron-weekly_review, etc.
    base_url: "http://localhost:8000"
    peer_name: "alex"
    ai_peer: "mybot"
```

### What Happens

1. Cron fires at 8am Monday
2. Bot sends "Good morning! Any priorities for today?" to Alex on Telegram
3. Because `persist_to_honcho: true`, the bot also writes this message to Honcho:
   - Session: `cron-morning_checkin` (or reuses today's session)
   - Peer: `mybot` (the bot is the author of the check-in)
4. Alex replies: "Focus on the Acme proposal and the team sync at 2pm"
5. The reply is written to the same Honcho session with peer `alex`
6. Next check-in or conversation, the bot remembers the priorities Alex set

### Implementation

This requires a small patch to Hermes's `scheduler.py` (the cron runner). The patch adds a `persist_to_honcho` flag check after message delivery:

```python
# In scheduler.py, after delivering the cron message:
if task.get("persist_to_honcho"):
    honcho_cfg = config.get("cron", {}).get("honcho", {})
    session_id = f"{honcho_cfg['session_prefix']}-{task['action']}"

    # Write the bot's check-in message to Honcho
    requests.post(
        f"{honcho_cfg['base_url']}/v3/workspaces/{honcho_cfg['workspace']}/sessions/{session_id}/messages",
        json={
            "peer_id": honcho_cfg["ai_peer"],
            "content": task["message"]
        }
    )
```

The reply path already writes to Honcho if the profile has `honcho.json` enabled — the key is making sure it uses the same session ID (`cron-morning_checkin`) so the check-in and reply are in the same conversation.

### Session Strategy

| Strategy | Behavior |
|----------|----------|
| One session per cron action | `cron-morning_checkin` accumulates all morning check-ins. Bot sees the history of priorities over time. |
| One session per day | `cron-2026-04-15` groups all cron interactions for that day. Cleaner for daily reviews. |
| One session per cron fire | `cron-morning_checkin-2026-04-15` isolates each check-in. No accumulated context. |

Recommended: one session per cron action. The bot builds a longitudinal view ("last Monday you said Acme was the priority, how did that go?").

---

## Putting It Together

A complete Hermes + Honcho setup for a multi-user Telegram bot with cron:

```
~/.hermes/profiles/mybot/
├── config.yaml          # Platform bindings, cron schedules
├── SOUL.md              # Personality, user ID table, overseer rules
├── honcho.json          # Honcho connection config
└── tools/
    └── honcho_tools.py  # Optional: custom tool wrappers
```

`honcho.json`:
```json
{
  "apiKey": "local",
  "baseUrl": "http://localhost:8000",
  "workspace": "mybot",
  "peerName": "dynamic",
  "aiPeer": "mybot",
  "enabled": true,
  "recallMode": "hybrid",
  "observationMode": "directional"
}
```

Note `"peerName": "dynamic"` — Hermes resolves the actual peer name at runtime from the Telegram user ID mapping.

`config.yaml` (relevant sections):
```yaml
platforms:
  telegram:
    token: "${TELEGRAM_BOT_TOKEN}"
    allowed_users:
      - id: 123456789
        peer: "alex"
        role: "owner"
      - id: 987654321
        peer: "sofia"
        role: "user"

cron:
  - schedule: "0 8 * * 1-5"
    action: "morning_checkin"
    message: "Good morning! Any priorities for today?"
    persist_to_honcho: true
  honcho:
    workspace: "mybot"
    session_prefix: "cron"
    base_url: "http://localhost:8000"
    peer_name: "alex"              # resolved at runtime for gateway sessions
    ai_peer: "mybot"
```

### Verify

```bash
# Start Hermes
hermes run mybot

# Check Honcho sees the workspace
curl http://localhost:8000/v3/workspaces/mybot | jq

# After a conversation, check observations were extracted
curl http://localhost:8000/v3/workspaces/mybot/peers/alex/conclusions | jq
```
