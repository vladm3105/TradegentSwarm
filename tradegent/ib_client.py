"""
Direct IB MCP Client - HTTP interface to IB Gateway.

Uses direct HTTP calls instead of Claude Code to avoid API costs.
IB MCP server runs at localhost:8100 with SSE transport.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

log = logging.getLogger("tradegent.ib-client")

IB_MCP_URL = os.environ.get("IB_MCP_URL", "http://localhost:8100")
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
    Direct HTTP client for IB MCP server.

    Avoids Claude Code API costs by calling IB MCP directly.
    """

    def __init__(self, base_url: str = IB_MCP_URL, timeout: float = IB_MCP_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.Client | None = None

    def __enter__(self):
        self._client = httpx.Client(timeout=self.timeout)
        return self

    def __exit__(self, *args):
        if self._client:
            self._client.close()
            self._client = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def _call_tool(self, tool_name: str, params: dict | None = None) -> Any:
        """
        Call an IB MCP tool via HTTP.

        The IB MCP server exposes tools at POST /tools/{tool_name}
        """
        client = self._get_client()
        url = f"{self.base_url}/tools/{tool_name}"

        try:
            response = client.post(url, json=params or {})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            log.error(f"IB MCP HTTP error: {e.response.status_code} - {e.response.text}")
            raise IBClientError(f"HTTP {e.response.status_code}", e.response.status_code)
        except httpx.RequestError as e:
            log.error(f"IB MCP request error: {e}")
            raise IBClientError(f"Request failed: {e}")
        except json.JSONDecodeError as e:
            log.error(f"IB MCP JSON decode error: {e}")
            raise IBClientError(f"Invalid JSON response")

    def health_check(self) -> bool:
        """Check if IB MCP server is available."""
        try:
            result = self._call_tool("health_check")
            return result.get("status") == "ok" or result.get("connected", False)
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
