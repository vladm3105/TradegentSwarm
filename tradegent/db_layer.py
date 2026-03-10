"""
Nexus Light - Database Layer
Async PostgreSQL access for stocks, scanners, schedules, and run history.

Uses psycopg3 (async) for connection pooling and typed queries.
Falls back to psycopg2 sync if async not available.
"""

import json
import logging
import os
import time as time_module
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row
from psycopg import errors as pg_errors

# Load .env file for credentials
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

log = logging.getLogger("nexus-light.db")

ET = ZoneInfo("America/New_York")

# ─── Configuration ───────────────────────────────────────────────────────────


def get_dsn() -> str:
    """Build PostgreSQL DSN from environment."""
    return (
        f"host={os.getenv('PG_HOST', 'localhost')} "
        f"port={os.getenv('PG_PORT', '5432')} "
        f"dbname={os.getenv('PG_DB', 'tradegent')} "
        f"user={os.getenv('PG_USER', 'tradegent')} "
        f"password={os.getenv('PG_PASS', '')}"
    )


# ─── Data Models ─────────────────────────────────────────────────────────────


@dataclass
class Stock:
    id: int
    ticker: str
    name: str | None
    sector: str | None
    is_enabled: bool
    state: str  # analysis, paper, live
    default_analysis_type: str
    priority: int
    next_earnings_date: date | None
    earnings_confirmed: bool
    beat_history: str | None
    has_open_position: bool
    position_state: str | None
    max_position_pct: float
    comments: str | None
    tags: list[str]

    @property
    def can_trade(self) -> bool:
        return self.state in ("paper", "live") and self.is_enabled

    @property
    def days_to_earnings(self) -> int | None:
        if self.next_earnings_date:
            return (self.next_earnings_date - date.today()).days
        return None


@dataclass
class IBScanner:
    id: int
    scanner_code: str
    display_name: str
    description: str | None
    is_enabled: bool
    instrument: str
    location: str
    num_results: int
    filters: dict
    auto_add_to_watchlist: bool
    auto_analyze: bool
    analysis_type: str
    max_candidates: int
    comments: str | None


@dataclass
class Schedule:
    id: int
    name: str
    description: str | None
    is_enabled: bool
    task_type: str
    target_ticker: str | None
    target_scanner_id: int | None
    target_tags: list[str] | None
    analysis_type: str
    auto_execute: bool
    custom_prompt: str | None
    frequency: str
    time_of_day: time | None
    day_of_week: str | None
    interval_minutes: int | None
    days_before_earnings: int | None
    days_after_earnings: int | None
    market_hours_only: bool
    trading_days_only: bool
    max_runs_per_day: int
    timeout_seconds: int
    priority: int
    last_run_at: datetime | None
    last_run_status: str | None
    next_run_at: datetime | None
    run_count: int
    fail_count: int
    consecutive_fails: int
    max_consecutive_fails: int
    comments: str | None


# ─── Database Connection ─────────────────────────────────────────────────────


class NexusDB:
    """Synchronous database access layer for the Nexus Light platform."""

    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or get_dsn()
        self._conn: psycopg.Connection | None = None

    def connect(self) -> "NexusDB":
        """Establish database connection."""
        self._conn = psycopg.connect(self.dsn, row_factory=dict_row)
        log.info("Database connected")
        return self

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *args):
        self.close()

    @property
    def conn(self) -> psycopg.Connection:
        if not self._conn:
            self.connect()
        return self._conn

    # ─── Stocks ──────────────────────────────────────────────────────────

    def get_enabled_stocks(
        self, state: str | None = None, tags: list[str] | None = None
    ) -> list[Stock]:
        """Get all enabled stocks, optionally filtered by state or tags."""
        query = "SELECT * FROM nexus.stocks WHERE is_enabled = true"
        params: list[Any] = []

        if state:
            query += " AND state = %s"
            params.append(state)

        if tags:
            query += " AND tags && %s"
            params.append(tags)

        query += " ORDER BY priority DESC, ticker ASC"

        with self.conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        return [self._row_to_stock(r) for r in rows]

    def get_stock(self, ticker: str) -> Stock | None:
        """Get a single stock by ticker."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.stocks WHERE ticker = %s", [ticker.upper()])
            row = cur.fetchone()
        return self._row_to_stock(row) if row else None

    def get_stocks_near_earnings(self, days: int = 14) -> list[Stock]:
        """Get stocks with earnings within N days."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM nexus.stocks 
                WHERE is_enabled = true 
                  AND next_earnings_date IS NOT NULL
                  AND next_earnings_date >= CURRENT_DATE
                  AND next_earnings_date <= CURRENT_DATE + %s * INTERVAL '1 day'
                ORDER BY next_earnings_date ASC
            """,
                [days],
            )
            rows = cur.fetchall()
        return [self._row_to_stock(r) for r in rows]

    # Valid column names for stocks table (whitelist)
    STOCK_COLUMNS = {
        "name",
        "sector",
        "is_enabled",
        "state",
        "default_analysis_type",
        "priority",
        "next_earnings_date",
        "earnings_confirmed",
        "beat_history",
        "has_open_position",
        "position_state",
        "max_position_pct",
        "comments",
        "tags",
    }

    def upsert_stock(self, ticker: str, **kwargs) -> Stock | None:
        """Insert or update a stock. Only provided fields are updated."""
        ticker = ticker.upper()

        # Validate column names to prevent SQL injection
        invalid_keys = set(kwargs.keys()) - self.STOCK_COLUMNS
        if invalid_keys:
            raise ValueError(f"Invalid stock column(s): {invalid_keys}")

        # Check if exists
        existing = self.get_stock(ticker)
        if existing:
            # Build SET clause from provided kwargs
            set_parts = []
            params = []
            for key, val in kwargs.items():
                set_parts.append(f"{key} = %s")
                params.append(val)
            if set_parts:
                params.append(ticker)
                with self.conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE nexus.stocks SET {', '.join(set_parts)} WHERE ticker = %s", params
                    )
                self.conn.commit()
        else:
            # Insert with defaults
            cols = ["ticker"] + list(kwargs.keys())
            vals = [ticker] + list(kwargs.values())
            placeholders = ", ".join(["%s"] * len(vals))
            col_str = ", ".join(cols)
            with self.conn.cursor() as cur:
                cur.execute(f"INSERT INTO nexus.stocks ({col_str}) VALUES ({placeholders})", vals)
            self.conn.commit()

        return self.get_stock(ticker)

    def update_stock_position(self, ticker: str, has_open_position: bool, position_state: str):
        """Update stock position tracking fields."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nexus.stocks 
                SET has_open_position = %s, position_state = %s
                WHERE ticker = %s
            """,
                [has_open_position, position_state, ticker.upper()],
            )
        self.conn.commit()

    def _row_to_stock(self, row: dict) -> Stock:
        return Stock(
            id=row["id"],
            ticker=row["ticker"],
            name=row.get("name"),
            sector=row.get("sector"),
            is_enabled=row["is_enabled"],
            state=row["state"],
            default_analysis_type=row["default_analysis_type"],
            priority=row["priority"],
            next_earnings_date=row.get("next_earnings_date"),
            earnings_confirmed=row.get("earnings_confirmed", False),
            beat_history=row.get("beat_history"),
            has_open_position=row.get("has_open_position", False),
            position_state=row.get("position_state"),
            max_position_pct=float(row.get("max_position_pct", 6.0)),
            comments=row.get("comments"),
            tags=row.get("tags") or [],
        )

    # ─── IB Scanners ────────────────────────────────────────────────────

    def get_enabled_scanners(self) -> list[IBScanner]:
        """Get all enabled IB scanners."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.ib_scanners WHERE is_enabled = true ORDER BY id")
            rows = cur.fetchall()
        return [self._row_to_scanner(r) for r in rows]

    def get_scanner(self, scanner_id: int) -> IBScanner | None:
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.ib_scanners WHERE id = %s", [scanner_id])
            row = cur.fetchone()
        return self._row_to_scanner(row) if row else None

    def get_scanner_by_code(self, code: str) -> IBScanner | None:
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.ib_scanners WHERE scanner_code = %s", [code])
            row = cur.fetchone()
        return self._row_to_scanner(row) if row else None

    def _row_to_scanner(self, row: dict) -> IBScanner:
        filters = row.get("filters", {})
        if isinstance(filters, str):
            filters = json.loads(filters)
        return IBScanner(
            id=row["id"],
            scanner_code=row["scanner_code"],
            display_name=row["display_name"],
            description=row.get("description"),
            is_enabled=row["is_enabled"],
            instrument=row.get("instrument", "STK"),
            location=row.get("location", "STK.US.MAJOR"),
            num_results=row.get("num_results", 20),
            filters=filters,
            auto_add_to_watchlist=row.get("auto_add_to_watchlist", False),
            auto_analyze=row.get("auto_analyze", False),
            analysis_type=row.get("analysis_type", "stock"),
            max_candidates=row.get("max_candidates", 5),
            comments=row.get("comments"),
        )

    # ─── Schedules ──────────────────────────────────────────────────────

    def get_due_schedules(self) -> list[Schedule]:
        """Get schedules that are due for execution (using the view)."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.v_due_schedules")
            rows = cur.fetchall()
        return [self._row_to_schedule(r) for r in rows]

    def get_enabled_schedules(self) -> list[Schedule]:
        """Get all enabled schedules."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM nexus.schedules WHERE is_enabled = true ORDER BY priority DESC"
            )
            rows = cur.fetchall()
        return [self._row_to_schedule(r) for r in rows]

    def get_schedule(self, schedule_id: int) -> Schedule | None:
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.schedules WHERE id = %s", [schedule_id])
            row = cur.fetchone()
        return self._row_to_schedule(row) if row else None

    def get_earnings_triggered_schedules(self, ticker: str, days_until: int) -> list[Schedule]:
        """Get pre/post-earnings schedules that match this ticker's timing."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM nexus.schedules 
                WHERE is_enabled = true
                  AND frequency IN ('pre_earnings', 'post_earnings')
                  AND (
                    (frequency = 'pre_earnings' AND days_before_earnings = %s)
                    OR
                    (frequency = 'post_earnings' AND days_after_earnings = %s)
                  )
            """,
                [days_until, abs(days_until)],
            )  # abs() for post-earnings: days_until is negative when past
            rows = cur.fetchall()
        return [self._row_to_schedule(r) for r in rows]

    def mark_schedule_started(self, schedule_id: int) -> int:
        """Mark a schedule as running and create a run_history entry. Returns run_id."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nexus.schedules 
                SET last_run_at = now(), last_run_status = 'running'
                WHERE id = %s
            """,
                [schedule_id],
            )

            # Get schedule details for run_history
            cur.execute("SELECT * FROM nexus.schedules WHERE id = %s", [schedule_id])
            sched = cur.fetchone()

            cur.execute(
                """
                INSERT INTO nexus.run_history (schedule_id, task_type, ticker, analysis_type, status, stage)
                VALUES (%s, %s, %s, %s, 'running', 'analysis')
                RETURNING id
            """,
                [
                    schedule_id,
                    sched["task_type"],
                    sched.get("target_ticker"),
                    sched.get("analysis_type"),
                ],
            )
            run_id = cur.fetchone()["id"]

        self.conn.commit()
        return run_id

    def mark_schedule_completed(
        self,
        schedule_id: int,
        run_id: int,
        status: str = "completed",
        error: str | None = None,
        **result_fields,
    ):
        """Update schedule and run_history after completion."""
        now = datetime.now(ET)

        with self.conn.cursor() as cur:
            # Update schedule
            if status == "completed":
                cur.execute(
                    """
                    UPDATE nexus.schedules 
                    SET last_run_status = %s, run_count = run_count + 1, 
                        consecutive_fails = 0
                    WHERE id = %s
                """,
                    [status, schedule_id],
                )
            elif status == "failed":
                cur.execute(
                    """
                    UPDATE nexus.schedules 
                    SET last_run_status = %s, run_count = run_count + 1,
                        fail_count = fail_count + 1, 
                        consecutive_fails = consecutive_fails + 1
                    WHERE id = %s
                """,
                    [status, schedule_id],
                )

                # Circuit breaker check
                cur.execute(
                    """
                    UPDATE nexus.schedules 
                    SET is_enabled = false 
                    WHERE id = %s AND consecutive_fails >= max_consecutive_fails
                """,
                    [schedule_id],
                )
            else:
                cur.execute(
                    """
                    UPDATE nexus.schedules SET last_run_status = %s WHERE id = %s
                """,
                    [status, schedule_id],
                )

            # Update run_history
            update_parts = ["status = %s", "completed_at = now()"]
            params: list[Any] = [status]

            if error:
                update_parts.append("error_message = %s")
                params.append(error)

            for key in [
                "gate_passed",
                "recommendation",
                "confidence",
                "expected_value",
                "order_placed",
                "order_id",
                "analysis_file",
                "trade_file",
                "raw_output",
            ]:
                if key in result_fields:
                    update_parts.append(f"{key} = %s")
                    params.append(result_fields[key])

            if "order_details" in result_fields:
                update_parts.append("order_details = %s")
                params.append(json.dumps(result_fields["order_details"]))

            params.append(run_id)
            cur.execute(
                f"UPDATE nexus.run_history SET {', '.join(update_parts)} WHERE id = %s", params
            )

            # Calculate and store duration
            cur.execute(
                """
                UPDATE nexus.run_history 
                SET duration_seconds = EXTRACT(EPOCH FROM (completed_at - started_at))
                WHERE id = %s
            """,
                [run_id],
            )

        self.conn.commit()

    # ─── Scanner Run Logging ────────────────────────────────────────────────────

    def start_scanner_run(self, scanner_code: str) -> int:
        """Start a scanner run and create a run_history entry. Returns run_id."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nexus.run_history
                (task_type, ticker, status, stage)
                VALUES ('run_scanner', %s, 'running', 'scan')
                RETURNING id
            """,
                [scanner_code],
            )
            run_id = cur.fetchone()["id"]
        self.conn.commit()
        return run_id

    def complete_scanner_run(
        self,
        run_id: int,
        status: str = "completed",
        candidates: list[dict] | None = None,
        scanner_code: str | None = None,
        scan_time: str | None = None,
        error: str | None = None,
    ):
        """Complete a scanner run with full results.

        Args:
            run_id: The run_history ID
            status: 'completed' or 'failed'
            candidates: List of candidate dicts with ticker, score, price, notes
            scanner_code: Scanner code (e.g., HIGH_OPT_IMP_VOLAT)
            scan_time: ISO timestamp of scan
            error: Error message if failed
        """
        candidates = candidates or []
        raw_output = json.dumps({
            "scanner": scanner_code,
            "scan_time": scan_time,
            "candidates_found": len(candidates),
            "candidates": candidates,
        })
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nexus.run_history
                SET status = %s,
                    completed_at = now(),
                    duration_seconds = EXTRACT(EPOCH FROM (now() - started_at)),
                    raw_output = %s,
                    error_message = %s
                WHERE id = %s
            """,
                [status, raw_output, error, run_id],
            )
        self.conn.commit()

    def calculate_next_run(self, schedule: Schedule) -> datetime | None:
        """Calculate the next run time for a schedule."""
        now = datetime.now(ET)

        if schedule.frequency == "once":
            return None  # Already ran

        elif schedule.frequency == "daily":
            if schedule.time_of_day:
                next_dt = now.replace(
                    hour=schedule.time_of_day.hour,
                    minute=schedule.time_of_day.minute,
                    second=0,
                    microsecond=0,
                )
                if next_dt <= now:
                    next_dt += timedelta(days=1)
                # Skip weekends if trading_days_only
                if schedule.trading_days_only:
                    while next_dt.weekday() >= 5:
                        next_dt += timedelta(days=1)
                return next_dt

        elif schedule.frequency == "weekly":
            day_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
            target_day = day_map.get(schedule.day_of_week or "mon", 0)
            days_ahead = target_day - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_dt = now + timedelta(days=days_ahead)
            if schedule.time_of_day:
                next_dt = next_dt.replace(
                    hour=schedule.time_of_day.hour,
                    minute=schedule.time_of_day.minute,
                    second=0,
                    microsecond=0,
                )
            return next_dt

        elif schedule.frequency == "interval":
            if schedule.interval_minutes:
                return now + timedelta(minutes=schedule.interval_minutes)

        elif schedule.frequency in ("pre_earnings", "post_earnings"):
            # These are triggered by earnings dates, not time-based
            # Return far future; the earnings checker will trigger them
            return None

        return None

    def update_next_run(self, schedule_id: int, next_run: datetime | None):
        """Set the next_run_at for a schedule."""
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE nexus.schedules SET next_run_at = %s WHERE id = %s", [next_run, schedule_id]
            )
        self.conn.commit()

    def save_analysis_result(
        self, run_id: int | None, ticker: str, analysis_type: str, parsed: dict
    ):
        """Save structured analysis result from parsed JSON."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nexus.analysis_results 
                (run_id, ticker, analysis_type, gate_passed, recommendation, confidence,
                 expected_value_pct, entry_price, stop_loss, target_price, position_size_pct,
                 structure, expiry_date, strikes, rationale)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
                [
                    run_id,
                    ticker,
                    analysis_type,
                    parsed.get("gate_passed"),
                    parsed.get("recommendation"),
                    parsed.get("confidence"),
                    parsed.get("expected_value_pct"),
                    parsed.get("entry_price"),
                    parsed.get("stop_loss"),
                    parsed.get("target"),
                    parsed.get("position_size_pct"),
                    parsed.get("structure"),
                    parsed.get("expiry"),
                    parsed.get("strikes"),
                    parsed.get("rationale_summary"),
                ],
            )
        self.conn.commit()

    def get_today_run_count(self, task_type: str | None = None) -> int:
        """Count runs executed today."""
        with self.conn.cursor() as cur:
            if task_type:
                cur.execute(
                    """
                    SELECT COUNT(*) as cnt FROM nexus.run_history 
                    WHERE started_at >= CURRENT_DATE AND task_type = %s
                """,
                    [task_type],
                )
            else:
                cur.execute("""
                    SELECT COUNT(*) as cnt FROM nexus.run_history 
                    WHERE started_at >= CURRENT_DATE
                """)
            return cur.fetchone()["cnt"]

    def _row_to_schedule(self, row: dict) -> Schedule:
        return Schedule(
            id=row["id"],
            name=row["name"],
            description=row.get("description"),
            is_enabled=row["is_enabled"],
            task_type=row["task_type"],
            target_ticker=row.get("target_ticker"),
            target_scanner_id=row.get("target_scanner_id"),
            target_tags=row.get("target_tags"),
            analysis_type=row.get("analysis_type", "stock"),
            auto_execute=row.get("auto_execute", False),
            custom_prompt=row.get("custom_prompt"),
            frequency=row["frequency"],
            time_of_day=row.get("time_of_day"),
            day_of_week=row.get("day_of_week"),
            interval_minutes=row.get("interval_minutes"),
            days_before_earnings=row.get("days_before_earnings"),
            days_after_earnings=row.get("days_after_earnings"),
            market_hours_only=row.get("market_hours_only", True),
            trading_days_only=row.get("trading_days_only", True),
            max_runs_per_day=row.get("max_runs_per_day", 1),
            timeout_seconds=row.get("timeout_seconds", 600),
            priority=row.get("priority", 5),
            last_run_at=row.get("last_run_at"),
            last_run_status=row.get("last_run_status"),
            next_run_at=row.get("next_run_at"),
            run_count=row.get("run_count", 0),
            fail_count=row.get("fail_count", 0),
            consecutive_fails=row.get("consecutive_fails", 0),
            max_consecutive_fails=row.get("max_consecutive_fails", 3),
            comments=row.get("comments"),
        )

    # ─── Settings ──────────────────────────────────────────────────────

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value fresh from database.

        Each call queries the database directly, allowing runtime configuration
        changes without restart. Used by parallel execution for dynamic tuning.

        Args:
            key: Setting key name
            default: Default value if not found or on error

        Returns:
            Setting value or default
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT value FROM nexus.settings WHERE key = %s", [key])
                row = cur.fetchone()
            return row["value"] if row else default
        except Exception:
            return default

    def get_settings_by_category(self, category: str) -> dict[str, Any]:
        """Get all settings in a category as a dict."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT key, value FROM nexus.settings WHERE category = %s", [category])
            rows = cur.fetchall()
        return {r["key"]: r["value"] for r in rows}

    def get_all_settings(self) -> dict[str, Any]:
        """Get all settings as a flat dict."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT key, value FROM nexus.settings")
            rows = cur.fetchall()
        return {r["key"]: r["value"] for r in rows}

    def set_setting(
        self, key: str, value: Any, description: str | None = None, category: str | None = None
    ):
        """Create or update a setting."""
        with self.conn.cursor() as cur:
            if description or category:
                parts = ["value = %s"]
                params: list[Any] = [json.dumps(value)]
                if description:
                    parts.append("description = %s")
                    params.append(description)
                if category:
                    parts.append("category = %s")
                    params.append(category)
                params.extend([key, json.dumps(value), category or "general", description or ""])
                cur.execute(
                    f"""
                    INSERT INTO nexus.settings (key, value, category, description)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (key) DO UPDATE SET {", ".join(parts)}
                """,
                    params,
                )
            else:
                cur.execute(
                    """
                    INSERT INTO nexus.settings (key, value) VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE SET value = %s
                """,
                    [key, json.dumps(value), json.dumps(value)],
                )
        self.conn.commit()

    def claim_analysis_slot(self) -> bool:
        """
        Atomically check if analysis slot is available against daily limit.
        Uses PostgreSQL advisory lock for thread safety across parallel workers.

        The advisory lock (ID 314159265) is held for the duration of the transaction,
        ensuring only one thread can check-and-proceed at a time.

        Returns:
            True if slot available (can proceed), False if daily limit reached.
        """
        # Get max_daily_analyses from settings (default 15)
        max_analyses = 15
        with self.conn.cursor() as cur:
            cur.execute("SELECT value FROM nexus.settings WHERE key = 'max_daily_analyses'")
            row = cur.fetchone()
            if row:
                try:
                    max_analyses = int(row["value"])
                except (ValueError, TypeError):
                    pass

            # Acquire advisory lock (released on commit/rollback)
            # Lock ID 314159265 is arbitrary but unique for this purpose
            cur.execute("SELECT pg_advisory_xact_lock(314159265)")

            # Check current count with lock held
            cur.execute("""
                SELECT COUNT(*) as cnt
                FROM nexus.analysis_results
                WHERE created_at >= CURRENT_DATE
            """)
            row = cur.fetchone()
            current_count = row["cnt"] if row else 0

        # Commit releases the advisory lock
        self.conn.commit()

        can_run = current_count < max_analyses
        if not can_run:
            log.debug(f"Daily limit check: {current_count}/{max_analyses} - limit reached")
        return can_run

    # ─── Service Status ──────────────────────────────────────────────────

    def heartbeat(
        self,
        state: str = "running",
        current_task: str | None = None,
        tick_duration_ms: int | None = None,
    ):
        """Update the service heartbeat (singleton row)."""
        import socket

        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nexus.service_status SET
                    last_heartbeat = now(),
                    state = %s,
                    current_task = %s,
                    last_tick_duration_ms = %s,
                    pid = %s,
                    hostname = %s,
                    ticks_total = ticks_total + 1,
                    today_date = CASE WHEN today_date < CURRENT_DATE
                                      THEN CURRENT_DATE ELSE today_date END,
                    today_analyses = CASE WHEN today_date < CURRENT_DATE
                                         THEN 0 ELSE today_analyses END,
                    today_executions = CASE WHEN today_date < CURRENT_DATE
                                           THEN 0 ELSE today_executions END,
                    today_errors = CASE WHEN today_date < CURRENT_DATE
                                       THEN 0 ELSE today_errors END
                WHERE id = 1
            """,
                [state, current_task, tick_duration_ms, os.getpid(), socket.gethostname()],
            )
        self.conn.commit()

    def increment_service_counter(self, counter: str):
        """Increment a service counter: analyses_total, executions_total, errors_total."""
        valid = {
            "analyses_total",
            "executions_total",
            "errors_total",
            "today_analyses",
            "today_executions",
            "today_errors",
        }
        if counter not in valid:
            return
        with self.conn.cursor() as cur:
            cur.execute(f"UPDATE nexus.service_status SET {counter} = {counter} + 1 WHERE id = 1")
        self.conn.commit()

    def get_service_status(self) -> dict | None:
        """Get current service status."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.service_status WHERE id = 1")
            return cur.fetchone()

    def mark_service_started(self):
        """Mark service as starting."""
        import socket

        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nexus.service_status SET
                    started_at = now(), last_heartbeat = now(),
                    state = 'starting', pid = %s, hostname = %s,
                    ticks_total = 0, analyses_total = 0, executions_total = 0, errors_total = 0,
                    today_analyses = 0, today_executions = 0, today_errors = 0,
                    today_date = CURRENT_DATE
                WHERE id = 1
            """,
                [os.getpid(), socket.gethostname()],
            )
        self.conn.commit()

    def mark_service_stopped(self, state: str = "stopped"):
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE nexus.service_status SET state = %s, current_task = NULL WHERE id = 1",
                [state],
            )
        self.conn.commit()

    # ─── Connection Resilience ───────────────────────────────────────────

    def ensure_connection(self, max_retries: int = 3, base_delay: float = 1.0):
        """Reconnect if the connection is dead. Call before each tick.

        Handles:
        - Connection lost (OperationalError)
        - Transaction aborted (InFailedSqlTransaction) - rolls back
        - Retries with exponential backoff
        """
        for attempt in range(max_retries):
            try:
                with self.conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return  # Connection is healthy
            except pg_errors.InFailedSqlTransaction:
                # Transaction aborted - rollback and continue
                log.warning("Transaction aborted — rolling back")
                try:
                    self._conn.rollback()
                except Exception:
                    pass
                return  # After rollback, connection should be usable
            except (pg_errors.OperationalError, pg_errors.AdminShutdown, Exception) as e:
                log.warning(f"DB connection issue (attempt {attempt + 1}/{max_retries}): {e}")
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    log.info(f"Retrying connection in {delay:.1f}s...")
                    time_module.sleep(delay)
                    try:
                        self.connect()
                    except Exception as conn_err:
                        log.error(f"Reconnection failed: {conn_err}")
                else:
                    log.error("Max reconnection attempts reached")
                    raise

    # ─── Utility ─────────────────────────────────────────────────────────

    def init_schema(self):
        """Run the init.sql schema file."""
        schema_file = os.path.join(os.path.dirname(__file__), "db", "init.sql")
        with open(schema_file) as f:
            sql = f.read()
        with self.conn.cursor() as cur:
            cur.execute(sql)
        self.conn.commit()
        log.info("Database schema initialized")

    def health_check(self) -> bool:
        """Verify database connectivity and schema."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as cnt FROM nexus.stocks")
                count = cur.fetchone()["cnt"]
                log.info(f"DB health OK - {count} stocks in watchlist")
                return True
        except Exception as e:
            log.error(f"DB health check failed: {e}")
            return False

    # ─── Audit Logging ─────────────────────────────────────────────────────

    def audit_log(
        self,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        result: str = "success",
        details: dict | None = None,
        actor: str = "system",
    ) -> int | None:
        """
        Log an audit event for security and compliance tracking.

        Args:
            action: The action performed (e.g., 'stock_add', 'setting_change')
            resource_type: Type of resource affected (e.g., 'stock', 'schedule')
            resource_id: Identifier of the resource (e.g., ticker, schedule name)
            result: Outcome ('success', 'failure', 'blocked', 'error')
            details: Additional context as dict (serialized to JSONB)
            actor: Who performed the action (e.g., 'system', 'orchestrator', 'cli:user')

        Returns:
            The audit log entry ID, or None on failure
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT nexus.audit_log_event(
                        %s, %s, %s, %s, %s, %s
                    ) AS id
                    """,
                    [action, resource_type, resource_id, result, json.dumps(details or {}), actor],
                )
                row = cur.fetchone()
                self.conn.commit()
                return row["id"] if row else None
        except Exception as e:
            log.warning(f"Failed to write audit log: {e}")
            return None

    def get_audit_logs(
        self,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        actor: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Retrieve audit log entries with optional filters.

        Args:
            action: Filter by action type
            resource_type: Filter by resource type
            resource_id: Filter by resource ID
            actor: Filter by actor
            since: Only entries after this timestamp
            limit: Maximum entries to return

        Returns:
            List of audit log entries as dictionaries
        """
        conditions = []
        params = []

        if action:
            conditions.append("action = %s")
            params.append(action)
        if resource_type:
            conditions.append("resource_type = %s")
            params.append(resource_type)
        if resource_id:
            conditions.append("resource_id = %s")
            params.append(resource_id)
        if actor:
            conditions.append("actor = %s")
            params.append(actor)
        if since:
            conditions.append("timestamp >= %s")
            params.append(since)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, timestamp, action, actor, resource_type, resource_id,
                       result, details
                FROM nexus.audit_log
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                params,
            )
            return [dict(row) for row in cur.fetchall()]

    # ─── Watchlist Methods ────────────────────────────────────────────────

    def get_watchlist_entry(self, ticker: str, watchlist_id: int | None = None) -> dict | None:
        """Get the active watchlist entry for ticker, optionally scoped to a named list."""
        query = "SELECT * FROM nexus.watchlist WHERE ticker = %s AND status = 'active'"
        params: list[Any] = [ticker.upper()]
        if watchlist_id is not None:
            query += " AND watchlist_id = %s"
            params.append(watchlist_id)
        query += " ORDER BY created_at DESC LIMIT 1"

        with self.conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
        return dict(row) if row else None

    def get_active_watchlist(self, watchlist_id: int | None = None) -> list[dict]:
        """Get all active watchlist entries, optionally for a named list."""
        query = "SELECT * FROM nexus.watchlist WHERE status = 'active'"
        params: list[Any] = []
        if watchlist_id is not None:
            query += " AND watchlist_id = %s"
            params.append(watchlist_id)
        query += " ORDER BY priority DESC, created_at DESC"

        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]

    def get_or_create_watchlist(
        self,
        name: str,
        source_type: str = "manual",
        source_ref: str | None = None,
        description: str | None = None,
        color: str | None = None,
        is_default: bool = False,
        is_pinned: bool = False,
    ) -> dict:
        """Get an existing named watchlist or create it if missing."""
        with self.conn.cursor() as cur:
            if source_ref:
                cur.execute(
                    "SELECT * FROM nexus.watchlists WHERE source_type = %s AND source_ref = %s LIMIT 1",
                    [source_type, source_ref],
                )
                row = cur.fetchone()
                if row:
                    return dict(row)

            cur.execute(
                "SELECT * FROM nexus.watchlists WHERE lower(name) = lower(%s) LIMIT 1",
                [name],
            )
            row = cur.fetchone()
            if row:
                return dict(row)

            try:
                cur.execute(
                    """
                    INSERT INTO nexus.watchlists (
                        name, description, source_type, source_ref, color, is_default, is_pinned
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    [
                        name,
                        description,
                        source_type,
                        source_ref,
                        color or "#3b82f6",
                        is_default,
                        is_pinned,
                    ],
                )
                row = cur.fetchone()
                self.conn.commit()
                return dict(row)
            except pg_errors.UniqueViolation:
                self.conn.rollback()

        with self.conn.cursor() as cur:
            if source_ref:
                cur.execute(
                    "SELECT * FROM nexus.watchlists WHERE source_type = %s AND source_ref = %s LIMIT 1",
                    [source_type, source_ref],
                )
            else:
                cur.execute(
                    "SELECT * FROM nexus.watchlists WHERE lower(name) = lower(%s) LIMIT 1",
                    [name],
                )
            row = cur.fetchone()
        if not row:
            raise RuntimeError(f"Failed to create watchlist: {name}")
        return dict(row)

    def add_watchlist_entry(self, entry: dict) -> int:
        """Add new watchlist entry. Returns entry ID."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.watchlist (
                    watchlist_id, ticker, entry_trigger, entry_price,
                    invalidation, invalidation_price, expires_at, priority,
                    source, source_analysis, notes
                )
                VALUES (
                    %(watchlist_id)s, %(ticker)s, %(entry_trigger)s, %(entry_price)s,
                    %(invalidation)s, %(invalidation_price)s, %(expires_at)s, %(priority)s,
                    %(source)s, %(source_analysis)s, %(notes)s
                )
                RETURNING id
            """, {
                "watchlist_id": entry.get("watchlist_id"),
                "ticker": entry.get("ticker", "").upper(),
                "entry_trigger": entry.get("entry_trigger"),
                "entry_price": entry.get("entry_price"),
                "invalidation": entry.get("invalidation"),
                "invalidation_price": entry.get("invalidation_price"),
                "expires_at": entry.get("expires_at"),
                "priority": entry.get("priority", "medium"),
                "source": entry.get("source"),
                "source_analysis": entry.get("source_analysis"),
                "notes": entry.get("notes"),
            })
            entry_id = cur.fetchone()["id"]
        self.conn.commit()
        return entry_id

    def update_watchlist_status(self, ticker: str, status: str) -> None:
        """Update watchlist entry status."""
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE nexus.watchlist SET status = %s, updated_at = now() WHERE ticker = %s AND status = 'active'",
                [status, ticker.upper()]
            )
        self.conn.commit()

    def update_watchlist_by_id(self, entry_id: int, status: str) -> None:
        """Update watchlist entry status by ID."""
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE nexus.watchlist SET status = %s, updated_at = now() WHERE id = %s",
                [status, entry_id]
            )
        self.conn.commit()

    def get_expired_watchlist(self) -> list[dict]:
        """Get watchlist entries that have expired."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM nexus.watchlist WHERE status = 'active' AND expires_at < now()"
            )
            return [dict(r) for r in cur.fetchall()]

    # ─── Trades Methods ────────────────────────────────────────────────────

    def add_trade(self, trade: dict) -> int:
        """Add new trade entry. Returns trade ID."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.trades (ticker, entry_date, entry_price, entry_size,
                    entry_type, current_size, thesis, source_analysis)
                VALUES (%(ticker)s, %(entry_date)s, %(entry_price)s, %(entry_size)s,
                    %(entry_type)s, %(entry_size)s, %(thesis)s, %(source_analysis)s)
                RETURNING id
            """, {
                "ticker": trade.get("ticker", "").upper(),
                "entry_date": trade.get("entry_date", datetime.now()),
                "entry_price": trade.get("entry_price"),
                "entry_size": trade.get("entry_size"),
                "entry_type": trade.get("entry_type", "stock"),
                "thesis": trade.get("thesis"),
                "source_analysis": trade.get("source_analysis"),
            })
            trade_id = cur.fetchone()["id"]
        self.conn.commit()
        return trade_id

    def close_trade(self, trade_id: int, exit_price: float, exit_reason: str) -> None:
        """Close a trade and calculate P&L."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.trades SET
                    status = 'closed',
                    exit_date = now(),
                    exit_price = %(exit_price)s,
                    exit_reason = %(exit_reason)s,
                    pnl_dollars = (%(exit_price)s - entry_price) * COALESCE(entry_size, 1),
                    pnl_pct = ((%(exit_price)s - entry_price) / NULLIF(entry_price, 0)) * 100,
                    updated_at = now()
                WHERE id = %(trade_id)s
            """, {"exit_price": exit_price, "exit_reason": exit_reason, "trade_id": trade_id})
        self.conn.commit()

    def get_trade(self, trade_id: int) -> dict | None:
        """Get trade by ID."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.trades WHERE id = %s", [trade_id])
            row = cur.fetchone()
        return dict(row) if row else None

    def get_trades_by_status(self, status: str = "open", limit: int = 20) -> list[dict]:
        """Get trades by status."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM nexus.trades WHERE status = %s ORDER BY created_at DESC LIMIT %s",
                [status, limit]
            )
            return [dict(r) for r in cur.fetchall()]

    def get_trades_pending_review(self) -> list[dict]:
        """Get closed trades that haven't been reviewed."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM nexus.trades WHERE status = 'closed' AND review_status = 'pending'"
            )
            return [dict(r) for r in cur.fetchall()]

    def mark_trade_reviewed(self, trade_id: int, review_path: str) -> None:
        """Mark trade as reviewed."""
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE nexus.trades SET review_status = 'completed', review_path = %s, updated_at = now() WHERE id = %s",
                [review_path, trade_id]
            )
        self.conn.commit()

    # ─── Order Tracking Methods ─────────────────────────────────────────────────

    def update_trade_order(self, trade_id: int, order_id: str, status: str,
                           partial_fills: list | None = None,
                           avg_fill_price: float | None = None) -> bool:
        """
        Update trade with IB order information.

        Args:
            trade_id: Trade ID in nexus.trades
            order_id: IB order ID
            status: Order status (Submitted, Filled, PartialFilled, Cancelled, Error)
            partial_fills: List of fill events [{time, shares, price}]
            avg_fill_price: Volume-weighted average fill price

        Returns:
            True if trade was updated, False if trade_id not found
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.trades SET
                    order_id = COALESCE(%s, order_id),
                    ib_order_status = %s,
                    partial_fills = CASE WHEN %s IS NOT NULL THEN %s::jsonb ELSE partial_fills END,
                    avg_fill_price = COALESCE(%s, avg_fill_price),
                    updated_at = now()
                WHERE id = %s
                RETURNING id
            """, [
                order_id,
                status,
                json.dumps(partial_fills) if partial_fills else None,
                json.dumps(partial_fills) if partial_fills else None,
                avg_fill_price,
                trade_id
            ])
            updated = cur.fetchone() is not None
        self.conn.commit()
        return updated

    def get_trades_with_pending_orders(self) -> list[dict]:
        """Get trades with orders that need status reconciliation."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.trades
                WHERE order_id IS NOT NULL
                  AND ib_order_status NOT IN ('Filled', 'Cancelled', 'Error')
                  AND status = 'open'
                ORDER BY created_at DESC
            """)
            return [dict(r) for r in cur.fetchall()]

    def get_open_trades_by_ticker(self, ticker: str) -> list[dict]:
        """Get all open trades for a ticker (may be multiple)."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.trades
                WHERE ticker = %s AND status = 'open'
                ORDER BY entry_date DESC
            """, [ticker.upper()])
            return [dict(r) for r in cur.fetchall()]

    def get_all_open_trades(self) -> list[dict]:
        """Get all open trades across all tickers."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.trades
                WHERE status = 'open'
                ORDER BY ticker, entry_date DESC
            """)
            return [dict(r) for r in cur.fetchall()]

    def update_trade_size(self, trade_id: int, new_size: float) -> bool:
        """Update current_size for a trade (partial close)."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.trades
                SET current_size = %s, updated_at = now()
                WHERE id = %s
                RETURNING id
            """, [new_size, trade_id])
            updated = cur.fetchone() is not None
        self.conn.commit()
        return updated

    def close_trade_with_direction(self, trade_id: int, exit_price: float,
                                    exit_reason: str, direction: str = "long") -> bool:
        """
        Close a trade with direction-aware P&L calculation.

        For long positions: P&L = (exit - entry) * size
        For short positions: P&L = (entry - exit) * size
        """
        with self.conn.cursor() as cur:
            if direction == "short":
                # Short: profit when price goes down
                cur.execute("""
                    UPDATE nexus.trades SET
                        status = 'closed',
                        exit_date = now(),
                        exit_price = %(exit_price)s,
                        exit_reason = %(exit_reason)s,
                        pnl_dollars = (entry_price - %(exit_price)s) * COALESCE(current_size, entry_size, 1),
                        pnl_pct = ((entry_price - %(exit_price)s) / NULLIF(entry_price, 0)) * 100,
                        updated_at = now()
                    WHERE id = %(trade_id)s
                    RETURNING id
                """, {"exit_price": exit_price, "exit_reason": exit_reason, "trade_id": trade_id})
            else:
                # Long: profit when price goes up
                cur.execute("""
                    UPDATE nexus.trades SET
                        status = 'closed',
                        exit_date = now(),
                        exit_price = %(exit_price)s,
                        exit_reason = %(exit_reason)s,
                        pnl_dollars = (%(exit_price)s - entry_price) * COALESCE(current_size, entry_size, 1),
                        pnl_pct = ((%(exit_price)s - entry_price) / NULLIF(entry_price, 0)) * 100,
                        updated_at = now()
                    WHERE id = %(trade_id)s
                    RETURNING id
                """, {"exit_price": exit_price, "exit_reason": exit_reason, "trade_id": trade_id})
            updated = cur.fetchone() is not None
        self.conn.commit()
        return updated

    # ─── Watchlist Methods ──────────────────────────────────────────────────────

    def update_watchlist_status(self, entry_id: int, status: str,
                                notes: str | None = None) -> bool:
        """Update watchlist entry status."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.watchlist
                SET status = %s,
                    notes = COALESCE(%s, notes),
                    updated_at = now()
                WHERE id = %s
                RETURNING id
            """, [status, notes, entry_id])
            updated = cur.fetchone() is not None
        self.conn.commit()
        return updated

    def get_expiring_watchlist(self, hours: int = 24) -> list[dict]:
        """Get watchlist entries expiring within N hours."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.watchlist
                WHERE status = 'active'
                  AND expires_at IS NOT NULL
                  AND expires_at < now() + (%s || ' hours')::interval
                ORDER BY expires_at ASC
            """, [hours])
            return [dict(r) for r in cur.fetchall()]

    # ─── Task Queue Methods ────────────────────────────────────────────────

    def queue_analysis(self, ticker: str, analysis_type: str, priority: int = 5) -> int | None:
        """Queue an analysis task. Returns task ID or None if cooldown active."""
        cooldown_key = f"analysis:{ticker.upper()}:{analysis_type}"
        with self.conn.cursor() as cur:
            # Check cooldown (4 hour default)
            cur.execute("""
                SELECT id FROM nexus.task_queue
                WHERE cooldown_key = %s AND cooldown_until > now()
            """, [cooldown_key])
            if cur.fetchone():
                return None  # Cooldown active

            # Get cooldown hours from settings
            cooldown_hours = self.get_setting("analysis_cooldown_hours", 4)
            if isinstance(cooldown_hours, str):
                cooldown_hours = int(cooldown_hours)

            cur.execute("""
                INSERT INTO nexus.task_queue (task_type, ticker, analysis_type, priority, cooldown_key, cooldown_until)
                VALUES ('analysis', %s, %s, %s, %s, now() + interval '%s hours')
                RETURNING id
            """, [ticker.upper(), analysis_type, priority, cooldown_key, cooldown_hours])
            task_id = cur.fetchone()["id"]
        self.conn.commit()
        return task_id

    def queue_task(
        self,
        task_type: str,
        ticker: str | None,
        prompt: str,
        priority: int = 5,
        cooldown_key: str | None = None,
        cooldown_hours: int = 0
    ) -> int | None:
        """Queue a task with optional cooldown deduplication.

        Args:
            task_type: Type of task (analysis, post_trade_review, fill_analysis, etc.)
            ticker: Stock ticker (optional for some task types)
            prompt: Task prompt/description
            priority: Task priority (1-10, higher = more urgent)
            cooldown_key: Unique key for deduplication (e.g., "fill_analysis:NVDA")
            cooldown_hours: Hours to suppress duplicate tasks with same cooldown_key

        Returns:
            Task ID if queued, None if suppressed by cooldown
        """
        # Check cooldown if specified
        if cooldown_key and cooldown_hours > 0:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT id FROM nexus.task_queue
                    WHERE cooldown_key = %s
                    AND cooldown_until > NOW()
                    AND status IN ('pending', 'running')
                """, [cooldown_key])
                existing = cur.fetchone()
                if existing:
                    log.debug(f"Task {cooldown_key} on cooldown, skipping (existing: {existing['id']})")
                    return None

        # Calculate cooldown_until
        cooldown_until = None
        if cooldown_key and cooldown_hours > 0:
            cooldown_until = datetime.now() + timedelta(hours=cooldown_hours)

        # Queue the task
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.task_queue (task_type, ticker, prompt, priority, cooldown_key, cooldown_until)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, [task_type, ticker.upper() if ticker else None, prompt, priority, cooldown_key, cooldown_until])
            task_id = cur.fetchone()["id"]
        self.conn.commit()

        log.info(f"Queued task {task_id}: {task_type} for {ticker or 'N/A'}")
        return task_id

    def get_pending_tasks(self, limit: int = 10) -> list[dict]:
        """Get pending tasks ordered by priority."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.task_queue
                WHERE status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT %s
            """, [limit])
            return [dict(r) for r in cur.fetchall()]

    def mark_task_started(self, task_id: int) -> None:
        """Mark task as running."""
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE nexus.task_queue SET status = 'running', started_at = now() WHERE id = %s",
                [task_id]
            )
        self.conn.commit()

    def mark_task_completed(self, task_id: int, error: str | None = None) -> None:
        """Mark task as completed or failed."""
        status = 'failed' if error else 'completed'
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.task_queue SET
                    status = %s,
                    completed_at = now(),
                    error_message = %s
                WHERE id = %s
            """, [status, error, task_id])
        self.conn.commit()

    def get_task_queue_stats(self) -> dict:
        """Get task queue statistics."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT status, COUNT(*) as count
                FROM nexus.task_queue
                GROUP BY status
            """)
            rows = cur.fetchall()
        return {r["status"]: r["count"] for r in rows}

    # ─── Task Queue Retry Methods ────────────────────────────────────────────────

    def get_retryable_tasks(self, limit: int = 5) -> list[dict]:
        """Get failed tasks that are ready for retry."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.task_queue
                WHERE status = 'failed'
                  AND retry_count < COALESCE(max_retries, 3)
                  AND (next_retry_at IS NULL OR next_retry_at <= now())
                ORDER BY priority DESC, created_at ASC
                LIMIT %s
            """, [limit])
            return [dict(r) for r in cur.fetchall()]

    def mark_task_for_retry(self, task_id: int, delay_minutes: int = 15) -> None:
        """Mark failed task for retry with exponential backoff."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.task_queue SET
                    status = 'pending',
                    retry_count = retry_count + 1,
                    next_retry_at = now() + ((%s * power(2, retry_count)) || ' minutes')::interval,
                    error_message = NULL,
                    started_at = NULL,
                    completed_at = NULL
                WHERE id = %s AND retry_count < COALESCE(max_retries, 3)
            """, [delay_minutes, task_id])
        self.conn.commit()

    def recover_stuck_tasks(self, timeout_minutes: int = 30) -> int:
        """Reset tasks stuck in 'running' state for too long."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.task_queue SET
                    status = 'pending',
                    started_at = NULL,
                    error_message = 'Task timeout - auto-recovered'
                WHERE status = 'running'
                  AND started_at < now() - (%s || ' minutes')::interval
                RETURNING id
            """, [timeout_minutes])
            stuck = cur.fetchall()
        self.conn.commit()
        return len(stuck)

    def get_pending_or_retryable_tasks(self, limit: int = 10) -> list[dict]:
        """Get pending tasks OR failed tasks ready for retry."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.task_queue
                WHERE (status = 'pending')
                   OR (status = 'failed'
                       AND retry_count < COALESCE(max_retries, 3)
                       AND (next_retry_at IS NULL OR next_retry_at <= now()))
                ORDER BY priority DESC, created_at ASC
                LIMIT %s
            """, [limit])
            return [dict(r) for r in cur.fetchall()]

    # ─── ADK Run State Methods ─────────────────────────────────────────────

    def create_run_state_run(
        self,
        run_id: str,
        status: str = "requested",
        *,
        parent_run_id: str | None = None,
        intent: str | None = None,
        ticker: str | None = None,
        analysis_type: str | None = None,
        contract_version: str | None = None,
        routing_policy_version: str | None = None,
        effective_config_hash: str | None = None,
    ) -> bool:
        """Create a run-state header row. Returns True when inserted."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nexus.run_state_runs (
                    run_id,
                    parent_run_id,
                    intent,
                    ticker,
                    analysis_type,
                    status,
                    contract_version,
                    routing_policy_version,
                    effective_config_hash
                )
                VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id) DO NOTHING
                RETURNING run_id
                """,
                [
                    run_id,
                    parent_run_id,
                    intent,
                    ticker,
                    analysis_type,
                    status,
                    contract_version,
                    routing_policy_version,
                    effective_config_hash,
                ],
            )
            inserted = cur.fetchone() is not None
        self.conn.commit()
        return inserted

    def append_run_state_event(
        self,
        run_id: str,
        *,
        from_state: str,
        to_state: str,
        phase: str,
        event_type: str = "state_transition",
        event_payload: dict[str, Any] | None = None,
        policy_decisions: list[dict[str, Any]] | None = None,
    ) -> int:
        """Append transition event and update current run state. Returns event ID."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nexus.run_state_events (
                    run_id,
                    from_state,
                    to_state,
                    phase,
                    event_type,
                    event_payload_json,
                    policy_decisions_json
                )
                VALUES (%s::uuid, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                RETURNING id
                """,
                [
                    run_id,
                    from_state,
                    to_state,
                    phase,
                    event_type,
                    json.dumps(event_payload) if event_payload is not None else None,
                    json.dumps(policy_decisions) if policy_decisions is not None else None,
                ],
            )
            event_id = cur.fetchone()["id"]
            cur.execute(
                """
                UPDATE nexus.run_state_runs
                SET status = %s,
                    updated_at = now()
                WHERE run_id = %s::uuid
                """,
                [to_state, run_id],
            )
        self.conn.commit()
        return event_id

    def get_run_state_status(self, run_id: str) -> str | None:
        """Get latest status for a run ID."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM nexus.run_state_runs WHERE run_id = %s::uuid",
                [run_id],
            )
            row = cur.fetchone()
        return row["status"] if row else None

    def get_run_dedup(self, dedup_key: str) -> dict[str, Any] | None:
        """Get active dedup record for the key when not expired."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT dedup_key, run_id::text AS run_id, status, response_json
                FROM nexus.run_request_dedup
                WHERE dedup_key = %s AND expires_at > now()
                """,
                [dedup_key],
            )
            row = cur.fetchone()
        return dict(row) if row else None

    def claim_run_dedup(self, dedup_key: str, run_id: str) -> bool:
        """Attempt to claim a dedup key for a new run. Returns True on claim."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nexus.run_request_dedup (dedup_key, run_id, status)
                VALUES (%s, %s::uuid, 'in_progress')
                ON CONFLICT (dedup_key) DO NOTHING
                RETURNING dedup_key
                """,
                [dedup_key, run_id],
            )
            inserted = cur.fetchone() is not None
        self.conn.commit()
        return inserted

    def finalize_run_dedup(
        self,
        dedup_key: str,
        *,
        status: str,
        response: dict[str, Any] | None = None,
    ) -> bool:
        """Finalize dedup record with terminal status and response envelope."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nexus.run_request_dedup
                SET status = %s,
                    response_json = %s::jsonb,
                    updated_at = now()
                WHERE dedup_key = %s
                RETURNING dedup_key
                """,
                [status, json.dumps(response) if response is not None else None, dedup_key],
            )
            updated = cur.fetchone() is not None
        self.conn.commit()
        return updated

    def claim_run_side_effect_marker(self, run_id: str, phase: str, marker_key: str) -> bool:
        """Claim a side-effect marker. Returns True only once per marker tuple."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nexus.run_side_effect_markers (run_id, phase, marker_key)
                VALUES (%s::uuid, %s, %s)
                ON CONFLICT (run_id, phase, marker_key) DO NOTHING
                RETURNING run_id
                """,
                [run_id, phase, marker_key],
            )
            inserted = cur.fetchone() is not None
        self.conn.commit()
        return inserted

    # ─── Position Detection Methods (IPLAN-005) ─────────────────────────────────

    def add_trade_detected(self, trade: dict) -> int:
        """Add new trade entry from position detection with options support. Returns trade ID."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.trades (
                    ticker, entry_date, entry_price, entry_size, entry_type,
                    current_size, thesis, source_analysis, source_type, direction,
                    full_symbol, option_underlying, option_expiration, option_strike,
                    option_type, option_multiplier, is_credit
                )
                VALUES (
                    %(ticker)s, %(entry_date)s, %(entry_price)s, %(entry_size)s, %(entry_type)s,
                    %(entry_size)s, %(thesis)s, %(source_analysis)s, %(source_type)s, %(direction)s,
                    %(full_symbol)s, %(option_underlying)s, %(option_expiration)s, %(option_strike)s,
                    %(option_type)s, %(option_multiplier)s, %(is_credit)s
                )
                RETURNING id
            """, {
                "ticker": trade.get("ticker", "").upper(),
                "entry_date": trade.get("entry_date", datetime.now()),
                "entry_price": trade.get("entry_price"),
                "entry_size": trade.get("entry_size"),
                "entry_type": trade.get("entry_type", "stock"),
                "thesis": trade.get("thesis"),
                "source_analysis": trade.get("source_analysis"),
                "source_type": trade.get("source_type", "detected"),
                "direction": trade.get("direction", "long"),
                "full_symbol": trade.get("full_symbol"),
                "option_underlying": trade.get("option_underlying"),
                "option_expiration": trade.get("option_expiration"),
                "option_strike": trade.get("option_strike"),
                "option_type": trade.get("option_type"),
                "option_multiplier": trade.get("option_multiplier", 100),
                "is_credit": trade.get("is_credit", False),
            })
            trade_id = cur.fetchone()["id"]
        self.conn.commit()
        return trade_id

    def get_trades_by_source_type(self, source_types: list[str]) -> list[dict]:
        """Get trades filtered by source_type."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.trades
                WHERE source_type = ANY(%s)
                ORDER BY created_at DESC
            """, [source_types])
            return [dict(r) for r in cur.fetchall()]

    def update_trade(self, trade_id: int, **kwargs) -> bool:
        """Update trade with arbitrary fields."""
        if not kwargs:
            return False

        # Whitelist of allowed columns
        allowed = {
            "source_type", "thesis", "entry_price", "entry_size", "current_size",
            "exit_price", "exit_reason", "status", "direction"
        }
        invalid = set(kwargs.keys()) - allowed
        if invalid:
            raise ValueError(f"Invalid trade column(s): {invalid}")

        set_parts = []
        params = []
        for key, val in kwargs.items():
            set_parts.append(f"{key} = %s")
            params.append(val)
        params.append(trade_id)

        with self.conn.cursor() as cur:
            cur.execute(
                f"UPDATE nexus.trades SET {', '.join(set_parts)}, updated_at = now() WHERE id = %s RETURNING id",
                params
            )
            updated = cur.fetchone() is not None
        self.conn.commit()
        return updated

    def archive_trade(self, trade_id: int, reason: str | None = None) -> bool:
        """Archive a trade (move to trades_archive and delete from trades)."""
        with self.conn.cursor() as cur:
            # Copy to archive
            cur.execute("""
                INSERT INTO nexus.trades_archive
                    (id, ticker, entry_date, entry_price, entry_size, direction,
                     thesis, source_type, source_analysis, archive_reason)
                SELECT id, ticker, entry_date, entry_price, entry_size, direction,
                       thesis, source_type, source_analysis, %s
                FROM nexus.trades WHERE id = %s
                RETURNING id
            """, [reason, trade_id])

            archived = cur.fetchone() is not None
            if archived:
                # Delete from trades
                cur.execute("DELETE FROM nexus.trades WHERE id = %s", [trade_id])

        self.conn.commit()
        return archived

    def record_position_detection(self, ticker: str, size: float, trade_id: int,
                                   full_symbol: str | None = None) -> int | None:
        """Record a position detection for idempotency tracking.

        For options, full_symbol should be the OCC symbol to distinguish
        different contracts on the same underlying.
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO nexus.position_detections (ticker, size, trade_id, full_symbol)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                """, [ticker.upper(), size, trade_id, full_symbol])
                row = cur.fetchone()
            self.conn.commit()
            return row["id"] if row else None
        except Exception as e:
            log.warning(f"Failed to record position detection: {e}")
            return None

    def get_position_detections_today(self, symbol_key: str) -> list[dict]:
        """Get position detections for a symbol today.

        Args:
            symbol_key: Ticker for stocks, full OCC symbol for options
        """
        with self.conn.cursor() as cur:
            # Check both ticker and full_symbol columns
            cur.execute("""
                SELECT * FROM nexus.position_detections
                WHERE (full_symbol = %s OR (full_symbol IS NULL AND ticker = %s))
                  AND detected_date = CURRENT_DATE
            """, [symbol_key, symbol_key.upper()])
            return [dict(r) for r in cur.fetchall()]

    def complete_task_by_type(self, task_type: str, ticker: str | None = None) -> bool:
        """Complete tasks by type and optional ticker."""
        with self.conn.cursor() as cur:
            if ticker:
                cur.execute("""
                    UPDATE nexus.task_queue SET
                        status = 'completed', completed_at = now()
                    WHERE task_type = %s AND ticker = %s AND status IN ('pending', 'running')
                    RETURNING id
                """, [task_type, ticker.upper()])
            else:
                cur.execute("""
                    UPDATE nexus.task_queue SET
                        status = 'completed', completed_at = now()
                    WHERE task_type = %s AND status IN ('pending', 'running')
                    RETURNING id
                """, [task_type])
            updated = cur.fetchone() is not None
        self.conn.commit()
        return updated

    # ─── Options-Specific Methods (IPLAN-006) ────────────────────────────────────

    def get_options_positions(self, underlying: str | None = None) -> list[dict]:
        """Get open options positions, optionally filtered by underlying."""
        with self.conn.cursor() as cur:
            if underlying:
                cur.execute("""
                    SELECT * FROM nexus.v_options_positions
                    WHERE option_underlying = %s
                """, [underlying.upper()])
            else:
                cur.execute("SELECT * FROM nexus.v_options_positions")
            return [dict(r) for r in cur.fetchall()]

    def get_expiring_options(self, days: int = 7) -> list[dict]:
        """Get options expiring within N days."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.v_options_positions
                WHERE days_to_expiry <= %s
                ORDER BY option_expiration ASC
            """, [days])
            return [dict(r) for r in cur.fetchall()]

    def close_option_trade(
        self,
        trade_id: int,
        exit_price: float,
        exit_reason: str,
        expiration_action: str | None = None
    ) -> bool:
        """Close options trade with proper P&L calculation.

        For long options: P&L = (exit - entry) * size * multiplier
        For short options: P&L = (entry - exit) * size * multiplier
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.trades SET
                    status = 'closed',
                    exit_date = now(),
                    exit_price = %(exit_price)s,
                    exit_reason = %(exit_reason)s,
                    expiration_action = %(expiration_action)s,
                    pnl_dollars = CASE
                        WHEN is_credit THEN
                            (entry_price - %(exit_price)s) * COALESCE(current_size, entry_size) * COALESCE(option_multiplier, 100)
                        ELSE
                            (%(exit_price)s - entry_price) * COALESCE(current_size, entry_size) * COALESCE(option_multiplier, 100)
                    END,
                    pnl_pct = CASE
                        WHEN entry_price > 0 THEN
                            CASE
                                WHEN is_credit THEN ((entry_price - %(exit_price)s) / entry_price) * 100
                                ELSE ((%(exit_price)s - entry_price) / entry_price) * 100
                            END
                        ELSE 0
                    END,
                    updated_at = now()
                WHERE id = %(trade_id)s
                RETURNING id
            """, {
                "exit_price": exit_price,
                "exit_reason": exit_reason,
                "expiration_action": expiration_action,
                "trade_id": trade_id
            })
            updated = cur.fetchone() is not None
        self.conn.commit()
        return updated

    def get_short_options_by_underlying(self, underlying: str) -> list[dict]:
        """Get open short options for an underlying (for assignment detection)."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.trades
                WHERE option_underlying = %s
                  AND status = 'open'
                  AND is_credit = TRUE
            """, [underlying.upper()])
            return [dict(r) for r in cur.fetchall()]

    def close_expired_option_worthless(self, trade_id: int) -> bool:
        """Close option trade as expired worthless."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.trades SET
                    status = 'closed',
                    exit_date = option_expiration,
                    exit_price = 0,
                    exit_reason = 'expired_worthless',
                    expiration_action = 'expired_worthless',
                    pnl_dollars = CASE
                        WHEN is_credit THEN entry_price * COALESCE(current_size, entry_size) * COALESCE(option_multiplier, 100)
                        ELSE -entry_price * COALESCE(current_size, entry_size) * COALESCE(option_multiplier, 100)
                    END,
                    pnl_pct = CASE WHEN is_credit THEN 100 ELSE -100 END,
                    updated_at = now()
                WHERE id = %s
                RETURNING id
            """, [trade_id])
            updated = cur.fetchone() is not None
        self.conn.commit()
        return updated

    # ─── Analysis Lineage Methods (IPLAN-001) ─────────────────────────────────────

    def get_pending_post_earnings_reviews(self) -> list[dict]:
        """Get earnings analyses that need post-earnings review."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.analysis_lineage
                WHERE analysis_type = 'earnings-analysis'
                AND earnings_date < CURRENT_DATE
                AND earnings_date >= CURRENT_DATE - INTERVAL '7 days'
                AND post_earnings_review_file IS NULL
                AND current_status = 'active'
                ORDER BY earnings_date DESC
            """)
            return [dict(r) for r in cur.fetchall()]

    def get_expired_forecasts(self) -> list[dict]:
        """Get analyses with expired forecast_valid_until."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.analysis_lineage
                WHERE forecast_valid_until < CURRENT_DATE
                AND current_status = 'active'
                ORDER BY forecast_valid_until DESC
            """)
            return [dict(r) for r in cur.fetchall()]

    def get_analysis_lineage(self, ticker: str, limit: int = 10) -> list[dict]:
        """Get analysis lineage chain for a ticker."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.analysis_lineage
                WHERE ticker = %s
                ORDER BY current_analysis_date DESC
                LIMIT %s
            """, [ticker.upper(), limit])
            return [dict(r) for r in cur.fetchall()]

    def get_active_analysis(self, ticker: str, analysis_type: str) -> dict | None:
        """Get the most recent active analysis for a ticker."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.analysis_lineage
                WHERE ticker = %s
                AND analysis_type = %s
                AND current_status = 'active'
                ORDER BY current_analysis_date DESC
                LIMIT 1
            """, [ticker.upper(), analysis_type])
            row = cur.fetchone()
        return dict(row) if row else None

    def create_lineage_entry(
        self,
        ticker: str,
        analysis_type: str,
        current_analysis_file: str,
        forecast_valid_until: date | None = None,
        earnings_date: date | None = None,
        prior_analysis_file: str | None = None,
        prior_analysis_date: datetime | None = None
    ) -> int:
        """Create a new analysis lineage entry. Returns lineage ID."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.analysis_lineage
                    (ticker, analysis_type, current_analysis_file, current_analysis_date,
                     forecast_valid_until, earnings_date, prior_analysis_file, prior_analysis_date)
                VALUES (%s, %s, %s, now(), %s, %s, %s, %s)
                RETURNING id
            """, [
                ticker.upper(),
                analysis_type,
                current_analysis_file,
                forecast_valid_until,
                earnings_date,
                prior_analysis_file,
                prior_analysis_date
            ])
            lineage_id = cur.fetchone()["id"]
        self.conn.commit()
        return lineage_id

    def update_lineage_status(
        self,
        lineage_id: int,
        status: str,
        validation_file: str | None = None,
        validation_result: str | None = None,
        post_earnings_file: str | None = None,
        grade: str | None = None
    ) -> bool:
        """Update analysis lineage status."""
        updates = ["current_status = %s"]
        params: list = [status]

        if validation_file:
            updates.append("validation_file = %s")
            updates.append("validation_date = now()")
            params.append(validation_file)

        if validation_result:
            updates.append("validation_result = %s")
            params.append(validation_result)

        if post_earnings_file:
            updates.append("post_earnings_review_file = %s")
            updates.append("post_earnings_review_date = now()")
            params.append(post_earnings_file)

        if grade:
            updates.append("post_earnings_grade = %s")
            params.append(grade)

        params.append(lineage_id)

        with self.conn.cursor() as cur:
            cur.execute(
                f"UPDATE nexus.analysis_lineage SET {', '.join(updates)} WHERE id = %s RETURNING id",
                params
            )
            updated = cur.fetchone() is not None
        self.conn.commit()
        return updated

    def get_latest_earnings_analysis(self, ticker: str) -> str | None:
        """Get the latest earnings analysis file path for a ticker."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT current_analysis_file FROM nexus.analysis_lineage
                WHERE ticker = %s AND analysis_type = 'earnings-analysis'
                ORDER BY current_analysis_date DESC
                LIMIT 1
            """, [ticker.upper()])
            row = cur.fetchone()
        return row["current_analysis_file"] if row else None

    def get_latest_analysis(self, ticker: str, analysis_type: str = None) -> str | None:
        """Get the latest analysis file path for a ticker."""
        with self.conn.cursor() as cur:
            if analysis_type:
                cur.execute("""
                    SELECT current_analysis_file FROM nexus.analysis_lineage
                    WHERE ticker = %s AND analysis_type = %s
                    ORDER BY current_analysis_date DESC
                    LIMIT 1
                """, [ticker.upper(), analysis_type])
            else:
                cur.execute("""
                    SELECT current_analysis_file FROM nexus.analysis_lineage
                    WHERE ticker = %s
                    ORDER BY current_analysis_date DESC
                    LIMIT 1
                """, [ticker.upper()])
            row = cur.fetchone()
        return row["current_analysis_file"] if row else None

    def get_all_unreviewed_earnings_analyses(self) -> list[dict]:
        """Get all earnings analyses that haven't been reviewed (for backfill)."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.analysis_lineage
                WHERE analysis_type = 'earnings-analysis'
                AND post_earnings_review_file IS NULL
                AND earnings_date IS NOT NULL
                ORDER BY earnings_date DESC
            """)
            return [dict(r) for r in cur.fetchall()]

    # ─── Confidence Calibration Methods (IPLAN-001) ───────────────────────────────

    def update_confidence_calibration(
        self,
        ticker: str | None,
        analysis_type: str,
        confidence: int,
        was_correct: bool
    ) -> bool:
        """Update confidence calibration tracking."""
        bucket = (confidence // 10) * 10  # Round to nearest 10
        correct_int = 1 if was_correct else 0

        with self.conn.cursor() as cur:
            # Upsert for ticker-specific calibration
            cur.execute("""
                INSERT INTO nexus.confidence_calibration
                    (ticker, analysis_type, confidence_bucket, total_predictions, correct_predictions)
                VALUES (%s, %s, %s, 1, %s)
                ON CONFLICT (COALESCE(ticker, ''), analysis_type, confidence_bucket)
                DO UPDATE SET
                    total_predictions = nexus.confidence_calibration.total_predictions + 1,
                    correct_predictions = nexus.confidence_calibration.correct_predictions + %s,
                    actual_rate = (nexus.confidence_calibration.correct_predictions + %s)::decimal /
                                 (nexus.confidence_calibration.total_predictions + 1),
                    last_updated = now()
            """, [ticker, analysis_type, bucket, correct_int, correct_int, correct_int])

            # Also update aggregate (ticker=NULL)
            cur.execute("""
                INSERT INTO nexus.confidence_calibration
                    (ticker, analysis_type, confidence_bucket, total_predictions, correct_predictions)
                VALUES (NULL, %s, %s, 1, %s)
                ON CONFLICT (COALESCE(ticker, ''), analysis_type, confidence_bucket)
                DO UPDATE SET
                    total_predictions = nexus.confidence_calibration.total_predictions + 1,
                    correct_predictions = nexus.confidence_calibration.correct_predictions + %s,
                    actual_rate = (nexus.confidence_calibration.correct_predictions + %s)::decimal /
                                 (nexus.confidence_calibration.total_predictions + 1),
                    last_updated = now()
            """, [analysis_type, bucket, correct_int, correct_int, correct_int])

        self.conn.commit()
        return True

    def get_calibration_stats(self, bucket: int | None = None) -> list[dict]:
        """Get confidence calibration statistics."""
        with self.conn.cursor() as cur:
            if bucket:
                cur.execute("""
                    SELECT * FROM nexus.confidence_calibration
                    WHERE ticker IS NULL AND confidence_bucket = %s
                    ORDER BY analysis_type, confidence_bucket
                """, [bucket])
            else:
                cur.execute("""
                    SELECT * FROM nexus.confidence_calibration
                    WHERE ticker IS NULL
                    ORDER BY analysis_type, confidence_bucket
                """)
            return [dict(r) for r in cur.fetchall()]

    def get_ticker_calibration(self, ticker: str, analysis_type: str) -> list[dict]:
        """Get confidence calibration for a specific ticker."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.confidence_calibration
                WHERE ticker = %s AND analysis_type = %s
                ORDER BY confidence_bucket
            """, [ticker.upper(), analysis_type])
            return [dict(r) for r in cur.fetchall()]

    # ─── Watchlist Invalidation (IPLAN-001) ───────────────────────────────────────

    def invalidate_watchlist_entry(self, ticker: str, reason: str) -> bool:
        """Invalidate watchlist entry for ticker if exists."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.watchlist
                SET status = 'invalidated',
                    notes = COALESCE(notes, '') || ' | Invalidated: ' || %s,
                    updated_at = now()
                WHERE ticker = %s
                AND status = 'active'
                RETURNING id
            """, [reason, ticker.upper()])
            result = cur.fetchone()
        self.conn.commit()
        return result is not None

    def task_already_queued(self, task_type: str, ticker: str, context_key: str = None) -> bool:
        """Check if a task is already queued (pending or running) to prevent duplicates."""
        cooldown_key = f"{task_type}:{ticker}:{context_key}" if context_key else f"{task_type}:{ticker}"
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM nexus.task_queue
                WHERE cooldown_key = %s
                AND status IN ('pending', 'running')
                LIMIT 1
            """, [cooldown_key])
            return cur.fetchone() is not None

    # ═══════════════════════════════════════════════════════════════════════════
    # Knowledge Base Methods (Migration 009)
    # ═══════════════════════════════════════════════════════════════════════════

    # ─── KB Validation Helpers ──────────────────────────────────────────────────

    def _validate_ticker(self, ticker: str | None, context: str = "operation") -> str:
        """Validate and normalize ticker symbol. Raises ValueError if invalid."""
        if not ticker:
            raise ValueError(f"ticker is required for {context}")
        ticker = ticker.upper().strip()
        if not ticker or len(ticker) > 10:
            raise ValueError(f"Invalid ticker format: {ticker}")
        return ticker

    def _validate_file_path(self, file_path: str | None, context: str = "operation") -> str:
        """Validate file path. Raises ValueError if invalid."""
        if not file_path:
            raise ValueError(f"file_path is required for {context}")
        # Normalize path
        from pathlib import Path
        return str(Path(file_path).resolve())

    def _extract_ticker_from_data(self, data: dict) -> str | None:
        """Extract ticker from YAML data, checking multiple locations."""
        meta = data.get("_meta", {})
        trade = data.get("trade", {})

        # Check common locations
        ticker = data.get("ticker") or meta.get("ticker") or trade.get("ticker")

        # Try to extract from ID (e.g., "NVDA_20260223T1100")
        if not ticker and meta.get("id"):
            id_val = meta["id"]
            if "_" in id_val:
                ticker = id_val.split("_")[0]

        return ticker.upper() if ticker else None

    # ─── KB Stock Analyses ─────────────────────────────────────────────────────

    def upsert_kb_stock_analysis(self, file_path: str, data: dict, user_id: int = 1) -> int:
        """Upsert a stock analysis into kb_stock_analyses. Returns ID."""
        # Validate inputs
        file_path = self._validate_file_path(file_path, "stock analysis")
        ticker = self._extract_ticker_from_data(data)
        ticker = self._validate_ticker(ticker, "stock analysis")

        meta = data.get("_meta", {})
        # v2.7 template: fields at top level, not under "decision"
        gate = data.get("do_nothing_gate", {})
        scenarios = data.get("scenarios", {})
        trade = data.get("trade_plan", {})
        summary = data.get("summary", {})
        scoring = data.get("scoring", {})
        threat = data.get("threat_assessment", {})
        catalyst = data.get("catalyst", {})
        bull_case = data.get("bull_case_analysis", {})
        bear_case = data.get("bear_case_analysis", {})

        recommendation_raw = data.get("recommendation")
        recommendation_action: str | None = None
        recommendation_confidence: int | None = None
        if isinstance(recommendation_raw, dict):
            recommendation_action = recommendation_raw.get("action") or recommendation_raw.get("recommendation")
            rec_conf = recommendation_raw.get("confidence")
            if isinstance(rec_conf, (int, float)) and not isinstance(rec_conf, bool):
                recommendation_confidence = int(rec_conf)
            elif isinstance(rec_conf, str) and rec_conf.strip().isdigit():
                recommendation_confidence = int(rec_conf.strip())
        elif isinstance(recommendation_raw, str):
            recommendation_action = recommendation_raw

        confidence_raw = data.get("confidence")
        confidence_level: int | None = None
        if isinstance(confidence_raw, dict):
            for key in ("level", "confidence", "confidence_pct", "pct"):
                candidate = confidence_raw.get(key)
                if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
                    confidence_level = int(candidate)
                    break
                if isinstance(candidate, str) and candidate.strip().isdigit():
                    confidence_level = int(candidate.strip())
                    break
        elif isinstance(confidence_raw, (int, float)) and not isinstance(confidence_raw, bool):
            confidence_level = int(confidence_raw)
        elif isinstance(confidence_raw, str) and confidence_raw.strip().isdigit():
            confidence_level = int(confidence_raw.strip())

        if confidence_level is None:
            confidence_level = recommendation_confidence
        if confidence_level is None:
            gate_confidence = gate.get("confidence_actual")
            if isinstance(gate_confidence, (int, float)) and not isinstance(gate_confidence, bool):
                confidence_level = int(gate_confidence)

        expected_value_pct = gate.get("ev_actual")
        if not isinstance(expected_value_pct, (int, float)) or isinstance(expected_value_pct, bool):
            expected_value_pct = gate.get("expected_value_actual")

        # Extract risk/reward ratio from gate criteria or gate.rr_actual
        rr_criteria = gate.get("criteria", {}).get("risk_reward", {})
        risk_reward = rr_criteria.get("value") if isinstance(rr_criteria, dict) else gate.get("rr_actual")

        # Extract position size from trade_plan
        position_sizing = trade.get("position_sizing", {})
        position_size = position_sizing.get("max_portfolio_pct")

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO nexus.kb_stock_analyses (
                        ticker, analysis_date, schema_version, file_path,
                        current_price, recommendation, confidence, expected_value_pct,
                        gate_result, gate_criteria_met,
                        bull_probability, base_probability, bear_probability,
                        entry_price, stop_price, target_1_price, target_2_price,
                        catalyst_score, technical_score, fundamental_score, sentiment_score,
                        total_threat_level, yaml_content,
                        bull_case_strength, bear_case_strength,
                        catalyst_type, catalyst_date, risk_reward_ratio, position_size_pct, days_to_catalyst,
                        user_id
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s
                    )
                    ON CONFLICT (file_path) DO UPDATE SET
                        current_price = EXCLUDED.current_price,
                        recommendation = EXCLUDED.recommendation,
                        confidence = EXCLUDED.confidence,
                        expected_value_pct = EXCLUDED.expected_value_pct,
                        gate_result = EXCLUDED.gate_result,
                        gate_criteria_met = EXCLUDED.gate_criteria_met,
                        bull_probability = EXCLUDED.bull_probability,
                        base_probability = EXCLUDED.base_probability,
                        bear_probability = EXCLUDED.bear_probability,
                        entry_price = EXCLUDED.entry_price,
                        stop_price = EXCLUDED.stop_price,
                        target_1_price = EXCLUDED.target_1_price,
                        target_2_price = EXCLUDED.target_2_price,
                        catalyst_score = EXCLUDED.catalyst_score,
                        technical_score = EXCLUDED.technical_score,
                        fundamental_score = EXCLUDED.fundamental_score,
                        sentiment_score = EXCLUDED.sentiment_score,
                        total_threat_level = EXCLUDED.total_threat_level,
                        yaml_content = EXCLUDED.yaml_content,
                        bull_case_strength = EXCLUDED.bull_case_strength,
                        bear_case_strength = EXCLUDED.bear_case_strength,
                        catalyst_type = EXCLUDED.catalyst_type,
                        catalyst_date = EXCLUDED.catalyst_date,
                        risk_reward_ratio = EXCLUDED.risk_reward_ratio,
                        position_size_pct = EXCLUDED.position_size_pct,
                        days_to_catalyst = EXCLUDED.days_to_catalyst,
                        user_id = EXCLUDED.user_id,
                        updated_at = now()
                    RETURNING id
                """, [
                    ticker,
                    meta.get("created"),
                    meta.get("schema_version") or meta.get("version"),
                    file_path,
                    data.get("current_price"),
                    recommendation_action,
                    confidence_level,
                    expected_value_pct,
                    gate.get("gate_result"),  # v2.7: do_nothing_gate.gate_result
                    gate.get("gates_passed"),  # v2.7: do_nothing_gate.gates_passed
                    scenarios.get("strong_bull", {}).get("probability"),
                    scenarios.get("base_bull", {}).get("probability"),
                    scenarios.get("base_bear", {}).get("probability"),
                    summary.get("key_levels", {}).get("entry"),  # v2.7: summary.key_levels
                    summary.get("key_levels", {}).get("stop"),
                    summary.get("key_levels", {}).get("target_1"),
                    summary.get("key_levels", {}).get("target_2"),
                    scoring.get("catalyst_score"),  # v2.7: scoring section
                    scoring.get("technical_score"),
                    scoring.get("fundamental_score") or scoring.get("environment_score"),  # v2.7 may use environment_score
                    scoring.get("sentiment_score"),
                    threat.get("total_threat_level"),  # v2.7: threat_assessment
                    json.dumps(data, default=str),
                    # New fields (migration 016)
                    bull_case.get("strength"),
                    bear_case.get("strength"),
                    catalyst.get("type"),
                    catalyst.get("date"),
                    risk_reward,
                    position_size,  # Added: from trade_plan.position_sizing.max_portfolio_pct
                    catalyst.get("days_until"),
                    user_id,
                ])
                result = cur.fetchone()
                if result is None:
                    raise RuntimeError(f"Upsert returned no ID for {file_path}")
            self.conn.commit()
            return result["id"]
        except Exception as e:
            self.conn.rollback()
            log.error(f"Failed to upsert stock analysis {file_path}: {e}")
            raise

    def get_kb_stock_analysis(self, ticker: str, analysis_date: datetime = None) -> dict | None:
        """Get stock analysis by ticker and optional date."""
        with self.conn.cursor() as cur:
            if analysis_date:
                cur.execute("""
                    SELECT * FROM nexus.kb_stock_analyses
                    WHERE ticker = %s AND DATE(analysis_date) = DATE(%s)
                    ORDER BY analysis_date DESC LIMIT 1
                """, [ticker.upper(), analysis_date])
            else:
                cur.execute("""
                    SELECT * FROM nexus.kb_stock_analyses
                    WHERE ticker = %s
                    ORDER BY analysis_date DESC LIMIT 1
                """, [ticker.upper()])
            row = cur.fetchone()
        return dict(row) if row else None

    def get_latest_kb_stock_analysis(self, ticker: str) -> dict | None:
        """Get latest stock analysis for ticker."""
        return self.get_kb_stock_analysis(ticker)

    def search_kb_stock_analyses(self, filters: dict) -> list[dict]:
        """Search stock analyses with filters (recommendation, gate_result, min_confidence)."""
        conditions = ["1=1"]
        params = []

        if filters.get("ticker"):
            conditions.append("ticker = %s")
            params.append(filters["ticker"].upper())
        if filters.get("recommendation"):
            conditions.append("recommendation = %s")
            params.append(filters["recommendation"])
        if filters.get("gate_result"):
            conditions.append("gate_result = %s")
            params.append(filters["gate_result"])
        if filters.get("min_confidence"):
            conditions.append("confidence >= %s")
            params.append(filters["min_confidence"])

        limit = filters.get("limit", 50)
        params.append(limit)

        with self.conn.cursor() as cur:
            cur.execute(f"""
                SELECT * FROM nexus.kb_stock_analyses
                WHERE {' AND '.join(conditions)}
                ORDER BY analysis_date DESC
                LIMIT %s
            """, params)
            return [dict(r) for r in cur.fetchall()]

    # ─── KB Earnings Analyses ──────────────────────────────────────────────────

    def upsert_kb_earnings_analysis(self, file_path: str, data: dict, user_id: int = 1) -> int:
        """Upsert an earnings analysis into kb_earnings_analyses. Returns ID."""
        # Validate inputs
        file_path = self._validate_file_path(file_path, "earnings analysis")
        ticker = self._extract_ticker_from_data(data)
        ticker = self._validate_ticker(ticker, "earnings analysis")

        meta = data.get("_meta", {})
        decision = data.get("decision", {})

        # v2.5: do_nothing_gate is at ROOT level, not under decision
        gate = data.get("do_nothing_gate", {}) or decision.get("do_nothing_gate", {})

        # v2.5: case analyses are at ROOT level (bull_case_analysis, bear_case_analysis)
        bull_case = data.get("bull_case_analysis", {}) or data.get("case_analysis", {}).get("bull_case", {})
        bear_case = data.get("bear_case_analysis", {}) or data.get("case_analysis", {}).get("bear_case", {})

        scenarios = data.get("scenarios", {})
        threat = data.get("threat_assessment", {})
        trade = data.get("trade_plan", {})
        preparation = data.get("preparation", {})
        summary = data.get("summary", {})
        probability = data.get("probability", {})

        # v2.6: scoring section added for consistency with stock-analysis
        scoring = data.get("scoring", {})

        # Extract earnings fields from root level (v2.4+ schema)
        # Also check under "earnings" for older schemas
        earnings_date = data.get("earnings_date") or data.get("earnings", {}).get("date")
        earnings_time = data.get("earnings_time") or data.get("earnings", {}).get("time")
        days_to_earnings = data.get("days_to_earnings") or data.get("earnings", {}).get("days_to_earnings")

        # Extract risk/reward ratio from gate criteria
        rr_criteria = gate.get("criteria", {}).get("risk_reward", {})
        risk_reward = rr_criteria.get("value") if isinstance(rr_criteria, dict) else gate.get("rr_actual")

        # v2.5: IV data is under preparation.implied_move, not options_data
        implied_move = preparation.get("implied_move", {})
        iv_rank = implied_move.get("iv_rank") or data.get("options_data", {}).get("iv_rank")
        expected_move_pct = implied_move.get("percentage") or data.get("options_data", {}).get("expected_move_pct")

        # v2.5: scenarios use strong_beat/modest_beat/modest_miss/strong_miss (not bull/base/bear/disaster)
        bull_prob = scenarios.get("strong_beat", {}).get("probability") or scenarios.get("bull", {}).get("probability")
        base_prob = scenarios.get("modest_beat", {}).get("probability") or scenarios.get("base", {}).get("probability")
        bear_prob = scenarios.get("modest_miss", {}).get("probability") or scenarios.get("bear", {}).get("probability")
        disaster_prob = scenarios.get("strong_miss", {}).get("probability") or scenarios.get("disaster", {}).get("probability")

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO nexus.kb_earnings_analyses (
                        ticker, analysis_date, schema_version, file_path,
                        earnings_date, earnings_time, days_to_earnings,
                        recommendation, confidence, p_beat, expected_value_pct, gate_result,
                        bull_case_strength, bear_case_strength, yaml_content,
                        current_price, entry_price, stop_price, target_1_price, target_2_price,
                        bull_probability, base_probability, bear_probability, disaster_probability,
                        catalyst_score, technical_score, fundamental_score, sentiment_score,
                        total_threat_level, gate_criteria_met, risk_reward_ratio,
                        iv_rank, expected_move_pct,
                        user_id
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s
                    )
                    ON CONFLICT (file_path) DO UPDATE SET
                        recommendation = EXCLUDED.recommendation,
                        confidence = EXCLUDED.confidence,
                        yaml_content = EXCLUDED.yaml_content,
                        current_price = EXCLUDED.current_price,
                        entry_price = EXCLUDED.entry_price,
                        stop_price = EXCLUDED.stop_price,
                        target_1_price = EXCLUDED.target_1_price,
                        target_2_price = EXCLUDED.target_2_price,
                        bull_probability = EXCLUDED.bull_probability,
                        base_probability = EXCLUDED.base_probability,
                        bear_probability = EXCLUDED.bear_probability,
                        disaster_probability = EXCLUDED.disaster_probability,
                        catalyst_score = EXCLUDED.catalyst_score,
                        technical_score = EXCLUDED.technical_score,
                        fundamental_score = EXCLUDED.fundamental_score,
                        sentiment_score = EXCLUDED.sentiment_score,
                        total_threat_level = EXCLUDED.total_threat_level,
                        gate_criteria_met = EXCLUDED.gate_criteria_met,
                        risk_reward_ratio = EXCLUDED.risk_reward_ratio,
                        iv_rank = EXCLUDED.iv_rank,
                        expected_move_pct = EXCLUDED.expected_move_pct,
                        user_id = EXCLUDED.user_id,
                        updated_at = now()
                    RETURNING id
                """, [
                    ticker,
                    meta.get("created"),
                    meta.get("schema_version") or meta.get("version"),
                    file_path,
                    earnings_date,
                    earnings_time,
                    days_to_earnings,
                    decision.get("recommendation"),
                    # v2.5: confidence_pct, not just confidence
                    decision.get("confidence_pct") or decision.get("confidence"),
                    # v2.5: probability.final_probability.p_beat
                    probability.get("final_probability", {}).get("p_beat") or probability.get("p_beat"),
                    # v2.5: expected_value from scenarios section
                    decision.get("expected_value_pct") or scenarios.get("expected_value"),
                    # v2.5: gate_result at ROOT, not under decision
                    gate.get("gate_result") or gate.get("result"),
                    # v2.5: case analyses at ROOT level
                    bull_case.get("strength"),
                    bear_case.get("strength"),
                    json.dumps(data, default=str),
                    # New fields (migration 016)
                    data.get("current_price"),
                    trade.get("entry", {}).get("price") or summary.get("key_levels", {}).get("entry"),
                    trade.get("stop_loss", {}).get("price") or trade.get("stop", {}).get("price") or summary.get("key_levels", {}).get("stop"),
                    trade.get("targets", {}).get("target_1") or trade.get("target_1", {}).get("price") or summary.get("key_levels", {}).get("target_1"),
                    trade.get("targets", {}).get("target_2") or trade.get("target_2", {}).get("price") or summary.get("key_levels", {}).get("target_2"),
                    # v2.5: scenario names fixed
                    bull_prob,
                    base_prob,
                    bear_prob,
                    disaster_prob,
                    # v2.6: scoring section added (consistent with stock-analysis)
                    scoring.get("catalyst_score"),
                    scoring.get("technical_score"),
                    scoring.get("fundamental_score"),
                    scoring.get("sentiment_score"),
                    threat.get("total_threat_level") or threat.get("total_level") or threat.get("primary_concern"),
                    gate.get("gates_passed"),
                    risk_reward,
                    iv_rank,
                    expected_move_pct,
                    user_id,
                ])
                result = cur.fetchone()
                if result is None:
                    raise RuntimeError(f"Upsert returned no ID for {file_path}")
                self.conn.commit()
                return result["id"]
        except Exception as e:
            self.conn.rollback()
            log.error(f"Failed to upsert earnings analysis {file_path}: {e}")
            raise

    def get_kb_earnings_analysis(self, ticker: str, earnings_date: date = None) -> dict | None:
        """Get earnings analysis by ticker and optional earnings date."""
        with self.conn.cursor() as cur:
            if earnings_date:
                cur.execute("""
                    SELECT * FROM nexus.kb_earnings_analyses
                    WHERE ticker = %s AND earnings_date = %s
                    ORDER BY analysis_date DESC LIMIT 1
                """, [ticker.upper(), earnings_date])
            else:
                cur.execute("""
                    SELECT * FROM nexus.kb_earnings_analyses
                    WHERE ticker = %s
                    ORDER BY analysis_date DESC LIMIT 1
                """, [ticker.upper()])
            row = cur.fetchone()
        return dict(row) if row else None

    def get_latest_kb_earnings_analysis(self, ticker: str) -> dict | None:
        """Get latest earnings analysis for ticker."""
        return self.get_kb_earnings_analysis(ticker)

    # ─── KB Research Analyses ──────────────────────────────────────────────────

    def upsert_kb_research_analysis(self, file_path: str, data: dict) -> int:
        """Upsert a research analysis into kb_research_analyses. Returns ID."""
        file_path = self._validate_file_path(file_path, "research analysis")
        meta = data.get("_meta", {})

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO nexus.kb_research_analyses (
                        research_id, research_type, title, file_path, schema_version, analysis_date,
                        tickers, sectors, themes, outlook, confidence, time_horizon, yaml_content
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (file_path) DO UPDATE SET
                        outlook = EXCLUDED.outlook,
                        confidence = EXCLUDED.confidence,
                        yaml_content = EXCLUDED.yaml_content,
                        updated_at = now()
                    RETURNING id
                """, [
                    meta.get("id"),
                    meta.get("research_type", data.get("research_type")),
                    data.get("title"),
                    file_path,
                    meta.get("schema_version"),
                    meta.get("created"),
                    data.get("tickers", []),
                    data.get("sectors", []),
                    data.get("themes", []),
                    data.get("outlook"),
                    data.get("confidence"),
                    data.get("time_horizon"),
                    json.dumps(data),
                ])
                result = cur.fetchone()
                if result is None:
                    raise RuntimeError(f"Upsert returned no ID for {file_path}")
            self.conn.commit()
            return result["id"]
        except Exception as e:
            self.conn.rollback()
            log.error(f"Failed to upsert research analysis {file_path}: {e}")
            raise

    def get_kb_research_by_sector(self, sector: str) -> list[dict]:
        """Get research analyses by sector."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.kb_research_analyses
                WHERE %s = ANY(sectors)
                ORDER BY analysis_date DESC
            """, [sector])
            return [dict(r) for r in cur.fetchall()]

    # ─── KB Ticker Profiles ────────────────────────────────────────────────────

    def upsert_kb_ticker_profile(self, file_path: str, data: dict) -> int:
        """Upsert a ticker profile into kb_ticker_profiles. Returns ID."""
        file_path = self._validate_file_path(file_path, "ticker profile")
        meta = data.get("_meta", {})
        perf = data.get("performance", {})

        ticker = self._extract_ticker_from_data(data)
        ticker = self._validate_ticker(ticker, "ticker profile")

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO nexus.kb_ticker_profiles (
                        ticker, file_path, company_name, sector, industry, market_cap_category,
                        typical_iv, avg_daily_volume, options_liquidity,
                        total_trades, win_rate, avg_return, total_pnl,
                        common_biases, lessons_learned, yaml_content
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ticker) DO UPDATE SET
                        win_rate = EXCLUDED.win_rate,
                        total_pnl = EXCLUDED.total_pnl,
                        common_biases = EXCLUDED.common_biases,
                        yaml_content = EXCLUDED.yaml_content,
                        updated_at = now()
                    RETURNING id
                """, [
                    ticker,
                    file_path,
                    data.get("company_name"),
                    data.get("sector"),
                    data.get("industry"),
                    data.get("market_cap_category"),
                    data.get("typical_iv"),
                    data.get("avg_daily_volume"),
                    data.get("options_liquidity"),
                    perf.get("total_trades"),
                    perf.get("win_rate"),
                    perf.get("avg_return"),
                    perf.get("total_pnl"),
                    data.get("common_biases", []),
                    data.get("lessons_learned", []),
                    json.dumps(data),
                ])
                result = cur.fetchone()
                if result is None:
                    raise RuntimeError(f"Upsert returned no ID for {file_path}")
            self.conn.commit()
            return result["id"]
        except Exception as e:
            self.conn.rollback()
            log.error(f"Failed to upsert ticker profile {file_path}: {e}")
            raise

    def get_kb_ticker_profile(self, ticker: str) -> dict | None:
        """Get ticker profile."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.kb_ticker_profiles WHERE ticker = %s
            """, [ticker.upper()])
            row = cur.fetchone()
        return dict(row) if row else None

    # ─── KB Trade Journals ─────────────────────────────────────────────────────

    def upsert_kb_trade_journal(self, file_path: str, data: dict, user_id: int = 1) -> int:
        """Upsert a trade journal into kb_trade_journals. Returns ID."""
        file_path = self._validate_file_path(file_path, "trade journal")
        meta = data.get("_meta", {})
        execution = data.get("execution", {})
        trade = data.get("trade", {})
        result = data.get("result", {})
        quality = data.get("quality", {})

        # Extract ticker from root level or meta
        ticker = self._extract_ticker_from_data(data)
        ticker = self._validate_ticker(ticker, "trade journal")

        # Extract trade_id from meta.id
        trade_id = meta.get("trade_id", meta.get("id"))
        if not trade_id:
            raise ValueError(f"trade_id is required for trade journal {file_path}")

        # Extract entry/exit from execution or trade section
        entries = execution.get("entries", trade.get("entries", []))
        exits = execution.get("exits", trade.get("exits", []))
        direction = execution.get("direction") or trade.get("direction")

        entry_date = entries[0].get("date") if entries else trade.get("entry_date")
        entry_price = entries[0].get("price") if entries else trade.get("entry_price")
        exit_date = exits[-1].get("date") if exits else trade.get("exit_date")
        exit_price = exits[-1].get("price") if exits else trade.get("exit_price")

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO nexus.kb_trade_journals (
                        trade_id, ticker, file_path, source_analysis_type,
                        direction, entry_date, entry_price, exit_date, exit_price,
                        outcome, return_pct, pnl_dollars, holding_days,
                        entry_grade, exit_grade, overall_grade,
                        biases_detected, primary_lesson, yaml_content, user_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (trade_id) DO UPDATE SET
                        outcome = EXCLUDED.outcome,
                        return_pct = EXCLUDED.return_pct,
                        pnl_dollars = EXCLUDED.pnl_dollars,
                        overall_grade = EXCLUDED.overall_grade,
                        biases_detected = EXCLUDED.biases_detected,
                        yaml_content = EXCLUDED.yaml_content,
                        user_id = EXCLUDED.user_id,
                        updated_at = now()
                    RETURNING id
                """, [
                    trade_id,
                    ticker,
                    file_path,
                    data.get("source_analysis_type") or data.get("catalyst"),
                    direction,
                    entry_date,
                    entry_price,
                    exit_date,
                    exit_price,
                    result.get("outcome"),
                    result.get("return_pct"),
                    result.get("pnl_dollars"),
                    result.get("holding_days"),
                    quality.get("entry_grade"),
                    quality.get("exit_grade"),
                    quality.get("overall_grade"),
                    data.get("biases_detected", []),
                    data.get("primary_lesson"),
                    json.dumps(data),
                    user_id,
                ])
                result_row = cur.fetchone()
                if result_row is None:
                    raise RuntimeError(f"Upsert returned no ID for {file_path}")
            self.conn.commit()
            return result_row["id"]
        except Exception as e:
            self.conn.rollback()
            log.error(f"Failed to upsert trade journal {file_path}: {e}")
            raise

    def get_kb_trade_journal(self, trade_id: str) -> dict | None:
        """Get trade journal by trade_id."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.kb_trade_journals WHERE trade_id = %s
            """, [trade_id])
            row = cur.fetchone()
        return dict(row) if row else None

    def get_kb_trades_by_ticker(self, ticker: str) -> list[dict]:
        """Get trade journals by ticker."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.kb_trade_journals
                WHERE ticker = %s
                ORDER BY entry_date DESC
            """, [ticker.upper()])
            return [dict(r) for r in cur.fetchall()]

    def get_kb_trade_performance(self, ticker: str = None) -> dict:
        """Get trade performance summary from view."""
        with self.conn.cursor() as cur:
            if ticker:
                cur.execute("""
                    SELECT * FROM nexus.v_trade_performance WHERE ticker = %s
                """, [ticker.upper()])
                row = cur.fetchone()
                return dict(row) if row else {}
            else:
                cur.execute("SELECT * FROM nexus.v_trade_performance")
                return [dict(r) for r in cur.fetchall()]

    # ─── KB Watchlist Entries ──────────────────────────────────────────────────

    def upsert_kb_watchlist_entry(self, file_path: str, data: dict, user_id: int = 1) -> int:
        """Upsert a watchlist entry into kb_watchlist_entries. Returns ID."""
        file_path = self._validate_file_path(file_path, "watchlist entry")
        meta = data.get("_meta", {})

        ticker = self._extract_ticker_from_data(data)
        ticker = self._validate_ticker(ticker, "watchlist entry")

        watchlist_id = meta.get("watchlist_id", meta.get("id"))
        if not watchlist_id:
            raise ValueError(f"watchlist_id is required for watchlist entry {file_path}")

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO nexus.kb_watchlist_entries (
                        watchlist_id, ticker, file_path, entry_trigger, entry_price,
                        status, priority, conviction_level, expires_at,
                        source_analysis, source_score, yaml_content, user_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (watchlist_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        entry_trigger = EXCLUDED.entry_trigger,
                        yaml_content = EXCLUDED.yaml_content,
                        user_id = EXCLUDED.user_id,
                        updated_at = now()
                    RETURNING id
                """, [
                    watchlist_id,
                    ticker,
                    file_path,
                    data.get("entry_trigger"),
                    data.get("entry_price"),
                    data.get("status", "active"),
                    data.get("priority"),
                    data.get("conviction_level"),
                    data.get("expires_at") or meta.get("expires"),
                    data.get("source_analysis"),
                    data.get("source_score"),
                    json.dumps(data),
                    user_id,
                ])
                result = cur.fetchone()
                if result is None:
                    raise RuntimeError(f"Upsert returned no ID for {file_path}")
            self.conn.commit()
            return result["id"]
        except Exception as e:
            self.conn.rollback()
            log.error(f"Failed to upsert watchlist entry {file_path}: {e}")
            raise

    def get_kb_active_watchlist(self) -> list[dict]:
        """Get active watchlist entries from view."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.v_kb_active_watchlist")
            return [dict(r) for r in cur.fetchall()]

    def update_kb_watchlist_status(self, watchlist_id: str, status: str) -> bool:
        """Update watchlist entry status."""
        timestamp_field = {
            "triggered": "triggered_at",
            "invalidated": "invalidated_at",
        }.get(status)

        with self.conn.cursor() as cur:
            if timestamp_field:
                cur.execute(f"""
                    UPDATE nexus.kb_watchlist_entries
                    SET status = %s, {timestamp_field} = now(), updated_at = now()
                    WHERE watchlist_id = %s
                    RETURNING id
                """, [status, watchlist_id])
            else:
                cur.execute("""
                    UPDATE nexus.kb_watchlist_entries
                    SET status = %s, updated_at = now()
                    WHERE watchlist_id = %s
                    RETURNING id
                """, [status, watchlist_id])
            updated = cur.fetchone() is not None
        self.conn.commit()
        return updated

    # ─── KB Reviews ────────────────────────────────────────────────────────────

    def upsert_kb_review(self, file_path: str, data: dict) -> int:
        """Upsert a review into kb_reviews. Returns ID."""
        file_path = self._validate_file_path(file_path, "review")
        meta = data.get("_meta", {})
        result = data.get("result", {})
        thesis_accuracy = data.get("thesis_accuracy", {})
        trade = data.get("trade", {})

        # Extract ticker from multiple possible locations
        ticker = self._extract_ticker_from_data(data)
        ticker = self._validate_ticker(ticker, "review")

        # Extract review_id from meta.id
        review_id = meta.get("review_id", meta.get("id"))
        if not review_id:
            raise ValueError(f"review_id is required for review {file_path}")

        # Extract grade from thesis_accuracy or result section
        overall_grade = thesis_accuracy.get("grade") or result.get("overall_grade") or data.get("overall_grade")

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO nexus.kb_reviews (
                        review_id, review_type, ticker, file_path,
                        overall_grade, return_pct, outcome, validation_result,
                        primary_lesson, biases_detected, bias_cost_estimate, yaml_content
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (review_id) DO UPDATE SET
                        overall_grade = EXCLUDED.overall_grade,
                        validation_result = EXCLUDED.validation_result,
                        yaml_content = EXCLUDED.yaml_content,
                        updated_at = now()
                    RETURNING id
                """, [
                    review_id,
                    meta.get("type", meta.get("review_type")),
                    ticker,
                    file_path,
                    overall_grade,
                    result.get("return_pct"),
                    result.get("outcome"),
                    data.get("validation_result"),
                    data.get("primary_lesson"),
                    data.get("biases_detected", []),
                    data.get("bias_cost_estimate"),
                    json.dumps(data),
                ])
                result_row = cur.fetchone()
                if result_row is None:
                    raise RuntimeError(f"Upsert returned no ID for {file_path}")
            self.conn.commit()
            return result_row["id"]
        except Exception as e:
            self.conn.rollback()
            log.error(f"Failed to upsert review {file_path}: {e}")
            raise

    def get_kb_reviews_by_ticker(self, ticker: str) -> list[dict]:
        """Get reviews by ticker."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.kb_reviews
                WHERE ticker = %s
                ORDER BY created_at DESC
            """, [ticker.upper()])
            return [dict(r) for r in cur.fetchall()]

    def get_kb_reviews_by_type(self, review_type: str) -> list[dict]:
        """Get reviews by type."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.kb_reviews
                WHERE review_type = %s
                ORDER BY created_at DESC
            """, [review_type])
            return [dict(r) for r in cur.fetchall()]

    # ─── KB Earnings Results ───────────────────────────────────────────────────

    def upsert_kb_earnings_result(self, ticker: str, earnings_date, data: dict, source_review_id: int = None) -> int:
        """Upsert an earnings result into kb_earnings_results. Returns ID."""
        ticker = self._validate_ticker(ticker, "earnings result")

        # Extract data with fallbacks
        eps = data.get("eps", {})
        revenue = data.get("revenue", {})
        guidance_data = data.get("guidance", {}) if isinstance(data.get("guidance"), dict) else {}
        key_metric = data.get("key_metric", {})
        reaction = data.get("stock_reaction", {})

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO nexus.kb_earnings_results (
                        ticker, earnings_date, earnings_time, fiscal_quarter, fiscal_year,
                        eps_actual, eps_consensus, eps_whisper, eps_surprise_pct,
                        revenue_actual, revenue_consensus, revenue_surprise_pct,
                        eps_yoy_growth_pct, revenue_yoy_growth_pct,
                        guidance, guidance_details,
                        key_metric_name, key_metric_actual, key_metric_consensus, key_metric_surprise_pct,
                        price_before, day1_move_pct, week1_move_pct, gap_direction, day1_direction, reaction_notes,
                        data_source, data_timestamp, source_review_id, yaml_content
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (ticker, earnings_date) DO UPDATE SET
                        eps_actual = EXCLUDED.eps_actual,
                        eps_consensus = EXCLUDED.eps_consensus,
                        eps_whisper = EXCLUDED.eps_whisper,
                        eps_surprise_pct = EXCLUDED.eps_surprise_pct,
                        revenue_actual = EXCLUDED.revenue_actual,
                        revenue_consensus = EXCLUDED.revenue_consensus,
                        revenue_surprise_pct = EXCLUDED.revenue_surprise_pct,
                        guidance = EXCLUDED.guidance,
                        guidance_details = EXCLUDED.guidance_details,
                        day1_move_pct = EXCLUDED.day1_move_pct,
                        week1_move_pct = EXCLUDED.week1_move_pct,
                        gap_direction = EXCLUDED.gap_direction,
                        day1_direction = EXCLUDED.day1_direction,
                        reaction_notes = EXCLUDED.reaction_notes,
                        yaml_content = EXCLUDED.yaml_content,
                        updated_at = now()
                    RETURNING id
                """, [
                    ticker,
                    earnings_date,
                    data.get("earnings_time"),
                    data.get("fiscal_quarter"),
                    data.get("fiscal_year"),
                    eps.get("actual"),
                    eps.get("consensus"),
                    eps.get("whisper"),
                    eps.get("surprise_pct"),
                    revenue.get("actual") or (revenue.get("actual_b", 0) * 1000 if revenue.get("actual_b") else None),
                    revenue.get("consensus") or (revenue.get("consensus_b", 0) * 1000 if revenue.get("consensus_b") else None),
                    revenue.get("surprise_pct"),
                    data.get("eps_yoy_growth_pct"),
                    data.get("yoy_growth_pct") or data.get("revenue_yoy_growth_pct"),
                    data.get("guidance") if isinstance(data.get("guidance"), str) else guidance_data.get("direction"),
                    data.get("guidance_details") or guidance_data.get("details"),
                    key_metric.get("name"),
                    key_metric.get("actual"),
                    key_metric.get("consensus"),
                    key_metric.get("surprise_pct"),
                    reaction.get("price_before") or reaction.get("intraday_low"),
                    reaction.get("day1_move_pct"),
                    reaction.get("week1_move_pct"),
                    reaction.get("gap_direction"),
                    reaction.get("day1_direction"),
                    reaction.get("reaction_notes"),
                    data.get("data_source"),
                    data.get("data_timestamp"),
                    source_review_id,
                    json.dumps(data, default=str),
                ])
                result = cur.fetchone()
                if result is None:
                    raise RuntimeError(f"Upsert returned no ID for {ticker} {earnings_date}")
            self.conn.commit()
            return result["id"]
        except Exception as e:
            self.conn.rollback()
            log.error(f"Failed to upsert earnings result {ticker} {earnings_date}: {e}")
            raise

    def get_kb_earnings_result(self, ticker: str, earnings_date=None) -> dict | None:
        """Get earnings result by ticker and optional date."""
        with self.conn.cursor() as cur:
            if earnings_date:
                cur.execute("""
                    SELECT * FROM nexus.kb_earnings_results
                    WHERE ticker = %s AND earnings_date = %s
                """, [ticker.upper(), earnings_date])
            else:
                cur.execute("""
                    SELECT * FROM nexus.kb_earnings_results
                    WHERE ticker = %s
                    ORDER BY earnings_date DESC LIMIT 1
                """, [ticker.upper()])
            row = cur.fetchone()
        return dict(row) if row else None

    def get_ticker_earnings_history(self, ticker: str) -> list[dict]:
        """Get all earnings results for a ticker."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.kb_earnings_results
                WHERE ticker = %s
                ORDER BY earnings_date DESC
            """, [ticker.upper()])
            return [dict(r) for r in cur.fetchall()]

    def get_earnings_surprises(self, limit: int = 20) -> list[dict]:
        """Get recent earnings surprises with reaction classification."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.v_earnings_surprises
                LIMIT %s
            """, [limit])
            return [dict(r) for r in cur.fetchall()]

    # ─── KB Learnings ──────────────────────────────────────────────────────────

    def upsert_kb_learning(self, file_path: str, data: dict) -> int:
        """Upsert a learning into kb_learnings. Returns ID."""
        file_path = self._validate_file_path(file_path, "learning")
        meta = data.get("_meta", {})
        pattern = data.get("pattern", {})
        countermeasure = data.get("countermeasure", {})
        evidence = data.get("evidence", {})
        validation = data.get("validation", {})

        learning_id = meta.get("learning_id", meta.get("id"))
        if not learning_id:
            raise ValueError(f"learning_id is required for learning {file_path}")

        # Extract fields with fallbacks for different schema versions
        description = pattern.get("description") or data.get("description")
        rule_statement = countermeasure.get("rule") or data.get("rule_statement")
        countermeasure_text = countermeasure.get("mantra") or countermeasure.get("checklist_addition")
        evidence_count = evidence.get("occurrences") or data.get("evidence_count")
        estimated_cost = evidence.get("estimated_cost") or data.get("estimated_cost")
        related_trades = evidence.get("source_trades", []) or data.get("related_trades", [])

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO nexus.kb_learnings (
                        learning_id, category, subcategory, file_path,
                        title, description, rule_statement, countermeasure,
                        confidence, validation_status, evidence_count, estimated_cost,
                        related_tickers, related_trades, yaml_content
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (learning_id) DO UPDATE SET
                        validation_status = EXCLUDED.validation_status,
                        evidence_count = EXCLUDED.evidence_count,
                        yaml_content = EXCLUDED.yaml_content,
                        updated_at = now()
                    RETURNING id
                """, [
                    learning_id,
                    meta.get("category", data.get("category")),
                    meta.get("subcategory", data.get("subcategory")),
                    file_path,
                    data.get("title"),
                    description,
                    rule_statement,
                    countermeasure_text,
                    meta.get("confidence") or data.get("confidence"),
                    validation.get("status") or data.get("validation_status", "pending"),
                    evidence_count,
                    estimated_cost,
                    data.get("related_tickers", []),
                    related_trades,
                    json.dumps(data),
                ])
                result = cur.fetchone()
                if result is None:
                    raise RuntimeError(f"Upsert returned no ID for {file_path}")
            self.conn.commit()
            return result["id"]
        except Exception as e:
            self.conn.rollback()
            log.error(f"Failed to upsert learning {file_path}: {e}")
            raise

    def get_kb_learnings_by_category(self, category: str) -> list[dict]:
        """Get learnings by category."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.kb_learnings
                WHERE category = %s
                ORDER BY created_at DESC
            """, [category])
            return [dict(r) for r in cur.fetchall()]

    def get_kb_bias_frequency(self) -> list[dict]:
        """Get bias frequency from view."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.v_bias_frequency")
            return [dict(r) for r in cur.fetchall()]

    # ─── KB Strategies ─────────────────────────────────────────────────────────

    def upsert_kb_strategy(self, file_path: str, data: dict) -> int:
        """Upsert a strategy into kb_strategies. Returns ID."""
        file_path = self._validate_file_path(file_path, "strategy")
        meta = data.get("_meta", {})
        perf = data.get("performance", {})
        overview = data.get("overview", {})
        entry_rules = data.get("entry_rules", {})
        exit_rules = data.get("exit_rules", {})

        strategy_id = meta.get("strategy_id", meta.get("id"))
        if not strategy_id:
            raise ValueError(f"strategy_id is required for strategy {file_path}")

        # Extract entry/exit conditions as TEXT[] arrays
        # Convert list of condition dicts to list of condition strings
        entry_conditions_raw = entry_rules.get("criteria", []) if isinstance(entry_rules, dict) else entry_rules
        exit_conditions_raw = exit_rules.get("profit_taking", []) if isinstance(exit_rules, dict) else exit_rules

        # Convert dicts to strings for TEXT[] array
        if entry_conditions_raw and isinstance(entry_conditions_raw[0], dict):
            entry_conditions = [c.get("condition", str(c)) for c in entry_conditions_raw]
        else:
            entry_conditions = entry_conditions_raw or []

        if exit_conditions_raw and isinstance(exit_conditions_raw[0], dict):
            exit_conditions = [c.get("trigger", str(c)) for c in exit_conditions_raw]
        else:
            exit_conditions = exit_conditions_raw or []

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO nexus.kb_strategies (
                        strategy_id, strategy_name, file_path, schema_version,
                        strategy_type, asset_class, time_horizon,
                        total_trades, win_rate, avg_return, max_drawdown, sharpe_ratio, total_pnl,
                        status, confidence_level, last_reviewed,
                        entry_conditions, exit_conditions, known_weaknesses, yaml_content
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (strategy_id) DO UPDATE SET
                        win_rate = EXCLUDED.win_rate,
                        total_pnl = EXCLUDED.total_pnl,
                        status = EXCLUDED.status,
                        yaml_content = EXCLUDED.yaml_content,
                        updated_at = now()
                    RETURNING id
                """, [
                    strategy_id,
                    data.get("strategy_name", data.get("name")),
                    file_path,
                    meta.get("schema_version") or meta.get("version"),
                    data.get("strategy_type") or data.get("category"),
                    data.get("asset_class"),
                    data.get("time_horizon"),
                    perf.get("total_trades"),
                    perf.get("win_rate"),
                    perf.get("avg_return"),
                    perf.get("max_drawdown"),
                    perf.get("sharpe_ratio"),
                    perf.get("total_pnl"),
                    meta.get("status") or data.get("status", "active"),
                    data.get("confidence_level"),
                    data.get("last_reviewed"),
                    entry_conditions,
                    exit_conditions,
                    overview.get("avoid_when", data.get("known_weaknesses", [])),
                    json.dumps(data),
                ])
                result = cur.fetchone()
                if result is None:
                    raise RuntimeError(f"Upsert returned no ID for {file_path}")
            self.conn.commit()
            return result["id"]
        except Exception as e:
            self.conn.rollback()
            log.error(f"Failed to upsert strategy {file_path}: {e}")
            raise

    def get_kb_strategy(self, strategy_id: str) -> dict | None:
        """Get strategy by ID."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.kb_strategies WHERE strategy_id = %s
            """, [strategy_id])
            row = cur.fetchone()
        return dict(row) if row else None

    def get_kb_active_strategies(self) -> list[dict]:
        """Get active strategies from view."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.v_active_strategies")
            return [dict(r) for r in cur.fetchall()]

    def update_kb_strategy_performance(self, strategy_id: str, stats: dict) -> bool:
        """Update strategy performance stats."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.kb_strategies SET
                    total_trades = COALESCE(%s, total_trades),
                    win_rate = COALESCE(%s, win_rate),
                    avg_return = COALESCE(%s, avg_return),
                    total_pnl = COALESCE(%s, total_pnl),
                    updated_at = now()
                WHERE strategy_id = %s
                RETURNING id
            """, [
                stats.get("total_trades"),
                stats.get("win_rate"),
                stats.get("avg_return"),
                stats.get("total_pnl"),
                strategy_id,
            ])
            updated = cur.fetchone() is not None
        self.conn.commit()
        return updated

    # ─── KB Scanner Configs ────────────────────────────────────────────────────

    def upsert_kb_scanner_config(self, file_path: str, data: dict) -> int:
        """Upsert a scanner config into kb_scanner_configs. Returns ID."""
        file_path = self._validate_file_path(file_path, "scanner config")
        meta = data.get("_meta", {})
        config = data.get("scanner_config", data)
        schedule = config.get("schedule", data.get("schedule", {}))
        scoring = data.get("scoring", {})

        # Extract scanner_code from meta.id (e.g., "SCANNER-EARNINGS-MOMENTUM-001")
        scanner_code = meta.get("id") or meta.get("scanner_code") or config.get("code")
        if not scanner_code:
            raise ValueError(f"scanner_code is required for scanner config {file_path}")

        # Extract scanner_type from run_frequency or infer from file path
        scanner_type = meta.get("run_frequency") or meta.get("scanner_type")
        if not scanner_type:
            # Try to infer from file path (e.g., /scanners/daily/xxx.yaml)
            if "/daily/" in file_path:
                scanner_type = "daily"
            elif "/intraday/" in file_path:
                scanner_type = "intraday"
            elif "/weekly/" in file_path:
                scanner_type = "weekly"
            else:
                scanner_type = "daily"  # Default

        # Handle schedule_time - could be single value or array, take first
        schedule_time = schedule.get("run_at", schedule.get("time"))
        if isinstance(schedule_time, list):
            schedule_time = schedule_time[0] if schedule_time else None

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO nexus.kb_scanner_configs (
                        scanner_code, scanner_name, file_path, schema_version,
                        scanner_type, category, schedule_time, schedule_days, is_enabled,
                        data_sources, max_candidates, min_score, filters_summary,
                        scoring_criteria, yaml_content
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (scanner_code) DO UPDATE SET
                        is_enabled = EXCLUDED.is_enabled,
                        scoring_criteria = EXCLUDED.scoring_criteria,
                        yaml_content = EXCLUDED.yaml_content,
                        updated_at = now()
                    RETURNING id
                """, [
                    scanner_code,
                    config.get("name", data.get("name")),
                    file_path,
                    meta.get("schema_version") or meta.get("version"),
                    scanner_type,
                    config.get("category"),
                    schedule_time,
                    schedule.get("run_days", schedule.get("days", [])),
                    config.get("is_enabled", meta.get("status") == "active"),
                    data.get("data_sources", []),
                    config.get("limits", {}).get("max_results", config.get("max_candidates")),
                    config.get("min_score"),
                    data.get("filters_summary"),
                    json.dumps(scoring) if scoring else None,
                    json.dumps(data),
                ])
                result = cur.fetchone()
                if result is None:
                    raise RuntimeError(f"Upsert returned no ID for {file_path}")
            self.conn.commit()
            return result["id"]
        except Exception as e:
            self.conn.rollback()
            log.error(f"Failed to upsert scanner config {file_path}: {e}")
            raise

    def get_kb_scanner_config(self, scanner_code: str) -> dict | None:
        """Get scanner config by code."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.kb_scanner_configs WHERE scanner_code = %s
            """, [scanner_code])
            row = cur.fetchone()
        return dict(row) if row else None

    def get_kb_enabled_scanners(self, scanner_type: str = None) -> list[dict]:
        """Get enabled scanners, optionally filtered by type."""
        with self.conn.cursor() as cur:
            if scanner_type:
                cur.execute("""
                    SELECT * FROM nexus.kb_scanner_configs
                    WHERE is_enabled = true AND scanner_type = %s
                    ORDER BY schedule_time
                """, [scanner_type])
            else:
                cur.execute("""
                    SELECT * FROM nexus.v_enabled_scanners
                """)
            return [dict(r) for r in cur.fetchall()]

    def update_kb_scanner_stats(self, scanner_code: str, candidates_count: int) -> bool:
        """Update scanner run statistics."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.kb_scanner_configs SET
                    total_runs = total_runs + 1,
                    avg_candidates = (COALESCE(avg_candidates, 0) * total_runs + %s) / (total_runs + 1),
                    last_run_at = now(),
                    updated_at = now()
                WHERE scanner_code = %s
                RETURNING id
            """, [candidates_count, scanner_code])
            updated = cur.fetchone() is not None
        self.conn.commit()
        return updated

    # ─── KB Scanner Runs ──────────────────────────────────────────────────────

    def upsert_kb_scanner_run(self, data: dict) -> int:
        """Insert a scanner run result into kb_scanner_runs. Returns ID.

        Args:
            data: Scanner run data with fields:
                - run_id: Unique run identifier
                - scanner_name: Scanner code/name
                - scanner_config_id: Optional FK to kb_scanner_configs
                - file_path: Optional path to saved YAML file
                - run_timestamp: When the scan was executed
                - schedule_type: daily, intraday, weekly
                - market_phase: premarket, open, mid_day, close, after_hours
                - market_regime: bull, bear, neutral, high_volatility
                - vix_level: Current VIX
                - spy_change_pct: SPY % change
                - universe_size: Total candidates scanned
                - passed_quality_filters: After quality filter
                - passed_liquidity_filters: After liquidity filter
                - scored_candidates: Total scored
                - high_score_count: Score >= 7.5
                - watchlist_count: Score 5.5-7.4
                - skipped_count: Score < 5.5
                - top_candidate_ticker: Best candidate ticker
                - top_candidate_score: Best candidate score
                - top_candidate_action: Action taken (analyze, watch)
                - candidates: Full list of candidates (stored in yaml_content)
        """
        run_id = data.get("run_id") or f"{data.get('scanner_name', 'UNKNOWN')}_{datetime.now(ET).strftime('%Y%m%dT%H%M%S')}"

        # Parse run_timestamp
        run_ts = data.get("run_timestamp")
        if isinstance(run_ts, str):
            try:
                run_ts = datetime.fromisoformat(run_ts.replace("Z", "+00:00"))
            except ValueError:
                run_ts = datetime.now(ET)
        elif run_ts is None:
            run_ts = datetime.now(ET)

        # Get top candidate from candidates list if not provided
        top_ticker = data.get("top_candidate_ticker")
        top_score = data.get("top_candidate_score")
        top_action = data.get("top_candidate_action")

        candidates = data.get("candidates", [])
        if candidates and not top_ticker:
            # Sort by score descending and get first
            sorted_candidates = sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)
            if sorted_candidates:
                top = sorted_candidates[0]
                top_ticker = top.get("ticker")
                top_score = top.get("score")
                top_action = top.get("action", "analyze" if (top.get("score") or 0) >= 7.5 else "watch")

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO nexus.kb_scanner_runs (
                        run_id, scanner_name, scanner_config_id, file_path,
                        run_timestamp, schedule_type, market_phase,
                        market_regime, vix_level, spy_change_pct,
                        universe_size, passed_quality_filters, passed_liquidity_filters,
                        scored_candidates, high_score_count, watchlist_count, skipped_count,
                        top_candidate_ticker, top_candidate_score, top_candidate_action,
                        yaml_content
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (scanner_name, run_timestamp) DO UPDATE SET
                        yaml_content = EXCLUDED.yaml_content,
                        high_score_count = EXCLUDED.high_score_count,
                        watchlist_count = EXCLUDED.watchlist_count
                    RETURNING id
                """, [
                    run_id,
                    data.get("scanner_name"),
                    data.get("scanner_config_id"),
                    data.get("file_path"),
                    run_ts,
                    data.get("schedule_type"),
                    data.get("market_phase"),
                    data.get("market_regime"),
                    data.get("vix_level"),
                    data.get("spy_change_pct"),
                    data.get("universe_size"),
                    data.get("passed_quality_filters"),
                    data.get("passed_liquidity_filters"),
                    data.get("scored_candidates") or len(candidates),
                    data.get("high_score_count") or len([c for c in candidates if (c.get("score") or 0) >= 7.5]),
                    data.get("watchlist_count") or len([c for c in candidates if 5.5 <= (c.get("score") or 0) < 7.5]),
                    data.get("skipped_count") or len([c for c in candidates if (c.get("score") or 0) < 5.5]),
                    top_ticker,
                    top_score,
                    top_action,
                    json.dumps(data),
                ])
                result = cur.fetchone()
                if result is None:
                    raise RuntimeError(f"Upsert scanner run returned no ID for {run_id}")
            self.conn.commit()
            return result["id"]
        except Exception as e:
            self.conn.rollback()
            log.error(f"Failed to upsert scanner run {run_id}: {e}")
            raise

    def get_kb_scanner_runs(
        self,
        scanner_name: str = None,
        market_regime: str = None,
        since: datetime = None,
        limit: int = 20
    ) -> list[dict]:
        """Get scanner runs with optional filters."""
        conditions = []
        params = []

        if scanner_name:
            conditions.append("scanner_name = %s")
            params.append(scanner_name)
        if market_regime:
            conditions.append("market_regime = %s")
            params.append(market_regime)
        if since:
            conditions.append("run_timestamp >= %s")
            params.append(since)

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)

        with self.conn.cursor() as cur:
            cur.execute(f"""
                SELECT * FROM nexus.kb_scanner_runs
                {where_clause}
                ORDER BY run_timestamp DESC
                LIMIT %s
            """, params)
            return [dict(r) for r in cur.fetchall()]

    # ─── KB Price History ─────────────────────────────────────────────────────

    def upsert_kb_price_history(
        self,
        ticker: str,
        price_date: date,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
        volume: int,
        adj_close: float = None,
        source: str = "ib_mcp"
    ) -> int:
        """Insert or update a price bar. Returns ID.

        Args:
            ticker: Stock symbol
            price_date: Date of the price bar
            open_price: Opening price
            high_price: High price
            low_price: Low price
            close_price: Closing price
            volume: Trading volume
            adj_close: Adjusted close (optional)
            source: Data source (ib_mcp, yahoo, polygon)
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO nexus.kb_price_history (
                        ticker, price_date, open_price, high_price, low_price,
                        close_price, adj_close, volume, data_source
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ticker, price_date) DO UPDATE SET
                        open_price = EXCLUDED.open_price,
                        high_price = EXCLUDED.high_price,
                        low_price = EXCLUDED.low_price,
                        close_price = EXCLUDED.close_price,
                        adj_close = EXCLUDED.adj_close,
                        volume = EXCLUDED.volume,
                        data_source = EXCLUDED.data_source
                    RETURNING id
                """, [ticker, price_date, open_price, high_price, low_price, close_price, adj_close, volume, source])
                result = cur.fetchone()
            self.conn.commit()
            return result["id"] if result else None
        except Exception as e:
            self.conn.rollback()
            log.error(f"Failed to upsert price history for {ticker} {price_date}: {e}")
            raise

    def bulk_upsert_kb_price_history(
        self,
        ticker: str,
        bars: list[dict],
        source: str = "ib_mcp"
    ) -> int:
        """Bulk insert price bars. Returns count inserted.

        Args:
            ticker: Stock symbol
            bars: List of dicts with keys: date, open, high, low, close, volume, adj_close (optional)
            source: Data source (ib_mcp, yahoo, polygon)
        """
        if not bars:
            return 0

        try:
            with self.conn.cursor() as cur:
                # Use executemany for bulk insert
                values = [
                    (
                        ticker,
                        bar.get("date"),
                        bar.get("open"),
                        bar.get("high"),
                        bar.get("low"),
                        bar.get("close"),
                        bar.get("adj_close"),
                        bar.get("volume"),
                        source
                    )
                    for bar in bars
                ]
                cur.executemany("""
                    INSERT INTO nexus.kb_price_history (
                        ticker, price_date, open_price, high_price, low_price,
                        close_price, adj_close, volume, data_source
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ticker, price_date) DO UPDATE SET
                        open_price = EXCLUDED.open_price,
                        high_price = EXCLUDED.high_price,
                        low_price = EXCLUDED.low_price,
                        close_price = EXCLUDED.close_price,
                        adj_close = EXCLUDED.adj_close,
                        volume = EXCLUDED.volume,
                        data_source = EXCLUDED.data_source
                """, values)
            self.conn.commit()
            return len(bars)
        except Exception as e:
            self.conn.rollback()
            log.error(f"Failed to bulk upsert price history for {ticker}: {e}")
            raise

    def get_kb_price_history(
        self,
        ticker: str,
        start_date: date = None,
        end_date: date = None,
        limit: int = 100
    ) -> list[dict]:
        """Get price history for a ticker."""
        conditions = ["ticker = %s"]
        params = [ticker]

        if start_date:
            conditions.append("price_date >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("price_date <= %s")
            params.append(end_date)

        params.append(limit)

        with self.conn.cursor() as cur:
            cur.execute(f"""
                SELECT * FROM nexus.kb_price_history
                WHERE {' AND '.join(conditions)}
                ORDER BY price_date DESC
                LIMIT %s
            """, params)
            return [dict(r) for r in cur.fetchall()]
