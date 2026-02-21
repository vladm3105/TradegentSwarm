---
mode: agent
description: Analyze stocks 3-10 days before earnings using the 8-phase framework
---

# Earnings Analysis

Analyze **${input:ticker}** for upcoming earnings using the 8-phase earnings analysis framework.

## Context

Load the full skill definition and output template:
- #file:../../tradegent_knowledge/skills/earnings-analysis/SKILL.md
- #file:../../tradegent_knowledge/skills/earnings-analysis/template.yaml

Check for existing ticker knowledge:
- #file:../../tradegent_knowledge/knowledge/analysis/ticker-profiles/

## When to Use

- Pre-earnings trade evaluation (3-10 days before announcement)
- Scanner identifies high-potential earnings setup
- Upcoming earnings for a stock you're tracking

## Workflow

1. **Read skill definition** from `tradegent_knowledge/skills/earnings-analysis/SKILL.md`
2. **Gather inputs**:
   - Ticker symbol: `${input:ticker}`
   - Earnings date and time (BMO/AMC)
   - Current stock price
   - Consensus EPS and revenue estimates
3. **Execute 8 phases**:
   - Phase 1: Preparation (historical earnings data, 8 quarters)
   - Phase 2: Customer Demand Signals (**50% weight** — critical)
   - Phase 3: Technical Setup
   - Phase 4: Sentiment Analysis
   - Phase 5: Probability Assessment
   - Phase 6: Bias Check
   - Phase 7: Decision Framework
   - Phase 8: Execution Plan
4. **Generate output** using `tradegent_knowledge/skills/earnings-analysis/template.yaml`
5. **Save** to `tradegent_knowledge/knowledge/analysis/earnings/{TICKER}_{YYYYMMDDTHHMM}.yaml`

## Chaining

After completion:
- If recommendation is **WATCH** → run the **watchlist** prompt
- If recommendation is **BULLISH/BEARISH** with trade → prepare for **trade-journal** prompt
- Update **ticker-profile** if significant new patterns observed

## Output

Save the completed analysis to `tradegent_knowledge/knowledge/analysis/earnings/` using the naming convention `{TICKER}_{YYYYMMDDTHHMM}.yaml`.
