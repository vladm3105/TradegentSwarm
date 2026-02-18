# Earnings Analysis Skill

## Purpose
Systematic 8-phase analysis of stocks before earnings announcements.

## When to Use
- 3-10 days before earnings announcement
- Scanner identifies high-potential earnings setup
- Manual review of upcoming earnings

## Required Inputs
- Ticker symbol
- Earnings date and time (BMO/AMC)
- Current stock price
- Consensus EPS and revenue estimates

## Output
- File: `{TICKER}_{YYYYMMDDHHMM}.yaml`
- Location: `trading-knowledge/analysis/earnings/`

---

## 8-Phase Framework

### Phase 1: Preparation
```
GATHER:
□ Last 8 quarters earnings history
  - EPS actual vs estimate
  - Revenue actual vs estimate
  - Stock reaction day 1 and day 5
  - Guidance given (raised/maintained/lowered)

□ Current estimates
  - Consensus EPS
  - Consensus revenue
  - Whisper number (if available)
  - High/low analyst range

□ Estimate revisions (last 30 days)
  - Direction of revisions
  - Magnitude of changes

□ Options market
  - Implied move (ATM straddle / stock price)
  - IV percentile vs historical

OUTPUT:
- Beat rate: X/8 quarters
- Average surprise: X%
- Average move on beat: +X%
- Average move on miss: -X%
- Current implied move: X%
```

### Phase 2: Customer Demand Signals
```
*** CRITICAL: This determines 50% of your assessment ***

SEARCH FOR evidence of customer spending:

FOR SEMICONDUCTORS (NVDA, AMD, AVGO, etc.):
□ Hyperscaler CapEx announcements
  - Microsoft Azure spending
  - Google Cloud spending
  - Amazon AWS spending
  - Meta AI infrastructure
□ Data center build announcements
□ AI chip demand indicators
□ Supply chain checks

FOR ENTERPRISE SOFTWARE (CRM, NOW, WDAY, etc.):
□ IT spending surveys
□ CIO sentiment indicators
□ Digital transformation budgets
□ Competitor results (if reported)

FOR CONSUMER (AMZN, WMT, TGT, etc.):
□ Consumer confidence data
□ Retail sales trends
□ Credit card spending data
□ Same-store sales (peers)

FOR HEALTHCARE:
□ Prescription data
□ Procedure volumes
□ Insurance claims data

SCORE THE SIGNAL:
- Strong Bullish: Multiple clear positive signals → +15-20% to base rate
- Moderate Bullish: Some positive signals → +5-10% to base rate
- Neutral: Mixed or no clear signal → No adjustment
- Moderate Bearish: Some negative signals → -5-10% from base rate
- Strong Bearish: Multiple negative signals → -15-20% from base rate

DOCUMENT:
- Each signal source
- Signal strength
- Your interpretation
```

### Phase 3: Technical Setup
```
ANALYZE:
□ Trend structure
  - Price vs 20-day MA
  - Price vs 50-day MA
  - Price vs 200-day MA
  - MA alignment (bullish: 20>50>200)

□ Momentum
  - RSI level
  - Recent price action (consolidating, trending, overextended)

□ Key levels
  - Nearest support
  - Nearest resistance
  - All-time high proximity

□ Volume
  - Recent volume vs average
  - Volume trend

□ Pre-earnings positioning
  - Already run up? (priced in risk)
  - Pulled back? (opportunity)

TECHNICAL SCORE: 1-10
```

### Phase 4: Sentiment Analysis
```
GATHER:
□ Analyst ratings
  - Buy/Hold/Sell distribution
  - Recent changes (upgrades/downgrades)
  - Price target range

□ Short interest
  - % of float
  - Days to cover
  - Recent changes

□ Options positioning
  - Put/call ratio
  - Unusual activity

□ News sentiment
  - Recent headlines
  - Tone (positive/negative/neutral)

ASSESS CONTRARIAN OPPORTUNITY:
- If everyone bullish → Downside risk from high expectations
- If everyone bearish → Upside potential from low bar
- If mixed → Neutral

SENTIMENT SCORE: 1-10
```

### Phase 5: Probability Assessment
```
START WITH BASE RATE:
- Use historical beat rate for this stock
- Example: 6/8 = 75% base rate

ADJUST FOR SIGNALS:

Customer Demand (±15-20%):
  Strong bullish signal: +15-20%
  Moderate bullish: +5-10%
  Neutral: 0%
  Moderate bearish: -5-10%
  Strong bearish: -15-20%

Estimate Revisions (±10%):
  Strong upward revisions: +5-10%
  Slight upward: +2-5%
  Flat: 0%
  Slight downward: -2-5%
  Strong downward: -5-10%

Sentiment Contrarian (±10%):
  Very bearish sentiment: +5-10% (low bar)
  Neutral: 0%
  Very bullish sentiment: -5-10% (high bar)

Technical Setup (±5%):
  Strong bullish setup: +3-5%
  Neutral: 0%
  Weak setup: -3-5%

CALCULATE:
P(Beat) = Base Rate + Adjustments
P(Miss) = 100% - P(Beat)
P(Significant Beat >5%) = P(Beat) × 0.4 (rough estimate)

CONFIDENCE:
- High: Clear signals, consistent data
- Medium: Some ambiguity
- Low: Conflicting signals
```

### Phase 6: Bias Check
```
HONESTLY ASSESS:

□ Recency Bias
  Am I overweighting the last 1-2 quarters?
  Have I checked all 8 quarters?

□ Confirmation Bias
  Did I search for contrary evidence?
  What's the bear case?

□ Overconfidence
  Is my probability too extreme (>80% or <20%)?
  What could I be missing?

□ Anchoring
  Am I anchored to a price or outcome?
  Would I feel differently at a different price?

□ FOMO
  Am I rushing because others are trading this?
  Is my process complete?

IF ANY BIAS DETECTED:
- Document it
- Describe how you're correcting
- Consider reducing position size
```

### Phase 7: Decision Framework
```
DECISION MATRIX:

IF P(Beat) ≥ 70% AND customer demand strong AND IV reasonable:
  → BULLISH
  → Position: 4-6% of portfolio
  → Structure: Stock or call spreads

IF P(Beat) 55-70% AND customer demand positive:
  → MODERATE BULLISH
  → Position: 2-4% of portfolio
  → Structure: Smaller position or defined risk

IF P(Beat) 45-55% OR mixed signals:
  → NEUTRAL / DO NOT TRADE
  → No position
  → Add to watchlist for post-earnings

IF P(Beat) 30-45% AND customer demand weak:
  → MODERATE BEARISH
  → Position: 2-4% of portfolio
  → Structure: Puts or put spreads

IF P(Beat) < 30% AND customer demand very weak:
  → BEARISH
  → Position: 4-6% of portfolio
  → Structure: Puts or short stock

DO-NOTHING GATE:
- If no clear edge → DO NOT TRADE
- If IV too high (>80th percentile) → Consider avoiding or use spreads
- If position would exceed 6% → Reduce size
```

### Phase 8: Execution Plan
```
IF TRADING:

Entry:
  - Price: [specific or "at market"]
  - Date: [when]
  - Size: [shares or contracts]
  - % of portfolio: [X%]

Structure:
  - Stock / Calls / Puts / Spreads
  - Strike(s): [if options]
  - Expiration: [if options]

Risk Management:
  - Stop loss: [price or condition]
  - Max loss: $[amount] ([X%] of portfolio)

Profit Target:
  - Target 1: [price] - sell [X%]
  - Target 2: [price] - sell [X%]
  - Or: "Hold through earnings"

Contingency:
  - If gaps against: [action]
  - If gaps for: [action]
  - If flat: [action]

Post-Earnings Plan:
  - Review within 24 hours
  - Update thesis with actual results
  - Trigger post-trade review
```

---

## Template

See `template.yaml` for the output format.

---

## Quality Checklist

Before finalizing:
□ All 8 phases completed
□ Customer demand thoroughly researched (50% weight)
□ Probabilities sum correctly
□ Bias check done honestly
□ Clear recommendation stated
□ Execution plan specific
□ Risk defined
