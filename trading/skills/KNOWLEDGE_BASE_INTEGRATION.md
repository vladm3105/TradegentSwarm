# Knowledge Base Integration

This document describes how to integrate trading skills with the Knowledge Graph and RAG systems.

## Post-Execution Hooks

After saving any analysis file to `trading/knowledge/`, run these commands to index the content:

### 1. Graph Extraction (entities and relationships)

```bash
cd /opt/data/trading_light_pilot/trader
python orchestrator.py graph extract <saved_file>
```

This extracts:
- Tickers and Companies
- Strategies and Patterns
- Risks and Biases
- Catalysts and Events
- Relationships between entities

### 2. RAG Embedding (semantic search)

```bash
cd /opt/data/trading_light_pilot/trader
python orchestrator.py rag embed <saved_file>
```

This enables:
- Semantic search across all analyses
- Similar analysis retrieval
- Historical context for new analyses

### 3. Verification

```bash
# Check extraction status
python orchestrator.py graph status

# Check embedding status
python orchestrator.py rag status
```

## Skill-Specific Entities

| Skill | Primary Entities Extracted |
|-------|---------------------------|
| `earnings-analysis` | Ticker, Company, EarningsEvent, Catalyst, Product, Executive, Sector, Industry |
| `stock-analysis` | Ticker, Catalyst, Sector, Industry, Pattern, Signal, Risk |
| `research-analysis` | Company, Product, MacroEvent, Risk, Industry |
| `trade-journal` | Trade, Ticker, Strategy, Structure, Bias, Pattern |
| `post-trade-review` | Learning, Bias, Strategy, Pattern |
| `ticker-profile` | Ticker, Company, Sector, Industry, Product, Risk, Pattern |
| `watchlist` | Ticker, Catalyst, Signal |

## Pre-Analysis Context

Before starting an analysis, the system can inject relevant historical context:

```python
from rag.hybrid import build_analysis_context

# Get context before analysis
context = build_analysis_context(ticker="NVDA", analysis_type="earnings-analysis")
# Returns: past analyses, peer comparisons, known biases, strategy performance
```

This is automatically called when using `orchestrator.py analyze`.

## Automatic Processing

When using the trading service daemon (`service.py`), new files in `trading/knowledge/`
are automatically detected and processed. Manual extraction is only needed for:
- Bulk imports
- Re-processing existing documents
- Testing

## MCP Tool Usage

Claude Code skills can use MCP tools directly:

```yaml
# Get context before analysis
Tool: rag_hybrid_context
Input: {"ticker": "NVDA", "query": "earnings analysis", "analysis_type": "earnings-analysis"}

# After saving analysis
Tool: graph_extract
Input: {"file_path": "trading/knowledge/analysis/earnings/NVDA_20260219T0900.yaml"}

Tool: rag_embed
Input: {"file_path": "trading/knowledge/analysis/earnings/NVDA_20260219T0900.yaml"}
```
