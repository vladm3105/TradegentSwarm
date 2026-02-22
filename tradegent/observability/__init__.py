# Observability module for TradegentSwarm
# OpenTelemetry with GenAI semantic conventions

from .tracing import init_tracing, get_tracer, TracingConfig
from .llm_spans import (
    LLMSpan,
    ToolCallSpan,
    PipelineSpan,
    GenAISystem,
    FinishReason,
)
from .metrics import init_metrics, get_meter, TradegentMetrics

__all__ = [
    # Tracing setup
    "init_tracing",
    "get_tracer",
    "TracingConfig",
    # Span types
    "LLMSpan",
    "ToolCallSpan",
    "PipelineSpan",
    # Enums
    "GenAISystem",
    "FinishReason",
    # Metrics
    "init_metrics",
    "get_meter",
    "TradegentMetrics",
]
