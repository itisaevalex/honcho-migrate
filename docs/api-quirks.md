# API Reference & Quirks

## The Big Gotcha: POST for Most Operations

The Honcho v3 API uses **POST** for list and get operations. If you try GET on a list endpoint, you get `405 Method Not Allowed`.

Notable **GET exceptions** (these actually use GET):
- **Peer card** — `GET /v3/workspaces/{id}/peers/{id}/card`
- **Queue status** — `GET /v3/workspaces/{id}/queue/status`
- **Health check** — `GET /health`

Everything else — list, create, upsert, search, chat — uses POST.

```bash
# WRONG — returns 405
curl http://localhost:8000/v3/workspaces/list

# RIGHT — use POST
curl -s -X POST http://localhost:8000/v3/workspaces/list \
  -H "Content-Type: application/json"
```

This applies to all `/list` endpoints and most retrieval endpoints. Create and upsert endpoints also use POST, which is expected. The non-obvious part is that reads are POST too.

## Workspace Creation Is Idempotent

POSTing to `/v3/workspaces` with an existing ID returns the existing workspace. No error, no duplicate. Same for peers and sessions. This means your agent startup code can unconditionally call create on every run without checking existence first.

```bash
# First call: creates the workspace
curl -s -X POST http://localhost:8000/v3/workspaces \
  -H "Content-Type: application/json" -d '{"id": "my-project"}'

# Second call: returns the same workspace, no error
curl -s -X POST http://localhost:8000/v3/workspaces \
  -H "Content-Type: application/json" -d '{"id": "my-project"}'
```

## Port Reference

| Port | Service | Description |
|------|---------|-------------|
| 8000 | Honcho API | The REST API (Docker container, bound to 0.0.0.0) |
| 8787 | MCP Bridge | Wrangler dev worker, translates MCP protocol to Honcho API calls |
| 11434 | Ollama | Local embedding model server (bge-m3) |
| 5432 | PostgreSQL | Database with pgvector (Docker, internal) |
| 6379/6380 | Redis | Cache; use 6380 if host Redis conflicts with Docker Redis |

If you are running behind Tailscale, the API is reachable at `http://YOUR_TAILSCALE_IP:8000`.

## Pagination

All list endpoints return paginated responses with the same shape:

```json
{
  "items": [...],
  "total": 42,
  "page": 1,
  "size": 50,
  "pages": 1
}
```

- `page` — 1-based current page number
- `size` — items per page (default 50, max 100)
- `pages` — total number of pages
- `total` — total number of items across all pages

Control pagination with query parameters: `?page=2&size=20`

To fetch all items, loop until `page >= pages`:

```bash
# Page 1
curl -s -X POST "http://localhost:8000/v3/workspaces/list?page=1&size=50" \
  -H "Content-Type: application/json"

# Page 2
curl -s -X POST "http://localhost:8000/v3/workspaces/list?page=2&size=50" \
  -H "Content-Type: application/json"
```

## Common API Patterns

### List workspaces

```bash
curl -s -X POST http://localhost:8000/v3/workspaces/list \
  -H "Content-Type: application/json"
```

Returns paginated list of all workspaces. No request body needed.

### Create a workspace

```bash
curl -s -X POST http://localhost:8000/v3/workspaces \
  -H "Content-Type: application/json" \
  -d '{"id": "my-project"}'
```

Returns the workspace object. Idempotent.

### Create a peer

```bash
curl -s -X POST http://localhost:8000/v3/workspaces/my-project/peers \
  -H "Content-Type: application/json" \
  -d '{"id": "alex"}'
```

Returns the peer object. Idempotent.

### List peers in a workspace

```bash
curl -s -X POST http://localhost:8000/v3/workspaces/my-project/peers/list \
  -H "Content-Type: application/json"
```

### Create a session

```bash
curl -s -X POST http://localhost:8000/v3/workspaces/my-project/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "id": "session-001",
    "peers": {
      "alex": {"observe_me": true, "observe_others": false},
      "claude-code": {"observe_me": true, "observe_others": false}
    }
  }'
```

The `peers` field is optional. If omitted, create the session first and configure peers separately.

### List sessions in a workspace

```bash
curl -s -X POST http://localhost:8000/v3/workspaces/my-project/sessions/list \
  -H "Content-Type: application/json"
```

### Add messages to a session

```bash
curl -s -X POST http://localhost:8000/v3/workspaces/my-project/sessions/session-001/messages \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"content": "I need to refactor the auth module.", "peer_id": "alex", "role": "user"},
      {"content": "I will start with the token validation logic.", "peer_id": "claude-code", "role": "user"}
    ]
  }'
```

Messages are batched — send up to 100 per call. Each message needs `content`, `peer_id`, and `role` at minimum.

### List messages in a session

```bash
curl -s -X POST "http://localhost:8000/v3/workspaces/my-project/sessions/session-001/messages/list?page=1&size=50" \
  -H "Content-Type: application/json"
```

Add `&reverse=true` to get newest messages first.

### Semantic search

```bash
curl -s -X POST http://localhost:8000/v3/workspaces/my-project/search \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication token handling", "limit": 10}'
```

Returns messages ranked by vector similarity. Scope to a specific peer:

```bash
curl -s -X POST http://localhost:8000/v3/workspaces/my-project/peers/alex/search \
  -H "Content-Type: application/json" \
  -d '{"query": "frontend preferences", "limit": 5}'
```

### Query the dialectic (chat with memory)

```bash
curl -s -X POST http://localhost:8000/v3/workspaces/my-project/peers/alex/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What does Alex prefer for state management?", "reasoning_level": "low"}'
```

Reasoning levels: `minimal`, `low`, `medium`, `high`, `max`. Higher levels produce better answers but take longer and cost more LLM tokens.

### Get a peer card

```bash
curl -s http://localhost:8000/v3/workspaces/my-project/peers/alex/card
```

This one actually uses GET. Returns the structured summary the deriver has built about the peer.

### Schedule a dream (memory consolidation)

```bash
curl -s -X POST http://localhost:8000/v3/workspaces/my-project/schedule_dream \
  -H "Content-Type: application/json" \
  -d '{"observer": "claude-code", "dream_type": "omni"}'
```

Dreams are async. Poll the queue to check completion:

```bash
curl -s http://localhost:8000/v3/workspaces/my-project/queue/status
```

### Health check

```bash
curl -s http://localhost:8000/health
```

Returns 200 if the API is running. Does not check deriver or database health.
