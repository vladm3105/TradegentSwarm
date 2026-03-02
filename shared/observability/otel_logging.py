"""OpenTelemetry log export to Loki via OTEL Collector."""
import logging

try:
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.resources import Resource

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False


def init_otel_logging(
    service_name: str,
    otlp_endpoint: str = "http://localhost:4317",
) -> logging.Handler:
    """Initialize OTEL log exporter.

    Sends logs to OTEL Collector -> Loki for centralized log aggregation.
    Logs include trace_id/span_id for correlation with traces.

    Args:
        service_name: Service identifier
        otlp_endpoint: OTEL Collector gRPC endpoint

    Returns:
        logging.Handler to attach to Python logger

    Raises:
        ImportError: If OTEL dependencies not installed
    """
    if not OTEL_AVAILABLE:
        raise ImportError(
            "OpenTelemetry logging dependencies not installed. "
            "Install with: pip install opentelemetry-exporter-otlp-proto-grpc"
        )

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": "1.0.0",
        }
    )

    logger_provider = LoggerProvider(resource=resource)
    set_logger_provider(logger_provider)

    exporter = OTLPLogExporter(endpoint=otlp_endpoint, insecure=True)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))

    # Create handler that bridges Python logging to OTEL
    handler = LoggingHandler(
        level=logging.DEBUG,
        logger_provider=logger_provider,
    )

    return handler


def is_otel_available() -> bool:
    """Check if OTEL logging dependencies are available."""
    return OTEL_AVAILABLE
