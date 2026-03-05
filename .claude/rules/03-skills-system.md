# Skills System

Skills in `.claude/skills/` auto-invoke based on context. Each skill has:
- YAML frontmatter with metadata and triggers
- Pre-analysis context retrieval (RAG + Graph)
- Real-time data gathering (IB MCP)
- Post-save hooks (index to knowledge base)
- Chaining to related skills

## Skill Index

| Skill | Version | Category |
|-------|---------|----------|
| **stock-analysis** | v2.7 | Analysis |
| **earnings-analysis** | v2.6 | Analysis |
| **research-analysis** | v2.1 | Research |
| **ticker-profile** | v2.1 | Knowledge |
| **trade-journal** | v2.1 | Trade Mgmt |
| **watchlist** | v2.1 | Trade Mgmt |
| **post-trade-review** | v2.1 | Learning |
| **post-earnings-review** | v1.0 | Learning |
| **report-validation** | v1.0 | Validation |
| **scan** | v1.0 | Scanning |
| **detected-position** | v1.0 | Monitoring |
| **options-management** | v1.0 | Options |
| **fill-analysis** | v1.0 | Learning |
| **position-close-review** | v1.0 | Monitoring |
| **expiration-review** | v1.0 | Learning |
| **iplan-review** | v1.0 | Quality Assurance |

> **Note**: `visualize-analysis` is DEPRECATED - UI renders from database.

## Skill Workflow Pattern

```
PRE-ANALYSIS          EXECUTE            POST-SAVE
    │                    │                   │
    ▼                    ▼                   ▼
┌─────────┐        ┌─────────┐        ┌─────────────────────┐
│ RAG +   │───────▶│  Run    │───────▶│ [1] DB (kb_* tables)│
│ Graph   │        │ Skill   │        │ [2] RAG (pgvector)  │
│ Context │        │ Phases  │        │ [3] Graph (Neo4j)   │
└─────────┘        └─────────┘        └─────────────────────┘
```

## Step 1: Pre-Analysis Context

```yaml
Tool: rag_hybrid_context
Input: {"ticker": "NVDA", "query": "earnings analysis", "analysis_type": "earnings-analysis"}
```

**How to apply learning context:**
1. Read framework lessons and check if conditions match
2. Note any patterns or signals active for the ticker
3. Adjust probabilities based on historical calibration
4. Document which rules were applied in the analysis

## Step 2: Real-Time Data

```yaml
Tool: mcp__ib-mcp__get_stock_price
Input: {"symbol": "NVDA"}

Tool: mcp__ib-mcp__get_historical_data
Input: {"symbol": "NVDA", "duration": "3 M", "bar_size": "1 day"}
```

## Steps 3-5: Execute, Save, Index

1. Read `SKILL.md` from `tradegent_knowledge/skills/{skill-name}/`
2. Follow workflow steps exactly
3. Use `template.yaml` structure for output
4. **ALWAYS save to `tradegent_knowledge/knowledge/` folder regardless of gate result**
5. Auto-ingest hook handles indexing (DB → RAG → Graph)

## Gate Results and Saving

**CRITICAL: Always save analysis YAML files regardless of gate result.**

| Gate Result | Recommendation | Save YAML | Why |
|-------------|----------------|-----------|-----|
| PASS | BUY/SELL | ✅ Yes | Execute trade |
| MARGINAL | WATCH | ✅ Yes | Monitor for entry |
| FAIL | NO_POSITION | ✅ Yes | Trading bot signals, statistics, learning |

FAIL results are essential for:
- Trading bot guidance (close positions, avoid entry)
- Historical statistics and win rate tracking
- Future learning and model calibration

## Workflow Chains

```
scan → earnings-analysis → watchlist → trade-journal → post-trade-review
         ↓                                    ↓
    stock-analysis                      ticker-profile
```

**Automatic chaining:**
- Analysis recommends WATCH → triggers watchlist skill
- Trade journal exit → triggers post-trade-review
- Scanner high score → triggers analysis skill
- Earnings release (T+1) → triggers post-earnings-review
- New analysis saved → triggers report-validation
