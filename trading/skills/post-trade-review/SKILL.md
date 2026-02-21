# Post-Trade Review Skill v2.1

## Purpose
Analyze completed trades to extract lessons, track data source effectiveness, and improve future performance. Closes the learning loop with validated rules.

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

## Review Framework (9 Steps)

```
Step 1: Document Facts              → Trade details
Step 2: Execution Analysis          → Entry/exit quality
Step 3: Thesis Accuracy             → What was right/wrong
Step 4: What Worked / Didn't        → Observations
Step 5: Data Source Effectiveness   → Which sources predicted well
Step 6: Bias Check Retrospective    → Bias impact with costs
Step 7: Grade the Trade             → Overall assessment
Step 8: Extract Lessons             → Patterns and rules
Step 9: Create Learnings            → Formalize for framework
```

---

## Step 1: Document Facts

```
TRADE FACTS:
□ Ticker
□ Direction
□ Entry date, price
□ Exit date, price
□ Holding period (days)
□ Gross P&L
□ Net P&L
□ Return %

ORIGINAL THESIS:
□ What was the catalyst?
□ What was supposed to happen?
□ What was the expected timeframe?
□ What was the target?
□ What was the stop?
□ What was the confidence % from analysis?

LINK FILES:
□ Trade journal file: ___
□ Analysis file: ___
```

---

## Step 2: Execution Analysis

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
□ Manual - emotional
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

---

## Step 3: Thesis Accuracy

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

---

## Step 4: What Worked / What Didn't

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

---

## Step 5: Data Source Effectiveness (NEW v2.1)

```
*** CRITICAL: Track which sources are predictive ***

FOR EACH DATA SOURCE USED IN ANALYSIS:

| Source | Used For | Expected Weight | Actual Predictive | Adjust? |
|--------|----------|-----------------|-------------------|---------|
| | | 0.0-1.0 | High/Medium/Low | +/=/- |
| | | | | |
| | | | | |

EXAMPLES:
| Source | Used For | Expected | Actual | Adjust? |
|--------|----------|----------|--------|---------|
| Hyperscaler CapEx | Demand signal | 0.3 | High | + |
| Analyst estimates | EPS prediction | 0.2 | Low | - |
| Short interest | Sentiment | 0.1 | Medium | = |

SOURCE EFFECTIVENESS SUMMARY:
What sources were most predictive for this trade?
What sources led you astray?
What adjustments will you make for future analyses of this ticker?

This data feeds into ticker-profile and analysis weights.
```

---

## Step 6: Bias Check Retrospective

```
For each bias, score 1-5 (1 = not present, 5 = strongly affected):

RECENCY BIAS: ___/5
- Did recent events skew judgment?
- Notes: ___
- Estimated cost: $___

CONFIRMATION BIAS: ___/5
- Did you ignore contrary evidence?
- Notes: ___
- Estimated cost: $___

OVERCONFIDENCE: ___/5
- Were you too certain?
- Notes: ___
- Estimated cost: $___

LOSS AVERSION: ___/5
- Did fear affect decisions?
- Premature exit? Y/N
- Notes: ___
- Estimated cost: $___
  (For premature exit: What was move AFTER you exited?)

TIMING CONSERVATISM: ___/5
- Did you wait too long to enter?
- Notes: ___
- Estimated cost: $___

ANCHORING: ___/5
- Were you stuck on a price?
- Notes: ___
- Estimated cost: $___

NEW BIASES IDENTIFIED:
| Bias | How it affected trade | Estimated cost |
|------|----------------------|----------------|
| | | $ |

TOTAL BIAS COST ESTIMATE: $___


COUNTERMEASURES NEEDED (v2.1):
For significant biases (score 4+):

| Bias Type | Rule | Implementation | Checklist Addition | Mantra |
|-----------|------|----------------|-------------------|--------|
| | | | | |

Example:
| loss_aversion | If profitable AND thesis intact AND catalyst pending → Hold 50% | Add pre-exit gate | "Don't exit for fear before catalyst" | "The catalyst justified entry" |
```

---

## Step 7: Grade the Trade

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

---

## Step 8: Extract Lessons

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
Trigger conditions:
  - ___
  - ___
Expected outcome: ___
Historical accuracy: ___% (from this and similar trades)
→ Add to pattern library? Y/N


RULE TO ADD/MODIFY:

Rule: ___
Reason: ___
Trigger condition: ___
Applies to: All / Earnings / Technical / Sector-specific / This ticker
→ Add to framework? Y/N

VALIDATION STATUS (v2.1):
- Status: Pending / Validated / Rejected
- Validation criteria:
  - ___
- Occurrences tested: ___
- Results so far: ___
```

---

## Step 9: Create Learnings (NEW v2.1)

```
IF PATTERN OR RULE IS SIGNIFICANT:

CREATES LEARNING?
Learning type: Bias / Pattern / Rule / None
Learning file: learnings/{type}/{name}.yaml
Learning ID: ___

LINK TO KNOWLEDGE BASE:
□ Update ticker-profile with trade result
□ Update analysis track record (if applicable)
□ Create learning file (if applicable)
□ Link similar reviews for pattern analysis


COMPARISON TO SIMILAR TRADES (v2.1):

| Past Trade | Similarity | Outcome | Lesson Applied? |
|------------|------------|---------|-----------------|
| | | | Y/N |

Did applying past lessons improve this trade?
What patterns recur?
```

---

## Template

See `template.yaml` for the output format (v2.1).

---

## Quality Checklist

```
FACTS:
□ All facts documented accurately
□ Trade journal and analysis linked

EXECUTION:
□ Entry and exit graded honestly
□ Slippage calculated
□ Plan adherence noted

ANALYSIS:
□ Thesis accuracy analyzed component by component
□ What worked / didn't documented

DATA SOURCES:
□ Source effectiveness tracked
□ Adjustments noted for future

BIASES:
□ Bias check completed with scores
□ Cost estimates for significant biases
□ Countermeasures defined for score 4+

GRADES:
□ All component grades assigned
□ Overall grade with rationale
□ "What would make A" answered

LESSONS:
□ At least one actionable lesson extracted
□ Pattern identified (if applicable)
□ Rule proposed (if applicable)
□ Validation criteria defined for rules

KNOWLEDGE BASE:
□ Ticker profile updated
□ Learning created (if applicable)
□ Similar trades compared
```

---

*Skill Version: 2.1*
*Updated: 2026-02-21*
