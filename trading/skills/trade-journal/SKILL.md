# Trade Journal Skill

## Purpose
Document executed trades with entry/exit details, rationale, and outcomes.

## When to Use
- Immediately after entering a position
- Immediately after exiting a position
- To update notes during a trade

## Required Inputs
- Ticker symbol
- Entry/exit price and date
- Number of shares/contracts
- Link to analysis that triggered trade

## Output
- File: `{TICKER}_{YYYYMMDDTHHMM}.yaml`
- Location: `knowledge/trades/`

---

## Trade Documentation Workflow

### On Entry

```
IMMEDIATELY AFTER EXECUTION:

Record Entry Details:
□ Ticker
□ Direction (long/short)
□ Entry date and time
□ Entry price (actual fill, not intended)
□ Number of shares/contracts
□ Position value
□ Order type used

Record Risk Management:
□ Stop loss level
□ Stop type (hard/mental/trailing)
□ Target price(s)
□ Risk per share: Entry - Stop
□ Total risk: Risk per share × Shares
□ % of portfolio at risk

Link to Analysis:
□ Analysis file that triggered this trade
□ Original thesis (copy 1-2 sentences)
□ Expected catalyst
□ Expected timeframe

Entry Notes:
□ Why entering now (trigger that fired)
□ Any concerns
□ Emotional state (confident/nervous/FOMO)
```

### During Trade

```
UPDATE AS NEEDED:

Price Action Notes:
□ Significant moves
□ News or events
□ Thesis still valid?

Stop Adjustments:
□ New stop level
□ Reason for change
□ ONLY tighten, never widen

Partial Exits:
□ Date, price, quantity
□ Reason
□ Remaining position
```

### On Exit

```
IMMEDIATELY AFTER EXIT:

Record Exit Details:
□ Exit date and time
□ Exit price (actual fill)
□ Shares exited
□ Order type used

Exit Reason (pick one):
□ Target hit
□ Stop loss hit
□ Manual exit - thesis changed
□ Manual exit - time stop
□ Manual exit - better opportunity
□ Partial exit - scaling out

Calculate Results:
□ Gross P&L = (Exit - Entry) × Shares
□ Fees/commissions
□ Net P&L = Gross - Fees
□ Return % = Net P&L / Entry Value
□ Holding period in days

Classify Outcome:
□ Big win (>10%)
□ Small win (2-10%)
□ Breakeven (-2% to 2%)
□ Small loss (-2% to -10%)
□ Big loss (<-10%)

Exit Notes:
□ What happened
□ Did you follow the plan?
□ Emotional state at exit

TRIGGER POST-TRADE REVIEW
```

---

## Position Sizing Reference

```
BEFORE ENTRY, VERIFY:

1. Calculate Risk:
   Stop Distance % = (Entry - Stop) / Entry
   
2. Determine Dollar Risk:
   Dollar Risk = Portfolio × Risk % (1-2% max)
   
3. Calculate Shares:
   Shares = Dollar Risk / (Entry × Stop Distance %)
   
4. Verify Position Size:
   Position Value = Shares × Entry
   Position % = Position Value / Portfolio
   
   MAX POSITION: 20% of portfolio
   
5. Check Portfolio Heat:
   Sum of all position risks < 15%
```

---

## Template

See `template.yaml` for the output format.

---

## Quality Checklist

On Entry:
□ Actual fill price recorded (not intended)
□ Stop loss set
□ Risk calculated
□ Analysis linked
□ Thesis documented

On Exit:
□ Actual fill recorded
□ Exit reason specified
□ P&L calculated correctly
□ Review triggered
