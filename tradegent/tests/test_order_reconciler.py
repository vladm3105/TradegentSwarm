"""Unit tests for order reconciler module."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from order_reconciler import OrderReconciler


class TestOrderReconciler:
    """Tests for OrderReconciler class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = MagicMock()
        self.mock_ib = MagicMock()
        self.reconciler = OrderReconciler(self.mock_db, self.mock_ib)

    def test_reconcile_no_pending_orders(self):
        """Test reconcile with no pending orders."""
        self.mock_db.get_trades_with_pending_orders.return_value = []
        results = self.reconciler.reconcile_pending_orders()
        assert results == {"filled": 0, "partial": 0, "cancelled": 0, "pending": 0, "errors": 0}

    def test_reconcile_filled_order(self):
        """Test reconciling a filled order."""
        self.mock_db.get_trades_with_pending_orders.return_value = [
            {"id": 1, "ticker": "NVDA", "order_id": "123", "entry_price": 125.00, "entry_size": 100}
        ]
        self.mock_ib.get_order_status.return_value = {
            "status": "Filled",
            "avgFillPrice": 125.50,
            "filled": 100,
        }

        results = self.reconciler.reconcile_pending_orders()
        assert results["filled"] == 1
        self.mock_db.update_trade_order.assert_called()

    def test_reconcile_partial_fill(self):
        """Test reconciling a partially filled order."""
        self.mock_db.get_trades_with_pending_orders.return_value = [
            {"id": 1, "ticker": "NVDA", "order_id": "123", "entry_price": 125.00, "entry_size": 100, "partial_fills": []}
        ]
        self.mock_ib.get_order_status.return_value = {
            "status": "PartiallyFilled",
            "avgFillPrice": 125.50,
            "filled": 50,
        }

        results = self.reconciler.reconcile_pending_orders()
        assert results["partial"] == 1

    def test_reconcile_cancelled_order(self):
        """Test reconciling a cancelled order."""
        self.mock_db.get_trades_with_pending_orders.return_value = [
            {"id": 1, "ticker": "NVDA", "order_id": "123", "entry_price": 125.00, "entry_size": 100}
        ]
        self.mock_ib.get_order_status.return_value = {
            "status": "Cancelled",
        }

        results = self.reconciler.reconcile_pending_orders()
        assert results["cancelled"] == 1
        self.mock_db.update_trade_order.assert_called()
        self.mock_db.update_stock_position.assert_called_with("NVDA", False, "none")

    def test_reconcile_pending_order(self):
        """Test reconciling a still-pending order."""
        self.mock_db.get_trades_with_pending_orders.return_value = [
            {"id": 1, "ticker": "NVDA", "order_id": "123", "entry_price": 125.00, "entry_size": 100}
        ]
        self.mock_ib.get_order_status.return_value = {
            "status": "Submitted",
        }

        results = self.reconciler.reconcile_pending_orders()
        assert results["pending"] == 1
        assert results["filled"] == 0

    def test_reconcile_error_status(self):
        """Test reconciling an order with error status."""
        self.mock_db.get_trades_with_pending_orders.return_value = [
            {"id": 1, "ticker": "NVDA", "order_id": "123", "entry_price": 125.00, "entry_size": 100}
        ]
        self.mock_ib.get_order_status.return_value = {
            "status": "Error",
            "message": "Insufficient funds",
        }

        results = self.reconciler.reconcile_pending_orders()
        assert results["errors"] == 1
        self.mock_db.update_trade_order.assert_called_with(1, "123", "Error")

    def test_reconcile_ib_unavailable(self):
        """Test reconciling when IB returns None."""
        self.mock_db.get_trades_with_pending_orders.return_value = [
            {"id": 1, "ticker": "NVDA", "order_id": "123", "entry_price": 125.00, "entry_size": 100}
        ]
        self.mock_ib.get_order_status.return_value = None

        results = self.reconciler.reconcile_pending_orders()
        assert results["errors"] == 1

    def test_reconcile_multiple_orders(self):
        """Test reconciling multiple orders at once."""
        self.mock_db.get_trades_with_pending_orders.return_value = [
            {"id": 1, "ticker": "NVDA", "order_id": "123", "entry_price": 125.00, "entry_size": 100},
            {"id": 2, "ticker": "AAPL", "order_id": "124", "entry_price": 175.00, "entry_size": 50},
            {"id": 3, "ticker": "MSFT", "order_id": "125", "entry_price": 400.00, "entry_size": 25},
        ]
        self.mock_ib.get_order_status.side_effect = [
            {"status": "Filled", "avgFillPrice": 125.50, "filled": 100},
            {"status": "Submitted"},
            {"status": "Cancelled"},
        ]

        results = self.reconciler.reconcile_pending_orders()
        assert results["filled"] == 1
        assert results["pending"] == 1
        assert results["cancelled"] == 1

    def test_handle_filled_updates_entry_price(self):
        """Test that filled orders update entry price to actual fill."""
        trade = {"id": 1, "ticker": "NVDA", "order_id": "123", "entry_price": 125.00, "entry_size": 100}
        status = {"status": "Filled", "avgFillPrice": 125.75, "filled": 100}

        self.reconciler._handle_filled(trade, status)

        # Verify update_trade_order was called
        self.mock_db.update_trade_order.assert_called_with(
            1, "123", "Filled", avg_fill_price=125.75
        )

    def test_handle_cancelled_closes_trade(self):
        """Test that cancelled orders close the trade with zero P&L."""
        trade = {"id": 1, "ticker": "NVDA", "order_id": "123"}
        status = {"status": "Cancelled"}

        self.reconciler._handle_cancelled(trade, status)

        self.mock_db.update_trade_order.assert_called_with(1, "123", "Cancelled")
        self.mock_db.update_stock_position.assert_called_with("NVDA", False, "none")


class TestOrderReconcilerStatusMappings:
    """Tests for various IB status string mappings."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = MagicMock()
        self.mock_ib = MagicMock()
        self.reconciler = OrderReconciler(self.mock_db, self.mock_ib)

    @pytest.mark.parametrize("status", ["FILLED", "Filled", "Fill", "FILL"])
    def test_filled_status_variations(self, status):
        """Test various filled status strings."""
        self.mock_db.get_trades_with_pending_orders.return_value = [
            {"id": 1, "ticker": "NVDA", "order_id": "123", "entry_price": 125.00, "entry_size": 100}
        ]
        self.mock_ib.get_order_status.return_value = {
            "status": status,
            "avgFillPrice": 125.50,
            "filled": 100,
        }

        results = self.reconciler.reconcile_pending_orders()
        assert results["filled"] == 1

    @pytest.mark.parametrize("status", ["CANCELLED", "Cancelled", "Canceled", "CANCEL"])
    def test_cancelled_status_variations(self, status):
        """Test various cancelled status strings."""
        self.mock_db.get_trades_with_pending_orders.return_value = [
            {"id": 1, "ticker": "NVDA", "order_id": "123", "entry_price": 125.00, "entry_size": 100}
        ]
        self.mock_ib.get_order_status.return_value = {"status": status}

        results = self.reconciler.reconcile_pending_orders()
        assert results["cancelled"] == 1

    @pytest.mark.parametrize("status", ["SUBMITTED", "Submitted", "PreSubmitted", "PendingSubmit"])
    def test_pending_status_variations(self, status):
        """Test various pending status strings."""
        self.mock_db.get_trades_with_pending_orders.return_value = [
            {"id": 1, "ticker": "NVDA", "order_id": "123", "entry_price": 125.00, "entry_size": 100}
        ]
        self.mock_ib.get_order_status.return_value = {"status": status}

        results = self.reconciler.reconcile_pending_orders()
        assert results["pending"] == 1
