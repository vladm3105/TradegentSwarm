# File Conventions

## File Naming (ISO 8601)

All trading documents follow ISO 8601 basic format:

```
{TICKER}_{YYYYMMDDTHHMM}.yaml
```

**Examples:**
```
NVDA_20260223T1100.yaml    # Feb 23, 2026 at 11:00
trades/2025/01/NVDA_20250115T1000.yaml
```

## Directory Structure

| Content Type | Directory Pattern |
|--------------|-------------------|
| Stock Analysis | `analysis/stock/` |
| Earnings Analysis | `analysis/earnings/` |
| Research Analysis | `analysis/research/` |
| Ticker Profile | `analysis/ticker-profiles/` |
| Trade Journal | `trades/{YYYY}/{MM}/` |
| Watchlist | `watchlist/` |
| Post-Trade Review | `reviews/{YYYY}/{MM}/` |
| Post-Earnings Review | `reviews/post-earnings/` |
| Report Validation | `reviews/validation/` |
| Learnings | `learnings/{category}/` |
| Strategies | `strategies/` |
| Scanner Configs | `scanners/{type}/` |

## Skill to Knowledge Mapping

| Skill | Output Location |
|-------|------------------|
| earnings-analysis | `knowledge/analysis/earnings/` |
| stock-analysis | `knowledge/analysis/stock/` |
| research-analysis | `knowledge/analysis/research/` |
| ticker-profile | `knowledge/analysis/ticker-profiles/` |
| trade-journal | `knowledge/trades/{YYYY}/{MM}/` |
| watchlist | `knowledge/watchlist/` |
| post-trade-review | `knowledge/reviews/{YYYY}/{MM}/` |
| post-earnings-review | `knowledge/reviews/post-earnings/` |
| report-validation | `knowledge/reviews/validation/` |

## ISO 8601 Components

- `YYYY` - 4-digit year (2026)
- `MM` - 2-digit month (01-12)
- `DD` - 2-digit day (01-31)
- `T` - Time separator (literal)
- `HHMM` - Hours (00-23) and minutes (00-59)
