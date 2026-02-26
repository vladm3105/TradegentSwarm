# Tradegent Workflow Overview

## The Complete Analysis Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ANALYSIS PHASE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. EARNINGS ANALYSIS (pre-earnings)                                         │
│     Trigger: "earnings analysis NVDA" or scheduled before earnings           │
│     Output:  knowledge/analysis/earnings/NVDA_20260225T0800.yaml             │
│              knowledge/analysis/earnings/NVDA_20260225T0800.svg (dashboard)  │
│                                                                              │
│  2. STOCK ANALYSIS (any time)                                                │
│     Trigger: "stock analysis NVDA" or scheduled                              │
│     Output:  knowledge/analysis/stock/NVDA_20260226T1000.yaml                │
│              knowledge/analysis/stock/NVDA_20260226T1000.svg (dashboard)     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           VALIDATION PHASE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  3. REPORT VALIDATION (auto or manual)                                       │
│     Trigger: Auto when new analysis saved (if prior exists)                  │
│              Auto when forecast_valid_until expires                          │
│              Manual: "validate analysis NVDA"                                │
│     Output:  knowledge/reviews/validation/NVDA_20260226T1005.yaml            │
│     Result:  CONFIRM | SUPERSEDE | INVALIDATE                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EARNINGS RELEASE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  4. POST-EARNINGS REVIEW (T+1 after earnings)                                │
│     Trigger: Auto T+1 after earnings date                                    │
│              Manual: "post-earnings review NVDA"                             │
│     Output:  knowledge/reviews/post-earnings/NVDA_20260226T1400.yaml         │
│     Result:  Grade A-F, confidence calibration update                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TRADE PHASE                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  5. TRADE JOURNAL (when position entered)                                    │
│     Trigger: "bought NVDA" or position detected                              │
│     Output:  knowledge/trades/NVDA_20260226T0935.yaml                        │
│                                                                              │
│  6. POST-TRADE REVIEW (when position closed)                                 │
│     Trigger: Trade closed                                                    │
│     Output:  knowledge/reviews/{YEAR}/{MM}/NVDA_20260301_review.yaml         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## What Gets Created on Each Run

### 1. Stock Analysis (`python tradegent.py analyze NVDA --type stock`)

| Output | Location | Content |
|--------|----------|---------|
| **YAML** | `knowledge/analysis/stock/NVDA_20260226T1000.yaml` | Full analysis with recommendation, targets, scenarios, gates |
| **SVG** | `knowledge/analysis/stock/NVDA_20260226T1000.svg` | Visual dashboard with price, metrics, scenarios, gates |

**SVG Dashboard includes:**
- Recommendation badge (BUY/SELL/HOLD) with confidence
- Current price with 52-week range bar
- Do Nothing Gate results (4 criteria)
- Scenario probability bars
- Comparable companies table
- Bull/Bear case strength
- Threat assessment level

---

### 2. Earnings Analysis (`python tradegent.py analyze NVDA --type earnings`)

| Output | Location | Content |
|--------|----------|---------|
| **YAML** | `knowledge/analysis/earnings/NVDA_20260225T0800.yaml` | Pre-earnings forecast with scenarios, implied move, signals |
| **SVG** | `knowledge/analysis/earnings/NVDA_20260225T0800.svg` | Visual dashboard similar to stock analysis |

**Additional earnings-specific content:**
- Earnings date and time (BMO/AMC)
- 4 scenarios with probabilities (strong_beat, modest_beat, modest_miss, strong_miss)
- Options implied move
- Customer demand signals
- Falsification criteria

---

### 3. Report Validation (Auto-triggered or `python tradegent.py validate-analysis run NVDA`)

| Output | Location | Content |
|--------|----------|---------|
| **YAML** | `knowledge/reviews/validation/NVDA_20260226T1005.yaml` | Comparison of prior vs new analysis |

**No SVG generated** - this is a validation record, not a visual dashboard.

**Content includes:**
- Prior analysis reference
- New analysis reference
- Thesis comparison (8+ aspects)
- Falsification check
- Validation result: **CONFIRM**, **SUPERSEDE**, or **INVALIDATE**
- If INVALIDATE: reason, watchlist update, alert

---

### 4. Post-Earnings Review (Auto T+1 or `python tradegent.py review-earnings run NVDA`)

| Output | Location | Content |
|--------|----------|---------|
| **YAML** | `knowledge/reviews/post-earnings/NVDA_20260226T1400.yaml` | Forecast vs actual comparison |

**No SVG generated** - this is a review record.

**Content includes:**
- Prior analysis reference
- Actual earnings results (from Brave web search)
- Scenario outcome (which scenario occurred)
- Implied move vs actual move comparison
- Forecast vs actual point-by-point
- Customer demand signal accuracy
- Data source effectiveness grades
- Bias retrospective
- **Thesis accuracy grade (A-F)**
- Confidence calibration update
- Framework lessons learned

---

### 5. Trade Journal (`log trade NVDA`)

| Output | Location | Content |
|--------|----------|---------|
| **YAML** | `knowledge/trades/NVDA_20260226T0935.yaml` | Trade entry documentation |

**No SVG generated**.

---

### 6. Post-Trade Review (Auto when trade closed)

| Output | Location | Content |
|--------|----------|---------|
| **YAML** | `knowledge/reviews/2026/02/NVDA_20260301_review.yaml` | Trade outcome analysis |

**No SVG generated**.

---

## Summary: Files Created

| Event | YAML Created | SVG Created |
|-------|--------------|-------------|
| Stock analysis | ✅ `analysis/stock/` | ✅ Auto-generated |
| Earnings analysis | ✅ `analysis/earnings/` | ✅ Auto-generated |
| Report validation | ✅ `reviews/validation/` | ❌ |
| Post-earnings review | ✅ `reviews/post-earnings/` | ❌ |
| Trade journal | ✅ `trades/` | ❌ |
| Post-trade review | ✅ `reviews/{year}/{month}/` | ❌ |

---

## Automatic Triggers

```
┌────────────────────────┬────────────────────────────────────────────────────┐
│ Event                  │ What Gets Triggered                                │
├────────────────────────┼────────────────────────────────────────────────────┤
│ New analysis saved     │ → Report validation (if prior analysis exists)     │
│                        │ → RAG embed + Graph extract (always)               │
├────────────────────────┼────────────────────────────────────────────────────┤
│ Earnings date passes   │ → Post-earnings review (T+1, 4hrs after open)      │
├────────────────────────┼────────────────────────────────────────────────────┤
│ forecast_valid_until   │ → Report validation (check if still valid)         │
│ expires                │                                                    │
├────────────────────────┼────────────────────────────────────────────────────┤
│ Trade closed           │ → Post-trade review                                │
├────────────────────────┼────────────────────────────────────────────────────┤
│ INVALIDATE result      │ → Watchlist entry invalidated                      │
│                        │ → Alert logged                                     │
└────────────────────────┴────────────────────────────────────────────────────┘
```

---

## Database Tables Supporting This Workflow

### `nexus.analysis_lineage`
Tracks the chain of analyses for each ticker:
- Current analysis file and date
- Prior analysis reference
- Validation status (active, confirmed, superseded, invalidated)
- Post-earnings review file and grade
- Forecast expiration date

### `nexus.confidence_calibration`
Tracks prediction accuracy by confidence bucket:
- Confidence bucket (50%, 60%, 70%, 80%, 90%)
- Total predictions at each level
- Correct predictions
- Actual accuracy rate

---

## CLI Commands Quick Reference

```bash
# Analysis
python tradegent.py analyze NVDA --type stock
python tradegent.py analyze NVDA --type earnings

# Validation
python tradegent.py validate-analysis run NVDA
python tradegent.py validate-analysis expired
python tradegent.py validate-analysis process-expired

# Post-Earnings Review
python tradegent.py review-earnings run NVDA
python tradegent.py review-earnings pending
python tradegent.py review-earnings backfill --limit 10

# Lineage & Calibration
python tradegent.py lineage show NVDA
python tradegent.py lineage active
python tradegent.py calibration summary
```

---

## Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| `auto_post_earnings_review` | true | Auto-queue review T+1 after earnings |
| `auto_report_validation` | true | Auto-validate when new analysis saved |
| `validation_on_expiry` | true | Auto-validate when forecast expires |
| `post_earnings_delay_hours` | 4 | Hours after market open to queue review |
| `invalidation_alerts_enabled` | true | Log alerts on INVALIDATE |

---

*Last updated: 2026-02-26 (IPLAN-001)*
