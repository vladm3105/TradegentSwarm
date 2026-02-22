# Analysis Workflow

Step-by-step guide to running stock and earnings analyses.

---

## Overview

```
┌───────────────────────────────────────────────────────────────────┐
│                      Analysis Pipeline                            │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. TRIGGER          2. CONTEXT         3. EXECUTE               │
│  ───────────         ─────────          ─────────                │
│  Manual CLI          RAG Search         Skill Phases              │
│  or Service          Graph Query        IB Data                   │
│                      IB Quotes          Brave Search              │
│                                                                   │
│  4. GATE             5. SAVE            6. INDEX                  │
│  ────────            ────────           ─────────                │
│  EV > 5%?            YAML File          Graph Extract             │
│  Conf > 60%?         analyses/          RAG Embed                 │
│  R:R > 2:1?                             GitHub Push               │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

1. Docker services running:
   ```bash
   cd tradegent && docker compose ps
   ```

2. IB MCP server running:
   ```bash
   # In separate terminal
   cd /opt/data/trading/mcp_ib
   PYTHONPATH=src python -m ibmcp --transport sse --port 8100
   ```

3. Dry run mode disabled:
   ```bash
   python orchestrator.py settings set dry_run_mode false
   ```

---

## Running Stock Analysis

### Via CLI

```bash
python orchestrator.py analyze NVDA --type stock
```

### Via Claude Code

```
Analyze NVDA stock
```

The stock-analysis skill auto-invokes.

### Output

```
tradegent_knowledge/knowledge/analysis/stock/NVDA_{YYYYMMDDTHHMM}.yaml
```

---

## Running Earnings Analysis

### Via CLI

```bash
python orchestrator.py analyze NVDA --type earnings
```

### Via Claude Code

```
Pre-earnings analysis for NVDA
```

### When to Use

- 1-2 weeks before earnings
- IV expansion opportunity
- Event-driven setup

---

## Analysis Phases

### 1. Data Quality Check

Validates data freshness and completeness:

| Check | Requirement |
|-------|-------------|
| Price data age | < 15 minutes |
| News age | < 24 hours |
| Analyst data | Available |
| Historical data | ≥ 3 months |

### 2. Pre-Analysis Context

Retrieves historical knowledge:

```yaml
Tool: rag_hybrid_context
Input: {"ticker": "NVDA", "query": "stock analysis", "analysis_type": "stock-analysis"}
```

Returns:
- Similar past analyses
- Known risks from graph
- Previous strategies and outcomes
- Detected biases

### 3. Real-Time Data

Fetches current market data:

```yaml
# Current price
Tool: mcp__ib-mcp__get_stock_price
Input: {"symbol": "NVDA"}

# Historical OHLCV
Tool: mcp__ib-mcp__get_historical_data
Input: {"symbol": "NVDA", "duration": "3 M", "bar_size": "1 day"}

# News/catalyst (use built-in WebSearch)
Tool: WebSearch
Input: {"query": "NVDA news catalyst 2026"}
```

### 4. Scenario Modeling

Four scenarios with probabilities:

| Scenario | Description | P(%) |
|----------|-------------|------|
| Bull | Best case, all catalysts fire | 15-25% |
| Base | Most likely outcome | 40-50% |
| Bear | Negative but manageable | 20-30% |
| Disaster | Tail risk, thesis broken | 5-10% |

### 5. Bias Countermeasures

For each identified bias:
- **Rule**: What to do
- **Implementation**: How to do it
- **Checklist**: Verification steps
- **Mantra**: Mental reminder

### 6. Do Nothing Gate

Must pass ALL checks:

| Check | Threshold | Fail Action |
|-------|-----------|-------------|
| Expected Value | > 5% | Skip trade |
| Confidence | > 60% | Skip trade |
| Risk/Reward | > 2:1 | Skip trade |
| Edge exists | Yes | Skip trade |

### 7. Recommendation

| Action | Meaning |
|--------|---------|
| BUY | Open long position |
| SELL | Exit or short |
| WATCH | Add to watchlist |
| SKIP | No action |

---

## Post-Analysis Indexing

**Required after every analysis:**

```yaml
# 1. Extract entities to graph
Tool: graph_extract
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/stock/NVDA_20250120.yaml"}

# 2. Embed for semantic search
Tool: rag_embed
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/stock/NVDA_20250120.yaml"}

# 3. Push to knowledge repo
Tool: mcp__github-vl__push_files
```

---

## Batch Analysis

### Analyze All Enabled Stocks

```bash
python orchestrator.py watchlist --limit 10
```

### Analyze Upcoming Earnings

```bash
python orchestrator.py run-due
```

### Priority Order

Stocks processed by:
1. Priority (10 = highest)
2. Earnings proximity
3. Add date

---

## Viewing Results

### List Recent Analyses

```bash
ls -la tradegent/analyses/
```

### Read Analysis

```bash
cat tradegent_knowledge/knowledge/analysis/stock/NVDA_20250120T0900.yaml
```

### Search Past Analyses

```yaml
Tool: rag_search
Input: {"query": "NVDA earnings surprise", "ticker": "NVDA", "top_k": 5}
```

---

## Troubleshooting

### "Dry run mode enabled"

```bash
python orchestrator.py settings set dry_run_mode false
```

### "IB MCP not connected"

Start the IB MCP server:
```bash
cd /opt/data/trading/mcp_ib
PYTHONPATH=src python -m ibmcp --transport sse --port 8100
```

### "No context available"

First analysis for ticker. Will proceed without historical context.

### "Gate failed"

Analysis complete but trade not recommended:
- Check EV calculation
- Review scenarios
- Consider WATCH instead

---

## Related Documentation

- [Skills Guide](skills-guide.md)
- [CLI Reference](cli-reference.md)
- [Scanners](scanners.md)
