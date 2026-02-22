# Troubleshooting Guide

Common issues, solutions, and diagnostic procedures for TradegentSwarm.

## Quick Diagnostics

### Health Check Command

```bash
cd tradegent
python orchestrator.py health
```

This checks all services: PostgreSQL, Neo4j, Ollama/LLM, and IB Gateway.

### Service Status

```bash
python orchestrator.py status
```

Shows: enabled stocks, upcoming earnings, active schedules, and daily run counts.

---

## Infrastructure Issues

### PostgreSQL Connection Failed

**Symptoms:**
- `Connection refused` or `could not connect to server`
- `FATAL: password authentication failed`

**Solutions:**

1. **Check if container is running:**
   ```bash
   docker compose ps
   docker compose logs nexus-postgres
   ```

2. **Verify environment variables:**
   ```bash
   echo $PG_HOST $PG_PORT $PG_USER $PG_DB
   ```

3. **Test connection manually:**
   ```bash
   psql "host=localhost port=5433 user=lightrag dbname=lightrag"
   ```

4. **Restart container:**
   ```bash
   docker compose restart nexus-postgres
   ```

### Neo4j Connection Failed

**Symptoms:**
- `ServiceUnavailable: Unable to retrieve routing information`
- `AuthError: The client is unauthorized`

**Solutions:**

1. **Check container status:**
   ```bash
   docker compose logs nexus-neo4j
   ```

2. **Verify bolt port:**
   ```bash
   curl http://localhost:7475  # HTTP port
   ```

3. **Check credentials:**
   ```bash
   echo $NEO4J_URI $NEO4J_USER
   ```

4. **Reset Neo4j (destructive):**
   ```bash
   docker compose down nexus-neo4j
   docker volume rm tradegent_neo4j_data
   docker compose up -d nexus-neo4j
   python orchestrator.py graph init
   ```

### IB Gateway Connection Failed

**Symptoms:**
- `Connection refused` on port 4002
- `Not connected` errors in IB MCP
- `Timeout waiting for connection`

**Solutions:**

1. **Check IB Gateway container:**
   ```bash
   docker compose logs nexus-ib-gateway
   ```

2. **Connect via VNC to verify login:**
   ```bash
   vncviewer localhost:5900
   # Password: nexus123 (or VNC_PASS from .env)
   ```

3. **Check if 2FA is needed:** The gateway requires manual 2FA approval after restart.

4. **Verify port mapping:**
   ```bash
   docker compose ps nexus-ib-gateway
   # Should show 4001->4001, 4002->4002
   ```

5. **Test IB MCP health:**
   ```bash
   curl http://localhost:8100/health  # If using direct mode
   curl http://localhost:8002/health  # If using Docker mode
   ```

---

## Embedding & RAG Issues

### Embedding Dimension Mismatch

**Symptoms:**
- `different vector dimensions` error
- `cannot insert vector with X dimensions into column with Y dimensions`

**Cause:** Embedding dimensions changed after schema was created.

**Solution:**

1. **Check current config:**
   ```bash
   grep dimensions tradegent/rag/config.yaml
   ```

2. **Reset RAG schema (destructive):**
   ```bash
   python orchestrator.py rag reset
   # Type 'yes' to confirm
   python orchestrator.py rag init
   ```

3. **Re-embed all documents:**
   ```bash
   python orchestrator.py rag embed --dir tradegent_knowledge/knowledge --force
   ```

### Embedding Provider Errors

**Symptoms:**
- `401 Unauthorized` from OpenAI
- `Connection refused` from Ollama
- `Rate limit exceeded`

**Solutions:**

1. **Verify API key:**
   ```bash
   echo $OPENAI_API_KEY | head -c 10
   # Should show: sk-proj-...
   ```

2. **Check Ollama is running:**
   ```bash
   curl http://localhost:11434/api/tags
   ```

3. **Check provider config:**
   ```bash
   cat tradegent/rag/config.yaml | grep -A5 embedding
   ```

4. **Switch providers temporarily:**
   ```bash
   export EMBED_PROVIDER=ollama
   ```

### RAG Search Returns Empty Results

**Symptoms:**
- `rag_search` returns empty list
- No chunks found for ticker

**Solutions:**

1. **Check if documents are embedded:**
   ```bash
   python orchestrator.py rag status
   python orchestrator.py rag list
   ```

2. **Verify document exists:**
   ```bash
   ls tradegent_knowledge/knowledge/analysis/earnings/NVDA*.yaml
   ```

3. **Re-embed specific document:**
   ```bash
   python orchestrator.py rag embed tradegent_knowledge/knowledge/analysis/earnings/NVDA_20250120T0900.yaml --force
   ```

---

## Graph Extraction Issues

### Graph Extraction Fails

**Symptoms:**
- `ExtractionError: LLM call failed`
- `GraphUnavailableError: Cannot commit to Neo4j`
- Entities extracted but not committed

**Solutions:**

1. **Check Neo4j connection:**
   ```bash
   python orchestrator.py graph status
   ```

2. **Check pending commits queue:**
   ```bash
   cat logs/pending_commits.jsonl | wc -l
   ```

3. **Retry pending commits:**
   ```bash
   python orchestrator.py graph retry --limit 10
   ```

4. **Check extractor config:**
   ```bash
   echo $EXTRACT_PROVIDER
   cat tradegent/graph/config.yaml | grep -A5 extraction
   ```

### Duplicate Entities in Graph

**Symptoms:**
- Same ticker appears multiple times
- Relationships duplicated

**Solution:**

```bash
python orchestrator.py graph dedupe
```

---

## Orchestrator Issues

### Claude Code CLI Not Found

**Symptoms:**
- `FileNotFoundError: [Errno 2] No such file or directory: 'claude'`

**Solutions:**

1. **Check if installed:**
   ```bash
   which claude
   claude --version
   ```

2. **Install Claude Code:**
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

3. **Check PATH:**
   ```bash
   echo $PATH | tr ':' '\n' | grep npm
   ```

### Dry Run Mode Blocking Operations

**Symptoms:**
- Analysis produces empty output
- Log shows "DRY RUN — would call Claude Code"

**Solution:**

```bash
python orchestrator.py settings set dry_run_mode false
```

### Daily Limit Reached

**Symptoms:**
- Log shows "Daily analysis limit reached — skipping"
- Schedules not running

**Solutions:**

1. **Check current count:**
   ```bash
   python orchestrator.py status
   ```

2. **Increase limit:**
   ```bash
   python orchestrator.py settings set max_daily_analyses 25
   ```

3. **Reset counter (next day):** Counters reset at midnight automatically.

### Schedule Not Running

**Symptoms:**
- Schedule shows as enabled but doesn't execute

**Solutions:**

1. **Check if schedule is due:**
   ```bash
   python orchestrator.py status
   # Look at "due" count in SCHEDULES section
   ```

2. **Check circuit breaker:**
   - If `consecutive_fails >= max_consecutive_fails`, schedule is paused
   - Fix: Reset the counter in database

3. **Check stock is enabled:**
   ```bash
   python orchestrator.py stock list
   ```

---

## Git & SSH Issues

### Git Push Fails with OpenSSL Error

**Symptoms:**
- `libcrypto.so.3: version 'OPENSSL_3.0.0' not found`
- `kex_exchange_identification: read: Connection reset`

**Cause:** Conda's OpenSSL conflicts with system SSH.

**Solution:**

```bash
GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push
```

Or add alias:

```bash
git config --global alias.pushs '!GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push'
git pushs  # Use this instead
```

### Permission Denied (publickey)

**Symptoms:**
- `Permission denied (publickey).`
- `git@github.com: Permission denied`

**Solutions:**

1. **Check SSH key:**
   ```bash
   ssh -T git@github.com
   ```

2. **Add key to agent:**
   ```bash
   eval "$(ssh-agent -s)"
   ssh-add ~/.ssh/your-github-key
   ```

3. **Verify SSH config:**
   ```bash
   cat ~/.ssh/config | grep -A4 github
   ```

---

## MCP Server Issues

### MCP Server Not Responding

**Symptoms:**
- Tool calls timeout
- `Connection refused` errors

**Solutions:**

1. **Check if server is running:**
   ```bash
   ps aux | grep mcp_server
   ```

2. **Start server manually:**
   ```bash
   # RAG server
   cd tradegent && python -m rag.mcp_server

   # Graph server
   cd tradegent && python -m graph.mcp_server

   # IB MCP (direct mode)
   cd /opt/data/trading/mcp_ib && python -m ibmcp --transport sse --port 8100
   ```

3. **Check mcp.json configuration:**
   ```bash
   cat tradegent/.claude/mcp.json
   ```

---

## Performance Issues

### Analysis Taking Too Long

**Symptoms:**
- Single analysis takes >10 minutes
- Timeout errors

**Solutions:**

1. **Check LLM provider speed:**
   - Ollama (local): Slower but free
   - OpenAI (cloud): Faster but costs money

2. **Reduce data gathering scope:**
   - Limit historical data period
   - Reduce web search queries

3. **Check IB rate limiting:**
   - IB enforces 50 req/sec
   - MCP server has built-in throttling

### High Memory Usage

**Symptoms:**
- OOM errors
- System slowdown during embedding

**Solutions:**

1. **Process documents in batches:**
   ```bash
   # Instead of --dir, process files individually
   for f in tradegent_knowledge/knowledge/analysis/earnings/*.yaml; do
     python orchestrator.py rag embed "$f"
   done
   ```

2. **Reduce chunk size in config:**
   ```yaml
   # rag/config.yaml
   chunking:
     max_tokens: 1000  # Reduce from 1500
   ```

---

## Common Error Messages

| Error | Cause | Quick Fix |
|-------|-------|-----------|
| `ModuleNotFoundError: No module named 'db_layer'` | Wrong working directory | `cd tradegent` |
| `psycopg.OperationalError: connection refused` | PostgreSQL not running | `docker compose up -d` |
| `neo4j.exceptions.ServiceUnavailable` | Neo4j not running | `docker compose up -d` |
| `subprocess.TimeoutExpired` | Claude Code took too long | Increase `CLAUDE_TIMEOUT` |
| `ValueError: Invalid stock column` | Typo in column name | Check `STOCK_COLUMNS` in db_layer.py |
| `KeyError: 'gate_passed'` | Analysis didn't return JSON | Check Claude Code output |

---

## Getting Help

1. **Check logs:**
   ```bash
   tail -100 tradegent/logs/orchestrator.log
   cat logs/rag_embed.jsonl | tail -5
   cat logs/graph_extractions.jsonl | tail -5
   ```

2. **Enable debug logging:**
   ```python
   # In orchestrator.py
   logging.basicConfig(level=logging.DEBUG, ...)
   ```

3. **File an issue:** https://github.com/vladm3105/TradegentSwarm/issues
