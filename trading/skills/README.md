# Trading Skills for AI Agents

Agent-agnostic skill definitions for systematic trading. Each skill is **self-contained** and **single-purpose**.

## Design Principles

1. **Single Responsibility**: One skill = one task type
2. **Agent-Agnostic**: Works with Claude, GPT, Gemini, or any LLM
3. **Self-Contained**: Each skill has all context needed
4. **Composable**: Workflows chain skills together

## Skills Index

### Analysis Skills
| Skill | Purpose | Output |
|-------|---------|--------|
| [earnings-analysis](earnings-analysis/) | 8-phase pre-earnings analysis | Earnings analysis document |
| [stock-analysis](stock-analysis/) | 7-phase non-earnings analysis | Stock analysis document |
| [research-analysis](research-analysis/) | Macro/sector/thematic research | Research document |
| [ticker-profile](ticker-profile/) | Persistent ticker knowledge | Ticker profile document |

### Trade Management Skills
| Skill | Purpose | Output |
|-------|---------|--------|
| [trade-journal](trade-journal/) | Record executed trades | Trade journal entry |
| [watchlist](watchlist/) | Track potential trades | Watchlist entry |
| [post-trade-review](post-trade-review/) | Analyze completed trades | Review document |

### Scanning Skills
| Skill | Purpose | Output |
|-------|---------|--------|
| [market-scanning](market-scanning/) | Find trading opportunities | Watchlist candidates |

## Skill Structure

Each skill folder contains:
```
skill-name/
├── SKILL.md           # Complete instructions (required)
└── template.yaml      # Output template (if applicable)
```

## How to Use

### For Any AI Agent
1. Read the `SKILL.md` file for the task you need
2. Follow the workflow steps exactly
3. Output using the `template.yaml` structure
4. Store output in corresponding `knowledge/` folder

## File Naming Convention

All outputs use: `{TICKER}_{YYYYMMDDTHHMM}.yaml`

Example: `NVDA_20250120T0900.yaml`

## Integration with knowledge

```
skills/                  →    knowledge/
─────────────────────────────────────────────────
earnings-analysis/       →    analysis/earnings/
stock-analysis/          →    analysis/stock/
research-analysis/       →    analysis/research/
ticker-profile/          →    analysis/ticker-profiles/
trade-journal/           →    trades/
watchlist/               →    watchlist/
post-trade-review/       →    reviews/
market-scanning/         →    scanners/ (configs live here)
```

## Version
- Current: 2.0.0
- Last Updated: 2025-01-26
