"""
Nexus Light - Database Layer
Async PostgreSQL access for stocks, scanners, schedules, and run history.

Uses psycopg3 (async) for connection pooling and typed queries.
Falls back to psycopg2 sync if async not available.
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

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
        f"dbname={os.getenv('PG_DB', 'lightrag')} "
        f"user={os.getenv('PG_USER', 'lightrag')} "
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
        candidates_found: int = 0,
        error: str | None = None,
    ):
        """Complete a scanner run with results."""
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
                [status, json.dumps({"candidates_found": candidates_found}), error, run_id],
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
        """Get a single setting value (parsed from JSONB)."""
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

    def ensure_connection(self):
        """Reconnect if the connection is dead. Call before each tick."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
        except Exception:
            log.warning("DB connection lost — reconnecting")
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
            self.connect()

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

    def get_watchlist_entry(self, ticker: str) -> dict | None:
        """Get active watchlist entry for ticker."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM nexus.watchlist WHERE ticker = %s AND status = 'active' ORDER BY created_at DESC LIMIT 1",
                [ticker.upper()]
            )
            row = cur.fetchone()
        return dict(row) if row else None

    def get_active_watchlist(self) -> list[dict]:
        """Get all active watchlist entries."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM nexus.watchlist WHERE status = 'active' ORDER BY priority DESC, created_at DESC"
            )
            return [dict(r) for r in cur.fetchall()]

    def add_watchlist_entry(self, entry: dict) -> int:
        """Add new watchlist entry. Returns entry ID."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.watchlist (ticker, entry_trigger, entry_price,
                    invalidation, invalidation_price, expires_at, priority, source, source_analysis, notes)
                VALUES (%(ticker)s, %(entry_trigger)s, %(entry_price)s,
                    %(invalidation)s, %(invalidation_price)s, %(expires_at)s,
                    %(priority)s, %(source)s, %(source_analysis)s, %(notes)s)
                RETURNING id
            """, {
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
                  AND expires_at < now() + make_interval(hours => %s)
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
                    next_retry_at = now() + make_interval(mins => %s * power(2, retry_count)),
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
                  AND started_at < now() - make_interval(mins => %s)
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
