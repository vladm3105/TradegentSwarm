---
mode: agent
description: Analyze completed trades and extract lessons to close the learning loop
---

# Post-Trade Review

Review the closed trade for **${input:ticker}**. Be honest in grading — learning requires truth.

## Context

Load the full skill definition and output template:
- #file:../../trading/skills/post-trade-review/SKILL.md
- #file:../../trading/skills/post-trade-review/template.yaml

Find the closed trade:
- #file:../../trading/knowledge/trades/

Check existing ticker profile:
- #file:../../trading/knowledge/analysis/ticker-profiles/

## When to Use

- After every closed trade (win or loss)
- Within 24–48 hours of exit (while memory is fresh)
- Automatically after trade-journal records an exit

## Workflow

1. **Read skill definition** from `trading/skills/post-trade-review/SKILL.md`
2. **Find closed trade** in `trading/knowledge/trades/`
3. **Execute review framework**:
   - Step 1: Document Facts (trade details, original thesis)
   - Step 2: Execution Analysis
     - Entry timing (early / on-time / late)
     - Exit timing and reason
     - Slippage analysis
     - Entry/Exit grades (A–F)
   - Step 3: Thesis Accuracy
     - Direction: correct?
     - Magnitude: within 50%?
     - Timing: correct?
     - Catalyst: played out?
   - Step 4: What Worked / What Didn't
   - Step 5: Bias Check Retrospective (score each 1–5)
     - Recency, Confirmation, Overconfidence, Loss Aversion, Anchoring
   - Step 6: Grade the Trade (overall A–F)
   - Step 7: Extract Lessons (actionable improvements)
4. **Generate output** using `trading/skills/post-trade-review/template.yaml`
5. **Save** to `trading/knowledge/reviews/{TICKER}_{YYYYMMDDTHHMM}_review.yaml`

## Grading Components

| Component | Grade |
|-----------|-------|
| Analysis Quality | A–F |
| Entry Execution | A–F |
| Exit Execution | A–F |
| Risk Management | A–F |
| Emotional Discipline | A–F |
| **Overall** | **A–F** |

## Lesson Extraction

For each significant lesson:
- **Lesson**: Specific insight
- **Action**: What to do differently
- **Applies to**: All trades / Earnings / Technical / This ticker

New patterns → save to `trading/knowledge/learnings/patterns/`
New rules → save to `trading/knowledge/learnings/rules/`

## Chaining

- Automatically triggered by **trade-journal** exit
- Updates **ticker-profile** with trade history and lessons
- Adds patterns/rules to `trading/knowledge/learnings/`
- Informs future **earnings-analysis** and **stock-analysis**

## Output

Save to `trading/knowledge/reviews/` using `{TICKER}_{YYYYMMDDTHHMM}_review.yaml`.
