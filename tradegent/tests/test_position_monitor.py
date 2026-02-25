"""Unit tests for position monitor module."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from decimal import Decimal

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from position_monitor import (
    PositionMonitor,
    PositionDelta,
    IBPosition,
    normalize_ib_symbol,
    parse_ib_positions,
)


class TestNormalizeIBSymbol:
    """Tests for normalize_ib_symbol function."""

    def test_stock_symbol(self):
        """Test normalizing a stock symbol."""
        assert normalize_ib_symbol("NVDA") == "NVDA"
        assert normalize_ib_symbol("aapl") == "AAPL"
        assert normalize_ib_symbol("Msft") == "MSFT"

    def test_option_symbol_with_spaces(self):
        """Test normalizing option symbol with multiple spaces."""
        assert normalize_ib_symbol("NVDA  240315C00500000") == "NVDA"
        assert normalize_ib_symbol("AAPL 240419P00150000") == "AAPL"

    def test_empty_symbol(self):
        """Test handling empty symbol."""
        assert normalize_ib_symbol("") == ""
        assert normalize_ib_symbol(None) == ""

    def test_whitespace_only(self):
        """Test handling whitespace-only symbol."""
        assert normalize_ib_symbol("   ") == ""


class TestParseIBPositions:
    """Tests for parse_ib_positions function."""

    def test_parse_standard_positions(self):
        """Test parsing standard position format."""
        raw = [
            {"symbol": "NVDA", "position": 100, "avgCost": 125.50, "marketValue": 12800, "unrealizedPnl": 250},
            {"symbol": "AAPL", "position": 50, "avgCost": 175.00, "marketValue": 8750, "unrealizedPnl": -100},
        ]
        positions = parse_ib_positions(raw)
        assert len(positions) == 2
        assert positions[0].symbol == "NVDA"
        assert positions[0].position == 100
        assert positions[0].avg_cost == 125.50
        assert positions[1].symbol == "AAPL"

    def test_parse_alternative_field_names(self):
        """Test parsing with alternative field names."""
        raw = [
            {"symbol": "NVDA", "pos": 100, "avg_cost": 125.50, "market_value": 12800, "unrealized_pnl": 250},
        ]
        positions = parse_ib_positions(raw)
        assert len(positions) == 1
        assert positions[0].position == 100
        assert positions[0].avg_cost == 125.50

    def test_filter_zero_positions(self):
        """Test that zero positions are filtered out."""
        raw = [
            {"symbol": "NVDA", "position": 100, "avgCost": 125.50, "marketValue": 12800, "unrealizedPnl": 250},
            {"symbol": "AAPL", "position": 0, "avgCost": 0, "marketValue": 0, "unrealizedPnl": 0},
        ]
        positions = parse_ib_positions(raw)
        assert len(positions) == 1
        assert positions[0].symbol == "NVDA"

    def test_detect_options(self):
        """Test option detection."""
        raw = [
            {"symbol": "NVDA  240315C00500000", "position": 10, "avgCost": 5.00, "marketValue": 50, "unrealizedPnl": 0},
        ]
        positions = parse_ib_positions(raw)
        assert len(positions) == 1
        assert positions[0].symbol == "NVDA"
        assert positions[0].is_option is True

    def test_empty_positions(self):
        """Test parsing empty positions list."""
        positions = parse_ib_positions([])
        assert positions == []


class TestPositionDelta:
    """Tests for PositionDelta dataclass."""

    def test_create_delta(self):
        """Test creating a position delta."""
        delta = PositionDelta(
            ticker="NVDA",
            trade_id=1,
            action="closed",
            db_size=Decimal("100"),
            ib_size=Decimal("0"),
            direction="long",
            last_price=Decimal("130.00"),
        )
        assert delta.ticker == "NVDA"
        assert delta.action == "closed"
        assert delta.direction == "long"

    def test_default_direction(self):
        """Test default direction is long."""
        delta = PositionDelta(
            ticker="NVDA",
            trade_id=1,
            action="closed",
            db_size=Decimal("100"),
            ib_size=Decimal("0"),
        )
        assert delta.direction == "long"

    def test_size_difference(self):
        """Test size_difference property."""
        delta = PositionDelta(
            ticker="NVDA",
            trade_id=0,
            action="increase",
            db_size=Decimal("100"),
            ib_size=Decimal("150"),
            direction="long",
            ib_avg_cost=Decimal("500"),
            last_price=Decimal("510"),
        )
        assert delta.size_difference == Decimal("50.0000")

    def test_is_new_position_true(self):
        """Test is_new_position is True for new positions."""
        delta = PositionDelta(
            ticker="NVDA",
            trade_id=0,
            action="increase",
            db_size=Decimal("0"),
            ib_size=Decimal("100"),
            direction="long",
            ib_avg_cost=Decimal("500"),
            last_price=Decimal("510"),
        )
        assert delta.is_new_position is True

    def test_is_new_position_false(self):
        """Test is_new_position is False for existing positions."""
        delta = PositionDelta(
            ticker="NVDA",
            trade_id=0,
            action="increase",
            db_size=Decimal("50"),
            ib_size=Decimal("100"),
            direction="long",
            ib_avg_cost=Decimal("500"),
            last_price=Decimal("510"),
        )
        assert delta.is_new_position is False


class TestPositionMonitor:
    """Tests for PositionMonitor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = MagicMock()
        self.mock_ib = MagicMock()

        # Default settings
        self.mock_db.get_setting.side_effect = lambda key, default=None: {
            "auto_track_position_increases": True,
            "position_detect_min_value": 100,
        }.get(key, default)

        self.monitor = PositionMonitor(self.mock_db, self.mock_ib)

    def test_check_positions_no_open_trades(self):
        """Test check_positions with no open trades."""
        self.mock_db.get_all_open_trades.return_value = []
        self.mock_db.get_trades_with_pending_orders.return_value = []
        self.mock_ib.get_positions.return_value = []
        deltas = self.monitor.check_positions()
        assert deltas == []

    def test_check_positions_ib_unavailable(self):
        """Test check_positions when IB is unavailable."""
        self.mock_db.get_all_open_trades.return_value = [
            {"id": 1, "ticker": "NVDA", "entry_size": 100, "direction": "long"}
        ]
        self.mock_db.get_trades_with_pending_orders.return_value = []
        self.mock_ib.get_positions.return_value = None
        deltas = self.monitor.check_positions()
        assert deltas == []

    def test_check_positions_position_closed(self):
        """Test detecting a closed position."""
        self.mock_db.get_all_open_trades.return_value = [
            {"id": 1, "ticker": "NVDA", "entry_size": 100, "entry_date": datetime.now(), "direction": "long"}
        ]
        self.mock_db.get_trades_with_pending_orders.return_value = []
        self.mock_ib.get_positions.return_value = []  # No IB positions
        self.mock_ib.get_stock_price.return_value = {"last": 130.00}

        deltas = self.monitor.check_positions()
        assert len(deltas) == 1
        assert deltas[0].ticker == "NVDA"
        assert deltas[0].action == "closed"
        assert deltas[0].last_price == Decimal("130.0")

    def test_check_positions_partial_close(self):
        """Test detecting a partial close."""
        self.mock_db.get_all_open_trades.return_value = [
            {"id": 1, "ticker": "NVDA", "entry_size": 100, "entry_date": datetime.now(), "direction": "long"}
        ]
        self.mock_db.get_trades_with_pending_orders.return_value = []
        self.mock_ib.get_positions.return_value = [
            {"symbol": "NVDA", "position": 50, "avgCost": 125.00, "marketValue": 6500, "unrealizedPnl": 100}
        ]
        self.mock_ib.get_stock_price.return_value = {"last": 130.00}

        deltas = self.monitor.check_positions()
        assert len(deltas) == 1
        assert deltas[0].action == "partial"
        assert deltas[0].ib_size == Decimal("50")

    def test_check_positions_no_change(self):
        """Test no delta when position unchanged."""
        self.mock_db.get_all_open_trades.return_value = [
            {"id": 1, "ticker": "NVDA", "entry_size": 100, "entry_date": datetime.now(), "direction": "long"}
        ]
        self.mock_db.get_trades_with_pending_orders.return_value = []
        self.mock_ib.get_positions.return_value = [
            {"symbol": "NVDA", "position": 100, "avgCost": 125.00, "marketValue": 13000, "unrealizedPnl": 500}
        ]

        deltas = self.monitor.check_positions()
        assert deltas == []

    def test_process_deltas_close(self):
        """Test processing a close delta."""
        delta = PositionDelta(
            ticker="NVDA",
            trade_id=1,
            action="closed",
            db_size=Decimal("100"),
            ib_size=Decimal("0"),
            direction="long",
            last_price=Decimal("130.00"),
        )
        self.mock_db.get_open_trades_by_ticker.return_value = []
        # Mock get_trade to return a stock trade (no option_underlying)
        self.mock_db.get_trade.return_value = {"id": 1, "ticker": "NVDA", "option_underlying": None}

        results = self.monitor.process_deltas([delta])
        assert results["closed"] == 1
        self.mock_db.close_trade_with_direction.assert_called_once_with(1, 130.00, "position_monitor", "long")

    def test_process_deltas_partial(self):
        """Test processing a partial close delta."""
        delta = PositionDelta(
            ticker="NVDA",
            trade_id=1,
            action="partial",
            db_size=Decimal("100"),
            ib_size=Decimal("50"),
            direction="long",
        )

        results = self.monitor.process_deltas([delta])
        assert results["partial"] == 1
        self.mock_db.update_trade_size.assert_called_once_with(1, 50.0)


class TestPositionIncreaseDetection:
    """Tests for position increase detection (IPLAN-005)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = MagicMock()
        self.mock_ib = MagicMock()

        # Default settings
        self.mock_db.get_setting.side_effect = lambda key, default=None: {
            "auto_track_position_increases": True,
            "position_detect_min_value": 100,
        }.get(key, default)

        self.monitor = PositionMonitor(self.mock_db, self.mock_ib)

    def test_detect_position_increase(self):
        """Test detecting a position increase from external source."""
        # Use 75 shares increase to avoid split ratio detection (ratio 1.75 not a split pattern)
        self.mock_db.get_all_open_trades.return_value = [
            {"id": 1, "ticker": "NVDA", "entry_size": 100, "entry_date": datetime.now(), "direction": "long"}
        ]
        self.mock_db.get_trades_with_pending_orders.return_value = []
        self.mock_ib.get_positions.return_value = [
            {"symbol": "NVDA", "position": 175, "avgCost": 480.00, "marketValue": 84000, "unrealizedPnl": 500}
        ]
        self.mock_ib.get_stock_price.return_value = {"last": 500.00}

        deltas = self.monitor.check_positions()

        # Should have one increase delta
        increase_deltas = [d for d in deltas if d.action == "increase"]
        assert len(increase_deltas) == 1
        assert increase_deltas[0].ticker == "NVDA"
        assert increase_deltas[0].size_difference == Decimal("75.0000")

    def test_skip_ticker_with_pending_orders(self):
        """Position check should skip tickers with pending orchestrator orders."""
        self.mock_db.get_all_open_trades.return_value = [
            {"id": 1, "ticker": "NVDA", "entry_size": 50, "entry_date": datetime.now(), "direction": "long"}
        ]
        self.mock_db.get_trades_with_pending_orders.return_value = [{"ticker": "NVDA"}]
        self.mock_ib.get_positions.return_value = [
            {"symbol": "NVDA", "position": 100, "avgCost": 480.00, "marketValue": 48000, "unrealizedPnl": 500}
        ]
        self.mock_ib.get_stock_price.return_value = {"last": 500.00}

        deltas = self.monitor.check_positions()

        # Should not have increase delta (ticker has pending orders)
        increase_deltas = [d for d in deltas if d.action == "increase"]
        assert len(increase_deltas) == 0

    def test_detect_new_position(self):
        """Test detecting a completely new position not in DB."""
        self.mock_db.get_all_open_trades.return_value = []  # No open trades
        self.mock_db.get_trades_with_pending_orders.return_value = []
        self.mock_ib.get_positions.return_value = [
            {"symbol": "AAPL", "position": 100, "avgCost": 175.00, "marketValue": 17500, "unrealizedPnl": 0}
        ]
        self.mock_ib.get_stock_price.return_value = {"last": 180.00}

        deltas = self.monitor.check_positions()

        assert len(deltas) == 1
        assert deltas[0].ticker == "AAPL"
        assert deltas[0].action == "increase"
        assert deltas[0].is_new_position is True

    def test_idempotency_prevents_duplicate(self):
        """Should not create duplicate trade for same detection today."""
        self.mock_db.get_position_detections_today.return_value = [
            {"ticker": "NVDA", "size": 50.0, "trade_id": 5}
        ]

        delta = PositionDelta(
            ticker="NVDA",
            trade_id=0,
            action="increase",
            db_size=Decimal("50"),
            ib_size=Decimal("100"),
            direction="long",
            ib_avg_cost=Decimal("500"),
            last_price=Decimal("510"),
        )

        self.monitor._handle_increase(delta)

        # Should not call add_trade_detected
        self.mock_db.add_trade_detected.assert_not_called()

    def test_minimum_value_threshold(self):
        """Should skip positions below minimum value threshold."""
        self.mock_db.get_position_detections_today.return_value = []

        delta = PositionDelta(
            ticker="PENNY",
            trade_id=0,
            action="increase",
            db_size=Decimal("0"),
            ib_size=Decimal("10"),
            direction="long",
            ib_avg_cost=Decimal("5"),
            last_price=Decimal("5"),  # Value = 10 * $5 = $50 < $100 threshold
        )

        self.monitor._handle_increase(delta)

        # Should not call add_trade_detected
        self.mock_db.add_trade_detected.assert_not_called()

    def test_entry_price_uses_avg_cost_for_new_position(self):
        """New position should use IB avg cost as entry price."""
        delta = PositionDelta(
            ticker="NVDA",
            trade_id=0,
            action="increase",
            db_size=Decimal("0"),
            ib_size=Decimal("100"),  # New position
            direction="long",
            ib_avg_cost=Decimal("500"),
            last_price=Decimal("510"),
        )

        price = self.monitor._estimate_entry_price(delta)
        assert price == Decimal("500")

    def test_entry_price_uses_last_for_existing_position(self):
        """Existing position should use last price (avg is blended)."""
        delta = PositionDelta(
            ticker="NVDA",
            trade_id=0,
            action="increase",
            db_size=Decimal("50"),
            ib_size=Decimal("100"),  # Existing
            direction="long",
            ib_avg_cost=Decimal("500"),
            last_price=Decimal("510"),
        )

        price = self.monitor._estimate_entry_price(delta)
        assert price == Decimal("510")

    def test_corporate_action_detection_split(self):
        """Should detect likely stock split (2:1, 4:1, etc.)."""
        assert self.monitor._is_likely_corporate_action(
            ticker="NVDA",
            db_size=100,
            ib_size=400,  # 4:1 split
            ib_avg_cost=Decimal("125")
        ) is True

    def test_corporate_action_detection_reverse_split(self):
        """Should detect likely reverse split."""
        assert self.monitor._is_likely_corporate_action(
            ticker="NVDA",
            db_size=100,
            ib_size=50,  # 1:2 reverse split
            ib_avg_cost=Decimal("250")
        ) is True

    def test_no_corporate_action_for_irregular_ratio(self):
        """Should not flag irregular ratio as corporate action."""
        assert self.monitor._is_likely_corporate_action(
            ticker="NVDA",
            db_size=100,
            ib_size=150,  # 1.5x not a split pattern
            ib_avg_cost=Decimal("200")
        ) is False

    def test_handle_increase_creates_trade(self):
        """Test that _handle_increase creates trade entry."""
        self.mock_db.get_position_detections_today.return_value = []
        self.mock_db.add_trade_detected.return_value = 42

        delta = PositionDelta(
            ticker="NVDA",
            trade_id=0,
            action="increase",
            db_size=Decimal("0"),
            ib_size=Decimal("100"),
            direction="long",
            ib_avg_cost=Decimal("500"),
            last_price=Decimal("510"),
        )

        self.monitor._handle_increase(delta)

        # Should call add_trade_detected
        self.mock_db.add_trade_detected.assert_called_once()
        trade_arg = self.mock_db.add_trade_detected.call_args[0][0]
        assert trade_arg["ticker"] == "NVDA"
        assert trade_arg["source_type"] == "detected"
        assert trade_arg["entry_price"] == 500.0

        # Should queue task
        self.mock_db.queue_task.assert_called_once()

        # Should record detection (includes full_symbol for options support)
        self.mock_db.record_position_detection.assert_called_once_with(
            ticker="NVDA",
            size=100.0,
            trade_id=42,
            full_symbol="NVDA",  # For stocks, full_symbol equals ticker
        )

    def test_process_deltas_increase_with_auto_track_disabled(self):
        """Test that increase is skipped when auto_track disabled."""
        self.monitor._settings["auto_track_position_increases"] = False

        delta = PositionDelta(
            ticker="NVDA",
            trade_id=0,
            action="increase",
            db_size=Decimal("0"),
            ib_size=Decimal("100"),
            direction="long",
            ib_avg_cost=Decimal("500"),
            last_price=Decimal("510"),
        )

        results = self.monitor.process_deltas([delta])
        assert results["increase"] == 0
        self.mock_db.add_trade_detected.assert_not_called()
