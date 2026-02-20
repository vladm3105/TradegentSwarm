---
title: "TradegentSwarm Open-Source Release Plan"
tags: [iplan, open-source, portfolio, release]
custom_fields:
  layer: 12
  artifact_type: IPLAN
  status: active
  created: 2025-02-20
  target_date: 2025-03-10
---

# IPLAN-002: TradegentSwarm Open-Source Release

## Overview

**Goal**: Prepare TradegentSwarm for open-source release as a portfolio project
**Current Rating**: 7.2/10 → Target: 8.5/10
**Total Estimated Effort**: 8-12 days (~2 weeks)

### Decisions

- **License**: MIT (most permissive, best for portfolio)
- **Demo Mode**: Skipped (focus on core features)
- **Scope**: Phases 1, 2, 3, 4 (Security → Docs → Watchlist → Polish)

---

## Phase 1: Security Audit & Cleanup (1-2 days)

### 1.1 Git History Audit

```bash
# Verify no .env files ever committed
git log --all --full-history -- '*.env'

# Run gitleaks locally
gitleaks detect --source . --verbose
```

### 1.2 Verify Environment Templates

| File | Action |
| ---- | ------ |
| `tradegent/.env.template` | Verify no real values |
| `tradegent/rag/.env.template` | Verify no real values |
| `tradegent/graph/.env.template` | Verify no real values |

### 1.3 Pre-commit Hook Setup

**Create**: `.pre-commit-config.yaml`

- Configure gitleaks hook
- Configure ruff/black hooks

### Phase 1 Verification

- [ ] `gitleaks detect` returns clean
- [ ] No credentials in any tracked files
- [ ] Pre-commit hooks installed and working

---

## Phase 2: Documentation (2-3 days)

### 2.1 Create CONTRIBUTING.md

**File**: `CONTRIBUTING.md`

Contents:

- Development setup instructions
- Code style (ruff, black, type hints)
- Testing requirements (pytest, coverage)
- PR process and review guidelines
- Commit message format

### 2.2 Add LICENSE

**File**: `LICENSE`

MIT License (permissive, portfolio-friendly)

### 2.3 Update README.md

**File**: `README.md`

Changes:

- Remove "Private repository" text
- Add license badge
- Add CI status badge
- Add Python version badge
- Add "Contributing" section link
- Improve Quick Start section

### 2.4 Create Architecture Doc

**File**: `docs/ARCHITECTURE.md`

Contents:

- System components diagram (Mermaid)
- Data flow explanations
- MCP server interactions
- Knowledge base structure

### Phase 2 Verification

- [ ] All docs render correctly on GitHub
- [ ] Links work
- [ ] Badges display

---

## Phase 3: Watchlist Expiration Feature (3-4 days)

### 3.1 Database Schema

**File**: `tradegent/db/init.sql`

Add `nexus.watchlist` table:

```sql
CREATE TABLE nexus.watchlist (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    entry_trigger JSONB,
    invalidation JSONB,
    expires TIMESTAMP,
    priority VARCHAR(10) DEFAULT 'medium',
    source_type VARCHAR(20),
    source_file VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 3.2 Database Layer Methods

**File**: `tradegent/db_layer.py`

Add methods:

- `get_active_watchlist()` → List all active entries
- `get_watchlist_entry(ticker)` → Get single entry
- `add_to_watchlist(...)` → Create new entry
- `update_watchlist_status(ticker, status)` → Update status
- `get_expired_entries()` → Entries past expiration
- `archive_watchlist_entry(ticker, reason)` → Move to archive

### 3.3 Service Integration

**File**: `tradegent/service.py`

Add to service loop:

```python
async def run_watchlist_check(self):
    # 1. Check expired entries (>30 days or past expires date)
    # 2. Archive expired entries
    # 3. Log summary
```

### 3.4 CLI Commands

**File**: `tradegent/orchestrator.py`

Add commands:

- `watchlist list` - Show active entries
- `watchlist add TICKER --trigger "..." --expires "..."`
- `watchlist remove TICKER`
- `watchlist check` - Run expiration check manually

### 3.5 Tests

**File**: `tradegent/tests/test_watchlist.py`

Test cases:

- Expiration logic (absolute date, relative days)
- Status transitions
- Archive behavior

### Phase 3 Verification

- [ ] `pytest tradegent/tests/test_watchlist.py` passes
- [ ] Manual test: add entry → wait → verify expiration

---

## Phase 4: Final Polish (2-3 days)

### 4.1 Code Quality

```bash
ruff check --fix tradegent/
black tradegent/
mypy tradegent/ --ignore-missing-imports
```

### 4.2 Test Coverage

```bash
pytest --cov=tradegent --cov-report=html
# Target: >70% coverage
```

### 4.3 Cleanup

Remove from repo:

- `tmp/` folder contents
- `tradegent/analyses/` runtime outputs
- Any `.pyc` or `__pycache__`

Update `.gitignore`:

```gitignore
tmp/
tradegent/analyses/
*.pyc
__pycache__/
```

### 4.4 Create Release

```bash
git tag -a v1.0.0 -m "Initial open-source release"
git push origin v1.0.0
```

Create GitHub Release with changelog.

### 4.5 Final Security Scan

```bash
gitleaks detect --source . --verbose
bandit -r tradegent/
```

### Phase 4 Verification

- [ ] All CI workflows green
- [ ] No linting errors
- [ ] No security warnings
- [ ] Watchlist feature working

---

## Critical Files Summary

| Phase | Key Files |
| ----- | --------- |
| 1 | `.pre-commit-config.yaml`, `*.env.template` |
| 2 | `CONTRIBUTING.md`, `LICENSE`, `README.md`, `docs/ARCHITECTURE.md` |
| 3 | `db/init.sql`, `db_layer.py`, `service.py`, `orchestrator.py`, `tests/test_watchlist.py` |
| 4 | All Python files (formatting), CI configs |

---

## Pre-Release Checklist

- [ ] All .env files excluded from git
- [ ] No secrets in git history (gitleaks clean)
- [ ] LICENSE file present (MIT)
- [ ] CONTRIBUTING.md present
- [ ] README badges working
- [ ] Watchlist expiration working
- [ ] CI/CD all green
- [ ] Test coverage >70%
- [ ] v1.0.0 tag created

---

## Post-Release

1. **Announce**: LinkedIn post, relevant subreddits (r/algotrading, r/Python)
2. **Monitor**: GitHub issues, stars, forks
3. **Iterate**: Address feedback, add features based on interest
