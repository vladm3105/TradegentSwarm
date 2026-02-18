---
title: Stock Analysis
tags:
  - trading-skill
  - analysis
  - technical
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
    - "stock analysis"
    - "analyze stock"
    - "technical analysis"
    - "value analysis"
    - "momentum trade"
  auto_invoke: true
---

# Stock Analysis Skill

Use this skill for non-earnings trading opportunities: technical breakouts, value plays, momentum trades, post-earnings drift. Auto-invokes when user requests stock analysis without earnings context.

## When to Use

- Technical breakout/breakdown setup identified
- Value opportunity analysis needed
- Momentum/trend following evaluation
- Post-earnings drift analysis
- Catalyst-driven opportunity (non-earnings)

## Workflow

1. **Read skill definition**: Load `trading/skills/stock-analysis/SKILL.md`
2. **Gather inputs**:
   - Ticker symbol
   - Catalyst or reason for analysis
   - Current stock price
3. **Execute 7 phases**:
   - Phase 1: Catalyst Identification (no catalyst = no trade)
   - Phase 2: Market Environment (regime, sector, volatility)
   - Phase 3: Technical Analysis (trend, patterns, levels)
   - Phase 4: Fundamental Check (valuation, growth, red flags)
   - Phase 5: Sentiment & Positioning
   - Phase 6: Scenario Analysis (bull/base/bear with probabilities)
   - Phase 7: Risk Management (position sizing, R:R)
4. **Calculate setup score** using weighted criteria
5. **Generate output** using `trading/skills/stock-analysis/template.yaml`
6. **Save** to `trading/knowledge/analysis/stock/{TICKER}_{YYYYMMDDTHHMM}.yaml`

## Scoring

```
Catalyst Quality:     ___/10 × 0.25
Market Environment:   ___/10 × 0.15
Technical Setup:      ___/10 × 0.25
Risk/Reward:          ___/10 × 0.25
Sentiment Edge:       ___/10 × 0.10
─────────────────────────────────
TOTAL SCORE:                ___/10
```

- Score ≥ 7.5: STRONG_BUY or STRONG_SELL
- Score 6.5-7.4: BUY or SELL
- Score 5.5-6.4: WATCH
- Score < 5.5: AVOID

## Chaining

After completion:
- If recommendation is WATCH → invoke **watchlist** skill
- If recommendation is BUY/SELL → prepare for **trade-journal** skill
- Update **ticker-profile** with new levels and observations

## Arguments

- `$ARGUMENTS`: Ticker symbol and optional catalyst description

## Execution

Analyze $ARGUMENTS using the 7-phase stock analysis framework. Read the full skill definition from `trading/skills/stock-analysis/SKILL.md`.
