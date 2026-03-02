"""MCP (Model Context Protocol) call spans."""
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


class MCPCallSpan:
    """Span for MCP server calls.

    Tracks MCP tool invocations with timing, result status, and metadata.

    Attributes:
        server: MCP server name (trading-rag, trading-graph, ib-mcp)
        tool: Tool name being called
        ticker: Optional stock ticker for context
        transport: MCP transport type (stdio, http)
        duration_ms: Call duration in milliseconds

    Example:
        with MCPCallSpan(server="trading-rag", tool="rag_search", ticker="NVDA") as span:
            result = await mcp_client.call("rag_search", {"ticker": "NVDA"})
            span.set_result(success=True, result_size=len(result))
    """

    def __init__(
        self,
        server: str,
        tool: str,
        ticker: str | None = None,
        transport: str = "stdio",
    ):
        """Initialize MCP call span.

        Args:
            server: MCP server name
            tool: Tool being called
            ticker: Optional stock ticker
            transport: Transport type (stdio, http)
        """
        self.server = server
        self.tool = tool
        self.ticker = ticker
        self.transport = transport
        self._span: "Span | None" = None
        self._start_time: float = 0
        self.duration_ms: float = 0
        self._success: bool | None = None
        self._result_size: int = 0

    def __enter__(self) -> "MCPCallSpan":
        """Start the span."""
        self._start_time = time.perf_counter()

        if OTEL_AVAILABLE:
            tracer = trace.get_tracer(__name__)
            self._span = tracer.start_span(
                f"mcp.call.{self.server}.{self.tool}",
                attributes={
                    "mcp.server": self.server,
                    "mcp.tool": self.tool,
                    "mcp.transport": self.transport,
                    **({"ticker": self.ticker} if self.ticker else {}),
                },
            )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """End the span."""
        self.duration_ms = (time.perf_counter() - self._start_time) * 1000

        if OTEL_AVAILABLE and self._span:
            self._span.set_attribute("duration_ms", self.duration_ms)

            if exc_type is not None:
                self._span.set_status(Status(StatusCode.ERROR, str(exc_val)))
                self._span.record_exception(exc_val)
            elif self._success is False:
                self._span.set_status(Status(StatusCode.ERROR, "Call failed"))
            else:
                self._span.set_status(Status(StatusCode.OK))

            self._span.set_attribute("result_size", self._result_size)
            self._span.end()

        # Always log the call
        log_method = log.info if self._success else log.warning
        log_method(
            "MCP call completed",
            server=self.server,
            tool=self.tool,
            ticker=self.ticker,
            duration_ms=round(self.duration_ms, 2),
            success=self._success,
            result_size=self._result_size,
        )

    def set_result(self, success: bool, result_size: int = 0) -> None:
        """Set the call result.

        Args:
            success: Whether the call succeeded
            result_size: Size of the result (bytes or count)
        """
        self._success = success
        self._result_size = result_size

        if OTEL_AVAILABLE and self._span:
            self._span.set_attribute("mcp.success", success)
            self._span.set_attribute("mcp.result_size", result_size)

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add an event to the span.

        Args:
            name: Event name
            attributes: Optional event attributes
        """
        if OTEL_AVAILABLE and self._span:
            self._span.add_event(name, attributes=attributes or {})
