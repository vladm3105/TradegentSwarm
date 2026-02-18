---
title: Trade Journal
tags:
  - trading-skill
  - trade-management
  - execution
  - ai-agent-primary
custom_fields:
  skill_category: trade-management
  priority: primary
  development_status: active
  upstream_artifacts:
    - earnings-analysis
    - stock-analysis
    - watchlist
  downstream_artifacts:
    - post-trade-review
    - ticker-profile
  triggers:
    - "trade journal"
    - "log trade"
    - "record trade"
    - "entered position"
    - "exited position"
    - "bought"
    - "sold"
  auto_invoke: true
---

# Trade Journal Skill

Use this skill to document executed trades with entry/exit details, rationale, and outcomes. Auto-invokes when user mentions entering or exiting a position.

## When to Use

- Immediately after entering a position
- Immediately after exiting a position
- To update notes during an open trade
- User says "I bought/sold TICKER"

## Workflow

1. **Read skill definition**: Load `trading/skills/trade-journal/SKILL.md`
2. **Determine action type**:
   - **entry**: Record new position
   - **exit**: Close position, calculate P&L
   - **update**: Add notes during trade
3. **For entry**, record:
   - Entry details (actual fill price, date, size, order type)
   - Risk management (stop loss level, targets)
   - Link to triggering analysis
   - Entry notes (why now, concerns, emotional state)
4. **For exit**, record:
   - Exit details (actual fill price, date, reason)
   - Calculate: Gross P&L, Net P&L, Return %
   - Classify outcome (big win/small win/breakeven/small loss/big loss)
   - **Trigger post-trade-review**
5. **Generate output** using `trading/skills/trade-journal/template.yaml`
6. **Save** to `trading/knowledge/trades/{TICKER}_{YYYYMMDDTHHMM}.yaml`

## Position Sizing Verification

Before entry, verify:
```
1. Stop Distance % = (Entry - Stop) / Entry
2. Dollar Risk = Portfolio × Risk % (1-2% max)
3. Shares = Dollar Risk / (Entry × Stop Distance %)
4. Position % = (Shares × Entry) / Portfolio
5. MAX POSITION: 20% of portfolio
6. Portfolio Heat: Sum of all position risks < 15%
```

## Chaining

- Entry triggered by **earnings-analysis** or **stock-analysis** recommendation
- Entry may come from **watchlist** trigger firing
- Exit automatically triggers **post-trade-review** skill
- Results update **ticker-profile** trading history

## Arguments

- `$ARGUMENTS`: Ticker symbol and action (entry/exit/update)

## Execution

Document the trade for $ARGUMENTS. Read the full skill definition from `trading/skills/trade-journal/SKILL.md`. Use actual fill prices, not intended prices.
