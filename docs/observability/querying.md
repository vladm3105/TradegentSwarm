# Querying Guide

Query traces, logs, and metrics using TraceQL, LogQL, and PromQL.

---

## TraceQL (Tempo)

Query language for distributed traces.

### Basic Syntax

```traceql
{ <span-selector> } | <pipeline>
```

### Span Selectors

#### By Service
```traceql
{ resource.service.name = "tradegent-orchestrator" }
```

#### By Span Name
```traceql
{ name = "gen_ai.chat NVDA" }
{ name =~ "gen_ai.tool.*" }
```

#### By Attribute
```traceql
{ span.tradegent.ticker = "NVDA" }
{ span.tradegent.phase = 1 }
{ span.gen_ai.system = "claude_code" }
```

#### By Duration
```traceql
{ duration > 3m }
{ duration > 180s && duration < 300s }
```

#### By Status
```traceql
{ status = error }
{ status = ok }
```

### Combined Queries

```traceql
# Slow NVDA analyses
{ span.tradegent.ticker = "NVDA" && duration > 200s }

# Failed tool calls
{ name =~ "gen_ai.tool.*" && status = error }

# Phase 1 calls over 3 minutes
{ span.tradegent.phase = 1 && duration > 3m }
```

### Aggregations

```traceql
# Count by ticker
{ span.tradegent.ticker != "" } | count() by (span.tradegent.ticker)

# Average duration by phase
{ span.tradegent.phase != "" } | avg(duration) by (span.tradegent.phase)

# Max duration
{ name =~ "pipeline.*" } | max(duration)
```

### Pipeline Operations

```traceql
# Filter after selection
{ span.tradegent.ticker = "NVDA" } | duration > 100s

# Select specific attributes
{ name = "gen_ai.chat" } | select(span.gen_ai.usage.input_tokens)
```

---

## LogQL (Loki)

Query language for log aggregation.

### Basic Syntax

```logql
{<label-selector>} <pipeline>
```

### Label Selectors

#### By Job
```logql
{job="tradegent"}
```

#### By Multiple Labels
```logql
{job="tradegent", level="error"}
```

#### Label Matching
```logql
{job="tradegent", ticker=~"NVDA|AAPL"}
{job="tradegent", phase!="4"}
```

### Line Filters

#### Contains
```logql
{job="tradegent"} |= "Phase 1"
{job="tradegent"} |= "error" |= "timeout"
```

#### Does Not Contain
```logql
{job="tradegent"} != "DEBUG"
```

#### Regex
```logql
{job="tradegent"} |~ "NVDA.*COMPLETE"
```

### JSON Parsing

```logql
# Parse JSON logs
{job="tradegent"} | json

# Extract specific fields
{job="tradegent"} | json | ticker="NVDA"

# Filter by parsed field
{job="tradegent"} | json | duration_sec > 200
```

### Log Formatting

```logql
# Format output
{job="tradegent"} | json | line_format "{{.ticker}}: {{.event}} ({{.duration_sec}}s)"
```

### Aggregations

```logql
# Count errors per hour
sum(count_over_time({job="tradegent"} |= "error" [1h]))

# Rate of log lines
rate({job="tradegent"}[5m])

# Count by ticker
sum by (ticker) (count_over_time({job="tradegent"} | json [1h]))
```

### Useful Queries

```logql
# Find slow analyses
{job="tradegent"} | json | duration_sec > 300

# Find failed gates
{job="tradegent"} |= "Gate: FAIL"

# Find specific error messages
{job="tradegent"} |= "TimeoutExpired"

# Correlate with trace ID
{job="tradegent"} | json | trace_id="abc123"
```

---

## PromQL (Prometheus)

Query language for time-series metrics.

### Basic Syntax

```promql
metric_name{label="value"}
```

### Instant Vectors

```promql
# Current value
tradegent_analyses_total

# With label filter
tradegent_analyses_total{ticker="NVDA"}

# Regex match
tradegent_analyses_total{ticker=~"NVDA|AAPL"}

# Negative match
tradegent_analyses_total{recommendation!="ERROR"}
```

### Range Vectors

```promql
# Last 5 minutes of data
tradegent_llm_call_duration[5m]

# Last hour
tradegent_analyses_total[1h]
```

### Aggregation Operators

```promql
# Sum across all labels
sum(tradegent_analyses_total)

# Sum by ticker
sum by (ticker) (tradegent_analyses_total)

# Average duration
avg(tradegent_llm_call_duration)

# Max duration
max(tradegent_llm_call_duration)

# Count of series
count(tradegent_analyses_total)

# Top 5 by value
topk(5, tradegent_llm_call_duration)
```

### Functions

#### Rate (per-second change)
```promql
rate(tradegent_analyses_total[5m])
```

#### Increase (total change over time)
```promql
increase(tradegent_analyses_total[1h])
```

#### Histogram Quantiles
```promql
# 95th percentile
histogram_quantile(0.95, sum(rate(tradegent_llm_call_duration_bucket[5m])) by (le))

# 50th percentile by phase
histogram_quantile(0.50, sum(rate(tradegent_llm_call_duration_bucket[5m])) by (le, phase))
```

#### Delta (change between first and last)
```promql
delta(tradegent_llm_cost_total[1h])
```

### Operators

```promql
# Division (rate calculation)
sum(tradegent_gate_results_total{result="pass"}) /
sum(tradegent_gate_results_total)

# Multiplication
tradegent_llm_cost_total * 100

# Comparison
tradegent_llm_call_duration > 200000
```

### Common Queries

```promql
# Average LLM call duration
avg(tradegent_llm_call_duration)

# Analyses per hour
sum(increase(tradegent_analyses_total[1h]))

# Gate pass rate
sum(tradegent_gate_results_total{result="pass"}) /
sum(tradegent_gate_results_total) * 100

# Token usage rate (per minute)
sum(rate(tradegent_llm_tokens_total[5m])) by (type) * 60

# Cost per hour
sum(increase(tradegent_llm_cost_total[1h]))

# Slowest phase (average)
avg by (phase_name) (tradegent_pipeline_phase_duration)

# Tool call rate by tool
sum(rate(tradegent_tool_calls_total[5m])) by (tool)

# Error rate
sum(rate(tradegent_analyses_total{recommendation="ERROR"}[5m])) /
sum(rate(tradegent_analyses_total[5m]))
```

---

## Cross-System Queries

### Trace to Logs

In Grafana, traces link to logs via trace_id:

1. View trace in Tempo
2. Click "Logs for this span"
3. Jumps to Loki with filter: `{job="tradegent"} | json | trace_id="<trace-id>"`

### Metrics to Traces

Use exemplars to jump from metric to trace:

```promql
# Enable exemplars in histogram
histogram_quantile(0.95, sum(rate(tradegent_llm_call_duration_bucket[5m])) by (le))
```

Click on data point → "Query with Tempo"

### Logs to Traces

Extract trace_id from logs:

```logql
{job="tradegent"} | json | trace_id != ""
```

Click on trace_id → Opens in Tempo

---

## Query Examples by Use Case

### Performance Analysis

```promql
# Identify slow phases
avg by (phase_name) (tradegent_pipeline_phase_duration) / 1000
# Returns average duration in seconds per phase

# Compare ticker performance
histogram_quantile(0.95, sum(rate(tradegent_llm_call_duration_bucket[5m])) by (le, ticker))
```

```traceql
# Find outlier traces
{ span.tradegent.ticker != "" } | quantile(duration, 0.99) by (span.tradegent.ticker)
```

### Cost Analysis

```promql
# Total cost today
sum(increase(tradegent_llm_cost_total[24h]))

# Cost by ticker
sum by (ticker) (increase(tradegent_llm_cost_total[24h]))

# Token efficiency (output/input ratio)
sum(rate(tradegent_llm_tokens_total{type="output"}[1h])) /
sum(rate(tradegent_llm_tokens_total{type="input"}[1h]))
```

### Error Investigation

```logql
# Recent errors
{job="tradegent"} |= "error" | json | line_format "{{.ts}} {{.ticker}}: {{.message}}"
```

```traceql
# Failed traces
{ status = error && span.tradegent.ticker != "" }
```

### Capacity Planning

```promql
# Analyses per hour trend
sum(increase(tradegent_analyses_total[1h]))

# Peak concurrent analyses
max_over_time(tradegent_analyses_total[24h])

# Resource utilization pattern
avg by (hour) (tradegent_llm_call_duration)
```

---

## Query Performance Tips

### PromQL

1. Use `rate()` instead of `increase()` for graphs
2. Limit label cardinality
3. Use recording rules for complex queries

### LogQL

1. Use label filters before line filters
2. Limit time range
3. Use `| json` only when needed

### TraceQL

1. Be specific with span selectors
2. Use duration filters to reduce results
3. Limit aggregation cardinality

---

## Related Documentation

- [Dashboards](dashboards.md) - Visualization reference
- [Troubleshooting](troubleshooting.md) - Common issues
