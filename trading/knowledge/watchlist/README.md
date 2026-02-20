# Watchlist

## Purpose

Track potential trades waiting for entry triggers. Watchlist entries have specific trigger conditions, invalidation criteria, and expiration dates.

## File Naming

```
{TICKER}_{YYYYMMDDTHHMM}.yaml
```

## Lifecycle

```
ENTRY SOURCES                    ACTIVE                     RESOLUTION
─────────────────────────────────────────────────────────────────────────
Scanner (score 5.5-7.4)  ───┐
Analysis (WATCH)         ───┼──▶  status: "active"  ───┬──▶ triggered
User request             ───┘     Daily monitoring     ├──▶ invalidated
                                                       ├──▶ expired
                                                       └──▶ removed (manual)
```

## Adding to Watchlist

### Entry Sources

| Source | Condition | Score Range |
|--------|-----------|-------------|
| Scanner | Passes filters, not high enough for analysis | 5.5-7.4 |
| Analysis | WATCH recommendation (good setup, wrong timing) | 5.5-6.4 |
| User | Manual request ("add to watchlist") | N/A |

### Required Fields

| Field | Description |
|-------|-------------|
| `entry_trigger` | Specific, measurable condition to enter |
| `invalidation` | Condition that breaks the thesis |
| `expires` | Max 30 days from creation |
| `priority` | high / medium / low |
| `source` | Link to analysis or scanner that created it |

### Trigger Types

```
PRICE TRIGGERS:
- Break above $X (breakout)
- Pullback to $X (entry on dip)
- Break below $X (short entry)

CONDITION TRIGGERS:
- Earnings report released
- FDA decision announced
- Pattern completion (cup & handle, etc.)

COMBINED TRIGGERS:
- Price above $X WITH volume > Y
- Break resistance AND sector confirming
```

### Add Process

```
1. Check for existing entry (rag_search)
2. Get current price (mcp__ib-mcp__get_stock_price)
3. Get historical data for levels (mcp__ib-mcp__get_historical_data)
4. Define entry trigger
5. Define invalidation criteria
6. Set expiration (max 30 days)
7. Create YAML file
8. Index (graph_extract, rag_embed)
9. Push to remote (mcp__github-vl__push_files)
```

## Removing from Watchlist

### Removal Reasons

| Reason | Status | Action |
|--------|--------|--------|
| Trigger fired | `triggered` | Create trade journal, archive |
| Thesis broken | `invalidated` | Archive with lesson learned |
| Time exceeded | `expired` | Archive |
| User removes | N/A | Delete or archive |

### Daily Review Process

For each active entry:

1. Get current price
2. Check if trigger condition met → `triggered`
3. Check if invalidation hit → `invalidated`
4. Check if expired → `expired`
5. Check news impact → update or invalidate

### Remove Process

```
1. Update status in YAML
2. Fill resolution section (date, outcome, final_action)
3. Archive to watchlist/archive/ (or delete)
4. Push changes to remote
5. If triggered: invoke trade-journal skill
```

## Status Values

| Status | Meaning | Next Action |
|--------|---------|-------------|
| `active` | Monitoring for trigger | Continue daily review |
| `triggered` | Entry condition met | Create trade journal, archive |
| `invalidated` | Thesis broken | Archive, log lesson |
| `expired` | Time limit exceeded | Archive |

## Expiration System

If a watchlist entry remains `active` without being triggered or invalidated, it automatically expires. This prevents stale entries from cluttering the watchlist.

### Expiration Types

```
EXPIRATION TYPES
────────────────────────────────────────────────────────────────────
1. ABSOLUTE    _meta.expires: "2025-03-22"
               Entry expires on this specific date

2. RELATIVE    invalidation.time_limit_days: 10
               Entry expires N days after creation

3. EVENT       events[].date (when impact: "high")
               Entry expires when catalyst event passes
────────────────────────────────────────────────────────────────────
```

### 30-Day Maximum Rule

**If a stock is not traded within 30 days, it is marked as expired.**

| Reason | Explanation |
|--------|-------------|
| Stale thesis | Market conditions change; old analysis loses relevance |
| Opportunity cost | Watching too many stocks dilutes focus |
| Forced review | Makes you re-evaluate if setup still valid |
| Clean watchlist | Prevents accumulation of forgotten entries |

### Recommended Expirations by Setup Type

| Setup Type | Expiration | Reason |
|------------|------------|--------|
| Earnings play | Earnings date (or day before) | Setup invalid after event |
| FDA catalyst | Decision date | Binary event |
| Breakout watch | 7-14 days | Momentum fades |
| Pullback entry | 5-10 days | If not pulling back, thesis wrong |
| Support bounce | 3-5 days | Quick reaction expected |
| Sector rotation | 14-21 days | Slower development |
| General thesis | 30 days (max) | Default ceiling |

### Expiration Check Logic

When both `_meta.expires` and `time_limit_days` are set, **whichever comes first** triggers expiration:

```
absolute_expiry = _meta.expires                    # e.g., 2025-03-22
relative_expiry = _meta.created + time_limit_days  # e.g., 2025-03-02

effective_expiry = MIN(absolute_expiry, relative_expiry)

IF today > effective_expiry:
    status = "expired"
```

### Daily Review Expiration Check

```
FOR EACH active entry:

    # Check 1: Absolute expiration
    IF today > _meta.expires:
        status = "expired"
        reason = "Expiration date passed"

    # Check 2: Relative expiration
    days_elapsed = today - _meta.created
    IF days_elapsed > invalidation.time_limit_days:
        status = "expired"
        reason = "Time limit exceeded"

    # Check 3: Event-based expiration
    FOR EACH event WHERE impact == "high":
        IF today > event.date:
            status = "expired"
            reason = "Catalyst event passed"
```

### Example: Expiration Timeline

```
DAY 1                              DAY 30                    DAY 31
──────────────────────────────────────────────────────────────────────
│                                    │                         │
▼                                    ▼                         ▼
┌──────────┐                    ┌──────────┐             ┌──────────┐
│  active  │ ─── 30 days ────▶ │  active  │ ── next ──▶ │ expired  │
│          │   (no trigger)    │          │    day      │          │
└──────────┘                    └──────────┘             └──────────┘
```

### Re-Adding After Expiration

If the setup is still valid after expiration:

1. **Let it expire** → Create new entry with fresh analysis
2. **Update before expiration** → Extend `_meta.expires` (if thesis still valid)

```yaml
# Old entry expired
NVDA_20250220T0900.yaml  # status: "expired"

# Create fresh entry with new analysis
NVDA_20250323T0900.yaml  # status: "active", new 30-day window
```

## Integration

### Inputs (Fed By)

- `analysis/` — WATCH recommendations from earnings/stock analysis
- `scanners/` — Candidates scoring 5.5-7.4

### Outputs (Feeds)

- `trades/` — When triggers fire, creates trade journal entry

### Skill

- `.claude/skills/watchlist.md` — Skill definition
- `skills/watchlist/SKILL.md` — Detailed workflow
- `skills/watchlist/template.yaml` — Output template

## MCP Tools Used

| Tool | Purpose |
|------|---------|
| `rag_search` | Check existing entries |
| `graph_context` | Ticker relationships |
| `mcp__ib-mcp__get_stock_price` | Current price |
| `mcp__ib-mcp__get_historical_data` | Support/resistance levels |
| `mcp__brave-search__brave_web_search` | News impact check |
| `graph_extract` | Index entry |
| `rag_embed` | Embed for search |
| `mcp__github-vl__push_files` | Push changes |

## Example Entry

```yaml
_meta:
  id: "NVDA_20250220T0900"
  type: watchlist
  status: "active"
  expires: "2025-03-22"

ticker: "NVDA"
priority: "high"
current_price: 142.50

source:
  type: "scanner"
  file: "scanners/daily/premarket-gap_20250220.yaml"
  original_score: 7.2

thesis: "Pre-earnings momentum, waiting for pullback to VWAP"

entry_trigger:
  type: "combined"
  description: "Pullback to $140 with volume confirmation"
  price_trigger:
    condition: "at"
    price: 140.00
  additional_conditions:
    - "Volume > 1.5x average"

invalidation:
  type: "price"
  description: "Close below 20-day MA"
  price_level: 135.00

key_levels:
  support: [140.00, 135.00]
  resistance: [150.00, 155.00]
  entry_zone: 140.00
```

## Best Practices

1. **Specific triggers** — "Break above $150" not "when it looks good"
2. **Clear invalidation** — Know when to give up
3. **Time limits** — Max 30 days, shorter for event-driven
4. **Daily review** — Check every trading day
5. **Archive don't delete** — Learn from invalidations
