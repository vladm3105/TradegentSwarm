"""
Tests for options_utils.py - Symbol parsing, P&L calculation, and helpers.
"""

import pytest
from datetime import date
from decimal import Decimal

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from options_utils import (
    parse_option_symbol,
    is_option_symbol,
    format_option_symbol,
    calculate_options_pnl,
    calculate_max_loss,
    is_itm,
    is_otm,
    calculate_intrinsic_value,
    ParsedOptionSymbol,
)


class TestParseOptionSymbol:
    """Tests for parse_option_symbol function."""

    def test_standard_call(self):
        """Parse standard call option."""
        result = parse_option_symbol("NVDA  240315C00500000")
        assert result is not None
        assert result.underlying == "NVDA"
        assert result.expiration == date(2024, 3, 15)
        assert result.option_type == "call"
        assert result.strike == Decimal("500.000")
        assert result.multiplier == 100
        assert result.is_call is True
        assert result.is_put is False
        assert not result.is_adjusted
        assert not result.is_mini

    def test_standard_put(self):
        """Parse standard put option."""
        result = parse_option_symbol("AAPL  240419P00150000")
        assert result is not None
        assert result.underlying == "AAPL"
        assert result.expiration == date(2024, 4, 19)
        assert result.option_type == "put"
        assert result.strike == Decimal("150.000")

    def test_no_padding(self):
        """Parse option without space padding."""
        result = parse_option_symbol("NVDA240315C00500000")
        assert result is not None
        assert result.underlying == "NVDA"
        assert result.strike == Decimal("500.000")

    def test_adjusted_option(self):
        """Parse adjusted option (post-split)."""
        result = parse_option_symbol("NVDA1 240315C00500000")
        assert result is not None
        assert result.underlying == "NVDA"
        assert result.is_adjusted is True
        assert result.multiplier == 100

    def test_mini_option(self):
        """Parse mini option (10 share multiplier)."""
        result = parse_option_symbol("NVDA7 240315C00500000")
        assert result is not None
        assert result.underlying == "NVDA"
        assert result.is_mini is True
        assert result.multiplier == 10

    def test_leaps(self):
        """Parse LEAPS option (2026+ expiration)."""
        result = parse_option_symbol("NVDA  260116C00500000")
        assert result is not None
        assert result.expiration == date(2026, 1, 16)

    def test_fractional_strike(self):
        """Parse option with fractional strike."""
        result = parse_option_symbol("NVDA  240315C00125500")
        assert result is not None
        assert result.strike == Decimal("125.500")

    def test_invalid_too_short(self):
        """Reject too short symbol."""
        assert parse_option_symbol("NVDA") is None
        assert parse_option_symbol("") is None
        assert parse_option_symbol(None) is None

    def test_invalid_date(self):
        """Reject invalid date."""
        # Month 13 is invalid
        assert parse_option_symbol("NVDA  241315C00500000") is None

    def test_invalid_format(self):
        """Reject non-option symbols."""
        assert parse_option_symbol("NVDA 240315X00500000") is None  # Invalid option type
        assert parse_option_symbol("NVDA random text") is None

    def test_display_name(self):
        """Test display_name property."""
        result = parse_option_symbol("NVDA  240315C00500000")
        assert result.display_name == "NVDA Mar 15 $500 CALL"

    def test_short_name(self):
        """Test short_name property."""
        result = parse_option_symbol("NVDA  240315C00500000")
        assert result.short_name == "NVDA 3/15 500C"


class TestIsOptionSymbol:
    """Tests for is_option_symbol function."""

    def test_valid_options(self):
        assert is_option_symbol("NVDA  240315C00500000") is True
        assert is_option_symbol("AAPL  240419P00150000") is True
        assert is_option_symbol("NVDA240315C00500000") is True

    def test_invalid_options(self):
        assert is_option_symbol("NVDA") is False
        assert is_option_symbol("") is False
        assert is_option_symbol(None) is False


class TestFormatOptionSymbol:
    """Tests for format_option_symbol function."""

    def test_format_call(self):
        result = format_option_symbol("NVDA", date(2024, 3, 15), "call", 500)
        assert result == "NVDA  240315C00500000"

    def test_format_put(self):
        result = format_option_symbol("AAPL", date(2024, 4, 19), "put", 150)
        assert result == "AAPL  240419P00150000"

    def test_format_fractional_strike(self):
        result = format_option_symbol("NVDA", date(2024, 3, 15), "call", 125.5)
        assert result == "NVDA  240315C00125500"

    def test_roundtrip(self):
        """Verify format -> parse roundtrip."""
        original = format_option_symbol("NVDA", date(2024, 3, 15), "call", 500)
        parsed = parse_option_symbol(original)
        assert parsed is not None
        assert parsed.underlying == "NVDA"
        assert parsed.expiration == date(2024, 3, 15)
        assert parsed.option_type == "call"
        assert parsed.strike == Decimal("500.000")


class TestCalculateOptionsPnl:
    """Tests for calculate_options_pnl function."""

    def test_long_call_profit(self):
        """Bought call at $5, sold at $8 -> $300 profit (60%)."""
        pnl_dollars, pnl_pct = calculate_options_pnl(5, 8, 1, 100, False)
        assert pnl_dollars == 300
        assert pnl_pct == 60.0

    def test_long_call_loss(self):
        """Bought call at $5, sold at $2 -> $300 loss (-60%)."""
        pnl_dollars, pnl_pct = calculate_options_pnl(5, 2, 1, 100, False)
        assert pnl_dollars == -300
        assert pnl_pct == -60.0

    def test_short_put_profit(self):
        """Sold put at $3, bought back at $1 -> $200 profit (66.7%)."""
        pnl_dollars, pnl_pct = calculate_options_pnl(3, 1, 1, 100, True)
        assert pnl_dollars == 200
        assert abs(pnl_pct - 66.67) < 0.1

    def test_short_put_loss(self):
        """Sold put at $3, bought back at $5 -> $200 loss (-66.7%)."""
        pnl_dollars, pnl_pct = calculate_options_pnl(3, 5, 1, 100, True)
        assert pnl_dollars == -200
        assert abs(pnl_pct - (-66.67)) < 0.1

    def test_multiple_contracts(self):
        """Multiple contracts scale P&L."""
        pnl_dollars, pnl_pct = calculate_options_pnl(5, 8, 5, 100, False)
        assert pnl_dollars == 1500  # 5 contracts * $300 each
        assert pnl_pct == 60.0  # Percentage stays same

    def test_mini_option(self):
        """Mini option with 10 share multiplier."""
        pnl_dollars, pnl_pct = calculate_options_pnl(5, 8, 1, 10, False)
        assert pnl_dollars == 30  # 1/10th of standard

    def test_zero_entry_price(self):
        """Handle zero entry price (should not divide by zero)."""
        pnl_dollars, pnl_pct = calculate_options_pnl(0, 5, 1, 100, False)
        assert pnl_dollars == 500
        assert pnl_pct == 0.0  # Can't calculate percentage


class TestCalculateMaxLoss:
    """Tests for calculate_max_loss function."""

    def test_long_call_max_loss(self):
        """Long call max loss = premium paid."""
        max_loss = calculate_max_loss(5, 1, 100, "call", 100, False)
        assert max_loss == 500  # $5 * 1 contract * 100 shares

    def test_long_put_max_loss(self):
        """Long put max loss = premium paid."""
        max_loss = calculate_max_loss(3, 2, 100, "put", 50, False)
        assert max_loss == 600  # $3 * 2 contracts * 100 shares

    def test_short_call_max_loss(self):
        """Short call has unlimited risk."""
        max_loss = calculate_max_loss(5, 1, 100, "call", 100, True)
        assert max_loss == -1  # Unlimited

    def test_short_put_max_loss(self):
        """Short put max loss = strike * multiplier - premium."""
        max_loss = calculate_max_loss(3, 1, 100, "put", 50, True)
        # If stock goes to $0: $50 * 100 - $300 premium = $4700
        assert max_loss == 4700


class TestITMOTM:
    """Tests for is_itm and is_otm functions."""

    def test_call_itm(self):
        """Call is ITM when stock > strike."""
        assert is_itm("call", 100, 110) is True
        assert is_itm("call", 100, 90) is False
        assert is_itm("call", 100, 100) is False  # ATM is not ITM

    def test_put_itm(self):
        """Put is ITM when stock < strike."""
        assert is_itm("put", 100, 90) is True
        assert is_itm("put", 100, 110) is False
        assert is_itm("put", 100, 100) is False  # ATM is not ITM

    def test_call_otm(self):
        """Call is OTM when stock <= strike."""
        assert is_otm("call", 100, 90) is True
        assert is_otm("call", 100, 110) is False
        assert is_otm("call", 100, 100) is True  # ATM is OTM

    def test_put_otm(self):
        """Put is OTM when stock >= strike."""
        assert is_otm("put", 100, 110) is True
        assert is_otm("put", 100, 90) is False
        assert is_otm("put", 100, 100) is True  # ATM is OTM


class TestIntrinsicValue:
    """Tests for calculate_intrinsic_value function."""

    def test_call_itm_intrinsic(self):
        """ITM call has intrinsic value."""
        value = calculate_intrinsic_value("call", 100, 110, 100)
        assert value == 1000  # ($110 - $100) * 100

    def test_call_otm_intrinsic(self):
        """OTM call has zero intrinsic value."""
        value = calculate_intrinsic_value("call", 100, 90, 100)
        assert value == 0

    def test_put_itm_intrinsic(self):
        """ITM put has intrinsic value."""
        value = calculate_intrinsic_value("put", 100, 90, 100)
        assert value == 1000  # ($100 - $90) * 100

    def test_put_otm_intrinsic(self):
        """OTM put has zero intrinsic value."""
        value = calculate_intrinsic_value("put", 100, 110, 100)
        assert value == 0

    def test_mini_option_intrinsic(self):
        """Mini option uses 10 share multiplier."""
        value = calculate_intrinsic_value("call", 100, 110, 10)
        assert value == 100  # ($110 - $100) * 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
