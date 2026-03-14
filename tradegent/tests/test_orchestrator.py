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

        with patch("orchestrator.NexusDB", return_value=mock_nexus_db):
            from orchestrator import Settings

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

        with patch("orchestrator.NexusDB", return_value=mock_nexus_db):
            from orchestrator import Settings

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


class TestAgentEngineValidation:
    """Test AGENT_ENGINE validation behavior."""

    def test_validate_agent_engine_legacy(self, monkeypatch):
        from orchestrator import validate_agent_engine

        monkeypatch.setenv("AGENT_ENGINE", "legacy")
        assert validate_agent_engine() == "legacy"

    def test_validate_agent_engine_invalid(self, monkeypatch):
        from orchestrator import validate_agent_engine

        monkeypatch.setenv("AGENT_ENGINE", "invalid")
        with pytest.raises(RuntimeError, match="Unsupported AGENT_ENGINE"):
            validate_agent_engine()


class TestJsonParsing:
    """Test JSON block parsing."""

    def test_parse_json_block_valid(self):
        """Test parsing valid JSON block from output."""
        from orchestrator import parse_json_block

        output = """
Some analysis text here...

```json
{
    "ticker": "NVDA",
    "gate_passed": true,
    "recommendation": "BUY",
    "confidence": 75,
    "expected_value_pct": 12.5
}
```
"""
        result = parse_json_block(output)

        assert result is not None
        assert result.get("gate_passed") is True
        assert result.get("recommendation") == "BUY"
        assert result.get("confidence") == 75

    def test_parse_json_block_invalid(self):
        """Test parsing invalid JSON block."""
        from orchestrator import parse_json_block

        result = parse_json_block("invalid: [json: broken")

        assert result is None

    def test_parse_json_block_no_fenced_block(self):
        """Test parsing JSON without fenced code block."""
        from orchestrator import parse_json_block

        output = """
Analysis complete.
{"ticker": "NVDA", "gate_passed": false}
"""
        result = parse_json_block(output)

        assert result is not None
        assert result.get("ticker") == "NVDA"
        assert result.get("gate_passed") is False


class TestAnalysisResult:
    """Test AnalysisResult data class."""

    def test_analysis_result_creation(self):
        """Test AnalysisResult dataclass."""
        from pathlib import Path

        from orchestrator import AnalysisResult, AnalysisType

        result = AnalysisResult(
            ticker="NVDA",
            type=AnalysisType.EARNINGS,
            filepath=Path("/tmp/test.md"),
            gate_passed=True,
            recommendation="BUY",
            confidence=75,
            expected_value=12.5,
            raw_output="test output",
        )

        assert result.ticker == "NVDA"
        assert result.gate_passed is True
        assert result.confidence == 75


class TestClaudeCodeExecution:
    """Test Claude Code CLI execution."""

    def test_call_claude_code_success(self, mock_settings):
        """Test successful Claude Code execution."""
        with patch("orchestrator.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="recommendation: BUY\nconfidence: 75",
                stderr="",
            )

            from orchestrator import call_claude_code

            with patch("orchestrator.cfg", mock_settings):
                mock_settings.dry_run_mode = False
                result = call_claude_code(
                    prompt="Analyze NVDA",
                    allowed_tools="mcp__ib-mcp__*",
                    label="test",
                )

            assert result is not None

    def test_call_claude_code_timeout(self, mock_settings):
        """Test Claude Code timeout handling - returns empty string."""
        import subprocess

        with patch("orchestrator.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=600)

            from orchestrator import call_claude_code

            with patch("orchestrator.cfg", mock_settings):
                mock_settings.dry_run_mode = False
                # call_claude_code catches TimeoutExpired and returns empty string
                result = call_claude_code(
                    prompt="Analyze NVDA",
                    allowed_tools="mcp__ib-mcp__*",
                    label="test",
                )
                assert result == ""

    def test_call_claude_code_dry_run(self, mock_settings):
        """Test Claude Code in dry run mode."""
        from orchestrator import call_claude_code

        with patch("orchestrator.cfg", mock_settings):
            mock_settings.dry_run_mode = True
            result = call_claude_code(
                prompt="Analyze NVDA",
                allowed_tools="mcp__ib-mcp__*",
                label="test",
            )
            # Dry run returns empty string without calling subprocess
            assert result == ""


class TestStockCommands:
    """Test stock CLI commands."""

    def test_stock_list_command(self, mock_nexus_db, sample_stocks_list):
        """Test stock list command output."""
        mock_nexus_db.get_all_stocks = MagicMock(return_value=sample_stocks_list)

        # This would test CLI output formatting
        stocks = mock_nexus_db.get_all_stocks()

        assert len(stocks) == 2
        assert stocks[0]["ticker"] == "NVDA"

    def test_stock_add_command(self, mock_nexus_db, mock_db_connection, sample_stock):
        """Test stock add command."""
        _, mock_cursor = mock_db_connection
        # upsert_stock calls get_stock which expects a full stock row
        pltr_stock = sample_stock.copy()
        pltr_stock["ticker"] = "PLTR"
        pltr_stock["name"] = "Palantir"
        pltr_stock["priority"] = 6
        pltr_stock["tags"] = ["ai", "defense"]
        mock_cursor.fetchone.return_value = pltr_stock

        result = mock_nexus_db.upsert_stock(
            ticker="PLTR",
            name="Palantir",
            priority=6,
            tags=["ai", "defense"],
        )

        assert result is not None
        assert result.ticker == "PLTR"


class TestScheduleExecution:
    """Test schedule execution logic."""

    def test_run_due_schedules_empty(self, mock_nexus_db):
        """Test running when no schedules are due."""
        mock_nexus_db.get_due_schedules = MagicMock(return_value=[])
        mock_nexus_db.get_today_run_count = MagicMock(return_value=0)
        mock_nexus_db.recover_stuck_schedule_runs = MagicMock(return_value=0)

        from orchestrator import run_due_schedules

        with patch("orchestrator.cfg") as mock_cfg:
            mock_cfg.dry_run_mode = True
            mock_cfg.max_daily_analyses = 15
            run_due_schedules(mock_nexus_db)

        # Should complete without error
        mock_nexus_db.get_due_schedules.assert_called_once()

    def test_run_due_schedules_with_task(self, mock_nexus_db, sample_schedule):
        """Test running with a due schedule."""
        mock_nexus_db.get_due_schedules = MagicMock(return_value=[sample_schedule])
        mock_nexus_db.get_today_run_count = MagicMock(return_value=0)
        mock_nexus_db.recover_stuck_schedule_runs = MagicMock(return_value=0)
        mock_nexus_db.start_run = MagicMock(return_value=1)
        mock_nexus_db.complete_run = MagicMock()
        mock_nexus_db.update_next_run = MagicMock()
        mock_nexus_db.calculate_next_run = MagicMock(return_value=None)

        from orchestrator import run_due_schedules

        with patch("orchestrator.cfg") as mock_cfg:
            mock_cfg.dry_run_mode = True
            mock_cfg.max_daily_analyses = 15
            mock_cfg._get = MagicMock(return_value="120")

            with patch("orchestrator.run_analysis") as mock_run:
                mock_run.return_value = {"success": True}
                run_due_schedules(mock_nexus_db)

    def test_run_due_schedules_recovers_stale_running_schedules(self, mock_nexus_db):
        """Scheduler should recover stale running schedule runs before executing due jobs."""
        mock_nexus_db.recover_stuck_schedule_runs = MagicMock(return_value=2)
        mock_nexus_db.get_due_schedules = MagicMock(return_value=[])
        mock_nexus_db.get_today_run_count = MagicMock(return_value=0)

        from orchestrator import run_due_schedules

        with patch("orchestrator.cfg") as mock_cfg:
            mock_cfg.max_daily_analyses = 15
            mock_cfg._get = MagicMock(return_value="120")
            run_due_schedules(mock_nexus_db)

        mock_nexus_db.recover_stuck_schedule_runs.assert_called_once_with(120)

    def test_run_due_schedules_tracks_analyze_watchlist(self, mock_nexus_db):
        """Analyze watchlist schedules must update schedule run metadata."""
        sched = MagicMock(
            id=2,
            name="Morning Watchlist Analysis",
            task_type="analyze_watchlist",
            auto_execute=False,
        )
        mock_nexus_db.get_due_schedules = MagicMock(return_value=[sched])
        mock_nexus_db.get_today_run_count = MagicMock(return_value=0)
        mock_nexus_db.calculate_next_run = MagicMock(return_value=None)
        mock_nexus_db.update_next_run = MagicMock()
        mock_nexus_db.mark_schedule_started = MagicMock(return_value=200)
        mock_nexus_db.mark_schedule_completed = MagicMock()

        from orchestrator import run_due_schedules

        with patch("orchestrator.cfg") as mock_cfg:
            mock_cfg.max_daily_analyses = 15
            with patch("orchestrator.run_watchlist") as mock_run_watchlist:
                run_due_schedules(mock_nexus_db)

        mock_run_watchlist.assert_called_once_with(mock_nexus_db, False)
        mock_nexus_db.mark_schedule_started.assert_called_once_with(2)
        mock_nexus_db.mark_schedule_completed.assert_called_once_with(2, 200, "completed")

    def test_run_due_schedules_tracks_run_all_scanners(self, mock_nexus_db):
        """Run-all-scanners schedules must update schedule run metadata."""
        sched = MagicMock(
            id=1,
            name="Pre-Market Earnings Scan",
            task_type="run_all_scanners",
        )
        mock_nexus_db.get_due_schedules = MagicMock(return_value=[sched])
        mock_nexus_db.get_today_run_count = MagicMock(return_value=0)
        mock_nexus_db.calculate_next_run = MagicMock(return_value=None)
        mock_nexus_db.update_next_run = MagicMock()
        mock_nexus_db.mark_schedule_started = MagicMock(return_value=100)
        mock_nexus_db.mark_schedule_completed = MagicMock()

        from orchestrator import run_due_schedules

        with patch("orchestrator.cfg") as mock_cfg:
            mock_cfg.max_daily_analyses = 15
            with patch("orchestrator.run_scanners") as mock_run_scanners:
                run_due_schedules(mock_nexus_db)

        mock_run_scanners.assert_called_once_with(mock_nexus_db)
        mock_nexus_db.mark_schedule_started.assert_called_once_with(1)
        mock_nexus_db.mark_schedule_completed.assert_called_once_with(1, 100, "completed")


class TestScannerRuntimeSelection:
    """Test scanner engine dispatch behavior."""

    def test_run_scanners_uses_adk_not_claude_cli(self, mock_nexus_db):
        """When AGENT_ENGINE=adk, scanner runs must not call Claude CLI directly."""
        scanner = MagicMock(
            scanner_code="HIGH_OPT_IMP_VOLAT",
            display_name="High Implied Volatility",
            auto_add_to_watchlist=False,
            auto_analyze=False,
            max_candidates=5,
        )

        mock_nexus_db.get_enabled_scanners = MagicMock(return_value=[scanner])
        mock_nexus_db.start_scanner_run = MagicMock(return_value=11)
        mock_nexus_db.complete_scanner_run = MagicMock()

        from orchestrator import run_scanners

        with patch("orchestrator.cfg") as mock_cfg:
            mock_cfg.scanners_enabled = True
            mock_cfg.allowed_tools_scanner = "mcp__ib-mcp__*"
            with patch("orchestrator.validate_agent_engine", return_value="adk"):
                with patch(
                    "orchestrator._run_adk_scan_generation",
                    return_value='{"scanner":"HIGH_OPT_IMP_VOLAT","scan_time":"2026-03-12T12:00:00","candidates":[]}',
                ) as mock_adk_scan:
                    with patch("orchestrator.call_claude_code") as mock_cli:
                        run_scanners(mock_nexus_db)

        mock_adk_scan.assert_called_once()
        mock_cli.assert_not_called()


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


class TestPromptBuilders:
    """Test prompt building functions."""

    def test_build_analysis_prompt_earnings(self):
        """Test building earnings analysis prompt."""
        from orchestrator import AnalysisType, build_analysis_prompt

        with patch("orchestrator.build_kb_context", return_value=""):
            prompt = build_analysis_prompt("NVDA", AnalysisType.EARNINGS)

            assert "NVDA" in prompt
            assert "earnings" in prompt.lower()
            assert "json" in prompt.lower()

    def test_build_analysis_prompt_stock(self):
        """Test building stock analysis prompt."""
        from orchestrator import AnalysisType, build_analysis_prompt

        with patch("orchestrator.build_kb_context", return_value=""):
            prompt = build_analysis_prompt("AAPL", AnalysisType.STOCK)

            assert "AAPL" in prompt
            assert "stock" in prompt.lower()

    def test_build_scanner_prompt(self):
        """Test building scanner prompt."""
        from orchestrator import build_scanner_prompt

        scanner = MagicMock()
        scanner.scanner_code = "TEST_SCANNER"
        scanner.display_name = "Test Scanner"
        scanner.instrument = "STK"
        scanner.location = "STK.US.MAJOR"
        scanner.num_results = 50
        scanner.max_candidates = 10
        scanner.filters = {}

        prompt = build_scanner_prompt(scanner)

        assert "TEST_SCANNER" in prompt
        assert "json" in prompt.lower()


class TestAnalysisType:
    """Test AnalysisType enum."""

    def test_analysis_type_values(self):
        """Test AnalysisType enum values."""
        from orchestrator import AnalysisType

        assert AnalysisType.EARNINGS.value == "earnings"
        assert AnalysisType.STOCK.value == "stock"
        assert AnalysisType.SCAN.value == "scan"
        assert AnalysisType.REVIEW.value == "review"
        assert AnalysisType.POSTMORTEM.value == "postmortem"
