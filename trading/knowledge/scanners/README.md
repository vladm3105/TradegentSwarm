# Scanners

## Purpose

Configures market scanners that identify trading opportunities. These ARE trading knowledge - they encode your edge and systematic approach.

## What Belongs Here

- Scanner configurations for AI agents
- Scoring criteria and thresholds
- Quality filters
- Agent execution instructions
- Strategy mappings

## Folder Structure

```
scanners/
├── daily/        ← Run every trading day
├── weekly/       ← Run weekly (weekends, specific days)
└── intraday/     ← Run multiple times per day
```

## Current Scanners

### Daily Scanners (Priority Order)

| Scanner | File | Run Time | Purpose |
|---------|------|----------|---------|
| Market Regime | `market-regime.yaml` | 09:35 | Classify market environment |
| Pre-Market Gap | `premarket-gap.yaml` | 08:30 | Gaps >3% with catalysts |
| News Catalyst | `news-catalyst.yaml` | 07:00, 12:00, 18:00 | Material news events |
| Earnings Momentum | `earnings-momentum.yaml` | 09:45 | Pre-earnings setups |
| 52-Week Extremes | `52w-extremes.yaml` | 15:45 | Breakouts and breakdowns |
| Sector Rotation | `sector-rotation.yaml` | 16:15 | Sector money flows |
| Oversold Bounce | `oversold-bounce.yaml` | 15:50 | Mean reversion candidates |

### Intraday Scanners

| Scanner | File | Run Time | Purpose |
|---------|------|----------|--------|
| Options Flow | `options-flow.yaml` | 09:45, 11:00, 13:00, 15:00 | Unusual options activity |
| Unusual Volume | `unusual-volume.yaml` | 10:00, 11:30, 14:00, 15:30 | Volume spikes |

### Weekly Scanners

| Scanner | File | Run Time | Purpose |
|---------|------|----------|---------|
| Earnings Calendar | `earnings-calendar.yaml` | Sunday 07:00 | Week ahead earnings |
| Institutional Activity | `institutional-activity.yaml` | Mon/Fri 18:00 | 13F, insider, dark pool |

## Execution Flow

```
1. SCHEDULE TRIGGER (e.g., 08:30 ET)
          ↓
2. LOAD SCANNER CONFIG
   Read scanners/daily/premarket-gap.yaml
          ↓
3. RUN IB SCANNER
   mcp__ib-mcp__run_scanner
          ↓
4. GATHER ADDITIONAL DATA
   - mcp__ib-mcp__get_quotes_batch
   - mcp__brave-search__brave_web_search
          ↓
5. APPLY QUALITY FILTERS
   - Min volume, market cap
   - Exclude ETFs, penny stocks
          ↓
6. SCORE CANDIDATES
   Score = Σ (Criterion × Weight)
          ↓
7. ROUTE BY SCORE
   ≥ 7.5 → Trigger analysis
   5.5-7.4 → Add to watchlist
   < 5.5 → Skip
```

## Scanner Structure

```yaml
_meta:              # ID, type, version, schedule
scanner_config:     # Name, priority, limits
scanner:            # Data sources (IB, web search)
quality_filters:    # Liquidity, fundamentals, exclusions
scoring:            # Criteria with weights (sum to 1.0)
strategies:         # Trade setups by score/criteria
output:             # Format, fields, storage
agent_instructions: # Step-by-step execution
_graph:             # Entity extraction hints
_links:             # Related skills and templates
```

## Scoring System

### Calculation

```
SCORE = Σ (Criterion Score × Weight)

Where:
- Each criterion scores 1-10
- Weights sum to 1.0
- Final score ranges 1-10
```

### Score Routing

| Score | Action | Example |
|-------|--------|---------|
| ≥ 7.5 | Trigger full analysis | earnings-analysis or stock-analysis skill |
| 5.5-7.4 | Add to watchlist | Monitor for entry trigger |
| < 5.5 | Skip | Log and continue |

### Example Criteria (Earnings Momentum)

| Criterion | Weight | Description |
|-----------|--------|-------------|
| Beat History | 0.20 | Last 8 quarters beat streak |
| Momentum | 0.25 | Price vs MAs, relative strength |
| Sentiment | 0.20 | Whisper vs consensus |
| IV Setup | 0.15 | Options premium reasonableness |
| Historical Reaction | 0.20 | Average post-earnings move |

## MCP Tools Used

| Tool | Purpose |
|------|---------|
| `mcp__ib-mcp__run_scanner` | Execute IB market scanner |
| `mcp__ib-mcp__get_scanner_params` | Get available scanner types |
| `mcp__ib-mcp__get_quotes_batch` | Batch quotes for candidates |
| `mcp__ib-mcp__get_news_headlines` | News for candidates |
| `mcp__brave-search__brave_web_search` | Catalyst and sentiment search |
| `rag_search` | Prior context for candidates |
| `graph_extract` | Index scan results |

## Strategy Assignment

Each scanner assigns recommended strategies based on score and criteria:

### Pre-Market Gap Strategies

| Strategy | Criteria | Entry | Stop | Target |
|----------|----------|-------|------|--------|
| Gap & Go | Score ≥8, strong catalyst | First 5-min high break | Below pre-market low | 1.5-2x risk |
| Gap Fade | Score ≤5, weak catalyst | After failed push | Above pre-market high | 50% gap fill |
| Gap Pullback | Score ≥7, holding | VWAP test | Below VWAP by 1 ATR | Pre-market high |

### Earnings Momentum Matrix

| Conviction | Price Action | Position |
|------------|--------------|----------|
| High (>70%) | Rising | Full size, enter now |
| High | Flat | Full size, enter now |
| High | Declining | Wait, reduced size |
| Medium (55-70%) | Any | Spreads or reduced size |
| Low (<55%) | Any | Pass |

## Daily Trading Routine

| Time (ET) | Scanner | Action |
|-----------|---------|--------|
| 07:00 | news-catalyst | Identify overnight catalysts |
| 08:30 | premarket-gap | Find gaps >3% with volume |
| 09:35 | market-regime | Classify bull/bear/neutral |
| 09:45 | earnings-momentum | Pre-earnings setups |
| 10:00+ | unusual-volume | Volume spike alerts (repeats) |
| 15:45 | 52w-extremes | Breakout/breakdown trades |
| 15:50 | oversold-bounce | Mean reversion candidates |
| 16:15 | sector-rotation | Money flow analysis |

## Creating a New Scanner

1. Copy `reference/templates/scanner-config.yaml`
2. Define data sources (IB scanner codes, web queries)
3. Set quality filters appropriate to strategy
4. Define scoring criteria (weights must sum to 1.0)
5. Define strategy assignments by score
6. Write agent_instructions step by step
7. Add _graph entities for knowledge extraction
8. Test and refine thresholds

## Integration

### Skill Chaining

```
SCANNER OUTPUT → SKILL TRIGGER
        ↓
┌───────────────────────────┐
│ Score ≥ 7.5?              │
│ Has earnings within 10d?  │
└───────────────────────────┘
        ↓
   YES to both → earnings-analysis skill
   YES score only → stock-analysis skill
   Score 5.5-7.4 → watchlist skill
```

### Output Paths

| Scanner Output | Destination |
|----------------|-------------|
| High score candidates | `analysis/earnings/` or `analysis/stock/` |
| Medium score candidates | `watchlist/` |
| Scan logs | `scanner-logs/{YYYY}/{MM}/` |

## Why Scanners Are Knowledge

Scanners encode:
- **What you look for** (your edge)
- **How you filter** (quality standards)
- **How you prioritize** (scoring weights)
- **When you look** (timing)
- **How you trade it** (strategy assignment)

This is **systematic trading knowledge**, not just automation.

## Performance Tracking

Track per scanner:
- Hit rate (% that move as expected)
- Win rate (% of trades profitable)
- Average return per signal
- False positive rate
- Score threshold optimization

## Security Note

Scanner configs encode your trading edge. Treat as sensitive - do not share scoring weights or quality filter thresholds publicly.
