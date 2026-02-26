# Trading Knowledge Base Monitoring

## Overview

Metrics for graph extraction, embedding pipeline, hybrid search operations, and trading system monitoring (v2.3).

---

## Monitoring Skills Integration (v2.3)

The v2.3 monitoring modules integrate with Claude Code skills through a task queue system. This enables automated analysis and learning from trading events.

### Hybrid Implementation Model

Skills use Python handlers (free) by default, with optional Claude Code enhancement (paid):

| Skill | Python Handler | Claude Code | Cost |
|-------|----------------|-------------|------|
| `detected-position` | Creates basic trade entry | Full context analysis + thesis | $0.25-0.40 |
| `options-management` | Lists positions with metrics | Roll recommendations, Greeks analysis | $0.30-0.50 |
| `fill-analysis` | Slippage calculation, grade | N/A (Python only) | Free |
| `position-close-review` | P&L calculation, queue review | N/A (Python only) | Free |
| `expiration-review` | Final P&L, update trade | Lesson extraction | $0.20 |

### Task Type Mapping

| Monitor | Event | Task Type | Handler |
|---------|-------|-----------|---------|
| Position Monitor | Position increase detected | `detected_position` | `_process_detected_position_task` |
| Position Monitor | Position closed | `position_close_review` | `_process_position_close_review_task` |
| Order Reconciler | Order filled | `fill_analysis` | `_process_fill_analysis_task` |
| Expiration Monitor | Option expiring (<7 days) | `options_management` | `_process_options_management_task` |
| Expiration Monitor | Option expired | `expiration_review` | `_process_expiration_review_task` |

### Settings

```sql
-- Skill integration settings
SELECT key, value, description FROM nexus.settings WHERE category = 'skills';

-- Key settings:
-- skill_auto_invoke_enabled: true      -- Auto-process skill tasks
-- skill_use_claude_code: false         -- Use Claude Code for complex skills (costs $)
-- skill_daily_cost_limit: 5.00         -- Max daily spend on Claude Code
-- skill_cooldown_hours: 1              -- Hours between same skill for same ticker
-- detected_position_auto_create_trade: true  -- Auto-create trade for detected positions
-- fill_analysis_enabled: true          -- Enable fill quality analysis
-- position_close_review_enabled: true  -- Enable position close review
-- expiration_review_enabled: true      -- Enable expiration review
```

### Skill Invocation Tracking

```sql
-- View today's skill invocations
SELECT skill_name, ticker, invocation_type, status, cost_estimate,
       started_at, completed_at
FROM nexus.skill_invocations
WHERE started_at >= CURRENT_DATE
ORDER BY started_at DESC;

-- Daily cost summary
SELECT * FROM nexus.v_skill_daily_costs
ORDER BY date DESC
LIMIT 7;

-- Check for failed invocations
SELECT * FROM nexus.skill_invocations
WHERE status = 'failed'
ORDER BY started_at DESC
LIMIT 10;
```

### Enable Claude Code Mode

```bash
# Enable Claude Code for complex skills (costs money)
python tradegent.py settings set skill_use_claude_code true

# Set daily cost limit
python tradegent.py settings set skill_daily_cost_limit 10.00

# Disable specific skills
python tradegent.py settings set fill_analysis_enabled false
```

### Skill Handlers Module

The `skill_handlers.py` module provides the invocation infrastructure:

```python
from skill_handlers import invoke_skill_python, invoke_skill_claude

# Python handler (free)
result = invoke_skill_python(
    db=db,
    skill_name="fill_analysis",
    ticker="NVDA",
    context={"order_id": "123", "fill_price": 450.0}
)

# Claude Code handler (paid, if enabled)
result = invoke_skill_claude(
    db=db,
    skill_name="detected_position",
    ticker="NVDA",
    prompt="Analyze this externally-added position..."
)
```

**Available Python handlers:**
- `python_fill_analysis(db, ticker, context)` — Calculates slippage, grades fill
- `python_position_close_review(db, ticker, context)` — Calculates P&L, queues review
- `python_detected_position_basic(db, ticker, context)` — Creates trade entry
- `python_options_summary(db, ticker, context)` — Lists expiring positions
- `python_expiration_review(db, ticker, context)` — Updates expired trade status

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

**Deduplication:**

Notifications are deduplicated by event_type + ticker within a 5-minute window to prevent spam:
- Same position_closed event for NVDA won't repeat within 5 minutes
- Different event types (position_closed vs order_filled) are not deduplicated
- Different tickers are not deduplicated

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
python tradegent.py status

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
