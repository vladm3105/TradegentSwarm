# Analysis

## Purpose
All trading analyses organized by skill type. Each subfolder corresponds to a specific analysis skill.

## Folder Structure

```
analysis/
├── earnings/         ← 8-phase earnings analysis (earnings-analysis skill)
├── stock/            ← 7-phase stock analysis (stock-analysis skill)
├── research/         ← Macro, sector, thematic research
└── ticker-profiles/  ← Persistent ticker knowledge
```

## File Naming Convention

```
{TICKER}_{YYYYMMDDTHHMM}.yaml
```

| Component | Description | Example |
|-----------|-------------|--------|
| TICKER | Stock symbol (uppercase) | NVDA |
| YYYY | Year | 2025 |
| MM | Month | 01 |
| DD | Day | 20 |
| T | Separator | T |
| HH | Hour (24h) | 09 |
| MM | Minute | 30 |

**Examples:**
- `NVDA_20250120T0900.yaml` - NVDA analysis on Jan 20, 2025 at 9:00 AM
- `AMD_20250122T0935.yaml` - AMD analysis on Jan 22, 2025 at 9:35 AM
- `AI_CAPEX_20250110T0800.yaml` - Research on Jan 10, 2025 at 8:00 AM

## Subfolder Details

### earnings/
Pre-earnings and post-earnings analyses using the 8-phase framework.

**When to use:** 3-10 days before earnings announcement
**Skill:** `trading-skills/document-creation/` (earnings section)
**Key focus:** Customer demand signals (50% weight)

### stock/
Non-earnings stock analyses: technical setups, value opportunities, momentum plays.

**When to use:** Any non-earnings trading opportunity
**Skill:** `trading-skills/document-creation/` (stock section)
**Key focus:** Catalyst identification, setup scoring

### research/
Macro, sector, and thematic research with longer time horizons.

**When to use:** Developing investment themes, sector views
**Skill:** `trading-skills/document-creation/` (research section)
**Key focus:** Thesis, evidence, implications

### ticker-profiles/
Persistent knowledge about frequently traded stocks.

**When to use:** First trade in new ticker, updating known stocks
**Skill:** `trading-skills/document-creation/` (ticker section)
**Key focus:** Patterns, history, your edge

## Integration

| From | To | When |
|------|-----|------|
| Scanners | analysis/ | High-score candidates trigger analysis |
| analysis/ | trades/ | BUY/SELL recommendations become trades |
| analysis/ | watchlist/ | WATCH recommendations go to watchlist |
| trades/ | reviews/ | Closed trades trigger reviews |
