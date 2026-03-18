"""Unit tests for IB MCP direct client."""

from unittest.mock import patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ib_client import IBClient, IBClientError, get_ib_client


class TestIBClient:
    """Tests for IBClient class."""

    def test_init_default_url(self):
        """Test default URL configuration."""
        client = IBClient()
        assert client.mcp_url == "http://localhost:8100/mcp"
        assert client.timeout == 30.0

    def test_init_custom_url(self):
        """Test custom URL configuration."""
        client = IBClient(mcp_url="http://custom:9000/mcp", timeout=60.0)
        assert client.mcp_url == "http://custom:9000/mcp"
        assert client.timeout == 60.0

    def test_context_manager(self):
        """Test context manager protocol."""
        with IBClient() as client:
            assert isinstance(client, IBClient)

    @patch.object(IBClient, "_call_tool")
    def test_health_check_success(self, mock_call_tool):
        """Test successful health check."""
        mock_call_tool.return_value = {"status": "healthy"}

        client = IBClient()
        result = client.health_check()
        assert result is True

    @patch.object(IBClient, "_call_tool")
    def test_health_check_failure(self, mock_call_tool):
        """Test failed health check."""
        mock_call_tool.side_effect = IBClientError("Connection refused")

        client = IBClient()
        result = client.health_check()
        assert result is False

    @patch.object(IBClient, "_call_tool")
    def test_get_positions_success(self, mock_call_tool):
        """Test successful get_positions call."""
        mock_call_tool.return_value = {
            "positions": [
                {"symbol": "NVDA", "position": 100, "avgCost": 125.50},
                {"symbol": "AAPL", "position": 50, "avgCost": 175.00},
            ]
        }

        client = IBClient()
        positions = client.get_positions()
        assert len(positions) == 2
        assert positions[0]["symbol"] == "NVDA"

    @patch.object(IBClient, "_call_tool")
    def test_get_positions_empty(self, mock_call_tool):
        """Test get_positions with no positions."""
        mock_call_tool.return_value = {"positions": []}

        client = IBClient()
        positions = client.get_positions()
        assert positions == []

    @patch.object(IBClient, "_call_tool")
    def test_get_stock_price_success(self, mock_call_tool):
        """Test successful get_stock_price call."""
        mock_call_tool.return_value = {
            "symbol": "NVDA",
            "last": 128.50,
            "bid": 128.45,
            "ask": 128.55,
        }

        client = IBClient()
        price = client.get_stock_price("NVDA")
        assert price["last"] == 128.50
        mock_call_tool.assert_called_once_with("get_stock_price", {"symbol": "NVDA"})

    @patch.object(IBClient, "_call_tool")
    def test_get_order_status_success(self, mock_call_tool):
        """Test successful get_order_status call."""
        mock_call_tool.return_value = {
            "order_id": "123",
            "status": "Filled",
            "avgFillPrice": 128.25,
            "filled": 100,
        }

        client = IBClient()
        status = client.get_order_status("123")
        assert status["status"] == "Filled"
        assert status["avgFillPrice"] == 128.25
        mock_call_tool.assert_called_once_with("get_order_status", {"order_id": "123"})

    @patch.object(IBClient, "_call_tool")
    def test_get_open_orders_success(self, mock_call_tool):
        """Test successful get_open_orders call."""
        mock_call_tool.return_value = {
            "orders": [
                {"order_id": "123", "symbol": "NVDA", "status": "Submitted"},
            ]
        }

        client = IBClient()
        orders = client.get_open_orders()
        assert len(orders) == 1
        assert orders[0]["order_id"] == "123"
        mock_call_tool.assert_called_once_with("get_open_orders")


class TestGetIBClient:
    """Tests for get_ib_client singleton function."""

    def test_returns_ib_client(self):
        """Test that get_ib_client returns an IBClient instance."""
        client = get_ib_client()
        assert isinstance(client, IBClient)

    def test_returns_same_instance(self):
        """Test that get_ib_client returns the same instance."""
        client1 = get_ib_client()
        client2 = get_ib_client()
        assert client1 is client2


class TestIBClientError:
    """Tests for IBClientError exception."""

    def test_error_with_message(self):
        """Test error with message only."""
        error = IBClientError("Connection failed")
        assert error.message == "Connection failed"
        assert error.status_code is None

    def test_error_with_status_code(self):
        """Test error with status code."""
        error = IBClientError("HTTP 404", 404)
        assert error.message == "HTTP 404"
        assert error.status_code == 404
