# Observability Overview

Comprehensive observability for TradegentSwarm using OpenTelemetry with LLM-specific tracing based on [GenAI semantic conventions](https://opentelemetry.io/blog/2024/llm-observability/).

---

## Why Observability?

TradegentSwarm's analysis pipeline involves multiple components with varying latencies:

| Component | Typical Latency | Variability |
|-----------|----------------|-------------|
| Claude Code subprocess startup | 14s | Low |
| IB MCP tool calls | 3-15s each | Medium |
| Web search calls | 5-20s each | High |
| LLM reasoning | 60-120s | High |
| RAG embedding | 1-5s | Low |
| Graph extraction | 20-40s | Medium |

Without observability, identifying bottlenecks requires manual log analysis. With proper instrumentation, you can:

- **Visualize** the full request timeline (waterfall traces)
- **Identify** slow tool calls and phases
- **Track** token usage and cost
- **Alert** on anomalies (slow calls, failures)
- **Compare** performance across runs

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Observability Architecture                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ orchestrator│    │ Claude Code │    │  IB MCP     │    │  RAG/Graph  │  │
│  │   (Python)  │───▶│ subprocess  │───▶│   Server    │    │   MCPs      │  │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘  │
│         │                  │                  │                  │          │
│         │ OTLP             │ (logs)           │ OTLP             │ OTLP     │
│         ▼                  ▼                  ▼                  ▼          │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    OpenTelemetry Collector                            │  │
│  │                         :4317 (gRPC)                                  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│           │                    │                    │                       │
│           ▼                    ▼                    ▼                       │
│    ┌─────────────┐      ┌─────────────┐      ┌─────────────┐               │
│    │    Tempo    │      │    Loki     │      │ Prometheus  │               │
│    │   (traces)  │      │   (logs)    │      │  (metrics)  │               │
│    │    :3200    │      │    :3100    │      │    :9090    │               │
│    └──────┬──────┘      └──────┬──────┘      └──────┬──────┘               │
│           │                    │                    │                       │
│           └────────────────────┼────────────────────┘                       │
│                                ▼                                            │
│                         ┌─────────────┐                                     │
│                         │   Grafana   │                                     │
│                         │    :3000    │                                     │
│                         └─────────────┘                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### OpenTelemetry Collector

Central hub that receives telemetry data and routes to backends.

| Port | Protocol | Purpose |
|------|----------|---------|
| 4317 | gRPC | OTLP traces, metrics, logs |
| 4318 | HTTP | OTLP HTTP fallback |
| 8888 | HTTP | Collector metrics |

### Tempo (Traces)

Distributed tracing backend compatible with Jaeger, Zipkin.

| Port | Purpose |
|------|---------|
| 3200 | HTTP API |
| 9095 | gRPC |

**Features:**
- Trace search by attributes
- TraceQL query language
- Service graph generation
- Span metrics

### Loki (Logs)

Log aggregation system (like Prometheus for logs).

| Port | Purpose |
|------|---------|
| 3100 | HTTP API |

**Features:**
- LogQL query language
- Label-based filtering
- Log-to-trace correlation
- Retention policies

### Prometheus (Metrics)

Time-series metrics storage and alerting.

| Port | Purpose |
|------|---------|
| 9090 | HTTP API + Web UI |

**Features:**
- PromQL queries
- Histograms for latency
- Counters for throughput
- Alerting rules

### Grafana (Visualization)

Unified dashboard for all telemetry.

| Port | Purpose |
|------|---------|
| 3000 | Web UI |

**Features:**
- Pre-built dashboards
- Trace exploration
- Log search
- Metric visualization
- Alerting

---

## Data Flow

### Trace Flow

```
1. orchestrator.py creates PipelineSpan
2. Phase spans created as children
3. LLMSpan wraps Claude Code call
4. Tool calls create nested spans
5. Spans exported to OTEL Collector
6. Collector forwards to Tempo
7. Grafana queries Tempo for visualization
```

### Log Flow

```
1. Python logger emits structured JSON
2. Promtail scrapes logs (file or journald)
3. Promtail ships to Loki
4. Loki indexes by labels
5. Grafana queries Loki
6. Logs correlated to traces via trace_id
```

### Metric Flow

```
1. TradegentMetrics records measurements
2. OTEL SDK batches metrics
3. Exported to OTEL Collector
4. Collector remote-writes to Prometheus
5. Grafana queries Prometheus
```

---

## Trace Example

A complete analysis trace looks like:

```
┌────────────────────────────────────────────────────────────────────────────┐
│ pipeline.NVDA (4:05 total)                                                  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│ ├── phase.1.Fresh_analysis [3:26] ████████████████████████████████████     │
│ │   │                                                                      │
│ │   ├── gen_ai.chat NVDA [3:20] ████████████████████████████████████       │
│ │   │   │                                                                  │
│ │   │   ├── subprocess.startup [14s] ███████                               │
│ │   │   │                                                                  │
│ │   │   ├── gen_ai.tool.Read (SKILL.md) [0.5s] ▌                           │
│ │   │   │                                                                  │
│ │   │   ├── gen_ai.tool.mcp__ib-mcp__get_stock_price [3s] █▌               │
│ │   │   │   ticker: NVDA                                                   │
│ │   │   │   result_size: 245                                               │
│ │   │   │                                                                  │
│ │   │   ├── gen_ai.tool.mcp__ib-mcp__get_historical_data [8s] ████         │
│ │   │   │   duration: 3 M, bar_size: 1 day                                 │
│ │   │   │                                                                  │
│ │   │   ├── gen_ai.tool.mcp__ib-mcp__get_option_chain [12s] ██████         │
│ │   │   │   expiry: 2026-03                                                │
│ │   │   │                                                                  │
│ │   │   ├── gen_ai.tool.WebSearch [15s] ███████▌                           │
│ │   │   │   query: NVDA earnings estimates consensus                       │
│ │   │   │                                                                  │
│ │   │   ├── gen_ai.tool.WebSearch [18s] █████████                          │
│ │   │   │   query: NVDA analyst upgrades downgrades                        │
│ │   │   │                                                                  │
│ │   │   └── llm.reasoning [90s] ███████████████████████████████████████    │
│ │   │       input_tokens: 4523                                             │
│ │   │       output_tokens: 1892                                            │
│ │   │                                                                      │
│ │   └── output.generation [5s] ██▌                                         │
│ │                                                                          │
│ ├── phase.2.Dual_ingest [0:37] ██                                          │
│ │   │                                                                      │
│ │   ├── tool.rag_embed [1s] ▌                                              │
│ │   │   chunks: 1                                                          │
│ │   │                                                                      │
│ │   └── tool.graph_extract [35s] █████████████████                         │
│ │       entities: 16, relations: 12                                        │
│ │                                                                          │
│ ├── phase.3.Retrieve_history [0:02] ▌                                      │
│ │   past_analyses: 2                                                       │
│ │                                                                          │
│ └── phase.4.Synthesize [<1s] ▌                                             │
│     confidence: 65% → 60%                                                  │
│     modifiers: sparse_history, no_graph, pattern_confirms                  │
│                                                                            │
│ RESULT: Gate=FAIL, Rec=NEUTRAL, Conf=60%                                   │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## GenAI Semantic Conventions

Following [OpenTelemetry GenAI specifications](https://opentelemetry.io/docs/specs/semconv/gen-ai/):

### Standard Attributes

| Attribute | Type | Example | Description |
|-----------|------|---------|-------------|
| `gen_ai.system` | string | `claude_code` | LLM system identifier |
| `gen_ai.operation.name` | string | `chat` | Operation type |
| `gen_ai.request.model` | string | `claude-sonnet-4-20250514` | Model requested |
| `gen_ai.request.max_tokens` | int | `4096` | Max tokens limit |
| `gen_ai.request.temperature` | float | `0.7` | Sampling temperature |
| `gen_ai.response.model` | string | `claude-sonnet-4-20250514` | Model actually used |
| `gen_ai.response.finish_reasons` | string[] | `["stop"]` | Why generation stopped |
| `gen_ai.usage.input_tokens` | int | `1523` | Prompt tokens |
| `gen_ai.usage.output_tokens` | int | `892` | Completion tokens |
| `gen_ai.prompt` | string | `Analyze NVDA...` | Full prompt (optional) |
| `gen_ai.completion` | string | `Based on...` | Full response (optional) |
| `gen_ai.tool.name` | string | `mcp__ib-mcp__get_stock_price` | Tool/function name |

### Custom Tradegent Attributes

| Attribute | Type | Example | Description |
|-----------|------|---------|-------------|
| `tradegent.ticker` | string | `NVDA` | Stock symbol |
| `tradegent.analysis_type` | string | `earnings` | Analysis type |
| `tradegent.phase` | int | `1` | Pipeline phase number |
| `tradegent.phase_name` | string | `Fresh analysis` | Phase description |
| `tradegent.tool_calls_count` | int | `6` | Tools invoked |
| `tradegent.gate_passed` | bool | `false` | Gate result |
| `tradegent.recommendation` | string | `NEUTRAL` | Final recommendation |
| `tradegent.confidence` | float | `60` | Confidence percentage |
| `tradegent.expected_value_pct` | float | `5.2` | Expected value |
| `tradegent.allowed_tools` | string | `mcp__ib-mcp__*,...` | Tool allowlist |
| `tradegent.output_length` | int | `5838` | Output chars |

---

## Related Documentation

- [Setup Guide](setup.md) - Installation and configuration
- [Instrumentation Guide](instrumentation.md) - Adding tracing to code
- [Dashboards](dashboards.md) - Grafana dashboard reference
- [Querying](querying.md) - TraceQL, LogQL, PromQL examples
- [Troubleshooting](troubleshooting.md) - Common issues
