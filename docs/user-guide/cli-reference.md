# CLI Reference

The `orchestrator.py` CLI provides commands for managing stocks, running analyses, and controlling the trading system.

---

## Quick Reference

```bash
cd tradegent
python orchestrator.py <command> [options]
```

| Command | Purpose |
|---------|---------|
| `status` | System status |
| `analyze` | Run analysis |
| `watchlist` | Analyze enabled stocks |
| `stock` | Stock management |
| `settings` | Configuration |
| `db-init` | Initialize database |

---

## System Commands

### status

Display system status including database connection, service state, and daily counts.

```bash
python orchestrator.py status
```

Output:
```
=== Nexus Light Status ===
Database: Connected
Service: running
Today: 2 analyses, 0 executions
Dry run mode: false
```

### db-init

Initialize or reset the database schema.

```bash
python orchestrator.py db-init
```

---

## Analysis Commands

### analyze

Run analysis for a single ticker.

```bash
python orchestrator.py analyze <TICKER> [options]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--type` | stock | Analysis type: `stock`, `earnings` |
| `--force` | false | Skip recent analysis check |

**Examples:**

```bash
# Stock analysis
python orchestrator.py analyze NVDA --type stock

# Earnings analysis
python orchestrator.py analyze MSFT --type earnings

# Force re-analysis
python orchestrator.py analyze AAPL --force
```

### watchlist

Analyze all enabled stocks in priority order.

```bash
python orchestrator.py watchlist [options]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--limit` | 10 | Max stocks to analyze |
| `--type` | (per-stock) | Override analysis type |

**Examples:**

```bash
# Analyze top 5 enabled stocks
python orchestrator.py watchlist --limit 5

# Force earnings analysis for all
python orchestrator.py watchlist --type earnings
```

### run-due

Run analyses for stocks with upcoming earnings.

```bash
python orchestrator.py run-due
```

---

## Stock Management

### stock list

List all stocks in the watchlist.

```bash
python orchestrator.py stock list [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--enabled` | Show only enabled stocks |
| `--state <state>` | Filter by state |
| `--tag <tag>` | Filter by tag |

**Examples:**

```bash
# All stocks
python orchestrator.py stock list

# Only enabled
python orchestrator.py stock list --enabled

# Paper trading stocks
python orchestrator.py stock list --state paper
```

### stock add

Add a stock to the watchlist.

```bash
python orchestrator.py stock add <TICKER> [options]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--priority` | 5 | Priority (1-10) |
| `--tags` | — | Space-separated tags |
| `--earnings-date` | — | Next earnings date (YYYY-MM-DD) |
| `--comment` | — | Description or notes |
| `--state` | analysis | Initial state |

**Examples:**

```bash
# Basic add
python orchestrator.py stock add PLTR

# With priority and comment
python orchestrator.py stock add DOCU --priority 5 --comment "DocuSign - e-signature"

# Full details
python orchestrator.py stock add PLTR \
  --priority 8 \
  --tags ai defense gov \
  --earnings-date "2025-02-15" \
  --comment "Palantir - AI/defense contractor"
```

### stock remove

Remove a stock from the watchlist.

```bash
python orchestrator.py stock remove <TICKER>
```

### stock enable / disable

Toggle stock inclusion in batch operations.

```bash
python orchestrator.py stock enable <TICKER>
python orchestrator.py stock disable <TICKER>
```

### stock set-state

Change stock trading state.

```bash
python orchestrator.py stock set-state <TICKER> <STATE>
```

**States:**

| State | Description |
|-------|-------------|
| `analysis` | Analysis only, no orders |
| `paper` | Paper trading enabled |
| `live` | Blocked (not implemented) |

**Example:**

```bash
# Enable paper trading for NVDA
python orchestrator.py stock set-state NVDA paper
```

### stock set-priority

Set stock priority.

```bash
python orchestrator.py stock set-priority <TICKER> <PRIORITY>
```

Priority range: 1-10 (10 = highest, processed first)

### stock set-earnings

Set next earnings date.

```bash
python orchestrator.py stock set-earnings <TICKER> <DATE>
```

Date format: YYYY-MM-DD

---

## Settings Commands

### settings list

Display all settings.

```bash
python orchestrator.py settings list
```

### settings get

Get a specific setting.

```bash
python orchestrator.py settings get <KEY>
```

### settings set

Set a configuration value.

```bash
python orchestrator.py settings set <KEY> <VALUE>
```

**Key Settings:**

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `dry_run_mode` | bool | true | Block all Claude calls |
| `auto_execute_enabled` | bool | false | Enable order placement |
| `max_daily_analyses` | int | 10 | Daily analysis limit |
| `max_daily_executions` | int | 5 | Daily execution limit |

**Examples:**

```bash
# Disable dry run mode
python orchestrator.py settings set dry_run_mode false

# Enable auto-execute
python orchestrator.py settings set auto_execute_enabled true
```

---

## Service Commands

### service start

Start the background service daemon.

```bash
python service.py
```

Or using systemd:

```bash
sudo systemctl start tradegent
```

### service status

Check service status.

```bash
python orchestrator.py status
```

---

## Common Workflows

### First Analysis

```bash
# 1. Disable dry run
python orchestrator.py settings set dry_run_mode false

# 2. Add stock
python orchestrator.py stock add NVDA --priority 10 --comment "NVIDIA - AI/GPU leader"

# 3. Run analysis
python orchestrator.py analyze NVDA --type stock
```

### Enable Paper Trading

```bash
# 1. Ensure dry run is off
python orchestrator.py settings set dry_run_mode false

# 2. Enable auto-execute
python orchestrator.py settings set auto_execute_enabled true

# 3. Set stock to paper state
python orchestrator.py stock set-state NVDA paper

# 4. Run analysis (will execute if gate passes)
python orchestrator.py analyze NVDA
```

### Batch Operations

```bash
# Analyze all enabled stocks
python orchestrator.py watchlist

# Analyze stocks with upcoming earnings
python orchestrator.py run-due
```

---

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Error |
| 2 | Invalid arguments |

---

## Related Documentation

- [Analysis Workflow](analysis-workflow.md)
- [Getting Started](../getting-started.md)
- [Architecture Overview](../architecture/overview.md)
