"""
OpenTelemetry metrics for TradegentSwarm.

Provides Prometheus-compatible metrics for:
- LLM call duration histograms
- Token usage counters
- Tool call latencies
- Pipeline phase durations
- Gate pass/fail rates
"""

import os
from typing import Optional

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME


_meter: Optional[metrics.Meter] = None


def init_metrics(
    service_name: str = "tradegent-orchestrator",
    otlp_endpoint: str = "http://localhost:4317",
    exporter_type: str = "otlp",
) -> metrics.Meter:
    """
    Initialize OpenTelemetry metrics.

    Args:
        service_name: Name of the service
        otlp_endpoint: OTLP collector endpoint
        exporter_type: 'otlp', 'console', or 'none'

    Returns:
        Configured meter instance
    """
    global _meter

    if _meter is not None:
        return _meter

    resource = Resource.create({SERVICE_NAME: service_name})

    # Create exporter
    if exporter_type == "otlp":
        exporter = OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)
    elif exporter_type == "console":
        exporter = ConsoleMetricExporter()
    else:
        exporter = None

    # Create meter provider
    if exporter:
        reader = PeriodicExportingMetricReader(exporter, export_interval_millis=10000)
        provider = MeterProvider(resource=resource, metric_readers=[reader])
    else:
        provider = MeterProvider(resource=resource)

    metrics.set_meter_provider(provider)
    _meter = metrics.get_meter(service_name)

    return _meter


def get_meter() -> metrics.Meter:
    """Get the initialized meter, or initialize with defaults."""
    global _meter
    if _meter is None:
        return init_metrics(
            exporter_type=os.getenv("OTEL_EXPORTER_TYPE", "otlp"),
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
        )
    return _meter


# Pre-defined metrics
class TradegentMetrics:
    """
    Pre-defined metrics for Tradegent.

    Usage:
        metrics = TradegentMetrics()
        metrics.llm_call_duration.record(3260, {"ticker": "NVDA", "phase": "1"})
        metrics.tokens_used.add(2300, {"type": "input"})
    """

    def __init__(self):
        meter = get_meter()

        # LLM call duration histogram (milliseconds)
        self.llm_call_duration = meter.create_histogram(
            name="tradegent.llm.call.duration",
            description="Duration of LLM calls in milliseconds",
            unit="ms",
        )

        # Token usage counter
        self.tokens_used = meter.create_counter(
            name="tradegent.llm.tokens.total",
            description="Total tokens used",
            unit="tokens",
        )

        # Tool call duration histogram
        self.tool_call_duration = meter.create_histogram(
            name="tradegent.tool.call.duration",
            description="Duration of tool calls in milliseconds",
            unit="ms",
        )

        # Tool call counter
        self.tool_calls = meter.create_counter(
            name="tradegent.tool.calls.total",
            description="Total tool calls made",
            unit="calls",
        )

        # Pipeline phase duration
        self.phase_duration = meter.create_histogram(
            name="tradegent.pipeline.phase.duration",
            description="Duration of pipeline phases in milliseconds",
            unit="ms",
        )

        # Analysis counter (by result)
        self.analyses_total = meter.create_counter(
            name="tradegent.analyses.total",
            description="Total analyses completed",
            unit="analyses",
        )

        # Gate pass/fail counter
        self.gate_results = meter.create_counter(
            name="tradegent.gate.results.total",
            description="Gate pass/fail counts",
            unit="checks",
        )

        # Cost counter (estimated USD)
        self.estimated_cost = meter.create_counter(
            name="tradegent.llm.cost.total",
            description="Estimated LLM cost in USD",
            unit="USD",
        )

        # Subprocess startup time
        self.subprocess_startup = meter.create_histogram(
            name="tradegent.subprocess.startup.duration",
            description="Claude Code subprocess startup time",
            unit="ms",
        )

    def record_llm_call(
        self,
        duration_ms: float,
        input_tokens: int,
        output_tokens: int,
        ticker: str,
        analysis_type: str,
        phase: int,
    ):
        """Record metrics for an LLM call."""
        labels = {
            "ticker": ticker,
            "analysis_type": analysis_type,
            "phase": str(phase),
        }

        self.llm_call_duration.record(duration_ms, labels)
        self.tokens_used.add(input_tokens, {"type": "input", **labels})
        self.tokens_used.add(output_tokens, {"type": "output", **labels})

        # Estimate cost (Claude Sonnet pricing)
        cost = (input_tokens / 1_000_000) * 3.0 + (output_tokens / 1_000_000) * 15.0
        self.estimated_cost.add(cost, labels)

    def record_tool_call(
        self,
        tool_name: str,
        duration_ms: float,
        ticker: Optional[str] = None,
    ):
        """Record metrics for a tool call."""
        labels = {"tool": tool_name}
        if ticker:
            labels["ticker"] = ticker

        self.tool_call_duration.record(duration_ms, labels)
        self.tool_calls.add(1, labels)

    def record_phase(
        self,
        phase: int,
        phase_name: str,
        duration_ms: float,
        ticker: str,
    ):
        """Record metrics for a pipeline phase."""
        labels = {
            "phase": str(phase),
            "phase_name": phase_name,
            "ticker": ticker,
        }
        self.phase_duration.record(duration_ms, labels)

    def record_analysis_result(
        self,
        ticker: str,
        analysis_type: str,
        gate_passed: bool,
        recommendation: str,
        confidence: float,
    ):
        """Record metrics for a completed analysis."""
        labels = {
            "ticker": ticker,
            "analysis_type": analysis_type,
            "recommendation": recommendation,
        }

        self.analyses_total.add(1, labels)
        self.gate_results.add(1, {"result": "pass" if gate_passed else "fail", **labels})
