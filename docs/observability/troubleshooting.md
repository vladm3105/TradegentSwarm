# Troubleshooting

Common issues and solutions for the observability stack.

---

## Service Health Checks

### Quick Status Check

```bash
# Check all containers
docker compose -f docker-compose.observability.yml ps

# Check individual service health
curl -s http://localhost:3200/ready  # Tempo
curl -s http://localhost:3100/ready  # Loki
curl -s http://localhost:9090/-/ready  # Prometheus
curl -s http://localhost:3000/api/health  # Grafana
```

### Container Logs

```bash
# View logs for specific service
docker compose -f docker-compose.observability.yml logs tempo
docker compose -f docker-compose.observability.yml logs loki
docker compose -f docker-compose.observability.yml logs otel-collector

# Follow logs
docker compose -f docker-compose.observability.yml logs -f otel-collector
```

---

## Common Issues

### No Traces Appearing in Tempo

**Symptoms:**
- Tempo shows "No traces found"
- Grafana Tempo datasource returns empty results

**Causes and Solutions:**

1. **OTEL Collector not receiving data**
   ```bash
   # Check collector metrics
   curl -s http://localhost:8888/metrics | grep otelcol_receiver
   ```

   If `otelcol_receiver_accepted_spans` is 0:
   - Verify Python SDK is initialized: `init_tracing()`
   - Check endpoint: `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317`

2. **Collector not forwarding to Tempo**
   ```bash
   # Check collector logs
   docker compose logs otel-collector | grep -i error
   ```

   Common fixes:
   - Verify `otel-collector-config.yaml` has correct Tempo endpoint
   - Check network connectivity: `docker network inspect observability`

3. **Tempo not ingesting**
   ```bash
   # Check Tempo logs
   docker compose logs tempo | grep -i error

   # Check Tempo metrics
   curl -s http://localhost:3200/metrics | grep tempo_distributor
   ```

4. **Wrong service name filter**
   - In Grafana, ensure you're searching for correct service name
   - Try removing all filters to see if any traces exist

### No Logs in Loki

**Symptoms:**
- Loki shows "No logs found"
- LogQL queries return empty

**Causes and Solutions:**

1. **Promtail not shipping logs**
   ```bash
   docker compose logs promtail | grep -i error
   ```

   Fixes:
   - Verify log path in `promtail.yaml`
   - Check Promtail can read log files (permissions)

2. **Wrong job label**
   ```logql
   # Try without job filter
   {} | json
   ```

3. **Logs not in expected format**
   ```bash
   # Check raw log format
   tail -f /var/log/tradegent.log
   ```

   Ensure logs are JSON formatted for parsing.

### Missing Metrics in Prometheus

**Symptoms:**
- Metrics queries return "No data"
- Graphs show gaps

**Causes and Solutions:**

1. **Metrics not being exported**
   ```python
   # Verify metrics initialization
   from observability import TradegentMetrics
   metrics = TradegentMetrics()
   metrics.record_llm_call(...)  # Should export
   ```

2. **Wrong metric name**
   ```bash
   # List all available metrics
   curl -s http://localhost:9090/api/v1/label/__name__/values | jq
   ```

3. **Prometheus not scraping**
   ```bash
   # Check targets
   curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets'
   ```

4. **Remote write failing**
   ```bash
   # Check collector logs for write errors
   docker compose logs otel-collector | grep -i "remote_write"
   ```

### Grafana Datasource Errors

**Symptoms:**
- "Datasource is not configured correctly"
- Red status indicators

**Causes and Solutions:**

1. **Service not reachable**
   - Verify service is running: `docker compose ps`
   - Check network: `docker network inspect observability`

2. **Wrong URL in datasource**
   - Tempo: `http://tempo:3200` (not localhost inside Docker)
   - Loki: `http://loki:3100`
   - Prometheus: `http://prometheus:9090`

3. **Authentication issues**
   - Verify no auth required (default setup)
   - Check Grafana logs: `docker compose logs grafana`

### High Memory Usage

**Symptoms:**
- Services OOM killed
- Slow queries

**Solutions:**

1. **Reduce retention**
   ```yaml
   # tempo.yaml
   compactor:
     compaction:
       block_retention: 24h  # Reduce from 48h
   ```

2. **Limit ingestion rate**
   ```yaml
   # loki.yaml
   limits_config:
     ingestion_rate_mb: 8  # Reduce from 16
   ```

3. **Increase resources**
   ```yaml
   # docker-compose.yml
   services:
     tempo:
       deploy:
         resources:
           limits:
             memory: 1G
   ```

### Traces Not Correlating with Logs

**Symptoms:**
- "Logs for this span" returns nothing
- trace_id not matching

**Solutions:**

1. **Ensure trace_id is logged**
   ```python
   from opentelemetry import trace

   ctx = trace.get_current_span().get_span_context()
   log.info("event", trace_id=format(ctx.trace_id, '032x'))
   ```

2. **Configure derived fields in Loki datasource**
   ```yaml
   # datasources.yaml
   jsonData:
     derivedFields:
       - datasourceUid: tempo
         matcherRegex: '"trace_id":"(\w+)"'
         name: TraceID
         url: '$${__value.raw}'
   ```

---

## Diagnostic Commands

### Test OTEL Collector Connectivity

```bash
# Send test trace via gRPC
grpcurl -plaintext localhost:4317 list

# Check health
curl http://localhost:8888/metrics | grep otelcol_exporter
```

### Test Tempo API

```bash
# Search for traces
curl -s 'http://localhost:3200/api/search' | jq

# Get trace by ID
curl -s 'http://localhost:3200/api/traces/<trace-id>' | jq
```

### Test Loki API

```bash
# Query logs
curl -s 'http://localhost:3100/loki/api/v1/query?query={job="tradegent"}' | jq

# Check label values
curl -s 'http://localhost:3100/loki/api/v1/labels' | jq
```

### Test Prometheus API

```bash
# Query metric
curl -s 'http://localhost:9090/api/v1/query?query=up' | jq

# List metrics
curl -s 'http://localhost:9090/api/v1/label/__name__/values' | jq
```

---

## Performance Tuning

### OTEL Collector

```yaml
# Increase batch size for high throughput
processors:
  batch:
    timeout: 5s
    send_batch_size: 4096
```

### Tempo

```yaml
# Increase query concurrency
querier:
  max_concurrent_queries: 20
```

### Loki

```yaml
# Increase chunk cache
chunk_store_config:
  chunk_cache_config:
    memcached:
      batch_size: 256
      parallelism: 100
```

### Prometheus

```bash
# Increase memory limits
--storage.tsdb.wal-segment-size=128MB
--query.max-concurrency=20
```

---

## Recovery Procedures

### Reset All Data

```bash
# Stop services
docker compose -f docker-compose.observability.yml down

# Remove volumes
docker volume rm tradegent_tempo-data tradegent_loki-data tradegent_prometheus-data

# Restart
docker compose -f docker-compose.observability.yml up -d
```

### Restart Individual Service

```bash
# Restart Tempo
docker compose -f docker-compose.observability.yml restart tempo

# Restart with fresh state
docker compose -f docker-compose.observability.yml rm -f tempo
docker compose -f docker-compose.observability.yml up -d tempo
```

### Export Data Before Reset

```bash
# Export Grafana dashboards
curl -s http://admin:admin@localhost:3000/api/dashboards/db/tradegent-llm > dashboard-backup.json

# Export Prometheus data (via snapshot)
curl -X POST http://localhost:9090/api/v1/admin/tsdb/snapshot
```

---

## Getting Help

### Log Locations

| Service | Log Command |
|---------|-------------|
| OTEL Collector | `docker compose logs otel-collector` |
| Tempo | `docker compose logs tempo` |
| Loki | `docker compose logs loki` |
| Prometheus | `docker compose logs prometheus` |
| Promtail | `docker compose logs promtail` |
| Grafana | `docker compose logs grafana` |

### Debug Mode

Enable debug logging:

```yaml
# otel-collector-config.yaml
service:
  telemetry:
    logs:
      level: debug
```

```yaml
# tempo.yaml
server:
  log_level: debug
```

### External Resources

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Grafana Tempo Documentation](https://grafana.com/docs/tempo/latest/)
- [Grafana Loki Documentation](https://grafana.com/docs/loki/latest/)
- [Prometheus Documentation](https://prometheus.io/docs/)
