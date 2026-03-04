# Observability

Unified observability using structlog, OpenTelemetry, and Prometheus.

## Logging

All services use structlog with JSON file output and log rotation (10MB x 5 backups).

| Service | Log File |
|---------|----------|
| orchestrator | `tradegent/logs/orchestrator.log` |
| service | `tradegent/logs/service.log` |
| tradegent_ui | `tradegent_ui/logs/agui.log` |

**View logs:**
```bash
tail -f tradegent/logs/orchestrator.log
tail -f tradegent_ui/logs/agui.log | jq .
grep "abc-123" tradegent_ui/logs/agui.log  # By correlation ID
```

**Enable debug:**
```bash
DEBUG=true python orchestrator.py ...
```

## Tracing (OpenTelemetry)

**Span Types:**
| Service | Span | Description |
|---------|------|-------------|
| tradegent | `pipeline.*` | Analysis pipeline phases |
| tradegent | `gen_ai.chat` | Claude Code LLM calls |
| tradegent_ui | `http.request` | FastAPI requests |
| tradegent_ui | `mcp.call.*` | MCP server calls |

## Metrics (Prometheus)

**tradegent:**
- `tradegent_llm_call_duration` - LLM call latency
- `tradegent_tokens_used` - Token usage
- `tradegent_analyses_total` - Completed analyses
- `tradegent_gate_results` - Gate pass/fail

**tradegent_ui:**
- `agentui_http_request_duration` - HTTP latency
- `agentui_mcp_call_duration` - MCP call latency
- `agentui_llm_tokens_input/output` - Token counts

## Correlation IDs

All services use B3 trace propagation:

```bash
curl -H "X-B3-TraceId: abc123" http://localhost:8081/api/chat ...
grep "abc123" tradegent_ui/logs/agui.log
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Enable debug logging |
| `OTEL_EXPORTER_TYPE` | `otlp` | Exporter type |
| `LOG_MAX_SIZE_MB` | `10` | Max log file size |
| `LOG_BACKUP_COUNT` | `5` | Rotation backups |

## Grafana Dashboards

Access at http://localhost:3000 (admin/admin):
- LLM Observability
- Agent UI
- System Health
