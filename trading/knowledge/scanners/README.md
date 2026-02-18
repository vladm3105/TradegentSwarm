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

## How to Use

### Running a Scanner
1. AI agent reads scanner config at scheduled time
2. Executes IB scanner and/or web search as configured
3. Applies quality filters
4. Scores results using defined criteria
5. Outputs watchlist for passing scores
6. Triggers full analysis for high scores (≥7.5)

### Scanner Structure
```yaml
_meta:           # ID, type, version, schedule
scanner_config:  # Name, priority, limits
scanner:         # Data sources (IB, web search)
quality_filters: # Liquidity, fundamentals, exclusions
scoring:         # Criteria with weights, thresholds
output:          # Format, fields, storage
agent_instructions:  # How to execute
```

### Creating a New Scanner
1. Copy `reference/templates/scanner-config.yaml`
2. Define data sources
3. Set quality filters appropriate to strategy
4. Define scoring criteria (weights must sum to 1.0)
5. Write agent instructions
6. Test and refine thresholds

## Integration
- Outputs to: `watchlist/` (candidates), `analysis/` (triggered analyses)
- Uses: IB Trading MCP tools, web search
- Informs: Daily trading decisions

## Why Scanners Are Knowledge
Scanners encode:
- What you look for (your edge)
- How you filter (quality standards)
- How you prioritize (scoring weights)
- When you look (timing)

This is **systematic trading knowledge**, not just automation.

## Performance Tracking
Track per scanner:
- Hit rate (% that move as expected)
- Win rate (% of trades profitable)
- Average return
- False positive rate
- Continuously optimize thresholds
