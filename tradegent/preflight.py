"""Pre-flight checks for analysis workflows.

Provides two check levels:
- Full check: Run at start of session (first analysis of day)
- Quick check: Run before each analysis

Trading Mode:
- Set IB_MODE=paper or IB_MODE=live in .env
- Paper: Port 4002, simulated trading
- Live: Port 4001, REAL MONEY

Usage:
    from tradegent.preflight import run_full_preflight, run_quick_preflight, get_trading_mode

    # Check current trading mode
    mode = get_trading_mode()
    print(f"Trading mode: {mode.mode} on port {mode.port}")

    # First run of day
    status = run_full_preflight()

    # Before each analysis
    status = run_quick_preflight()
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv

# Load .env file
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

log = logging.getLogger(__name__)


class TradingModeType(Enum):
    """Trading mode enumeration."""
    PAPER = "paper"
    LIVE = "live"


@dataclass
class TradingModeConfig:
    """Trading mode configuration."""
    mode: TradingModeType
    port: int
    container_name: str
    account: str
    is_readonly: bool

    @property
    def is_paper(self) -> bool:
        return self.mode == TradingModeType.PAPER

    @property
    def is_live(self) -> bool:
        return self.mode == TradingModeType.LIVE

    @property
    def mode_banner(self) -> str:
        """Get a prominent banner for the current mode."""
        if self.is_paper:
            return "📋 PAPER TRADING (Simulated)"
        else:
            return "🔴 LIVE TRADING (REAL MONEY)"


def get_trading_mode() -> TradingModeConfig:
    """
    Get the current trading mode configuration.

    Returns:
        TradingModeConfig with mode, port, container, and account info
    """
    mode_str = os.getenv("IB_MODE", "paper").lower()

    if mode_str == "live":
        return TradingModeConfig(
            mode=TradingModeType.LIVE,
            port=4001,
            container_name="live-ib-gateway",
            account=os.getenv("IB_LIVE_ACCOUNT", ""),
            is_readonly=True,  # Safety default for live
        )
    else:
        return TradingModeConfig(
            mode=TradingModeType.PAPER,
            port=4002,
            container_name="paper-ib-gateway",
            account=os.getenv("IB_PAPER_ACCOUNT", ""),
            is_readonly=False,
        )


@dataclass
class ServiceStatus:
    """Status of a single service."""
    name: str
    status: str  # "healthy", "degraded", "unhealthy", "unknown"
    message: str = ""
    details: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status in ("healthy", "degraded")


@dataclass
class PreflightResult:
    """Result of preflight checks."""
    timestamp: datetime
    check_type: str  # "full" or "quick"
    trading_mode: TradingModeConfig = field(default_factory=get_trading_mode)
    services: dict[str, ServiceStatus] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        """All services healthy or degraded."""
        return all(s.ok for s in self.services.values())

    @property
    def can_analyze(self) -> bool:
        """Minimum requirements met for analysis."""
        # Need at least RAG working for historical context
        # IB is optional (will show stale/no data warning)
        # Graph is optional (will skip graph context)
        rag = self.services.get("rag")
        return rag is not None and rag.ok

    def summary(self) -> str:
        """Human-readable summary."""
        lines = []

        # Trading mode banner (prominent!)
        lines.append("=" * 60)
        lines.append(f"  {self.trading_mode.mode_banner}")
        lines.append(f"  Account: {self.trading_mode.account or 'Not configured'}")
        lines.append(f"  Port: {self.trading_mode.port} | Container: {self.trading_mode.container_name}")
        lines.append("=" * 60)
        lines.append("")

        lines.append(f"Preflight Check ({self.check_type}) - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("-" * 60)

        for name, status in self.services.items():
            icon = "✓" if status.ok else "✗"
            lines.append(f"  {icon} {name}: {status.status} - {status.message}")

        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            for w in self.warnings:
                lines.append(f"  ⚠ {w}")

        if self.errors:
            lines.append("")
            lines.append("Errors:")
            for e in self.errors:
                lines.append(f"  ✗ {e}")

        lines.append("-" * 60)
        status = "READY" if self.can_analyze else "NOT READY"
        lines.append(f"Status: {status}")

        return "\n".join(lines)


def check_postgres() -> ServiceStatus:
    """Check PostgreSQL/pgvector connection."""
    try:
        from rag.search import get_rag_stats
        stats = get_rag_stats()
        return ServiceStatus(
            name="rag",
            status="healthy",
            message=f"{stats.document_count} docs, {stats.chunk_count} chunks",
            details={"documents": stats.document_count, "chunks": stats.chunk_count}
        )
    except Exception as e:
        return ServiceStatus(
            name="rag",
            status="unhealthy",
            message=str(e)
        )


def check_neo4j() -> ServiceStatus:
    """Check Neo4j connection."""
    try:
        from graph.layer import TradingGraph
        with TradingGraph() as graph:
            if graph.health_check():
                stats = graph.get_stats()
                return ServiceStatus(
                    name="graph",
                    status="healthy",
                    message=f"{stats.total_nodes} nodes, {stats.total_edges} edges",
                    details={"nodes": stats.total_nodes, "edges": stats.total_edges}
                )
            else:
                return ServiceStatus(
                    name="graph",
                    status="unhealthy",
                    message="Health check failed"
                )
    except Exception as e:
        return ServiceStatus(
            name="graph",
            status="unhealthy",
            message=str(e)
        )


def check_ib_mcp() -> ServiceStatus:
    """Check IB MCP server by testing TCP connection to IB Gateway port."""
    mode = get_trading_mode()
    mode_label = mode.mode.value.upper()

    try:
        import socket

        # Test direct TCP connection to IB Gateway port
        # This verifies the gateway is accessible on the expected port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        result = sock.connect_ex(('localhost', mode.port))
        sock.close()

        if result == 0:
            return ServiceStatus(
                name="ib_mcp",
                status="healthy",
                message=f"{mode_label}: IB Gateway port {mode.port} accessible",
                details={"mode": mode.mode.value, "port": mode.port, "container": mode.container_name}
            )
        else:
            return ServiceStatus(
                name="ib_mcp",
                status="unhealthy",
                message=f"{mode_label}: IB Gateway port {mode.port} not responding",
                details={"mode": mode.mode.value, "port": mode.port, "error_code": result}
            )
    except socket.timeout:
        return ServiceStatus(
            name="ib_mcp",
            status="unhealthy",
            message=f"{mode_label}: Connection timeout to port {mode.port}"
        )
    except Exception as e:
        return ServiceStatus(
            name="ib_mcp",
            status="unhealthy",
            message=f"{mode_label}: {str(e)}"
        )


def check_ib_gateway_docker() -> ServiceStatus:
    """Check IB Gateway Docker container status based on current trading mode."""
    mode = get_trading_mode()
    container_name = mode.container_name
    mode_label = mode.mode.value.upper()

    try:
        import subprocess
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", container_name],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            health = result.stdout.strip()
            if health == "healthy":
                return ServiceStatus(
                    name="ib_gateway",
                    status="healthy",
                    message=f"{mode_label} container healthy ({container_name})",
                    details={"container": container_name, "mode": mode.mode.value}
                )
            elif health == "starting":
                return ServiceStatus(
                    name="ib_gateway",
                    status="degraded",
                    message=f"{mode_label} container starting ({container_name})",
                    details={"container": container_name, "mode": mode.mode.value}
                )
            else:
                return ServiceStatus(
                    name="ib_gateway",
                    status="unhealthy",
                    message=f"{mode_label} container: {health} ({container_name})",
                    details={"container": container_name, "mode": mode.mode.value}
                )
        else:
            return ServiceStatus(
                name="ib_gateway",
                status="unhealthy",
                message=f"{mode_label} container not found ({container_name})",
                details={"container": container_name, "mode": mode.mode.value}
            )
    except Exception as e:
        return ServiceStatus(
            name="ib_gateway",
            status="unknown",
            message=str(e)
        )


def check_market_status() -> ServiceStatus:
    """Check if markets are open."""
    from datetime import datetime
    import pytz

    try:
        et = pytz.timezone("America/New_York")
        now = datetime.now(et)

        # Check if weekend
        if now.weekday() >= 5:
            return ServiceStatus(
                name="market",
                status="degraded",
                message=f"Weekend - markets closed ({now.strftime('%A')})",
                details={"day": now.strftime("%A"), "time_et": now.strftime("%H:%M")}
            )

        # Check time (market hours 9:30 AM - 4:00 PM ET)
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

        if now < market_open:
            return ServiceStatus(
                name="market",
                status="degraded",
                message=f"Pre-market ({now.strftime('%H:%M')} ET)",
                details={"session": "pre-market", "time_et": now.strftime("%H:%M")}
            )
        elif now > market_close:
            return ServiceStatus(
                name="market",
                status="degraded",
                message=f"After-hours ({now.strftime('%H:%M')} ET)",
                details={"session": "after-hours", "time_et": now.strftime("%H:%M")}
            )
        else:
            return ServiceStatus(
                name="market",
                status="healthy",
                message=f"Market open ({now.strftime('%H:%M')} ET)",
                details={"session": "regular", "time_et": now.strftime("%H:%M")}
            )
    except Exception as e:
        return ServiceStatus(
            name="market",
            status="unknown",
            message=str(e)
        )


def run_full_preflight() -> PreflightResult:
    """
    Run full preflight checks - use at start of session.

    Checks:
    - PostgreSQL/pgvector (RAG)
    - Neo4j (Graph)
    - IB Gateway Docker container
    - IB MCP server
    - Market status
    """
    result = PreflightResult(
        timestamp=datetime.now(),
        check_type="full"
    )

    # Check all services
    result.services["rag"] = check_postgres()
    result.services["graph"] = check_neo4j()
    result.services["ib_gateway"] = check_ib_gateway_docker()
    result.services["ib_mcp"] = check_ib_mcp()
    result.services["market"] = check_market_status()

    # Generate warnings
    if not result.services["ib_gateway"].ok:
        result.warnings.append("IB Gateway unhealthy - live market data unavailable")

    if not result.services["ib_mcp"].ok:
        result.warnings.append("IB MCP not connected - cannot fetch real-time quotes")

    market = result.services["market"]
    if market.status == "degraded":
        result.warnings.append(f"Market closed: {market.message}")

    if not result.services["graph"].ok:
        result.warnings.append("Neo4j unavailable - graph context will be skipped")

    # Generate errors
    if not result.services["rag"].ok:
        result.errors.append("RAG (PostgreSQL) unavailable - cannot retrieve historical context")

    return result


def run_quick_preflight() -> PreflightResult:
    """
    Run quick preflight checks - use before each analysis.

    Checks:
    - PostgreSQL/pgvector (RAG) - essential
    - IB MCP server - for market data
    - Market status - for context
    """
    result = PreflightResult(
        timestamp=datetime.now(),
        check_type="quick"
    )

    # Essential checks only
    result.services["rag"] = check_postgres()
    result.services["ib_mcp"] = check_ib_mcp()
    result.services["market"] = check_market_status()

    # Generate warnings
    if not result.services["ib_mcp"].ok:
        result.warnings.append("IB MCP unavailable - using cached/stale data")

    market = result.services["market"]
    if market.status == "degraded":
        result.warnings.append(f"Note: {market.message}")

    # Generate errors
    if not result.services["rag"].ok:
        result.errors.append("RAG unavailable - cannot proceed with analysis")

    return result


def run_preflight(full: bool = False) -> PreflightResult:
    """
    Run preflight checks.

    Args:
        full: If True, run full checks. If False, run quick checks.
    """
    if full:
        return run_full_preflight()
    else:
        return run_quick_preflight()


if __name__ == "__main__":
    # CLI usage
    import sys

    full = "--full" in sys.argv
    result = run_preflight(full=full)
    print(result.summary())

    sys.exit(0 if result.can_analyze else 1)
