---
title: Visualize Analysis v1.4
tags:
  - trading-skill
  - visualization
  - utility
  - v1.4-required
custom_fields:
  skill_category: utility
  priority: secondary
  development_status: active
  version: "1.4"
  upstream_artifacts:
    - stock-analysis
    - earnings-analysis
  downstream_artifacts: []
  triggers:
    - "visualize analysis"
    - "create visualization"
    - "generate svg"
    - "visual dashboard"
  auto_invoke: false
---

# Visualize Analysis Skill v1.4

Generate professional SVG dashboard visualizations from v2.6 stock/earnings analysis YAML files.

## What's New in v1.4

- **Simplified workflow**: Two visualization types only (Stock-only, Combined)
- **Expanded stock visualization** (1200x1400): News & Data Quality, Fundamentals, Sentiment, Trade Plan, Alerts, Falsification, Rationale
- **Expanded combined visualization** (1200x1580): Full stock + earnings with Trade Plan, Falsification, Rationale, gate conflict warnings

## Visualization Types

| Condition | Visualization | Dimensions |
|-----------|---------------|------------|
| Stock analysis only | **Stock SVG** | 1200 x 1400 |
| Stock + Earnings analyses | **Combined SVG** | 1200 x 1580 |

## When to Use

- After completing a stock-analysis or earnings-analysis
- When reviewing an existing analysis
- When sharing analysis with others (visual format)
- User requests "visualize", "create SVG", or "dashboard"

## Workflow

### Step 1: Identify Analysis Files

```bash
ls -t tradegent_knowledge/knowledge/analysis/stock/{TICKER}_*.yaml | head -1
ls -t tradegent_knowledge/knowledge/analysis/earnings/{TICKER}_*.yaml | head -1
```

### Step 2: Generate Visualization

**Primary Method (Recommended)** - Auto-detects and routes correctly:
```bash
cd /opt/data/tradegent_swarm/tradegent && python scripts/visualize_combined.py TICKER
```
- If both stock and earnings exist → **Combined SVG** (1200x1580)
- If only stock exists → **Stock SVG** (1200x1400)
- Output: `analysis/combined/` or `analysis/stock/`

**Direct Stock Visualization** (when you have the file path):
```bash
cd /opt/data/tradegent_swarm/tradegent && python scripts/visualize_analysis.py <stock.yaml>
```

Options:
- `--output custom.svg` - Custom output path
- `--json` - Return result as JSON

### Step 3: Push SVG to Repository

```yaml
Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: tradegent-knowledge
  branch: main
  files:
    - path: knowledge/analysis/stock/{TICKER}_{TIMESTAMP}.svg
      content: [SVG content]
  message: "Add SVG visualization for {TICKER}"
```

### Step 4: Report Result

Report the generated SVG path to the user:
- File location
- Size in bytes
- Key metrics shown (recommendation, confidence, EV)

## SVG Dimensions

| Type | Dimensions | Content Rows |
|------|------------|--------------|
| **Stock Analysis** | 1200x1400 | 8 rows + footer |
| **Combined Analysis** | 1200x1580 | 9 rows + footer |

## Stock Analysis Layout (1200x1400)

| Row | Y | Content |
|-----|---|---------|
| Header | 0-100 | Ticker, company, version, date, recommendation badge |
| Row 1 | 120-280 | Price Box, Key Metrics, Gate Decision |
| Row 2 | 300-580 | Scenario Analysis (bars + pie chart), Comparable Companies |
| Row 3 | 600-740 | Threat Assessment, Case Strength, Alternative Actions |
| Row 4 | 760-860 | Liquidity, Confidence, Biases Detected, Next Steps |
| Row 5 | 880-980 | Pattern Identified, Data Source Effectiveness, Historical Comparison |
| Row 6 | 1000-1100 | News & Data Quality, Fundamentals Growth, Sentiment Details |
| Row 7 | 1120-1220 | Trade Plan/Pass Reasoning, Alert Levels, Falsification |
| Row 8 | 1240-1360 | Rationale Text Box |
| Footer | 1380-1400 | Source file reference, version, date |

## Combined Analysis Layout (1200x1580)

| Row | Y | Content |
|-----|---|---------|
| Header | 20-100 | Ticker, earnings countdown, dual recommendation badges |
| Columns | 120-440 | Stock Analysis (left) / Earnings Analysis (right) |
| Row 3 | 460-600 | Expectations, Historical Earnings Moves, Combined Recommendation |
| Row 4 | 620-780 | Stock Technicals, Comparable Companies, Consensus & Sentiment |
| Row 5 | 800-980 | Combined Analysis Summary with Decision Matrix |
| Row 6 | 1000-1140 | Stock Alternatives / Earnings Alternatives |
| Row 7 | 1160-1240 | Action Items (Stock and Earnings) |
| Row 8 | 1260-1360 | Trade Plan / Falsification (Stock and Earnings) |
| Row 9 | 1380-1460 | Combined Rationale |
| Footer | 1480-1560 | Source files, generation date, gate conflict warning |

## Output Sections

| Section | Content |
|---------|---------|
| **Header** | Ticker, company name, version, date, recommendation badge |
| **Price Box** | Current price, 52-week range bar, % from low |
| **Key Metrics** | Forward P/E (vs peers), Market Cap, YTD Return, Next Earnings |
| **Gate Decision** | Do Nothing Gate (PASS/FAIL), Open Trade Gate (PASS/FAIL), Criteria X/4 |
| **Scenario Analysis** | Bull/Base/Bear bars with probabilities + pie chart + EV |
| **Comparable Companies** | Table with subject row highlighted (yellow), 4 peers, median |
| **Threat Assessment** | Threat level badge (STRUCTURAL/ELEVATED/MODERATE), description, evidence |
| **Case Strength** | Bull/Base/Bear strength bars (0-10 scale) |
| **Alternative Actions** | Bullet list of 3 alternative strategies |
| **Liquidity** | Score X/10, ADV, spread |
| **Confidence** | Percentage with threshold indicator |
| **Biases Detected** | List with risk levels (HIGH=red, MEDIUM=yellow) |
| **News & Data Quality** | Fresh catalyst indicator, news items, data limitations |
| **Fundamentals** | Revenue growth YoY, EPS growth YoY, Gross/Operating margins |
| **Sentiment Details** | Analyst ratings (B/H/S), short interest, put/call ratio, unusual activity |
| **Trade Plan** | Entry price, stop loss, targets, position size (or Pass Reasoning) |
| **Alert Levels** | Price alerts with actions, event alerts |
| **Falsification** | Thesis invalid conditions, bull wrong conditions |
| **Rationale** | Full rationale text box, watchlist trigger |
| **Footer** | Source filename (left), Tradegent version + date (right) |

## Source Reference

Every SVG includes a reference to its source YAML file:

1. **XML Comment Header**: Full path, document ID, generation date
2. **Footer Left**: Source filename (e.g., `DOCU_20260222T1730.yaml`)
3. **Footer Right**: Version and date

## Examples

```bash
# Auto-detect and generate appropriate visualization (RECOMMENDED)
python scripts/visualize_combined.py NVDA

# With explicit files
python scripts/visualize_combined.py --stock stock.yaml --earnings earnings.yaml

# Direct stock visualization
python scripts/visualize_analysis.py ../tradegent_knowledge/knowledge/analysis/stock/DOCU_20260222T1730.yaml

# Custom output path
python scripts/visualize_combined.py NVDA --output /tmp/nvda_combined.svg

# JSON output for programmatic use
python scripts/visualize_combined.py NVDA --json
```

## Supported Formats

| Input | Output |
|-------|--------|
| Stock Analysis only | Stock SVG (1200x1400) |
| Stock + Earnings | Combined SVG (1200x1580) |

Note: v2.6 stock analysis and v2.4+ earnings analysis required for full functionality.

## Execution

When invoked, run the visualization script on the specified analysis file, push to repository, and report the result.
