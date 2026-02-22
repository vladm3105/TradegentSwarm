# Instrumentation Guide

How to add OpenTelemetry tracing to TradegentSwarm code.

---

## Overview

The observability module provides three main span types:

| Span Type | Purpose | Use Case |
|-----------|---------|----------|
| `PipelineSpan` | Top-level analysis span | Wrap entire analysis pipeline |
| `LLMSpan` | LLM/GenAI call span | Wrap Claude Code subprocess |
| `ToolCallSpan` | Tool/function call span | Wrap MCP tool calls |

---

## Basic Usage

### Initialize Tracing

Call once at application startup:

```python
from observability import init_tracing

# Initialize with defaults (reads from environment)
init_tracing()

# Or with explicit configuration
from observability import TracingConfig

config = TracingConfig(
    service_name="tradegent-orchestrator",
    otlp_endpoint="http://localhost:4317",
)
init_tracing(config)
```

### Pipeline Span

Wrap the entire analysis pipeline:

```python
from observability import PipelineSpan

def run_4phase_analysis(ticker: str, analysis_type: str):
    with PipelineSpan(
        ticker=ticker,
        analysis_type=analysis_type,
        run_id="NVDA-215014",
    ) as pipeline:

        # Phase 1
        with pipeline.phase(1, "Fresh analysis") as phase1:
            result = do_fresh_analysis(ticker)

        # Phase 2
        with pipeline.phase(2, "Dual ingest") as phase2:
            embed_result = embed_document(result)
            extract_result = extract_entities(result)

        # Phase 3
        with pipeline.phase(3, "Retrieve history") as phase3:
            history = get_history(ticker)

        # Phase 4
        with pipeline.phase(4, "Synthesize") as phase4:
            final = synthesize(result, history)

        # Record final result
        pipeline.set_result(
            gate_passed=final.gate_passed,
            recommendation=final.recommendation,
            confidence=final.confidence,
        )

        return final
```

### LLM Span

Wrap LLM calls with GenAI semantic conventions:

```python
from observability import LLMSpan, GenAISystem, FinishReason

def call_claude_code(prompt: str, allowed_tools: str, label: str):
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

        # Record prompt (optional, controlled by config)
        span.set_prompt(prompt)

        # Record subprocess command
        span.set_subprocess_cmd(["claude", "--print", ...])

        # Execute subprocess
        result = subprocess.run([
            "claude", "--print",
            "--dangerously-skip-permissions",
            "--allowedTools", allowed_tools,
            "-p", prompt,
        ], capture_output=True, text=True)

        # Record completion
        span.set_completion(result.stdout)
        span.set_output_length(len(result.stdout))

        # Set token counts (if available)
        span.set_tokens(input=1500, output=800)

        # Set finish reason
        if result.returncode == 0:
            span.set_finish_reason(FinishReason.STOP)
        else:
            span.set_finish_reason(FinishReason.ERROR)

        return result.stdout
```

### Tool Call Span

Track individual tool calls:

```python
from observability import ToolCallSpan

def call_ib_mcp(tool_name: str, params: dict, ticker: str):
    with ToolCallSpan(
        tool_name=f"mcp__ib-mcp__{tool_name}",
        ticker=ticker,
        arguments=params,
    ) as span:

        result = ib_client.call(tool_name, **params)

        span.set_result(result, result_size=len(str(result)))

        return result
```

### Nested Tool Calls within LLM Span

When tool calls happen during LLM execution:

```python
with LLMSpan(...) as llm_span:
    # Tool call as child of LLM span
    with llm_span.tool_call(
        "mcp__ib-mcp__get_stock_price",
        arguments={"symbol": "NVDA"}
    ) as tool_span:
        price = get_stock_price("NVDA")

    # Or add tool call record after the fact
    llm_span.add_tool_call(
        name="WebSearch",
        arguments={"query": "NVDA earnings"},
        duration_ms=15000,
    )
```

---

## Instrumenting orchestrator.py

### Full Integration Example

```python
# At the top of orchestrator.py
from observability import (
    init_tracing,
    PipelineSpan,
    LLMSpan,
    ToolCallSpan,
    GenAISystem,
    FinishReason,
    TradegentMetrics,
)

# Initialize at module load
init_tracing()
otel_metrics = TradegentMetrics()


def call_claude_code(
    prompt: str, allowed_tools: str, label: str, timeout: int | None = None
) -> str:
    """Execute a Claude Code CLI call with tracing."""
    timeout = timeout or cfg.claude_timeout
    ticker = label.split("-")[1] if "-" in label else "UNKNOWN"

    if cfg.dry_run_mode:
        log.info(f"[{label}] DRY RUN — would call Claude Code")
        return ""

    with LLMSpan(
        operation="chat",
        system=GenAISystem.CLAUDE_CODE,
        model="claude-sonnet-4-20250514",
        ticker=ticker,
        allowed_tools=allowed_tools,
    ) as span:

        log.info(f"[{label}] Calling Claude Code...")
        span.set_subprocess_cmd(["claude", "--print", ...])

        try:
            result = subprocess.run(
                [
                    cfg.claude_cmd,
                    "--print",
                    "--dangerously-skip-permissions",
                    "--allowedTools", allowed_tools,
                    "-p", prompt,
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(BASE_DIR),
            )

            if result.returncode != 0:
                log.error(f"[{label}] Error: {result.stderr[:500]}")
                span.set_finish_reason(FinishReason.ERROR)
                return ""

            span.set_output_length(len(result.stdout))
            span.set_finish_reason(FinishReason.STOP)

            # Record metrics
            otel_metrics.record_llm_call(
                duration_ms=span.metrics.duration_ms,
                input_tokens=span.metrics.input_tokens,
                output_tokens=span.metrics.output_tokens,
                ticker=ticker,
                analysis_type="analysis",
                phase=1,
            )

            log.info(f"[{label}] Completed ({len(result.stdout)} chars)")
            return result.stdout

        except subprocess.TimeoutExpired:
            log.error(f"[{label}] Timed out after {timeout}s")
            span.set_finish_reason(FinishReason.ERROR)
            return ""


def run_4phase_analysis(ticker: str, analysis_type: AnalysisType, ...):
    """Run 4-phase analysis pipeline with tracing."""

    with PipelineSpan(
        ticker=ticker,
        analysis_type=analysis_type.value,
        run_id=f"{ticker}-{datetime.now().strftime('%H%M%S')}",
    ) as pipeline:

        # Phase 1: Fresh analysis
        with pipeline.phase(1, "Fresh analysis"):
            prompt = build_analysis_prompt(ticker, analysis_type, ...)
            output = call_claude_code(prompt, cfg.allowed_tools_analysis, f"ANALYZE-{ticker}")

            if not output:
                return None

            filepath.write_text(output)

        # Phase 2: Dual ingest
        with pipeline.phase(2, "Dual ingest"):
            with ToolCallSpan("rag_embed", ticker=ticker) as rag_span:
                rag_result = embed_document(filepath)
                rag_span.set_result(rag_result, result_size=rag_result.chunks_created)

            with ToolCallSpan("graph_extract", ticker=ticker) as graph_span:
                graph_result = extract_document(filepath)
                graph_span.set_result(graph_result)

        # Phase 3: Retrieve history
        with pipeline.phase(3, "Retrieve history"):
            history = retrieve_history(ticker)

        # Phase 4: Synthesize
        with pipeline.phase(4, "Synthesize"):
            final = synthesize(output, history)

        # Record result
        pipeline.set_result(
            gate_passed=final.gate_passed,
            recommendation=final.recommendation,
            confidence=final.confidence,
        )

        # Record metrics
        otel_metrics.record_analysis_result(
            ticker=ticker,
            analysis_type=analysis_type.value,
            gate_passed=final.gate_passed,
            recommendation=final.recommendation,
            confidence=final.confidence,
        )

        return final
```

---

## Recording Metrics

### Using TradegentMetrics

```python
from observability import TradegentMetrics

metrics = TradegentMetrics()

# Record LLM call
metrics.record_llm_call(
    duration_ms=206000,
    input_tokens=1523,
    output_tokens=892,
    ticker="NVDA",
    analysis_type="earnings",
    phase=1,
)

# Record tool call
metrics.record_tool_call(
    tool_name="mcp__ib-mcp__get_stock_price",
    duration_ms=3000,
    ticker="NVDA",
)

# Record pipeline phase
metrics.record_phase(
    phase=2,
    phase_name="Dual ingest",
    duration_ms=37000,
    ticker="NVDA",
)

# Record analysis result
metrics.record_analysis_result(
    ticker="NVDA",
    analysis_type="earnings",
    gate_passed=False,
    recommendation="NEUTRAL",
    confidence=60.0,
)
```

### Available Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `tradegent.llm.call.duration` | histogram | ticker, analysis_type, phase | LLM call duration (ms) |
| `tradegent.llm.tokens.total` | counter | type, ticker | Token usage |
| `tradegent.llm.cost.total` | counter | ticker | Estimated cost (USD) |
| `tradegent.tool.call.duration` | histogram | tool, ticker | Tool call duration (ms) |
| `tradegent.tool.calls.total` | counter | tool, ticker | Tool call count |
| `tradegent.pipeline.phase.duration` | histogram | phase, phase_name, ticker | Phase duration (ms) |
| `tradegent.analyses.total` | counter | ticker, analysis_type, recommendation | Analysis count |
| `tradegent.gate.results.total` | counter | result, ticker | Gate pass/fail count |

---

## Structured Logging

Combine tracing with structured logging:

```python
import structlog
import json

# Configure structlog for JSON output
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)

log = structlog.get_logger()

# Log with trace context
from opentelemetry import trace

def call_claude_code(...):
    with LLMSpan(...) as span:
        # Get current trace/span IDs for log correlation
        ctx = trace.get_current_span().get_span_context()

        log.info(
            "claude_call_start",
            ticker=ticker,
            trace_id=format(ctx.trace_id, '032x'),
            span_id=format(ctx.span_id, '016x'),
            prompt_length=len(prompt),
        )

        # ... do work ...

        log.info(
            "claude_call_end",
            ticker=ticker,
            trace_id=format(ctx.trace_id, '032x'),
            span_id=format(ctx.span_id, '016x'),
            duration_sec=span.metrics.duration_ms / 1000,
            output_length=len(result.stdout),
        )
```

---

## Error Handling

Spans automatically capture exceptions:

```python
with LLMSpan(...) as span:
    try:
        result = risky_operation()
    except TimeoutError as e:
        # Span status automatically set to ERROR
        # Exception automatically recorded
        span.set_finish_reason(FinishReason.ERROR)
        raise  # Re-raise to propagate

    except ValueError as e:
        # Handle gracefully, but still record
        log.warning(f"Validation error: {e}")
        span.span.record_exception(e)
        return None
```

---

## Best Practices

### 1. Span Naming

```python
# Good: Descriptive, consistent
"pipeline.NVDA"
"phase.1.Fresh_analysis"
"gen_ai.chat NVDA"
"gen_ai.tool.mcp__ib-mcp__get_stock_price"

# Bad: Too generic
"analysis"
"call"
"tool"
```

### 2. Attribute Cardinality

```python
# Good: Bounded cardinality
span.set_attribute("tradegent.phase", 1)  # 1-4 values
span.set_attribute("tradegent.recommendation", "NEUTRAL")  # 4 values

# Bad: Unbounded cardinality (avoid)
span.set_attribute("tradegent.prompt_hash", hash(prompt))  # Infinite values
span.set_attribute("tradegent.timestamp", str(datetime.now()))  # Infinite
```

### 3. Content Capture

```python
# Only capture content when debugging
if os.getenv("OTEL_CAPTURE_PROMPTS") == "true":
    span.set_prompt(prompt)

# Or use built-in config
span.set_prompt(prompt)  # Respects TracingConfig.capture_prompts
```

### 4. Performance

```python
# Batch span creation for many small operations
from opentelemetry.trace import SpanKind

tracer = get_tracer()
with tracer.start_span("batch_operation") as parent:
    for item in items:
        with tracer.start_span(
            f"process_{item.id}",
            context=trace.set_span_in_context(parent),
            kind=SpanKind.INTERNAL,
        ) as child:
            process(item)
```

---

## Testing Instrumentation

### Console Exporter for Debugging

```python
from observability import TracingConfig, init_tracing

# Use console exporter during development
config = TracingConfig(exporter_type="console")
init_tracing(config)

# Now spans print to stdout
with LLMSpan(...) as span:
    ...
```

### Verify Traces Reach Tempo

```bash
# Send a test trace
python -c "
from observability import init_tracing, LLMSpan, GenAISystem
import time

init_tracing()

with LLMSpan(
    operation='test',
    system=GenAISystem.CLAUDE_CODE,
    ticker='TEST',
) as span:
    time.sleep(0.1)
    span.set_output_length(100)

print('Test trace sent')
"

# Check Tempo
curl -s 'http://localhost:3200/api/search?tags=tradegent.ticker%3DTEST' | jq
```

---

## Next Steps

- [View dashboards](dashboards.md)
- [Query traces](querying.md)
