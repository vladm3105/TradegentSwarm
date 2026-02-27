"""Shared test fixtures for orchestrator and db_layer tests."""

from unittest.mock import MagicMock, patch

import pytest

# ─── Environment Setup ───────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Set test environment variables."""
    monkeypatch.setenv("PG_HOST", "localhost")
    monkeypatch.setenv("PG_PORT", "5433")
    monkeypatch.setenv("PG_USER", "tradegent")
    monkeypatch.setenv("PG_PASS", "testpass")
    monkeypatch.setenv("PG_DB", "tradegent")
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7688")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASS", "testpass")


# ─── Database Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def mock_db_connection():
    """Mock PostgreSQL connection."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cursor


@pytest.fixture
def mock_nexus_db(mock_db_connection):
    """Mock NexusDB instance."""
    mock_conn, mock_cursor = mock_db_connection

    with patch("db_layer.psycopg.connect", return_value=mock_conn):
        from db_layer import NexusDB

        db = NexusDB()
        db._conn = mock_conn
        yield db


# ─── Settings Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def mock_settings():
    """Mock Settings object with default values."""
    settings = MagicMock()
    settings.dry_run_mode = True
    settings.auto_execute_enabled = False
    settings.max_daily_analyses = 15
    settings.max_daily_executions = 5
    settings.scheduler_poll_seconds = 60
    settings.claude_cmd = "claude"
    settings.claude_timeout_seconds = 600
    return settings


# ─── Stock Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def sample_stock():
    """Sample stock data structure."""
    return {
        "id": 1,
        "ticker": "NVDA",
        "name": "NVIDIA",
        "sector": "Technology",
        "is_enabled": True,
        "state": "analysis",
        "default_analysis_type": "earnings",
        "priority": 9,
        "tags": ["mega_cap", "ai", "semiconductors"],
        "next_earnings_date": None,
        "max_position_pct": 6.0,
    }


@pytest.fixture
def sample_stocks_list(sample_stock):
    """List of sample stocks."""
    return [
        sample_stock,
        {
            "id": 2,
            "ticker": "AAPL",
            "name": "Apple",
            "sector": "Technology",
            "is_enabled": True,
            "state": "analysis",
            "default_analysis_type": "stock",
            "priority": 7,
            "tags": ["mega_cap", "tech", "consumer"],
            "next_earnings_date": None,
            "max_position_pct": 6.0,
        },
    ]


# ─── Schedule Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def sample_schedule():
    """Sample schedule data structure."""
    return MagicMock(
        id=1,
        name="Test Schedule",
        task_type="analyze_stock",
        frequency="daily",
        is_enabled=True,
        target_ticker="NVDA",
        analysis_type="earnings",
        auto_execute=False,
        next_run_at=None,
        consecutive_fails=0,
        max_consecutive_fails=3,
    )


# ─── Analysis Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def sample_analysis_result():
    """Sample analysis result structure."""
    return {
        "gate_passed": True,
        "recommendation": "BUY",
        "confidence": 75,
        "expected_value_pct": 12.5,
        "entry_price": 125.00,
        "stop_loss": 118.75,
        "target_price": 143.75,
        "position_size_pct": 3.0,
        "structure": "call_spread",
        "rationale": "Strong earnings momentum, beat history, low IV",
    }


# ─── Path Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def tmp_analyses_dir(tmp_path):
    """Create temporary analyses directory."""
    analyses_dir = tmp_path / "analyses"
    analyses_dir.mkdir()
    return analyses_dir


@pytest.fixture
def tmp_trades_dir(tmp_path):
    """Create temporary trades directory."""
    trades_dir = tmp_path / "trades"
    trades_dir.mkdir()
    return trades_dir
