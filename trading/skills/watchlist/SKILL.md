# Watchlist Skill v2.1

## Purpose
Track potential trades that don't yet meet entry criteria. Monitor for trigger conditions with documented reasoning and conviction levels.

## When to Use
- Analysis recommendation is WATCH
- Good setup but waiting for trigger
- Scanner candidate needs more time
- Tracking for future opportunity

## Required Inputs
- Ticker symbol
- Entry trigger condition
- Invalidation condition
- Source (analysis or scanner)

## Output
- File: `{TICKER}_{YYYYMMDDTHHMM}.yaml`
- Location: `knowledge/watchlist/`

---

## Watchlist Framework (7 Steps)

```
Step 1: Qualify Entry        → Verify source and analysis quality
Step 2: Document Thesis      → Why this is on watchlist
Step 3: Set Conviction Level → How confident are you?
Step 4: Define Triggers      → When to enter
Step 5: Set Invalidation     → When to remove
Step 6: Daily Review         → Monitor and update
Step 7: Resolution           → Triggered, invalidated, or expired
```

---

## Step 1: Qualify Entry

```
WHEN TO ADD:
□ Analysis score 5.5-6.4 (WATCH recommendation)
□ Good setup waiting for specific trigger
□ Scanner candidate needs confirmation
□ Quality stock at wrong price

CHECK ANALYSIS QUALITY (v2.1):
□ Do Nothing gate result from source analysis
□ Bear case was considered in analysis
□ Bias check was completed
□ R:R ratio is acceptable (>2:1)
□ EV estimate from analysis

SOURCE REQUIREMENTS:
□ Link to source analysis file
□ Original score from analysis
□ Date of analysis (must be <7 days old)

PRIORITY LEVELS:
- High: Likely to trigger soon, strong setup, high conviction
- Medium: Good setup, needs more time
- Low: Interesting but speculative
```

---

## Step 2: Document Thesis (NEW v2.1)

```
THESIS SUMMARY:
Brief statement of why this is on watchlist.

THESIS REASONING:
Write 2-3 paragraphs explaining:
- What is the opportunity?
- What is the key catalyst?
- What makes this setup attractive?

KEY CATALYST:
Specific event or condition that matters most.

CATALYST TIMING:
- Immediate: Within days
- Near-term: 1-2 weeks
- Longer-term: 2-4 weeks

WHY NOT ENTERING NOW:
Explicitly state why you're waiting:
- Price too high? Need pullback to $___
- Waiting for confirmation? Need to see ___
- Timing issue? Event on ___
- Conviction not high enough? Need ___
```

---

## Step 3: Set Conviction Level (NEW v2.1)

```
CONVICTION ASSESSMENT:

LEVEL: High / Medium / Low
SCORE: 1-10

RATIONALE:
Why this conviction level?

CONDITIONS TO INCREASE CONVICTION:
| Condition | Impact |
|-----------|--------|
| | Would increase to ___ |
| | Would increase to ___ |

CONDITIONS TO DECREASE CONVICTION:
| Condition | Impact |
|-----------|--------|
| | Would decrease to ___ |
| | Would decrease to ___ |

This helps decide when to upgrade to trade or remove.
```

---

## Step 4: Define Entry Triggers

```
TRIGGER TYPE: Price / Condition / Combined

PRIMARY TRIGGER:
Specific, measurable condition.
Example: "Breaks above $150 on volume >2x average"

PRICE TRIGGERS:
□ Breakout above $X
□ Pullback to $X
□ Break below $X (for shorts)

CONDITION TRIGGERS:
□ Earnings report (beat/miss)
□ FDA decision
□ Technical pattern completion
□ Volume confirmation
□ Sector confirmation

COMBINED TRIGGERS:
□ Price above $X WITH volume > Y
□ Break above resistance AND sector confirming

ALTERNATIVE ENTRIES (v2.1):
| Alternative | Trigger | Price | Rationale |
|-------------|---------|-------|-----------|
| 1 | | | |
| 2 | | | |

KEY LEVELS:
- Entry zone: $___
- Stop zone: $___
- Support: $___
- Resistance: $___
```

---

## Step 5: Set Invalidation

```
INVALIDATION TYPE: Price / Condition / Time

PRICE INVALIDATION:
□ Breaks below $X (for longs)
□ Breaks above $X (for shorts)
□ Closes below support

CONDITION INVALIDATION:
□ Earnings miss (if bullish thesis)
□ Thesis broken by news
□ Sector turns negative
□ Key metric disappoints

TIME INVALIDATION:
□ No trigger in X days (max 30)
□ Setup becomes stale

EXPIRATION DATE: {YYYY-MM-DD}
- Max 30 days from creation
- Shorter for event-driven (earnings date, FDA decision)

THESIS BROKEN IF:
List specific conditions that would break thesis.
```

---

## Step 6: Daily Review

```
EVERY TRADING DAY:

FOR EACH WATCHLIST ENTRY:
□ Check expiration first (cheapest check)
  → If expired → Status = "expired", archive

□ Check invalidation
  → If invalidated → Status = "invalidated", archive, document lesson

□ Check trigger
  → If triggered → Status = "triggered", execute analysis, create trade journal

□ Check news
  → Any news affecting thesis? Update or invalidate

□ Check conviction
  → Has conviction changed? Update level

MONITORING LOG:
| Date | Price | Note | Action | Conviction Change |
|------|-------|------|--------|-------------------|
| | | | none/updated/triggered/removed | none/up/down |

WEEKLY:
□ Remove stale entries (>30 days)
□ Reprioritize based on likelihood
□ Check for new candidates from scanners
```

---

## Step 7: Resolution

```
WHEN WATCHLIST ENTRY RESOLVES:

IF TRIGGERED:
□ Update status = "triggered"
□ Record trigger date and price
□ Create trade journal entry
□ Link trade journal to watchlist entry
□ Archive watchlist entry

IF INVALIDATED:
□ Update status = "invalidated"
□ Record invalidation reason
□ Document lesson learned
□ Archive watchlist entry

IF EXPIRED:
□ Update status = "expired"
□ Record expiration date
□ Document why it didn't trigger
□ Archive watchlist entry

RESOLUTION RECORD:
- Date: {YYYY-MM-DD}
- Outcome: triggered/invalidated/expired
- Final action: ___
- Lesson learned: ___
```

---

## Trigger → Trade Journal Chain

```
WHEN TRIGGER FIRES:

1. Update watchlist entry:
   status: "triggered"
   resolution.date: [today]
   resolution.outcome: "triggered"

2. Create trade journal entry:
   Link to watchlist entry
   Copy thesis and key levels

3. Archive watchlist entry

4. Execute trade per analysis plan
```

---

## Template

See `template.yaml` for the output format (v2.1).

---

## Quality Checklist

When Adding:
```
SOURCE QUALITY:
□ Source analysis linked
□ Analysis is recent (<7 days)
□ Analysis passed quality checks

THESIS QUALITY:
□ Thesis reasoning documented
□ Key catalyst identified
□ "Why not now" explained

CONVICTION:
□ Conviction level set
□ Conditions to increase/decrease documented

TRIGGERS:
□ Entry trigger specific and measurable
□ Alternative entries considered
□ Key levels defined

RISK:
□ Invalidation is clear
□ Expiration date set (max 30 days)
□ Thesis broken conditions listed
```

Daily Review:
```
□ All entries checked
□ Expirations handled first
□ Triggered entries actioned
□ Invalid entries removed
□ Notes updated with date
□ Conviction changes logged
```

---

*Skill Version: 2.1*
*Updated: 2026-02-21*
