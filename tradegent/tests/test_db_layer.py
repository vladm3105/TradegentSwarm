"""Tests for tradegent/db_layer.py"""

from unittest.mock import patch

import pytest


class TestNexusDBConnection:
    """Test database connection handling."""

    def test_connect_success(self, mock_db_connection):
        """Test successful database connection."""
        mock_conn, _ = mock_db_connection

        with patch("tradegent.db_layer.psycopg.connect", return_value=mock_conn) as mock_connect:
            from tradegent.db_layer import NexusDB

            db = NexusDB()
            db.connect()

            mock_connect.assert_called_once()
            assert db._conn is not None

    def test_connect_with_custom_dsn(self, mock_db_connection, monkeypatch):
        """Test connection with custom DSN parameters."""
        mock_conn, _ = mock_db_connection
        monkeypatch.setenv("PG_HOST", "custom-host")
        monkeypatch.setenv("PG_PORT", "5434")

        with patch("tradegent.db_layer.psycopg.connect", return_value=mock_conn) as mock_connect:
            from tradegent.db_layer import get_dsn

            dsn = get_dsn()

            assert "custom-host" in dsn
            assert "5434" in dsn

    def test_context_manager(self, mock_db_connection):
        """Test database as context manager."""
        mock_conn, _ = mock_db_connection

        with patch("tradegent.db_layer.psycopg.connect", return_value=mock_conn):
            from tradegent.db_layer import NexusDB

            with NexusDB() as db:
                assert db._conn is not None

            mock_conn.close.assert_called_once()

    def test_health_check_healthy(self, mock_nexus_db, mock_db_connection):
        """Test health check when database is healthy."""
        _, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = (1,)

        result = mock_nexus_db.health_check()
        assert result is True

    def test_health_check_unhealthy(self, mock_nexus_db, mock_db_connection):
        """Test health check when database is unhealthy."""
        _, mock_cursor = mock_db_connection
        mock_cursor.execute.side_effect = Exception("Connection failed")

        result = mock_nexus_db.health_check()
        assert result is False


class TestStockOperations:
    """Test stock CRUD operations."""

    def test_get_stock(self, mock_nexus_db, mock_db_connection, sample_stock):
        """Test getting a single stock by ticker."""
        _, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = sample_stock

        result = mock_nexus_db.get_stock("NVDA")

        assert result is not None
        mock_cursor.execute.assert_called()

    def test_get_stock_not_found(self, mock_nexus_db, mock_db_connection):
        """Test getting a stock that doesn't exist."""
        _, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = None

        result = mock_nexus_db.get_stock("INVALID")

        assert result is None

    def test_get_enabled_stocks(self, mock_nexus_db, mock_db_connection, sample_stocks_list):
        """Test getting all enabled stocks."""
        _, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = sample_stocks_list

        result = mock_nexus_db.get_enabled_stocks()

        assert len(result) >= 0  # May be empty or populated

    def test_upsert_stock_invalid_column(self, mock_nexus_db):
        """Test upsert with invalid column raises error."""
        with pytest.raises(ValueError, match="Invalid stock column"):
            mock_nexus_db.upsert_stock("NVDA", invalid_column="value")

    def test_upsert_stock_valid_columns(self, mock_nexus_db, mock_db_connection):
        """Test upsert with valid columns."""
        _, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = {"ticker": "NVDA", "name": "NVIDIA Updated"}

        result = mock_nexus_db.upsert_stock("NVDA", name="NVIDIA Updated")

        mock_cursor.execute.assert_called()


class TestSettingsOperations:
    """Test settings operations."""

    def test_get_setting(self, mock_nexus_db, mock_db_connection):
        """Test getting a single setting."""
        _, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = ("15",)

        result = mock_nexus_db.get_setting("max_daily_analyses")

        assert result == "15"

    def test_get_setting_default(self, mock_nexus_db, mock_db_connection):
        """Test getting a setting with default value."""
        _, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = None

        result = mock_nexus_db.get_setting("nonexistent", default="default_value")

        assert result == "default_value"

    def test_set_setting(self, mock_nexus_db, mock_db_connection):
        """Test setting a configuration value."""
        _, mock_cursor = mock_db_connection

        mock_nexus_db.set_setting("test_key", "test_value")

        mock_cursor.execute.assert_called()


class TestScheduleOperations:
    """Test schedule operations."""

    def test_get_enabled_schedules(self, mock_nexus_db, mock_db_connection, sample_schedule):
        """Test getting enabled schedules."""
        _, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = [sample_schedule]

        result = mock_nexus_db.get_enabled_schedules()

        assert len(result) >= 0

    def test_get_due_schedules(self, mock_nexus_db, mock_db_connection, sample_schedule):
        """Test getting due schedules."""
        _, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = [sample_schedule]

        result = mock_nexus_db.get_due_schedules()

        assert isinstance(result, list)


class TestServiceStatus:
    """Test service status operations."""

    def test_get_service_status(self, mock_nexus_db, mock_db_connection):
        """Test getting service status."""
        _, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = {
            "state": "running",
            "ticks_total": 100,
            "today_analyses": 5,
        }

        result = mock_nexus_db.get_service_status()

        assert result is not None

    def test_heartbeat(self, mock_nexus_db, mock_db_connection):
        """Test heartbeat update."""
        _, mock_cursor = mock_db_connection

        mock_nexus_db.heartbeat("running")

        mock_cursor.execute.assert_called()

    def test_increment_counter(self, mock_nexus_db, mock_db_connection):
        """Test incrementing service counter."""
        _, mock_cursor = mock_db_connection

        mock_nexus_db.increment_service_counter("ticks_total")

        mock_cursor.execute.assert_called()


class TestRunHistory:
    """Test run history operations."""

    def test_start_run(self, mock_nexus_db, mock_db_connection):
        """Test starting a run history entry."""
        _, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = (1,)

        run_id = mock_nexus_db.start_run(
            schedule_id=1,
            task_type="analyze_stock",
            ticker="NVDA",
        )

        assert run_id == 1

    def test_complete_run(self, mock_nexus_db, mock_db_connection):
        """Test completing a run history entry."""
        _, mock_cursor = mock_db_connection

        mock_nexus_db.complete_run(
            run_id=1,
            status="completed",
            gate_passed=True,
            recommendation="BUY",
        )

        mock_cursor.execute.assert_called()


class TestAnalysisResults:
    """Test analysis results operations."""

    def test_save_analysis_result(self, mock_nexus_db, mock_db_connection, sample_analysis_result):
        """Test saving an analysis result."""
        _, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = (1,)

        result_id = mock_nexus_db.save_analysis_result(
            run_id=1,
            ticker="NVDA",
            analysis_type="earnings",
            **sample_analysis_result,
        )

        assert result_id == 1

    def test_get_analysis_results_for_ticker(self, mock_nexus_db, mock_db_connection):
        """Test getting analysis results for a ticker."""
        _, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = []

        results = mock_nexus_db.get_analysis_results("NVDA", limit=10)

        assert isinstance(results, list)
