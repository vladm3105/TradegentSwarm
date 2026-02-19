# Fix Development Gaps for MCP Trading Graph

## Overview

Add missing tests for webhook handlers and rate limiting logic, plus configure coverage reports.

## Gaps to Fix

| Gap | Solution | Priority |
|-----|----------|----------|
| Webhook handlers not tested | Create `test_webhook.py` | High |
| Rate limiting logic not tested | Create `test_rate_limit.py` | High |
| No coverage reports configured | Create `.coveragerc` + update `pytest.ini` | Medium |

## Files to Create/Modify

| File | Action |
|------|--------|
| `trader/graph/tests/test_webhook.py` | Create (~200 lines) |
| `trader/graph/tests/test_rate_limit.py` | Create (~120 lines) |
| `trader/.coveragerc` | Create |
| `trader/pytest.ini` | Modify (add coverage flags) |
| `trader/graph/tests/conftest.py` | Modify (add 2 fixtures) |

## Implementation Details

### 1. Webhook Tests (`test_webhook.py`)

Test 12 FastAPI endpoints from `webhook.py`:

| Endpoint | Test Classes |
|----------|--------------|
| `POST /api/graph/extract` | Success, ExtractionError→400, GraphUnavailableError→503 |
| `POST /api/graph/extract-text` | Success, ExtractionError→400 |
| `POST /api/graph/query` | Success, GraphUnavailableError→503, Exception→400 |
| `GET /api/graph/status` | Success, GraphUnavailableError→503 |
| `GET /api/graph/ticker/{symbol}` | Success, symbol uppercase |
| `GET /api/graph/ticker/{symbol}/peers` | Success |
| `GET /api/graph/ticker/{symbol}/risks` | Success |
| `GET /api/graph/ticker/{symbol}/competitors` | Success |
| `GET /api/graph/biases` | Success, optional name param |
| `GET /api/graph/strategies` | Success, optional name param |
| `GET /api/graph/health` | Healthy, unhealthy |
| `GET /api/graph/ready` | Ready, not ready→503 |

Uses `TestClient` from `starlette.testclient` (bundled with FastAPI).

### 2. Rate Limit Tests (`test_rate_limit.py`)

Test decorators in `extract.py`:

```python
# Line 314-315: Rate limit decorator
@sleep_and_retry
@limits(calls=45, period=1)
def _call_ollama_rate_limited(prompt, model, timeout) -> str

# Line 328-332: Retry decorator
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=10, max=30),
       retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)))
def _extract_entities_from_field(text, extractor, timeout) -> list[dict]
```

**Test scenarios:**
- `TestRateLimitDecorator`: Verify decorator applied, mock `requests.post`
- `TestRetryOnTimeout`: Verify 3 retries on `requests.Timeout`
- `TestRetryOnConnectionError`: Verify 3 retries on `requests.ConnectionError`
- `TestNoRetryOnOtherErrors`: Verify no retry on `requests.HTTPError`

### 3. Coverage Configuration

**`.coveragerc`:**
- Branch coverage enabled
- Source: `graph`, `rag` modules
- Omit tests and cache directories
- HTML report to `coverage_report/`

**`pytest.ini` update:**
```ini
addopts = -v --tb=short --cov=graph --cov=rag --cov-report=term-missing
```

### 4. New Fixtures (`conftest.py`)

```python
@pytest.fixture
def test_client():
    """FastAPI test client for webhook tests."""
    from starlette.testclient import TestClient
    from graph.webhook import app
    return TestClient(app)

@pytest.fixture
def mock_trading_graph():
    """Mock TradingGraph context manager."""
    with patch("graph.webhook.TradingGraph") as mock_class:
        mock_instance = MagicMock()
        mock_class.return_value.__enter__ = MagicMock(return_value=mock_instance)
        mock_class.return_value.__exit__ = MagicMock(return_value=False)
        yield mock_instance
```

## Verification

```bash
cd /opt/data/trading_light_pilot/trader

# Run new tests
pytest graph/tests/test_webhook.py graph/tests/test_rate_limit.py -v

# Run all tests with coverage report
pytest --cov=graph --cov-report=term-missing --cov-report=html

# View coverage
cat coverage_report/index.html  # or open in browser
```
