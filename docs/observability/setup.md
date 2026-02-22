# Observability Setup Guide

Step-by-step guide to setting up the TradegentSwarm observability stack.

---

## Prerequisites

- Docker and Docker Compose
- Python 3.11+
- 4GB+ available RAM (for full stack)

---

## Quick Start

### 1. Start Infrastructure

```bash
cd /opt/data/tradegent_swarm/tradegent/observability

# Start all services
docker compose -f docker-compose.observability.yml up -d

# Verify services are running
docker compose -f docker-compose.observability.yml ps
```

Expected output:
```
NAME                      STATUS    PORTS
tradegent-grafana         running   0.0.0.0:3000->3000/tcp
tradegent-loki            running   0.0.0.0:3100->3100/tcp
tradegent-otel-collector  running   0.0.0.0:4317->4317/tcp, 0.0.0.0:4318->4318/tcp
tradegent-prometheus      running   0.0.0.0:9090->9090/tcp
tradegent-promtail        running
tradegent-tempo           running   0.0.0.0:3200->3200/tcp
```

### 2. Install Python Dependencies

```bash
pip install \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-grpc \
    opentelemetry-propagator-b3
```

### 3. Verify Connectivity

```bash
# Check OTEL Collector
curl -s http://localhost:4317 || echo "gRPC endpoint ready"

# Check Tempo
curl -s http://localhost:3200/ready
# Expected: ready

# Check Loki
curl -s http://localhost:3100/ready
# Expected: ready

# Check Prometheus
curl -s http://localhost:9090/-/ready
# Expected: Prometheus Server is Ready.

# Check Grafana
curl -s http://localhost:3000/api/health
# Expected: {"database":"ok"}
```

### 4. Access Grafana

Open http://localhost:3000 in your browser.

- **Username**: `admin`
- **Password**: `admin`

Pre-configured datasources:
- Tempo (traces)
- Loki (logs)
- Prometheus (metrics)

---

## Configuration

### Environment Variables

Set these before running the orchestrator:

```bash
# Required: OTEL Collector endpoint
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Optional: Service identification
export OTEL_SERVICE_NAME=tradegent-orchestrator
export SERVICE_VERSION=1.0.0
export ENVIRONMENT=development

# Optional: Exporter type (otlp, console, none)
export OTEL_EXPORTER_TYPE=otlp

# Optional: Sampling rate (0.0 to 1.0)
export OTEL_SAMPLE_RATE=1.0

# Optional: Content capture (careful with costs/PII)
export OTEL_CAPTURE_PROMPTS=false
export OTEL_CAPTURE_COMPLETIONS=false
```

### Python Configuration

```python
from observability import TracingConfig, init_tracing

# Custom configuration
config = TracingConfig(
    service_name="tradegent-orchestrator",
    service_version="1.0.0",
    environment="production",

    exporter_type="otlp",
    otlp_endpoint="http://localhost:4317",
    otlp_insecure=True,

    sample_rate=1.0,  # 100% of traces

    # Content capture (disabled by default)
    capture_prompts=False,
    capture_completions=False,
    max_content_length=1000,
)

# Initialize at application startup
tracer = init_tracing(config)
```

---

## Service Ports Reference

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Grafana | 3000 | HTTP | Web UI |
| Tempo | 3200 | HTTP | Trace API |
| Tempo | 9095 | gRPC | Internal |
| Loki | 3100 | HTTP | Log API |
| Prometheus | 9090 | HTTP | Metrics API |
| OTEL Collector | 4317 | gRPC | OTLP receiver |
| OTEL Collector | 4318 | HTTP | OTLP HTTP |
| OTEL Collector | 8888 | HTTP | Collector metrics |

---

## Docker Compose Services

### Full Stack (Recommended)

```bash
docker compose -f docker-compose.observability.yml up -d
```

Includes:
- OpenTelemetry Collector
- Tempo (traces)
- Loki (logs)
- Prometheus (metrics)
- Promtail (log shipping)
- Grafana (visualization)

### Minimal Stack (Traces Only)

```bash
docker compose -f docker-compose.observability.yml up -d \
    otel-collector tempo grafana
```

### Development Mode (Console Output)

Set environment variable to log traces to console instead of sending to collector:

```bash
export OTEL_EXPORTER_TYPE=console
```

---

## Resource Requirements

| Service | RAM | CPU | Disk |
|---------|-----|-----|------|
| OTEL Collector | 256MB | 0.1 | - |
| Tempo | 512MB | 0.2 | 10GB |
| Loki | 512MB | 0.2 | 10GB |
| Prometheus | 512MB | 0.2 | 5GB |
| Grafana | 256MB | 0.1 | 100MB |
| **Total** | **~2GB** | **~0.8** | **~25GB** |

---

## Data Retention

Default retention settings:

| Service | Retention | Configuration |
|---------|-----------|---------------|
| Tempo | 48 hours | `tempo.yaml: block_retention` |
| Loki | 7 days | `loki.yaml: retention_period` |
| Prometheus | 15 days | `prometheus.yaml: --storage.tsdb.retention.time` |

### Adjusting Retention

**Tempo** (`config/tempo.yaml`):
```yaml
compactor:
  compaction:
    block_retention: 168h  # 7 days
```

**Loki** (`config/loki.yaml`):
```yaml
table_manager:
  retention_deletes_enabled: true
  retention_period: 336h  # 14 days
```

**Prometheus** (command line):
```yaml
command:
  - "--storage.tsdb.retention.time=30d"
```

---

## Security Considerations

### Production Deployment

1. **Enable Authentication**:
   ```yaml
   # Grafana
   environment:
     - GF_AUTH_ANONYMOUS_ENABLED=false
     - GF_SECURITY_ADMIN_PASSWORD=<strong-password>
   ```

2. **Use TLS**:
   ```yaml
   # OTEL Collector
   receivers:
     otlp:
       protocols:
         grpc:
           tls:
             cert_file: /etc/ssl/certs/collector.crt
             key_file: /etc/ssl/private/collector.key
   ```

3. **Network Isolation**:
   - Run observability stack on internal network
   - Use reverse proxy for Grafana access
   - Restrict OTEL Collector to known clients

### Content Capture

**Warning**: Enabling prompt/completion capture can:
- Expose sensitive trading data
- Increase storage costs significantly
- Impact performance

Only enable for debugging:
```bash
export OTEL_CAPTURE_PROMPTS=true
export OTEL_CAPTURE_COMPLETIONS=true
```

---

## Integration with Existing Infrastructure

### Using External Tempo

```python
config = TracingConfig(
    otlp_endpoint="https://tempo.your-company.com:4317",
    otlp_insecure=False,  # Use TLS
)
```

### Using Grafana Cloud

```yaml
# config/otel-collector-config.yaml
exporters:
  otlp/grafana:
    endpoint: tempo-prod-01-prod-us-east-0.grafana.net:443
    headers:
      authorization: "Basic <base64-encoded-credentials>"
```

### Using Datadog

```yaml
exporters:
  datadog:
    api:
      key: "${DD_API_KEY}"
```

---

## Verification Checklist

- [ ] All Docker containers running
- [ ] OTEL Collector receiving data (check :8888/metrics)
- [ ] Traces visible in Grafana → Explore → Tempo
- [ ] Logs visible in Grafana → Explore → Loki
- [ ] Metrics visible in Grafana → Explore → Prometheus
- [ ] Pre-built dashboard loading correctly
- [ ] Python SDK sending traces (check console output)

---

## Next Steps

1. [Instrument your code](instrumentation.md)
2. [Explore dashboards](dashboards.md)
3. [Learn querying](querying.md)
