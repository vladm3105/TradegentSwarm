"""Correlation ID management and B3 trace propagation."""
import uuid
from contextvars import ContextVar
from typing import Any

# Context variable for correlation ID
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    """Get the current correlation ID from context."""
    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID in context."""
    _correlation_id.set(correlation_id)


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())


def extract_from_headers(headers: dict[str, Any]) -> str | None:
    """Extract correlation ID from HTTP headers.

    Supports B3 format headers:
    - X-B3-TraceId (standard B3)
    - X-Correlation-Id (common alternative)
    - X-Request-Id (another common pattern)

    Args:
        headers: HTTP headers dictionary (case-insensitive keys supported)

    Returns:
        Correlation ID if found, None otherwise
    """
    # Normalize headers to lowercase for case-insensitive lookup
    normalized = {k.lower(): v for k, v in headers.items()}

    # Check B3 headers in priority order
    for header in ["x-b3-traceid", "x-correlation-id", "x-request-id"]:
        if header in normalized:
            value = normalized[header]
            if value:
                return str(value)

    return None


def inject_to_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    """Inject correlation ID into HTTP headers.

    Uses B3 format for compatibility with distributed tracing systems.

    Args:
        headers: Existing headers dict to update (creates new if None)

    Returns:
        Headers dict with correlation ID added
    """
    if headers is None:
        headers = {}

    correlation_id = get_correlation_id()
    if correlation_id:
        headers["X-B3-TraceId"] = correlation_id
        headers["X-Correlation-Id"] = correlation_id

    return headers


def correlation_id_processor(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Structlog processor that adds correlation ID to log events.

    Use this processor in structlog configuration to automatically
    include correlation IDs in all log records.

    Example:
        structlog.configure(
            processors=[
                correlation_id_processor,
                # ... other processors
            ]
        )
    """
    correlation_id = get_correlation_id()
    if correlation_id:
        event_dict["correlation_id"] = correlation_id
    return event_dict


class CorrelationContext:
    """Context manager for setting correlation ID.

    Example:
        with CorrelationContext("abc123"):
            # All code here has access to correlation_id
            log.info("Processing request")  # Includes correlation_id
    """

    def __init__(self, correlation_id: str | None = None):
        """Initialize context with correlation ID.

        Args:
            correlation_id: ID to use, generates new if None
        """
        self.correlation_id = correlation_id or generate_correlation_id()
        self._token = None

    def __enter__(self) -> str:
        """Enter context and set correlation ID."""
        self._token = _correlation_id.set(self.correlation_id)
        return self.correlation_id

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context and restore previous correlation ID."""
        if self._token is not None:
            _correlation_id.reset(self._token)
