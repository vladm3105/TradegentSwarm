"""Logging configuration for Tradegent Agent UI.

Uses shared observability module for unified logging with:
- Log rotation (10MB x 5 backups)
- Structured JSON output
- Optional OTEL export to Loki
- Correlation ID tracking
"""
import os
from pathlib import Path

# Import from shared observability module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.observability import setup_logging as shared_setup_logging
from shared.observability.logging_setup import get_log_file as shared_get_log_file

# Log file location
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "agui.log"

# Service name for OTEL
SERVICE_NAME = "tradegent-ui"


def setup_logging(debug: bool = False) -> None:
    """Configure logging for the application.

    Sets up structlog with:
    - Console output (colored, human-readable)
    - File output (JSON with rotation)
    - Optional OTEL log export to Loki

    Args:
        debug: Enable debug level logging
    """
    otel_enabled = os.getenv("OTEL_LOGS_ENABLED", "false").lower() == "true"
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    max_bytes = int(os.getenv("LOG_MAX_SIZE_MB", "10")) * 1024 * 1024
    backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    shared_setup_logging(
        service_name=SERVICE_NAME,
        log_file=LOG_FILE,
        debug=debug,
        max_bytes=max_bytes,
        backup_count=backup_count,
        otel_enabled=otel_enabled,
        otlp_endpoint=otlp_endpoint,
    )


def get_log_file() -> Path:
    """Get the log file path."""
    return LOG_FILE
