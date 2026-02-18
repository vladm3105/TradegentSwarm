# Watchlist Skill

## Purpose
Track potential trades that don't yet meet entry criteria. Monitor for trigger conditions.

## When to Use
- Analysis recommendation is WATCH
- Good setup but waiting for trigger
- Scanner candidate needs more time
- Tracking for future opportunity

## Required Inputs
- Ticker symbol
- Entry trigger condition
- Invalidation condition
- Source (analysis or scanner)

## Output
- File: `{TICKER}_{YYYYMMDDHHMM}.yaml`
- Location: `trading-knowledge/watchlist/`

---

## Watchlist Management

### Adding to Watchlist

```
WHEN TO ADD:
□ Analysis score 5.5-6.4 (WATCH recommendation)
□ Good setup waiting for specific trigger
□ Scanner candidate needs confirmation
□ Quality stock at wrong price

REQUIRED FIELDS:
□ Ticker
□ Entry trigger (specific, measurable)
□ Target entry price or condition
□ Invalidation criteria
□ Expiration date (max 30 days default)
□ Source (which analysis/scanner)

PRIORITY LEVELS:
- High: Likely to trigger soon, strong setup
- Medium: Good setup, needs more time
- Low: Interesting but speculative
```

### Entry Trigger Types

```
PRICE TRIGGERS:
□ Breakout above $X
□ Pullback to $X
□ Break below $X (for shorts)

CONDITION TRIGGERS:
□ Earnings report
□ FDA decision
□ Technical pattern completion
□ Volume confirmation

COMBINED TRIGGERS:
□ Price above $X WITH volume > Y
□ Break above resistance AND sector confirming
```

### Invalidation Criteria

```
PRICE INVALIDATION:
□ Breaks below $X
□ Breaks above $X (for shorts)
□ Closes below support

CONDITION INVALIDATION:
□ Earnings miss
□ Thesis broken by news
□ Sector turns negative

TIME INVALIDATION:
□ No trigger in X days
□ Setup becomes stale
```

### Daily Watchlist Review

```
EVERY TRADING DAY:

□ Check each entry against current price
□ Did any triggers fire? → Execute analysis
□ Did any invalidations occur? → Remove
□ Any news affecting thesis? → Update or remove

WEEKLY:
□ Remove stale entries (>30 days)
□ Reprioritize based on likelihood
□ Check for new candidates from scanners
```

### Monitoring Log

```
FOR EACH WATCHLIST ENTRY:

Log significant observations:
- Date
- Price at time
- Observation
- Action taken (if any)

This creates a history that's useful for learning.
```

---

## Template

See `template.yaml` for the output format.

---

## Quality Checklist

When Adding:
□ Entry trigger is specific and measurable
□ Invalidation is clear
□ Expiration date set
□ Priority assigned
□ Source linked

Daily Review:
□ All entries checked
□ Triggered entries actioned
□ Invalid entries removed
□ Notes updated
