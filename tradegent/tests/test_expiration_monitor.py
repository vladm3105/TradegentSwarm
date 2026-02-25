"""
Tests for expiration_monitor.py - Options expiration tracking and handling.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import date, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from expiration_monitor import ExpirationMonitor


class MockDB:
    """Mock database for testing."""

    def __init__(self):
        self.settings = {
            "options_expiry_warning_days": 7,
            "options_expiry_critical_days": 3,
            "auto_close_expired_options": True,
        }
        self.closed_trades = []
        self.queued_tasks = []
        self._conn = MagicMock()

    def get_setting(self, key, default=None):
        return self.settings.get(key, default)

    @property
    def conn(self):
        return self._conn

    def queue_task(self, task_type, ticker, prompt, priority):
        self.queued_tasks.append({
            "task_type": task_type,
            "ticker": ticker,
            "prompt": prompt,
            "priority": priority,
        })
        return len(self.queued_tasks)

    def close_expired_option_worthless(self, trade_id):
        self.closed_trades.append(trade_id)
        return True

    def get_short_options_by_underlying(self, underlying):
        return []


class TestExpirationMonitor:
    """Tests for ExpirationMonitor class."""

    def test_init_loads_settings(self):
        """Verify settings are loaded on init."""
        db = MockDB()
        monitor = ExpirationMonitor(db)

        assert monitor._settings["warning_days"] == 7
        assert monitor._settings["critical_days"] == 3
        assert monitor._settings["auto_close"] is True

    def test_get_expiring_soon_uses_view(self):
        """Verify get_expiring_soon queries the view."""
        db = MockDB()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = []
        db._conn.cursor.return_value = mock_cursor

        monitor = ExpirationMonitor(db)
        result = monitor.get_expiring_soon(7)

        mock_cursor.execute.assert_called_once()
        call_sql = mock_cursor.execute.call_args[0][0]
        assert "v_options_positions" in call_sql
        assert "days_to_expiry" in call_sql

    def test_get_expired_queries_negative_days(self):
        """Verify get_expired queries for negative days_to_expiry."""
        db = MockDB()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = []
        db._conn.cursor.return_value = mock_cursor

        monitor = ExpirationMonitor(db)
        result = monitor.get_expired()

        mock_cursor.execute.assert_called_once()
        call_sql = mock_cursor.execute.call_args[0][0]
        assert "days_to_expiry < 0" in call_sql

    def test_process_expirations_disabled(self):
        """Verify processing is skipped when auto_close disabled."""
        db = MockDB()
        db.settings["auto_close_expired_options"] = False

        monitor = ExpirationMonitor(db)
        monitor._refresh_settings()

        result = monitor.process_expirations()

        assert result == {"expired_worthless": 0, "needs_review": 0, "errors": 0}

    def test_process_expirations_close_worthless(self):
        """Verify OTM expired options are closed as worthless."""
        db = MockDB()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        # Return one expired option
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "ticker": "NVDA",
                "full_symbol": "NVDA  240315C00500000",
                "option_underlying": "NVDA",
                "option_strike": 500.0,
                "option_type": "call",
                "entry_price": 0.10,  # Low premium = likely OTM
            }
        ]
        db._conn.cursor.return_value = mock_cursor

        monitor = ExpirationMonitor(db)

        # Price function shows stock at $450 (below $500 strike) = OTM call
        def get_price(ticker):
            return 450.0

        result = monitor.process_expirations(get_stock_price_fn=get_price)

        assert result["expired_worthless"] == 1
        assert 1 in db.closed_trades

    def test_process_expirations_itm_needs_review(self):
        """Verify ITM expired options are queued for review."""
        db = MockDB()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        # Return one expired option
        mock_cursor.fetchall.return_value = [
            {
                "id": 2,
                "ticker": "NVDA",
                "full_symbol": "NVDA  240315C00500000",
                "option_underlying": "NVDA",
                "option_strike": 500.0,
                "option_type": "call",
                "entry_price": 5.0,
            }
        ]
        db._conn.cursor.return_value = mock_cursor

        monitor = ExpirationMonitor(db)

        # Price function shows stock at $550 (above $500 strike) = ITM call
        def get_price(ticker):
            return 550.0

        result = monitor.process_expirations(get_stock_price_fn=get_price)

        assert result["needs_review"] == 1
        assert len(db.queued_tasks) == 1
        assert db.queued_tasks[0]["task_type"] == "review_expired_option"

    def test_process_expirations_fallback_high_premium(self):
        """Verify high premium options are flagged for review without price function."""
        db = MockDB()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        # Return expired option with high premium (might have been ITM)
        mock_cursor.fetchall.return_value = [
            {
                "id": 3,
                "ticker": "NVDA",
                "full_symbol": "NVDA  240315P00500000",
                "option_underlying": "NVDA",
                "option_strike": 500.0,
                "option_type": "put",
                "entry_price": 2.50,  # >$0.50 suggests possibly ITM
            }
        ]
        db._conn.cursor.return_value = mock_cursor

        monitor = ExpirationMonitor(db)

        # No price function - use fallback heuristic
        result = monitor.process_expirations(get_stock_price_fn=None)

        assert result["needs_review"] == 1

    def test_get_summary(self):
        """Test get_summary aggregates counts."""
        db = MockDB()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = []
        db._conn.cursor.return_value = mock_cursor

        monitor = ExpirationMonitor(db)
        summary = monitor.get_summary()

        assert "expiring_today" in summary
        assert "critical" in summary
        assert "warning" in summary
        assert "expired" in summary


class TestAssignmentDetection:
    """Tests for assignment detection logic."""

    def test_check_for_assignment_no_short_options(self):
        """No assignments when no short options exist."""
        db = MockDB()
        monitor = ExpirationMonitor(db)

        result = monitor.check_for_assignment("NVDA", [])

        assert result == []

    def test_check_for_assignment_put_detected(self):
        """Detect potential put assignment when stock appears."""
        db = MockDB()

        # Mock short put
        db.get_short_options_by_underlying = MagicMock(return_value=[
            {
                "id": 1,
                "full_symbol": "NVDA  240315P00500000",
                "option_type": "put",
                "option_strike": 500.0,
                "current_size": 1,
                "option_multiplier": 100,
            }
        ])

        monitor = ExpirationMonitor(db)

        # Mock IB position showing 100 shares of stock appeared
        mock_ib_pos = MagicMock()
        mock_ib_pos.symbol = "NVDA"
        mock_ib_pos.is_option = False
        mock_ib_pos.position = 100  # 100 shares = 1 contract assigned

        result = monitor.check_for_assignment("NVDA", [mock_ib_pos])

        assert len(result) == 1
        assert result[0]["type"] == "put_assignment"
        assert result[0]["expected_shares"] == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
