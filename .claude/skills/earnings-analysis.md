---
title: Earnings Analysis
tags:
  - trading-skill
  - analysis
  - earnings
  - ai-agent-primary
custom_fields:
  skill_category: analysis
  priority: primary
  development_status: active
  upstream_artifacts:
    - ticker-profile
    - scan
  downstream_artifacts:
    - watchlist
    - trade-journal
  triggers:
    - "earnings analysis"
    - "analyze earnings"
    - "pre-earnings"
    - "before earnings"
  auto_invoke: true
---

# Earnings Analysis Skill

Use this skill when analyzing stocks 3-10 days before earnings announcements. Auto-invokes when user mentions earnings analysis, pre-earnings setup, or requests analysis before an earnings date.

## When to Use

- User asks for earnings analysis on a ticker
- Scanner identifies high-potential earnings setup
- User mentions upcoming earnings for a stock
- Pre-earnings trade evaluation needed

## Workflow

1. **Read skill definition**: Load `trading/skills/earnings-analysis/SKILL.md`
2. **Gather inputs**:
   - Ticker symbol
   - Earnings date and time (BMO/AMC)
   - Current stock price
   - Consensus EPS and revenue estimates
3. **Execute 8 phases**:
   - Phase 1: Preparation (historical earnings data, 8 quarters)
   - Phase 2: Customer Demand Signals (**50% weight** - critical)
   - Phase 3: Technical Setup
   - Phase 4: Sentiment Analysis
   - Phase 5: Probability Assessment
   - Phase 6: Bias Check
   - Phase 7: Decision Framework
   - Phase 8: Execution Plan
4. **Generate output** using `trading/skills/earnings-analysis/template.yaml`
5. **Save** to `trading/knowledge/analysis/earnings/{TICKER}_{YYYYMMDDTHHMM}.yaml`

## Chaining

After completion:
- If recommendation is WATCH → invoke **watchlist** skill
- If recommendation is BULLISH/BEARISH with trade → prepare for **trade-journal** skill
- Update **ticker-profile** if significant new patterns observed

## Arguments

- `$ARGUMENTS`: Ticker symbol (e.g., NVDA, AAPL, MSFT)

## Execution

Analyze $ARGUMENTS for upcoming earnings using the 8-phase framework. Read the full skill definition from `trading/skills/earnings-analysis/SKILL.md` and follow all phases systematically.
