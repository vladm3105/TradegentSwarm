"""Tradegent timezone configuration helpers.

Centralizes timezone selection so pipeline code and DB session settings can use
the same value from environment.
"""

from __future__ import annotations

import os
import time as time_module
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TRADEGENT_TIMEZONE = "America/New_York"


def get_tradegent_timezone_name() -> str:
    """Return configured Tradegent timezone name."""
    tz_name = (os.getenv("TRADEGENT_TIMEZONE") or "").strip()
    return tz_name or DEFAULT_TRADEGENT_TIMEZONE


def get_db_timezone_name() -> str:
    """Return configured PostgreSQL session timezone name."""
    db_tz = (os.getenv("PG_TIMEZONE") or "").strip()
    return db_tz or get_tradegent_timezone_name()


def get_tradegent_zoneinfo() -> ZoneInfo:
    """Return configured timezone object with safe fallback."""
    tz_name = get_tradegent_timezone_name()
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TRADEGENT_TIMEZONE)


def now_tradegent() -> datetime:
    """Return timezone-aware now in configured Tradegent timezone."""
    return datetime.now(get_tradegent_zoneinfo())


def apply_process_timezone_from_env() -> None:
    """Apply configured timezone to process-level TZ for naive datetime consumers."""
    tz_name = get_tradegent_timezone_name()
    os.environ["TZ"] = tz_name
    if hasattr(time_module, "tzset"):
        try:
            time_module.tzset()
        except OSError:
            # Keep runtime functional if host tz database does not expose TZ value.
            pass
