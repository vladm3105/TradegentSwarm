# Monitoring Guide

Monitor TradegentSwarm health, performance, and trading activity.

---

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Monitoring Stack                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Service    │  │  Database    │  │    Docker    │          │
│  │   Health     │  │   Metrics    │  │    Stats     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         │                 │                 │                   │
│         └─────────────────┼─────────────────┘                   │
│                           │                                     │
│                           ▼                                     │
│                    ┌──────────────┐                             │
│                    │   Alerts     │                             │
│                    └──────────────┘                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Health Checks

### Preflight Check (Recommended)

The preflight check verifies all services in one command:

```bash
# Full check (all services)
cd tradegent && python preflight.py --full

# Quick check (essential services only)
cd tradegent && python preflight.py
```

**Full Check Services:**

| Service | Check Type | Description |
|---------|------------|-------------|
| `postgres_container` | Docker | tradegent-postgres-1 container |
| `neo4j_container` | Docker | tradegent-neo4j-1 container |
| `ib_gateway` | Docker | paper-ib-gateway container health |
| `rag` | Python | pgvector connectivity (doc/chunk counts) |
| `graph` | Python | Neo4j connectivity (node/edge counts) |
| `ib_mcp` | HTTP | IB MCP server on port 8100 |
| `ib_gateway_port` | TCP | IB Gateway API port |
| `market` | Time | Market hours status |

### System Status

```bash
python orchestrator.py status
```

Output:
```
=== Tradegent Status ===
Database: Connected
Service: running
Today: 5 analyses, 2 executions
Dry run mode: false
```

### Service Health

```bash
# Main service
sudo systemctl status tradegent

# IB MCP
sudo systemctl status tradegent-ib-mcp

# Docker services
docker compose ps
```

### Database Health

```bash
# PostgreSQL
psql -h localhost -p 5433 -U tradegent -d tradegent -c "SELECT 1"

# Neo4j
curl -s http://localhost:7474/db/neo4j/cluster/available
```

### IB MCP Health

```bash
# Check if IB MCP server is responding on port 8100
curl -s http://localhost:8100/mcp -X GET 2>&1 | head -1
# Any HTTP response (including 406 or 307) means server is running
```

---

## Key Metrics

### Daily Metrics

| Metric | Query | Alert Threshold |
|--------|-------|-----------------|
| Analyses today | `run_history WHERE date = today` | < expected |
| Executions today | `run_history WHERE run_type = 'execution'` | > limit |
| Service uptime | `service_status.started_at` | < 1 hour |
| Last heartbeat | `service_status.last_heartbeat` | > 5 min ago |

### RAG Metrics

```sql
-- Document count
SELECT COUNT(*) FROM nexus.rag_documents;

-- Chunk count
SELECT COUNT(*) FROM nexus.rag_chunks;

-- Documents by ticker
SELECT ticker, COUNT(*) FROM nexus.rag_documents GROUP BY ticker;

-- Recent embeds
SELECT doc_id, created_at FROM nexus.rag_documents
ORDER BY created_at DESC LIMIT 10;
```

### Graph Metrics

```cypher
// Node counts by type
MATCH (n) RETURN labels(n) as type, count(n) as count;

// Relationship counts
MATCH ()-[r]->() RETURN type(r) as type, count(r) as count;

// Recent extractions
MATCH (d:Document) RETURN d.doc_id, d.created_at
ORDER BY d.created_at DESC LIMIT 10;
```

### Run History

```sql
-- Recent runs
SELECT ticker, run_type, status, started_at
FROM nexus.run_history
ORDER BY started_at DESC LIMIT 20;

-- Failed runs
SELECT ticker, run_type, error_message, started_at
FROM nexus.run_history
WHERE status = 'failed'
ORDER BY started_at DESC LIMIT 10;

-- Daily summary
SELECT
  DATE(started_at) as date,
  COUNT(*) as total,
  COUNT(*) FILTER (WHERE status = 'completed') as completed,
  COUNT(*) FILTER (WHERE status = 'failed') as failed
FROM nexus.run_history
WHERE started_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(started_at)
ORDER BY date DESC;
```

---

## Log Monitoring

### Service Logs

```bash
# Main service
sudo journalctl -u tradegent -f

# IB MCP
sudo journalctl -u tradegent-ib-mcp -f

# Last 100 lines
sudo journalctl -u tradegent -n 100
```

### Docker Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f postgres

# Last 100 lines
docker compose logs --tail=100 postgres
```

### Log Patterns

| Pattern | Meaning | Action |
|---------|---------|--------|
| `ERROR` | Error occurred | Investigate |
| `WARN` | Warning | Monitor |
| `timeout` | Connection timeout | Check service |
| `connection refused` | Service down | Restart |
| `rate limit` | API throttled | Reduce frequency |

---

## Alerting

### Critical Alerts

| Condition | Check | Response |
|-----------|-------|----------|
| Service down | systemctl status | Restart service |
| DB connection lost | SELECT 1 | Restart postgres |
| IB disconnected | health_check | Check VNC, reconnect |
| No heartbeat 5 min | service_status | Check service logs |

### Warning Alerts

| Condition | Check | Response |
|-----------|-------|----------|
| No analyses today | run_history | Verify schedule |
| Failed analysis | status = failed | Review error |
| High error rate | failed/total > 20% | Investigate |
| Disk > 80% | df -h | Clean up |

### Simple Alert Script

```bash
#!/bin/bash
# monitor.sh - Simple health check

# Check service
if ! systemctl is-active --quiet tradegent; then
  echo "ALERT: tradegent service down"
  # Send notification
fi

# Check database
if ! psql -h localhost -p 5433 -U tradegent -d tradegent -c "SELECT 1" > /dev/null 2>&1; then
  echo "ALERT: Database connection failed"
fi

# Check heartbeat
LAST_HEARTBEAT=$(psql -h localhost -p 5433 -U tradegent -d tradegent -t -c \
  "SELECT EXTRACT(EPOCH FROM NOW() - last_heartbeat) FROM nexus.service_status WHERE id = 1")

if [ "${LAST_HEARTBEAT%.*}" -gt 300 ]; then
  echo "ALERT: No heartbeat for ${LAST_HEARTBEAT%.*} seconds"
fi
```

### Cron Setup

```bash
# crontab -e
*/5 * * * * /opt/data/tradegent_swarm/scripts/monitor.sh 2>&1 | logger -t tradegent-monitor
```

---

## Dashboard Queries

### Overview Dashboard

```sql
-- System status
SELECT
  (SELECT status FROM nexus.service_status WHERE id = 1) as service_status,
  (SELECT COUNT(*) FROM nexus.stocks WHERE is_enabled = true) as enabled_stocks,
  (SELECT COUNT(*) FROM nexus.run_history WHERE DATE(started_at) = CURRENT_DATE) as runs_today,
  (SELECT COUNT(*) FROM nexus.rag_documents) as rag_documents,
  (SELECT value FROM nexus.settings WHERE key = 'dry_run_mode') as dry_run_mode;
```

### Performance Dashboard

```sql
-- Average run time by type
SELECT
  run_type,
  AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_seconds,
  COUNT(*) as count
FROM nexus.run_history
WHERE completed_at IS NOT NULL
  AND started_at > NOW() - INTERVAL '7 days'
GROUP BY run_type;
```

### Error Dashboard

```sql
-- Error summary
SELECT
  DATE(started_at) as date,
  run_type,
  COUNT(*) as error_count,
  array_agg(DISTINCT LEFT(error_message, 50)) as errors
FROM nexus.run_history
WHERE status = 'failed'
  AND started_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(started_at), run_type
ORDER BY date DESC;
```

---

## Troubleshooting Metrics

### Slow Analysis

```sql
-- Long running analyses
SELECT ticker, run_type, started_at,
  EXTRACT(EPOCH FROM (COALESCE(completed_at, NOW()) - started_at)) as seconds
FROM nexus.run_history
WHERE started_at > NOW() - INTERVAL '24 hours'
ORDER BY seconds DESC
LIMIT 10;
```

### Embedding Failures

```sql
-- Documents without embeddings
SELECT doc_id, file_path, created_at
FROM nexus.rag_documents
WHERE chunk_count = 0 OR chunk_count IS NULL;
```

### Graph Extraction Issues

```cypher
// Documents with few extractions
MATCH (d:Document)
WHERE NOT (d)<-[:EXTRACTED_FROM]-()
RETURN d.doc_id, d.file_path
LIMIT 10;
```

---

## Resource Monitoring

### Disk Usage

```bash
# Overall
df -h /opt/data

# Docker volumes
docker system df

# Database sizes
psql -h localhost -p 5433 -U tradegent -d tradegent -c "
SELECT pg_size_pretty(pg_database_size('tradegent')) as db_size;
"
```

### Memory Usage

```bash
# Services
ps aux | grep -E "(python|docker)" | awk '{print $4, $11}'

# Docker containers
docker stats --no-stream
```

### Connection Counts

```sql
-- PostgreSQL connections
SELECT count(*) FROM pg_stat_activity;
```

---

## Related Documentation

- [Deployment](deployment.md)
- [Troubleshooting](troubleshooting.md)
- [Runbooks](runbooks.md)
