---
title: Visualize Analysis v1.2
tags:
  - trading-skill
  - visualization
  - utility
  - v1.2-required
custom_fields:
  skill_category: utility
  priority: secondary
  development_status: active
  version: "1.2"
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

# Visualize Analysis Skill v1.2

Generate professional SVG dashboard visualizations from v2.6 stock/earnings analysis YAML files.

## When to Use

- After completing a stock-analysis or earnings-analysis
- When reviewing an existing analysis
- When sharing analysis with others (visual format)
- User requests "visualize", "create SVG", or "dashboard"

## Workflow

### Step 1: Identify Analysis File

If ticker provided, find the latest analysis:

```bash
ls -t tradegent_knowledge/knowledge/analysis/stock/{TICKER}_*.yaml | head -1
ls -t tradegent_knowledge/knowledge/analysis/earnings/{TICKER}_*.yaml | head -1
```

If file path provided directly, use that.

### Step 2: Generate Visualization

**For Stock Analysis** (files in `analysis/stock/`):
```bash
cd /opt/data/tradegent_swarm/tradegent && python scripts/visualize_analysis.py <analysis.yaml>
```

**For Earnings Analysis** (files in `analysis/earnings/`):
```bash
cd /opt/data/tradegent_swarm/tradegent && python scripts/visualize_earnings.py <analysis.yaml>
```

Options:
- `--output custom.svg` - Custom output path
- `--json` - Return result as JSON

**Auto-detect**: Check file path to determine which script to use:
- Path contains `/earnings/` → use `visualize_earnings.py`
- Path contains `/stock/` → use `visualize_analysis.py`

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

## SVG Layout (5 Rows, 1200x1020)

| Row | Y | Content |
|-----|---|---------|
| Header | 0-100 | Ticker, company, version, date, recommendation badge |
| Row 1 | 120-280 | Price Box, Key Metrics, Gate Decision |
| Row 2 | 300-580 | Scenario Analysis (bars + pie chart), Comparable Companies |
| Row 3 | 600-740 | Threat Assessment, Case Strength, Alternative Actions |
| Row 4 | 760-860 | Liquidity, Confidence, Biases Detected, Next Steps |
| Row 5 | 880-980 | Pattern Identified, Data Source Effectiveness, Historical Comparison |
| Footer | 1000-1020 | Source file reference, version, date |

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
| **Next Steps** | Review date, immediate action items |
| **Pattern Identified** | Pattern name (blue), comparison summary |
| **Data Source Effectiveness** | Sources with predictive ratings (green=high, yellow=medium) |
| **Historical Comparison** | Word-wrapped comparison to past situations |
| **Footer** | Source filename (left), Tradegent version + date (right) |

## Source Reference

Every SVG includes a reference to its source YAML file:

1. **XML Comment Header**: Full path, document ID, generation date
2. **Footer Left**: Source filename (e.g., `DOCU_20260222T1730.yaml`)
3. **Footer Right**: Version and date

## Template Reference

See `tradegent_knowledge/skills/stock-analysis/svg-template.md` for:
- Complete layout specification
- Color palette
- Pie chart calculation
- Section coordinates

## Examples

```bash
# Stock analysis visualization
python scripts/visualize_analysis.py ../tradegent_knowledge/knowledge/analysis/stock/DOCU_20260222T1730.yaml

# Earnings analysis visualization
python scripts/visualize_earnings.py ../tradegent_knowledge/knowledge/analysis/earnings/NVDA_20260224T1430.yaml

# Custom output path
python scripts/visualize_analysis.py ../tradegent_knowledge/knowledge/analysis/stock/NVDA_20260220T0900.yaml --output /tmp/nvda_dashboard.svg

# JSON output for programmatic use
python scripts/visualize_earnings.py ../tradegent_knowledge/knowledge/analysis/earnings/CRM_20260224T1200.yaml --json
```

## Supported Formats

| Input | Output |
|-------|--------|
| v2.6 Stock Analysis YAML | SVG Dashboard (1200x1020) |
| v2.6 Earnings Analysis YAML | SVG Dashboard (1200x1020) |

Note: Earlier versions (v2.4, v2.5) will generate warnings but may still work with reduced functionality.

## Execution

When invoked, run the visualization script on the specified analysis file, push to repository, and report the result.
