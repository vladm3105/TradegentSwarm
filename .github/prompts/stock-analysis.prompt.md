---
mode: agent
description: Analyze non-earnings trading opportunities using the 7-phase framework
---

# Stock Analysis

Analyze **${input:ticker}** for a non-earnings trading opportunity using the 7-phase stock analysis framework.

## Context

Load the full skill definition and output template:
- #file:../../trading/skills/stock-analysis/SKILL.md
- #file:../../trading/skills/stock-analysis/template.yaml

Check for existing ticker knowledge:
- #file:../../trading/knowledge/analysis/ticker-profiles/

## When to Use

- Technical breakout/breakdown setup identified
- Value opportunity analysis needed
- Momentum/trend following evaluation
- Post-earnings drift analysis
- Catalyst-driven opportunity (non-earnings)

## Workflow

1. **Read skill definition** from `trading/skills/stock-analysis/SKILL.md`
2. **Gather inputs**:
   - Ticker symbol: `${input:ticker}`
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
4. **Calculate setup score** using weighted criteria:

   | Criterion | Weight |
   |-----------|--------|
   | Catalyst Quality | 0.25 |
   | Market Environment | 0.15 |
   | Technical Setup | 0.25 |
   | Risk/Reward | 0.25 |
   | Sentiment Edge | 0.10 |

5. **Interpret score**:
   - ≥ 7.5: STRONG_BUY or STRONG_SELL
   - 6.5–7.4: BUY or SELL
   - 5.5–6.4: WATCH
   - < 5.5: AVOID
6. **Generate output** using `trading/skills/stock-analysis/template.yaml`
7. **Save** to `trading/knowledge/analysis/stock/{TICKER}_{YYYYMMDDTHHMM}.yaml`

## Chaining

After completion:
- If recommendation is **WATCH** → run the **watchlist** prompt
- If recommendation is **BUY/SELL** → prepare for **trade-journal** prompt
- Update **ticker-profile** with new levels and observations

## Output

Save the completed analysis to `trading/knowledge/analysis/stock/` using the naming convention `{TICKER}_{YYYYMMDDTHHMM}.yaml`.
