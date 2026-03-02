"""HTTP request spans for FastAPI."""
import time
from typing import Any

try:
    from opentelemetry import trace
    from opentelemetry.trace import Span, Status, StatusCode

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

import structlog

log = structlog.get_logger()


class HTTPRequestSpan:
    """Span for FastAPI request handling.

    Tracks HTTP requests with timing, status codes, and session info.

    Attributes:
        method: HTTP method (GET, POST, etc.)
        path: Request path
        session_id: Optional session identifier
        duration_ms: Request duration in milliseconds

    Example:
        with HTTPRequestSpan(method="POST", path="/api/chat", session_id="abc123") as span:
            response = await process_request(request)
            span.set_status_code(200)
    """

    def __init__(
        self,
        method: str,
        path: str,
        session_id: str | None = None,
        query_params: dict[str, str] | None = None,
    ):
        """Initialize HTTP request span.

        Args:
            method: HTTP method
            path: Request path
            session_id: Optional session ID
            query_params: Optional query parameters
        """
        self.method = method
        self.path = path
        self.session_id = session_id
        self.query_params = query_params or {}
        self._span: "Span | None" = None
        self._start_time: float = 0
        self.duration_ms: float = 0
        self._status_code: int = 0

    def __enter__(self) -> "HTTPRequestSpan":
        """Start the span."""
        self._start_time = time.perf_counter()

        if OTEL_AVAILABLE:
            tracer = trace.get_tracer(__name__)
            self._span = tracer.start_span(
                f"http.{self.method.lower()}.{self.path}",
                attributes={
                    "http.method": self.method,
                    "http.url": self.path,
                    "http.target": self.path,
                    **({"session_id": self.session_id} if self.session_id else {}),
                },
            )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """End the span."""
        self.duration_ms = (time.perf_counter() - self._start_time) * 1000

        if OTEL_AVAILABLE and self._span:
            self._span.set_attribute("http.status_code", self._status_code)
            self._span.set_attribute("duration_ms", self.duration_ms)

            if exc_type is not None:
                self._span.set_status(Status(StatusCode.ERROR, str(exc_val)))
                self._span.record_exception(exc_val)
            elif self._status_code >= 400:
                self._span.set_status(
                    Status(StatusCode.ERROR, f"HTTP {self._status_code}")
                )
            else:
                self._span.set_status(Status(StatusCode.OK))

            self._span.end()

        # Log for non-OTEL environments
        log_level = log.info if self._status_code < 400 else log.warning
        log_level(
            "HTTP request completed",
            method=self.method,
            path=self.path,
            status_code=self._status_code,
            duration_ms=round(self.duration_ms, 2),
            session_id=self.session_id,
        )

    def set_status_code(self, status_code: int) -> None:
        """Set the HTTP status code.

        Args:
            status_code: HTTP response status code
        """
        self._status_code = status_code

        if OTEL_AVAILABLE and self._span:
            self._span.set_attribute("http.status_code", status_code)

    def set_user_id(self, user_id: str) -> None:
        """Set the user ID.

        Args:
            user_id: User identifier
        """
        if OTEL_AVAILABLE and self._span:
            self._span.set_attribute("user.id", user_id)

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add an event to the span.

        Args:
            name: Event name
            attributes: Optional event attributes
        """
        if OTEL_AVAILABLE and self._span:
            self._span.add_event(name, attributes=attributes or {})
