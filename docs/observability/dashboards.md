# Grafana Dashboards

Pre-built dashboards for TradegentSwarm observability.

---

## Accessing Dashboards

1. Open Grafana: http://localhost:3000
2. Login: `admin` / `admin`
3. Navigate: **Dashboards** → **Tradegent** folder

---

## LLM Observability Dashboard

**Location**: Dashboards → Tradegent → Tradegent LLM Observability

### Overview Row

| Panel | Metric | Description |
|-------|--------|-------------|
| Avg LLM Call Duration | `avg(tradegent_llm_call_duration)` | Average Claude Code call time |
| Total Analyses | `sum(tradegent_analyses_total)` | Total analyses completed |
| Est. LLM Cost | `sum(tradegent_llm_cost_total)` | Estimated API cost (USD) |
| Gate Pass Rate | `pass / total` | Percentage of gates passed |

### LLM Call Latency Row

#### Duration by Phase
```
histogram_quantile(0.95, sum(rate(tradegent_llm_call_duration_bucket[5m])) by (le, phase))
histogram_quantile(0.50, sum(rate(tradegent_llm_call_duration_bucket[5m])) by (le, phase))
```

Shows p50 and p95 latency for each pipeline phase.

#### Tool Calls by Type
```
sum(increase(tradegent_tool_calls_total[1h])) by (tool)
```

Breakdown of tool calls (IB MCP, WebSearch, etc.).

### Traces Row

Embedded Tempo trace explorer showing recent traces.

**Filters available**:
- Service name
- Span name
- Duration range
- Attributes (ticker, phase, etc.)

### Token Usage & Cost Row

#### Token Usage by Ticker
```
sum(increase(tradegent_llm_tokens_total{type="input"}[1h])) by (ticker)
sum(increase(tradegent_llm_tokens_total{type="output"}[1h])) by (ticker)
```

#### Cost by Ticker
```
sum(increase(tradegent_llm_cost_total[1h])) by (ticker)
```

---

## Creating Custom Dashboards

### Step 1: Create New Dashboard

1. Click **+** → **Dashboard**
2. Add visualization

### Step 2: Add Panels

#### Trace Search Panel

1. Add panel → Select **Tempo** datasource
2. Query type: **Search**
3. Add filters:
   - `service.name = tradegent-orchestrator`
   - `tradegent.ticker = NVDA`

#### Metric Panel

1. Add panel → Select **Prometheus** datasource
2. Enter PromQL query
3. Configure visualization

#### Log Panel

1. Add panel → Select **Loki** datasource
2. Enter LogQL query:
   ```
   {job="tradegent"} | json
   ```

### Step 3: Add Variables

Create dashboard variables for dynamic filtering:

```yaml
Name: ticker
Type: Query
Datasource: Prometheus
Query: label_values(tradegent_analyses_total, ticker)
```

Use in queries:
```
tradegent_llm_call_duration{ticker="$ticker"}
```

---

## Panel Examples

### Analysis Timeline

Visualization: Time series

```promql
# Analyses over time by recommendation
sum(increase(tradegent_analyses_total[1h])) by (recommendation)
```

### Phase Duration Heatmap

Visualization: Heatmap

```promql
# Phase duration distribution
sum(rate(tradegent_pipeline_phase_duration_bucket[5m])) by (le, phase_name)
```

### Gate Results Pie Chart

Visualization: Pie chart

```promql
# Gate pass vs fail
sum(tradegent_gate_results_total) by (result)
```

### Slowest Tools Table

Visualization: Table

```promql
# Top 10 slowest tool calls
topk(10, avg(tradegent_tool_call_duration) by (tool))
```

### Error Rate

Visualization: Stat

```promql
# Error rate (last hour)
sum(increase(tradegent_analyses_total{recommendation="ERROR"}[1h])) /
sum(increase(tradegent_analyses_total[1h]))
```

---

## Annotations

Add analysis markers to graphs:

### Manual Annotation

1. Click on graph at desired time
2. Add annotation with tags: `analysis`, `NVDA`

### Automatic Annotations from Loki

```yaml
Name: Analyses
Datasource: Loki
Query: {job="tradegent"} |= "4-PHASE COMPLETE"
```

---

## Alerting

### Create Alert Rule

1. Go to panel → Edit
2. Alert tab → Create alert rule

### Example: Slow Analysis Alert

```yaml
Alert name: Slow Analysis
Condition: avg(tradegent_llm_call_duration) > 300000
For: 5m
Labels:
  severity: warning
Annotations:
  summary: "Analysis taking > 5 minutes"
  description: "Average LLM call duration is {{ $value }}ms"
```

### Example: High Cost Alert

```yaml
Alert name: High LLM Cost
Condition: sum(increase(tradegent_llm_cost_total[1h])) > 10
For: 0m
Labels:
  severity: warning
Annotations:
  summary: "LLM costs exceeded $10/hour"
```

---

## Dashboard JSON Export

Export dashboard for version control:

1. Dashboard settings (gear icon)
2. JSON Model
3. Copy JSON
4. Save to `config/grafana/dashboards/`

Dashboards in this directory auto-load on restart.

---

## Useful Links in Dashboard

Add links to related resources:

```yaml
Links:
  - title: "IB Gateway"
    url: "http://localhost:5900"  # VNC
  - title: "Orchestrator Logs"
    url: "/explore?left=[\"now-1h\",\"now\",\"Loki\",{\"expr\":\"{job=\\\"tradegent\\\"}\"}]"
```

---

## Dashboard Best Practices

### 1. Use Variables

```yaml
# Instead of hardcoding
tradegent_llm_call_duration{ticker="NVDA"}

# Use variables
tradegent_llm_call_duration{ticker="$ticker"}
```

### 2. Consistent Time Ranges

Use `$__interval` for rate calculations:
```promql
sum(rate(tradegent_tool_calls_total[$__interval])) by (tool)
```

### 3. Meaningful Colors

- Green: Success, pass
- Yellow: Warning, slow
- Red: Error, fail
- Blue: Informational

### 4. Clear Titles

```yaml
# Good
"LLM Call Duration by Phase (p95)"
"Tool Calls per Hour"

# Bad
"Duration"
"Calls"
```

---

## Related Documentation

- [Querying Guide](querying.md) - TraceQL, LogQL, PromQL
- [Troubleshooting](troubleshooting.md) - Common issues
