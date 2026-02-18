# Post-Trade Reviews

## Purpose
Analyze completed trades to extract lessons and improve performance.

## File Naming
```
{TICKER}_{YYYYMMDDHHMM}_review.yaml   # Individual trade reviews
weekly_{YYYYMMDD}.md                   # Weekly summaries
```

## How to Use
1. Create review within 24-48 hours of closing a trade
2. Follow the post-trade-review skill framework
3. Extract lessons and update knowledge base
4. Complete weekly reviews every weekend

## Integration
- Fed by: `trades/` (closed trades)
- Feeds: `learnings/`, ticker profiles, strategy updates
- Skill: `skills/post-trade-review/`
- Workflow: `skills/workflows/weekly-review.md`

## Review Types
- **Trade review**: Individual trade analysis
- **Weekly review**: Week's performance summary
- **Monthly review**: Monthly performance and strategy assessment
