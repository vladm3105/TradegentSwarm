"""Unified logging setup with structlog, rotation, and OTEL export."""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import structlog

from .config import LoggingConfig

# Module-level storage for log file path
_log_file: Path | None = None


def correlation_id_processor(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add correlation ID to log records if available."""
    from .correlation import get_correlation_id

    correlation_id = get_correlation_id()
    if correlation_id:
        event_dict["correlation_id"] = correlation_id
    return event_dict


def setup_logging(
    service_name: str,
    log_file: Path,
    debug: bool = False,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    otel_enabled: bool = False,
    otlp_endpoint: str = "http://localhost:4317",
) -> None:
    """Configure structlog with rotation for any service.

    Sets up:
    - Console output: colored, human-readable
    - File output: JSON with rotation
    - Optional OTEL log export to Loki

    Args:
        service_name: Service identifier for logs
        log_file: Path to log file
        debug: Enable debug level logging
        max_bytes: Max log file size before rotation (default 10MB)
        backup_count: Number of backup files to keep (default 5)
        otel_enabled: Enable OTEL log export to Loki
        otlp_endpoint: OTEL Collector endpoint
    """
    global _log_file
    _log_file = log_file

    # Ensure log directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    log_level = logging.DEBUG if debug else logging.INFO

    # Clear any existing handlers on root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)

    # Shared processors for structlog
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        correlation_id_processor,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # Configure structlog
    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Console formatter: colored, human-readable
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=True),
        foreign_pre_chain=shared_processors,
    )

    # File formatter: JSON for machine parsing
    file_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=shared_processors,
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(log_level)
    root_logger.addHandler(console_handler)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(log_level)
    root_logger.addHandler(file_handler)

    # Reduce noise from third-party libraries
    for logger_name in ["httpx", "httpcore", "uvicorn.access", "openai", "anthropic"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Add OTEL handler for log export to Loki
    if otel_enabled:
        try:
            from .otel_logging import init_otel_logging

            otel_handler = init_otel_logging(service_name, otlp_endpoint)
            root_logger.addHandler(otel_handler)

            log = structlog.get_logger()
            log.info("OTEL log export enabled", endpoint=otlp_endpoint)
        except ImportError as e:
            log = structlog.get_logger()
            log.warning(
                "OTEL logging not available",
                error=str(e),
                hint="Install opentelemetry-exporter-otlp-proto-grpc",
            )
        except Exception as e:
            log = structlog.get_logger()
            log.warning("Failed to initialize OTEL logging", error=str(e))


def setup_logging_from_config(config: LoggingConfig) -> None:
    """Configure logging from a LoggingConfig object."""
    setup_logging(
        service_name=config.service_name,
        log_file=config.log_file,
        debug=config.debug,
        max_bytes=config.max_bytes,
        backup_count=config.backup_count,
        otel_enabled=config.otel_enabled,
        otlp_endpoint=config.otlp_endpoint,
    )


def get_log_file() -> Path | None:
    """Get the current log file path."""
    return _log_file
