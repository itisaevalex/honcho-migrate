# Multi-Workspace Architecture

## Core Concepts

Honcho organizes memory into three levels:

**Workspace** — Top-level isolation boundary. One workspace per project or product. Everything inside a workspace shares the same memory graph. Nothing leaks between workspaces.

**Peer** — A participant inside a workspace. Can be a human, an AI agent, or a domain category. Honcho builds a "peer card" for each peer over time — a structured summary of what it has learned about that peer from conversations.

**Session** — A conversation container. Messages live inside sessions. One or more peers participate in each session. The deriver watches sessions and extracts observations about the peers involved.

```
Workspace
├── Peer A
├── Peer B
└── Session 1
    ├── Message (from Peer A)
    ├── Message (from Peer B)
    └── ...
```

Sessions belong to the workspace, not to individual peers. Peers are linked to sessions through observer configs that control which peers the deriver tracks in that session.

## One Workspace Per Project

Use one workspace per distinct project or product. Do not mix unrelated projects in a single workspace — the memory graph will conflate observations across them.

Good:
- `acme-app` — your SaaS product
- `sales-pipeline` — your sales workflow
- `personal` — personal agent conversations

Bad:
- `everything` — all projects dumped together
- `agent-1`, `agent-2` — splitting by agent instead of by project

Agents that work on the same project should share the same workspace so they can access shared context about the project and its users.

## Peer Types

### Domain Peers

Represent knowledge areas or system components. Useful when you want Honcho to build separate memory profiles for different parts of your project.

| Peer ID | Purpose |
|---------|---------|
| `frontend` | Frontend code, UI patterns, component library decisions |
| `backend` | API design, database schema, server architecture |
| `business` | Product requirements, customer feedback, roadmap |
| `infrastructure` | Deployment, CI/CD, monitoring, scaling |
| `design` | Visual direction, brand guidelines, UX patterns |

Domain peers let you scope conversations. When you discuss frontend architecture with an agent, tag those messages with `peer_id: "frontend"` so the deriver builds observations under the frontend peer card.

### Agent Peers

Represent AI agents that interact with the workspace. Each agent gets its own peer so Honcho can track what each agent has learned and discussed.

| Peer ID | Purpose |
|---------|---------|
| `claude-code` | Claude Code sessions |
| `hermes` | Hermes agent conversations |
| `cursor` | Cursor IDE agent |
| `custom-bot` | Your custom agent |

### Human Peers

Represent the humans involved.

| Peer ID | Purpose |
|---------|---------|
| `alex` | The primary user |
| `team-lead` | Another team member |

## Creating Workspaces and Peers

### Create a workspace

```bash
curl -s -X POST http://localhost:8000/v3/workspaces \
  -H "Content-Type: application/json" \
  -d '{"id": "my-project"}'
```

This is idempotent. Calling it twice with the same ID returns the existing workspace without error.

### Create a peer

```bash
curl -s -X POST http://localhost:8000/v3/workspaces/my-project/peers \
  -H "Content-Type: application/json" \
  -d '{"id": "frontend"}'
```

Also idempotent. Safe to call on every agent startup.

### Create a session with peers

```bash
curl -s -X POST http://localhost:8000/v3/workspaces/my-project/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "id": "session-2026-04-15",
    "peers": {
      "alex": {"observe_me": true, "observe_others": false},
      "claude-code": {"observe_me": true, "observe_others": false}
    }
  }'
```

The `peers` field configures observer behavior:
- `observe_me: true` — the deriver extracts observations about this peer from the session
- `observe_others: false` — this peer does not observe what other peers say (set to `true` if you want cross-peer observation)

## Session Strategies

How you map real-world interactions to Honcho sessions depends on your use case.

### Per-directory

One session per project directory. Good for code agents where the working directory defines context.

```
session_id = "dir-" + hash("/home/alex/projects/acme-app")
```

### Per-session

One session per agent invocation. Good for chatbots and assistants where each conversation is independent.

```
session_id = "chat-" + uuid()
```

### Global

One long-running session per peer. Good for simple setups where you want all messages in one stream.

```
session_id = "global-alex"
```

### Manual mapping

Explicit session IDs chosen by the user or agent for specific topics.

```
session_id = "acme-app-auth-redesign"
session_id = "q2-sales-planning"
```

Pick one strategy and stick with it. Mixing strategies in the same workspace makes it harder to query history.

## Cross-Agent Coordination

Multiple agents can share the same workspace. Each agent registers as its own peer and writes messages to sessions. The deriver processes all messages regardless of which agent wrote them.

### How it works

1. Both agents create themselves as peers in the workspace (idempotent, safe to repeat).
2. Both agents create or join sessions, including themselves and the human user as peers.
3. Messages from all agents flow into the same workspace's memory graph.
4. The deriver extracts observations about each peer from every session.
5. Any agent can query the dialectic for accumulated knowledge about any peer.

### Practical example

Claude Code works on the frontend. Hermes handles backend tasks. Both share the `acme-app` workspace.

Claude Code session:
```bash
# Claude Code registers and starts a session
curl -s -X POST http://localhost:8000/v3/workspaces/acme-app/peers \
  -H "Content-Type: application/json" -d '{"id": "claude-code"}'

curl -s -X POST http://localhost:8000/v3/workspaces/acme-app/sessions \
  -H "Content-Type: application/json" \
  -d '{"id": "claude-frontend-session", "peers": {"alex": {"observe_me": true, "observe_others": false}, "claude-code": {"observe_me": true, "observe_others": false}}}'
```

Later, Hermes can query what Claude Code discussed:
```bash
curl -s -X POST http://localhost:8000/v3/workspaces/acme-app/peers/alex/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What frontend decisions were made recently?", "reasoning_level": "low"}'
```

The dialectic synthesizes across all sessions in the workspace, not just Hermes's own sessions.

## Worked Example: Setting Up "acme-app"

Goal: a workspace for the Acme App project with a human user, two AI agents, and three domain peers.

### Target layout

```
acme-app workspace
├── alex          (human)
├── claude-code   (agent)
├── hermes        (agent)
├── frontend      (domain)
├── backend       (domain)
└── business      (domain)
```

### Step 1: Create the workspace

```bash
curl -s -X POST http://localhost:8000/v3/workspaces \
  -H "Content-Type: application/json" \
  -d '{"id": "acme-app"}'
```

### Step 2: Create all peers

```bash
# Human
curl -s -X POST http://localhost:8000/v3/workspaces/acme-app/peers \
  -H "Content-Type: application/json" -d '{"id": "alex"}'

# Agents
curl -s -X POST http://localhost:8000/v3/workspaces/acme-app/peers \
  -H "Content-Type: application/json" -d '{"id": "claude-code"}'

curl -s -X POST http://localhost:8000/v3/workspaces/acme-app/peers \
  -H "Content-Type: application/json" -d '{"id": "hermes"}'

# Domain peers
curl -s -X POST http://localhost:8000/v3/workspaces/acme-app/peers \
  -H "Content-Type: application/json" -d '{"id": "frontend"}'

curl -s -X POST http://localhost:8000/v3/workspaces/acme-app/peers \
  -H "Content-Type: application/json" -d '{"id": "backend"}'

curl -s -X POST http://localhost:8000/v3/workspaces/acme-app/peers \
  -H "Content-Type: application/json" -d '{"id": "business"}'
```

### Step 3: Create a session for frontend work

```bash
curl -s -X POST http://localhost:8000/v3/workspaces/acme-app/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "id": "frontend-redesign",
    "peers": {
      "alex": {"observe_me": true, "observe_others": false},
      "claude-code": {"observe_me": true, "observe_others": false}
    }
  }'
```

### Step 4: Add messages

```bash
curl -s -X POST http://localhost:8000/v3/workspaces/acme-app/sessions/frontend-redesign/messages \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"content": "Let us switch from CSS modules to Tailwind for the new dashboard.", "peer_id": "alex", "role": "user"},
      {"content": "Done. Converted all dashboard components to Tailwind. Kept CSS modules for the legacy pages.", "peer_id": "claude-code", "role": "user"}
    ]
  }'
```

### Step 5: Query memory from any agent

```bash
curl -s -X POST http://localhost:8000/v3/workspaces/acme-app/peers/alex/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the frontend styling preferences?", "reasoning_level": "low"}'
```

The deriver will have extracted observations like "Alex prefers Tailwind for new work" and "legacy pages still use CSS modules" — available to any agent querying the workspace.
