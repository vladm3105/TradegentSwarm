---
title: Watchlist
tags:
  - trading-skill
  - trade-management
  - monitoring
  - ai-agent-primary
custom_fields:
  skill_category: trade-management
  priority: primary
  development_status: active
  upstream_artifacts:
    - earnings-analysis
    - stock-analysis
    - scan
  downstream_artifacts:
    - trade-journal
  triggers:
    - "watchlist"
    - "add to watchlist"
    - "watch this"
    - "monitor"
    - "waiting for trigger"
    - "review watchlist"
  auto_invoke: true
---

# Watchlist Skill

Use this skill to track potential trades waiting for trigger conditions. Auto-invokes when analysis recommends WATCH or user wants to monitor a setup.

## When to Use

- Analysis score 5.5-6.4 (WATCH recommendation)
- Good setup but waiting for specific trigger
- Scanner candidate needs confirmation
- Quality stock at wrong price
- User says "add to watchlist" or "watch this"

## Workflow

1. **Read skill definition**: Load `trading/skills/watchlist/SKILL.md`
2. **Determine action**:
   - **add**: Create new watchlist entry
   - **review**: Check all entries against current prices
   - **remove**: Remove triggered/invalidated/expired entries
3. **For adding**, specify:
   - Entry trigger (specific, measurable)
   - Invalidation criteria
   - Expiration date (max 30 days)
   - Priority (high/medium/low)
   - Source (which analysis or scanner)
4. **For review**, check each entry:
   - Did trigger fire? → Execute analysis or trade
   - Did invalidation occur? → Remove
   - News affecting thesis? → Update or remove
   - Stale (>30 days)? → Remove
5. **Generate output** using `trading/skills/watchlist/template.yaml`
6. **Save** to `trading/knowledge/watchlist/{TICKER}_{YYYYMMDDTHHMM}.yaml`

## Entry Trigger Types

```
PRICE TRIGGERS:
- Breakout above $X
- Pullback to $X
- Break below $X (shorts)

CONDITION TRIGGERS:
- Earnings report
- FDA decision
- Pattern completion
- Volume confirmation

COMBINED TRIGGERS:
- Price above $X WITH volume > Y
- Break resistance AND sector confirming
```

## Daily Review Routine

```
EVERY TRADING DAY:
□ Check each entry vs current price
□ Triggers fired? → Execute
□ Invalidations? → Remove
□ News impact? → Update/remove

WEEKLY:
□ Remove stale entries (>30 days)
□ Reprioritize by likelihood
□ Check for new scanner candidates
```

## Chaining

- Receives WATCH recommendations from **earnings-analysis** and **stock-analysis**
- Receives candidates from **scan** skill
- Triggers fire → invoke **trade-journal** for entry
- May trigger new **stock-analysis** when conditions met

## Arguments

- `$ARGUMENTS`: Ticker symbol and action (add/review/remove), or "review all"

## Execution

Manage watchlist for $ARGUMENTS. Read the full skill definition from `trading/skills/watchlist/SKILL.md`.
