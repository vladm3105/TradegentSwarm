"""
Trading calendar utilities for NYSE market hours and holidays.

Supports multiple years with automatic detection.
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# NYSE holidays by year (update as needed)
NYSE_HOLIDAYS = {
    2025: {
        date(2025, 1, 1),   # New Year's Day
        date(2025, 1, 20),  # MLK Day
        date(2025, 2, 17),  # Presidents Day
        date(2025, 4, 18),  # Good Friday
        date(2025, 5, 26),  # Memorial Day
        date(2025, 7, 4),   # Independence Day
        date(2025, 9, 1),   # Labor Day
        date(2025, 11, 27), # Thanksgiving
        date(2025, 12, 25), # Christmas
    },
    2026: {
        date(2026, 1, 1),   # New Year's Day
        date(2026, 1, 19),  # MLK Day
        date(2026, 2, 16),  # Presidents Day
        date(2026, 4, 3),   # Good Friday
        date(2026, 5, 25),  # Memorial Day
        date(2026, 7, 3),   # Independence Day (observed)
        date(2026, 9, 7),   # Labor Day
        date(2026, 11, 26), # Thanksgiving
        date(2026, 12, 25), # Christmas
    },
    2027: {
        date(2027, 1, 1),   # New Year's Day
        date(2027, 1, 18),  # MLK Day
        date(2027, 2, 15),  # Presidents Day
        date(2027, 3, 26),  # Good Friday
        date(2027, 5, 31),  # Memorial Day
        date(2027, 7, 5),   # Independence Day (observed)
        date(2027, 9, 6),   # Labor Day
        date(2027, 11, 25), # Thanksgiving
        date(2027, 12, 24), # Christmas (observed)
    },
}

# Early close days (1:00 PM ET) by year
NYSE_EARLY_CLOSE = {
    2025: {date(2025, 11, 28), date(2025, 12, 24)},
    2026: {date(2026, 11, 27), date(2026, 12, 24)},
    2027: {date(2027, 11, 26), date(2027, 12, 23)},
}


def _get_holidays_for_year(year: int) -> set[date]:
    """Get holidays for a given year, with fallback."""
    if year in NYSE_HOLIDAYS:
        return NYSE_HOLIDAYS[year]
    # Fallback: return empty set and log warning
    import logging
    logging.getLogger("tradegent.trading-calendar").warning(
        f"NYSE holidays not defined for {year}, assuming no holidays"
    )
    return set()


def _get_early_close_for_year(year: int) -> set[date]:
    """Get early close days for a given year."""
    return NYSE_EARLY_CLOSE.get(year, set())


def is_trading_day(d: date | None = None) -> bool:
    """Check if given date is a trading day (weekday, not holiday)."""
    if d is None:
        d = datetime.now(ET).date()

    # Weekend check
    if d.weekday() >= 5:
        return False

    # Holiday check
    if d in _get_holidays_for_year(d.year):
        return False

    return True


def is_market_hours(dt: datetime | None = None) -> bool:
    """Check if given datetime is during regular market hours (9:30 AM - 4:00 PM ET)."""
    if dt is None:
        dt = datetime.now(ET)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=ET)
    else:
        dt = dt.astimezone(ET)

    if not is_trading_day(dt.date()):
        return False

    market_open = time(9, 30)
    market_close = time(16, 0)

    # Check for early close
    if dt.date() in _get_early_close_for_year(dt.year):
        market_close = time(13, 0)

    current_time = dt.time()
    return market_open <= current_time <= market_close


def is_extended_hours(dt: datetime | None = None) -> bool:
    """Check if given datetime is during extended hours (4:00 AM - 8:00 PM ET)."""
    if dt is None:
        dt = datetime.now(ET)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=ET)
    else:
        dt = dt.astimezone(ET)

    if not is_trading_day(dt.date()):
        return False

    extended_open = time(4, 0)
    extended_close = time(20, 0)

    current_time = dt.time()
    return extended_open <= current_time <= extended_close


def get_market_status() -> dict:
    """Get current market status."""
    now = datetime.now(ET)

    return {
        "timestamp": now.isoformat(),
        "is_trading_day": is_trading_day(now.date()),
        "is_market_hours": is_market_hours(now),
        "is_extended_hours": is_extended_hours(now),
        "day_of_week": now.strftime("%A"),
        "year": now.year,
    }
