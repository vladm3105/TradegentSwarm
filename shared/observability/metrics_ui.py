"""Metrics for Tradegent Agent UI."""
from typing import Any

try:
    from opentelemetry import metrics
    from opentelemetry.metrics import Counter, Histogram, Meter

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False


class AgentUIMetrics:
    """Metrics collection for Agent UI.

    Collects:
    - MCP call metrics (duration, counts, errors)
    - LLM call metrics (duration, tokens)
    - HTTP request metrics
    - Agent processing metrics

    Example:
        metrics = AgentUIMetrics()
        metrics.record_mcp_call("trading-rag", "rag_search", 150.5, success=True)
        metrics.record_llm_call(250.0, input_tokens=500, output_tokens=100)
    """

    def __init__(self, service_name: str = "tradegent-ui"):
        """Initialize metrics.

        Args:
            service_name: Service name for metric labels
        """
        self.service_name = service_name
        self._meter: "Meter | None" = None

        # MCP metrics
        self._mcp_call_duration: "Histogram | None" = None
        self._mcp_calls_total: "Counter | None" = None
        self._mcp_errors_total: "Counter | None" = None

        # LLM metrics
        self._llm_call_duration: "Histogram | None" = None
        self._llm_tokens_input: "Counter | None" = None
        self._llm_tokens_output: "Counter | None" = None

        # HTTP metrics
        self._http_request_duration: "Histogram | None" = None
        self._http_requests_total: "Counter | None" = None

        # Agent metrics
        self._agent_requests_total: "Counter | None" = None
        self._intent_classification_duration: "Histogram | None" = None

        if OTEL_AVAILABLE:
            self._init_metrics()

    def _init_metrics(self) -> None:
        """Initialize OTEL metrics."""
        self._meter = metrics.get_meter(self.service_name)

        # MCP metrics
        self._mcp_call_duration = self._meter.create_histogram(
            "agentui.mcp.call.duration",
            description="MCP call duration in milliseconds",
            unit="ms",
        )
        self._mcp_calls_total = self._meter.create_counter(
            "agentui.mcp.calls.total",
            description="Total MCP calls",
        )
        self._mcp_errors_total = self._meter.create_counter(
            "agentui.mcp.errors.total",
            description="Total MCP call errors",
        )

        # LLM metrics
        self._llm_call_duration = self._meter.create_histogram(
            "agentui.llm.call.duration",
            description="LLM API call duration in milliseconds",
            unit="ms",
        )
        self._llm_tokens_input = self._meter.create_counter(
            "agentui.llm.tokens.input",
            description="Total input tokens used",
        )
        self._llm_tokens_output = self._meter.create_counter(
            "agentui.llm.tokens.output",
            description="Total output tokens generated",
        )

        # HTTP metrics
        self._http_request_duration = self._meter.create_histogram(
            "agentui.http.request.duration",
            description="HTTP request duration in milliseconds",
            unit="ms",
        )
        self._http_requests_total = self._meter.create_counter(
            "agentui.http.requests.total",
            description="Total HTTP requests",
        )

        # Agent metrics
        self._agent_requests_total = self._meter.create_counter(
            "agentui.agent.requests.total",
            description="Total agent processing requests",
        )
        self._intent_classification_duration = self._meter.create_histogram(
            "agentui.intent.duration",
            description="Intent classification duration in milliseconds",
            unit="ms",
        )

    def record_mcp_call(
        self,
        server: str,
        tool: str,
        duration_ms: float,
        success: bool = True,
        ticker: str | None = None,
    ) -> None:
        """Record an MCP call.

        Args:
            server: MCP server name
            tool: Tool name
            duration_ms: Call duration in milliseconds
            success: Whether the call succeeded
            ticker: Optional stock ticker
        """
        if not OTEL_AVAILABLE:
            return

        attributes: dict[str, Any] = {
            "server": server,
            "tool": tool,
        }
        if ticker:
            attributes["ticker"] = ticker

        if self._mcp_call_duration:
            self._mcp_call_duration.record(duration_ms, attributes)

        if self._mcp_calls_total:
            self._mcp_calls_total.add(1, attributes)

        if not success and self._mcp_errors_total:
            self._mcp_errors_total.add(1, attributes)

    def record_llm_call(
        self,
        duration_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str = "unknown",
    ) -> None:
        """Record an LLM API call.

        Args:
            duration_ms: Call duration in milliseconds
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model name
        """
        if not OTEL_AVAILABLE:
            return

        attributes = {"model": model}

        if self._llm_call_duration:
            self._llm_call_duration.record(duration_ms, attributes)

        if self._llm_tokens_input and input_tokens > 0:
            self._llm_tokens_input.add(input_tokens, attributes)

        if self._llm_tokens_output and output_tokens > 0:
            self._llm_tokens_output.add(output_tokens, attributes)

    def record_http_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Record an HTTP request.

        Args:
            method: HTTP method
            path: Request path
            status_code: Response status code
            duration_ms: Request duration in milliseconds
        """
        if not OTEL_AVAILABLE:
            return

        attributes = {
            "method": method,
            "path": path,
            "status_code": str(status_code),
        }

        if self._http_request_duration:
            self._http_request_duration.record(duration_ms, attributes)

        if self._http_requests_total:
            self._http_requests_total.add(1, attributes)

    def record_agent_request(
        self,
        intent: str,
        session_id: str | None = None,
    ) -> None:
        """Record an agent processing request.

        Args:
            intent: Classified intent
            session_id: Optional session ID
        """
        if not OTEL_AVAILABLE:
            return

        attributes = {"intent": intent}

        if self._agent_requests_total:
            self._agent_requests_total.add(1, attributes)

    def record_intent_classification(
        self,
        duration_ms: float,
        intents: list[str],
    ) -> None:
        """Record intent classification.

        Args:
            duration_ms: Classification duration in milliseconds
            intents: Classified intents
        """
        if not OTEL_AVAILABLE:
            return

        attributes = {"intent_count": str(len(intents))}

        if self._intent_classification_duration:
            self._intent_classification_duration.record(duration_ms, attributes)


# Global metrics instance
_metrics: AgentUIMetrics | None = None


def get_metrics() -> AgentUIMetrics:
    """Get the global metrics instance."""
    global _metrics
    if _metrics is None:
        _metrics = AgentUIMetrics()
    return _metrics
