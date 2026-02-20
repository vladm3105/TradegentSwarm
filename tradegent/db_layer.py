"""
Nexus Light - Database Layer
Async PostgreSQL access for stocks, scanners, schedules, and run history.

Uses psycopg3 (async) for connection pooling and typed queries.
Falls back to psycopg2 sync if async not available.
"""

import os
import json
import logging
from datetime import datetime, date, time, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional, Any
from enum import Enum
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

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
    name: Optional[str]
    sector: Optional[str]
    is_enabled: bool
    state: str  # analysis, paper, live
    default_analysis_type: str
    priority: int
    next_earnings_date: Optional[date]
    earnings_confirmed: bool
    beat_history: Optional[str]
    has_open_position: bool
    position_state: Optional[str]
    max_position_pct: float
    comments: Optional[str]
    tags: list[str]

    @property
    def can_trade(self) -> bool:
        return self.state in ('paper', 'live') and self.is_enabled

    @property
    def days_to_earnings(self) -> Optional[int]:
        if self.next_earnings_date:
            return (self.next_earnings_date - date.today()).days
        return None


@dataclass
class IBScanner:
    id: int
    scanner_code: str
    display_name: str
    description: Optional[str]
    is_enabled: bool
    instrument: str
    location: str
    num_results: int
    filters: dict
    auto_add_to_watchlist: bool
    auto_analyze: bool
    analysis_type: str
    max_candidates: int
    comments: Optional[str]


@dataclass
class Schedule:
    id: int
    name: str
    description: Optional[str]
    is_enabled: bool
    task_type: str
    target_ticker: Optional[str]
    target_scanner_id: Optional[int]
    target_tags: Optional[list[str]]
    analysis_type: str
    auto_execute: bool
    custom_prompt: Optional[str]
    frequency: str
    time_of_day: Optional[time]
    day_of_week: Optional[str]
    interval_minutes: Optional[int]
    days_before_earnings: Optional[int]
    days_after_earnings: Optional[int]
    market_hours_only: bool
    trading_days_only: bool
    max_runs_per_day: int
    timeout_seconds: int
    priority: int
    last_run_at: Optional[datetime]
    last_run_status: Optional[str]
    next_run_at: Optional[datetime]
    run_count: int
    fail_count: int
    consecutive_fails: int
    max_consecutive_fails: int
    comments: Optional[str]


# ─── Database Connection ─────────────────────────────────────────────────────

class NexusDB:
    """Synchronous database access layer for the Nexus Light platform."""

    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or get_dsn()
        self._conn: Optional[psycopg.Connection] = None

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

    def get_enabled_stocks(self, state: Optional[str] = None, tags: Optional[list[str]] = None) -> list[Stock]:
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

    def get_stock(self, ticker: str) -> Optional[Stock]:
        """Get a single stock by ticker."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.stocks WHERE ticker = %s", [ticker.upper()])
            row = cur.fetchone()
        return self._row_to_stock(row) if row else None

    def get_stocks_near_earnings(self, days: int = 14) -> list[Stock]:
        """Get stocks with earnings within N days."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.stocks 
                WHERE is_enabled = true 
                  AND next_earnings_date IS NOT NULL
                  AND next_earnings_date >= CURRENT_DATE
                  AND next_earnings_date <= CURRENT_DATE + %s * INTERVAL '1 day'
                ORDER BY next_earnings_date ASC
            """, [days])
            rows = cur.fetchall()
        return [self._row_to_stock(r) for r in rows]

    # Valid column names for stocks table (whitelist)
    STOCK_COLUMNS = {
        'name', 'sector', 'is_enabled', 'state', 'default_analysis_type',
        'priority', 'next_earnings_date', 'earnings_confirmed', 'beat_history',
        'has_open_position', 'position_state', 'max_position_pct', 'comments', 'tags',
    }

    def upsert_stock(self, ticker: str, **kwargs) -> Optional[Stock]:
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
                        f"UPDATE nexus.stocks SET {', '.join(set_parts)} WHERE ticker = %s",
                        params
                    )
                self.conn.commit()
        else:
            # Insert with defaults
            cols = ['ticker'] + list(kwargs.keys())
            vals = [ticker] + list(kwargs.values())
            placeholders = ', '.join(['%s'] * len(vals))
            col_str = ', '.join(cols)
            with self.conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO nexus.stocks ({col_str}) VALUES ({placeholders})",
                    vals
                )
            self.conn.commit()

        return self.get_stock(ticker)

    def update_stock_position(self, ticker: str, has_open_position: bool, position_state: str):
        """Update stock position tracking fields."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.stocks 
                SET has_open_position = %s, position_state = %s
                WHERE ticker = %s
            """, [has_open_position, position_state, ticker.upper()])
        self.conn.commit()

    def _row_to_stock(self, row: dict) -> Stock:
        return Stock(
            id=row['id'], ticker=row['ticker'], name=row.get('name'),
            sector=row.get('sector'), is_enabled=row['is_enabled'],
            state=row['state'], default_analysis_type=row['default_analysis_type'],
            priority=row['priority'], next_earnings_date=row.get('next_earnings_date'),
            earnings_confirmed=row.get('earnings_confirmed', False),
            beat_history=row.get('beat_history'),
            has_open_position=row.get('has_open_position', False),
            position_state=row.get('position_state'),
            max_position_pct=float(row.get('max_position_pct', 6.0)),
            comments=row.get('comments'), tags=row.get('tags') or [],
        )

    # ─── IB Scanners ────────────────────────────────────────────────────

    def get_enabled_scanners(self) -> list[IBScanner]:
        """Get all enabled IB scanners."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.ib_scanners WHERE is_enabled = true ORDER BY id")
            rows = cur.fetchall()
        return [self._row_to_scanner(r) for r in rows]

    def get_scanner(self, scanner_id: int) -> Optional[IBScanner]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.ib_scanners WHERE id = %s", [scanner_id])
            row = cur.fetchone()
        return self._row_to_scanner(row) if row else None

    def get_scanner_by_code(self, code: str) -> Optional[IBScanner]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.ib_scanners WHERE scanner_code = %s", [code])
            row = cur.fetchone()
        return self._row_to_scanner(row) if row else None

    def _row_to_scanner(self, row: dict) -> IBScanner:
        filters = row.get('filters', {})
        if isinstance(filters, str):
            filters = json.loads(filters)
        return IBScanner(
            id=row['id'], scanner_code=row['scanner_code'],
            display_name=row['display_name'], description=row.get('description'),
            is_enabled=row['is_enabled'], instrument=row.get('instrument', 'STK'),
            location=row.get('location', 'STK.US.MAJOR'),
            num_results=row.get('num_results', 20), filters=filters,
            auto_add_to_watchlist=row.get('auto_add_to_watchlist', False),
            auto_analyze=row.get('auto_analyze', False),
            analysis_type=row.get('analysis_type', 'stock'),
            max_candidates=row.get('max_candidates', 5),
            comments=row.get('comments'),
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
            cur.execute("SELECT * FROM nexus.schedules WHERE is_enabled = true ORDER BY priority DESC")
            rows = cur.fetchall()
        return [self._row_to_schedule(r) for r in rows]

    def get_schedule(self, schedule_id: int) -> Optional[Schedule]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.schedules WHERE id = %s", [schedule_id])
            row = cur.fetchone()
        return self._row_to_schedule(row) if row else None

    def get_earnings_triggered_schedules(self, ticker: str, days_until: int) -> list[Schedule]:
        """Get pre/post-earnings schedules that match this ticker's timing."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.schedules 
                WHERE is_enabled = true
                  AND frequency IN ('pre_earnings', 'post_earnings')
                  AND (
                    (frequency = 'pre_earnings' AND days_before_earnings = %s)
                    OR
                    (frequency = 'post_earnings' AND days_after_earnings = %s)
                  )
            """, [days_until, abs(days_until)])  # abs() for post-earnings: days_until is negative when past
            rows = cur.fetchall()
        return [self._row_to_schedule(r) for r in rows]

    def mark_schedule_started(self, schedule_id: int) -> int:
        """Mark a schedule as running and create a run_history entry. Returns run_id."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.schedules 
                SET last_run_at = now(), last_run_status = 'running'
                WHERE id = %s
            """, [schedule_id])

            # Get schedule details for run_history
            cur.execute("SELECT * FROM nexus.schedules WHERE id = %s", [schedule_id])
            sched = cur.fetchone()

            cur.execute("""
                INSERT INTO nexus.run_history (schedule_id, task_type, ticker, analysis_type, status, stage)
                VALUES (%s, %s, %s, %s, 'running', 'analysis')
                RETURNING id
            """, [schedule_id, sched['task_type'], sched.get('target_ticker'), sched.get('analysis_type')])
            run_id = cur.fetchone()['id']

        self.conn.commit()
        return run_id

    def mark_schedule_completed(self, schedule_id: int, run_id: int, 
                                 status: str = 'completed', error: Optional[str] = None,
                                 **result_fields):
        """Update schedule and run_history after completion."""
        now = datetime.now(ET)

        with self.conn.cursor() as cur:
            # Update schedule
            if status == 'completed':
                cur.execute("""
                    UPDATE nexus.schedules 
                    SET last_run_status = %s, run_count = run_count + 1, 
                        consecutive_fails = 0
                    WHERE id = %s
                """, [status, schedule_id])
            elif status == 'failed':
                cur.execute("""
                    UPDATE nexus.schedules 
                    SET last_run_status = %s, run_count = run_count + 1,
                        fail_count = fail_count + 1, 
                        consecutive_fails = consecutive_fails + 1
                    WHERE id = %s
                """, [status, schedule_id])

                # Circuit breaker check
                cur.execute("""
                    UPDATE nexus.schedules 
                    SET is_enabled = false 
                    WHERE id = %s AND consecutive_fails >= max_consecutive_fails
                """, [schedule_id])
            else:
                cur.execute("""
                    UPDATE nexus.schedules SET last_run_status = %s WHERE id = %s
                """, [status, schedule_id])

            # Update run_history
            update_parts = ["status = %s", "completed_at = now()"]
            params: list[Any] = [status]

            if error:
                update_parts.append("error_message = %s")
                params.append(error)

            for key in ['gate_passed', 'recommendation', 'confidence', 'expected_value',
                        'order_placed', 'order_id', 'analysis_file', 'trade_file', 'raw_output']:
                if key in result_fields:
                    update_parts.append(f"{key} = %s")
                    params.append(result_fields[key])

            if 'order_details' in result_fields:
                update_parts.append("order_details = %s")
                params.append(json.dumps(result_fields['order_details']))

            params.append(run_id)
            cur.execute(
                f"UPDATE nexus.run_history SET {', '.join(update_parts)} WHERE id = %s",
                params
            )

            # Calculate and store duration
            cur.execute("""
                UPDATE nexus.run_history 
                SET duration_seconds = EXTRACT(EPOCH FROM (completed_at - started_at))
                WHERE id = %s
            """, [run_id])

        self.conn.commit()

    # ─── Scanner Run Logging ────────────────────────────────────────────────────

    def start_scanner_run(self, scanner_code: str) -> int:
        """Start a scanner run and create a run_history entry. Returns run_id."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.run_history
                (task_type, ticker, status, stage)
                VALUES ('run_scanner', %s, 'running', 'scan')
                RETURNING id
            """, [scanner_code])
            run_id = cur.fetchone()['id']
        self.conn.commit()
        return run_id

    def complete_scanner_run(self, run_id: int, status: str = 'completed',
                             candidates_found: int = 0, error: Optional[str] = None):
        """Complete a scanner run with results."""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.run_history
                SET status = %s,
                    completed_at = now(),
                    duration_seconds = EXTRACT(EPOCH FROM (now() - started_at)),
                    raw_output = %s,
                    error_message = %s
                WHERE id = %s
            """, [status, json.dumps({"candidates_found": candidates_found}), error, run_id])
        self.conn.commit()

    def calculate_next_run(self, schedule: Schedule) -> Optional[datetime]:
        """Calculate the next run time for a schedule."""
        now = datetime.now(ET)

        if schedule.frequency == 'once':
            return None  # Already ran

        elif schedule.frequency == 'daily':
            if schedule.time_of_day:
                next_dt = now.replace(
                    hour=schedule.time_of_day.hour,
                    minute=schedule.time_of_day.minute,
                    second=0, microsecond=0
                )
                if next_dt <= now:
                    next_dt += timedelta(days=1)
                # Skip weekends if trading_days_only
                if schedule.trading_days_only:
                    while next_dt.weekday() >= 5:
                        next_dt += timedelta(days=1)
                return next_dt

        elif schedule.frequency == 'weekly':
            day_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
            target_day = day_map.get(schedule.day_of_week or 'mon', 0)
            days_ahead = target_day - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_dt = now + timedelta(days=days_ahead)
            if schedule.time_of_day:
                next_dt = next_dt.replace(
                    hour=schedule.time_of_day.hour,
                    minute=schedule.time_of_day.minute,
                    second=0, microsecond=0
                )
            return next_dt

        elif schedule.frequency == 'interval':
            if schedule.interval_minutes:
                return now + timedelta(minutes=schedule.interval_minutes)

        elif schedule.frequency in ('pre_earnings', 'post_earnings'):
            # These are triggered by earnings dates, not time-based
            # Return far future; the earnings checker will trigger them
            return None

        return None

    def update_next_run(self, schedule_id: int, next_run: Optional[datetime]):
        """Set the next_run_at for a schedule."""
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE nexus.schedules SET next_run_at = %s WHERE id = %s",
                [next_run, schedule_id]
            )
        self.conn.commit()

    def save_analysis_result(self, run_id: Optional[int], ticker: str, analysis_type: str, parsed: dict):
        """Save structured analysis result from parsed JSON."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.analysis_results 
                (run_id, ticker, analysis_type, gate_passed, recommendation, confidence,
                 expected_value_pct, entry_price, stop_loss, target_price, position_size_pct,
                 structure, expiry_date, strikes, rationale)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, [
                run_id, ticker, analysis_type,
                parsed.get('gate_passed'),
                parsed.get('recommendation'),
                parsed.get('confidence'),
                parsed.get('expected_value_pct'),
                parsed.get('entry_price'),
                parsed.get('stop_loss'),
                parsed.get('target'),
                parsed.get('position_size_pct'),
                parsed.get('structure'),
                parsed.get('expiry'),
                parsed.get('strikes'),
                parsed.get('rationale_summary'),
            ])
        self.conn.commit()

    def get_today_run_count(self, task_type: Optional[str] = None) -> int:
        """Count runs executed today."""
        with self.conn.cursor() as cur:
            if task_type:
                cur.execute("""
                    SELECT COUNT(*) as cnt FROM nexus.run_history 
                    WHERE started_at >= CURRENT_DATE AND task_type = %s
                """, [task_type])
            else:
                cur.execute("""
                    SELECT COUNT(*) as cnt FROM nexus.run_history 
                    WHERE started_at >= CURRENT_DATE
                """)
            return cur.fetchone()['cnt']

    def _row_to_schedule(self, row: dict) -> Schedule:
        return Schedule(
            id=row['id'], name=row['name'], description=row.get('description'),
            is_enabled=row['is_enabled'], task_type=row['task_type'],
            target_ticker=row.get('target_ticker'),
            target_scanner_id=row.get('target_scanner_id'),
            target_tags=row.get('target_tags'),
            analysis_type=row.get('analysis_type', 'stock'),
            auto_execute=row.get('auto_execute', False),
            custom_prompt=row.get('custom_prompt'),
            frequency=row['frequency'],
            time_of_day=row.get('time_of_day'),
            day_of_week=row.get('day_of_week'),
            interval_minutes=row.get('interval_minutes'),
            days_before_earnings=row.get('days_before_earnings'),
            days_after_earnings=row.get('days_after_earnings'),
            market_hours_only=row.get('market_hours_only', True),
            trading_days_only=row.get('trading_days_only', True),
            max_runs_per_day=row.get('max_runs_per_day', 1),
            timeout_seconds=row.get('timeout_seconds', 600),
            priority=row.get('priority', 5),
            last_run_at=row.get('last_run_at'),
            last_run_status=row.get('last_run_status'),
            next_run_at=row.get('next_run_at'),
            run_count=row.get('run_count', 0),
            fail_count=row.get('fail_count', 0),
            consecutive_fails=row.get('consecutive_fails', 0),
            max_consecutive_fails=row.get('max_consecutive_fails', 3),
            comments=row.get('comments'),
        )

    # ─── Settings ──────────────────────────────────────────────────────

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a single setting value (parsed from JSONB)."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT value FROM nexus.settings WHERE key = %s", [key])
                row = cur.fetchone()
            return row['value'] if row else default
        except Exception:
            return default

    def get_settings_by_category(self, category: str) -> dict[str, Any]:
        """Get all settings in a category as a dict."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT key, value FROM nexus.settings WHERE category = %s",
                [category]
            )
            rows = cur.fetchall()
        return {r['key']: r['value'] for r in rows}

    def get_all_settings(self) -> dict[str, Any]:
        """Get all settings as a flat dict."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT key, value FROM nexus.settings")
            rows = cur.fetchall()
        return {r['key']: r['value'] for r in rows}

    def set_setting(self, key: str, value: Any, description: Optional[str] = None, category: Optional[str] = None):
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
                params.extend([key, json.dumps(value), category or 'general', description or ''])
                cur.execute(f"""
                    INSERT INTO nexus.settings (key, value, category, description)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (key) DO UPDATE SET {', '.join(parts)}
                """, params)
            else:
                cur.execute("""
                    INSERT INTO nexus.settings (key, value) VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE SET value = %s
                """, [key, json.dumps(value), json.dumps(value)])
        self.conn.commit()

    # ─── Service Status ──────────────────────────────────────────────────

    def heartbeat(self, state: str = 'running', current_task: Optional[str] = None,
                  tick_duration_ms: Optional[int] = None):
        """Update the service heartbeat (singleton row)."""
        import socket
        with self.conn.cursor() as cur:
            cur.execute("""
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
            """, [state, current_task, tick_duration_ms, os.getpid(), socket.gethostname()])
        self.conn.commit()

    def increment_service_counter(self, counter: str):
        """Increment a service counter: analyses_total, executions_total, errors_total."""
        valid = {'analyses_total', 'executions_total', 'errors_total',
                 'today_analyses', 'today_executions', 'today_errors'}
        if counter not in valid:
            return
        with self.conn.cursor() as cur:
            cur.execute(
                f"UPDATE nexus.service_status SET {counter} = {counter} + 1 WHERE id = 1"
            )
        self.conn.commit()

    def get_service_status(self) -> Optional[dict]:
        """Get current service status."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.service_status WHERE id = 1")
            return cur.fetchone()

    def mark_service_started(self):
        """Mark service as starting."""
        import socket
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.service_status SET
                    started_at = now(), last_heartbeat = now(),
                    state = 'starting', pid = %s, hostname = %s,
                    ticks_total = 0, analyses_total = 0, executions_total = 0, errors_total = 0,
                    today_analyses = 0, today_executions = 0, today_errors = 0,
                    today_date = CURRENT_DATE
                WHERE id = 1
            """, [os.getpid(), socket.gethostname()])
        self.conn.commit()

    def mark_service_stopped(self, state: str = 'stopped'):
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE nexus.service_status SET state = %s, current_task = NULL WHERE id = 1",
                [state]
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
        schema_file = os.path.join(os.path.dirname(__file__), 'db', 'init.sql')
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
                count = cur.fetchone()['cnt']
                log.info(f"DB health OK - {count} stocks in watchlist")
                return True
        except Exception as e:
            log.error(f"DB health check failed: {e}")
            return False

    # ─── Audit Logging ─────────────────────────────────────────────────────

    def audit_log(
        self,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        result: str = "success",
        details: Optional[dict] = None,
        actor: str = "system",
    ) -> Optional[int]:
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
                    [action, resource_type, resource_id, result,
                     json.dumps(details or {}), actor],
                )
                row = cur.fetchone()
                self.conn.commit()
                return row['id'] if row else None
        except Exception as e:
            log.warning(f"Failed to write audit log: {e}")
            return None

    def get_audit_logs(
        self,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        actor: Optional[str] = None,
        since: Optional[datetime] = None,
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
