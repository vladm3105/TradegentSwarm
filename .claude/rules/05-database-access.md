# Database Access

PostgreSQL stores all pipeline config, tickers, and results.
Schema in `tradegent/db/init.sql` + migrations in `tradegent/db/migrations/`

## Database Access Pattern (psycopg3)

```python
import sys
sys.path.insert(0, '.')
from db_layer import NexusDB  # NOT TradingDB

db = NexusDB()
db.connect()

# psycopg3 returns DICTS, not tuples - use row['column_name']
with db._conn.cursor() as cur:
    cur.execute("SELECT * FROM nexus.schedules")
    for row in cur.fetchall():
        print(row['name'])  # Correct
        # print(row[0])     # KeyError - rows are dicts

db.close()
```

## Common Mistakes to Avoid

| Mistake | Correct |
|---------|---------|
| `from db_layer import TradingDB` | `from db_layer import NexusDB` |
| `row[0]` (tuple access) | `row['column_name']` (dict access) |
| `db.execute_query(...)` | `db._conn.cursor().execute(...)` |
| Guessing column names | Query `information_schema.columns` first |
| `service_status.status` | `service_status.state` |
| `run_history.result_summary` | `run_history.raw_output` |
| `schedules.schedule_type` | `schedules.task_type` |
| `task_type = 'scanner'` | `task_type = 'run_scanner'` |

## Query Schema First Pattern

```python
# Always check columns before querying unfamiliar tables
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_schema = 'nexus' AND table_name = 'your_table'
    ORDER BY ordinal_position
""")
cols = [r['column_name'] for r in cur.fetchall()]
print(cols)
```

## Key Tables (nexus schema)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `stocks` | Watchlist stocks | ticker, state, is_enabled, priority |
| `schedules` | Automated tasks | name, task_type, frequency, next_run_at |
| `settings` | Config key-values | section, key, value |
| `service_status` | Service health | **state** (not status!), current_task |
| `run_history` | Scanner/analysis runs | task_type, ticker, status, raw_output |

## Knowledge Base Tables

| Table | Purpose |
|-------|---------|
| `kb_stock_analyses` | Stock analysis storage |
| `kb_earnings_analyses` | Earnings analysis storage |
| `kb_trade_journals` | Trade journal storage |
| `kb_watchlist_entries` | Watchlist storage |
| `kb_reviews` | All review types |

## Timezone Handling

All datetime comparisons must use timezone-aware objects:

```python
from zoneinfo import ZoneInfo
ET = ZoneInfo("America/New_York")
now = datetime.now(ET)  # Correct - timezone-aware
```

## Error Handling

| Error | Handling |
|-------|----------|
| `OperationalError` | Auto-reconnect with exponential backoff |
| `AdminShutdown` | Auto-reconnect (DB restart detected) |
| `InFailedSqlTransaction` | Auto-rollback and continue |
| 5+ consecutive DB errors | Service stops gracefully |
