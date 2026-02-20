# Testing Guide

This guide covers the test structure, fixtures, mocking patterns, and best practices for TradegentSwarm.

## Test Structure

```
tradegent/
├── conftest.py                    # Root pytest config (registers options)
├── tests/                         # Core platform tests
│   ├── conftest.py               # Shared fixtures
│   ├── test_db_layer.py          # Database layer tests
│   └── test_orchestrator.py      # Orchestrator tests
├── rag/tests/                     # RAG module tests
│   ├── conftest.py               # RAG-specific fixtures
│   ├── test_chunk.py             # Chunking tests
│   ├── test_embed.py             # Embedding tests
│   ├── test_embedding.py         # Embedding client tests
│   └── test_integration.py       # Integration tests
└── graph/tests/                   # Graph module tests
    ├── conftest.py               # Graph-specific fixtures
    ├── test_extract.py           # Extraction tests
    ├── test_layer.py             # Graph layer tests
    └── test_integration.py       # Integration tests
```

## Running Tests

### All Unit Tests

```bash
cd tradegent
python -m pytest -v
```

### Specific Test File

```bash
python -m pytest tests/test_orchestrator.py -v
```

### Specific Test Class or Function

```bash
python -m pytest tests/test_orchestrator.py::TestSettings -v
python -m pytest tests/test_orchestrator.py::TestSettings::test_settings_initialization -v
```

### Integration Tests

Integration tests require running PostgreSQL and Neo4j. Use the `--run-integration` flag:

```bash
# Start infrastructure first
docker compose up -d

# Run integration tests
python -m pytest --run-integration -m integration -v
```

### Test with Coverage

```bash
python -m pytest --cov=. --cov-report=term-missing
```

### Skip Slow Tests

```bash
python -m pytest -m "not slow" -v
```

---

## Test Categories (Markers)

Tests are categorized using pytest markers:

| Marker | Description | Usage |
|--------|-------------|-------|
| `unit` | No external dependencies | Default, always run |
| `integration` | Requires PostgreSQL/Neo4j | Use `--run-integration` |
| `slow` | Takes >10 seconds | Skip with `-m "not slow"` |

### Marking Tests

```python
import pytest

@pytest.mark.integration
def test_real_database_connection():
    """This test requires a running PostgreSQL."""
    pass

@pytest.mark.slow
def test_full_embedding_pipeline():
    """This test embeds a large document."""
    pass
```

---

## Shared Fixtures

### Database Fixtures (tests/conftest.py)

#### mock_db_connection

Provides a mocked PostgreSQL connection and cursor.

```python
def test_example(mock_db_connection):
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = {"id": 1, "ticker": "NVDA"}
    # ... use in test
```

#### mock_nexus_db

Provides a mocked `NexusDB` instance with connection set up.

```python
def test_get_stock(mock_nexus_db, mock_db_connection, sample_stock):
    _, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = sample_stock

    result = mock_nexus_db.get_stock("NVDA")

    assert result is not None
    assert result.ticker == "NVDA"
```

### Sample Data Fixtures

#### sample_stock

Returns a dictionary representing a stock row:

```python
{
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
```

#### sample_stocks_list

Returns a list of two sample stocks (NVDA and AAPL).

#### sample_schedule

Returns a `MagicMock` schedule object:

```python
MagicMock(
    id=1,
    name="Test Schedule",
    task_type="analyze_stock",
    frequency="daily",
    is_enabled=True,
    target_ticker="NVDA",
    analysis_type="earnings",
    auto_execute=False,
    consecutive_fails=0,
    max_consecutive_fails=3,
)
```

#### sample_analysis_result

Returns a dictionary representing analysis output:

```python
{
    "gate_passed": True,
    "recommendation": "BUY",
    "confidence": 75,
    "expected_value_pct": 12.5,
    "entry_price": 125.00,
    "stop_loss": 118.75,
    "target_price": 143.75,
    "position_size_pct": 3.0,
    "structure": "call_spread",
    "rationale": "Strong earnings momentum",
}
```

### Path Fixtures

#### tmp_analyses_dir / tmp_trades_dir

Create temporary directories for test output files:

```python
def test_save_analysis(tmp_analyses_dir):
    filepath = tmp_analyses_dir / "NVDA_test.md"
    filepath.write_text("test content")
    assert filepath.exists()
```

---

## Mocking Patterns

### Mocking Database Cursor

The database returns dictionaries (from psycopg's dict_row factory). Mock return values accordingly:

```python
def test_health_check_healthy(mock_nexus_db, mock_db_connection):
    _, mock_cursor = mock_db_connection
    # Return dict with expected keys
    mock_cursor.fetchone.return_value = {"cnt": 5}

    result = mock_nexus_db.health_check()

    assert result is True
```

### Mocking Multiple fetchone Calls

When a method makes multiple database calls, use `side_effect`:

```python
def test_mark_schedule_started(mock_nexus_db, mock_db_connection):
    _, mock_cursor = mock_db_connection
    # First call returns schedule row, second returns run_id
    mock_cursor.fetchone.side_effect = [
        {"task_type": "analyze_stock", "target_ticker": "NVDA"},
        {"id": 1},
    ]

    run_id = mock_nexus_db.mark_schedule_started(schedule_id=1)

    assert run_id == 1
```

### Mocking Settings

```python
def test_with_mock_settings(mock_settings):
    mock_settings.dry_run_mode = True
    mock_settings.max_daily_analyses = 15

    with patch("orchestrator.cfg", mock_settings):
        # Code that uses cfg
        pass
```

### Mocking subprocess (Claude Code CLI)

```python
def test_call_claude_code_success(mock_settings):
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

        assert "BUY" in result
```

### Mocking External APIs

For embedding client tests:

```python
@patch("requests.post")
def test_ollama_embed_success(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {"embeddings": [[0.1] * 1536]}
    mock_post.return_value = mock_response

    # Test embedding code
```

---

## RAG Test Fixtures (rag/tests/conftest.py)

### mock_embedding_client

Mocks the embedding HTTP endpoint:

```python
def test_embed_document(mock_embedding_client):
    # mock_embedding_client returns 1536-dimensional vectors
    pass
```

### mock_config

Provides mock RAG configuration:

```python
config = {
    "embedding": {
        "default_provider": "openai",
        "fallback_chain": ["openai", "ollama"],
        "dimensions": 1536,
        "timeout_seconds": 30,
    },
    "chunking": {
        "max_tokens": 1500,
        "min_tokens": 50,
    },
}
```

### sample_embedding

Returns a 1536-dimensional embedding vector:

```python
def test_search(sample_embedding):
    # sample_embedding is a list of 1536 floats
    assert len(sample_embedding) == 1536
```

---

## Graph Test Fixtures (graph/tests/conftest.py)

### mock_neo4j

Mocks the Neo4j driver:

```python
def test_graph_operation(mock_neo4j):
    mock_session = mock_neo4j["session"]
    mock_session.run.return_value = [{"name": "NVDA"}]
    # Test graph code
```

### mock_ollama

Mocks the Ollama API for extraction tests:

```python
def test_extract(mock_ollama):
    mock_ollama.return_value = '[{"label": "Ticker", "name": "NVDA"}]'
    # Test extraction
```

---

## Writing New Tests

### Test Class Structure

Group related tests in classes:

```python
class TestFeatureName:
    """Test feature description."""

    def test_feature_success(self, fixture1, fixture2):
        """Test feature works in happy path."""
        pass

    def test_feature_error_case(self, fixture1):
        """Test feature handles errors."""
        pass

    def test_feature_edge_case(self):
        """Test feature handles edge cases."""
        pass
```

### Naming Conventions

- Test files: `test_*.py`
- Test classes: `Test*` (PascalCase)
- Test functions: `test_*` (snake_case)
- Descriptive names: `test_parse_json_block_with_invalid_input`

### Assertions

```python
# Basic assertions
assert result is not None
assert result.ticker == "NVDA"
assert len(results) == 5

# Type assertions
assert isinstance(result, Stock)

# Exception assertions
with pytest.raises(ValueError, match="Invalid stock column"):
    mock_nexus_db.upsert_stock("NVDA", invalid_column="value")

# Approximate comparisons (floats)
assert abs(result - expected) < 0.001
```

### Parameterized Tests

```python
@pytest.mark.parametrize("input,expected", [
    ("earnings", AnalysisType.EARNINGS),
    ("stock", AnalysisType.STOCK),
    ("scan", AnalysisType.SCAN),
])
def test_analysis_type_parsing(input, expected):
    from orchestrator import AnalysisType
    assert AnalysisType(input) == expected
```

---

## Integration Test Requirements

Integration tests (marked `@pytest.mark.integration`) require:

1. **PostgreSQL** running on port 5433
2. **Neo4j** running on port 7688
3. **Test database** created and initialized

### Setup for Integration Tests

```bash
# Start infrastructure
docker compose up -d nexus-postgres nexus-neo4j

# Wait for services
sleep 10

# Initialize schemas
python orchestrator.py db-init
python orchestrator.py rag init
python orchestrator.py graph init

# Run integration tests
python -m pytest --run-integration -m integration -v
```

### Skipping Integration Tests

Integration tests are skipped by default. They use this pattern:

```python
@pytest.mark.skipif(
    "not config.getoption('--run-integration')",
    reason="Integration tests require --run-integration flag",
)
def test_real_database():
    pass
```

---

## Coverage Targets

| Component | Target |
|-----------|--------|
| Unit tests | 80% |
| Integration tests | 60% |
| Critical paths | 95% |

### Checking Coverage

```bash
# Full coverage report
python -m pytest --cov=. --cov-report=html
open htmlcov/index.html

# Coverage for specific module
python -m pytest --cov=orchestrator tests/test_orchestrator.py
```

---

## Common Test Patterns

### Testing CLI Commands

```python
def test_stock_list_output(mock_nexus_db, sample_stocks_list, capsys):
    mock_nexus_db.get_enabled_stocks = MagicMock(return_value=sample_stocks_list)

    from orchestrator import show_status
    show_status(mock_nexus_db)

    captured = capsys.readouterr()
    assert "NVDA" in captured.out
```

### Testing File I/O

```python
def test_save_analysis_file(tmp_analyses_dir):
    from orchestrator import save_analysis_file

    analysis_data = {"ticker": "NVDA", "recommendation": "BUY"}
    filepath = tmp_analyses_dir / "NVDA_test.yaml"

    # Save file
    import yaml
    with open(filepath, "w") as f:
        yaml.dump(analysis_data, f)

    assert filepath.exists()
    assert "NVDA" in filepath.read_text()
```

### Testing Async Code

```python
import pytest

@pytest.mark.asyncio
async def test_async_operation():
    result = await some_async_function()
    assert result is not None
```

---

## Troubleshooting Tests

### Test Discovery Issues

```bash
# Show what pytest finds
python -m pytest --collect-only

# Check for import errors
python -c "from orchestrator import Settings"
```

### Fixture Not Found

Ensure the fixture is defined in `conftest.py` in the correct location (same directory or parent).

### Mock Not Working

1. Check patch target path: `patch("module.function")` not `patch("function")`
2. Patch where it's used, not where it's defined
3. Use `autospec=True` to catch signature mismatches

### Environment Variable Issues

Use the `monkeypatch` fixture or `mock_env` autouse fixture:

```python
def test_custom_dsn(monkeypatch):
    monkeypatch.setenv("PG_HOST", "custom-host")
    # Now PG_HOST is set to custom-host
```

---

## CI/CD Integration

Tests run automatically on:
- Pull request creation
- Push to main branch

See `.github/workflows/test.yml` for the CI configuration.

### Running Tests Locally (Like CI)

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests as CI would
python -m pytest -v --tb=short
```
