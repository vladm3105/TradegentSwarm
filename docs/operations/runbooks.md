# Runbooks

Step-by-step procedures for common operational tasks.

---

## Daily Operations

### Morning Startup

**When:** Before market open (8:00 ET)

```bash
# 1. Verify services
docker compose ps
sudo systemctl status tradegent tradegent-ib-mcp

# 2. Check IB Gateway connection
curl -s http://localhost:8100/health | jq

# 3. Verify database
python orchestrator.py status

# 4. Check for overnight issues
sudo journalctl -u tradegent --since "yesterday" | grep -i error

# 5. Review scheduled analyses
python orchestrator.py stock list --enabled
```

### Evening Shutdown (Optional)

**When:** After market close (16:30 ET)

```bash
# 1. Check daily summary
SELECT run_type, status, COUNT(*)
FROM nexus.run_history
WHERE DATE(started_at) = CURRENT_DATE
GROUP BY run_type, status;

# 2. Review failures
SELECT ticker, error_message
FROM nexus.run_history
WHERE status = 'failed' AND DATE(started_at) = CURRENT_DATE;

# 3. Backup knowledge (weekly)
tar -czf ~/backups/knowledge_$(date +%Y%m%d).tar.gz \
  tradegent_knowledge/knowledge/
```

---

## Adding a New Stock

**When:** Adding ticker to watchlist for automated analysis

```bash
# 1. Add stock with details
python orchestrator.py stock add PLTR \
  --name "Palantir Technologies" \
  --priority 7 \
  --tags "ai,defense,gov"

# 2. Set earnings date (if known)
python orchestrator.py stock set-earnings PLTR 2025-02-15

# 3. Run initial analysis
python orchestrator.py analyze PLTR --type stock

# 4. Verify indexing
python -c "
from rag.search import semantic_search
results = semantic_search('PLTR analysis', ticker='PLTR', top_k=1)
print(f'Found: {len(results)} results')
"

# 5. Enable for batch runs
python orchestrator.py stock enable PLTR
```

---

## Running Manual Analysis

**When:** Need immediate analysis outside scheduled runs

```bash
# 1. Ensure dry run is off
python orchestrator.py settings set dry_run_mode false

# 2. Run analysis
python orchestrator.py analyze NVDA --type earnings

# 3. Verify output
ls -la tradegent_knowledge/knowledge/analysis/earnings/ | grep NVDA

# 4. Check indexing
python orchestrator.py status
```

---

## Enabling Paper Trading

**When:** Ready to test execution with paper account

```bash
# 1. Verify paper account connected
curl -s http://localhost:8100/health | jq '.account_type'
# Should show "paper"

# 2. Disable dry run
python orchestrator.py settings set dry_run_mode false

# 3. Enable auto-execute
python orchestrator.py settings set auto_execute_enabled true

# 4. Set stock to paper state
python orchestrator.py stock set-state NVDA paper

# 5. Run analysis (will execute if gate passes)
python orchestrator.py analyze NVDA

# 6. Check execution
python orchestrator.py status
```

---

## Re-indexing Knowledge Base

**When:** After embedding dimension change or data corruption

```bash
# 1. Stop service (prevent conflicts)
sudo systemctl stop tradegent

# 2. Clear existing indexes (optional - for full rebuild)
psql -h localhost -p 5433 -U lightrag -d lightrag -c "
TRUNCATE nexus.rag_documents CASCADE;
"

# Neo4j (optional)
cypher-shell -a bolt://localhost:7688 -u neo4j -p $NEO4J_PASS \
  "MATCH (n) WHERE NOT n:Ticker DETACH DELETE n"

# 3. Re-index all documents
python scripts/index_knowledge_base.py --force

# 4. Verify
python -c "
from rag.search import get_rag_stats
stats = get_rag_stats()
print(f'Docs: {stats.document_count}, Chunks: {stats.chunk_count}')
"

# 5. Restart service
sudo systemctl start tradegent
```

---

## Disaster Recovery

**When:** Major failure requiring full system restore

### Phase 1: Stop Everything

```bash
sudo systemctl stop tradegent tradegent-ib-mcp
docker compose down
```

### Phase 2: Assess Damage

```bash
# Check disk
df -h /opt/data

# Check Docker volumes
docker volume ls

# Check backups
ls -la ~/backups/
```

### Phase 3: Restore Data

```bash
# Start infrastructure only
docker compose up -d postgres neo4j

# Wait for healthy
docker compose ps

# Restore database
psql -h localhost -p 5433 -U lightrag -d lightrag < ~/backups/latest.sql

# Restore knowledge files
tar -xzf ~/backups/knowledge_latest.tar.gz -C /opt/data/tradegent_swarm/
```

### Phase 4: Re-index and Verify

```bash
# Initialize if needed
python orchestrator.py db-init

# Re-index
python scripts/index_knowledge_base.py --force

# Verify
python orchestrator.py status
```

### Phase 5: Restart Services

```bash
# Start IB Gateway
docker compose up -d ib-gateway

# Connect via VNC to complete login
vncviewer localhost:5900

# Start IB MCP
sudo systemctl start tradegent-ib-mcp

# Verify IB connection
curl -s http://localhost:8100/health

# Start main service
sudo systemctl start tradegent
```

---

## Handling Failed Analysis

**When:** Analysis shows failed status

```bash
# 1. Check error
psql -h localhost -p 5433 -U lightrag -c "
SELECT ticker, run_type, error_message, started_at
FROM nexus.run_history
WHERE status = 'failed'
ORDER BY started_at DESC LIMIT 5;
"

# 2. Check service logs
sudo journalctl -u tradegent -n 50 | grep -i error

# 3. Common fixes:
# - IB disconnected: vncviewer localhost:5900, reconnect
# - API error: Check API keys
# - Timeout: Increase timeouts or retry

# 4. Retry analysis
python orchestrator.py analyze TICKER --force
```

---

## Rotating API Keys

**When:** Security policy or key compromise

```bash
# 1. Get new keys from providers
# OpenAI: platform.openai.com
# Anthropic: console.anthropic.com

# 2. Update .env
nano tradegent/.env
# Change OPENAI_API_KEY, ANTHROPIC_API_KEY

# 3. Restart services
sudo systemctl restart tradegent tradegent-ib-mcp

# 4. Verify
python -c "
from rag.embedding_client import get_embedding
e = get_embedding('test')
print(f'OK: {len(e)} dimensions')
"
```

---

## Database Maintenance

**When:** Weekly or when performance degrades

```bash
# 1. Vacuum and analyze
psql -h localhost -p 5433 -U lightrag -c "
VACUUM ANALYZE nexus.rag_chunks;
VACUUM ANALYZE nexus.run_history;
"

# 2. Clear old run history (optional)
psql -h localhost -p 5433 -U lightrag -c "
DELETE FROM nexus.run_history
WHERE started_at < NOW() - INTERVAL '90 days';
"

# 3. Check sizes
psql -h localhost -p 5433 -U lightrag -c "
SELECT
  pg_size_pretty(pg_total_relation_size('nexus.rag_chunks')) as rag_chunks,
  pg_size_pretty(pg_total_relation_size('nexus.run_history')) as run_history;
"
```

---

## Service Log Rotation

**When:** Logs consuming too much disk

```bash
# 1. Check current log size
du -sh /var/log/journal/

# 2. Configure journald (edit /etc/systemd/journald.conf)
SystemMaxUse=500M
MaxFileSec=1week

# 3. Apply and vacuum
sudo systemctl restart systemd-journald
sudo journalctl --vacuum-size=500M
```

---

## Emergency Stop

**When:** Need to halt all trading activity immediately

```bash
# 1. Stop main service (stops all analyses/executions)
sudo systemctl stop tradegent

# 2. Enable dry run (prevents any future execution)
cd /opt/data/tradegent_swarm/tradegent
source .env
python orchestrator.py settings set dry_run_mode true
python orchestrator.py settings set auto_execute_enabled false

# 3. Verify
python orchestrator.py status
# Should show: Dry run mode: true
```

---

## Related Documentation

- [Deployment](deployment.md)
- [Monitoring](monitoring.md)
- [Troubleshooting](troubleshooting.md)
