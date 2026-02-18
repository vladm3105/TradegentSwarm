---
title: Market Scanning
tags:
  - trading-skill
  - scanning
  - opportunity-finding
  - ai-agent-primary
custom_fields:
  skill_category: scanning
  priority: primary
  development_status: active
  upstream_artifacts: []
  downstream_artifacts:
    - earnings-analysis
    - stock-analysis
    - watchlist
  triggers:
    - "scan"
    - "market scan"
    - "find opportunities"
    - "run scanner"
    - "daily scan"
    - "what should I trade"
  auto_invoke: true
---

# Market Scanning Skill

Use this skill to systematically identify trading opportunities using scanner configurations. Auto-invokes for daily trading routine or when user asks for opportunities.

## When to Use

- Daily market routine (pre-market, open, close)
- Finding new trade candidates
- User asks "what should I trade?" or "find opportunities"
- Running specific scanner by name

## Available Scanners

### Daily Scanners (`trading/knowledge/scanners/daily/`)
| Scanner | Time | Purpose |
|---------|------|----------|
| market-regime | 09:35 | Classify market environment |
| premarket-gap | 08:30 | Gaps with catalysts |
| news-catalyst | 07:00/12:00/18:00 | Material news |
| earnings-momentum | 09:45 | Pre-earnings setups |
| 52w-extremes | 15:45 | Breakouts/breakdowns |
| sector-rotation | 16:15 | Sector flows |
| oversold-bounce | 15:50 | Mean reversion |

### Intraday Scanners (`trading/knowledge/scanners/intraday/`)
| Scanner | Purpose |
|---------|----------|
| options-flow | Unusual options activity |
| unusual-volume | Volume spikes |

### Weekly Scanners (`trading/knowledge/scanners/weekly/`)
| Scanner | Time | Purpose |
|---------|------|----------|
| earnings-calendar | Sun 07:00 | Week ahead earnings |
| institutional-activity | Mon/Fri 18:00 | 13F filings, insiders |

## Workflow

1. **Read skill definition**: Load `trading/skills/market-scanning/SKILL.md`
2. **Load scanner config** from `trading/knowledge/scanners/{daily|intraday|weekly}/`
3. **Execute scanner**:
   - Gather data using specified sources
   - Apply quality filters (liquidity, exclusions)
   - Score candidates using weighted criteria
4. **Route results by score**:
   - Score ≥ 7.5: **Trigger full analysis** (earnings or stock)
   - Score 5.5-7.4: **Add to watchlist**
   - Score < 5.5: Skip
5. **Output summary** of scanner run

## Scoring System

```
SCORE CALCULATION:
Score = Σ (Criterion Score × Weight)
Where weights sum to 1.0

INTERPRETATION:
≥ 7.5: High priority → trigger analysis
6.5-7.4: Good → add to watchlist
5.5-6.4: Marginal → monitor only
< 5.5: Skip
```

## Daily Routine

```
PRE-MARKET (07:00-09:30):
□ News Catalyst scanner
□ Pre-Market Gap scanner
□ Note high-priority candidates

MARKET OPEN (09:35-10:00):
□ Market Regime classifier
□ Earnings Momentum scanner
□ First Unusual Volume check

MID-DAY (11:00-14:00):
□ Options Flow checks
□ Unusual Volume updates

CLOSE (15:30-16:15):
□ 52-Week Extremes
□ Oversold Bounce
□ Sector Rotation
□ Daily summary
```

## Chaining

- High scores → invoke **earnings-analysis** or **stock-analysis**
- Medium scores → invoke **watchlist** skill
- Updates market regime context for all other skills
- Weekly earnings-calendar informs **earnings-analysis** pipeline

## Arguments

- `$ARGUMENTS`: Scanner name (optional), or "daily", "weekly", "all"

## Auto-Commit to Remote

After adding candidates to watchlist, use the GitHub MCP server to push directly:

```yaml
Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: trading_light_pilot
  branch: main
  files:
    - path: trading/knowledge/watchlist/{TICKER1}_{YYYYMMDDTHHMM}.yaml
      content: [watchlist entry content]
    - path: trading/knowledge/watchlist/{TICKER2}_{YYYYMMDDTHHMM}.yaml
      content: [watchlist entry content]
  message: "Scanner results: {scanner_name} - {count} candidates"
```

## Execution

Run market scanning for $ARGUMENTS. Read the full skill definition from `trading/skills/market-scanning/SKILL.md`. Load scanner configs from `trading/knowledge/scanners/`. After adding watchlist candidates, auto-commit and push to remote.
