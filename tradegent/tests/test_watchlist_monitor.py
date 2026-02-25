"""
Tests for watchlist trigger monitoring (IPLAN-004).

Tests cover:
- parse_trigger() natural language parsing
- ConditionEvaluator market data evaluation
- WatchlistMonitor orchestration
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from watchlist_monitor import (
    parse_trigger,
    ConditionType,
    ParsedCondition,
    ConditionEvaluator,
    WatchlistMonitor,
    MonitorResults,
    MonitorEvent,
)
from ib_client import Quote


# ─── parse_trigger() Tests ──────────────────────────────────────────────────────


class TestParseTrigger:
    """Tests for trigger condition parsing."""

    def test_parse_price_above_breaks(self):
        result = parse_trigger("Price breaks above $150")
        assert result.type == ConditionType.PRICE_ABOVE
        assert result.value == 150.0

    def test_parse_price_above_crosses(self):
        result = parse_trigger("Crosses above 145.50")
        assert result.type == ConditionType.PRICE_ABOVE
        assert result.value == 145.50

    def test_parse_price_above_over(self):
        result = parse_trigger("Above $160")
        assert result.type == ConditionType.PRICE_ABOVE
        assert result.value == 160.0

    def test_parse_price_above_no_dollar(self):
        result = parse_trigger("breaks over 125")
        assert result.type == ConditionType.PRICE_ABOVE
        assert result.value == 125.0

    def test_parse_price_below_drops(self):
        result = parse_trigger("Drops below $140")
        assert result.type == ConditionType.PRICE_BELOW
        assert result.value == 140.0

    def test_parse_price_below_falls(self):
        result = parse_trigger("Falls below 135")
        assert result.type == ConditionType.PRICE_BELOW
        assert result.value == 135.0

    def test_parse_price_below_under(self):
        result = parse_trigger("Under $120")
        assert result.type == ConditionType.PRICE_BELOW
        assert result.value == 120.0

    def test_parse_support_hold(self):
        result = parse_trigger("Holds $145 support")
        assert result.type == ConditionType.SUPPORT_HOLD
        assert result.value == 145.0

    def test_parse_support_holds(self):
        result = parse_trigger("Price holds 142.50 support")
        assert result.type == ConditionType.SUPPORT_HOLD
        assert result.value == 142.50

    def test_parse_resistance_break(self):
        result = parse_trigger("Breaks $160 resistance")
        assert result.type == ConditionType.RESISTANCE_BREAK
        assert result.value == 160.0

    def test_parse_resistance_break_variant(self):
        result = parse_trigger("Break 155 resistance")
        assert result.type == ConditionType.RESISTANCE_BREAK
        assert result.value == 155.0

    def test_parse_date_before_earnings(self):
        result = parse_trigger("Before earnings on 2026-03-15")
        assert result.type == ConditionType.DATE_BEFORE
        assert result.value == "2026-03-15"

    def test_parse_date_before_simple(self):
        result = parse_trigger("Before 2026-04-01")
        assert result.type == ConditionType.DATE_BEFORE
        assert result.value == "2026-04-01"

    def test_parse_date_after(self):
        result = parse_trigger("After 2026-05-01")
        assert result.type == ConditionType.DATE_AFTER
        assert result.value == "2026-05-01"

    def test_parse_volume_above_adv(self):
        result = parse_trigger("Volume > 2x ADV")
        assert result.type == ConditionType.VOLUME_ABOVE
        assert result.value == 2.0

    def test_parse_volume_above_average(self):
        result = parse_trigger("volume > 1.5x average")
        assert result.type == ConditionType.VOLUME_ABOVE
        assert result.value == 1.5

    def test_parse_custom_fallback(self):
        result = parse_trigger("Wait for Fed meeting")
        assert result.type == ConditionType.CUSTOM
        assert result.confidence == 0.0
        assert result.raw_text == "Wait for Fed meeting"

    def test_parse_custom_complex(self):
        result = parse_trigger("Buy when RSI oversold and MACD crosses bullish")
        assert result.type == ConditionType.CUSTOM
        assert result.confidence == 0.0

    def test_parse_preserves_raw_text(self):
        original = "Price breaks above $150.00"
        result = parse_trigger(original)
        assert result.raw_text == original


# ─── ConditionEvaluator Tests ───────────────────────────────────────────────────


class TestConditionEvaluator:
    """Tests for condition evaluation against market data."""

    @pytest.fixture
    def mock_ib_client(self):
        """Mock IB client that returns a predictable quote."""
        client = Mock()
        client.get_quote.return_value = Quote(
            symbol="NVDA",
            last=150.0,
            bid=149.90,
            ask=150.10,
            volume=1000000,
            close=148.0
        )
        return client

    @pytest.fixture
    def evaluator(self, mock_ib_client):
        return ConditionEvaluator(mock_ib_client, price_tolerance_pct=0.5)

    # Price Above Tests
    def test_price_above_met(self, evaluator):
        condition = ParsedCondition(ConditionType.PRICE_ABOVE, 149.0)
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is True
        assert "150.00" in reason
        assert ">= target" in reason

    def test_price_above_not_met(self, evaluator):
        condition = ParsedCondition(ConditionType.PRICE_ABOVE, 155.0)
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is False
        assert "< target" in reason

    def test_price_above_with_tolerance(self, evaluator):
        # Price is 150, target is 150.5, tolerance is 0.5% = 0.75
        # So 150 >= 150.5 - 0.75 = 149.75 -> True
        condition = ParsedCondition(ConditionType.PRICE_ABOVE, 150.5)
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is True

    def test_price_above_exact_match(self, evaluator):
        condition = ParsedCondition(ConditionType.PRICE_ABOVE, 150.0)
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is True

    # Price Below Tests
    def test_price_below_met(self, evaluator):
        condition = ParsedCondition(ConditionType.PRICE_BELOW, 155.0)
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is True
        assert "<= target" in reason

    def test_price_below_not_met(self, evaluator):
        condition = ParsedCondition(ConditionType.PRICE_BELOW, 145.0)
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is False
        assert "> target" in reason

    def test_price_below_with_tolerance(self, evaluator):
        # Price is 150, target is 149.5, tolerance is 0.5% = 0.75
        # So 150 <= 149.5 + 0.75 = 150.25 -> True
        condition = ParsedCondition(ConditionType.PRICE_BELOW, 149.5)
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is True

    # Support Hold Tests
    def test_support_hold_counting(self, evaluator):
        condition = ParsedCondition(ConditionType.SUPPORT_HOLD, 145.0)

        # First check - should not be met yet (1/3)
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is False
        assert "1/3" in reason

        # Second check (2/3)
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is False
        assert "2/3" in reason

        # Third check - now met (3/3)
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is True
        assert "held" in reason

    def test_support_hold_broken_resets_count(self, evaluator, mock_ib_client):
        condition = ParsedCondition(ConditionType.SUPPORT_HOLD, 155.0)

        # Price at 150 is below 155 support
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is False
        assert "broken" in reason

    # Resistance Break Tests
    def test_resistance_break_met(self, evaluator):
        condition = ParsedCondition(ConditionType.RESISTANCE_BREAK, 149.0)
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is True
        assert "broke resistance" in reason

    def test_resistance_break_not_met(self, evaluator):
        condition = ParsedCondition(ConditionType.RESISTANCE_BREAK, 155.0)
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is False
        assert "below resistance" in reason

    # Date Condition Tests
    def test_date_before_met(self, evaluator):
        future_date = (date.today() + timedelta(days=7)).isoformat()
        condition = ParsedCondition(ConditionType.DATE_BEFORE, future_date)
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is True
        assert "is before" in reason

    def test_date_before_not_met(self, evaluator):
        past_date = (date.today() - timedelta(days=7)).isoformat()
        condition = ParsedCondition(ConditionType.DATE_BEFORE, past_date)
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is False
        assert "has passed" in reason

    def test_date_after_met(self, evaluator):
        past_date = (date.today() - timedelta(days=1)).isoformat()
        condition = ParsedCondition(ConditionType.DATE_AFTER, past_date)
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is True

    def test_date_after_not_met(self, evaluator):
        future_date = (date.today() + timedelta(days=7)).isoformat()
        condition = ParsedCondition(ConditionType.DATE_AFTER, future_date)
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is False

    # Edge Cases
    def test_custom_never_met(self, evaluator):
        condition = ParsedCondition(ConditionType.CUSTOM, raw_text="something custom")
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is False
        assert "manual" in reason.lower()

    def test_no_quote_returns_false(self, evaluator, mock_ib_client):
        mock_ib_client.get_quote.return_value = None
        condition = ParsedCondition(ConditionType.PRICE_ABOVE, 150.0)
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is False
        assert "No quote" in reason

    def test_no_price_data_returns_false(self, evaluator, mock_ib_client):
        mock_ib_client.get_quote.return_value = Quote(
            symbol="NVDA", last=None, bid=None, ask=None, volume=None, close=None
        )
        condition = ParsedCondition(ConditionType.PRICE_ABOVE, 150.0)
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is False
        assert "No price data" in reason

    def test_uses_close_when_last_unavailable(self, evaluator, mock_ib_client):
        mock_ib_client.get_quote.return_value = Quote(
            symbol="NVDA", last=None, bid=None, ask=None, volume=None, close=148.0
        )
        condition = ParsedCondition(ConditionType.PRICE_ABOVE, 145.0)
        is_met, reason = evaluator.evaluate("NVDA", condition)
        assert is_met is True
        assert "148.00" in reason


# ─── WatchlistMonitor Tests ─────────────────────────────────────────────────────


class TestWatchlistMonitor:
    """Tests for watchlist monitor orchestration."""

    @pytest.fixture
    def mock_db(self):
        db = Mock()
        db.get_active_watchlist.return_value = []
        db.update_watchlist_status.return_value = True
        db.queue_task.return_value = 1
        return db

    @pytest.fixture
    def mock_ib_client(self):
        client = Mock()
        client.get_quotes_batch.return_value = {}
        client.health_check.return_value = True
        return client

    @pytest.fixture
    def monitor(self, mock_db, mock_ib_client):
        return WatchlistMonitor(mock_db, mock_ib_client)

    def test_empty_watchlist(self, monitor):
        results = monitor.check_entries()
        assert results.checked == 0
        assert results.triggered == 0
        assert results.invalidated == 0
        assert results.expired == 0

    def test_expired_entry(self, monitor, mock_db):
        mock_db.get_active_watchlist.return_value = [{
            "id": 1,
            "ticker": "NVDA",
            "entry_trigger": "Price above $150",
            "invalidation": None,
            "priority": "high",
            "status": "active",
            "created_at": datetime.now() - timedelta(days=10),
            "expires_at": datetime.now() - timedelta(days=1),
            "entry_price": None,
            "invalidation_price": None,
        }]

        results = monitor.check_entries()
        assert results.checked == 1
        assert results.expired == 1
        assert results.triggered == 0
        mock_db.update_watchlist_status.assert_called_once()

    def test_triggered_entry(self, monitor, mock_db, mock_ib_client):
        mock_db.get_active_watchlist.return_value = [{
            "id": 1,
            "ticker": "NVDA",
            "entry_trigger": "Price above $140",
            "invalidation": None,
            "priority": "high",
            "status": "active",
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=7),
            "entry_price": None,
            "invalidation_price": None,
        }]
        mock_ib_client.get_quotes_batch.return_value = {
            "NVDA": Quote("NVDA", last=150.0, bid=149.9, ask=150.1, volume=1000000, close=148.0)
        }

        results = monitor.check_entries()
        assert results.checked == 1
        assert results.triggered == 1
        assert results.invalidated == 0
        assert len(results.events) == 1
        assert results.events[0].event_type == "triggered"

    def test_triggered_by_entry_price(self, monitor, mock_db, mock_ib_client):
        """Test that entry_price field can trigger."""
        mock_db.get_active_watchlist.return_value = [{
            "id": 1,
            "ticker": "NVDA",
            "entry_trigger": None,  # No text trigger
            "invalidation": None,
            "priority": "medium",
            "status": "active",
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=7),
            "entry_price": 145.0,  # Price-based trigger
            "invalidation_price": None,
        }]
        mock_ib_client.get_quotes_batch.return_value = {
            "NVDA": Quote("NVDA", last=150.0, bid=149.9, ask=150.1, volume=1000000, close=148.0)
        }

        results = monitor.check_entries()
        assert results.triggered == 1

    def test_invalidated_entry(self, monitor, mock_db, mock_ib_client):
        mock_db.get_active_watchlist.return_value = [{
            "id": 1,
            "ticker": "NVDA",
            "entry_trigger": "Price above $160",
            "invalidation": "Drops below $140",
            "priority": "high",
            "status": "active",
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=7),
            "entry_price": None,
            "invalidation_price": None,
        }]
        mock_ib_client.get_quotes_batch.return_value = {
            "NVDA": Quote("NVDA", last=135.0, bid=134.9, ask=135.1, volume=1000000, close=142.0)
        }

        results = monitor.check_entries()
        assert results.checked == 1
        assert results.invalidated == 1
        assert results.triggered == 0

    def test_invalidated_by_price(self, monitor, mock_db, mock_ib_client):
        """Test that invalidation_price field can invalidate."""
        mock_db.get_active_watchlist.return_value = [{
            "id": 1,
            "ticker": "NVDA",
            "entry_trigger": "Price above $160",
            "invalidation": None,  # No text invalidation
            "priority": "high",
            "status": "active",
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=7),
            "entry_price": None,
            "invalidation_price": 140.0,  # Stop level
        }]
        mock_ib_client.get_quotes_batch.return_value = {
            "NVDA": Quote("NVDA", last=135.0, bid=134.9, ask=135.1, volume=1000000, close=142.0)
        }

        results = monitor.check_entries()
        assert results.invalidated == 1

    def test_neither_triggered_nor_invalidated(self, monitor, mock_db, mock_ib_client):
        """Entry that doesn't meet any condition yet."""
        mock_db.get_active_watchlist.return_value = [{
            "id": 1,
            "ticker": "NVDA",
            "entry_trigger": "Price above $160",  # Need 160
            "invalidation": "Drops below $130",  # Invalidate at 130
            "priority": "medium",
            "status": "active",
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=7),
            "entry_price": None,
            "invalidation_price": None,
        }]
        mock_ib_client.get_quotes_batch.return_value = {
            "NVDA": Quote("NVDA", last=150.0, bid=149.9, ask=150.1, volume=1000000, close=148.0)
        }

        results = monitor.check_entries()
        assert results.checked == 1
        assert results.triggered == 0
        assert results.invalidated == 0
        assert results.expired == 0

    def test_event_callback(self, mock_db, mock_ib_client):
        events = []
        monitor = WatchlistMonitor(
            mock_db,
            mock_ib_client,
            on_event=lambda e: events.append(e)
        )

        mock_db.get_active_watchlist.return_value = [{
            "id": 1,
            "ticker": "NVDA",
            "entry_trigger": "Price above $140",
            "invalidation": None,
            "priority": "high",
            "status": "active",
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=7),
            "entry_price": None,
            "invalidation_price": None,
        }]
        mock_ib_client.get_quotes_batch.return_value = {
            "NVDA": Quote("NVDA", last=150.0, bid=149.9, ask=150.1, volume=1000000, close=148.0)
        }

        monitor.check_entries()

        assert len(events) == 1
        assert events[0].event_type == "triggered"
        assert events[0].ticker == "NVDA"

    def test_multiple_entries(self, monitor, mock_db, mock_ib_client):
        """Test with multiple watchlist entries."""
        mock_db.get_active_watchlist.return_value = [
            {
                "id": 1,
                "ticker": "NVDA",
                "entry_trigger": "Price above $140",
                "invalidation": None,
                "priority": "high",
                "status": "active",
                "created_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=7),
                "entry_price": None,
                "invalidation_price": None,
            },
            {
                "id": 2,
                "ticker": "AAPL",
                "entry_trigger": "Price above $200",  # Won't be met
                "invalidation": None,
                "priority": "medium",
                "status": "active",
                "created_at": datetime.now(),
                "expires_at": datetime.now() - timedelta(days=1),  # Expired
                "entry_price": None,
                "invalidation_price": None,
            },
            {
                "id": 3,
                "ticker": "MSFT",
                "entry_trigger": "Price above $400",
                "invalidation": "Drops below $350",
                "priority": "low",
                "status": "active",
                "created_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=7),
                "entry_price": None,
                "invalidation_price": None,
            },
        ]
        mock_ib_client.get_quotes_batch.return_value = {
            "NVDA": Quote("NVDA", last=150.0, bid=149.9, ask=150.1, volume=1000000, close=148.0),
            "AAPL": Quote("AAPL", last=180.0, bid=179.9, ask=180.1, volume=500000, close=178.0),
            "MSFT": Quote("MSFT", last=340.0, bid=339.9, ask=340.1, volume=300000, close=338.0),
        }

        results = monitor.check_entries()
        assert results.checked == 3
        assert results.triggered == 1  # NVDA
        assert results.expired == 1  # AAPL
        assert results.invalidated == 1  # MSFT (below 350)

    def test_error_handling(self, monitor, mock_db, mock_ib_client):
        """Test that errors in one entry don't stop others."""
        mock_db.get_active_watchlist.return_value = [
            {
                "id": 1,
                "ticker": "NVDA",
                "entry_trigger": "Price above $140",
                "invalidation": None,
                "priority": "high",
                "status": "active",
                "created_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=7),
                "entry_price": None,
                "invalidation_price": None,
            },
            {
                "id": 2,
                "ticker": "AAPL",
                "entry_trigger": "Price above $180",
                "invalidation": None,
                "priority": "medium",
                "status": "active",
                "created_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=7),
                "entry_price": None,
                "invalidation_price": None,
            }
        ]

        # Return quotes, but make update_watchlist_status fail for first entry
        mock_ib_client.get_quotes_batch.return_value = {
            "NVDA": Quote("NVDA", last=150.0, bid=149.9, ask=150.1, volume=1000000, close=148.0),
            "AAPL": Quote("AAPL", last=190.0, bid=189.9, ask=190.1, volume=500000, close=188.0),
        }

        # Make update fail for first entry (NVDA triggers, update raises)
        def update_side_effect(entry_id, status, notes=None):
            if entry_id == 1:
                raise Exception("Database error")
            return True
        mock_db.update_watchlist_status.side_effect = update_side_effect

        results = monitor.check_entries()
        # First entry errors, second entry triggers successfully
        assert results.checked == 2
        assert results.errors == 1
        assert results.triggered == 1  # AAPL should still trigger
        # First error event, then triggered event
        error_events = [e for e in results.events if e.event_type == "error"]
        assert len(error_events) == 1

    def test_queues_task_on_trigger(self, monitor, mock_db, mock_ib_client):
        """Test that triggered entries queue a task."""
        mock_db.get_active_watchlist.return_value = [{
            "id": 1,
            "ticker": "NVDA",
            "entry_trigger": "Price above $140",
            "invalidation": None,
            "priority": "high",
            "status": "active",
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=7),
            "entry_price": None,
            "invalidation_price": None,
        }]
        mock_ib_client.get_quotes_batch.return_value = {
            "NVDA": Quote("NVDA", last=150.0, bid=149.9, ask=150.1, volume=1000000, close=148.0)
        }

        monitor.check_entries()

        mock_db.queue_task.assert_called_once()
        call_args = mock_db.queue_task.call_args
        assert call_args.kwargs["task_type"] == "watchlist_triggered"
        assert call_args.kwargs["ticker"] == "NVDA"
        assert call_args.kwargs["priority"] == 8


class TestMonitorResults:
    """Tests for MonitorResults dataclass."""

    def test_str_representation(self):
        results = MonitorResults(
            checked=10,
            triggered=2,
            invalidated=1,
            expired=3,
            errors=0
        )
        s = str(results)
        assert "Checked: 10" in s
        assert "Triggered: 2" in s
        assert "Invalidated: 1" in s
        assert "Expired: 3" in s

    def test_default_values(self):
        results = MonitorResults()
        assert results.checked == 0
        assert results.triggered == 0
        assert results.invalidated == 0
        assert results.expired == 0
        assert results.errors == 0
        assert results.events == []
