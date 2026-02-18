# Watchlist

## Purpose
Track potential trades waiting for entry triggers.

## File Naming
```
{TICKER}_{YYYYMMDDHHMM}.yaml
```

## How to Use
1. Add entries from analysis (WATCH recommendations) or scanners
2. Review daily for triggered/invalidated entries
3. Remove expired entries (>30 days)

## Integration
- Fed by: `analysis/` (WATCH recommendations), `scanners/`
- Feeds: `trades/` (when triggers fire)
- Skill: `trading-skills/watchlist/`

## Status Values
- `active`: Monitoring for trigger
- `triggered`: Entry executed → trade journal created
- `invalidated`: Conditions no longer valid
- `expired`: Time limit exceeded
