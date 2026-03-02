"""Shared observability module for TradegentSwarm.

Provides unified logging, tracing, and metrics across all services.
"""
from .config import LoggingConfig, TracingConfig
from .logging_setup import setup_logging, get_log_file
from .correlation import (
    get_correlation_id,
    set_correlation_id,
    extract_from_headers,
    inject_to_headers,
    correlation_id_processor,
)

__all__ = [
    # Config
    "LoggingConfig",
    "TracingConfig",
    # Logging
    "setup_logging",
    "get_log_file",
    # Correlation
    "get_correlation_id",
    "set_correlation_id",
    "extract_from_headers",
    "inject_to_headers",
    "correlation_id_processor",
]
