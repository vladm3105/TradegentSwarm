# Observability Documentation

Comprehensive observability for TradegentSwarm using OpenTelemetry with LLM-specific tracing.

---

## Quick Links

| Document | Description |
|----------|-------------|
| [Overview](overview.md) | Architecture, components, GenAI conventions |
| [Setup Guide](setup.md) | Installation and configuration |
| [Instrumentation](instrumentation.md) | Adding tracing to code |
| [Dashboards](dashboards.md) | Grafana dashboard reference |
| [Querying](querying.md) | TraceQL, LogQL, PromQL examples |
| [Troubleshooting](troubleshooting.md) | Common issues and solutions |

---

## Quick Start

```bash
# 1. Start observability stack
cd tradegent/observability
docker compose -f docker-compose.observability.yml up -d

# 2. Install Python dependencies
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc

# 3. Initialize tracing in your code
from observability import init_tracing
init_tracing()

# 4. Access Grafana
open http://localhost:3000  # admin/admin
```

---

## Stack Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    Observability Stack                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │   Tempo     │     │    Loki     │     │ Prometheus  │       │
│  │  (traces)   │     │   (logs)    │     │  (metrics)  │       │
│  │   :3200     │     │   :3100     │     │   :9090     │       │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘       │
│         └────────────────────┼────────────────────┘             │
│                              ▼                                  │
│                       ┌─────────────┐                           │
│                       │   Grafana   │                           │
│                       │    :3000    │                           │
│                       └─────────────┘                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Services Covered

Both tradegent (orchestrator/service) and tradegent_ui are fully instrumented:

| Service | Traces | Metrics | Logs |
|---------|--------|---------|------|
| **tradegent** | Pipeline phases, LLM calls, tool executions | Analysis counts, gate results, token usage, costs | JSON to `logs/orchestrator.log`, exported to Loki |
| **tradegent_ui** | HTTP requests, MCP calls, **LLM calls (GenAI)** | Request latency, MCP latency, **LLM token usage** | JSON to `logs/agui.log`, exported to Loki |

### tradegent_ui Span Types

| Span | Description |
|------|-------------|
| `http.request.*` | FastAPI request handling with correlation |
| `mcp.call.trading-rag.*` | RAG MCP calls (search, embed) |
| `mcp.call.trading-graph.*` | Graph MCP calls (context, peers) |
| `mcp.call.ib-mcp.*` | IB MCP calls (positions, quotes) |
| `gen_ai.chat` | A2UI response generation (LLM) |
| `gen_ai.classify` | Intent classification (LLM) |

### Correlation Across Services

All services use B3 trace propagation. A single user request can be traced across:

```
User Request
    ↓
tradegent_ui (http.request span)
    ├── gen_ai.classify (intent classification)
    ├── mcp.call.trading-rag (RAG search)
    ├── gen_ai.chat (A2UI generation)
    ↓ B3 headers (if calling tradegent)
tradegent orchestrator (if triggered)
    ↓
Claude Code (gen_ai.chat span)
```

---

## Key Features

### LLM Observability (GenAI Semantic Conventions)

Track LLM calls with standard attributes:

| Attribute | Example |
|-----------|---------|
| `gen_ai.system` | `claude_code`, `openai`, `openrouter` |
| `gen_ai.request.model` | `claude-sonnet-4-20250514`, `gpt-4o-mini` |
| `gen_ai.operation.name` | `chat`, `classify` |
| `gen_ai.usage.input_tokens` | `1523` |
| `gen_ai.usage.output_tokens` | `892` |
| `gen_ai.response.finish_reasons` | `["stop"]` |
| `gen_ai.tool.name` | `mcp__ib-mcp__get_stock_price` |

**tradegent_ui LLM Spans:**

```
gen_ai.chat (A2UI generation)
├── gen_ai.system: openrouter
├── gen_ai.request.model: google/gemini-2.0-flash-001
├── gen_ai.usage.input_tokens: 1523
├── gen_ai.usage.output_tokens: 892
├── gen_ai.response.finish_reasons: ["stop"]
├── duration_ms: 1250.5
└── event: a2ui_generated {agent_type: "analysis", component_count: 3}

gen_ai.classify (Intent classification)
├── gen_ai.system: openrouter
├── gen_ai.request.model: google/gemini-2.0-flash-001
├── gen_ai.usage.input_tokens: 245
├── gen_ai.usage.output_tokens: 50
└── event: intent_classified {intent: "analysis", confidence: 0.95}
```

### Trace Visualization

```
pipeline.NVDA (4:05)
├── phase.1.Fresh_analysis [3:26]
│   └── gen_ai.chat [3:20]
│       ├── gen_ai.tool.mcp__ib-mcp__get_stock_price [3s]
│       ├── gen_ai.tool.WebSearch [15s]
│       └── llm.reasoning [90s]
├── phase.2.Dual_ingest [0:37]
├── phase.3.Retrieve_history [0:02]
└── phase.4.Synthesize [<1s]
```

### Pre-built Dashboards

- LLM call duration by phase
- Tool call breakdown
- Token usage and cost tracking
- Gate pass/fail rates
- Trace explorer

### Query Languages

- **TraceQL**: `{ span.tradegent.ticker = "NVDA" && duration > 3m }`
- **LogQL**: `{job="tradegent"} | json | ticker="NVDA"`
- **PromQL**: `histogram_quantile(0.95, tradegent_llm_call_duration_bucket)`

### tradegent_ui Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `agentui_http_request_duration` | Histogram | HTTP request latency |
| `agentui_mcp_call_duration` | Histogram | MCP call latency by server/tool |
| `agentui_mcp_calls_total` | Counter | Total MCP calls |
| `agentui_mcp_errors_total` | Counter | MCP call errors |
| `agentui_llm_call_duration` | Histogram | LLM API latency |
| `agentui_llm_tokens_input` | Counter | Input tokens used |
| `agentui_llm_tokens_output` | Counter | Output tokens generated |
| `agentui_intent_duration` | Histogram | Intent classification latency |

---

## Service Ports

| Service | Port | Purpose |
|---------|------|---------|
| Grafana | 3000 | Web UI |
| Tempo | 3200 | Trace API |
| Loki | 3100 | Log API |
| Prometheus | 9090 | Metrics API |
| OTEL Collector | 4317 | OTLP gRPC |

---

## File Structure

### Shared Observability Module (new)

```
shared/observability/
├── __init__.py           # Public API exports
├── config.py             # LoggingConfig, TracingConfig
├── logging_setup.py      # Unified structlog with rotation
├── correlation.py        # B3 trace propagation, correlation IDs
├── otel_logging.py       # OTEL log exporter (optional)
├── metrics_ui.py         # AgentUIMetrics
└── spans/
    ├── __init__.py
    ├── mcp_spans.py      # MCPCallSpan
    ├── http_spans.py     # HTTPRequestSpan
    └── llm_spans.py      # LLMSpan with GenAI conventions
```

### tradegent Observability Module (existing)

```
tradegent/observability/
├── __init__.py                 # Module exports
├── tracing.py                  # OpenTelemetry setup
├── llm_spans.py               # LLMSpan, ToolCallSpan, PipelineSpan
├── metrics.py                  # Prometheus metrics
├── README.md                   # Module documentation
├── docker-compose.observability.yml
└── config/
    ├── otel-collector-config.yaml
    ├── tempo.yaml
    ├── loki.yaml
    ├── prometheus.yaml
    ├── promtail.yaml
    └── grafana/
        ├── provisioning/
        └── dashboards/
```

---

## Environment Variables

### All Services

| Variable | Default | Description |
|----------|---------|-------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | OTEL Collector endpoint |
| `OTEL_EXPORTER_TYPE` | `otlp` | Exporter: otlp, console, none |
| `OTEL_LOGS_ENABLED` | `true` | Export logs to Loki |
| `OTEL_SAMPLE_RATE` | `1.0` | Trace sampling rate (0.0-1.0) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_MAX_SIZE_MB` | `10` | Max log file size |
| `LOG_BACKUP_COUNT` | `5` | Rotation backups |

### tradegent-specific

```bash
export OTEL_SERVICE_NAME=tradegent-orchestrator
export OTEL_CAPTURE_PROMPTS=false
export OTEL_CAPTURE_COMPLETIONS=false
```

### tradegent_ui-specific

```bash
export DEBUG=false  # Enable debug logging
```

---

## Common Tasks

### View Recent Traces

1. Open Grafana: http://localhost:3000
2. Go to: Explore → Tempo
3. Run query: `{ resource.service.name = "tradegent-orchestrator" }`

### Find Slow Analyses

TraceQL:
```traceql
{ span.tradegent.phase = 1 && duration > 3m }
```

### Check Token Usage

PromQL:
```promql
sum by (ticker) (increase(tradegent_llm_tokens_total[1h]))
```

### View Error Logs

LogQL:
```logql
{job="tradegent"} |= "error" | json
```

---

## Related Documentation

- [Architecture Overview](../architecture/overview.md)
- [MCP Servers](../architecture/mcp-servers.md)
- [Operations Guide](../operations/monitoring.md)
