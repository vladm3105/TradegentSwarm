# Scanner System

Scanners are YAML configurations that define systematic rules for finding trading opportunities.

## Scanner Types

| Type | Folder | Run Time |
|------|--------|----------|
| **Daily** | `scanners/daily/` | Once per day |
| **Intraday** | `scanners/intraday/` | Multiple times |
| **Weekly** | `scanners/weekly/` | Weekly |

## Daily Schedule (ET)

| Time | Scanner | Purpose |
|------|---------|---------|
| 07:00 | news-catalyst | Overnight news |
| 08:30 | premarket-gap | Gaps >3% |
| 09:35 | market-regime | Bull/bear/neutral |
| 09:45 | earnings-momentum | Pre-earnings setups |
| 10:00+ | unusual-volume | Volume spikes |
| 15:45 | 52w-extremes | Breakouts/breakdowns |
| 16:15 | sector-rotation | Money flow |

## Scanner Structure

```yaml
_meta:              # ID, version, schedule
scanner_config:     # Name, priority, limits
scanner:            # Data sources (IB + web)
quality_filters:    # Liquidity, fundamentals, exclusions
scoring:            # Weighted criteria (sum to 1.0)
output:             # Format, fields, storage
agent_instructions: # Step-by-step execution
```

## Scoring and Routing

```
Score = Σ (Criterion × Weight)

≥ 7.5: High Priority → Trigger full analysis
6.5-7.4: Good → Add to watchlist, monitor closely
5.5-6.4: Marginal → Add to watchlist, lower priority
< 5.5: Skip
```

## Running Scanners

```yaml
# Execute IB scanner
Tool: mcp__ib-mcp__run_scanner
Input: {"scan_code": "TOP_OPEN_PERC_GAIN", "max_results": 50}

# Get detailed quotes
Tool: mcp__ib-mcp__get_quotes_batch
Input: {"symbols": ["NVDA", "AAPL", "..."]}

# Search for catalysts
Tool: mcp__brave-search__brave_web_search
Input: {"query": "NVDA earnings preview analyst"}
```

## Available Scanners

| Scanner | Category | Key Criteria |
|---------|----------|--------------|
| `premarket-gap` | Momentum | Gap >3%, catalyst, volume |
| `earnings-momentum` | Earnings | Beat history, IV, sentiment |
| `news-catalyst` | Event | Material news, price impact |
| `52w-extremes` | Technical | Breakout/breakdown, volume |
| `oversold-bounce` | Mean Reversion | RSI, support |
| `sector-rotation` | Macro | Sector flows |
| `options-flow` | Sentiment | Unusual options activity |
| `unusual-volume` | Momentum | Volume spikes |

> Scanner configs in `knowledge/scanners/` encode your trading edge - treat as sensitive.
