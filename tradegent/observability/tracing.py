"""
OpenTelemetry tracing configuration for TradegentSwarm.

Supports multiple backends:
- Tempo (Grafana)
- Jaeger
- OTLP-compatible collectors
- Console (for debugging)
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter,
)
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat


@dataclass
class TracingConfig:
    """Configuration for OpenTelemetry tracing."""

    service_name: str = "tradegent-orchestrator"
    service_version: str = "1.0.0"
    environment: str = "development"

    # Exporter settings
    exporter_type: str = "otlp"  # otlp, console, none
    otlp_endpoint: str = "http://localhost:4317"
    otlp_insecure: bool = True

    # Sampling
    sample_rate: float = 1.0  # 1.0 = 100% of traces

    # Content capture (careful with PII/costs)
    capture_prompts: bool = False  # Log full prompts
    capture_completions: bool = False  # Log full completions
    max_content_length: int = 1000  # Truncate if capturing

    # Additional attributes
    extra_attributes: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "TracingConfig":
        """Load configuration from environment variables."""
        return cls(
            service_name=os.getenv("OTEL_SERVICE_NAME", "tradegent-orchestrator"),
            service_version=os.getenv("SERVICE_VERSION", "1.0.0"),
            environment=os.getenv("ENVIRONMENT", "development"),
            exporter_type=os.getenv("OTEL_EXPORTER_TYPE", "otlp"),
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
            otlp_insecure=os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true",
            sample_rate=float(os.getenv("OTEL_SAMPLE_RATE", "1.0")),
            capture_prompts=os.getenv("OTEL_CAPTURE_PROMPTS", "false").lower() == "true",
            capture_completions=os.getenv("OTEL_CAPTURE_COMPLETIONS", "false").lower() == "true",
        )


_tracer: Optional[trace.Tracer] = None
_config: Optional[TracingConfig] = None


def init_tracing(config: Optional[TracingConfig] = None) -> trace.Tracer:
    """
    Initialize OpenTelemetry tracing.

    Call once at application startup.

    Args:
        config: Tracing configuration. If None, loads from environment.

    Returns:
        Configured tracer instance.
    """
    global _tracer, _config

    if _tracer is not None:
        return _tracer

    _config = config or TracingConfig.from_env()

    # Build resource with service info
    resource = Resource.create(
        {
            SERVICE_NAME: _config.service_name,
            SERVICE_VERSION: _config.service_version,
            "deployment.environment": _config.environment,
            "service.instance.id": os.getenv("HOSTNAME", "local"),
            **_config.extra_attributes,
        }
    )

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add exporter based on config
    exporter = _create_exporter(_config)
    if exporter:
        provider.add_span_processor(BatchSpanProcessor(exporter))

    # Set as global provider
    trace.set_tracer_provider(provider)

    # Use B3 propagation (works with most systems)
    set_global_textmap(B3MultiFormat())

    _tracer = trace.get_tracer(
        _config.service_name,
        _config.service_version,
    )

    return _tracer


def _create_exporter(config: TracingConfig) -> Optional[SpanExporter]:
    """Create span exporter based on configuration."""
    if config.exporter_type == "none":
        return None
    elif config.exporter_type == "console":
        return ConsoleSpanExporter()
    elif config.exporter_type == "otlp":
        return OTLPSpanExporter(
            endpoint=config.otlp_endpoint,
            insecure=config.otlp_insecure,
        )
    else:
        raise ValueError(f"Unknown exporter type: {config.exporter_type}")


def get_tracer() -> trace.Tracer:
    """Get the initialized tracer, or initialize with defaults."""
    global _tracer
    if _tracer is None:
        return init_tracing()
    return _tracer


def get_config() -> TracingConfig:
    """Get current tracing configuration."""
    global _config
    if _config is None:
        init_tracing()
    return _config
