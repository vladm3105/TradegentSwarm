---
mode: agent
description: Track potential trades waiting for trigger conditions on the watchlist
---

# Watchlist

Manage the watchlist for **${input:ticker}** — action: **${input:action}** (add / review / remove).

Use "review all" to check all watchlist entries against current conditions.

## Context

Load the full skill definition and output template:
- #file:../../trading/skills/watchlist/SKILL.md
- #file:../../trading/skills/watchlist/template.yaml

Check current watchlist:
- #file:../../trading/knowledge/watchlist/

## When to Use

- Analysis score 5.5–6.4 (WATCH recommendation)
- Good setup but waiting for specific trigger
- Scanner candidate needs confirmation
- Quality stock at wrong price

## Workflow

1. **Read skill definition** from `trading/skills/watchlist/SKILL.md`
2. **Determine action**:
   - **add**: Create new watchlist entry
   - **review**: Check all entries against current prices
   - **remove**: Remove triggered/invalidated/expired entries
3. **For adding**, specify:
   - Entry trigger (specific, measurable)
   - Invalidation criteria
   - Expiration date (max 30 days)
   - Priority (high / medium / low)
   - Source (which analysis or scanner)
4. **For review**, check each entry:
   - Did trigger fire? → Execute analysis or trade
   - Did invalidation occur? → Remove
   - News affecting thesis? → Update or remove
   - Stale (>30 days)? → Remove
5. **Generate output** using `trading/skills/watchlist/template.yaml`
6. **Save** to `trading/knowledge/watchlist/{TICKER}_{YYYYMMDDTHHMM}.yaml`

## Entry Trigger Types

**Price Triggers**: Breakout above $X, Pullback to $X, Break below $X (shorts)

**Condition Triggers**: Earnings report, FDA decision, Pattern completion, Volume confirmation

**Combined Triggers**: Price above $X WITH volume > Y, Break resistance AND sector confirming

## Daily Review Routine

**Every Trading Day**: Check each entry vs current price, execute fired triggers, remove invalidated

**Weekly**: Remove stale entries (>30 days), reprioritize by likelihood, check for new scanner candidates

## Chaining

- Receives WATCH recommendations from **earnings-analysis** and **stock-analysis**
- Receives candidates from **scan** prompt
- Triggers fire → invoke **trade-journal** for entry
- May trigger new **stock-analysis** when conditions met

## Output

Save to `trading/knowledge/watchlist/` using `{TICKER}_{YYYYMMDDTHHMM}.yaml`.
