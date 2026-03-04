# Watchlist Management

Watchlist entries track potential trades waiting for trigger conditions.

## Watchlist Lifecycle

```
ENTRY SOURCES           ACTIVE              RESOLUTION
────────────────────────────────────────────────────────
Scanner (5.5-7.4)  ─┐
Analysis (WATCH)   ─┼─▶ status: active ─┬─▶ triggered → trade-journal
User request       ─┘   Daily review    ├─▶ invalidated → archive
                                        └─▶ expired → archive
```

## Adding to Watchlist

| Source | Condition |
|--------|-----------|
| Scanner | Score 5.5-7.4 (not high enough for immediate analysis) |
| Analysis | WATCH recommendation (good setup, wrong timing/price) |
| User | "add TICKER to watchlist" |

**Required fields:**
- `entry_trigger`: Specific condition (price, event, combined)
- `invalidation`: When to remove without triggering
- `expires`: Max 30 days
- `priority`: high / medium / low

## Removing from Watchlist

| Reason | Status | Action |
|--------|--------|--------|
| Trigger fired | `triggered` | Create trade journal, archive |
| Thesis broken | `invalidated` | Archive with lesson |
| Time exceeded | `expired` | Archive |
| User removes | N/A | Delete or archive |

## Expiration Rules

**Max 30 days** - if not traded, marked as expired.

| Setup Type | Recommended Expiration |
|------------|------------------------|
| Earnings play | Earnings date |
| Breakout watch | 7-14 days |
| Pullback entry | 5-10 days |
| General thesis | 30 days (max) |

Two mechanisms (whichever comes first):
- **Absolute**: `_meta.expires: "2025-03-22"`
- **Relative**: `invalidation.time_limit_days: 10`

## Daily Review

```yaml
FOR EACH active entry:
  1. Check expiration → expired?
  2. Check invalidation → invalidated?
  3. Check trigger → triggered?
  4. Check news → update or invalidate?
```

## Trigger → Trade Journal Chain

```yaml
IF entry_trigger MET:
  status: "triggered"
  → Invoke trade-journal skill
  → Archive watchlist entry
```

## Stock Table Management

Stocks in `nexus.stocks` table with state machine: `analysis` → `paper` → `live`

```bash
python tradegent.py stock list
python tradegent.py stock add PLTR --priority 6 --tags ai defense
python tradegent.py stock enable NVDA
python tradegent.py stock set-state NVDA paper
```

| Column | Purpose |
|--------|---------|
| `ticker` | Stock symbol (primary key) |
| `state` | `analysis` / `paper` / `live` |
| `is_enabled` | Include in automated runs |
| `priority` | Processing order (10=highest) |
