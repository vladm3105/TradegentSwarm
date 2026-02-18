# Strategies

## Purpose
Documents complete trading strategies with entry/exit rules, position sizing, and performance tracking. Your edge, codified.

## What Belongs Here
- Fully defined trading strategies
- Entry and exit criteria
- Position sizing rules
- Risk management parameters
- Historical performance metrics
- Strategy variations

## File Naming Convention
```
{strategy-name}.yaml
```
Example: `earnings-momentum.yaml`

## How to Use

### Defining a Strategy
1. Create strategy YAML with clear structure
2. Define clear entry criteria (specific, measurable)
3. Define exit rules (target, stop, time)
4. Set position sizing guidelines
5. Document edge hypothesis
6. Track performance over time

### Strategy Components

| Component | Description |
|-----------|-------------|
| thesis | Why this strategy works (your edge) |
| universe | What stocks/instruments qualify |
| entry_rules | Specific criteria to enter |
| exit_rules | Target, stop, time-based exits |
| position_sizing | How much to risk per trade |
| filters | Quality/liquidity requirements |
| performance | Win rate, avg win/loss, expectancy |

## Integration
- Fed by: `learnings/` (insights become rules), `research/` (macro overlay)
- Executed via: `scanners/` (find candidates), `analysis/` (evaluate)
- Tracked in: `trades/` (actual execution)

## Example Strategies

### Earnings Momentum
- Enter 5-7 days before earnings
- Require beat streak ≥4 and bullish customer demand
- Exit morning of earnings or hold through
- Size: 2-6% based on conviction

### Oversold Bounce
- Enter quality stocks at RSI <25
- Require fundamental support (no value traps)
- Target: 20-day MA
- Stop: Below recent low

### Breakout Follow
- Enter on 52-week high breakout with volume
- Require sector confirmation
- Trail stop at 20-day MA
- Let winners run

## Performance Tracking
Track for each strategy:
- Number of trades
- Win rate
- Average winner / Average loser
- Profit factor
- Max drawdown
- Expectancy per trade

## Review Cadence
- Monthly: Performance review
- Quarterly: Strategy refinement
- Annually: Major overhaul or retirement
