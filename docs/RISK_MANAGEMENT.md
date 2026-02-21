# Risk Management

Position sizing, stop-loss rules, and portfolio hedging strategies for the Tradegent platform.

## Overview

Risk management in Tradegent operates at three levels:

```
┌─────────────────────────────────────────────────────────────┐
│                    RISK MANAGEMENT LAYERS                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Level 1: POSITION LEVEL                                     │
│  • Stop loss per trade                                       │
│  • Position sizing by conviction                             │
│  • Max single position limit                                 │
│                                                              │
│  Level 2: PORTFOLIO LEVEL                                    │
│  • Total portfolio heat                                      │
│  • Sector concentration                                      │
│  • Correlation management                                    │
│                                                              │
│  Level 3: SYSTEM LEVEL                                       │
│  • Trading mode gates                                        │
│  • Do Nothing gate                                           │
│  • Pre-exit gate                                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Position Sizing

### Risk-Based Position Sizing

Position size is calculated based on maximum acceptable loss per trade:

```
Position Size = Dollar Risk / (Entry - Stop)

Where:
  Dollar Risk = Portfolio Value × Risk Percentage
  Risk Percentage = 1-2% per trade (depends on conviction)
```

### Example Calculation

```
Portfolio Value:  $100,000
Risk Percentage:  1.5%
Dollar Risk:      $1,500

Entry Price:      $150
Stop Loss:        $142
Risk Per Share:   $8

Position Size:    $1,500 / $8 = 187 shares
Position Value:   187 × $150 = $28,050
Position %:       28%
```

### Position Sizing by Conviction

| Confidence Level | Risk % | Max Position % | Structure |
|------------------|--------|----------------|-----------|
| High (>70%) | 2.0% | 6% of portfolio | Full position |
| Medium (55-70%) | 1.5% | 4% of portfolio | Reduced size or spreads |
| Low (<55%) | 1.0% | 2% of portfolio | Small speculative or no position |

### Maximum Position Limits

| Limit Type | Value | Rationale |
|------------|-------|-----------|
| **Single Position** | 20% | Diversification |
| **Sector Concentration** | 40% | Sector risk |
| **Earnings Exposure** | 6% | Event risk |
| **New Position** | 5% | Start small |

---

## Stop Loss Rules

### Stop Loss Types

| Type | Description | Use Case |
|------|-------------|----------|
| **Hard Stop** | Automatic order placed | High volatility, overnight |
| **Mental Stop** | Manual exit at level | Intraday, liquid stocks |
| **Trailing Stop** | Moves with price | Momentum trades |
| **Time Stop** | Exit after X days | Catalyst trades |

### Stop Loss Placement

```
Technical Stop:
  Long:  Below key support level
  Short: Above key resistance level
  Buffer: Add 0.5-1% for noise

ATR-Based Stop:
  Stop Distance = ATR × Multiplier
  Multiplier: 1.5-3.0 (depends on volatility)

Percentage Stop:
  Standard: 5-8% from entry
  Tight: 2-3% (high conviction, tight setup)
  Wide: 10-15% (volatile stocks, longer timeframe)
```

### Stop Loss Rules

1. **Set before entry** - Never enter without knowing stop
2. **Never widen** - Only tighten stops, never widen
3. **Honor the stop** - No exceptions for hard stops
4. **Document reason** - Record why stop was placed at level

### Maximum Loss Limits

| Limit | Value | Action |
|-------|-------|--------|
| **Per Trade** | 2% of portfolio | Exit immediately |
| **Daily** | 5% of portfolio | Stop trading for day |
| **Weekly** | 10% of portfolio | Review and reduce size |
| **Monthly** | 15% of portfolio | Pause, full review |

---

## Portfolio Heat

Portfolio heat measures total risk across all positions:

```
Portfolio Heat = Sum of (Position Risk %)

Where Position Risk % = (Entry - Stop) / Entry × Position %
```

### Heat Limits

| Heat Level | Range | Action |
|------------|-------|--------|
| **Low** | 0-5% | Normal, can add positions |
| **Medium** | 5-10% | Caution, selective adds |
| **High** | 10-15% | No new positions |
| **Critical** | >15% | Reduce exposure |

### Example Heat Calculation

```
Position 1: NVDA
  Entry: $150, Stop: $142, Size: 5%
  Risk %: (150-142)/150 × 5% = 0.27%

Position 2: AMD
  Entry: $130, Stop: $118, Size: 4%
  Risk %: (130-118)/130 × 4% = 0.37%

Position 3: MSFT
  Entry: $400, Stop: $380, Size: 6%
  Risk %: (400-380)/400 × 6% = 0.30%

Total Portfolio Heat: 0.27% + 0.37% + 0.30% = 0.94%
```

---

## System-Level Gates

### Do Nothing Gate

Every analysis must pass this gate before position entry:

| Criteria | Threshold | Rationale |
|----------|-----------|-----------|
| **Expected Value** | >5% | Sufficient edge |
| **Confidence** | >60% | Conviction required |
| **Risk:Reward** | >2:1 | Asymmetric payoff |
| **Edge Not Priced** | Yes | Information advantage |

**Gate Result:**
- **PASS (4/4)**: Proceed with position
- **FAIL (<4/4)**: No position or WATCH only

### Pre-Exit Gate (Loss Aversion Check)

Before exiting profitable positions:

```
IF position is profitable AND considering exit:
  □ Is thesis still intact? Y/N
  □ Is catalyst still pending? Y/N
  □ Am I exiting due to FEAR or LOGIC?

IF thesis_intact AND catalyst_pending AND reason=FEAR:
  → GATE RESULT: HOLD
  → "The catalyst justified entry; don't exit before it arrives"
  → Minimum: Hold 50% through catalyst
```

### Trading Mode Gates

| Mode | dry_run_mode | auto_execute | stock_state | Behavior |
|------|--------------|--------------|-------------|----------|
| **Off** | true | any | any | Log only, no actions |
| **Analysis** | false | false | analysis | Reports only |
| **Paper** | false | true | paper | Paper trades |
| **Live** | false | true | live | **BLOCKED** (not implemented) |

---

## Bias Countermeasures

### Common Biases and Mitigations

| Bias | Detection | Mitigation |
|------|-----------|------------|
| **Loss Aversion** | Exiting winners early due to fear | Pre-exit gate |
| **Confirmation** | Ignoring contrary evidence | Steel-man bear case |
| **Recency** | Overweighting recent data | Check 8+ quarters |
| **Overconfidence** | Extreme probabilities (>80%) | Calibration check |
| **Anchoring** | Fixed on entry price | Focus on thesis validity |
| **FOMO** | Chasing after move | Wait for pullback |

### Countermeasure Framework

For each detected bias, document:

```yaml
bias_type: loss_aversion
rule: "IF profitable AND thesis intact AND catalyst pending → Hold 50%"
implementation: "Add pre-exit gate check to trade-journal exit step"
checklist_addition: "Complete pre-exit gate before any profitable exit"
mantra: "The catalyst justified entry; don't exit before it arrives"
```

---

## Correlation Management

### Correlation Limits

| Correlation | Limit | Example |
|-------------|-------|---------|
| **Same Sector** | Max 3 positions | No more than 3 tech stocks |
| **Same Theme** | Max 40% exposure | AI theme capped at 40% |
| **Same Catalyst** | Max 2 positions | Max 2 earnings plays same week |

### Correlation Check

Before adding position, verify:

```
□ Different sector from largest positions?
□ Different primary catalyst?
□ Not adding to already heavy theme exposure?
□ Beta-weighted exposure acceptable?
```

---

## Hedge Strategies

### Portfolio Hedges

| Hedge | Use Case | Structure |
|-------|----------|-----------|
| **SPY Puts** | Broad market hedge | 2-5% OTM, 30-60 DTE |
| **VIX Calls** | Volatility hedge | 20-25 strike, 30-45 DTE |
| **Sector Shorts** | Sector hedge | Short ETF of overweight sector |

### Position Hedges

| Hedge | Use Case | Structure |
|-------|----------|-----------|
| **Protective Put** | Downside protection | ATM or 5% OTM |
| **Collar** | Capped risk/reward | Sell call, buy put |
| **Pairs Trade** | Relative value | Long A, short B same sector |

### When to Hedge

| Condition | Action |
|-----------|--------|
| Portfolio >75% long | Consider SPY puts |
| Single position >10% | Consider protective put |
| Ahead of major event | Reduce size or buy protection |
| VIX <15 | Cheap insurance opportunity |

---

## Risk Checklists

### Pre-Trade Checklist

```
BEFORE ENTRY:
□ Analysis completed with PASS on Do Nothing gate
□ Position size calculated using risk formula
□ Stop loss defined with specific price
□ Maximum loss in dollars acceptable
□ Portfolio heat stays within limits
□ Correlation check passed
□ Bias check completed
```

### Daily Risk Review

```
EVERY TRADING DAY:
□ Calculate current portfolio heat
□ Verify all stops in place
□ Check for new earnings/catalysts
□ Review positions approaching stops
□ Check correlation to market
□ Note any bias triggers
```

### Weekly Risk Review

```
EVERY WEEK:
□ Calculate weekly P&L
□ Review losing trades for lessons
□ Update bias tracking
□ Check sector concentration
□ Review hedge positions
□ Adjust position sizes if needed
```

---

## Quick Reference

### Position Sizing Formula

```
Shares = (Portfolio × Risk%) / (Entry - Stop)
Max Position = 20% of portfolio
Max Risk = 2% per trade
```

### Stop Loss Guidelines

```
Technical: Below support with 0.5-1% buffer
ATR-based: 1.5-3.0 × ATR
Percentage: 5-8% standard
```

### Portfolio Heat

```
Low: <5% (add positions)
Medium: 5-10% (selective adds)
High: 10-15% (no new positions)
Critical: >15% (reduce exposure)
```

### Key Rules

1. **Never risk more than 2% on a single trade**
2. **Never widen a stop loss**
3. **Always know your exit before entry**
4. **Pass the Do Nothing gate before entry**
5. **Complete pre-exit gate for profitable positions**
6. **Keep total portfolio heat below 15%**
