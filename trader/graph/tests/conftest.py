"""Pytest fixtures for graph layer tests."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


@pytest.fixture
def sample_earnings_yaml():
    """Load sample earnings analysis fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_earnings.yaml"
    with open(fixture_path, "r") as f:
        return f.read()


@pytest.fixture
def sample_trade_yaml():
    """Load sample trade journal fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_trade.yaml"
    with open(fixture_path, "r") as f:
        return f.read()


@pytest.fixture
def sample_research_yaml():
    """Load sample research analysis fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_research.yaml"
    with open(fixture_path, "r") as f:
        return f.read()


@pytest.fixture
def mock_neo4j():
    """Mock Neo4j driver for unit tests."""
    with patch("graph.layer.GraphDatabase") as mock_db:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()

        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = mock_result
        mock_db.driver.return_value = mock_driver

        yield {
            "driver": mock_driver,
            "session": mock_session,
            "result": mock_result,
        }


@pytest.fixture
def mock_ollama():
    """Mock Ollama API for extraction tests."""
    with patch("graph.extract._call_ollama_rate_limited") as mock:
        mock.return_value = '[]'
        yield mock


@pytest.fixture
def mock_config():
    """Mock graph configuration."""
    config = {
        "extraction": {
            "commit_threshold": 0.7,
            "flag_threshold": 0.5,
            "timeout_seconds": 30,
            "ollama": {
                "base_url": "http://localhost:11434",
                "model": "qwen3:8b",
            },
        },
        "logging": {
            "extraction_log": "logs/graph_extractions.jsonl",
            "pending_commits": "logs/pending_commits.jsonl",
        },
    }
    with patch("graph.extract._config", config):
        yield config
