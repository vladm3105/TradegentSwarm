# Stock Analysis Skill v2.3

## Purpose
Systematic multi-phase analysis for non-earnings trading opportunities: technical setups, value plays, momentum trades. Enhanced with reasoning sections, bias checks, and decision gates.

## When to Use
- Technical breakout/breakdown setup
- Value opportunity identified
- Momentum/trend following
- Post-earnings drift
- Catalyst-driven opportunity (non-earnings)
- Follow-up analysis (post-mortem)

## Required Inputs
- Ticker symbol
- Catalyst or reason for analysis
- Current stock price (verify data quality)

## Output
- File: `{TICKER}_{YYYYMMDDTHHMM}.yaml`
- Location: `knowledge/analysis/stock/`

---

## Framework Overview (12 Phases)

```
Phase 0.5: Data Quality Check      → Verify data reliability
Phase 1:   Catalyst Identification → Why trade this?
Phase 1.5: News Age Check          → Is news priced in?
Phase 2:   Market Environment      → Context alignment
Phase 2.5: Threat Assessment       → Structural vs cyclical
Phase 3:   Technical Analysis      → Price action setup
Phase 4:   Fundamental Check       → Value assessment
Phase 5:   Sentiment & Positioning → Market psychology
Phase 5.5: Expectations Assessment → Priced for perfection?
Phase 6:   Scenario Analysis       → 4-scenario framework
Phase 7:   Steel-Man Bear Case     → Counter-arguments
Phase 8:   Bias Check              → Self-assessment
Phase 9:   Do Nothing Gate         → Go/No-Go decision
Phase 9.5: Pass Reasoning          → Document why passing
Phase 10:  Alternative Strategies  → Options when NO_POSITION
Phase 11:  Trade Plan              → Execution details
Phase 12:  Summary & Action Items  → Quick reference
```

---

## Phase 0.5: Data Quality Check (NEW)
```
VERIFY DATA QUALITY BEFORE ANALYSIS:

□ Price data source: IB Gateway / Yahoo / Manual / Delayed
□ Price data fresh? (< 1 hour old for intraday relevance)
□ Any data gaps or errors?
□ Key metrics verified from reliable source?

IF data issues exist:
  → Flag with ⚠️ warning in data_quality.warning
  → Note requires_reverification = true
  → Document limitations and impact

Example warning:
"⚠️ DATA LIMITATION: IB Gateway offline - verify prices before trading"

PROCEED WITH CAUTION if data quality is compromised.
```

---

## Phase 1: Catalyst Identification
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

WRITE REASONING:
Document 2-3 paragraphs explaining the catalyst:
- What is the specific catalyst?
- Why is the timing right?
- What makes this catalyst actionable?
```

---

## Phase 1.5: News Age Check (NEW)
```
ASSESS IF NEWS IS PRICED IN:

FOR EACH relevant news item, create table:
| News Item | Date | Age (weeks) | Priced In? | Reasoning |
|-----------|------|-------------|------------|-----------|
| | | | Fully/Partially/Not | |

RULES OF THUMB:
- 6+ weeks old → Likely FULLY priced in
- 2-6 weeks old → PARTIALLY priced, magnitude matters
- < 2 weeks old → May NOT be fully priced
- Fresh catalyst (< 1 week) → Price discovery ongoing

ASSESS:
□ Stale news risk? (relying heavily on old catalysts)
□ Fresh catalyst exists?
□ Market had time to digest information?

IF stale_news_risk = true AND fresh_catalyst_exists = false:
  → Reduce conviction
  → This may be "priced in" trade
  → Consider whether edge remains
```

---

## Phase 2: Market Environment
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

WRITE CONTEXT:
Document market alignment and sector dynamics.
```

---

## Phase 2.5: Threat Assessment (NEW)
```
CLASSIFY THE PRIMARY THREAT:

STRUCTURAL vs CYCLICAL FRAMEWORK:

STRUCTURAL THREAT (Business model at risk):
□ Moat erosion evidence?
□ Competitive disruption?
□ Secular decline?
□ Regulatory existential risk?

If structural threat exists:
  - Beat streak IRRELEVANT (past success doesn't predict future)
  - Management credibility suspect
  - Value trap risk HIGH
  - Historical valuation NOT anchor

CYCLICAL WEAKNESS (Temporary downturn):
□ Industry-wide slowdown?
□ Macro-driven demand dip?
□ Temporary execution issues?
□ Recovery catalysts visible?

If cyclical weakness:
  - Beat streak RELEVANT
  - History is valid guide
  - Recovery timeline estimable
  - Buy-the-dip candidate

WRITE THREAT SUMMARY:
"This is [STRUCTURAL/CYCLICAL/NONE] because..."
```

---

## Phase 3: Technical Analysis
```
ANALYZE PRICE ACTION:

Trend Analysis:
□ Primary trend (weekly)
□ Intermediate trend (daily)
□ Short-term trend (hourly)
□ Price vs 20/50/200 MA
□ MA alignment (bullish/neutral/bearish)
□ Death cross or golden cross?

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
□ 52-week low proximity

Volume Analysis:
□ Volume trend
□ Volume at key levels
□ Accumulation/distribution

Momentum:
□ RSI level (overbought/neutral/oversold)
□ MACD signal
□ ADX trend strength
□ Relative strength vs SPY

TECHNICAL SCORE: 1-10

WRITE TECHNICAL SUMMARY:
Document setup quality and key observations.
```

---

## Phase 4: Fundamental Check
```
VERIFY FUNDAMENTALS:

Valuation:
□ P/E vs peers (cheap/fair/expensive)
□ P/E vs 5-year history
□ P/S ratio
□ EV/EBITDA
□ PEG ratio
□ FCF yield

Growth:
□ Revenue growth rate
□ Earnings growth rate
□ Growth trajectory (accelerating/stable/decelerating)

Quality:
□ Profit margins
□ Operating margin
□ Return on equity
□ Free cash flow
□ Debt levels

KEY METRIC:
Identify the ONE metric that matters most for this stock.
- What is consensus expecting?
- What is YOUR view?

WHAT WOULD SURPRISE:
- Positive surprise: What could beat?
- Negative surprise: What could disappoint?

Insider Activity:
□ Recent insider buys/sells
□ Notable transactions
□ Insider selling at lows? (RED FLAG)

RED FLAGS (Any = caution):
□ Declining revenues
□ Rising debt significantly
□ Heavy insider selling
□ Accounting concerns
□ Negative cash flow

FUNDAMENTAL SCORE: 1-10

WRITE ASSESSMENTS:
1. Value trap assessment: Is this a trap or opportunity?
2. Market missing: What does consensus not appreciate?
```

---

## Phase 5: Sentiment & Positioning
```
ASSESS MARKET SENTIMENT:

Analyst Sentiment:
□ Ratings distribution (buy/hold/sell)
□ Recent rating changes
□ Price target range
□ Notable analyst calls

Short Interest:
□ % of float short
□ Days to cover
□ Trend (increasing/decreasing)
□ Squeeze potential?

Options Activity:
□ Put/call ratio
□ IV percentile
□ IV rank
□ Unusual options flow (bullish/bearish)

Institutional:
□ Ownership %
□ Recent 13F changes
□ Notable holders

Retail Sentiment:
□ Social media sentiment
□ Capitulation signs?

CROWDED TRADE CHECK:
□ Is everyone on the same side?
□ Consensus direction?
□ Contrarian opportunity?
□ Contrarian TRAP risk?

SENTIMENT SCORE: 1-10 (0-100 numeric)
```

---

## Phase 5.5: Expectations Assessment (NEW)
```
"PRICED FOR PERFECTION" CHECK:

□ Near ATH? (within 10%)
  - If yes: Limited upside even on beat
  - ATH distance: ___%

□ Beat streak length?
  - If >6 consecutive beats: "Priced for perfection" risk
  - Market EXPECTS beats, surprise asymmetric

□ Analyst targets already reached?
  - If current price near avg target: Where does upside come from?

□ Crowded bullish consensus?
  - If >80% buy ratings: Disappointment risk elevated

SELL THE NEWS RISK:
- Low: Stock beaten down, low expectations, setup for surprise
- Medium: Stock near fair value, moderate expectations
- High: Stock near ATH, high expectations, long beat streak

→ If HIGH: Even a beat may get "sell the news" reaction

DOCUMENT:
- Expectations level: Low / Moderate / High / Extreme
- Priced for perfection: YES / NO
- Sell the news risk: Low / Medium / High
- Limited upside even on beat: YES / NO
```

---

## Phase 6: Scenario Analysis (4 Scenarios)
```
DEFINE FOUR SCENARIOS (not three):

STRONG BULL CASE:
- Probability: ___%
- What happens: [best case outcome]
- Price target: $___
- Return: ___%
- Timeline: ___ days
- Key driver: [what makes this happen]

BASE BULL CASE:
- Probability: ___%
- What happens: [moderately positive]
- Price target: $___
- Return: ___%
- Timeline: ___ days
- Key driver: [likely positive path]

BASE BEAR CASE:
- Probability: ___%
- What happens: [moderately negative]
- Price target: $___
- Return: ___%
- Timeline: ___ days
- Key driver: [likely negative path]

STRONG BEAR CASE:
- Probability: ___%
- What happens: [worst case]
- Price target: $___
- Return: ___%
- Timeline: ___ days
- Key driver: [risk factor]

PROBABILITIES MUST SUM TO 100%

Expected Value Calculation:
EV = (P_sb × R_sb) + (P_bb × R_bb) + (P_br × R_br) + (P_sr × R_sr)

Write out the calculation explicitly.
```

---

## Phase 7: Steel-Man Bear Case (NEW)
```
ARGUE THE BEAR CASE HONESTLY:

For each bear argument:
| # | Argument | Evidence | Counter | Strength |
|---|----------|----------|---------|----------|
| 1 | | | | 1-10 |
| 2 | | | | 1-10 |
| 3 | | | | 1-10 |
| 4 | | | | 1-10 |
| 5 | | | | 1-10 |

BEAR CASE STRENGTH (overall): 1-10

WRITE BEAR CASE SUMMARY:
Steel-man the bear case in 2-3 paragraphs.
Be honest about when bears would be right.

INTERPRETATION:
- 8-10: Bear case compelling, need strong bull conviction
- 6-7: Solid bear case, proceed with caution
- 4-5: Weak bear case, bull case dominates
- 1-3: No credible bear case
```

---

## Phase 8: Bias Check (NEW)
```
MANDATORY BIAS ASSESSMENT:

For each bias:
| Bias | Detected | Severity | Notes | Mitigation |
|------|----------|----------|-------|------------|
| Recency | Y/N | H/M/L | | |
| Confirmation | Y/N | H/M/L | | |
| Timing Conservatism | Y/N | H/M/L | | |
| Anchoring | Y/N | H/M/L | | |
| Overconfidence | Y/N | H/M/L | | |
| Loss Aversion | Y/N | H/M/L | | |
| FOMO | Y/N | H/M/L | | |
| Value Trap Blindness | Y/N | H/M/L | | |
| Contrarian Trap | Y/N | H/M/L | | |
| Category Error | Y/N | H/M/L | | |

SPECIAL CHECKS:

TIMING CONSERVATISM:
"Weakness + strong fundamentals = ENTRY SIGNAL, not warning"
□ Am I treating weakness as warning when it's actually opportunity?
□ this_is_entry_signal: true/false

ANCHORING:
□ What price am I anchored to? $___
□ Is my target based on wishful thinking or realistic analysis?

CONFIRMATION BIAS:
□ Did I seek contrary evidence? Y/N
□ What contrary sources did I check?
□ What's the strongest counter-argument?

LOSS AVERSION PRE-EXIT GATE (v2.3):
When position is profitable:
□ Is thesis intact?
□ Is catalyst still pending?
□ Am I exiting due to LOGIC or FEAR?
→ If thesis_intact AND catalyst_pending AND exit_reason=FEAR:
   "The catalyst justified entry; don't exit before it arrives"
   gate_result = HOLD

COUNTERMEASURES:
For detected biases, document:
- Rule: "IF [condition] THEN [action]"
- Implementation steps
- Checklist addition
- Mantra (memorable phrase)

FINAL CHECK:
□ Both sides argued equally? Y/N
□ Would I feel comfortable defending the opposite position?

WRITE BIAS SUMMARY.
```

---

## Phase 9: Do Nothing Gate (NEW)
```
"DO NOTHING" GATE - Must pass to take position:

| Criteria | Threshold | Actual | Pass/Fail |
|----------|-----------|--------|-----------|
| Expected Value | >5% | | |
| Confidence | >60% | | |
| Risk:Reward | >2:1 | | |
| Edge Not Priced | Yes | | |

GATES PASSED: ___/4

GATE RESULT: PASS / FAIL

IF FAIL:
→ Recommendation = NO_POSITION or WATCH
→ Document reasoning in gate_reasoning
→ Proceed to Phase 9.5 (Pass Reasoning)
→ Proceed to Phase 10 (Alternative Strategies)

POSITION SIZING BY CONFIDENCE:

| Confidence | Position Size |
|------------|---------------|
| >70% | Full position (standard) |
| 55-70% | Reduced size (50-75%) or spreads |
| <55% | No position or volatility play |
```

---

## Phase 9.5: Pass Reasoning (NEW)
```
WHEN NOT TAKING POSITION (NO_POSITION/WATCH/AVOID):

Document why passing:

PRIMARY REASON: ___

ALL REASONS:
| # | Reason | Impact |
|---|--------|--------|
| 1 | | H/M/L |
| 2 | | H/M/L |
| 3 | | H/M/L |

WRITE SUMMARY:
"Passing on this setup because..."

BETTER OPPORTUNITIES:
□ Do better opportunities exist elsewhere? Y/N
□ Opportunity cost of capital in this position?

LEARNING VALUE:
Even when passing, document the lesson:
"This analysis demonstrates..."

Example:
"Demonstrates proper application of Do Nothing gate.
Strong fundamentals don't automatically translate to favorable R:R.
Discipline in passing on marginal setups preserves capital
for higher-EV opportunities."
```

---

## Phase 10: Alternative Strategies (NEW)
```
WHEN RECOMMENDATION IS NO_POSITION:

Consider these alternatives:

ALTERNATIVE 1: Wait for Pullback
- Entry trigger: "Price reaches $___ (___% below current)"
- Entry zone: $___ - $___
- Rationale: "R:R improves at lower levels"
- Set alert? Y/N

ALTERNATIVE 2: Volatility Play
- Structure: Iron Condor / Straddle / Strangle
- Condition: "If IV elevated vs expected move"
- Rationale: "Sell premium if overpriced"

ALTERNATIVE 3: Small Speculative Position
- Condition: "If conviction develops"
- Max size: ___% of normal position
- Rationale: "Limited risk, optionality"

BEST ALTERNATIVE: ___
WHY: ___

SET ALERTS for alternative triggers.
```

---

## Phase 11: Trade Plan
```
DEFINE EXECUTION PLAN:

Entry Criteria:
- Primary trigger: ___
- Alternative trigger: ___

STAGED ENTRY (if applicable):

Tranche 1: ___% allocation
- Entry zone: $___ - $___
- Trigger: ___
- Rationale: ___

Tranche 2: ___% allocation
- Entry zone: $___ - $___
- Trigger: ___
- Rationale: ___

Tranche 3: ___% allocation
- Entry zone: $___ - $___
- Trigger: ___
- Rationale: ___

Position Sizing:
- Max portfolio %: ___
- Account risk %: ___ (1-2% max)
- Dollar risk: $___

Stop Loss:
- Price: $___
- Basis: Technical level / Percentage / ATR
- Type: Hard / Mental / Trailing
- Distance: ___%

HARD STOP (no exceptions): $___

Targets:
- Target 1: $___ (sell ___%)
- Target 2: $___ (sell ___%)
- Target 3: $___ (sell ___%)

Time Stop:
- Days: ___
- Action: ___

Contingencies:
- If gaps against: ___
- If gaps for: ___
- If thesis changes: ___
```

---

## Phase 12: Summary & Action Items
```
CREATE SUMMARY BOX:

═══════════════════════════════════════════════════════════════
{TICKER} ANALYSIS SUMMARY
Date: {date} | Event: {event} | Days: {days}
═══════════════════════════════════════════════════════════════

SETUP:
Price: ${price} | Beat History: {beats} | Key: {metric}

PROBABILITY ASSESSMENT:
- Strong Bull: {pct}% → {return}%
- Base Bull: {pct}% → {return}%
- Base Bear: {pct}% → {return}%
- Strong Bear: {pct}% → {return}%
Expected Value: {ev}%

RECOMMENDATION: {recommendation} ({confidence}% confidence)

"DO NOTHING" GATE: {result} ({n}/4 criteria)

POSITION: {position_detail}

ALTERNATIVE ACTIONS (if NO_POSITION):
1. {alternative_1}
2. {alternative_2}
3. {alternative_3}

FALSIFICATION: {criteria}

BIASES CHECKED:
- [x] Recency bias
- [x] Confirmation bias
- [x] Timing conservatism
- [x] Anchoring
- [x] Both sides argued

POST-EVENT REVIEW: {date}
═══════════════════════════════════════════════════════════════

ACTION ITEMS:
□ Immediate: ___
□ Before entry: ___
□ After entry: ___
□ Monitoring: ___
□ Post-event: ___
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
- Score ≥ 7.5 AND Gate PASS: STRONG_BUY (or STRONG_SELL)
- Score 6.5-7.4 AND Gate PASS: BUY (or SELL)
- Score 5.5-6.4 OR Gate marginal: WATCH (add to watchlist)
- Score < 5.5 OR Gate FAIL: NO_POSITION or AVOID
```

---

## Post-Mortem (For Follow-Up Analyses)
```
WHEN is_follow_up = true:

Link prior analysis file.

PREDICTION VS ACTUAL:
| Element | Predicted | Actual | Correct? |
|---------|-----------|--------|----------|
| Direction | | | Y/N |
| Key Metric | | | Y/N |
| EV Estimate | | | Y/N |
| Target Price | | | Y/N |

ERROR ANALYSIS:
What we got right:
-
What we got wrong:
-

BIASES THAT IMPACTED:
| Bias | How it manifested | Severity |
|------|-------------------|----------|

FRAMEWORK LESSON:
What generalizable lesson applies to future analyses?

GRADE: A/B/C/D/F
Rationale: ___
```

---

## Meta-Learning
```
AFTER EVERY ANALYSIS:

NEW RULE (if applicable):
- Rule: "When [condition], then [action]"
- Trigger: ___
- Applies to: All / Earnings / Technical / Sector-specific / This ticker
- Add to framework? Y/N
- Validation status: Pending / Validated / Rejected

DATA SOURCE EFFECTIVENESS:
| Source | Expected Weight | Actual Predictive | Adjust? |
|--------|-----------------|-------------------|---------|
| | | H/M/L | +/=/- |

PATTERN IDENTIFIED: ___

COMPARISON TO PAST:
How does this setup compare to similar analyses?

POST-ANALYSIS REVIEW DATE: {date}
```

---

## Quality Checklist

Before finalizing:
```
DATA QUALITY:
□ Price data verified
□ Data limitations documented

ANALYSIS:
□ Clear catalyst identified with reasoning
□ News age checked (priced in?)
□ Market environment assessed
□ Threat assessment (structural vs cyclical)
□ Technical levels mapped
□ Fundamentals verified (no red flags)
□ Sentiment assessed
□ Expectations assessed ("priced for perfection"?)
□ Four scenarios with probabilities summing to 100%

DECISION:
□ Bear case steel-manned
□ All biases checked
□ Do Nothing gate evaluated
□ Position size calculated (if applicable)
□ R:R ≥ 2:1 (if taking position)

OUTPUT:
□ Pass reasoning documented (if NO_POSITION)
□ Alternative strategies listed (if NO_POSITION)
□ Clear recommendation with confidence %
□ Summary box completed
□ Action items listed
□ Post-event review scheduled
```

---

## Template

See `template.yaml` for the output format (v2.3).

---

*Skill Version: 2.3*
*Updated: 2026-02-21*
