# Market Scanning Skill

## Purpose
Systematically identify trading opportunities using defined scanners.

## When to Use
- Daily market routine
- Finding new trade candidates
- Monitoring for setups

## Scanner Configurations
Scanner configs live in: `trading-knowledge/scanners/`

## Output
- Watchlist candidates
- Triggers for full analysis

---

## Available Scanners

### Daily Scanners

| Scanner | File | Time | Purpose |
|---------|------|------|---------|
| Market Regime | `market-regime.yaml` | 09:35 | Classify market |
| Pre-Market Gap | `premarket-gap.yaml` | 08:30 | Gaps with catalysts |
| News Catalyst | `news-catalyst.yaml` | 07:00/12:00/18:00 | Material news |
| Earnings Momentum | `earnings-momentum.yaml` | 09:45 | Pre-earnings setups |
| Options Flow | `options-flow.yaml` | Intraday | Unusual options |
| Unusual Volume | `unusual-volume.yaml` | Intraday | Volume spikes |
| 52-Week Extremes | `52w-extremes.yaml` | 15:45 | Breakouts/breakdowns |
| Sector Rotation | `sector-rotation.yaml` | 16:15 | Sector flows |
| Oversold Bounce | `oversold-bounce.yaml` | 15:50 | Mean reversion |

### Weekly Scanners

| Scanner | File | Time | Purpose |
|---------|------|------|---------|
| Earnings Calendar | `earnings-calendar.yaml` | Sun 07:00 | Week ahead earnings |
| Institutional Activity | `institutional-activity.yaml` | Mon/Fri 18:00 | 13F, insiders |

---

## Scanner Execution Framework

### General Workflow

```
1. GATHER DATA
   Use tools: Trading API, web search, data feeds
   Collect required data points per scanner config

2. APPLY FILTERS
   - Liquidity (volume, market cap)
   - Quality (fundamentals, technicals)
   - Exclusions (specific tickers, sectors)

3. SCORE CANDIDATES
   Apply scoring criteria from scanner config
   Calculate weighted total score

4. OUTPUT RESULTS
   - Score >= 7.5: Trigger full analysis
   - Score 5.5-7.4: Add to watchlist
   - Score < 5.5: Skip
```

### Daily Routine

```
PRE-MARKET (07:00-09:30):
□ Run News Catalyst scanner
□ Run Pre-Market Gap scanner
□ Note high-priority candidates

MARKET OPEN (09:35-10:00):
□ Run Market Regime classifier
□ Run Earnings Momentum scanner
□ First Unusual Volume check

MID-DAY (11:00-14:00):
□ Options Flow checks
□ Unusual Volume updates

CLOSE (15:30-16:15):
□ 52-Week Extremes scanner
□ Oversold Bounce scanner
□ Sector Rotation scanner
□ Compile daily summary
```

### Scoring System

All scanners use 1-10 scoring with criteria weights:

```
SCORE CALCULATION:
Score = Σ (Criterion Score × Weight)

Where weights sum to 1.0

INTERPRETATION:
≥ 7.5: High priority - trigger full analysis
6.5-7.4: Good - add to watchlist
5.5-6.4: Marginal - monitor only
< 5.5: Skip
```

---

## Scanner Output Format

```yaml
scanner_run:
  scanner: "{name}"
  timestamp: "{ISO_DATETIME}"
  regime: "{from regime classifier}"

candidates:
  - ticker: "AAAA"
    score: 8.5
    action: "FULL_ANALYSIS"
    key_data: {}
    
  - ticker: "BBBB"
    score: 6.8
    action: "WATCHLIST"
    key_data: {}

summary:
  total_scanned: 500
  passed_filters: 45
  high_score: 5
```

---

## Integration

```
Scanner Output → Action
─────────────────────────
Score >= 7.5   → Create analysis (earnings or stock)
Score 5.5-7.4  → Create watchlist entry
Score < 5.5    → No action
```

---

## Scanner Configuration Reference

Each scanner YAML contains:
- `scanner_config`: Metadata, schedule, limits
- `scanner`: Data sources (IB, web search)
- `quality_filters`: Liquidity, exclusions
- `scoring`: Criteria with weights
- `agent_instructions`: Execution steps

See individual scanner files for details.
