# Contributing to TradegentSwarm

Thank you for your interest in contributing to TradegentSwarm.

## Development Setup

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Interactive Brokers account (paper trading)
- OpenAI API key (for embeddings)

### Environment Setup

1. Clone the repository:

```bash
git clone https://github.com/vladm3105/TradegentSwarm.git
cd TradegentSwarm
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows
```

3. Install dependencies:

```bash
cd tradegent
pip install -e ".[dev]"
```

4. Copy environment template and configure:

```bash
cp .env.template .env
# Edit .env with your credentials
```

5. Start infrastructure services:

```bash
docker compose up -d
```

6. Initialize the database:

```bash
docker exec nexus-postgres psql -U lightrag -d lightrag -f /docker-entrypoint-initdb.d/init.sql
```

7. Verify setup:

```bash
python orchestrator.py status
```

## Code Style

This project uses:

- **Ruff** for linting and formatting
- **Type hints** throughout (Python 3.11+ style)
- **Conventional commits** for commit messages

### Running Linters

```bash
# Check for issues
ruff check tradegent/

# Auto-fix issues
ruff check --fix tradegent/

# Format code
ruff format tradegent/
```

### Type Hints

All functions should have type hints:

```python
def analyze_stock(ticker: str, analysis_type: AnalysisType) -> AnalysisResult:
    """Analyze a stock and return results."""
    ...
```

## Testing

### Running Tests

```bash
# Run all tests
pytest tradegent/tests/

# Run with coverage
pytest --cov=tradegent tradegent/tests/

# Run specific test file
pytest tradegent/tests/test_db_layer.py
```

### Writing Tests

- Place tests in `tradegent/tests/`
- Use descriptive test names: `test_scanner_returns_candidates_when_market_open`
- Mock external services (IB Gateway, OpenAI) in unit tests

## Pull Request Process

1. **Fork** the repository and create a feature branch:

```bash
git checkout -b feature/your-feature-name
```

2. **Make changes** following the code style guidelines

3. **Write tests** for new functionality

4. **Run checks** before committing:

```bash
ruff check --fix tradegent/
ruff format tradegent/
pytest tradegent/tests/
```

5. **Commit** using conventional commit format:

```bash
git commit -m "feat: add watchlist expiration feature"
git commit -m "fix: handle missing IB connection gracefully"
git commit -m "docs: update architecture diagram"
```

6. **Push** and create a Pull Request

### Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no code change |
| `refactor` | Code restructuring |
| `test` | Adding tests |
| `chore` | Maintenance tasks |

### PR Review Criteria

- All CI checks pass
- Code follows project style
- Tests cover new functionality
- Documentation updated if needed

## Project Structure

```
tradegent_swarm/
├── tradegent/              # Main platform
│   ├── orchestrator.py     # CLI and pipeline engine
│   ├── service.py          # Long-running daemon
│   ├── db_layer.py         # Database access
│   ├── rag/                # RAG module (embeddings, search)
│   ├── graph/              # Graph module (Neo4j, extraction)
│   └── tests/              # Test suite
├── trading/                # Trading knowledge system
│   ├── skills/             # Agent skill definitions
│   └── knowledge/          # Trading data & analyses
├── .claude/                # Claude Code configuration
│   └── skills/             # Auto-invoke skills
└── docs/                   # Documentation
```

## Getting Help

- Open an issue for bugs or feature requests
- Check existing issues before creating new ones
- Provide reproduction steps for bugs

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
