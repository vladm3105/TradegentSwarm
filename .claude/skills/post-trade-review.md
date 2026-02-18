---
title: Post-Trade Review
tags:
  - trading-skill
  - learning
  - review
  - ai-agent-primary
custom_fields:
  skill_category: learning
  priority: primary
  development_status: active
  upstream_artifacts:
    - trade-journal
  downstream_artifacts:
    - ticker-profile
    - learnings
  triggers:
    - "post-trade review"
    - "review trade"
    - "what did I learn"
    - "trade analysis"
    - "closed trade"
  auto_invoke: true
---

# Post-Trade Review Skill

Use this skill to analyze completed trades and extract lessons. Closes the learning loop. Auto-invokes after trade-journal records an exit.

## When to Use

- After every closed trade (win or loss)
- Within 24-48 hours of exit (while memory fresh)
- Automatically triggered by trade-journal exit
- User asks "what did I learn from TICKER trade?"

## Workflow

1. **Read skill definition**: Load `trading/skills/post-trade-review/SKILL.md`
2. **Find closed trade** in `trading/knowledge/trades/`
3. **Execute review framework**:
   - Step 1: Document Facts (trade details, original thesis)
   - Step 2: Execution Analysis
     - Entry timing (early/on-time/late)
     - Exit timing and reason
     - Slippage analysis
     - Entry/Exit grades (A-F)
   - Step 3: Thesis Accuracy
     - Direction: correct?
     - Magnitude: within 50%?
     - Timing: correct?
     - Catalyst: played out?
   - Step 4: What Worked / What Didn't
   - Step 5: Bias Check Retrospective (score each 1-5)
     - Recency, Confirmation, Overconfidence, Loss Aversion, Anchoring
   - Step 6: Grade the Trade (overall A-F)
   - Step 7: Extract Lessons (actionable improvements)
4. **Generate output** using `trading/skills/post-trade-review/template.yaml`
5. **Save** to `trading/knowledge/reviews/{TICKER}_{YYYYMMDDTHHMM}_review.yaml`

## Grading Components

```
Analysis Quality:      A / B / C / D / F
Entry Execution:       A / B / C / D / F
Exit Execution:        A / B / C / D / F
Risk Management:       A / B / C / D / F
Emotional Discipline:  A / B / C / D / F
─────────────────────────────────────────
OVERALL GRADE:         A / B / C / D / F
```

## Lesson Extraction

For each significant lesson:
```
PRIMARY LESSON:
- Lesson: [specific insight]
- Action: [what to do differently]
- Applies to: All trades / Earnings / Technical / This ticker

PATTERN TO ADD:
- Pattern: [what you observed]
- Expected outcome: [probability/direction]
→ Save to learnings/patterns/

RULE TO ADD:
- Rule: [specific rule]
- Reason: [why this rule]
→ Save to learnings/rules/
```

## Chaining

- Automatically triggered by **trade-journal** exit
- Updates **ticker-profile** with trade history and lessons
- Adds patterns/rules to `trading/knowledge/learnings/`
- Informs future **earnings-analysis** and **stock-analysis**

## Arguments

- `$ARGUMENTS`: Ticker symbol of closed trade

## Auto-Commit to Remote

After saving the review file (and any learnings), use the GitHub MCP server to push directly:

```yaml
Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: trading_light_pilot
  branch: main
  files:
    - path: trading/knowledge/reviews/{TICKER}_{YYYYMMDDTHHMM}_review.yaml
      content: [generated review content]
    - path: trading/knowledge/learnings/patterns/{pattern_file}.yaml
      content: [pattern content if applicable]
    - path: trading/knowledge/learnings/rules/{rule_file}.yaml
      content: [rule content if applicable]
  message: "Add post-trade review for {TICKER}"
```

## Execution

Review the closed trade for $ARGUMENTS. Read the full skill definition from `trading/skills/post-trade-review/SKILL.md`. Be honest in grading—learning requires truth. After saving the output file, auto-commit and push to remote.
