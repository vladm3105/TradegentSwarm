# Skills Guide

Skills are Claude Code automation workflows that produce structured trading analyses. They auto-invoke based on conversation context.

---

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Skill Workflow                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────┐   ┌───────────────┐   ┌───────────────┐     │
│  │ Pre-Analysis  │──▶│    Execute    │──▶│   Post-Save   │     │
│  │   Context     │   │    Phases     │   │    Hooks      │     │
│  └───────────────┘   └───────────────┘   └───────────────┘     │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│    RAG + Graph         IB Data +           Graph + RAG         │
│    Historical          Skill Logic         Index + Push        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Available Skills

| Skill | Version | Triggers | Output |
|-------|---------|----------|--------|
| **stock-analysis** | v2.5 | "stock analysis", "technical" | `analysis/stock/` |
| **earnings-analysis** | v2.5 | "earnings analysis", "pre-earnings" | `analysis/earnings/` |
| **research-analysis** | v2.1 | "research", "macro analysis" | `analysis/research/` |
| **ticker-profile** | v2.1 | "ticker profile", "what do I know about" | `analysis/ticker-profiles/` |
| **trade-journal** | v2.1 | "log trade", "bought", "sold" | `trades/` |
| **watchlist** | v2.1 | "watchlist", "add to watchlist" | `watchlist/` |
| **post-trade-review** | v2.1 | "review trade", "what did I learn" | `reviews/` |
| **scan** | v1.0 | "scan", "find opportunities" | `watchlist/` |

---

## Core Analysis Skills

### stock-analysis (v2.5)

Comprehensive stock analysis with bias checks and scenario modeling.

**Location:** `tradegent_knowledge/skills/stock-analysis/`

**Phases:**
1. Data Quality Check
2. Catalyst Analysis
3. Technical Analysis
4. Fundamental Analysis
5. Scenario Modeling (4 scenarios)
6. Bias Countermeasures
7. Do Nothing Gate
8. Recommendation

**Key Features:**
- Steel-man bear case with scored arguments
- Bias countermeasures (rule + checklist + mantra)
- 4-scenario framework (bull, base, bear, disaster)
- Pre-exit gate for loss aversion
- Falsification criteria

**Do Nothing Gate:**
| Check | Threshold |
|-------|-----------|
| Expected Value | > 5% |
| Confidence | > 60% |
| Risk/Reward | > 2:1 |
| Edge | Not priced in |

### earnings-analysis (v2.5)

Pre-earnings analysis focused on IV, consensus, and event risk.

**Location:** `tradegent_knowledge/skills/earnings-analysis/`

**Additional Phases:**
- Consensus Estimates
- IV Analysis
- Earnings History
- Post-Earnings Drift

---

## Knowledge Skills

### ticker-profile

Aggregated knowledge about a ticker from all sources.

**Triggers:** "ticker profile", "what do I know about NVDA"

**Output Sections:**
- Company overview
- Historical analyses
- Trade history
- Known risks
- Effective strategies
- Detected biases

### research-analysis

Macro, sector, or thematic research.

**Triggers:** "research", "macro analysis", "sector analysis"

---

## Trade Management Skills

### trade-journal

Log trade entries and exits.

**Triggers:** "log trade", "bought NVDA", "sold position"

**Required Fields:**
- Symbol, direction, size
- Entry/exit price
- Thesis
- Risk parameters

### watchlist

Add tickers to monitoring list.

**Triggers:** "watchlist", "add to watchlist", "watch this"

**Required Fields:**
- Entry trigger (price, event, combined)
- Invalidation condition
- Expiration (max 30 days)
- Priority

### post-trade-review

Post-trade analysis and learning extraction.

**Triggers:** "review trade", "closed trade", "what did I learn"

**Output:**
- What worked/didn't work
- Bias detection
- Lessons learned
- Process improvements

---

## Skill Workflow

### Pre-Analysis Context

Before executing, skills retrieve historical context:

```yaml
Tool: rag_hybrid_context
Input: {"ticker": "NVDA", "query": "stock analysis"}
```

Returns:
- Similar past analyses
- Graph context (peers, risks, strategies)
- Detected biases

### Post-Save Indexing

After saving output, skills MUST index:

```yaml
# 1. Graph extraction
Tool: graph_extract
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/stock/NVDA_20250120.yaml"}

# 2. RAG embedding
Tool: rag_embed
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/stock/NVDA_20250120.yaml"}

# 3. Push to repo
Tool: mcp__github-vl__push_files
Input: {
  "owner": "vladm3105",
  "repo": "tradegent-knowledge",
  "files": [...]
}
```

---

## Skill Chaining

Skills automatically chain based on outcomes:

```
                    ┌──────────────┐
                    │     scan     │
                    └──────┬───────┘
                           │
              Score ≥7.5   │   Score 5.5-7.4
           ┌───────────────┴───────────────┐
           ▼                               ▼
    ┌──────────────┐               ┌──────────────┐
    │   analysis   │               │  watchlist   │
    └──────┬───────┘               └──────────────┘
           │
           │ Recommendation
           │
    WATCH  │   BUY/SELL
    ───────┴──────────
           │
           ▼
    ┌──────────────┐
    │trade-journal │
    └──────┬───────┘
           │
           │ Exit
           ▼
    ┌──────────────┐
    │ post-trade   │
    │   review     │
    └──────────────┘
```

| Trigger | Chain |
|---------|-------|
| Analysis → WATCH | triggers watchlist |
| Trade journal exit | triggers post-trade-review |
| Scanner score ≥7.5 | triggers analysis |
| Post-trade review | updates ticker-profile |

---

## Creating Custom Skills

### Skill Structure

```
skills/{skill-name}/
├── SKILL.md          # Workflow instructions
└── template.yaml     # Output schema
```

### SKILL.md Format

```markdown
# {Skill Name}

## Workflow

### Phase 1: {Phase Name}
- Step 1
- Step 2

### Phase 2: {Phase Name}
...

## Output

Save to: `knowledge/{category}/{TICKER}_{YYYYMMDDTHHMM}.yaml`

## Chaining

- If X → trigger Y skill
```

### template.yaml Format

```yaml
_meta:
  version: "1.0"
  doc_type: "{doc-type}"
  ticker: "{TICKER}"
  created: "{TIMESTAMP}"

# Sections matching SKILL.md phases
section_1:
  field_1: ""
  field_2: ""

recommendation:
  action: ""
  rationale: ""
```

---

## File Naming

All skill outputs use ISO 8601 format:

```
{TICKER}_{YYYYMMDDTHHMM}.yaml
```

Example: `NVDA_20250120T0900.yaml`

---

## Related Documentation

- [Analysis Workflow](analysis-workflow.md)
- [Knowledge Base](knowledge-base.md)
- [RAG System](../architecture/rag-system.md)
- [Graph System](../architecture/graph-system.md)
