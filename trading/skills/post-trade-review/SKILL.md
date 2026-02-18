# Post-Trade Review Skill

## Purpose
Analyze completed trades to extract lessons and improve future performance. Closes the learning loop.

## When to Use
- After every closed trade (win or loss)
- Within 24-48 hours of exit
- While memory is fresh

## Required Inputs
- Trade journal entry (closed trade)
- Original analysis
- Actual outcomes

## Output
- File: `{TICKER}_{YYYYMMDDTHHMM}_review.yaml`
- Location: `knowledge/reviews/`

---

## Review Framework

### Step 1: Document Facts

```
TRADE FACTS:
□ Ticker
□ Direction
□ Entry date, price
□ Exit date, price
□ Holding period
□ Gross P&L
□ Net P&L
□ Return %

ORIGINAL THESIS:
□ What was the catalyst?
□ What was supposed to happen?
□ What was the expected timeframe?
□ What was the target?
□ What was the stop?
```

### Step 2: Execution Analysis

```
ENTRY EXECUTION:

Planned entry: $___
Actual entry:  $___
Slippage:      $___  (___%)

Entry Timing:
□ Early (before trigger)
□ On time (at trigger)
□ Late (chased)

Entry Grade: A / B / C / D / F
Notes: ___


EXIT EXECUTION:

Planned exit: $___  (target: $___ / stop: $___)
Actual exit:  $___

Exit Reason:
□ Target hit
□ Stop hit
□ Manual - thesis changed
□ Manual - time stop
□ Manual - other

Followed Plan: Yes / No

Exit Timing:
□ Early (left money on table)
□ On time (per plan)
□ Late (held too long)

Exit Grade: A / B / C / D / F
Notes: ___


POSITION SIZING:

Planned size: ___% of portfolio
Actual size:  ___% of portfolio

Appropriate for conviction? Yes / No
Notes: ___
```

### Step 3: Thesis Accuracy

```
COMPONENT ANALYSIS:

Direction:
- Predicted: Up / Down
- Actual:    Up / Down
- Correct?   Yes / No

Magnitude:
- Predicted: ___% move
- Actual:    ___% move
- Within 50%? Yes / No

Timing:
- Predicted: ___ days
- Actual:    ___ days
- Correct?   Yes / No

Catalyst:
- Predicted: ___
- Actual:    ___
- Correct?   Yes / No / Partially

FOR EARNINGS TRADES:
- Customer demand signal: Bullish / Neutral / Bearish
- Signal accuracy:        Correct / Wrong
- Beat/miss prediction:   Correct / Wrong
```

### Step 4: What Worked / What Didn't

```
WHAT WORKED:
1. ___
2. ___
3. ___

WHAT DIDN'T WORK:
1. ___
2. ___
3. ___

SURPRISES:
1. ___
2. ___

MISSED SIGNALS:
1. ___
2. ___
```

### Step 5: Bias Check Retrospective

```
For each bias, score 1-5 (1 = not present, 5 = strongly affected):

RECENCY BIAS: ___/5
- Did recent events skew judgment?
- Notes: ___

CONFIRMATION BIAS: ___/5
- Did you ignore contrary evidence?
- Notes: ___

OVERCONFIDENCE: ___/5
- Were you too certain?
- Notes: ___

LOSS AVERSION: ___/5
- Did fear affect decisions?
- Notes: ___

ANCHORING: ___/5
- Were you stuck on a price?
- Notes: ___

NEW BIASES IDENTIFIED:
- Bias: ___
- How it affected trade: ___
```

### Step 6: Grade the Trade

```
COMPONENT GRADES:

Analysis Quality:      A / B / C / D / F
Entry Execution:       A / B / C / D / F
Exit Execution:        A / B / C / D / F
Risk Management:       A / B / C / D / F
Emotional Discipline:  A / B / C / D / F

OVERALL GRADE: A / B / C / D / F

Grade Rationale:
___

What Would Make This an A?
___
```

### Step 7: Extract Lessons

```
PRIMARY LESSON:

Lesson: ___

Action to take differently: ___

Applies to: All trades / Earnings / Technical / This ticker


SECONDARY LESSONS:

1. Lesson: ___
   Action: ___

2. Lesson: ___
   Action: ___


PATTERN TO ADD:

Pattern: ___
Description: ___
Expected outcome: ___
→ Add to learnings/patterns/


RULE TO ADD/MODIFY:

Rule: ___
Reason: ___
→ Add to learnings/rules/
```

---

## Template

See `template.yaml` for the output format.

---

## Quality Checklist

□ All facts documented accurately
□ Entry and exit graded honestly
□ Thesis accuracy analyzed component by component
□ Bias check completed with scores
□ Overall grade assigned with rationale
□ At least one actionable lesson extracted
□ Lessons linked to knowledge base
