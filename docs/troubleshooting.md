# Troubleshooting

Common issues and fixes for self-hosted Honcho and the honcho-migrate tooling.

## Deriver not processing messages

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

## Embedding dimension mismatch

**Symptom:** `column cannot have more than 2000 dimensions for hnsw index` or vector insert errors.

**Cause:** The DB schema dimensions don't match the embedding model output.

- bge-m3: 1024 dims
- nomic-embed-text: 768 dims
- qwen3-embedding:8b: 4096 dims (too high for HNSW, needs truncation)

Set `VECTOR_STORE_DIMENSIONS` in `.env` to match your model, and use `HONCHO_FRESH_INSTALL=true` on first start.

## Docker can't reach local Ollama

**Symptom:** Embedding requests timeout from inside Docker containers.

**Fix:** See [Firewall Setup](self-hosting.md#firewall-setup-ufw--docker) in the self-hosting guide.

## Redis port conflict

**Symptom:** `address already in use` on port 6379.

**Fix:** Remap Docker Redis to a different port in docker-compose.yml:
```yaml
redis:
  ports:
    - "127.0.0.1:6380:6379"
```

## GET returns 405 Method Not Allowed

**Symptom:** API calls to list or get resources return `405 Method Not Allowed`.

**Cause:** Honcho v3 API uses POST for list/get operations, not GET. All resource retrieval endpoints expect POST requests with a JSON body.

**Fix:** Change your HTTP method from GET to POST. For example:
```bash
# Wrong
curl http://localhost:8000/v3/apps/default/workspaces

# Correct
curl -X POST http://localhost:8000/v3/apps/default/workspaces \
  -H "Content-Type: application/json" \
  -d '{}'
```

## MCP tools not showing up

**Symptom:** Claude or other MCP clients don't list Honcho memory tools.

**Cause:** The MCP bridge server is not running or not reachable.

**Fix:** Verify that `wrangler dev` (or the MCP bridge process) is running on port 8787:
```bash
# Check if the process is running
curl http://localhost:8787

# Start the MCP bridge if needed (inside the honcho repo's mcp/ directory)
cd ~/Documents/honcho/mcp/
wrangler dev --port 8787
```

Ensure your MCP client configuration points to `http://localhost:8787`.

## Workspace shim not switching

**Symptom:** Commands run against the wrong workspace, or the workspace shim doesn't pick up changes.

**Cause:** Syntax error in `workspace-map.conf` or shell environment not reloaded.

**Fix:**
1. Check `workspace-map.conf` syntax -- each line should be `pattern=workspace` where pattern is matched against `$PWD`, with no extra spaces or quotes.
2. Re-source your shell config:
```bash
source ~/.bashrc
```
3. Verify the active workspace:
```bash
echo $HONCHO_WORKSPACE
```

## Hermes not persisting memories

**Symptom:** Conversations happen but no observations or memories appear in the dashboard.

**Cause:** Misconfigured base URL or the target workspace doesn't exist.

**Fix:**
1. Check `honcho.json` (or your agent config) -- the `baseUrl` must point to your Honcho API (e.g., `http://localhost:8000`).
2. Verify the workspace exists:
```bash
curl -X POST http://localhost:8000/v3/apps/default/workspaces \
  -H "Content-Type: application/json" \
  -d '{}'
```
3. Look for your workspace in the response. If it doesn't exist, create it:
```bash
curl -X POST http://localhost:8000/v3/apps/default/workspaces \
  -H "Content-Type: application/json" \
  -d '{"name": "your-workspace-name"}'
```

## Port confusion

Quick reference for all services and their default ports:

| Port | Service | Notes |
|------|---------|-------|
| 8000 | Honcho API | Main REST API, binds 0.0.0.0 by default |
| 8787 | MCP bridge | Wrangler dev server for MCP tool integration |
| 11434 | Ollama | Local embedding model (bge-m3); must bind 0.0.0.0 for Docker access |
| 5432 | PostgreSQL | Inside Docker; not exposed to host by default |
| 6379 | Redis (container) | Default Redis port inside the container |
| 6380 | Redis (host-mapped) | Use this if host already runs Redis on 6379 |
