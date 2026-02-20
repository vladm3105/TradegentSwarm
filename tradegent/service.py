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

import os
import sys
import signal
import time
import logging
import threading
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
from db_layer import NexusDB
import orchestrator
from orchestrator import (
    Settings, cfg,
    run_due_schedules, run_earnings_check,
)

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
                is_healthy = status and status.get('state') in ('running', 'starting')

                if is_healthy:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()

                    import json
                    # Only expose detailed metrics if authenticated
                    if self._check_auth():
                        body = json.dumps({
                            "status": "healthy",
                            "state": status.get('state'),
                            "uptime_since": str(status.get('started_at')),
                            "last_heartbeat": str(status.get('last_heartbeat')),
                            "ticks": status.get('ticks_total', 0),
                            "today_analyses": status.get('today_analyses', 0),
                            "today_executions": status.get('today_executions', 0),
                        })
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
        self._db: Optional[NexusDB] = None
        self._health_server = None
        self._last_earnings_check: Optional[datetime] = None

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
        log.info(f"Settings loaded: poll={orchestrator.cfg.scheduler_poll_seconds}s, "
                 f"dry_run={orchestrator.cfg.dry_run_mode}, "
                 f"auto_execute={orchestrator.cfg.auto_execute_enabled}")

        # Mark service started
        self._db.mark_service_started()

        # Initialize schedule next_run_at times
        self._init_schedule_times()

        # Start health endpoint
        health_port = int(os.getenv("HEALTH_PORT", "8080"))
        self._health_server = start_health_server(self._db, health_port)

        # Enter main loop
        self._running = True
        self._db.heartbeat('running')
        log.info("Service running — entering main loop")

        try:
            self._main_loop()
        except Exception as e:
            log.error(f"Fatal error in main loop: {e}", exc_info=True)
            self._db.heartbeat('error', current_task=str(e)[:200])
            self._db.increment_service_counter('errors_total')
            self._db.increment_service_counter('today_errors')
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
                self._db.increment_service_counter('errors_total')
                self._db.increment_service_counter('today_errors')

            tick_ms = int((time.monotonic() - tick_start) * 1000)
            self._db.heartbeat('running', tick_duration_ms=tick_ms)

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
        self._db.heartbeat('running', current_task='checking due schedules')
        run_due_schedules(self._db)

        # 4. Check earnings triggers (during configured hours)
        now = datetime.now(ET)
        earnings_hours = orchestrator.cfg.earnings_check_hours
        is_trading_day = now.weekday() < 5

        if (now.hour in earnings_hours and is_trading_day and
                (self._last_earnings_check is None or
                 (now - self._last_earnings_check).total_seconds() > 3600)):
            self._db.heartbeat('running', current_task='earnings check')
            run_earnings_check(self._db)
            self._last_earnings_check = now

        # 5. Clear current task
        self._db.heartbeat('running', current_task=None)

    def _interruptible_sleep(self, seconds: int):
        """Sleep that can be interrupted by SIGTERM/SIGINT."""
        end = time.monotonic() + seconds
        while self._running and time.monotonic() < end:
            time.sleep(min(1.0, end - time.monotonic()))

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

    print(f"\n{'═'*55}")
    print(f"  NEXUS LIGHT SERVICE HEALTH")
    print(f"{'═'*55}")
    print(f"  State:          {status.get('state', 'unknown')}")
    print(f"  PID:            {status.get('pid', '—')}")
    print(f"  Host:           {status.get('hostname', '—')}")
    print(f"  Started:        {status.get('started_at', '—')}")
    print(f"  Last Heartbeat: {status.get('last_heartbeat', '—')}")
    print(f"  Last Tick:      {status.get('last_tick_duration_ms', '—')}ms")
    print(f"  Current Task:   {status.get('current_task', '(idle)')}")
    print(f"  Version:        {status.get('version', '—')}")

    print(f"\n  Lifetime Totals:")
    print(f"    Ticks:        {status.get('ticks_total', 0)}")
    print(f"    Analyses:     {status.get('analyses_total', 0)}")
    print(f"    Executions:   {status.get('executions_total', 0)}")
    print(f"    Errors:       {status.get('errors_total', 0)}")

    print(f"\n  Today ({status.get('today_date', '—')}):")
    print(f"    Analyses:     {status.get('today_analyses', 0)} / {settings.get('max_daily_analyses', '?')}")
    print(f"    Executions:   {status.get('today_executions', 0)} / {settings.get('max_daily_executions', '?')}")
    print(f"    Errors:       {status.get('today_errors', 0)}")

    print(f"\n  Key Settings:")
    print(f"    Poll interval: {settings.get('scheduler_poll_seconds', '?')}s")
    print(f"    Dry run mode:  {settings.get('dry_run_mode', '?')}")
    print(f"    Auto execute:  {settings.get('auto_execute_enabled', '?')}")
    print(f"    Scanners:      {settings.get('scanners_enabled', '?')}")
    print(f"{'═'*55}\n")


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
