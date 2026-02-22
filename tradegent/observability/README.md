# TradegentSwarm Observability

OpenTelemetry-based observability stack with LLM-specific tracing using [GenAI semantic conventions](https://opentelemetry.io/blog/2024/llm-observability/).

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Observability Stack                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   orchestrator.py ──────┐                                               │
│   (LLMSpan, ToolCallSpan)│                                              │
│                          ▼                                              │
│                   ┌─────────────────┐                                   │
│                   │ OTEL Collector  │                                   │
│                   │   :4317 gRPC    │                                   │
│                   └────────┬────────┘                                   │
│                            │                                            │
│              ┌─────────────┼─────────────┐                              │
│              ▼             ▼             ▼                              │
│       ┌───────────┐ ┌───────────┐ ┌───────────┐                        │
│       │   Tempo   │ │   Loki    │ │Prometheus │                        │
│       │  (traces) │ │  (logs)   │ │ (metrics) │                        │
│       └─────┬─────┘ └─────┬─────┘ └─────┬─────┘                        │
│             └─────────────┼─────────────┘                               │
│                           ▼                                             │
│                    ┌───────────┐                                        │
│                    │  Grafana  │                                        │
│                    │   :3000   │                                        │
│                    └───────────┘                                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Start Observability Stack

```bash
cd tradegent/observability
docker compose -f docker-compose.observability.yml up -d
```

### 2. Install Python Dependencies

```bash
pip install opentelemetry-api opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-grpc \
    opentelemetry-propagator-b3
```

### 3. Initialize Tracing in orchestrator.py

```python
from observability import init_tracing, LLMSpan, GenAISystem

# Initialize at startup
init_tracing()

# Use in call_claude_code()
def call_claude_code(prompt, allowed_tools, label, timeout=None):
    ticker = label.split("-")[1] if "-" in label else None

    with LLMSpan(
        operation="chat",
        system=GenAISystem.CLAUDE_CODE,
        model="claude-sonnet-4-20250514",
        ticker=ticker,
        analysis_type="earnings",
        phase=1,
        phase_name="Fresh analysis",
        allowed_tools=allowed_tools,
    ) as span:
        span.set_prompt(prompt)

        result = subprocess.run([...])

        span.set_completion(result.stdout)
        span.set_output_length(len(result.stdout))

        return result.stdout
```

### 4. Access Dashboards

- **Grafana**: http://localhost:3000 (admin/admin)
- **Tempo**: http://localhost:3200
- **Prometheus**: http://localhost:9090

## GenAI Semantic Conventions

Following [OpenTelemetry GenAI](https://opentelemetry.io/docs/specs/semconv/gen-ai/):

| Attribute | Example | Description |
|-----------|---------|-------------|
| `gen_ai.system` | `claude_code` | LLM provider |
| `gen_ai.request.model` | `claude-sonnet-4-20250514` | Model used |
| `gen_ai.usage.input_tokens` | `1523` | Prompt tokens |
| `gen_ai.usage.output_tokens` | `892` | Completion tokens |
| `gen_ai.response.finish_reasons` | `["stop"]` | Why it stopped |
| `gen_ai.tool.name` | `mcp__ib-mcp__get_stock_price` | Tool called |

### Custom Tradegent Attributes

| Attribute | Example | Description |
|-----------|---------|-------------|
| `tradegent.ticker` | `NVDA` | Stock being analyzed |
| `tradegent.analysis_type` | `earnings` | Type of analysis |
| `tradegent.phase` | `1` | Pipeline phase |
| `tradegent.gate_passed` | `false` | Did gate pass |
| `tradegent.confidence` | `60` | Analysis confidence |

## Trace Visualization

Example trace waterfall in Tempo:

```
┌────────────────────────────────────────────────────────────────────────┐
│ pipeline.NVDA (4:05 total)                                              │
├────────────────────────────────────────────────────────────────────────┤
│ ├── phase.1.Fresh_analysis [3:26] ████████████████████████████████████ │
│ │   ├── gen_ai.chat [3:20] ███████████████████████████████████         │
│ │   │   ├── gen_ai.tool.mcp__ib-mcp__get_stock_price [3s] █            │
│ │   │   ├── gen_ai.tool.mcp__ib-mcp__get_historical [8s] ███           │
│ │   │   ├── gen_ai.tool.mcp__ib-mcp__get_option_chain [12s] █████      │
│ │   │   ├── gen_ai.tool.WebSearch [15s] ██████                         │
│ │   │   ├── gen_ai.tool.WebSearch [18s] ███████                        │
│ │   │   └── llm.reasoning [90s] ████████████████████████████████       │
│ ├── phase.2.Dual_ingest [0:37] ██                                       │
│ │   ├── tool.rag_embed [1s] ▌                                           │
│ │   └── tool.graph_extract [35s] █████████████████                     │
│ ├── phase.3.Retrieve_history [0:02] ▌                                   │
│ └── phase.4.Synthesize [<1s] ▌                                          │
└────────────────────────────────────────────────────────────────────────┘
```

## Grafana Dashboards

Pre-built dashboards included:

### LLM Observability Dashboard
- **Overview**: Avg call duration, total analyses, estimated cost, gate pass rate
- **Latency**: LLM call duration by phase (p50, p95)
- **Tool Calls**: Breakdown by tool type
- **Traces**: Recent trace explorer
- **Cost**: Token usage and estimated cost by ticker

## Configuration

### Environment Variables

```bash
# Tracing
export OTEL_SERVICE_NAME=tradegent-orchestrator
export OTEL_EXPORTER_TYPE=otlp  # otlp, console, none
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_SAMPLE_RATE=1.0

# Content capture (careful with costs/PII)
export OTEL_CAPTURE_PROMPTS=false
export OTEL_CAPTURE_COMPLETIONS=false
```

### Tracing Configuration

```python
from observability import TracingConfig, init_tracing

config = TracingConfig(
    service_name="tradegent-orchestrator",
    exporter_type="otlp",
    otlp_endpoint="http://localhost:4317",
    capture_prompts=True,  # Enable for debugging
    capture_completions=False,
    max_content_length=1000,
)

init_tracing(config)
```

## Files

```
observability/
├── __init__.py                 # Module exports
├── tracing.py                  # OpenTelemetry setup
├── llm_spans.py               # LLMSpan, ToolCallSpan, PipelineSpan
├── metrics.py                  # Prometheus metrics
├── docker-compose.observability.yml
├── config/
│   ├── otel-collector-config.yaml
│   ├── tempo.yaml
│   ├── loki.yaml
│   ├── prometheus.yaml
│   ├── promtail.yaml
│   └── grafana/
│       ├── provisioning/
│       │   ├── datasources/datasources.yaml
│       │   └── dashboards/dashboards.yaml
│       └── dashboards/
│           └── llm-observability.json
└── README.md
```

## Querying Traces

### TraceQL (Tempo)

```
# Find slow LLM calls
{ span.gen_ai.system = "claude_code" } | duration > 180s

# Find by ticker
{ span.tradegent.ticker = "NVDA" }

# Find failed gates
{ span.tradegent.gate_passed = false }

# Find specific tool calls
{ span.gen_ai.tool.name =~ "mcp__ib-mcp.*" }
```

### LogQL (Loki)

```
# Errors in Phase 1
{job="tradegent"} |= "Phase 1" |= "error"

# Filter by ticker
{job="tradegent"} | json | ticker="NVDA"

# Timing analysis
{job="tradegent"} | json | duration_sec > 200
```

### PromQL (Prometheus)

```
# Average LLM call duration
avg(tradegent_llm_call_duration_bucket)

# Token usage rate
sum(rate(tradegent_llm_tokens_total[5m])) by (type)

# Gate pass rate
sum(tradegent_gate_results_total{result="pass"}) /
sum(tradegent_gate_results_total)

# Cost per hour
sum(increase(tradegent_llm_cost_total[1h]))
```

## Troubleshooting

### No traces appearing in Tempo

1. Check OTEL Collector is running: `docker compose ps`
2. Check collector logs: `docker compose logs otel-collector`
3. Verify endpoint: `curl http://localhost:4317`

### Missing metrics

1. Check Prometheus targets: http://localhost:9090/targets
2. Verify metric names match in queries

### High cardinality warnings

Reduce cardinality by limiting unique label values:
- Don't use full prompts as labels
- Aggregate by phase, not individual tool calls
