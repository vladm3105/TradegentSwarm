#!/usr/bin/env python3
"""
Nexus Light - Service v2.1
Long-running, uninterrupted orchestrator service.

All configuration is read from PostgreSQL on every tick — no restarts needed.
Settings changes, new stocks, scanner toggles, schedule edits all take effect
on the next tick automatically.

Modes:
    service.py                 # Run as long-running service (default)
    service.py once            # Single tick, then exit (for cron/Cloud Run Jobs)
    service.py init            # Initialize schedule times and exit
    service.py health          # Print health status and exit

Architecture:
    ┌─────────────────────────────────────────────┐
    │                SERVICE LOOP                  │
    │                                              │
    │   ┌─────────┐   ┌──────────┐   ┌────────┐  │
    │   │ Refresh  │──▶│ Check    │──▶│Execute │  │
    │   │ Settings │   │ Due      │   │ Tasks  │  │
    │   │ from DB  │   │ Schedules│   │        │  │
    │   └─────────┘   └──────────┘   └────────┘  │
    │         │              │             │       │
    │   ┌─────▼──────────────▼─────────────▼──┐   │
    │   │           Heartbeat + Metrics        │   │
    │   └──────────────────────────────────────┘   │
    │                                              │
    │   sleep(scheduler_poll_seconds from DB)       │
    └─────────────────────────────────────────────┘
"""

import logging
import os
import signal
import sys
import threading
import time
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
import orchestrator
from db_layer import NexusDB
from expiration_monitor import ExpirationMonitor
from ib_client import IBClient
from notifications import (
    NotificationRouter,
    Notification,
    NotificationPriority,
    TelegramChannel,
    WebhookChannel,
    EmailChannel,
    create_notification_router,
)
from order_reconciler import OrderReconciler
from orchestrator import (
    Settings,
    run_due_schedules,
    run_earnings_check,
    process_task_queue,
)
from position_monitor import PositionMonitor
from trading_calendar import is_market_hours, is_trading_day, ET as TRADING_ET
from watchlist_monitor import WatchlistMonitor

ET = ZoneInfo("America/New_York")
BASE_DIR = Path(__file__).parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "logs" / "service.log"),
    ],
)
log = logging.getLogger("nexus-service")

# ─── Health Check HTTP Server ────────────────────────────────────────────────


class HealthHandler(BaseHTTPRequestHandler):
    """
    Secure HTTP handler for Docker/Cloud Run health checks.

    Security features:
    - Binds to localhost by default (HEALTH_BIND_ADDR env var)
    - Optional token authentication (HEALTH_CHECK_TOKEN env var)
    - Minimal information exposure in authenticated vs unauthenticated mode
    """

    db_ref: NexusDB = None
    auth_token: str = None

    def _check_auth(self) -> bool:
        """Verify authentication token if configured."""
        if not self.auth_token:
            return True  # No auth configured, allow access

        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            provided_token = auth_header[7:]
            return provided_token == self.auth_token
        return False

    def do_GET(self):
        if self.path == "/health" or self.path == "/":
            try:
                # Always respond to health check for liveness probes
                status = self.db_ref.get_service_status() if self.db_ref else None
                is_healthy = status and status.get("state") in ("running", "starting")

                if is_healthy:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()

                    import json

                    # Only expose detailed metrics if authenticated
                    if self._check_auth():
                        body = json.dumps(
                            {
                                "status": "healthy",
                                "state": status.get("state"),
                                "uptime_since": str(status.get("started_at")),
                                "last_heartbeat": str(status.get("last_heartbeat")),
                                "ticks": status.get("ticks_total", 0),
                                "today_analyses": status.get("today_analyses", 0),
                                "today_executions": status.get("today_executions", 0),
                            }
                        )
                    else:
                        # Minimal response for unauthenticated requests
                        body = json.dumps({"status": "healthy"})
                    self.wfile.write(body.encode())
                else:
                    self.send_response(503)
                    self.end_headers()
                    self.wfile.write(b'{"status":"unhealthy"}')
            except Exception:
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b'{"status":"error"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress request logging


def start_health_server(db: NexusDB, port: int = 8080):
    """
    Start health check HTTP server in background thread.

    Environment variables:
    - HEALTH_BIND_ADDR: Address to bind (default: 127.0.0.1 for security)
    - HEALTH_CHECK_TOKEN: Optional bearer token for authentication
    """
    HealthHandler.db_ref = db
    HealthHandler.auth_token = os.getenv("HEALTH_CHECK_TOKEN")

    # Default to localhost for security; use 0.0.0.0 only in containerized envs
    bind_addr = os.getenv("HEALTH_BIND_ADDR", "127.0.0.1")
    server = HTTPServer((bind_addr, port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log.info(f"Health endpoint listening on {bind_addr}:{port}/health")
    return server


# ─── Service Core ────────────────────────────────────────────────────────────


class NexusService:
    """
    Long-running orchestrator service.

    On every tick:
    1. Refresh settings from DB (hot-reload)
    2. Reconnect DB if needed
    3. Check for due schedules → execute
    4. Check earnings triggers (during configured hours)
    5. Write heartbeat + metrics
    6. Sleep for configured interval
    """

    def __init__(self):
        self._running = False
        self._db: NexusDB | None = None
        self._health_server = None
        self._last_earnings_check: datetime | None = None

        # Position monitoring and order reconciliation
        self._ib_client: IBClient | None = None
        self._position_monitor: PositionMonitor | None = None
        self._order_reconciler: OrderReconciler | None = None
        self._last_position_check: datetime | None = None
        self._last_order_reconcile: datetime | None = None

        # Task queue processing
        self._last_task_process: datetime | None = None

        # Watchlist monitoring (IPLAN-004)
        self._watchlist_monitor = None
        self._last_watchlist_check: datetime | None = None

        # Options expiration monitoring (IPLAN-006)
        self._expiration_monitor: ExpirationMonitor | None = None
        self._last_expiration_check: datetime | None = None

        # Notification system (IPLAN-007)
        self._notifier: NotificationRouter | None = None

        # Wire up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum, frame):
        sig_name = signal.Signals(signum).name
        log.info(f"Received {sig_name} — shutting down gracefully")
        self._running = False

    @property
    def db(self) -> NexusDB:
        return self._db

    def start(self):
        """Initialize and enter the main service loop."""
        log.info("╔══════════════════════════════════════════╗")
        log.info("║  NEXUS LIGHT SERVICE v2.1                ║")
        log.info("╚══════════════════════════════════════════╝")

        # Connect to database
        self._db = NexusDB()
        self._db.connect()

        if not self._db.health_check():
            log.error("Database unhealthy. Run: python orchestrator.py db-init")
            sys.exit(1)

        # Initialize settings from DB
        orchestrator.cfg = Settings(self._db)
        log.info(
            f"Settings loaded: poll={orchestrator.cfg.scheduler_poll_seconds}s, "
            f"dry_run={orchestrator.cfg.dry_run_mode}, "
            f"auto_execute={orchestrator.cfg.auto_execute_enabled}"
        )

        # Initialize notification system (IPLAN-007)
        self._notifier = create_notification_router(self._db)
        if self._notifier:
            self._notifier.start()
            log.info("Notification router initialized")

        # Initialize IB client and monitors
        self._ib_client = IBClient()
        self._position_monitor = PositionMonitor(self._db, self._ib_client, self._notifier)
        self._order_reconciler = OrderReconciler(self._db, self._ib_client, self._notifier)

        # Verify IB MCP is available
        if not self._ib_client.health_check():
            log.warning("IB MCP server not available - position monitoring disabled")
        else:
            log.info("IB MCP server connected - position monitoring enabled")

        # Mark service started
        self._db.mark_service_started()

        # Initialize schedule next_run_at times
        self._init_schedule_times()

        # Start health endpoint
        health_port = int(os.getenv("HEALTH_PORT", "8080"))
        self._health_server = start_health_server(self._db, health_port)

        # Enter main loop
        self._running = True
        self._db.heartbeat("running")
        log.info("Service running — entering main loop")

        try:
            self._main_loop()
        except Exception as e:
            log.error(f"Fatal error in main loop: {e}", exc_info=True)
            self._db.heartbeat("error", current_task=str(e)[:200])
            self._db.increment_service_counter("errors_total")
            self._db.increment_service_counter("today_errors")
        finally:
            self._shutdown()

    def _main_loop(self):
        """The core tick loop."""
        while self._running:
            tick_start = time.monotonic()

            try:
                self._tick()
            except Exception as e:
                log.error(f"Tick error: {e}", exc_info=True)
                self._db.increment_service_counter("errors_total")
                self._db.increment_service_counter("today_errors")

            tick_ms = int((time.monotonic() - tick_start) * 1000)
            self._db.heartbeat("running", tick_duration_ms=tick_ms)

            # Sleep for configured interval (re-read from DB each cycle)
            poll_seconds = orchestrator.cfg.scheduler_poll_seconds
            self._interruptible_sleep(poll_seconds)

    def _tick(self):
        """Single service tick — the atomic unit of work."""

        # 1. Ensure DB connection is alive
        self._db.ensure_connection()

        # 2. Refresh settings from DB (hot-reload)
        orchestrator.cfg.refresh()

        # 3. Check and execute due schedules
        self._db.heartbeat("running", current_task="checking due schedules")
        run_due_schedules(self._db)

        # 4. Check earnings triggers (during configured hours)
        now = datetime.now(ET)
        earnings_hours = orchestrator.cfg.earnings_check_hours
        is_trading = now.weekday() < 5  # Weekday check

        if (
            now.hour in earnings_hours
            and is_trading
            and (
                self._last_earnings_check is None
                or (now - self._last_earnings_check).total_seconds() > 3600
            )
        ):
            self._db.heartbeat("running", current_task="earnings check")
            run_earnings_check(self._db)
            self._last_earnings_check = now

        # ─── Position Monitoring (every 5 minutes during market hours) ───────────
        now_et = datetime.now(TRADING_ET)
        position_monitor_enabled = orchestrator.cfg._get(
            "position_monitor_enabled", "feature_flags", "true"
        ).lower() == "true"

        if position_monitor_enabled and is_market_hours(now_et):
            position_interval = int(orchestrator.cfg._get(
                "position_monitor_interval_seconds", "scheduler", "300"
            ))

            if (self._last_position_check is None or
                (now_et - self._last_position_check).total_seconds() > position_interval):

                # Check IB MCP health first
                if self._ib_client and self._ib_client.health_check():
                    self._db.heartbeat("running", current_task="position monitoring")
                    try:
                        deltas = self._position_monitor.check_positions()
                        if deltas:
                            results = self._position_monitor.process_deltas(deltas)
                            log.info(f"Position monitor: {results}")
                    except Exception as e:
                        log.warning(f"Position monitor error: {e}")
                else:
                    log.debug("Skipping position monitor - IB MCP unavailable")

                self._last_position_check = now_et

        # ─── Order Reconciliation (every 2 minutes when orders pending) ──────────
        order_interval = 120  # seconds

        if (self._last_order_reconcile is None or
            (now_et - self._last_order_reconcile).total_seconds() > order_interval):

            pending = self._db.get_trades_with_pending_orders()
            if pending and self._ib_client and self._ib_client.health_check():
                self._db.heartbeat("running", current_task="order reconciliation")
                try:
                    results = self._order_reconciler.reconcile_pending_orders()
                    if results["filled"] or results["cancelled"] or results["partial"]:
                        log.info(f"Order reconciler: {results}")
                except Exception as e:
                    log.warning(f"Order reconciler error: {e}")

            self._last_order_reconcile = now_et

        # ─── Task Queue Processing (every tick, respects daily limits) ───────────
        task_queue_enabled = orchestrator.cfg._get(
            "task_queue_enabled", "feature_flags", "true"
        ).lower() == "true"

        if task_queue_enabled:
            # Process tasks every tick (limits enforced inside process_task_queue)
            max_tasks = int(orchestrator.cfg._get("max_tasks_per_tick", "scheduler", "3"))

            self._db.heartbeat("running", current_task="task queue processing")
            try:
                results = process_task_queue(self._db, max_tasks=max_tasks)
                if results["processed"] > 0:
                    log.info(f"Task queue: {results}")
            except Exception as e:
                log.warning(f"Task queue error: {e}")

        # ─── Watchlist Trigger Monitoring (every 5 minutes during market hours) ────
        watchlist_monitor_enabled = orchestrator.cfg._get(
            "watchlist_monitor_enabled", "feature_flags", "true"
        ).lower() == "true"

        if watchlist_monitor_enabled and is_market_hours(now_et):
            watchlist_interval = int(orchestrator.cfg._get(
                "watchlist_check_interval_seconds", "feature_flags", "300"
            ))

            if (self._last_watchlist_check is None or
                (now_et - self._last_watchlist_check).total_seconds() > watchlist_interval):

                # Initialize monitor on first use
                if self._watchlist_monitor is None:
                    if self._ib_client and self._ib_client.health_check():
                        price_tolerance = float(orchestrator.cfg._get(
                            "watchlist_price_threshold_pct", "feature_flags", "0.5"
                        ))
                        self._watchlist_monitor = WatchlistMonitor(
                            db=self._db,
                            ib_client=self._ib_client,
                            price_tolerance_pct=price_tolerance,
                            notifier=self._notifier
                        )
                        log.info("Watchlist monitor initialized")
                    else:
                        log.warning("IB MCP not available - watchlist monitoring disabled")

                if self._watchlist_monitor:
                    self._db.heartbeat("running", current_task="watchlist monitoring")
                    try:
                        results = self._watchlist_monitor.check_entries()
                        if results.triggered or results.invalidated or results.expired or results.errors:
                            log.info(f"Watchlist monitor: {results}")
                    except Exception as e:
                        log.warning(f"Watchlist monitor error: {e}")

                self._last_watchlist_check = now_et

        # ─── Options Expiration Check (once daily) ──────────────────────────────────
        if self._should_check_expirations():
            self._process_expirations()

        # 5. Clear current task
        self._db.heartbeat("running", current_task=None)

    def _interruptible_sleep(self, seconds: int):
        """Sleep that can be interrupted by SIGTERM/SIGINT."""
        end = time.monotonic() + seconds
        while self._running and time.monotonic() < end:
            time.sleep(min(1.0, end - time.monotonic()))

    def _should_check_expirations(self) -> bool:
        """Check if we should run expiration processing (once daily)."""
        last_check = self._last_expiration_check
        if last_check is None:
            return True
        # Run once per day
        return last_check.date() < date.today()

    def _process_expirations(self):
        """Process expired options (IPLAN-006)."""
        self._db.heartbeat("running", current_task="options expiration check")

        try:
            # Initialize monitor on first use
            if self._expiration_monitor is None:
                self._expiration_monitor = ExpirationMonitor(self._db, self._notifier)
                log.info("Expiration monitor initialized")

            # Pass stock price function for ITM detection
            def get_price(ticker):
                if self._ib_client and self._ib_client.health_check():
                    try:
                        result = self._ib_client.get_stock_price(ticker)
                        return float(result.get("last") or result.get("close") or 0) or None
                    except Exception:
                        return None
                return None

            results = self._expiration_monitor.process_expirations(get_stock_price_fn=get_price)

            if results["expired_worthless"] or results["needs_review"] or results["errors"]:
                log.info(f"Expiration check: {results}")

            # Log summary of upcoming expirations
            summary = self._expiration_monitor.get_summary()
            if summary["critical"]:
                log.warning(f"CRITICAL: {summary['critical']} options expiring within 3 days")
                # Send expiration warning notifications
                warnings_sent = self._expiration_monitor.send_expiration_warnings()
                if warnings_sent:
                    log.info(f"Sent {warnings_sent} expiration warning notifications")
            if summary["warning"]:
                log.info(f"Options expiring within 7 days: {summary['warning']}")

        except Exception as e:
            log.warning(f"Expiration check error: {e}")

        self._last_expiration_check = datetime.now()

    def _init_schedule_times(self):
        """Set next_run_at for all enabled schedules."""
        schedules = self._db.get_enabled_schedules()
        log.info(f"Initializing next_run_at for {len(schedules)} schedules")
        for sched in schedules:
            if sched.next_run_at is None:
                next_run = self._db.calculate_next_run(sched)
                if next_run:
                    self._db.update_next_run(sched.id, next_run)
                    log.info(f"  {sched.name}: {next_run.strftime('%Y-%m-%d %H:%M')}")

    def _shutdown(self):
        """Clean shutdown."""
        log.info("Shutting down...")

        # Stop notification router
        if self._notifier:
            try:
                self._notifier.stop()
            except Exception:
                pass

        # Close IB client
        if self._ib_client:
            try:
                self._ib_client.__exit__(None, None, None)
            except Exception:
                pass

        if self._db:
            try:
                self._db.mark_service_stopped()
            except Exception:
                pass
            self._db.close()
        if self._health_server:
            self._health_server.shutdown()
        log.info("Service stopped")

    def run_once(self):
        """Single tick for cron/Cloud Run Jobs usage."""
        self._db = NexusDB()
        self._db.connect()

        if not self._db.health_check():
            log.error("Database unhealthy")
            sys.exit(1)

        orchestrator.cfg = Settings(self._db)

        try:
            self._tick()
        finally:
            self._db.close()


# ─── CLI ─────────────────────────────────────────────────────────────────────


def show_health(db: NexusDB):
    """Print service health status."""
    status = db.get_service_status()
    if not status:
        print("No service status found. Run: python orchestrator.py db-init")
        return

    settings = db.get_all_settings()

    print(f"\n{'═' * 55}")
    print("  NEXUS LIGHT SERVICE HEALTH")
    print(f"{'═' * 55}")
    print(f"  State:          {status.get('state', 'unknown')}")
    print(f"  PID:            {status.get('pid', '—')}")
    print(f"  Host:           {status.get('hostname', '—')}")
    print(f"  Started:        {status.get('started_at', '—')}")
    print(f"  Last Heartbeat: {status.get('last_heartbeat', '—')}")
    print(f"  Last Tick:      {status.get('last_tick_duration_ms', '—')}ms")
    print(f"  Current Task:   {status.get('current_task', '(idle)')}")
    print(f"  Version:        {status.get('version', '—')}")

    print("\n  Lifetime Totals:")
    print(f"    Ticks:        {status.get('ticks_total', 0)}")
    print(f"    Analyses:     {status.get('analyses_total', 0)}")
    print(f"    Executions:   {status.get('executions_total', 0)}")
    print(f"    Errors:       {status.get('errors_total', 0)}")

    print(f"\n  Today ({status.get('today_date', '—')}):")
    print(
        f"    Analyses:     {status.get('today_analyses', 0)} / {settings.get('max_daily_analyses', '?')}"
    )
    print(
        f"    Executions:   {status.get('today_executions', 0)} / {settings.get('max_daily_executions', '?')}"
    )
    print(f"    Errors:       {status.get('today_errors', 0)}")

    print("\n  Key Settings:")
    print(f"    Poll interval: {settings.get('scheduler_poll_seconds', '?')}s")
    print(f"    Dry run mode:  {settings.get('dry_run_mode', '?')}")
    print(f"    Auto execute:  {settings.get('auto_execute_enabled', '?')}")
    print(f"    Scanners:      {settings.get('scanners_enabled', '?')}")
    print(f"{'═' * 55}\n")


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "run"

    if command in ("run", "daemon", "start"):
        service = NexusService()
        service.start()

    elif command == "once":
        service = NexusService()
        service.run_once()

    elif command == "init":
        with NexusDB() as db:
            orchestrator.cfg = Settings(db)
            schedules = db.get_enabled_schedules()
            for sched in schedules:
                next_run = db.calculate_next_run(sched)
                if next_run:
                    db.update_next_run(sched.id, next_run)
                    print(f"  {sched.name}: {next_run}")

    elif command == "health":
        with NexusDB() as db:
            show_health(db)

    else:
        print("""
Nexus Light Service v2.1

Usage:
    service.py              Run as long-running service (default)
    service.py once         Single tick and exit (cron/Cloud Run Jobs)
    service.py init         Initialize schedule times
    service.py health       Show service health status

Settings are read from nexus.settings table on every tick.
To change behavior without restarting:
    UPDATE nexus.settings SET value = '30' WHERE key = 'scheduler_poll_seconds';
    UPDATE nexus.settings SET value = 'false' WHERE key = 'dry_run_mode';
""")


if __name__ == "__main__":
    main()
