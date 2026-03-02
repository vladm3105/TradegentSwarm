"""Configuration classes for observability."""
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LoggingConfig:
    """Logging configuration."""

    service_name: str
    log_file: Path
    debug: bool = False
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    json_output: bool = True
    console_output: bool = True
    otel_enabled: bool = True
    otlp_endpoint: str = "http://localhost:4317"

    @classmethod
    def from_env(cls, service_name: str, log_file: Path) -> "LoggingConfig":
        """Create config from environment variables."""
        return cls(
            service_name=service_name,
            log_file=log_file,
            debug=os.getenv("DEBUG", "false").lower() == "true",
            max_bytes=int(os.getenv("LOG_MAX_SIZE_MB", "10")) * 1024 * 1024,
            backup_count=int(os.getenv("LOG_BACKUP_COUNT", "5")),
            json_output=os.getenv("LOG_JSON", "true").lower() == "true",
            console_output=os.getenv("LOG_CONSOLE", "true").lower() == "true",
            otel_enabled=os.getenv("OTEL_LOGS_ENABLED", "true").lower() == "true",
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
        )


@dataclass
class TracingConfig:
    """Tracing configuration."""

    service_name: str
    enabled: bool = True
    exporter_type: str = "otlp"  # otlp, console, none
    otlp_endpoint: str = "http://localhost:4317"
    sample_rate: float = 1.0
    propagators: list[str] = field(default_factory=lambda: ["b3multi", "tracecontext"])

    @classmethod
    def from_env(cls, service_name: str) -> "TracingConfig":
        """Create config from environment variables."""
        return cls(
            service_name=os.getenv("OTEL_SERVICE_NAME", service_name),
            enabled=os.getenv("OTEL_EXPORTER_TYPE", "otlp") != "none",
            exporter_type=os.getenv("OTEL_EXPORTER_TYPE", "otlp"),
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
            sample_rate=float(os.getenv("OTEL_SAMPLE_RATE", "1.0")),
        )
