# Trade Journal

## Purpose
Documents all executed trades with entry/exit details, rationale, and outcomes. The source of truth for actual trading activity.

## What Belongs Here
- Every executed trade (entries and exits)
- Position sizing decisions
- Real P&L tracking
- Links to original analysis

## File Naming Convention
```
{YYYY}/{MM}/{TICKER}_{YYYYMMDDTHHMM}.yaml
```
Example: `2025/01/NVDA_20250115T1000.yaml`

## How to Use

### Opening a Trade
1. Copy template from `reference/templates/trade-journal.yaml`
2. Fill in entry details:
   - Entry price, date, size
   - Link to analysis document
   - Original thesis
   - Planned stop and target
3. Save immediately after execution

### Closing a Trade
1. Update the same document with exit details:
   - Exit price, date
   - Exit reason (target/stop/manual)
   - Actual P&L
2. Create post-trade review in `reviews/`

### For Options Trades
- Document strike, expiration, premium
- Track Greeks at entry
- Note IV level and expected crush

## Integration
- Links to: `analysis/earnings/` or `analysis/stock/` (source analysis), `reviews/` (post-trade review)
- Updates: `analysis/ticker-profiles/` (trade history per ticker)

## Required Fields
- Entry: date, price, size, ticker, direction
- Exit: date, price, reason
- P&L: gross, fees, net, return %

## Best Practices
- Document immediately after execution
- Don't edit historical entries (append notes instead)
- Always link to original analysis
- Be honest about mistakes
