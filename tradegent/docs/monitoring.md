# Trading Knowledge Base Monitoring

## Overview

Metrics for graph extraction, embedding pipeline, hybrid search operations, and trading system monitoring (v2.3).

---

## Trading Monitoring Modules (v2.3)

The service includes built-in monitoring modules that track positions, orders, watchlist conditions, and options expiration.

### Position Monitor

Detects IB position changes by comparing IB positions vs `nexus.trades`.

**Check Interval:** Every 5 minutes during market hours

**Detection Types:**
| Type | Trigger | Action |
|------|---------|--------|
| Full Close | Position gone from IB | Mark trade closed, calculate P&L |
| Partial Close | Position reduced | Update trade size |
| External Increase | New shares added | Log or auto-create trade |

**Settings:**
```sql
-- Check position monitoring settings
SELECT key, value FROM nexus.settings
WHERE key IN ('position_monitor_enabled', 'position_monitor_interval_seconds',
              'auto_track_position_increases', 'position_detect_min_value');
```

### Order Reconciler

Polls IB for order status updates on pending orders.

**Check Interval:** Every 2 minutes when orders are pending

**Status Handling:**
| IB Status | Action |
|-----------|--------|
| Filled | Update trade with fill price, send notification |
| Cancelled | Close trade with P&L=0 |
| Partial | Update trade with partial fill info |

**Settings:**
```sql
SELECT key, value FROM nexus.settings
WHERE key IN ('order_reconciler_enabled', 'order_reconcile_interval_seconds');
```

### Watchlist Monitor

Evaluates trigger/invalidation conditions on active watchlist entries.

**Check Interval:** Every 5 minutes during market hours

**Condition Types:**
| Condition | Example | Auto-Evaluated |
|-----------|---------|----------------|
| PRICE_ABOVE | "breaks above $150" | Yes |
| PRICE_BELOW | "drops below $140" | Yes |
| SUPPORT_HOLD | "holds $145 support" | Yes (3 consecutive checks) |
| DATE_BEFORE | "before 2026-03-15" | Yes |
| CUSTOM | Complex conditions | No (manual review) |

**Settings:**
```sql
SELECT key, value FROM nexus.settings
WHERE key IN ('watchlist_monitor_enabled', 'watchlist_check_interval_seconds',
              'watchlist_price_threshold_pct');
```

### Expiration Monitor

Tracks options approaching expiration.

**Check Interval:** Once daily

**Thresholds:**
| Level | Days Until Expiration | Action |
|-------|----------------------|--------|
| Warning | ≤ 7 days | Send warning notification |
| Critical | ≤ 3 days | Send critical notification |
| Expired | 0 days | Auto-close as worthless (unless ITM) |

**Settings:**
```sql
SELECT key, value FROM nexus.settings
WHERE key IN ('options_expiry_warning_days', 'options_expiry_critical_days',
              'auto_close_expired_options');
```

### Notifications

Multi-channel alert system for trading events.

**Channels:**
| Channel | Configuration | Status |
|---------|---------------|--------|
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` env vars | Check logs |
| Webhook | `webhook_url` setting | Check logs |
| Console | Always available | Always enabled |

**Events and Priorities:**
| Event | Priority | Module |
|-------|----------|--------|
| `position_closed` | HIGH | Position Monitor |
| `order_filled` | HIGH | Order Reconciler |
| `watchlist_triggered` | HIGH | Watchlist Monitor |
| `options_expiring` | MEDIUM/HIGH | Expiration Monitor |

**Check Notification Log:**
```sql
-- Recent notifications
SELECT event_type, priority, channel, sent_at, success
FROM nexus.notification_log
ORDER BY sent_at DESC
LIMIT 20;

-- Failures
SELECT * FROM nexus.notification_log
WHERE success = false
ORDER BY sent_at DESC;
```

**Settings:**
```sql
SELECT key, value FROM nexus.settings
WHERE key IN ('notifications_enabled', 'notification_min_priority', 'notification_rate_limit');
```

---

## Extraction Metrics

### Success Rate

Track via JSONL logs in `tradegent/logs/`:

```bash
# Count successful extractions (last 24h)
grep '"status": "success"' logs/extract_*.jsonl | wc -l

# Count failures
grep '"status": "error"' logs/extract_*.jsonl | wc -l

# Success rate calculation
success=$(grep -c '"status": "success"' logs/extract_*.jsonl 2>/dev/null || echo 0)
total=$(wc -l < logs/extract_*.jsonl 2>/dev/null || echo 1)
echo "Scale: $((success * 100 / total))%"
```

### Confidence Distribution

```sql
-- PostgreSQL: Check confidence levels for pending commits
SELECT
    confidence_bucket,
    COUNT(*) as count
FROM (
    SELECT
        CASE
            WHEN confidence >= 0.7 THEN 'auto_commit'
            WHEN confidence >= 0.5 THEN 'flagged'
            ELSE 'skipped'
        END as confidence_bucket
    FROM graph.pending_commits
    WHERE created_at > NOW() - INTERVAL '7 days'
) sub
GROUP BY confidence_bucket;
```

### Entity Extraction Stats

```python
from graph.layer import TradingGraph

with TradingGraph() as graph:
    stats = graph.get_stats()
    print(f"Total nodes: {stats['node_count']}")
    print(f"Total relationships: {stats['relationship_count']}")
    print(f"Labels: {stats['labels']}")
```

## Embedding Pipeline Metrics

### Embedding Throughput

```sql
-- Chunks embedded per hour
SELECT
    DATE_TRUNC('hour', embedded_at) as hour,
    COUNT(*) as chunks_embedded
FROM rag.chunks
WHERE embedded_at > NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', embedded_at)
ORDER BY hour DESC;
```

### Token Usage

```sql
-- Average tokens per chunk by doc type
SELECT
    doc_type,
    AVG(content_tokens) as avg_tokens,
    MAX(content_tokens) as max_tokens,
    COUNT(*) as chunk_count
FROM rag.chunks
GROUP BY doc_type;
```

### Embedding Model Status

```python
from rag.embedding import EmbeddingClient

client = EmbeddingClient()
status = client.health_check()
print(f"Primary (Ollama): {status.get('ollama', 'unavailable')}")
print(f"Fallback chain: {client.fallback_chain}")
```

## Search Performance

### Query Latency

```python
import time
from rag.search import semantic_search

start = time.time()
results = semantic_search("NVDA earnings thesis", top_k=5)
latency_ms = (time.time() - start) * 1000
print(f"Search latency: {latency_ms:.1f}ms")
print(f"Results returned: {len(results)}")
```

### Similarity Score Distribution

```sql
-- Check similarity scores from recent searches (if logged)
SELECT
    AVG(similarity) as avg_similarity,
    MIN(similarity) as min_similarity,
    MAX(similarity) as max_similarity
FROM rag.search_log
WHERE searched_at > NOW() - INTERVAL '24 hours';
```

## Pending Commits Queue

### Queue Depth

```sql
-- Pending commits awaiting review
SELECT
    status,
    COUNT(*) as count,
    MIN(created_at) as oldest,
    MAX(created_at) as newest
FROM graph.pending_commits
GROUP BY status;
```

### Retry Status

```sql
-- Failed commits with retry counts
SELECT
    doc_id,
    entity_type,
    retry_count,
    last_error,
    created_at
FROM graph.pending_commits
WHERE status = 'failed'
ORDER BY retry_count DESC
LIMIT 10;
```

## Health Checks

### Service Health

```bash
# Check all services
cd /opt/data/tradegent_swarm/tradegent
python -c "
from graph.layer import TradingGraph
from rag.embedding import EmbeddingClient
import psycopg

# Neo4j
with TradingGraph() as g:
    print(f'Neo4j: {\"OK\" if g.health_check() else \"FAIL\"}')

# Embedding
client = EmbeddingClient()
print(f'Embedding: {\"OK\" if client.health_check() else \"FAIL\"}')

# PostgreSQL
try:
    import os
    conn_str = os.getenv('DATABASE_URL', 'postgresql://lightrag:lightrag@localhost:5433/lightrag')
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT 1')
            print('PostgreSQL: OK')
except Exception as e:
    print(f'PostgreSQL: FAIL ({e})')
"
```

### Docker Health

```bash
cd /opt/data/tradegent_swarm/tradegent
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}"
```

## Alerting Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Extraction success rate | < 90% | < 80% |
| Pending queue depth | > 50 | > 100 |
| Average confidence | < 0.6 | < 0.5 |
| Search latency (p95) | > 500ms | > 1000ms |
| Embedding failures | > 5/hour | > 20/hour |

## Log Locations

| Component | Log Path | Format |
|-----------|----------|--------|
| Extraction | `logs/extract_YYYYMMDD.jsonl` | JSONL |
| Embedding | `logs/embed_YYYYMMDD.jsonl` | JSONL |
| MCP Servers | `logs/mcp_graph.log`, `logs/mcp_rag.log` | Text |
| Service | `logs/service.log` | Text |
| Docker | `docker compose logs <service>` | Text |

## Service Status

### Quick Health Check

```bash
# Service status
python orchestrator.py status

# Detailed service health
python service.py health
```

### Service Status Table

```sql
-- Current service state
SELECT
    state,
    last_heartbeat,
    last_tick_duration_ms,
    current_task,
    ticks_total,
    today_analyses,
    today_executions,
    today_errors
FROM nexus.service_status
WHERE id = 1;
```

### Trading Monitors Health

```python
# Check all monitors in one call
from service import Service

svc = Service()
print(f"Position Monitor: {'enabled' if svc._position_monitor else 'disabled'}")
print(f"Order Reconciler: {'enabled' if svc._order_reconciler else 'disabled'}")
print(f"Watchlist Monitor: {'enabled' if svc._watchlist_monitor else 'disabled'}")
print(f"Expiration Monitor: {'enabled' if svc._expiration_monitor else 'disabled'}")
print(f"Notifier: {'enabled' if svc._notifier else 'disabled'}")
```

### IB MCP Connectivity

```python
# Check IB MCP server health
from ib_client import IBClient

client = IBClient()
healthy = client.health_check()
print(f"IB MCP: {'connected' if healthy else 'disconnected'}")

# Test quote fetch
quote = client.get_stock_price("AAPL")
print(f"AAPL quote: {quote}")
```

### Monitor-Specific Checks

```python
# Position Monitor
from position_monitor import PositionMonitor
pm = PositionMonitor(db, ib_client)
deltas = pm.check_positions()
print(f"Position deltas: {len(deltas)}")

# Order Reconciler
from order_reconciler import OrderReconciler
recon = OrderReconciler(db, ib_client)
results = recon.reconcile_pending_orders()
print(f"Order reconciliation: {results}")

# Watchlist Monitor
from watchlist_monitor import WatchlistMonitor
wm = WatchlistMonitor(db, ib_client)
results = wm.check_entries()
print(f"Watchlist check: {results}")
```
