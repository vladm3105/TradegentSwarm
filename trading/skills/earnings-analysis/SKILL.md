# Earnings Analysis Skill v2.3

## Purpose
Systematic multi-phase analysis of stocks before earnings announcements. Enhanced with reasoning sections, bias checks, and decision gates.

## When to Use
- 3-10 days before earnings announcement
- Scanner identifies high-potential earnings setup
- Manual review of upcoming earnings
- Follow-up analysis (post-mortem)

## Required Inputs
- Ticker symbol
- Earnings date and time (BMO/AMC)
- Current stock price (verify data quality)
- Consensus EPS and revenue estimates

## Output
- File: `{TICKER}_{YYYYMMDDTHHMM}.yaml`
- Location: `knowledge/analysis/earnings/`

---

## Framework Overview (14 Phases)

```
Phase 0.5: Data Quality Check        → Verify data reliability
Phase 1:   Preparation               → Historical data gathering
Phase 1.5: Historical Moves Analysis → Past earnings reactions
Phase 2:   Customer Demand Signals   → 50% weight factor
Phase 2.5: News Age Check            → Is news priced in?
Phase 3:   Technical Setup           → Price action context
Phase 3.5: Threat Assessment         → Structural vs cyclical
Phase 4:   Sentiment Analysis        → Market psychology
Phase 4.5: Expectations Assessment   → Priced for perfection?
Phase 5:   Scenario Analysis         → 4-scenario framework
Phase 6:   Steel-Man Bear Case       → Counter-arguments
Phase 7:   Bias Check                → Self-assessment
Phase 8:   Do Nothing Gate           → Go/No-Go decision
Phase 8.5: Pass Reasoning            → Document why passing
Phase 9:   Alternative Strategies    → Options when NO_POSITION
Phase 10:  Execution Plan            → Trade details
Phase 11:  Summary & Action Items    → Quick reference
```

---

## Phase 0.5: Data Quality Check (NEW)
```
VERIFY DATA QUALITY BEFORE ANALYSIS:

□ Price data source: IB Gateway / Yahoo / Manual / Delayed
□ Price data fresh? (< 1 hour old)
□ Earnings date confirmed?
□ Consensus estimates from reliable source?

IF data issues exist:
  → Flag with ⚠️ warning
  → Note requires_reverification = true
  → Document limitations and impact

Example warning:
"⚠️ DATA LIMITATION: IB Gateway offline - verify prices before trading"
```

---

## Phase 1: Preparation
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

---

## Phase 1.5: Historical Moves Analysis (NEW)
```
BUILD HISTORICAL MOVES TABLE:

| Quarter | Date | EPS Surprise | Rev Surprise | Move % | Beat/Miss |
|---------|------|--------------|--------------|--------|-----------|
| Q4 2025 | | | | | |
| Q3 2025 | | | | | |
| Q2 2025 | | | | | |
| Q1 2025 | | | | | |

CALCULATE AVERAGES:
- Average move (all quarters): ___%
- Average beat move: ___%
- Average miss move: ___%

COMPARE TO CURRENT IMPLIED:
- Current implied move: ___%
- Implied vs Historical: Above / Inline / Below

ASSESSMENT:
□ Is market pricing more volatility than historical?
  → If YES: Selling premium may have edge
  → If NO: Buying options may be cheaper than historical

WRITE implied_move_assessment explaining the comparison.
```

---

## Phase 2: Customer Demand Signals
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

DOCUMENT each signal with:
- Source
- Signal description
- Interpretation (bullish/bearish/neutral)
- Weight (importance)
```

---

## Phase 2.5: News Age Check (NEW)
```
ASSESS IF NEWS IS PRICED IN:

FOR EACH relevant news item:
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
  → This may be "priced in" situation
```

---

## Phase 3: Technical Setup
```
ANALYZE:
□ Trend structure
  - Price vs 20-day MA
  - Price vs 50-day MA
  - Price vs 200-day MA
  - MA alignment (bullish: 20>50>200)

□ Momentum
  - RSI level (overbought/neutral/oversold)
  - MACD signal
  - Recent price action (consolidating, trending, overextended)

□ Key levels
  - Nearest support
  - Nearest resistance
  - All-time high proximity
  - 52-week low proximity

□ Volume
  - Recent volume vs average
  - Volume trend

□ Pre-earnings positioning
  - Already run up? (priced in risk)
  - Run-up percentage: ___%
  - Pulled back? (opportunity)

TECHNICAL SCORE: 1-10

WRITE technical_summary explaining setup quality.
```

---

## Phase 3.5: Threat Assessment (NEW)
```
CLASSIFY THE PRIMARY THREAT:

STRUCTURAL vs CYCLICAL FRAMEWORK:

STRUCTURAL THREAT (Business model at risk):
□ Moat erosion evidence?
□ Competitive disruption?
□ Secular decline in end market?
□ Regulatory existential risk?

If structural threat exists:
  - Beat streak IRRELEVANT
  - Management credibility suspect
  - Value trap risk HIGH
  - Even a beat may not save stock

CYCLICAL WEAKNESS (Temporary downturn):
□ Industry-wide slowdown?
□ Macro-driven demand dip?
□ Temporary execution issues?
□ Recovery catalysts visible?

If cyclical weakness:
  - Beat streak RELEVANT
  - History is valid guide
  - Recovery timeline estimable
  - Miss may be buying opportunity

WRITE threat_summary:
"This is [STRUCTURAL/CYCLICAL/NONE] because..."
```

---

## Phase 4: Sentiment Analysis
```
GATHER:
□ Analyst ratings
  - Buy/Hold/Sell distribution
  - Recent changes (upgrades/downgrades)
  - Price target range (avg, high, low)

□ Short interest
  - % of float
  - Days to cover
  - Recent changes
  - Squeeze potential?

□ Options positioning
  - Put/call ratio
  - IV percentile
  - Unusual activity (bullish/bearish)

□ Institutional
  - Ownership %
  - Recent 13F changes

□ News sentiment
  - Recent headlines
  - Tone (positive/negative/neutral)

CROWDED TRADE CHECK:
□ Is everyone on the same side?
□ Consensus direction?
□ Contrarian opportunity?

ASSESS CONTRARIAN OPPORTUNITY:
- If everyone bullish → Downside risk from high expectations
- If everyone bearish → Upside potential from low bar
- If mixed → Neutral

SENTIMENT SCORE: 1-10
```

---

## Phase 4.5: Expectations Assessment (NEW)
```
"PRICED FOR PERFECTION" CHECK:

□ Near ATH? (within 10%)
  - If yes: Limited upside even on beat
  - ATH distance: ___%

□ Beat streak length?
  - If >6 consecutive beats: "Priced for perfection" risk
  - Market EXPECTS beats, surprise is asymmetric

□ Analyst targets already reached?
  - If current price near avg target: Where does upside come from?

□ Crowded bullish consensus?
  - If >80% buy ratings: Disappointment risk elevated

SELL THE NEWS RISK:
- Low: Stock beaten down, low expectations
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

## Phase 5: Scenario Analysis (4 Scenarios)
```
DEFINE FOUR SCENARIOS:

STRONG BEAT:
- Probability: ___%
- What happens: EPS >5% above consensus, strong guidance
- Expected move: +___%
- Key driver: [what makes this happen]

MODEST BEAT:
- Probability: ___%
- What happens: EPS 1-5% above consensus, in-line guidance
- Expected move: +___%
- Key driver: [likely path]

MODEST MISS:
- Probability: ___%
- What happens: EPS 1-5% below consensus
- Expected move: -___%
- Key driver: [what goes wrong]

STRONG MISS:
- Probability: ___%
- What happens: EPS >5% below consensus, cut guidance
- Expected move: -___%
- Key driver: [worst case]

PROBABILITIES MUST SUM TO 100%

Expected Value Calculation:
EV = (P_sb × M_sb) + (P_mb × M_mb) + (P_mm × M_mm) + (P_sm × M_sm)

Write out the calculation explicitly.

COMPARE EV TO IMPLIED MOVE:
- If |EV| > Implied move: Directional edge exists
- If |EV| < Implied move: Consider volatility plays
```

---

## Phase 6: Steel-Man Bear Case (NEW)
```
ARGUE THE BEAR CASE HONESTLY:

For each bear argument:
| # | Argument | Evidence | Counter | Strength |
|---|----------|----------|---------|----------|
| 1 | | | | 1-10 |
| 2 | | | | 1-10 |
| 3 | | | | 1-10 |

BEAR CASE STRENGTH (overall): 1-10

WRITE BEAR CASE SUMMARY:
What could cause a miss? Be specific:
- Customer demand weakness?
- Guidance disappointment?
- Margin pressure?
- One-time charges?
- Competition taking share?

When would bears be right?
```

---

## Phase 7: Bias Check (Enhanced)
```
MANDATORY BIAS ASSESSMENT:

For each bias:
| Bias | Detected | Severity | Notes | Mitigation |
|------|----------|----------|-------|------------|
| Recency | Y/N | H/M/L | | |
| Confirmation | Y/N | H/M/L | | |
| Overconfidence | Y/N | H/M/L | | |
| Anchoring | Y/N | H/M/L | | |
| FOMO | Y/N | H/M/L | | |
| Timing Conservatism | Y/N | H/M/L | | |
| Loss Aversion | Y/N | H/M/L | | |

SPECIAL CHECKS:

RECENCY BIAS:
□ Am I overweighting the last 1-2 quarters?
□ Have I checked all 8 quarters?

CONFIRMATION BIAS:
□ Did I search for contrary evidence?
□ What's the strongest bear case?

OVERCONFIDENCE:
□ Is my probability too extreme (>80% or <20%)?
□ What could I be missing?

TIMING CONSERVATISM:
"Weakness + strong fundamentals = ENTRY SIGNAL, not warning"
□ Am I treating weakness as warning when it's opportunity?

LOSS AVERSION (for exits):
□ If position profitable, am I exiting due to FEAR or LOGIC?
□ Pre-exit gate: thesis_intact AND catalyst_pending = HOLD

FINAL CHECK:
□ Both sides argued equally? Y/N
□ Would I feel comfortable defending the opposite position?

IF ANY BIAS DETECTED:
- Document it
- Describe correction applied
- Consider reducing position size

WRITE corrections_applied explaining adjustments.
```

---

## Phase 8: Do Nothing Gate (Enhanced)
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

ADDITIONAL GATES:
- If IV >80th percentile → Consider spreads only
- If position would exceed 6% → Reduce size
- If no clear customer demand signal → DO NOT TRADE

IF FAIL:
→ Recommendation = NEUTRAL or NO_POSITION
→ Document reasoning in gate_reasoning
→ Proceed to Phase 8.5 (Pass Reasoning)
→ Proceed to Phase 9 (Alternative Strategies)

POSITION SIZING BY CONFIDENCE:

| Confidence | Position Size |
|------------|---------------|
| >70% | 4-6% of portfolio |
| 55-70% | 2-4% of portfolio |
| <55% | No position |
```

---

## Phase 8.5: Pass Reasoning (NEW)
```
WHEN NOT TAKING POSITION (NEUTRAL):

Document why passing:

PRIMARY REASON: ___

ALL REASONS:
| # | Reason | Impact |
|---|--------|--------|
| 1 | | H/M/L |
| 2 | | H/M/L |
| 3 | | H/M/L |

WRITE SUMMARY:
"Passing on this earnings play because..."

BETTER OPPORTUNITIES:
□ Do better earnings plays exist this week?
□ Opportunity cost of capital tied up here?

LEARNING VALUE:
Even when passing, document the lesson.
```

---

## Phase 9: Alternative Strategies (NEW)
```
WHEN RECOMMENDATION IS NEUTRAL/NO_POSITION:

Consider these alternatives:

ALTERNATIVE 1: Wait for Post-Earnings Pullback
- Trigger: "Stock drops >X% post-earnings"
- Entry zone: $___
- Rationale: "Better entry if thesis intact"

ALTERNATIVE 2: Volatility Play (Iron Condor)
- Structure: Sell OTM call spread + put spread
- Condition: "If IV elevated vs expected move"
- Rationale: "Capture IV crush"

ALTERNATIVE 3: Post-Earnings Drift Play
- Trigger: "Wait for earnings, trade the drift"
- Entry: "Morning after, if direction confirmed"
- Rationale: "Let earnings reveal direction"

BEST ALTERNATIVE: ___
WHY: ___

SET ALERTS for alternative triggers.
```

---

## Phase 10: Execution Plan
```
IF TRADING:

Entry:
  - Price: [specific or "at market"]
  - Date: [when]
  - Size: [shares or contracts]
  - % of portfolio: [X%]

Structure:
  - Stock / Calls / Puts / Spreads / Straddle
  - Strike(s): [if options]
  - Expiration: [if options]
  - Max risk: $___
  - Max reward: $___
  - Breakeven: $___

Position Sizing:
  - Max portfolio %: ___
  - Account risk %: ___
  - Dollar risk: $___

Stop Loss:
  - Price: $___
  - Type: Hard / Mental / Time
  - Distance: ___%

Profit Target:
  - Target 1: [price] - sell [X%]
  - Target 2: [price] - sell [X%]
  - Or: "Hold through earnings"

Contingency:
  - If gaps against: [action]
  - If gaps for: [action]
  - If flat: [action]

LOSS AVERSION PRE-EXIT CHECK (v2.3):
When profitable before earnings:
□ Is thesis still intact?
□ Is earnings catalyst still pending?
□ Am I exiting due to LOGIC or FEAR?

→ If thesis_intact AND catalyst_pending AND reason=FEAR:
  "The catalyst justified entry; don't exit before it arrives"
  → HOLD minimum 50% through catalyst

Post-Earnings Plan:
  - Review within 24 hours
  - Update thesis with actual results
  - Trigger post-trade review
```

---

## Phase 11: Summary & Action Items
```
CREATE SUMMARY BOX:

═══════════════════════════════════════════════════════════════
{TICKER} EARNINGS ANALYSIS
Date: {date} | Earnings: {date} {time} | Days: {days}
═══════════════════════════════════════════════════════════════

BEAT HISTORY: {beats}/{total} ({rate}%)

HISTORICAL MOVES:
- Avg move: {avg}%
- Avg beat move: {beat}%
- Avg miss move: {miss}%
- Current implied: {implied}%

PROBABILITY ASSESSMENT:
- Strong Beat: {pct}% → {move}%
- Modest Beat: {pct}% → {move}%
- Modest Miss: {pct}% → {move}%
- Strong Miss: {pct}% → {move}%
Expected Value: {ev}%

RECOMMENDATION: {recommendation} ({confidence}% confidence)

"DO NOTHING" GATE: {result} ({n}/4 criteria)

POSITION: {position_detail}

ALTERNATIVE ACTIONS (if NEUTRAL):
1. {alternative_1}
2. {alternative_2}
3. {alternative_3}

FALSIFICATION: {criteria}

BIASES CHECKED:
- [x] Recency bias
- [x] Confirmation bias
- [x] Overconfidence
- [x] Both sides argued

POST-EARNINGS REVIEW: {date}
═══════════════════════════════════════════════════════════════

ACTION ITEMS:
□ Immediate: ___
□ Pre-earnings: ___
□ Earnings day: ___
□ Post-earnings: ___
```

---

## Post-Mortem (For Follow-Up Analyses)
```
WHEN is_follow_up = true:

Link prior analysis file.

PREDICTION VS ACTUAL:
| Element | Predicted | Actual | Correct? |
|---------|-----------|--------|----------|
| Beat/Miss | | | Y/N |
| Move magnitude | | | Y/N |
| Key metric | | | Y/N |

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
- Applies to: All / Earnings / This ticker
- Add to framework? Y/N
- Validation status: Pending / Validated / Rejected

DATA SOURCE EFFECTIVENESS:
| Source | Expected Weight | Actual Predictive | Adjust? |
|--------|-----------------|-------------------|---------|
| | | H/M/L | +/=/- |

POST-ANALYSIS REVIEW DATE: {date}
```

---

## Quality Checklist

Before finalizing:
```
DATA QUALITY:
□ Price data verified
□ Earnings date confirmed
□ Estimates from reliable source

ANALYSIS:
□ Historical moves analyzed
□ Customer demand thoroughly researched (50% weight)
□ News age checked (priced in?)
□ Threat assessment (structural vs cyclical)
□ Technical setup scored
□ Sentiment assessed
□ Expectations assessment completed
□ Four scenarios with probabilities summing to 100%

DECISION:
□ Bear case steel-manned
□ All biases checked
□ Do Nothing gate evaluated
□ Probabilities reasonable (not extreme)

OUTPUT:
□ Pass reasoning documented (if NEUTRAL)
□ Alternative strategies listed (if not trading)
□ Clear recommendation with confidence %
□ Execution plan specific (if trading)
□ Summary box completed
□ Action items listed
□ Post-earnings review scheduled
```

---

## Template

See `template.yaml` for the output format (v2.3).

---

*Skill Version: 2.3*
*Updated: 2026-02-21*
