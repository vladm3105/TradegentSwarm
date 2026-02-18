---
mode: agent
description: Document executed trades with entry/exit details, rationale, and outcomes
---

# Trade Journal

Document a trade for **${input:ticker}** — action: **${input:action}** (entry / exit / update).

## Context

Load the full skill definition and output template:
- #file:../../trading/skills/trade-journal/SKILL.md
- #file:../../trading/skills/trade-journal/template.yaml

Check for existing trades:
- #file:../../trading/knowledge/trades/

## When to Use

- Immediately after entering a position
- Immediately after exiting a position
- To update notes during an open trade

## Workflow

1. **Read skill definition** from `trading/skills/trade-journal/SKILL.md`
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
   - Classify outcome (big win / small win / breakeven / small loss / big loss)
   - **Trigger post-trade-review**
5. **Generate output** using `trading/skills/trade-journal/template.yaml`
6. **Save** to `trading/knowledge/trades/{TICKER}_{YYYYMMDDTHHMM}.yaml`

## Position Sizing Verification

Before entry, verify:
1. Stop Distance % = (Entry − Stop) / Entry
2. Dollar Risk = Portfolio × Risk % (1–2% max)
3. Shares = Dollar Risk / (Entry × Stop Distance %)
4. Position % = (Shares × Entry) / Portfolio
5. MAX POSITION: 20% of portfolio
6. Portfolio Heat: Sum of all position risks < 15%

## Chaining

- Entry triggered by **earnings-analysis** or **stock-analysis** recommendation
- Entry may come from **watchlist** trigger firing
- Exit automatically triggers **post-trade-review** prompt
- Results update **ticker-profile** trading history

## Output

Save to `trading/knowledge/trades/` using `{TICKER}_{YYYYMMDDTHHMM}.yaml`. Use actual fill prices, not intended prices.
