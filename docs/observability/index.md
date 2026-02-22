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

## Key Features

### LLM Observability (GenAI Semantic Conventions)

Track LLM calls with standard attributes:

| Attribute | Example |
|-----------|---------|
| `gen_ai.system` | `claude_code` |
| `gen_ai.request.model` | `claude-sonnet-4-20250514` |
| `gen_ai.usage.input_tokens` | `1523` |
| `gen_ai.usage.output_tokens` | `892` |
| `gen_ai.tool.name` | `mcp__ib-mcp__get_stock_price` |

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

```bash
# Required
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Optional
export OTEL_SERVICE_NAME=tradegent-orchestrator
export OTEL_EXPORTER_TYPE=otlp  # otlp, console, none
export OTEL_SAMPLE_RATE=1.0
export OTEL_CAPTURE_PROMPTS=false
export OTEL_CAPTURE_COMPLETIONS=false
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
