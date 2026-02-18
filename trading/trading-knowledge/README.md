# Trading Knowledge Base

AI-centric trading knowledge repository. Stores actual trading data, analyses, and insights. Works with any AI agent using the companion `trading-skills` package.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TRADING SYSTEM                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌──────────────┐      ┌──────────────┐      ┌──────────────┐     │
│   │   AI Agent   │      │   trading-   │      │   trading-   │     │
│   │  (Any LLM)   │─────▶│   skills/    │─────▶│   knowledge/ │     │
│   │              │      │  (how-to)    │      │   (data)     │     │
│   └──────────────┘      └──────────────┘      └──────────────┘     │
│                                                      │              │
│                                                      ▼              │
│                                               ┌──────────────┐     │
│                                               │   LightRAG   │     │
│                                               │   (optional) │     │
│                                               └──────────────┘     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Folder Structure

```
trading-knowledge/
├── analysis/                    # All analyses by skill type
│   ├── earnings/                # 8-phase earnings analyses
│   ├── stock/                   # 7-phase stock analyses
│   ├── research/                # Macro/sector/thematic research
│   └── ticker-profiles/         # Persistent ticker knowledge
├── trades/                      # Executed trade journals
├── watchlist/                   # Potential trades waiting for trigger
├── reviews/                     # Post-trade and weekly reviews
├── learnings/                   # Lessons, biases, patterns, rules
│   ├── biases/                  # Cognitive biases
│   ├── signals/                 # Market signals
│   ├── patterns/                # Price/volume patterns
│   └── rules/                   # Experience-derived rules
├── strategies/                  # Strategy definitions
├── scanners/                    # Scanner configurations
│   ├── daily/                   # Run every trading day
│   ├── intraday/                # Run multiple times per day
│   └── weekly/                  # Run weekly
└── reference/                   # Roadmap and notes
```

## File Naming Convention

All analysis and trade documents use:
```
{TICKER}_{YYYYMMDDTHHMM}.yaml
```

Examples:
- `NVDA_20250120T0900.yaml` - NVDA analysis on Jan 20, 2025 at 9:00 AM
- `AMD_20250122T0935.yaml` - AMD analysis on Jan 22, 2025 at 9:35 AM

## Current Documents

### Earnings Analyses
| File | Ticker | Status |
|------|--------|--------|
| `analysis/earnings/NVDA_20250120T0900.yaml` | NVDA | Pre-earnings |
| `analysis/earnings/NFLX_20250118T0800.yaml` | NFLX | Pre-earnings |

### Stock Analyses
| File | Ticker | Type |
|------|--------|------|
| `analysis/stock/AMD_20250122T0935.yaml` | AMD | Technical |
| `analysis/stock/PFE_20250118T1400.yaml` | PFE | Value |
| `analysis/stock/ORCL_20251217T1000.yaml` | ORCL | Post-earnings |

### Other Documents
| Folder | Documents |
|--------|-----------|
| `analysis/research/` | AI CapEx cycle research |
| `analysis/ticker-profiles/` | NVDA profile |
| `trades/` | NVDA trade journal |
| `learnings/` | Loss aversion bias |
| `strategies/` | Earnings momentum |
| `scanners/daily/` | 7 daily scanners |
| `scanners/intraday/` | 2 intraday scanners |
| `scanners/weekly/` | 2 weekly scanners |

## Knowledge vs Skills

### This Repo: trading-knowledge/
**Contains:** Actual trading data and insights
- Your real analyses
- Your real trades
- Your real lessons learned
- Scanner configs (encodes YOUR edge)

### Companion: trading-skills/
**Contains:** Agent instructions and workflows
- How to create analyses
- How to run scanners
- How to manage trades
- Works with ANY AI agent

## Integration with trading-skills

| Skill | Creates Documents In |
|-------|---------------------|
| `earnings-analysis/` | `analysis/earnings/` |
| `stock-analysis/` | `analysis/stock/` |
| `research-analysis/` | `analysis/research/` |
| `ticker-profile/` | `analysis/ticker-profiles/` |
| `trade-journal/` | `trades/` |
| `watchlist/` | `watchlist/` |
| `post-trade-review/` | `reviews/` |
| `market-scanning/` | Uses `scanners/`, outputs to `watchlist/` |

## Getting Started

1. **With AI Agent:** Point agent to `trading-skills/` for instructions
2. **Agent creates documents** following skill workflows
3. **Documents saved here** in appropriate folders
4. **Optional:** Sync to LightRAG for semantic search

## Version
- Current: 2.0.0
- Last Updated: 2025-01-26
