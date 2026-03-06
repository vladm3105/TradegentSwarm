"""MCP client pool for all MCP servers."""
import os
import sys
import time
import httpx
import structlog
from dataclasses import dataclass
from pathlib import Path

# Load runtime env with tradegent/.env as default.
try:
    from tradegent.adk_runtime.env import load_runtime_env as _shared_load_runtime_env
except ImportError:
    from dotenv import load_dotenv

    def _shared_load_runtime_env(env_path: Path | None = None) -> Path:
        fallback_path = env_path or Path("/opt/data/tradegent_swarm/tradegent/.env")
        if fallback_path.exists():
            load_dotenv(fallback_path)
        return fallback_path

_shared_load_runtime_env()

# Add shared module to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .stdio_mcp import StdioMCPClient, MCPResponse
from server.config import get_settings
from shared.observability.spans import MCPCallSpan
from shared.observability.metrics_ui import get_metrics
from shared.observability import inject_to_headers

log = structlog.get_logger(__name__)


@dataclass
class MCPHealthStatus:
    """Health status for MCP servers."""

    trading_rag: bool = False
    trading_graph: bool = False
    ib_mcp: bool = False

    def all_healthy(self) -> bool:
        return all([self.trading_rag, self.trading_graph, self.ib_mcp])

    def any_healthy(self) -> bool:
        return any([self.trading_rag, self.trading_graph, self.ib_mcp])


class MCPClientPool:
    """Pool of MCP clients for different servers.

    Manages connections to:
    - trading-rag: stdio transport (RAG operations)
    - trading-graph: stdio transport (Graph operations)
    - ib-mcp: HTTP transport (IB Gateway operations)
    """

    def __init__(self):
        self._settings = get_settings()
        self._http_client: httpx.AsyncClient | None = None
        self._rag_client: StdioMCPClient | None = None
        self._graph_client: StdioMCPClient | None = None
        self._initialized = False

    async def initialize(self):
        """Initialize all MCP clients."""
        if self._initialized:
            return

        settings = self._settings

        # HTTP client for IB MCP (streamable-http requires special headers)
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.mcp_timeout),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )

        # Stdio clients for RAG and Graph
        self._rag_client = StdioMCPClient(
            name="trading-rag",
            command=settings.rag_mcp_cmd,
            cwd=settings.mcp_cwd,
            env={
                "PG_HOST": settings.pg_host,
                "PG_PORT": str(settings.pg_port),
                "PG_USER": settings.pg_user,
                "PG_PASS": settings.pg_pass,
                "PG_DB": settings.pg_db,
            },
        )

        self._graph_client = StdioMCPClient(
            name="trading-graph",
            command=settings.graph_mcp_cmd,
            cwd=settings.mcp_cwd,
            env={
                "NEO4J_URI": os.getenv("NEO4J_URI", f"bolt://{settings.pg_host}:7688"),
                "NEO4J_USER": os.getenv("NEO4J_USER", "neo4j"),
                "NEO4J_PASS": os.getenv("NEO4J_PASS", ""),
            },
        )

        self._initialized = True
        log.info("MCP client pool initialized")

    async def start_stdio_servers(self):
        """Start stdio MCP servers (RAG and Graph)."""
        if self._rag_client:
            await self._rag_client.start()
        if self._graph_client:
            await self._graph_client.start()

    async def shutdown(self):
        """Shutdown all MCP clients."""
        if self._http_client:
            await self._http_client.aclose()

        if self._rag_client:
            await self._rag_client.stop()

        if self._graph_client:
            await self._graph_client.stop()

        self._initialized = False
        log.info("MCP client pool shutdown")

    async def call_ib_mcp(self, tool: str, params: dict | None = None) -> MCPResponse:
        """Call IB MCP via streamable-http.

        Args:
            tool: Tool name (e.g., "get_positions", "get_stock_price")
            params: Tool parameters

        Returns:
            MCPResponse with result or error
        """
        if not self._http_client:
            log.error("mcp.ib.not_initialized")
            return MCPResponse(success=False, error="HTTP client not initialized")

        ticker = (params or {}).get("symbol") or (params or {}).get("ticker")
        metrics = get_metrics()
        start_time = time.perf_counter()

        log.debug(
            "mcp.ib.calling",
            tool=tool,
            ticker=ticker,
            param_keys=list((params or {}).keys()),
        )

        with MCPCallSpan(server="ib-mcp", tool=tool, ticker=ticker, transport="http") as span:
            try:
                # MCP streamable-http format
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": tool,
                        "arguments": params or {},
                    },
                }

                # Inject correlation headers
                headers = inject_to_headers()

                response = await self._http_client.post(
                    self._settings.ib_mcp_url,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()

                data = response.json()

                if "error" in data:
                    span.set_result(success=False)
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    metrics.record_mcp_call("ib-mcp", tool, duration_ms, success=False, ticker=ticker)
                    error_msg = data["error"].get("message", str(data["error"]))
                    log.warning(
                        "mcp.ib.error_response",
                        tool=tool,
                        ticker=ticker,
                        error=error_msg,
                        duration_ms=round(duration_ms, 2),
                    )
                    return MCPResponse(success=False, error=error_msg)

                result = data.get("result", {})
                result_size = len(str(result))

                # Extract content from MCP response format
                if isinstance(result, dict) and "content" in result:
                    content = result["content"]
                    if isinstance(content, list) and len(content) > 0:
                        span.set_result(success=True, result_size=result_size)
                        duration_ms = (time.perf_counter() - start_time) * 1000
                        metrics.record_mcp_call("ib-mcp", tool, duration_ms, success=True, ticker=ticker)
                        log.info(
                            "mcp.ib.success",
                            tool=tool,
                            ticker=ticker,
                            result_size=result_size,
                            duration_ms=round(duration_ms, 2),
                        )
                        return MCPResponse(success=True, result=content[0].get("text", content))

                span.set_result(success=True, result_size=result_size)
                duration_ms = (time.perf_counter() - start_time) * 1000
                metrics.record_mcp_call("ib-mcp", tool, duration_ms, success=True, ticker=ticker)
                log.info(
                    "mcp.ib.success",
                    tool=tool,
                    ticker=ticker,
                    result_size=result_size,
                    duration_ms=round(duration_ms, 2),
                )
                return MCPResponse(success=True, result=result)

            except httpx.TimeoutException:
                span.set_result(success=False)
                duration_ms = (time.perf_counter() - start_time) * 1000
                metrics.record_mcp_call("ib-mcp", tool, duration_ms, success=False, ticker=ticker)
                log.error(
                    "mcp.ib.timeout",
                    tool=tool,
                    ticker=ticker,
                    duration_ms=round(duration_ms, 2),
                )
                return MCPResponse(success=False, error="Request timed out")
            except httpx.HTTPStatusError as e:
                span.set_result(success=False)
                duration_ms = (time.perf_counter() - start_time) * 1000
                metrics.record_mcp_call("ib-mcp", tool, duration_ms, success=False, ticker=ticker)
                log.error(
                    "mcp.ib.http_error",
                    tool=tool,
                    ticker=ticker,
                    status_code=e.response.status_code,
                    duration_ms=round(duration_ms, 2),
                )
                return MCPResponse(success=False, error=f"HTTP {e.response.status_code}")
            except Exception as e:
                span.set_result(success=False)
                duration_ms = (time.perf_counter() - start_time) * 1000
                metrics.record_mcp_call("ib-mcp", tool, duration_ms, success=False, ticker=ticker)
                log.error(
                    "mcp.ib.exception",
                    tool=tool,
                    ticker=ticker,
                    error=str(e),
                    error_type=type(e).__name__,
                    duration_ms=round(duration_ms, 2),
                )
                return MCPResponse(success=False, error=str(e))

    async def call_rag(self, tool: str, params: dict | None = None) -> MCPResponse:
        """Call trading-rag MCP via stdio subprocess.

        Args:
            tool: Tool name (e.g., "rag_search", "rag_embed")
            params: Tool parameters

        Returns:
            MCPResponse with result or error
        """
        if not self._rag_client:
            log.error("mcp.rag.not_initialized")
            return MCPResponse(success=False, error="RAG client not initialized")

        ticker = (params or {}).get("ticker")
        metrics = get_metrics()
        start_time = time.perf_counter()

        log.debug(
            "mcp.rag.calling",
            tool=tool,
            ticker=ticker,
            param_keys=list((params or {}).keys()),
        )

        with MCPCallSpan(server="trading-rag", tool=tool, ticker=ticker, transport="stdio") as span:
            result = await self._rag_client.call("tools/call", {"name": tool, "arguments": params or {}})

            duration_ms = (time.perf_counter() - start_time) * 1000
            result_size = len(str(result.result)) if result.result else 0
            span.set_result(success=result.success, result_size=result_size)
            metrics.record_mcp_call("trading-rag", tool, duration_ms, success=result.success, ticker=ticker)

            if result.success:
                log.info(
                    "mcp.rag.success",
                    tool=tool,
                    ticker=ticker,
                    result_size=result_size,
                    duration_ms=round(duration_ms, 2),
                )
            else:
                log.warning(
                    "mcp.rag.failed",
                    tool=tool,
                    ticker=ticker,
                    error=result.error,
                    duration_ms=round(duration_ms, 2),
                )

            return result

    async def call_graph(self, tool: str, params: dict | None = None) -> MCPResponse:
        """Call trading-graph MCP via stdio subprocess.

        Args:
            tool: Tool name (e.g., "graph_context", "graph_peers")
            params: Tool parameters

        Returns:
            MCPResponse with result or error
        """
        if not self._graph_client:
            log.error("mcp.graph.not_initialized")
            return MCPResponse(success=False, error="Graph client not initialized")

        ticker = (params or {}).get("ticker")
        metrics = get_metrics()
        start_time = time.perf_counter()

        log.debug(
            "mcp.graph.calling",
            tool=tool,
            ticker=ticker,
            param_keys=list((params or {}).keys()),
        )

        with MCPCallSpan(server="trading-graph", tool=tool, ticker=ticker, transport="stdio") as span:
            result = await self._graph_client.call("tools/call", {"name": tool, "arguments": params or {}})

            duration_ms = (time.perf_counter() - start_time) * 1000
            result_size = len(str(result.result)) if result.result else 0
            span.set_result(success=result.success, result_size=result_size)
            metrics.record_mcp_call("trading-graph", tool, duration_ms, success=result.success, ticker=ticker)

            if result.success:
                log.info(
                    "mcp.graph.success",
                    tool=tool,
                    ticker=ticker,
                    result_size=result_size,
                    duration_ms=round(duration_ms, 2),
                )
            else:
                log.warning(
                    "mcp.graph.failed",
                    tool=tool,
                    ticker=ticker,
                    error=result.error,
                    duration_ms=round(duration_ms, 2),
                )

            return result

    async def health_check(self) -> MCPHealthStatus:
        """Check health of all MCP servers.

        Returns:
            MCPHealthStatus with per-server status
        """
        status = MCPHealthStatus()

        # Check IB MCP (just verify server is reachable)
        try:
            # Simple GET to check server is running (will return 405 but that's OK)
            response = await self._http_client.get(
                self._settings.ib_mcp_url,
                timeout=5.0,
            )
            # Any response means server is up (405 Method Not Allowed is fine)
            status.ib_mcp = response.status_code in (200, 405, 400, 406)
        except Exception:
            status.ib_mcp = False

        # Check RAG MCP
        if self._rag_client:
            status.trading_rag = await self._rag_client.health_check()

        # Check Graph MCP
        if self._graph_client:
            status.trading_graph = await self._graph_client.health_check()

        return status


# Global singleton
_mcp_pool: MCPClientPool | None = None


async def get_mcp_pool() -> MCPClientPool:
    """Get or create the global MCP client pool."""
    global _mcp_pool
    if _mcp_pool is None:
        _mcp_pool = MCPClientPool()
        await _mcp_pool.initialize()
        await _mcp_pool.start_stdio_servers()
    return _mcp_pool
