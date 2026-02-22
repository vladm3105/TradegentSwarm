# Scanners Guide

Scanners systematically find trading opportunities using IB market data and custom scoring rules.

---

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Scanner Pipeline                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐     │
│  │  Config  │──▶│ IB Scan  │──▶│  Filter  │──▶│  Score   │     │
│  │  (YAML)  │   │  API     │   │ Quality  │   │ & Route  │     │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘     │
│                                                      │          │
│                                    ┌─────────────────┼──────┐   │
│                                    │                 │      │   │
│                                    ▼                 ▼      ▼   │
│                              ┌──────────┐     ┌──────┐  ┌────┐  │
│                              │ Analysis │     │Watch │  │Skip│  │
│                              │  (≥7.5)  │     │(5.5+)│  │(<5)│  │
│                              └──────────┘     └──────┘  └────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Scanner Types

| Type | Folder | Run Time | Purpose |
|------|--------|----------|---------|
| **Daily** | `scanners/daily/` | Once/day | Pre-market setups |
| **Intraday** | `scanners/intraday/` | Multiple | Real-time signals |
| **Weekly** | `scanners/weekly/` | Weekly | Earnings, filings |

---

## Available Scanners

### Daily Scanners

| Scanner | Time (ET) | Purpose |
|---------|-----------|---------|
| `news-catalyst` | 07:00 | Overnight news |
| `premarket-gap` | 08:30 | Gaps > 3% |
| `market-regime` | 09:35 | Bull/bear/neutral |
| `earnings-momentum` | 09:45 | Pre-earnings setups |
| `52w-extremes` | 15:45 | Breakouts/breakdowns |
| `sector-rotation` | 16:15 | Money flow |

### Intraday Scanners

| Scanner | Frequency | Purpose |
|---------|-----------|---------|
| `unusual-volume` | 30 min | Volume spikes |
| `options-flow` | 15 min | Unusual options |

### Weekly Scanners

| Scanner | Day | Purpose |
|---------|-----|---------|
| `earnings-calendar` | Sunday | Week's earnings |
| `13f-filings` | Tuesday | Institutional moves |

---

## Scanner Structure

```yaml
_meta:
  id: "earnings-momentum"
  version: "1.0"
  schedule: "daily"
  run_time: "09:45"

scanner_config:
  name: "Earnings Momentum Scanner"
  priority: "high"
  max_results: 50

scanner:
  sources:
    - type: "ib_scanner"
      params:
        scan_code: "TOP_OPEN_PERC_GAIN"
    - type: "web_search"
      params:
        query: "{ticker} earnings preview"

quality_filters:
  min_price: 10
  min_volume: 500000
  min_market_cap: 1000000000
  exclude_sectors: ["utilities", "real_estate"]

scoring:
  catalyst_strength:
    weight: 0.30
    criteria: "Material news or earnings"
  technical_setup:
    weight: 0.25
    criteria: "Above key MAs, breakout"
  risk_reward:
    weight: 0.25
    criteria: "R:R > 2:1"
  sentiment:
    weight: 0.20
    criteria: "Analyst upgrades, flow"

output:
  format: "watchlist"
  fields: ["ticker", "score", "catalyst", "entry", "stop"]
```

---

## Scoring System

Scanners score candidates 0-10 using weighted criteria.

### Scoring Weights

```
Score = Σ (Criterion × Weight)
        where Σ weights = 1.0
```

Example:
```
Catalyst:  8 × 0.30 = 2.40
Technical: 7 × 0.25 = 1.75
Risk/Reward: 9 × 0.25 = 2.25
Sentiment: 6 × 0.20 = 1.20
                      ──────
Total Score:          7.60
```

### Score Routing

| Score | Action | Destination |
|-------|--------|-------------|
| ≥ 7.5 | Full analysis | earnings-analysis or stock-analysis |
| 6.5-7.4 | High priority watch | watchlist (priority: high) |
| 5.5-6.4 | Standard watch | watchlist (priority: medium) |
| < 5.5 | Skip | No action |

---

## Running Scanners

### Manual Execution

```yaml
# 1. Load scanner config
Read: tradegent_knowledge/knowledge/scanners/daily/earnings-momentum.yaml

# 2. Execute IB scanner
Tool: mcp__ib-mcp__run_scanner
Input: {"scan_code": "TOP_OPEN_PERC_GAIN", "max_results": 50}

# 3. Get detailed quotes
Tool: mcp__ib-mcp__get_quotes_batch
Input: {"symbols": ["NVDA", "AAPL", "..."]}

# 4. Search for catalysts
Tool: mcp__brave-search__brave_web_search
Input: {"query": "NVDA earnings preview analyst"}

# 5. Apply filters and scoring
# 6. Route results
```

### Via Claude Code

```
Run earnings momentum scan
```

### Via Service

Automated via `service.py` tick loop based on schedule.

---

## Quality Filters

### Liquidity Filters

| Filter | Default | Purpose |
|--------|---------|---------|
| `min_price` | $10 | Avoid penny stocks |
| `min_volume` | 500K | Ensure liquidity |
| `min_avg_volume` | 1M | Average daily volume |
| `min_market_cap` | $1B | Institutional interest |

### Fundamental Filters

| Filter | Default | Purpose |
|--------|---------|---------|
| `exclude_sectors` | utilities, RE | Low volatility sectors |
| `min_analyst_coverage` | 5 | Research availability |
| `max_short_interest` | 30% | Avoid squeeze risk |

### Technical Filters

| Filter | Default | Purpose |
|--------|---------|---------|
| `above_sma_50` | true | Trend filter |
| `rsi_range` | 30-70 | Avoid extremes |
| `max_gap_pct` | 15% | Avoid overextended |

---

## IB Scanner Codes

Common scanner types available via IB API:

| Code | Description |
|------|-------------|
| `TOP_OPEN_PERC_GAIN` | Top % gainers at open |
| `TOP_OPEN_PERC_LOSE` | Top % losers at open |
| `TOP_PERC_GAIN` | Top intraday % gainers |
| `TOP_PERC_LOSE` | Top intraday % losers |
| `MOST_ACTIVE` | Highest volume |
| `HOT_BY_VOLUME` | Volume vs average |
| `HIGH_OPEN_GAP` | Gap up at open |
| `LOW_OPEN_GAP` | Gap down at open |
| `HALTED` | Halted stocks |

```yaml
Tool: mcp__ib-mcp__run_scanner
Input: {
  "scan_code": "TOP_OPEN_PERC_GAIN",
  "instrument": "STK",
  "location": "STK.US.MAJOR",
  "max_results": 50
}
```

---

## Creating Custom Scanners

### 1. Create YAML Config

```yaml
# knowledge/scanners/daily/my-scanner.yaml
_meta:
  id: "my-scanner"
  version: "1.0"
  schedule: "daily"
  run_time: "09:30"

scanner_config:
  name: "My Custom Scanner"
  max_results: 30

scanner:
  sources:
    - type: "ib_scanner"
      params:
        scan_code: "MOST_ACTIVE"

quality_filters:
  min_price: 20
  min_volume: 1000000

scoring:
  volume_spike:
    weight: 0.50
    criteria: "Volume > 200% average"
  price_action:
    weight: 0.50
    criteria: "Breakout above resistance"
```

### 2. Test Scanner

```bash
# Via Claude Code
Run my-scanner scan
```

### 3. Add to Schedule

Edit `service.py` tick loop or create schedule entry.

---

## Scanner Output

### Watchlist Entry

```yaml
_meta:
  source: "earnings-momentum"
  scan_date: "2025-01-20"

ticker: "NVDA"
score: 7.8
score_breakdown:
  catalyst: 8
  technical: 7
  risk_reward: 9
  sentiment: 7

entry_trigger:
  type: "price"
  condition: "above"
  value: 145.00

invalidation: "Below $135"
expires: "2025-01-25"
```

---

## Best Practices

1. **Run before market open** for gap scanners
2. **Validate with manual review** before trading
3. **Track scanner performance** (hit rate, P&L)
4. **Adjust weights** based on market regime
5. **Combine scanners** for confirmation

---

## Related Documentation

- [Analysis Workflow](analysis-workflow.md)
- [Skills Guide](skills-guide.md)
- [IB MCP Server](../architecture/mcp-servers.md)
