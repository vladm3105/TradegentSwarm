# Troubleshooting Guide

Common issues and solutions for TradegentSwarm.

---

## Quick Diagnostics

```bash
# Check all services
python orchestrator.py status
docker compose ps
sudo systemctl status tradegent tradegent-ib-mcp
```

---

## Connection Issues

### Database Connection Failed

**Symptoms:**
- "Connection refused" errors
- `psql: could not connect to server`

**Solutions:**

1. Check Docker is running:
   ```bash
   docker compose ps
   docker compose logs postgres
   ```

2. Restart PostgreSQL:
   ```bash
   docker compose restart postgres
   ```

3. Verify credentials:
   ```bash
   source .env
   psql -h localhost -p 5433 -U $PG_USER -d $PG_DB -c "SELECT 1"
   ```

4. Check port availability:
   ```bash
   netstat -tlnp | grep 5433
   ```

### Neo4j Connection Failed

**Symptoms:**
- "Failed to connect to Neo4j"
- Graph operations timeout

**Solutions:**

1. Check container:
   ```bash
   docker compose logs neo4j
   ```

2. Restart Neo4j:
   ```bash
   docker compose restart neo4j
   ```

3. Verify connection:
   ```bash
   curl http://localhost:7474
   ```

4. Check bolt port:
   ```bash
   netstat -tlnp | grep 7688
   ```

### IB Gateway Not Connecting

**Symptoms:**
- "Failed to connect to IB Gateway"
- Market data unavailable

**Solutions:**

1. Check container status:
   ```bash
   docker compose ps ib-gateway
   ```

2. Connect via VNC to check login:
   ```bash
   vncviewer localhost:5900
   # Password: value of VNC_PASS
   ```

3. Complete 2FA if prompted

4. Verify API port:
   ```bash
   nc -zv localhost 4002
   ```

5. Restart gateway:
   ```bash
   docker compose restart ib-gateway
   ```

---

## RAG Issues

### Dimension Mismatch Error

**Symptoms:**
- "Dimension mismatch: got 768, expected 1536"
- Search returns no results

**Cause:** Embedding provider changed (e.g., Ollama→OpenAI)

**Solutions:**

1. Check current provider:
   ```bash
   echo $EMBED_PROVIDER
   ```

2. Option A - Switch back to original provider:
   ```bash
   export EMBED_PROVIDER=ollama
   ```

3. Option B - Re-embed all documents:
   ```bash
   python scripts/index_knowledge_base.py --force
   ```

### Empty Search Results

**Symptoms:**
- RAG search returns empty
- "No documents found"

**Solutions:**

1. Check embeddings exist:
   ```sql
   SELECT COUNT(*) FROM nexus.rag_chunks;
   ```

2. Verify document was embedded:
   ```sql
   SELECT * FROM nexus.rag_documents WHERE doc_id LIKE '%NVDA%';
   ```

3. Lower similarity threshold:
   ```yaml
   Tool: rag_search
   Input: {"query": "...", "min_similarity": 0.3}
   ```

4. Try hybrid search (adds BM25):
   ```yaml
   Tool: rag_hybrid_context
   ```

### Embedding Fails

**Symptoms:**
- "Failed to generate embedding"
- OpenAI API errors

**Solutions:**

1. Check API key:
   ```bash
   echo $OPENAI_API_KEY | head -c 10
   ```

2. Verify provider:
   ```bash
   echo $EMBED_PROVIDER
   ```

3. Test directly:
   ```python
   from rag.embedding_client import get_embedding
   embedding = get_embedding("test")
   print(len(embedding))
   ```

---

## Graph Issues

### Empty Extraction Results

**Symptoms:**
- "Extracted 0 entities"
- Graph context empty

**Solutions:**

1. Check document has content:
   ```bash
   cat path/to/document.yaml | head -50
   ```

2. Verify extraction provider:
   ```bash
   echo $EXTRACT_PROVIDER
   ```

3. Try OpenAI instead of Ollama:
   ```bash
   export EXTRACT_PROVIDER=openai
   ```

4. Check API key for provider:
   ```bash
   echo $OPENAI_API_KEY | head -c 10
   ```

### Slow Extraction

**Symptoms:**
- Extraction takes >60 seconds
- Timeouts

**Solutions:**

1. Use OpenAI (12x faster than Ollama):
   ```bash
   export EXTRACT_PROVIDER=openai
   ```

2. Increase timeout:
   ```bash
   export EXTRACT_TIMEOUT_SECONDS=60
   ```

3. Reduce document size (split large files)

---

## Service Issues

### Service Won't Start

**Symptoms:**
- systemctl shows "failed"
- Service exits immediately

**Solutions:**

1. Check logs:
   ```bash
   sudo journalctl -u tradegent -n 50
   ```

2. Test manually:
   ```bash
   cd /opt/data/tradegent_swarm/tradegent
   source .env
   python service.py
   ```

3. Fix Python path issues:
   ```bash
   which python3
   # Ensure correct Python in service file
   ```

### Dry Run Mode Blocking

**Symptoms:**
- "Dry run mode enabled, skipping"
- No Claude Code calls made

**Solution:**

```bash
python orchestrator.py settings set dry_run_mode false
```

### Analysis Not Running

**Symptoms:**
- Manual analyze works, batch doesn't
- Stocks not being processed

**Solutions:**

1. Check stock is enabled:
   ```bash
   python orchestrator.py stock list --enabled
   ```

2. Enable stock:
   ```bash
   python orchestrator.py stock enable NVDA
   ```

3. Check daily limits:
   ```bash
   python orchestrator.py settings get max_daily_analyses
   ```

---

## Claude Code Issues

### "claude" Command Not Found

**Symptoms:**
- `command not found: claude`
- Service fails to call Claude

**Solutions:**

1. Check Node.js installation:
   ```bash
   node --version
   ```

2. Add to PATH (if using nvm):
   ```bash
   export PATH="$HOME/.nvm/versions/node/v20.x.x/bin:$PATH"
   ```

3. Reinstall Claude Code:
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

### Claude Code Auth Failed

**Symptoms:**
- "Authentication required"
- API key errors

**Solutions:**

1. Sign in:
   ```bash
   claude
   ```

2. Or set API key:
   ```bash
   export ANTHROPIC_API_KEY=sk-...
   ```

---

## Git Push Issues

### SSH Failures with Conda

**Symptoms:**
- `kex_exchange_identification: Connection closed`
- SSH handshake fails

**Cause:** Conda's OpenSSL conflicts with system SSH

**Solutions:**

1. Use LD_LIBRARY_PATH fix:
   ```bash
   GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push
   ```

2. Create alias:
   ```bash
   git config --global alias.pushs '!GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push'
   git pushs
   ```

3. Deactivate conda:
   ```bash
   conda deactivate
   git push
   ```

---

## Performance Issues

### Slow Analysis

**Possible causes:**
- RAG search slow
- Graph extraction slow
- IB data latency

**Solutions:**

1. Use OpenAI for RAG (faster than Ollama)
2. Reduce search top_k
3. Check IB connection stability

### High Memory Usage

**Solutions:**

1. Check container limits:
   ```bash
   docker stats
   ```

2. Restart services:
   ```bash
   docker compose restart
   ```

3. Clear old data:
   ```sql
   DELETE FROM nexus.run_history WHERE started_at < NOW() - INTERVAL '30 days';
   ```

---

## Data Issues

### Missing Analysis Output

**Symptoms:**
- Analysis ran but no file
- Index failed

**Solutions:**

1. Check output directory:
   ```bash
   ls -la tradegent_knowledge/knowledge/analysis/stock/
   ```

2. Check run history:
   ```sql
   SELECT * FROM nexus.run_history ORDER BY started_at DESC LIMIT 5;
   ```

3. Check for errors:
   ```sql
   SELECT error_message FROM nexus.run_history
   WHERE status = 'failed' ORDER BY started_at DESC LIMIT 5;
   ```

### Stale Data

**Symptoms:**
- Search returns old results
- Graph shows outdated entities

**Solution:** Re-index knowledge base:

```bash
python scripts/index_knowledge_base.py --force
```

---

## Recovery Procedures

### Full Reset

```bash
# Stop services
sudo systemctl stop tradegent tradegent-ib-mcp
docker compose down

# Clear data (careful!)
docker volume rm tradegent_postgres_data tradegent_neo4j_data

# Restart
docker compose up -d
python orchestrator.py db-init
python scripts/index_knowledge_base.py
```

### Database Recovery

```bash
# Restore from backup
psql -h localhost -p 5433 -U lightrag -d lightrag < backup.sql
```

---

## Getting Help

1. Check logs first:
   ```bash
   sudo journalctl -u tradegent -n 100
   docker compose logs
   ```

2. Search past sessions:
   ```bash
   grep "error" ~/.claude/projects/-opt-data-tradegent-swarm/*.jsonl
   ```

3. File issue: [GitHub Issues](https://github.com/vladm3105/TradegentSwarm/issues)

---

## Related Documentation

- [Deployment](deployment.md)
- [Monitoring](monitoring.md)
- [Runbooks](runbooks.md)
