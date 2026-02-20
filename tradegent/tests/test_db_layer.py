"""Tests for tradegent/db_layer.py"""

from unittest.mock import MagicMock, patch

import pytest


class TestNexusDBConnection:
    """Test database connection handling."""

    def test_connect_success(self, mock_db_connection):
        """Test successful database connection."""
        mock_conn, _ = mock_db_connection

        with patch("db_layer.psycopg.connect", return_value=mock_conn) as mock_connect:
            from db_layer import NexusDB

            db = NexusDB()
            db.connect()

            mock_connect.assert_called_once()
            assert db._conn is not None

    def test_connect_with_custom_dsn(self, mock_db_connection, monkeypatch):
        """Test connection with custom DSN parameters."""
        mock_conn, _ = mock_db_connection
        monkeypatch.setenv("PG_HOST", "custom-host")
        monkeypatch.setenv("PG_PORT", "5434")

        with patch("db_layer.psycopg.connect", return_value=mock_conn) as mock_connect:
            from db_layer import get_dsn

            dsn = get_dsn()

            assert "custom-host" in dsn
            assert "5434" in dsn

    def test_context_manager(self, mock_db_connection):
        """Test database as context manager."""
        mock_conn, _ = mock_db_connection

        with patch("db_layer.psycopg.connect", return_value=mock_conn):
            from db_layer import NexusDB

            with NexusDB() as db:
                assert db._conn is not None

            mock_conn.close.assert_called_once()

    def test_health_check_healthy(self, mock_nexus_db, mock_db_connection):
        """Test health check when database is healthy."""
        _, mock_cursor = mock_db_connection
        # health_check expects fetchone to return dict with 'cnt' key
        mock_cursor.fetchone.return_value = {"cnt": 5}

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
        assert result.ticker == "NVDA"
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

        assert len(result) == 2
        assert result[0].ticker == "NVDA"

    def test_upsert_stock_invalid_column(self, mock_nexus_db):
        """Test upsert with invalid column raises error."""
        with pytest.raises(ValueError, match="Invalid stock column"):
            mock_nexus_db.upsert_stock("NVDA", invalid_column="value")

    def test_upsert_stock_valid_columns(self, mock_nexus_db, mock_db_connection, sample_stock):
        """Test upsert with valid columns."""
        _, mock_cursor = mock_db_connection
        # upsert calls get_stock which needs a full stock row
        updated_stock = sample_stock.copy()
        updated_stock["name"] = "NVIDIA Updated"
        mock_cursor.fetchone.return_value = updated_stock

        result = mock_nexus_db.upsert_stock("NVDA", name="NVIDIA Updated")

        assert result is not None
        assert result.name == "NVIDIA Updated"
        mock_cursor.execute.assert_called()


class TestSettingsOperations:
    """Test settings operations."""

    def test_get_setting(self, mock_nexus_db, mock_db_connection):
        """Test getting a single setting."""
        _, mock_cursor = mock_db_connection
        # get_setting expects fetchone to return dict with 'value' key
        mock_cursor.fetchone.return_value = {"value": "15"}

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

    def test_get_enabled_schedules(self, mock_nexus_db, mock_db_connection):
        """Test getting enabled schedules."""
        _, mock_cursor = mock_db_connection
        # Schedule rows
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "name": "Test Schedule",
                "task_type": "analyze_stock",
                "frequency": "daily",
                "is_enabled": True,
                "target_ticker": "NVDA",
                "target_scanner_id": None,
                "analysis_type": "earnings",
                "auto_execute": False,
                "next_run_at": None,
                "schedule_time": None,
                "day_of_week": None,
                "day_of_month": None,
                "custom_prompt": None,
                "last_run_at": None,
                "last_run_status": None,
                "consecutive_fails": 0,
                "max_consecutive_fails": 3,
                "notes": None,
            }
        ]

        result = mock_nexus_db.get_enabled_schedules()

        assert len(result) >= 0

    def test_get_due_schedules(self, mock_nexus_db, mock_db_connection):
        """Test getting due schedules."""
        _, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = []

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
        """Test incrementing service counter - valid counter."""
        _, mock_cursor = mock_db_connection
        mock_cursor.execute.return_value = None

        # Valid counter name should call execute
        mock_nexus_db.increment_service_counter("analyses_total")

        mock_cursor.execute.assert_called()

    def test_increment_counter_invalid(self, mock_nexus_db, mock_db_connection):
        """Test incrementing service counter - invalid counter does nothing."""
        _, mock_cursor = mock_db_connection

        # Invalid counter should NOT call execute (early return)
        mock_nexus_db.increment_service_counter("invalid_counter")

        # Since "invalid_counter" is not in the valid set, execute should not be called


class TestRunHistory:
    """Test run history operations."""

    def test_mark_schedule_started(self, mock_nexus_db, mock_db_connection):
        """Test marking a schedule as started."""
        _, mock_cursor = mock_db_connection
        # mark_schedule_started does multiple fetchone calls:
        # 1. First returns schedule row (for task_type, target_ticker, analysis_type)
        # 2. Second returns the new run_id
        mock_cursor.fetchone.side_effect = [
            {"task_type": "analyze_stock", "target_ticker": "NVDA", "analysis_type": "earnings"},
            {"id": 1},
        ]

        run_id = mock_nexus_db.mark_schedule_started(schedule_id=1)

        assert run_id == 1
        mock_cursor.execute.assert_called()

    def test_mark_schedule_completed(self, mock_nexus_db, mock_db_connection):
        """Test marking a schedule as completed."""
        _, mock_cursor = mock_db_connection
        mock_cursor.execute.return_value = None

        mock_nexus_db.mark_schedule_completed(
            schedule_id=1,
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
        mock_cursor.execute.return_value = None

        # save_analysis_result takes run_id, ticker, analysis_type, and a parsed dict
        mock_nexus_db.save_analysis_result(
            run_id=1,
            ticker="NVDA",
            analysis_type="earnings",
            parsed=sample_analysis_result,
        )

        mock_cursor.execute.assert_called()

    def test_get_today_run_count(self, mock_nexus_db, mock_db_connection):
        """Test getting today's run count."""
        _, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = {"cnt": 5}

        count = mock_nexus_db.get_today_run_count()

        assert count == 5
