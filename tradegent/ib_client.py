"""
Direct IB MCP Client - MCP protocol interface to IB Gateway.

Uses MCP client library to communicate with IB MCP server.
IB MCP server runs at localhost:8100 with streamable-http transport.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Protocol

log = logging.getLogger("tradegent.ib-client")

IB_MCP_URL = os.environ.get("IB_MCP_URL", "http://localhost:8100/mcp")
IB_MCP_TIMEOUT = float(os.environ.get("IB_MCP_TIMEOUT", "30"))


@dataclass
class IBClientError(Exception):
    """IB MCP client error."""
    message: str
    status_code: int | None = None


@dataclass
class Quote:
    """Stock quote data for watchlist monitoring."""
    symbol: str
    last: float | None
    bid: float | None
    ask: float | None
    volume: int | None
    close: float | None  # Previous close for reference


class IBClientProtocol(Protocol):
    """Interface for IB client implementations (for type checking)."""

    def get_quote(self, symbol: str) -> Quote | None:
        """Get current quote for symbol."""
        ...

    def get_quotes_batch(self, symbols: list[str]) -> dict[str, Quote]:
        """Get quotes for multiple symbols in one call."""
        ...

    def health_check(self) -> bool:
        """Check if IB connection is healthy."""
        ...


class IBClient:
    """
    MCP client for IB MCP server.

    Uses the MCP protocol over streamable-http transport.
    Avoids Claude Code API costs by calling IB MCP directly.
    """

    def __init__(self, mcp_url: str = IB_MCP_URL, timeout: float = IB_MCP_TIMEOUT):
        self.mcp_url = mcp_url
        self.timeout = timeout
        self._loop: asyncio.AbstractEventLoop | None = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create event loop for sync calls."""
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            if self._loop is None or self._loop.is_closed():
                self._loop = asyncio.new_event_loop()
            return self._loop

    def _run_async(self, coro):
        """Run async coroutine from sync context."""
        try:
            loop = asyncio.get_running_loop()
            # Already in async context - create task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=self.timeout)
        except RuntimeError:
            # No running loop - use asyncio.run
            return asyncio.run(coro)

    async def _call_tool_async(self, tool_name: str, params: dict | None = None) -> Any:
        """Call an IB MCP tool via MCP protocol."""
        from mcp.client.streamable_http import streamablehttp_client
        from mcp.client.session import ClientSession

        try:
            async with streamablehttp_client(self.mcp_url) as (read, write, get_session_id):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, params or {})

                    # Parse the result - MCP returns TextContent with JSON string
                    if result.content and len(result.content) > 0:
                        content = result.content[0]
                        if hasattr(content, 'text'):
                            return json.loads(content.text)
                    return {}
        except Exception as e:
            log.error(f"IB MCP call failed for {tool_name}: {e}")
            raise IBClientError(f"MCP call failed: {e}")

    def _call_tool(self, tool_name: str, params: dict | None = None) -> Any:
        """Sync wrapper for _call_tool_async."""
        return self._run_async(self._call_tool_async(tool_name, params))

    def health_check(self) -> bool:
        """Check if IB MCP server is available."""
        try:
            result = self._call_tool("health_check")
            return (
                result.get("status") == "healthy" or
                result.get("success", False) or
                result.get("ib_connected", False)
            )
        except Exception as e:
            log.warning(f"IB MCP health check failed: {e}")
            return False

    def get_positions(self) -> list[dict]:
        """Get all current positions."""
        try:
            result = self._call_tool("get_positions")
            return result.get("positions", []) if isinstance(result, dict) else result
        except IBClientError:
            return []

    def get_stock_price(self, symbol: str) -> dict | None:
        """Get current stock price."""
        try:
            return self._call_tool("get_stock_price", {"symbol": symbol})
        except IBClientError:
            return None

    def get_quote(self, symbol: str) -> Quote | None:
        """Get current quote as Quote dataclass for watchlist monitoring."""
        data = self.get_stock_price(symbol)
        if not data:
            return None
        return Quote(
            symbol=symbol,
            last=data.get("last"),
            bid=data.get("bid"),
            ask=data.get("ask"),
            volume=data.get("volume"),
            close=data.get("close")
        )

    def get_quotes_batch(self, symbols: list[str]) -> dict[str, Quote]:
        """Get batch quotes for multiple symbols."""
        try:
            result = self._call_tool("get_quotes_batch", {"symbols": symbols})
            quotes = {}
            # Handle different response formats
            quote_data = result.get("quotes", result) if isinstance(result, dict) else {}
            for symbol, data in quote_data.items():
                if isinstance(data, dict):
                    quotes[symbol] = Quote(
                        symbol=symbol,
                        last=data.get("last"),
                        bid=data.get("bid"),
                        ask=data.get("ask"),
                        volume=data.get("volume"),
                        close=data.get("close")
                    )
            return quotes
        except IBClientError:
            return {}

    def get_order_status(self, order_id: str) -> dict | None:
        """Get order status by ID."""
        try:
            return self._call_tool("get_order_status", {"order_id": order_id})
        except IBClientError:
            return None

    def get_open_orders(self) -> list[dict]:
        """Get all open orders."""
        try:
            result = self._call_tool("get_open_orders")
            return result.get("orders", []) if isinstance(result, dict) else result
        except IBClientError:
            return []

    def get_portfolio(self) -> list[dict]:
        """Get portfolio with P&L."""
        try:
            result = self._call_tool("get_portfolio")
            return result.get("portfolio", []) if isinstance(result, dict) else result
        except IBClientError:
            return []

    def get_account_summary(self) -> dict | None:
        """Get account summary (buying power, etc.)."""
        try:
            return self._call_tool("get_account_summary")
        except IBClientError:
            return None


# Singleton instance for convenience
_default_client: IBClient | None = None


def get_ib_client() -> IBClient:
    """Get default IB client instance."""
    global _default_client
    if _default_client is None:
        _default_client = IBClient()
    return _default_client
