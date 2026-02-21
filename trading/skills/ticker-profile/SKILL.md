# Ticker Profile Skill v2.1

## Purpose
Maintain persistent knowledge about frequently traded stocks, including analysis track record, bias history, and learned patterns.

## When to Use
- First trade in a new ticker
- Updating known stock after earnings
- Building knowledge on focus stocks
- After post-trade review (to update track record)

## Output
- File: `{TICKER}_{YYYYMMDDTHHMM}.yaml`
- Location: `knowledge/analysis/ticker-profiles/`

---

## Profile Framework (8 Sections)

```
Section 1: Company Basics          → Static company info
Section 2: Earnings Patterns       → Historical earnings data
Section 3: Technical Levels        → Key price levels
Section 4: Your Edge               → What you know better
Section 5: Analysis Track Record   → Prediction accuracy
Section 6: Trading History         → Your trades in this ticker
Section 7: Bias History            → Common biases and costs
Section 8: Known Risks             → Structural and cyclical risks
```

---

## Section 1: Company Basics

```
STATIC INFO:
□ Company name
□ Sector / Industry
□ Market cap tier (mega/large/mid/small)
□ Market cap ($B)
□ Business description (1-2 sentences)
□ Key products/services
□ Key competitors
```

---

## Section 2: Earnings Patterns

```
HISTORICAL DATA (8 quarters):

| Quarter | EPS Est | EPS Act | Surprise % | Rev Est | Rev Act | 1D Move | 5D Move | Guidance |
|---------|---------|---------|------------|---------|---------|---------|---------|----------|
| Q4 2025 | | | | | | | | R/M/L |
| Q3 2025 | | | | | | | | R/M/L |
| ... | | | | | | | | |

PATTERNS TO NOTE:
□ Beat rate: ___/8 (___%)
□ Typical surprise magnitude: ____%
□ Average beat move: +___%
□ Average miss move: -___%
□ Guidance tendencies: Usually raises / maintains / lowers
□ Seasonal patterns: Q___ typically strongest/weakest
```

---

## Section 3: Technical Levels

```
KEY LEVELS:

All-time high: $___  (Date: ___)
52-week high:  $___
52-week low:   $___

MAJOR SUPPORT:
| Price | Significance | Times Tested |
|-------|--------------|--------------|
| | | |

MAJOR RESISTANCE:
| Price | Significance | Times Tested |
|-------|--------------|--------------|
| | | |

Last updated: {YYYY-MM-DD}

Update after significant moves.
```

---

## Section 4: Your Edge

```
DOCUMENT YOUR EDGE:

What you understand better than consensus:
___

Reliable signals for this stock:
| Signal | Description | Historical Accuracy |
|--------|-------------|---------------------|
| | | ___% |

Common mistakes to avoid:
| Mistake | Lesson | Occurrences |
|---------|--------|-------------|
| | | |

Notes:
___

*** This is the most valuable section. Update after each trade. ***
```

---

## Section 5: Analysis Track Record (NEW v2.1)

```
*** CRITICAL: Track your prediction accuracy for this ticker ***

ANALYSIS STATISTICS:
- Total analyses: ___
- Earnings analyses: ___
- Stock analyses: ___

PREDICTION ACCURACY:

Direction:
- Correct: ___
- Total: ___
- Accuracy: ____%

Magnitude (within 50%):
- Correct: ___
- Total: ___
- Accuracy: ____%

Catalyst:
- Correct: ___
- Total: ___
- Accuracy: ____%

EARNINGS PREDICTIONS:
- Beat predicted correctly: ___/___
- Miss predicted correctly: ___/___
- Overall accuracy: ____%

RECOMMENDATION PERFORMANCE:
| Recommendation | Count | Avg Return |
|----------------|-------|------------|
| STRONG_BUY | | % |
| BUY | | % |
| WATCH (converted) | | |
| AVOID (dodged) | | |

RECENT ANALYSES:
| File | Date | Recommendation | Outcome | Grade |
|------|------|----------------|---------|-------|
| | | | | |

TRACK RECORD SUMMARY:
Are you good at analyzing this ticker?
What types of predictions are you best/worst at?
```

---

## Section 6: Trading History

```
YOUR TRADES IN THIS TICKER:

STATISTICS:
- Total trades: ___
- Wins: ___
- Losses: ___
- Win rate: ____%
- Total P&L: $___
- Average return: ____%
- Average holding days: ___

TRADE LOG:
| Date | Direction | Return % | Outcome | Note | Review File |
|------|-----------|----------|---------|------|-------------|
| | L/S | | W/L | | |

BEST TRADE:
___

WORST TRADE:
___

KEY LEARNINGS FROM TRADING THIS TICKER:
1. ___
2. ___
```

---

## Section 7: Bias History (NEW v2.1)

```
*** Track which biases affect you with this ticker ***

TOTAL BIAS COST (estimated): $___

COMMON BIASES:
| Bias | Occurrences | Total Cost | Countermeasure | Effective? |
|------|-------------|------------|----------------|------------|
| | | $ | | Y/N |

MOST COSTLY BIAS: ___
MOST FREQUENT BIAS: ___

BIAS SUMMARY:
What patterns of bias do you see with this ticker?
Are certain biases more common with this ticker type (mega-cap tech, earnings play, etc.)?
```

---

## Section 8: Known Risks (NEW v2.1)

```
STRUCTURAL RISKS (Business model threats):
| Risk | Description | Severity | Moat Erosion? |
|------|-------------|----------|---------------|
| | | H/M/L | Y/N |

CYCLICAL RISKS (Temporary pressures):
| Risk | Description | Cycle Phase |
|------|-------------|-------------|
| | | Early/Mid/Late |

EXECUTION RISKS (Management/operational):
| Risk | Description |
|------|-------------|
| | |

RISK SUMMARY:
What are the key risks to monitor for this ticker?
When would you abandon a bullish thesis?
```

---

## Section 9: Learned Patterns (NEW v2.1)

```
PATTERNS OBSERVED FOR THIS TICKER:

| Pattern | Description | Trigger Conditions | Expected Outcome | Occurrences | Success Rate |
|---------|-------------|-------------------|------------------|-------------|--------------|
| | | | | | % |

SOURCE TRADES:
Which trades taught these patterns?
- Pattern 1: trades/___
- Pattern 2: trades/___
```

---

## Key Dates

```
CALENDAR:
□ Typical earnings months: [e.g., Jan, Apr, Jul, Oct]
□ Next earnings: {YYYY-MM-DD}
□ Dividend dates: ___
□ Other key events:
  - Event: ___
    Date: ___
```

---

## Maintenance Schedule

```
UPDATE AFTER:
□ Each earnings report
  - Update earnings history
  - Update track record if analyzed
□ Each trade you make
  - Update trading history
  - Update bias history
□ Each post-trade review
  - Update edge section
  - Update learned patterns
□ Significant price moves
  - Update technical levels
□ Major news events
  - Update known risks

QUARTERLY:
□ Refresh all levels
□ Update earnings history
□ Review edge section
□ Verify known risks still relevant
□ Calculate updated track record stats
```

---

## Template

See `template.yaml` for the output format (v2.1).

---

## Quality Checklist

```
BASICS:
□ Company info complete
□ Key competitors listed

EARNINGS:
□ 8 quarters of history
□ Patterns calculated
□ Seasonal notes added

TECHNICAL:
□ All major levels documented
□ ATH and 52-week range current

EDGE:
□ Understanding documented
□ Reliable signals listed
□ Mistakes to avoid noted

TRACK RECORD:
□ Prediction accuracy calculated
□ Recommendation performance tracked
□ Recent analyses listed

TRADING:
□ All trades logged
□ Statistics calculated
□ Key learnings extracted

BIASES:
□ Bias history tracked
□ Costs estimated
□ Countermeasures documented

RISKS:
□ Structural risks identified
□ Cyclical risks noted
□ Risk summary written

PATTERNS:
□ Learned patterns documented
□ Source trades linked

MAINTENANCE:
□ Last update date noted
□ Next earnings date current
```

---

*Skill Version: 2.1*
*Updated: 2026-02-21*
