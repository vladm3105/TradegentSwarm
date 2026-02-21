# Trade Journal Skill v2.1

## Purpose
Document executed trades with entry/exit details, rationale, psychological state, and decision quality assessment.

## When to Use
- Before entering: Complete pre-trade checklist
- Immediately after entering a position
- During trade: Update notes and psychological state
- Immediately after exiting a position

## Required Inputs
- Ticker symbol
- Entry/exit price and date
- Number of shares/contracts
- Link to analysis that triggered trade

## Output
- File: `{TICKER}_{YYYYMMDDTHHMM}.yaml`
- Location: `knowledge/trades/`

---

## Trade Documentation Framework (6 Steps)

```
Step 1: Pre-Trade Checklist    → Verify readiness
Step 2: Entry Documentation    → Record entry details
Step 3: Psychological State    → Assess mental state
Step 4: Decision Quality       → Grade the process
Step 5: During Trade Updates   → Monitor and log
Step 6: Exit Documentation     → Record exit with loss aversion check
```

---

## Step 1: Pre-Trade Checklist (NEW v2.1)

```
BEFORE EXECUTING TRADE:

□ Analysis completed
  Analysis file: ___

□ Do Nothing gate passed
  Result: PASS / FAIL

□ Bias check completed
  Any biases flagged: Y/N

□ Position size calculated
  Shares: ___
  % of portfolio: ___

□ Stop loss defined
  Price: $___
  Type: Hard / Mental / Trailing

□ Targets defined
  Target 1: $___
  Target 2: $___

□ Risk acceptable
  Dollar risk: $___
  % of portfolio at risk: ___

CHECKLIST COMPLETE: Y/N

IF ANY BOX UNCHECKED:
→ Do not enter trade
→ Complete missing items first
```

---

## Step 2: Entry Documentation

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
□ Confidence % from analysis

Entry Notes:
□ Why entering now (trigger that fired)
□ Any concerns
```

---

## Step 3: Psychological State Assessment (NEW v2.1)

```
ENTRY PSYCHOLOGICAL STATE:

Overall state: Confident / Neutral / Nervous / FOMO / Reluctant

SCORE EACH (1-10):
| Factor | Score | Notes |
|--------|-------|-------|
| Confidence | | |
| Anxiety | | |
| FOMO | | |
| Clarity | | |

PHYSICAL STATE:
Well-rested / Tired / Stressed / Distracted

MARKET STATE:
Normal / Volatile / Trending / Choppy

ENTRY QUALITY ASSESSMENT:
Write brief assessment of decision-making process:
- Was I calm and clear?
- Did I follow the process?
- Any red flags I'm ignoring?

IF ANXIETY > 7 OR FOMO > 5:
→ Consider reducing position size
→ Document why proceeding anyway
```

---

## Step 4: Decision Quality Assessment (NEW v2.1)

```
GRADE YOUR ENTRY DECISION:

PROCESS:
□ Did I follow the analysis process? Y/N
□ Was this rushed? Y/N
□ Was thesis clear before entering? Y/N
□ Did I consider alternatives? Y/N

ENTRY GRADE: A/B/C/D/F
A = Perfect process, calm execution
B = Good process, minor issues
C = Acceptable, some shortcuts
D = Poor process, lucky if it works
F = No process, gambling

NOTES:
What would have made this an A?
```

---

## Step 5: During Trade Updates

```
UPDATE AS NEEDED:

PRICE ACTION NOTES:
| Date | Price | Note | Thesis Valid? |
|------|-------|------|---------------|
| | | | Y/N |

PSYCHOLOGICAL STATE DURING TRADE:
| Date | Emotional State | Urge to Exit (1-10) | Urge to Add (1-10) | Notes |
|------|-----------------|---------------------|--------------------|-|
| | | | | |

STOP ADJUSTMENTS:
□ New stop level
□ Reason for change
□ ONLY tighten, never widen

PARTIAL EXITS:
| Date | Price | Shares | Reason | Remaining | Planned/Emotional |
|------|-------|--------|--------|-----------|-------------------|
| | | | | | |

REAL-TIME NOTES (v2.1):
Capture thoughts as they happen:
| Timestamp | Price | Thought | Action Taken |
|-----------|-------|---------|--------------|
| | | | |
```

---

## Step 6: Exit Documentation

```
LOSS AVERSION PRE-EXIT CHECK (v2.1):

*** CRITICAL: Complete this BEFORE exiting profitable positions ***

IF position is profitable AND considering exit:

□ Is thesis still intact? Y/N
□ Is catalyst still pending? Y/N
□ Am I exiting due to FEAR or LOGIC?

PRE-EXIT GATE:
| Question | Answer |
|----------|--------|
| Thesis still valid? | Y/N |
| Catalyst still pending? | Y/N |
| Exit reason | LOGIC / FEAR |
| Have I recalculated EV? | Y/N |

IF thesis_intact AND catalyst_pending AND reason=FEAR:
→ GATE RESULT: HOLD
→ Reminder: "The catalyst justified entry; don't exit before it arrives"
→ Minimum: Hold 50% through catalyst

IF thesis_changed OR catalyst_occurred OR reason=LOGIC:
→ GATE RESULT: EXIT OK
→ Proceed with exit

---

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
□ Manual exit - emotional (document why)
□ Partial exit - scaling out

EXIT PSYCHOLOGICAL STATE:
Overall: Confident / Neutral / Nervous / Relief / Regret / Frustration

□ Did I follow the plan? Y/N
□ Was this an emotional exit? Y/N

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

VS PLAN (v2.1):
| Metric | Planned | Actual | Notes |
|--------|---------|--------|-------|
| Target | | | |
| Exit price | | | |
| Captured % of planned | | | |

Exit Notes:
□ What happened
□ Did you follow the plan?
□ Emotional state at exit

DECISION QUALITY - EXIT:
□ Process followed? Y/N
□ Loss aversion check passed? Y/N
□ Emotional decision? Y/N
GRADE: A/B/C/D/F

OVERALL DECISION QUALITY:
Entry grade + Management grade + Exit grade
OVERALL GRADE: A/B/C/D/F
Reasoning: ___

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

See `template.yaml` for the output format (v2.1).

---

## Quality Checklist

Pre-Trade:
```
□ Pre-trade checklist complete
□ All items checked
□ Analysis linked
```

On Entry:
```
□ Actual fill price recorded (not intended)
□ Stop loss set
□ Risk calculated
□ Analysis linked
□ Thesis documented
□ Psychological state assessed
□ Entry decision graded
```

During Trade:
```
□ Updates logged with dates
□ Psychological state tracked
□ Stop adjustments documented
□ Partial exits recorded
```

On Exit:
```
□ Loss aversion check completed (if profitable)
□ Actual fill recorded
□ Exit reason specified
□ P&L calculated correctly
□ Psychological state recorded
□ Exit decision graded
□ Overall decision quality assessed
□ Post-trade review triggered
```

---

*Skill Version: 2.1*
*Updated: 2026-02-21*
