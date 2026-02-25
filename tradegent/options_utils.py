"""
Options utilities - Symbol parsing, P&L calculation, and helpers.

Handles OCC (Options Clearing Corporation) option symbol format:
  NVDA  240315C00500000
  │     │     ││
  │     │     │└── Strike price × 1000 (500.00)
  │     │     └─── Option type: C=Call, P=Put
  │     └───────── Expiration: YYMMDD
  └─────────────── Underlying symbol (padded to 6 chars)
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re


@dataclass
class ParsedOptionSymbol:
    """Parsed OCC option symbol."""
    underlying: str
    expiration: date
    option_type: str  # 'call' or 'put'
    strike: Decimal
    raw_symbol: str
    multiplier: int = 100
    is_adjusted: bool = False  # Post corporate action
    is_mini: bool = False      # 10 share multiplier

    @property
    def is_call(self) -> bool:
        return self.option_type == "call"

    @property
    def is_put(self) -> bool:
        return self.option_type == "put"

    @property
    def days_to_expiry(self) -> int:
        return (self.expiration - date.today()).days

    @property
    def is_expired(self) -> bool:
        return self.days_to_expiry < 0

    @property
    def display_name(self) -> str:
        """Human-readable format: NVDA Mar 15 $500 CALL"""
        return f"{self.underlying} {self.expiration.strftime('%b %d')} ${self.strike:.0f} {self.option_type.upper()}"

    @property
    def short_name(self) -> str:
        """Compact format: NVDA 3/15 500C"""
        opt_char = "C" if self.is_call else "P"
        return f"{self.underlying} {self.expiration.month}/{self.expiration.day} {self.strike:.0f}{opt_char}"


def parse_option_symbol(symbol: str) -> ParsedOptionSymbol | None:
    """
    Parse OCC option symbol with support for variations.

    Examples:
    - "NVDA  240315C00500000" -> NVDA Mar 15 2024 $500 Call
    - "AAPL  240419P00150000" -> AAPL Apr 19 2024 $150 Put
    - "NVDA1 240315C00500000" -> Adjusted option (post-split)
    - "NVDA7 240315C00500000" -> Mini option (10 shares)

    Returns:
        ParsedOptionSymbol if valid option, None otherwise
    """
    if not symbol or len(symbol) < 15:
        return None

    # Clean and normalize
    symbol = symbol.strip()

    # Pattern: underlying (1-6 chars, may have digit suffix) + YYMMDD + C/P + 8-digit strike
    # Handles: NVDA, NVDA1 (adjusted), NVDA7 (mini), with or without space padding
    pattern = r'^([A-Z]+)(\d)?\s*(\d{6})([CP])(\d{8})$'
    match = re.match(pattern, symbol)

    if not match:
        return None

    underlying = match.group(1)
    suffix = match.group(2)  # None, "1" (adjusted), "7" (mini)
    exp_str = match.group(3)
    opt_type = match.group(4)
    strike_raw = match.group(5)

    # Detect special types
    is_adjusted = suffix == "1"
    is_mini = suffix == "7"
    multiplier = 10 if is_mini else 100

    # Parse expiration (YYMMDD)
    year = 2000 + int(exp_str[:2])
    month = int(exp_str[2:4])
    day = int(exp_str[4:6])

    try:
        expiration = date(year, month, day)
    except ValueError:
        return None  # Invalid date

    # Parse strike (last 3 digits are decimals: 00500000 = 500.000)
    strike = Decimal(strike_raw) / 1000

    return ParsedOptionSymbol(
        underlying=underlying,
        expiration=expiration,
        option_type="call" if opt_type == "C" else "put",
        strike=strike,
        raw_symbol=symbol,
        multiplier=multiplier,
        is_adjusted=is_adjusted,
        is_mini=is_mini,
    )


def is_option_symbol(symbol: str) -> bool:
    """Check if symbol appears to be an option."""
    return parse_option_symbol(symbol) is not None


def format_option_symbol(
    underlying: str,
    expiration: date,
    option_type: str,
    strike: float,
) -> str:
    """Build OCC symbol from components."""
    opt_char = "C" if option_type.lower() in ("call", "c") else "P"
    exp_str = expiration.strftime("%y%m%d")
    strike_int = int(strike * 1000)
    return f"{underlying:<6}{exp_str}{opt_char}{strike_int:08d}"


def calculate_options_pnl(
    entry_price: float,
    exit_price: float,
    quantity: int,
    multiplier: int = 100,
    is_credit: bool = False,
) -> tuple[float, float]:
    """
    Calculate P&L for options position.

    Args:
        entry_price: Premium paid/received per contract
        exit_price: Premium at close per contract
        quantity: Number of contracts (always positive)
        multiplier: Contract multiplier (usually 100)
        is_credit: True if sold to open (received premium)

    Returns:
        (pnl_dollars, pnl_pct)

    Examples:
        Bought call at $5, sold at $8:
            calculate_options_pnl(5, 8, 1, 100, False) -> (300, 60.0)

        Sold put at $3, bought back at $1:
            calculate_options_pnl(3, 1, 1, 100, True) -> (200, 66.7)
    """
    if is_credit:
        # Sold to open: profit when price goes down
        pnl_dollars = (entry_price - exit_price) * quantity * multiplier
    else:
        # Bought to open: profit when price goes up
        pnl_dollars = (exit_price - entry_price) * quantity * multiplier

    # Percentage based on premium paid/received
    if entry_price > 0:
        pnl_pct = (pnl_dollars / (entry_price * quantity * multiplier)) * 100
    else:
        pnl_pct = 0.0

    return pnl_dollars, pnl_pct


def calculate_max_loss(
    entry_price: float,
    quantity: int,
    multiplier: int,
    option_type: str,
    strike: float,
    is_credit: bool,
) -> float:
    """
    Calculate maximum possible loss for options position.

    For long options: max loss = premium paid
    For short calls: max loss = unlimited (return -1)
    For short puts: max loss = strike * multiplier - premium received

    Returns:
        Max loss in dollars, or -1 for unlimited risk
    """
    premium_value = entry_price * quantity * multiplier

    if not is_credit:
        # Long option: max loss is premium paid
        return premium_value

    if option_type == "call":
        # Short call: unlimited risk
        return -1  # Indicates unlimited

    # Short put: max loss if stock goes to $0
    return (strike * quantity * multiplier) - premium_value


def is_itm(option_type: str, strike: float, stock_price: float) -> bool:
    """Check if option is in-the-money."""
    if option_type == "call":
        return stock_price > strike
    else:  # put
        return stock_price < strike


def is_otm(option_type: str, strike: float, stock_price: float) -> bool:
    """Check if option is out-of-the-money."""
    return not is_itm(option_type, strike, stock_price)


def calculate_intrinsic_value(
    option_type: str,
    strike: float,
    stock_price: float,
    multiplier: int = 100,
) -> float:
    """
    Calculate intrinsic value per contract.

    For calls: max(0, stock_price - strike) * multiplier
    For puts: max(0, strike - stock_price) * multiplier
    """
    if option_type == "call":
        intrinsic = max(0.0, stock_price - strike)
    else:
        intrinsic = max(0.0, strike - stock_price)

    return intrinsic * multiplier
