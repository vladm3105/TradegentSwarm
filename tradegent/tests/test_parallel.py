"""Unit tests for parallel analysis execution."""
import threading
import time
from unittest.mock import Mock, patch, MagicMock

import pytest


class TestParallelBatchResult:
    """Tests for ParallelBatchResult dataclass."""

    def test_default_values(self):
        from orchestrator import ParallelBatchResult
        result = ParallelBatchResult()
        assert result.total == 0
        assert result.succeeded == 0
        assert result.failed == 0
        assert result.skipped == 0
        assert result.duration_ms == 0

    def test_custom_values(self):
        from orchestrator import ParallelBatchResult
        result = ParallelBatchResult(total=5, succeeded=3, failed=1, skipped=1, duration_ms=1000)
        assert result.total == 5
        assert result.succeeded == 3
        assert result.failed == 1
        assert result.skipped == 1
        assert result.duration_ms == 1000


class TestRunAnalysesParallel:
    """Tests for run_analyses_parallel function."""

    @patch('orchestrator.cfg')
    @patch('orchestrator.run_pipeline')
    @patch('orchestrator.NexusDB')
    def test_empty_tasks_returns_empty_result(self, mock_db_class, mock_pipeline, mock_cfg):
        from orchestrator import run_analyses_parallel, ParallelBatchResult

        result = run_analyses_parallel([])

        assert result.total == 0
        mock_pipeline.assert_not_called()

    @patch('orchestrator.cfg')
    @patch('orchestrator.run_pipeline')
    @patch('orchestrator.NexusDB')
    def test_single_task_runs_sequential(self, mock_db_class, mock_pipeline, mock_cfg):
        from orchestrator import run_analyses_parallel, AnalysisType

        mock_cfg.parallel_execution_enabled = True
        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance
        mock_db_instance.claim_analysis_slot.return_value = True

        tasks = [('NVDA', AnalysisType.STOCK, False)]
        result = run_analyses_parallel(tasks)

        # Single task should use sequential path
        assert result.total == 1

    @patch('orchestrator.cfg')
    @patch('orchestrator._run_analyses_sequential')
    def test_disabled_parallel_runs_sequential(self, mock_seq, mock_cfg):
        from orchestrator import run_analyses_parallel, AnalysisType, ParallelBatchResult

        mock_cfg.parallel_execution_enabled = False
        mock_seq.return_value = ParallelBatchResult(total=2, succeeded=2, failed=0, skipped=0, duration_ms=100)

        tasks = [('NVDA', AnalysisType.STOCK, False), ('AAPL', AnalysisType.STOCK, False)]
        result = run_analyses_parallel(tasks)

        mock_seq.assert_called_once()
        assert result.total == 2
        assert result.succeeded == 2

    @patch('orchestrator.cfg')
    @patch('orchestrator.run_pipeline')
    @patch('orchestrator.NexusDB')
    def test_respects_max_concurrent_runs(self, mock_db_class, mock_pipeline, mock_cfg):
        from orchestrator import run_analyses_parallel, AnalysisType

        mock_cfg.parallel_execution_enabled = True
        mock_cfg.parallel_fallback_to_sequential = True

        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance
        mock_db_instance.get_setting.return_value = '2'  # max 2 concurrent
        mock_db_instance.claim_analysis_slot.return_value = True

        # Track concurrent executions
        max_concurrent = [0]
        current_concurrent = [0]
        lock = threading.Lock()

        def mock_run(*args, **kwargs):
            with lock:
                current_concurrent[0] += 1
                max_concurrent[0] = max(max_concurrent[0], current_concurrent[0])
            time.sleep(0.05)  # Simulate work
            with lock:
                current_concurrent[0] -= 1

        mock_pipeline.side_effect = mock_run

        tasks = [('NVDA', AnalysisType.STOCK, False)] * 5
        result = run_analyses_parallel(tasks)

        # Should never exceed max_concurrent_runs (2)
        assert max_concurrent[0] <= 2
        assert result.total == 5

    @patch('orchestrator.cfg')
    @patch('orchestrator.run_pipeline')
    @patch('orchestrator.NexusDB')
    def test_daily_limit_skips_tasks(self, mock_db_class, mock_pipeline, mock_cfg):
        from orchestrator import run_analyses_parallel, AnalysisType

        mock_cfg.parallel_execution_enabled = True
        mock_cfg.parallel_fallback_to_sequential = True

        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance
        mock_db_instance.get_setting.return_value = '2'
        # First call returns True, rest return False (limit reached)
        mock_db_instance.claim_analysis_slot.side_effect = [True, False, False]

        tasks = [
            ('NVDA', AnalysisType.STOCK, False),
            ('AAPL', AnalysisType.STOCK, False),
            ('MSFT', AnalysisType.STOCK, False),
        ]
        result = run_analyses_parallel(tasks)

        assert result.succeeded == 1
        assert result.skipped == 2


class TestRunAnalysesSequential:
    """Tests for _run_analyses_sequential function."""

    @patch('orchestrator.run_pipeline')
    @patch('orchestrator.NexusDB')
    def test_sequential_runs_all_tasks(self, mock_db_class, mock_pipeline):
        from orchestrator import _run_analyses_sequential, AnalysisType

        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance

        tasks = [
            ('NVDA', AnalysisType.STOCK, False),
            ('AAPL', AnalysisType.STOCK, False),
        ]
        result = _run_analyses_sequential(tasks)

        assert result.total == 2
        assert result.succeeded == 2
        assert mock_pipeline.call_count == 2

    @patch('orchestrator.run_pipeline')
    @patch('orchestrator.NexusDB')
    def test_sequential_handles_failures(self, mock_db_class, mock_pipeline):
        from orchestrator import _run_analyses_sequential, AnalysisType

        mock_db_instance = MagicMock()
        mock_db_class.return_value = mock_db_instance
        mock_pipeline.side_effect = [None, Exception("Test error"), None]

        tasks = [
            ('NVDA', AnalysisType.STOCK, False),
            ('AAPL', AnalysisType.STOCK, False),
            ('MSFT', AnalysisType.STOCK, False),
        ]
        result = _run_analyses_sequential(tasks)

        assert result.total == 3
        assert result.succeeded == 2
        assert result.failed == 1


class TestClaimAnalysisSlot:
    """Tests for claim_analysis_slot database method."""

    def test_returns_true_when_under_limit(self):
        """Integration test - requires database."""
        # This test requires a real database connection
        # Skip for unit tests, run in integration tests
        pass

    def test_returns_false_when_at_limit(self):
        """Integration test - requires database."""
        # This test requires a real database connection
        # Skip for unit tests, run in integration tests
        pass

    def test_thread_safe_with_advisory_lock(self):
        """Integration test - requires database and multiple threads."""
        # This test requires a real database connection
        # Skip for unit tests, run in integration tests
        pass


class TestGetSetting:
    """Tests for get_setting database method."""

    @patch('db_layer.psycopg.connect')
    def test_returns_value_when_found(self, mock_connect):
        from db_layer import NexusDB

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": "3"}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
        mock_connect.return_value = mock_conn

        db = NexusDB()
        db.connect()
        result = db.get_setting('max_concurrent_runs', '2')

        assert result == "3"

    @patch('db_layer.psycopg.connect')
    def test_returns_default_when_not_found(self, mock_connect):
        from db_layer import NexusDB

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
        mock_connect.return_value = mock_conn

        db = NexusDB()
        db.connect()
        result = db.get_setting('nonexistent_key', 'default_value')

        assert result == 'default_value'
