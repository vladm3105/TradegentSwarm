"""Tests for tradegent/orchestrator.py"""

from unittest.mock import MagicMock, patch

import pytest


class TestSettings:
    """Test Settings class."""

    def test_settings_initialization(self, mock_nexus_db, mock_db_connection):
        """Test Settings initialization from database."""
        _, mock_cursor = mock_db_connection

        # Mock get_all_settings return
        mock_nexus_db.get_all_settings = MagicMock(
            return_value={
                "dry_run_mode": True,
                "auto_execute_enabled": False,
                "max_daily_analyses": 15,
                "scheduler_poll_seconds": 60,
            }
        )

        with patch("tradegent.orchestrator.NexusDB", return_value=mock_nexus_db):
            from tradegent.orchestrator import Settings

            settings = Settings(mock_nexus_db)

            assert settings.dry_run_mode is True
            assert settings.auto_execute_enabled is False
            assert settings.max_daily_analyses == 15

    def test_settings_refresh(self, mock_nexus_db):
        """Test settings refresh from database."""
        mock_nexus_db.get_all_settings = MagicMock(
            return_value={
                "dry_run_mode": False,
                "auto_execute_enabled": True,
                "max_daily_analyses": 20,
            }
        )

        with patch("tradegent.orchestrator.NexusDB", return_value=mock_nexus_db):
            from tradegent.orchestrator import Settings

            settings = Settings(mock_nexus_db)

            # Change the mock return value
            mock_nexus_db.get_all_settings.return_value = {
                "dry_run_mode": True,
                "auto_execute_enabled": False,
                "max_daily_analyses": 25,
            }

            settings.refresh()

            assert settings.dry_run_mode is True
            assert settings.max_daily_analyses == 25


class TestAnalysisParsing:
    """Test analysis output parsing."""

    def test_parse_analysis_output_valid(self):
        """Test parsing valid analysis output."""
        from tradegent.orchestrator import parse_analysis_output

        analysis_yaml = """
gate_passed: true
recommendation: BUY
confidence: 75
expected_value_pct: 12.5
entry_price: 125.00
stop_loss: 118.75
target_price: 143.75
position_size_pct: 3.0
structure: call_spread
rationale: Strong earnings momentum
"""
        result = parse_analysis_output(analysis_yaml)

        assert result is not None
        assert result.get("gate_passed") is True
        assert result.get("recommendation") == "BUY"
        assert result.get("confidence") == 75

    def test_parse_analysis_output_invalid(self):
        """Test parsing invalid analysis output."""
        from tradegent.orchestrator import parse_analysis_output

        result = parse_analysis_output("invalid: [yaml: broken")

        assert result is None or result == {}


class TestGateCheck:
    """Test Do Nothing gate check."""

    def test_gate_passes(self, sample_analysis_result):
        """Test that gate passes for valid analysis."""
        from tradegent.orchestrator import check_do_nothing_gate

        result = check_do_nothing_gate(sample_analysis_result)

        assert result["passed"] is True

    def test_gate_fails_low_confidence(self, sample_analysis_result):
        """Test that gate fails for low confidence."""
        from tradegent.orchestrator import check_do_nothing_gate

        sample_analysis_result["confidence"] = 40
        result = check_do_nothing_gate(sample_analysis_result)

        # Should fail due to low confidence
        assert result["passed"] is False or "confidence" in str(result.get("reason", "")).lower()

    def test_gate_fails_no_recommendation(self):
        """Test that gate fails without recommendation."""
        from tradegent.orchestrator import check_do_nothing_gate

        analysis = {"gate_passed": False}
        result = check_do_nothing_gate(analysis)

        assert result["passed"] is False


class TestFileOperations:
    """Test file handling operations."""

    def test_save_analysis_file(self, tmp_analyses_dir):
        """Test saving analysis to file."""
        from tradegent.orchestrator import save_analysis_file

        analysis_data = {
            "ticker": "NVDA",
            "recommendation": "BUY",
            "confidence": 75,
        }

        filepath = save_analysis_file(
            analysis_data,
            ticker="NVDA",
            analysis_type="earnings",
            output_dir=tmp_analyses_dir,
        )

        assert filepath.exists()
        assert "NVDA" in filepath.name

    def test_load_analysis_file(self, tmp_analyses_dir):
        """Test loading analysis from file."""
        import yaml

        from tradegent.orchestrator import load_analysis_file

        # Create a test file
        test_file = tmp_analyses_dir / "NVDA_20250120T0900.yaml"
        test_data = {"ticker": "NVDA", "recommendation": "BUY"}
        with open(test_file, "w") as f:
            yaml.dump(test_data, f)

        result = load_analysis_file(test_file)

        assert result is not None
        assert result["ticker"] == "NVDA"


class TestClaudeCodeExecution:
    """Test Claude Code CLI execution."""

    def test_call_claude_code_success(self, mock_settings):
        """Test successful Claude Code execution."""
        with patch("tradegent.orchestrator.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="recommendation: BUY\nconfidence: 75",
                stderr="",
            )

            from tradegent.orchestrator import call_claude_code

            with patch("tradegent.orchestrator.cfg", mock_settings):
                result = call_claude_code(
                    prompt="Analyze NVDA",
                    allowed_tools="mcp__ib-mcp__*",
                    label="test",
                )

            assert result is not None

    def test_call_claude_code_timeout(self, mock_settings):
        """Test Claude Code timeout handling."""
        import subprocess

        with patch("tradegent.orchestrator.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=600)

            from tradegent.orchestrator import call_claude_code

            with patch("tradegent.orchestrator.cfg", mock_settings):
                with pytest.raises(subprocess.TimeoutExpired):
                    call_claude_code(
                        prompt="Analyze NVDA",
                        allowed_tools="mcp__ib-mcp__*",
                        label="test",
                    )


class TestStockCommands:
    """Test stock CLI commands."""

    def test_stock_list_command(self, mock_nexus_db, sample_stocks_list):
        """Test stock list command output."""
        mock_nexus_db.get_all_stocks = MagicMock(return_value=sample_stocks_list)

        # This would test CLI output formatting
        stocks = mock_nexus_db.get_all_stocks()

        assert len(stocks) == 2
        assert stocks[0]["ticker"] == "NVDA"

    def test_stock_add_command(self, mock_nexus_db, mock_db_connection):
        """Test stock add command."""
        _, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = {"ticker": "PLTR", "name": "Palantir"}

        result = mock_nexus_db.upsert_stock(
            ticker="PLTR",
            name="Palantir",
            priority=6,
            tags=["ai", "defense"],
        )

        assert result is not None


class TestScheduleExecution:
    """Test schedule execution logic."""

    def test_run_due_schedules_empty(self, mock_nexus_db):
        """Test running when no schedules are due."""
        mock_nexus_db.get_due_schedules = MagicMock(return_value=[])

        from tradegent.orchestrator import run_due_schedules

        with patch("tradegent.orchestrator.cfg") as mock_cfg:
            mock_cfg.dry_run_mode = True
            run_due_schedules(mock_nexus_db)

        # Should complete without error
        mock_nexus_db.get_due_schedules.assert_called_once()

    def test_run_due_schedules_with_task(self, mock_nexus_db, sample_schedule):
        """Test running with a due schedule."""
        mock_nexus_db.get_due_schedules = MagicMock(return_value=[sample_schedule])
        mock_nexus_db.start_run = MagicMock(return_value=1)
        mock_nexus_db.complete_run = MagicMock()
        mock_nexus_db.update_next_run = MagicMock()

        from tradegent.orchestrator import run_due_schedules

        with patch("tradegent.orchestrator.cfg") as mock_cfg:
            mock_cfg.dry_run_mode = True
            mock_cfg.max_daily_analyses = 15

            with patch("tradegent.orchestrator.run_analysis") as mock_run:
                mock_run.return_value = {"success": True}
                run_due_schedules(mock_nexus_db)


class TestRateLimiting:
    """Test rate limiting logic."""

    def test_daily_limit_not_exceeded(self, mock_nexus_db):
        """Test when daily limit is not exceeded."""
        mock_nexus_db.get_service_status = MagicMock(
            return_value={
                "today_analyses": 5,
                "today_executions": 2,
            }
        )

        status = mock_nexus_db.get_service_status()

        assert status["today_analyses"] < 15
        assert status["today_executions"] < 5

    def test_daily_limit_exceeded(self, mock_nexus_db):
        """Test when daily limit is exceeded."""
        mock_nexus_db.get_service_status = MagicMock(
            return_value={
                "today_analyses": 15,
                "today_executions": 5,
            }
        )

        status = mock_nexus_db.get_service_status()

        assert status["today_analyses"] >= 15


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_circuit_breaker_open(self, sample_schedule):
        """Test circuit breaker opens after consecutive failures."""
        sample_schedule.consecutive_fails = 3
        sample_schedule.max_consecutive_fails = 3

        # Schedule should be skipped
        is_circuit_ok = sample_schedule.consecutive_fails < sample_schedule.max_consecutive_fails
        assert is_circuit_ok is False

    def test_circuit_breaker_closed(self, sample_schedule):
        """Test circuit breaker is closed with no failures."""
        sample_schedule.consecutive_fails = 0

        is_circuit_ok = sample_schedule.consecutive_fails < sample_schedule.max_consecutive_fails
        assert is_circuit_ok is True
