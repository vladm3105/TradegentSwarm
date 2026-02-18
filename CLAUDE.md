# Trading Light Pilot - Claude Code Instructions

AI-driven trading platform using Claude Code CLI, Interactive Brokers, and LightRAG. This is an **AI-first project** with agent automation.

## Project Structure

```
trading_light_pilot/
├── .claude/skills/          # Claude Code skills (auto-invoke enabled)
├── trader/                  # Nexus Light Trading Platform (Python)
│   ├── service.py           # Long-running daemon
│   ├── orchestrator.py      # Pipeline engine + CLI
│   ├── db_layer.py          # PostgreSQL access layer
│   └── docker-compose.yml   # Infrastructure services
│
└── trading/                 # Trading Knowledge System
    ├── skills/              # Agent skill definitions (SKILL.md + template.yaml)
    ├── knowledge/           # Trading data & analyses (YAML documents)
    └── workflows/           # CI/CD & LightRAG schemas
```

## Claude Code Skills

Skills in `.claude/skills/` auto-invoke based on context. Each skill has:
- YAML frontmatter with metadata and triggers
- Workflow steps referencing `trading/skills/`
- Chaining to related skills

### Skill Index

| Skill                 | Triggers                                                 | Category   |
| --------------------- | -------------------------------------------------------- | ---------- |
| **earnings-analysis** | "earnings analysis", "pre-earnings", "before earnings"   | Analysis   |
| **stock-analysis**    | "stock analysis", "technical analysis", "value analysis" | Analysis   |
| **research**          | "research", "macro analysis", "sector analysis"          | Research   |
| **ticker-profile**    | "ticker profile", "what do I know about"                 | Knowledge  |
| **trade-journal**     | "log trade", "bought", "sold", "entered position"        | Trade Mgmt |
| **watchlist**         | "watchlist", "add to watchlist", "watch this"            | Trade Mgmt |
| **post-trade-review** | "review trade", "closed trade", "what did I learn"       | Learning   |
| **scan**              | "scan", "find opportunities", "what should I trade"      | Scanning   |

### Workflow Chains

```text
scan → earnings-analysis → watchlist → trade-journal → post-trade-review
         ↓                                    ↓
    stock-analysis ─────────────────────→ ticker-profile
         ↓
      research
```

**Automatic chaining:**

- Analysis recommends WATCH → triggers watchlist skill
- Trade journal exit → triggers post-trade-review skill
- Scanner high score → triggers appropriate analysis skill
- Post-trade review → updates ticker-profile

## Key Conventions

### File Naming
All trading documents use ISO 8601 format:
```
{TICKER}_{YYYYMMDDTHHMM}.yaml
```
Example: `NVDA_20250120T0900.yaml`

### Skill → Knowledge Mapping

| Skill | Output Location |
|-------|------------------|
| earnings-analysis | `knowledge/analysis/earnings/` |
| stock-analysis | `knowledge/analysis/stock/` |
| research-analysis | `knowledge/analysis/research/` |
| ticker-profile | `knowledge/analysis/ticker-profiles/` |
| trade-journal | `knowledge/trades/` |
| watchlist | `knowledge/watchlist/` |
| post-trade-review | `knowledge/reviews/` |
| market-scanning | Uses `knowledge/scanners/`, outputs to `watchlist/` |

## Executing Skills

When a skill is invoked (auto or manual):

1. Read the `SKILL.md` file from `trading/skills/{skill-name}/`
2. Follow the workflow steps exactly
3. Use the `template.yaml` structure for output
4. Save output to corresponding `trading/knowledge/` folder
5. Check for chaining actions (WATCH → watchlist, exit → review)

## Trader Platform

### Running Commands
```bash
cd trader
python orchestrator.py --help     # CLI commands
python service.py                 # Start daemon
```

### Infrastructure
```bash
cd trader
docker compose up -d              # Start PostgreSQL, IB Gateway, Neo4j, LightRAG
docker compose logs -f            # View logs
```

### Database
- PostgreSQL stores all pipeline config, tickers, and results
- Schema in `trader/db/init.sql`
- Use `db_layer.py` for all database operations

## Code Standards

- Python 3.11+ with type hints
- Follow PEP 8 conventions
- Use existing patterns in `orchestrator.py` and `db_layer.py`
- All SQL queries go through `db_layer.py`

## GitHub MCP Server (Preferred)

Use the `github-vl` MCP server for pushing skill outputs directly to GitHub. This avoids conda/SSH issues and provides atomic commits.

### Auto-Commit Skill Outputs

When skills save to `trading/knowledge/`, use:

```yaml
Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: trading_light_pilot
  branch: main
  files:
    - path: trading/knowledge/{output_path}
      content: [generated content]
  message: "Add {skill_name} for {TICKER}"
```

### Available MCP Tools

| Tool | Purpose |
|------|----------|
| `mcp__github-vl__push_files` | Push multiple files in single commit |
| `mcp__github-vl__create_or_update_file` | Create/update single file |
| `mcp__github-vl__get_file_contents` | Read file from repo |
| `mcp__github-vl__list_commits` | View commit history |

## IB MCP Server (Interactive Brokers)

Access Interactive Brokers TWS/Gateway for market data, portfolio, and trading.

**Source**: `/opt/data/trading/mcp_ib`

### Available Tools (22 total)

**Market Data**:
| Tool | Purpose |
|------|----------|
| `get_stock_price` | Real-time quote (bid, ask, last, volume) |
| `get_quotes_batch` | Batch quotes for multiple symbols |
| `get_option_chain` | Option chain (expirations, strikes) |
| `get_option_quotes` | Option prices for specific contracts |
| `get_historical_data` | OHLCV historical bars |
| `get_market_depth` | Level 2 order book |
| `get_fundamental_data` | Company fundamentals |

**Portfolio & Account**:
| Tool | Purpose |
|------|----------|
| `get_positions` | Current portfolio positions |
| `get_portfolio` | Full portfolio with P&L |
| `get_account_summary` | Account balances and metrics |
| `get_pnl` | Profit/loss summary |
| `get_executions` | Recent trade executions |

**Orders**:
| Tool | Purpose |
|------|----------|
| `place_order` | Submit new order |
| `cancel_order` | Cancel existing order |
| `get_open_orders` | List open orders |
| `get_order_status` | Check order status |

**Research & Discovery**:
| Tool | Purpose |
|------|----------|
| `search_symbols` | Search for symbols |
| `get_contract_details` | Contract specifications |
| `run_scanner` | Run market scanner |
| `get_scanner_params` | Available scanner parameters |
| `get_news_providers` | News provider list |
| `get_news_headlines` | Recent news headlines |

**Options Analytics**:
| Tool | Purpose |
|------|----------|
| `calc_implied_volatility` | Calculate implied volatility |
| `calc_option_price` | Calculate theoretical option price |
| `what_if_order` | Simulate order impact on margin/P&L |

**System**:
| Tool | Purpose |
|------|----------|
| `health_check` | Check IB Gateway connection |

### Usage Examples

```yaml
# Get stock price
Tool: get_stock_price
Input: {"symbol": "NVDA"}

# Get historical data
Tool: get_historical_data
Input: {"symbol": "NVDA", "duration": "1 D", "bar_size": "5 mins"}

# Get portfolio P&L
Tool: get_pnl

# Search symbols
Tool: search_symbols
Input: {"pattern": "NVDA"}
```

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `IB_GATEWAY_HOST` | host.docker.internal | TWS/Gateway hostname |
| `IB_GATEWAY_PORT` | 4002 | API port (7496=TWS live, 7497=TWS paper, 4001=Gateway live, 4002=Gateway paper) |
| `IB_CLIENT_ID` | 2 | Unique client ID |
| `IB_READONLY` | true | Read-only mode (blocks order placement) |
| `IB_RATE_LIMIT` | 45 | Requests per second limit |

## Brave Browser MCP (Web Scraping)

Browser automation for accessing protected content (Medium, Seeking Alpha, analyst reports).

**Source**: `/opt/data/trading/mcp_brave-browser`

### MCP Tools (stdio mode)

| Tool | Purpose |
|------|----------|
| `fetch_protected_article` | Fetch paywalled/protected article content |
| `take_screenshot` | Take page screenshot (base64 PNG) |
| `extract_structured_data` | Extract data using CSS selectors |
| `search_and_extract` | Search and extract results |

### HTTP API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|----------|
| `/health` | GET | Health check (no auth) |
| `/api/fetch_article` | POST | Fetch article content |
| `/api/screenshot` | POST | Take screenshot |
| `/api/extract_data` | POST | Extract structured data |
| `/api/search` | POST | Search and extract |
| `/api/cache/clear` | POST | Clear article cache |

### Usage Examples

```yaml
# Fetch article content (MCP)
Tool: fetch_protected_article
Input: {"url": "https://seekingalpha.com/article/...", "wait_for_selector": "article"}

# Take screenshot (MCP)
Tool: take_screenshot
Input: {"url": "https://finviz.com/chart.ashx?t=NVDA", "full_page": true}

# Extract consensus data
Tool: extract_data
Input: {
  "url": "https://seekingalpha.com/symbol/NVDA/earnings",
  "selectors": {"eps": "[data-test-id='eps']", "revenue": "[data-test-id='revenue']"}
}
```

### Features

- Profile persistence (maintains login sessions)
- Article caching (SHA-256 keyed, TTL support)
- SSRF protection (blocks internal networks)
- API key authentication

## Git Workflow (Fallback)

### Pushing Changes

This project uses SSH authentication. The remote is configured as:

```bash
git remote set-url origin git@github.com:vladm3105/trading_light_pilot.git
```

**Standard workflow (when MCP unavailable):**

```bash
git add -A
git commit -m "description of change"
GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push
```

### Git Push with Conda/OpenSSL Issue

If using conda, its `LD_LIBRARY_PATH` loads a newer OpenSSL that conflicts with system SSH. Fix options:

```bash
# Option 1: Clear LD_LIBRARY_PATH for SSH during git operations
GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push

# Option 2: Use git alias (one-time setup)
git config --global alias.pushs '!GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push'
# Then use: git pushs

# Option 3: Deactivate conda before git operations
conda deactivate
git push
```

### SSH Configuration

Requires `~/.ssh/config` entry:

```text
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github-vladm3105
    IdentitiesOnly yes
```

## Important Notes

- Do not commit `.env` files (contains credentials)
- IB Gateway requires valid paper trading account
- LightRAG syncs trading knowledge for semantic search
- Scanner configs in `knowledge/scanners/` encode trading edge - treat as sensitive
- Skills auto-invoke based on conversation context - no manual `/command` needed
- Always use the SSH git push command with `LD_LIBRARY_PATH=` fix when in conda environment
