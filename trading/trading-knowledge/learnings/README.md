# Learnings

## Purpose
Captures trading lessons, bias patterns, and signals discovered through experience. The accumulated wisdom from wins and losses.

## What Belongs Here
- Cognitive biases identified in your trading
- Pattern recognition insights
- Market signals that work (or don't)
- Rules derived from experience
- Mistakes to avoid

## Folder Structure
```
learnings/
├── biases/       ← Cognitive biases affecting decisions
├── signals/      ← Market signals and their reliability
├── patterns/     ← Price/volume patterns observed
└── rules/        ← Trading rules derived from experience
```

## File Naming Convention
```
{category}/{descriptive-name}.yaml
```
Examples:
- `biases/loss-aversion-pre-earnings.yaml`
- `signals/vix-spike-reversal.yaml`
- `patterns/gap-fill-probability.yaml`
- `rules/position-sizing-by-conviction.yaml`

## How to Use

### Documenting a Learning
1. Create YAML with consistent structure
2. Describe the insight clearly
3. Provide specific examples (link to trades)
4. Define actionable rules
5. Track effectiveness over time

### Categories

| Category | What to Document |
|----------|------------------|
| biases | Psychological patterns that hurt performance |
| signals | Market indicators and their predictive value |
| patterns | Recurring price/volume behaviors |
| rules | Concrete rules derived from experience |

## Integration
- Fed by: `reviews/` (post-trade reviews surface learnings)
- Updates: `strategies/` (learnings refine strategies)
- Informs: Future `earnings/` and `analysis/` documents

## Review Cadence
- After each losing trade: What bias was present?
- Weekly: Any new patterns observed?
- Monthly: Which learnings are proving valuable?
- Quarterly: Update or retire stale learnings

## Example Learnings
- "I tend to size too large when I'm confident" → Bias
- "VIX >30 reversals have 70% success rate" → Signal
- "Gaps >5% fill within 5 days 60% of time" → Pattern
- "Never enter full size before earnings" → Rule
