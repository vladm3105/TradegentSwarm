---
mode: agent
description: Systematically identify trading opportunities using scanner configurations
---

# Market Scanning

Run market scanning: **${input:scanner}** (scanner name, "daily", "weekly", or "all").

## Context

Load the full skill definition:
- #file:../../tradegent_knowledge/skills/market-scanning/SKILL.md

Load scanner configurations:
- #file:../../tradegent_knowledge/knowledge/scanners/daily/
- #file:../../tradegent_knowledge/knowledge/scanners/intraday/
- #file:../../tradegent_knowledge/knowledge/scanners/weekly/

## When to Use

- Daily market routine (pre-market, open, close)
- Finding new trade candidates
- Running a specific scanner by name

## Available Scanners

### Daily (`tradegent_knowledge/knowledge/scanners/daily/`)
| Scanner | Time | Purpose |
|---------|------|---------|
| market-regime | 09:35 | Classify market environment |
| premarket-gap | 08:30 | Gaps with catalysts |
| news-catalyst | 07:00/12:00/18:00 | Material news |
| earnings-momentum | 09:45 | Pre-earnings setups |
| 52w-extremes | 15:45 | Breakouts/breakdowns |
| sector-rotation | 16:15 | Sector flows |
| oversold-bounce | 15:50 | Mean reversion |

### Intraday (`tradegent_knowledge/knowledge/scanners/intraday/`)
| Scanner | Purpose |
|---------|---------|
| options-flow | Unusual options activity |
| unusual-volume | Volume spikes |

### Weekly (`tradegent_knowledge/knowledge/scanners/weekly/`)
| Scanner | Time | Purpose |
|---------|------|---------|
| earnings-calendar | Sun 07:00 | Week ahead earnings |
| institutional-activity | Mon/Fri 18:00 | 13F filings, insiders |

## Workflow

1. **Read skill definition** from `tradegent_knowledge/skills/market-scanning/SKILL.md`
2. **Load scanner config** from `tradegent_knowledge/knowledge/scanners/{daily|intraday|weekly}/`
3. **Execute scanner**:
   - Gather data using specified sources
   - Apply quality filters (liquidity, exclusions)
   - Score candidates using weighted criteria
4. **Route results by score**:
   - Score ≥ 7.5: **Trigger full analysis** (earnings or stock)
   - Score 5.5–7.4: **Add to watchlist**
   - Score < 5.5: Skip
5. **Output summary** of scanner run

## Daily Routine

**Pre-Market (07:00–09:30)**: News Catalyst, Pre-Market Gap, note high-priority candidates

**Market Open (09:35–10:00)**: Market Regime, Earnings Momentum, first Unusual Volume check

**Mid-Day (11:00–14:00)**: Options Flow, Unusual Volume updates

**Close (15:30–16:15)**: 52-Week Extremes, Oversold Bounce, Sector Rotation, daily summary

## Chaining

- High scores → invoke **earnings-analysis** or **stock-analysis**
- Medium scores → invoke **watchlist** prompt
- Updates market regime context for all other skills
- Weekly earnings-calendar informs **earnings-analysis** pipeline

## Output

Summarize scanner results with candidates scored and routed to the appropriate next step.
