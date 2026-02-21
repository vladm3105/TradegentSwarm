---
mode: agent
description: Create or update a persistent ticker profile with trading knowledge and patterns
---

# Ticker Profile

Create or update the ticker profile for **${input:ticker}**.

## Context

Load the full skill definition and output template:
- #file:../../tradegent_knowledge/skills/ticker-profile/SKILL.md
- #file:../../tradegent_knowledge/skills/ticker-profile/template.yaml

Check for existing profile:
- #file:../../tradegent_knowledge/knowledge/analysis/ticker-profiles/

## When to Use

- First trade in a new ticker (create profile)
- After earnings report (update profile)
- Building knowledge on focus stocks
- Before analysis to load context
- User asks "what do I know about TICKER?"

## Workflow

1. **Read skill definition** from `tradegent_knowledge/skills/ticker-profile/SKILL.md`
2. **Check existing profile** in `tradegent_knowledge/knowledge/analysis/ticker-profiles/`
3. **Gather or update**:
   - Company Basics (sector, market cap, business model)
   - Earnings Patterns (8 quarters: beats, reactions, guidance)
   - Technical Levels (ATH, 52-week range, support/resistance, MAs)
   - Your Edge (patterns you've observed, reliable signals)
   - Trading History (your trades, win rate, lessons)
   - Key Dates (earnings schedule, dividends, conferences)
4. **Generate output** using `tradegent_knowledge/skills/ticker-profile/template.yaml`
5. **Save** to `tradegent_knowledge/knowledge/analysis/ticker-profiles/{TICKER}_{YYYYMMDDTHHMM}.yaml`

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

## Output

Save to `tradegent_knowledge/knowledge/analysis/ticker-profiles/` using the naming convention `{TICKER}_{YYYYMMDDTHHMM}.yaml`.
