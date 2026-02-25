"""Unit tests for IB MCP direct HTTP client."""

import pytest
from unittest.mock import MagicMock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ib_client import IBClient, IBClientError, get_ib_client


class TestIBClient:
    """Tests for IBClient class."""

    def test_init_default_url(self):
        """Test default URL configuration."""
        client = IBClient()
        assert client.base_url == "http://localhost:8100"
        assert client.timeout == 30.0

    def test_init_custom_url(self):
        """Test custom URL configuration."""
        client = IBClient(base_url="http://custom:9000", timeout=60.0)
        assert client.base_url == "http://custom:9000"
        assert client.timeout == 60.0

    def test_context_manager(self):
        """Test context manager protocol."""
        with IBClient() as client:
            assert client._client is not None
        assert client._client is None

    @patch("ib_client.httpx.Client")
    def test_health_check_success(self, mock_client_class):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "connected": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = IBClient()
        result = client.health_check()
        assert result is True

    @patch("ib_client.httpx.Client")
    def test_health_check_failure(self, mock_client_class):
        """Test failed health check."""
        import httpx

        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.RequestError("Connection refused")
        mock_client_class.return_value = mock_client

        client = IBClient()
        result = client.health_check()
        assert result is False

    @patch("ib_client.httpx.Client")
    def test_get_positions_success(self, mock_client_class):
        """Test successful get_positions call."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "positions": [
                {"symbol": "NVDA", "position": 100, "avgCost": 125.50},
                {"symbol": "AAPL", "position": 50, "avgCost": 175.00},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = IBClient()
        positions = client.get_positions()
        assert len(positions) == 2
        assert positions[0]["symbol"] == "NVDA"

    @patch("ib_client.httpx.Client")
    def test_get_positions_empty(self, mock_client_class):
        """Test get_positions with no positions."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"positions": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = IBClient()
        positions = client.get_positions()
        assert positions == []

    @patch("ib_client.httpx.Client")
    def test_get_stock_price_success(self, mock_client_class):
        """Test successful get_stock_price call."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "symbol": "NVDA",
            "last": 128.50,
            "bid": 128.45,
            "ask": 128.55,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = IBClient()
        price = client.get_stock_price("NVDA")
        assert price["last"] == 128.50
        mock_client.post.assert_called_with(
            "http://localhost:8100/tools/get_stock_price",
            json={"symbol": "NVDA"}
        )

    @patch("ib_client.httpx.Client")
    def test_get_order_status_success(self, mock_client_class):
        """Test successful get_order_status call."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "order_id": "123",
            "status": "Filled",
            "avgFillPrice": 128.25,
            "filled": 100,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = IBClient()
        status = client.get_order_status("123")
        assert status["status"] == "Filled"
        assert status["avgFillPrice"] == 128.25

    @patch("ib_client.httpx.Client")
    def test_get_open_orders_success(self, mock_client_class):
        """Test successful get_open_orders call."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "orders": [
                {"order_id": "123", "symbol": "NVDA", "status": "Submitted"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        client = IBClient()
        orders = client.get_open_orders()
        assert len(orders) == 1
        assert orders[0]["order_id"] == "123"


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
