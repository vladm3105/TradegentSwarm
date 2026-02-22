# Contributing Guide

Guidelines for contributing to TradegentSwarm.

---

## Development Setup

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Runtime |
| Docker | 20+ | Infrastructure |
| Git | 2.30+ | Version control |
| pre-commit | Latest | Git hooks |

### Clone and Install

```bash
# Clone repository
git clone git@github.com:vladm3105/TradegentSwarm.git
cd TradegentSwarm

# Install development dependencies
pip install -e ".[dev]"

# Setup pre-commit hooks (required)
pip install pre-commit
pre-commit install
```

### Start Infrastructure

```bash
cd tradegent
docker compose up -d
python orchestrator.py db-init
```

---

## Code Style

### Python

- Follow PEP 8
- Use type hints
- Maximum line length: 100
- Use existing patterns in codebase

### Formatting

```bash
# Format code
black tradegent/

# Sort imports
isort tradegent/

# Lint
flake8 tradegent/
```

### Pre-commit Hooks

Pre-commit runs automatically on commit:
- Secret scanning (blocks exposed credentials)
- Black formatting
- isort import sorting
- flake8 linting

---

## Testing

### Run Tests

```bash
cd tradegent

# All tests
pytest

# With coverage
pytest --cov=rag --cov=graph --cov-report=html

# Specific module
pytest rag/tests/
pytest graph/tests/
```

### Test Requirements

- New features require tests
- Bug fixes include regression tests
- Maintain coverage above 80%

### Test Structure

```
tradegent/
├── tests/                  # Orchestrator tests
├── rag/tests/              # RAG module tests
└── graph/tests/            # Graph module tests
```

---

## Pull Request Process

### Before Submitting

1. Run tests locally:
   ```bash
   pytest tradegent/
   ```

2. Check formatting:
   ```bash
   black --check tradegent/
   flake8 tradegent/
   ```

3. Update documentation if needed

4. Commit with descriptive message

### PR Requirements

- Clear title and description
- Tests pass
- No secrets in code
- Documentation updated

### Review Process

1. Submit PR
2. CI runs automatically
3. Address review feedback
4. Squash and merge

---

## Commit Guidelines

### Message Format

```
type: short description

Optional longer description explaining the change.

Fixes #123
```

### Types

| Type | Use for |
|------|---------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation |
| `refactor` | Code refactoring |
| `test` | Adding tests |
| `chore` | Maintenance |

### Examples

```
feat: add reranking to RAG search

fix: handle dimension mismatch in embeddings

docs: update getting started guide

refactor: consolidate database queries
```

---

## Branch Naming

```
feature/add-reranking
fix/dimension-mismatch
docs/update-architecture
```

---

## Security

### Secret Scanning

- Pre-commit hooks block secrets
- CI scans all PRs
- Never commit credentials

### Detected Patterns

- API keys (OpenAI, Anthropic, etc.)
- Database passwords
- IB credentials
- VNC passwords

### If Secrets Exposed

1. Immediately rotate the credential
2. Contact maintainers
3. Force push to remove from history

---

## Architecture Guidelines

### Adding Features

1. Follow existing patterns
2. Use dependency injection
3. Add tests
4. Update documentation

### Database Changes

1. Add migration in `db/migrations/`
2. Update `db/init.sql`
3. Document schema changes

### MCP Server Changes

1. Follow MCP protocol
2. Update tool documentation
3. Add integration tests

---

## Documentation

### When to Update

- New features
- API changes
- Configuration changes
- Deprecations

### Documentation Structure

```
docs/
├── architecture/      # System design
├── user-guide/        # Usage
├── operations/        # Deployment
└── development/       # Contributing
```

---

## Getting Help

- **Issues**: GitHub Issues
- **Questions**: Open a discussion
- **Security**: Email maintainers directly

---

## Related Documentation

- [Testing](testing.md)
- [Architecture](../architecture/overview.md)
