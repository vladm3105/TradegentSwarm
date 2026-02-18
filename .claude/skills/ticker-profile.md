---
title: Ticker Profile
tags:
  - trading-skill
  - knowledge-base
  - ticker
  - ai-agent-primary
custom_fields:
  skill_category: knowledge-management
  priority: primary
  development_status: active
  upstream_artifacts:
    - post-trade-review
  downstream_artifacts:
    - earnings-analysis
    - stock-analysis
  triggers:
    - "ticker profile"
    - "stock profile"
    - "what do I know about"
    - "historical data for"
    - "update profile"
  auto_invoke: true
---

# Ticker Profile Skill

Use this skill to maintain persistent knowledge about frequently traded stocks. Auto-invokes when user asks about historical patterns, ticker knowledge, or before first trade in a new ticker.

## When to Use

- First trade in a new ticker (create profile)
- After earnings report (update profile)
- Building knowledge on focus stocks
- User asks "what do I know about TICKER?"
- Before analysis to load context

## Workflow

1. **Read skill definition**: Load `trading/skills/ticker-profile/SKILL.md`
2. **Check existing profile** in `trading/knowledge/analysis/ticker-profiles/`
3. **Gather or update**:
   - Company Basics (sector, market cap, business model)
   - Earnings Patterns (8 quarters: beats, reactions, guidance)
   - Technical Levels (ATH, 52-week range, support/resistance, MAs)
   - Your Edge (patterns you've observed, reliable signals)
   - Trading History (your trades, win rate, lessons)
   - Key Dates (earnings schedule, dividends, conferences)
4. **Generate output** using `trading/skills/ticker-profile/template.yaml`
5. **Save** to `trading/knowledge/analysis/ticker-profiles/{TICKER}_{YYYYMMDDTHHMM}.yaml`

## Profile Maintenance

Update after:
- Each earnings report
- Each trade you make (via post-trade-review)
- Significant price moves (>10%)
- Major news events

Quarterly refresh:
- All technical levels
- Earnings history
- Edge section review

## Chaining

- Called by **earnings-analysis** and **stock-analysis** for context
- Updated by **post-trade-review** with new lessons
- Informs **watchlist** entry quality assessment

## Arguments

- `$ARGUMENTS`: Ticker symbol

## Execution

Create or update the ticker profile for $ARGUMENTS. Read the full skill definition from `trading/skills/ticker-profile/SKILL.md`. Check for existing profile first.
