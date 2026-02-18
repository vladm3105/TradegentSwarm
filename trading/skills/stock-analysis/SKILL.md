# Stock Analysis Skill

## Purpose
Systematic 7-phase analysis for non-earnings trading opportunities: technical setups, value plays, momentum trades.

## When to Use
- Technical breakout/breakdown setup
- Value opportunity identified
- Momentum/trend following
- Post-earnings drift
- Catalyst-driven opportunity (non-earnings)

## Required Inputs
- Ticker symbol
- Catalyst or reason for analysis
- Current stock price

## Output
- File: `{TICKER}_{YYYYMMDDTHHMM}.yaml`
- Location: `knowledge/analysis/stock/`

---

## 7-Phase Framework

### Phase 1: Catalyst Identification
```
IDENTIFY THE CATALYST:

Technical Catalysts:
□ Breakout above resistance
□ Breakdown below support
□ Chart pattern completion (cup/handle, flag, H&S)
□ Moving average crossover
□ Support test / bounce

Fundamental Catalysts:
□ Valuation anomaly
□ Growth inflection point
□ Margin expansion
□ New product/market
□ Restructuring/turnaround

Event Catalysts:
□ FDA approval/rejection
□ M&A announcement
□ Activist involvement
□ Regulatory change
□ Management change

Momentum Catalysts:
□ Relative strength breakout
□ Sector rotation beneficiary
□ Institutional accumulation
□ Short squeeze setup

RATE CATALYST QUALITY: 1-10
- 10: Clear, specific, timely catalyst
- 7: Good catalyst, some ambiguity
- 5: Weak catalyst or timing unclear
- 3: No clear catalyst (avoid)

NO CLEAR CATALYST = NO TRADE
```

### Phase 2: Market Environment
```
CHECK MARKET CONTEXT:

□ Market Regime (from regime classifier)
  - Strong Bull / Bull / Pullback / Sideways / Bear / Crisis
  - Strategy alignment with regime?

□ Sector Trend
  - Sector vs SPY (leading/lagging)
  - Sector momentum direction
  - Rotation signals

□ Volatility Environment
  - VIX level
  - VIX trend
  - Impact on position sizing

□ Correlation Regime
  - Stock-picking environment?
  - Risk-on or risk-off?

ENVIRONMENT SCORE: 1-10
- 10: Perfect alignment (bull market, leading sector, low vol)
- 7: Good alignment
- 5: Neutral
- 3: Fighting the tape (reduce size or avoid)
```

### Phase 3: Technical Analysis
```
ANALYZE PRICE ACTION:

Trend Analysis:
□ Primary trend (weekly)
□ Intermediate trend (daily)
□ Short-term trend (hourly)
□ Price vs 20/50/200 MA
□ MA alignment

Pattern Recognition:
□ Chart patterns present
□ Pattern completion status
□ Measured move target

Key Levels:
□ Immediate support
□ Immediate resistance
□ Major support
□ Major resistance
□ All-time high proximity

Volume Analysis:
□ Volume trend
□ Volume at key levels
□ Accumulation/distribution

Momentum:
□ RSI level and trend
□ MACD signal
□ Relative strength vs SPY

TECHNICAL SCORE: 1-10
```

### Phase 4: Fundamental Check
```
VERIFY FUNDAMENTALS:

Valuation:
□ P/E vs peers
□ P/E vs history
□ P/S ratio
□ EV/EBITDA
□ PEG ratio

Growth:
□ Revenue growth rate
□ Earnings growth rate
□ Growth trajectory

Quality:
□ Profit margins
□ Return on equity
□ Free cash flow
□ Debt levels

Insider Activity:
□ Recent insider buys/sells
□ Institutional ownership changes

RED FLAGS (Any = caution):
□ Declining revenues
□ Rising debt significantly
□ Heavy insider selling
□ Accounting concerns
□ Negative cash flow

FUNDAMENTAL SCORE: 1-10
(Lower weight for technical trades, higher for value)
```

### Phase 5: Sentiment & Positioning
```
ASSESS MARKET SENTIMENT:

Analyst Sentiment:
□ Ratings distribution
□ Recent changes
□ Price target range

Short Interest:
□ % of float short
□ Days to cover
□ Trend

Options Activity:
□ Put/call ratio
□ Unusual options flow
□ IV vs historical

Retail/Institutional:
□ Social sentiment (if relevant)
□ 13F filings
□ Fund flows

SENTIMENT SCORE: 1-10
Note contrarian opportunities
```

### Phase 6: Scenario Analysis
```
DEFINE THREE SCENARIOS:

BULL CASE:
- Probability: ___% 
- What happens: [specific outcome]
- Price target: $___
- Timeline: ___ days/weeks
- Key driver: [what makes this happen]

BASE CASE:
- Probability: ___%
- What happens: [expected outcome]
- Price target: $___
- Timeline: ___ days/weeks
- Key driver: [most likely path]

BEAR CASE:
- Probability: ___%
- What happens: [what goes wrong]
- Price target: $___
- Timeline: ___ days/weeks
- Key driver: [risk factor]

PROBABILITIES MUST SUM TO 100%

Expected Value:
EV = (P_bull × Bull_return) + (P_base × Base_return) + (P_bear × Bear_return)
```

### Phase 7: Risk Management
```
CALCULATE POSITION:

Entry:
- Trigger: [specific condition]
- Price: [exact or range]
- Order type: [limit/stop/market]

Stop Loss:
- Price: $___
- Basis: [technical level, %, ATR]
- Type: [hard/mental/trailing]

Position Size:
- Account risk: ___% (1-2% max)
- Dollar risk: $___
- Stop distance: ___%
- Position size = Dollar risk / (Entry × Stop %)
- Shares: ___
- Position value: $___
- % of portfolio: ___%

Risk/Reward:
- Risk: $____ (___%)
- Reward (base case): $____ (___%)
- R:R ratio: ___:1
- MINIMUM 2:1 REQUIRED

Targets:
- Target 1: $___ (sell ___%)
- Target 2: $___ (sell ___%)
- Trailing stop after T1: [method]

Time Stop:
- If nothing in ___ days: [action]
```

---

## Scoring & Recommendation

```
SETUP SCORE CALCULATION:

Catalyst Quality:     ___/10 × 0.25 = ___
Market Environment:   ___/10 × 0.15 = ___
Technical Setup:      ___/10 × 0.25 = ___
Risk/Reward:          ___/10 × 0.25 = ___
Sentiment Edge:       ___/10 × 0.10 = ___
                              ─────────
TOTAL SCORE:                    ___/10

RECOMMENDATION:
- Score ≥ 7.5: STRONG_BUY (or STRONG_SELL)
- Score 6.5-7.4: BUY (or SELL)
- Score 5.5-6.4: WATCH (add to watchlist)
- Score < 5.5: AVOID

If WATCH: Document entry trigger for watchlist
```

---

## Template

See `template.yaml` for the output format.

---

## Quality Checklist

Before finalizing:
□ Clear catalyst identified
□ Market environment checked
□ Technical levels mapped
□ Fundamentals verified (no red flags)
□ Sentiment assessed
□ Three scenarios with probabilities
□ Position size calculated
□ R:R ≥ 2:1
□ Clear recommendation with score
