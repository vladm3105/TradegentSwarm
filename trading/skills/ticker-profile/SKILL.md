# Ticker Profile Skill

## Purpose
Maintain persistent knowledge about frequently traded stocks.

## When to Use
- First trade in a new ticker
- Updating known stock after earnings
- Building knowledge on focus stocks

## Output
- File: `{TICKER}_{YYYYMMDDTHHMM}.yaml`
- Location: `knowledge/analysis/ticker-profiles/`

---

## Profile Framework

### Company Basics

```
STATIC INFO:
□ Company name
□ Sector / Industry
□ Market cap tier (mega/large/mid/small)
□ Business description (1-2 sentences)
□ Key products/services
```

### Earnings Patterns

```
HISTORICAL DATA (8 quarters):
□ EPS actual vs estimate
□ Revenue actual vs estimate
□ Stock reaction (1-day, 5-day)
□ Guidance given

PATTERNS TO NOTE:
□ Beat rate
□ Typical surprise magnitude
□ Typical stock reaction
□ Guidance tendencies
□ Seasonal patterns
```

### Technical Levels

```
KEY LEVELS:
□ All-time high
□ 52-week high/low
□ Major support levels
□ Major resistance levels
□ Key moving averages

Update after significant moves.
```

### Your Edge

```
DOCUMENT:
□ What you understand better than consensus
□ Patterns you've observed
□ Reliable signals for this stock
□ Common mistakes to avoid

This is the most valuable section.
```

### Trading History

```
YOUR TRADES IN THIS TICKER:
□ Date, direction, outcome
□ Win rate
□ Average return
□ Best/worst trade
□ Lessons learned
```

### Key Dates

```
TRACK:
□ Earnings dates (historical pattern)
□ Dividend dates
□ Conference presentations
□ Index rebalancing impact
```

---

## Maintenance

```
UPDATE AFTER:
□ Each earnings report
□ Each trade you make
□ Significant price moves
□ Major news events

QUARTERLY:
□ Refresh all levels
□ Update earnings history
□ Review edge section
```

---

## Template

See `template.yaml` for the output format.
