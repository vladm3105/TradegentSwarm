# Metabase Portal Dashboard Setup

## Quick Setup (Automated)

```bash
cd /opt/data/tradegent_swarm/tradegent

# Run setup script
python dashboard/setup_metabase_portal.py \
  --email your-admin@example.com \
  --password your-password
```

## Manual Setup

### Step 1: Login to Metabase

Open http://localhost:3001 and login with your admin account.

### Step 2: Create Portal Dashboard

1. Click **New** → **Dashboard**
2. Name: `📈 Tradegent Portal`
3. Description: `Trading platform home - links, metrics, and quick access`

### Step 3: Add Header Card

Click **+** → **Text** and paste:

```markdown
# 📈 Tradegent Trading Platform

Welcome to your trading command center.

---

## 🔗 Quick Links

| Tool | URL | Purpose |
|------|-----|---------|
| **Streamlit** | [localhost:8501](http://localhost:8501) | Custom dashboards, RAG search |
| **Neo4j Browser** | [localhost:7475](http://localhost:7475) | Knowledge graph |
| **IB Gateway** | [localhost:5902](http://localhost:5902) | Paper trading (VNC) |

---
```

### Step 4: Add Metric Cards

Click **+** → **Question** → **Native query** for each:

**Active Stocks:**
```sql
SELECT COUNT(*) as "Active Stocks"
FROM nexus.stocks
WHERE is_enabled = true
```
Display: Number

**Analyses (7 days):**
```sql
SELECT COUNT(*) as "Analyses"
FROM nexus.analysis_results
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
```
Display: Number

**Open Trades:**
```sql
SELECT COUNT(*) as "Open Trades"
FROM nexus.trades
WHERE status = 'open'
```
Display: Number

### Step 5: Add Recent Analyses Table

```sql
SELECT
    ticker as "Ticker",
    analysis_type::text as "Type",
    recommendation as "Rec",
    confidence || '%' as "Conf",
    CASE WHEN gate_passed THEN '✓' ELSE '✗' END as "Gate",
    TO_CHAR(created_at, 'MM-DD HH24:MI') as "Date"
FROM nexus.analysis_results
ORDER BY created_at DESC
LIMIT 10
```
Display: Table

### Step 6: Add Service Status

```sql
SELECT
    state as "State",
    TO_CHAR(last_heartbeat, 'HH24:MI:SS') as "Last Heartbeat",
    analyses_total as "Total Analyses",
    today_analyses as "Today",
    CASE
        WHEN last_heartbeat > NOW() - INTERVAL '5 minutes' THEN '🟢 Healthy'
        WHEN last_heartbeat > NOW() - INTERVAL '15 minutes' THEN '🟡 Degraded'
        ELSE '🔴 Unhealthy'
    END as "Health"
FROM nexus.service_status
```
Display: Table

### Step 7: Add Knowledge Base Chart

```sql
SELECT
    doc_type as "Type",
    COUNT(*) as "Documents"
FROM nexus.rag_documents
GROUP BY doc_type
ORDER BY COUNT(*) DESC
```
Display: Bar Chart

### Step 8: Add Stock Watchlist

```sql
SELECT
    ticker as "Ticker",
    state as "State",
    priority as "Priority",
    default_analysis_type::text as "Type",
    TO_CHAR(next_earnings_date, 'MM-DD') as "Earnings"
FROM nexus.stocks
WHERE is_enabled = true
ORDER BY priority DESC
LIMIT 10
```
Display: Table

### Step 9: Set as Homepage

1. Go to **Settings** (gear icon) → **Admin settings**
2. Click **Homepage** in sidebar
3. Select **A specific dashboard**
4. Choose **📈 Tradegent Portal**
5. Save

## Dashboard Layout

```
┌────────────────────────────────────────────────────────────┐
│  📈 Tradegent Trading Platform                             │
│  [Quick Links: Streamlit | Neo4j | IB Gateway]             │
├──────────────┬──────────────┬──────────────────────────────┤
│ Active       │ Analyses     │ Open Trades                  │
│ Stocks: 20   │ (7d): 15     │ 3                            │
├──────────────┴──────────────┴──────────────────────────────┤
│  Recent Analyses                                            │
│  ┌─────────┬──────┬─────────┬──────┬──────┬───────────────┐│
│  │ Ticker  │ Type │ Rec     │ Conf │ Gate │ Date          ││
│  ├─────────┼──────┼─────────┼──────┼──────┼───────────────┤│
│  │ NVDA    │ stk  │ BUY     │ 75%  │ ✓    │ 02-28 14:30   ││
│  │ ZIM     │ stk  │ BUY     │ 75%  │ ✓    │ 02-28 16:45   ││
│  └─────────┴──────┴─────────┴──────┴──────┴───────────────┘│
├────────────────────────────┬───────────────────────────────┤
│  Service Status            │  Stock Watchlist              │
│  🟢 Healthy                │  NVDA, AAPL, GOOGL...         │
├────────────────────────────┴───────────────────────────────┤
│  Knowledge Base Stats (Bar Chart)                          │
│  [stock-analysis: 55] [earnings: 34] [research: 8]         │
└────────────────────────────────────────────────────────────┘
```

## Additional Dashboards to Create

After the portal, consider creating:

1. **Trade Performance** - P&L charts, win rate, by ticker
2. **Analysis History** - Filterable analysis list
3. **Forecast Accuracy** - Calibration tracking
4. **Knowledge Growth** - RAG/Graph metrics over time

## Useful BI Views

Pre-built views for dashboards:

| View | Description |
|------|-------------|
| `nexus.v_bi_daily_pnl` | Daily P&L aggregation |
| `nexus.v_bi_weekly_pnl` | Weekly with profit factor |
| `nexus.v_bi_monthly_pnl` | Monthly with cumulative |
| `nexus.v_bi_ticker_performance` | By ticker stats |
| `nexus.v_bi_analysis_performance` | Analysis metrics |
| `nexus.v_bi_recommendation_distribution` | Weekly patterns |
| `nexus.v_bi_rag_stats` | Knowledge base stats |
| `nexus.v_bi_service_health` | Service monitoring |
